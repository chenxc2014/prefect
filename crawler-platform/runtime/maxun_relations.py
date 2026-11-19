"""保存 Maxun 设计、发布和执行的明确关联，不改写已发布模板或机器人。"""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import UUID, uuid4


class MaxunRelations:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('CRAWLER_MAXUN_RELATIONS_ROOT', '/var/lib/crawler-dev/catalog/.maxun-relations'))

    @staticmethod
    def template_id(value):
        if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
            raise ValueError('关联的任务版本号无效')
        return value

    def save(self, category, key, document):
        directory = self.root / category
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / (key + '.' + uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True), encoding='utf-8')
        temporary.replace(directory / (key + '.json'))

    def publication(self, template_id, source_robot_id, published_robot_id, source_fingerprint=None):
        template_id = self.template_id(template_id)
        document = {'template_id': template_id, 'source_robot_id': str(UUID(source_robot_id)),
                    'published_robot_id': str(UUID(published_robot_id)), 'source_fingerprint': source_fingerprint,
                    'linked_at': datetime.now(timezone.utc).isoformat()}
        self.save('publications', template_id, document)
        return document

    def execution(self, template_id, prefect_run_id, robot_id, maxun_run_id=None, parameters=None):
        robot_id = str(UUID(robot_id))
        document = {'template_id': self.template_id(template_id), 'prefect_run_id': str(UUID(prefect_run_id)),
                    'robot_id': robot_id, 'maxun_run_id': str(UUID(maxun_run_id)) if maxun_run_id else None,
                    'parameters': {key: value for key, value in (parameters or {}).items() if key in ('begindate', 'enddate')},
                    'linked_at': datetime.now(timezone.utc).isoformat()}
        self.save('executions', robot_id, document)
        return document

    def records(self, category):
        return [json.loads(path.read_text(encoding='utf-8')) for path in sorted((self.root / category).glob('*.json'))]

    def draft_versions(self, catalog, source_id):
        drafts = {item['template_id']: item for item in self.records('publications')
                  if item['source_robot_id'] == source_id}
        return [(info, drafts[info['id']]) for info in catalog.list() if info['id'] in drafts]


def build_snapshot(catalog, client, flow_runs, store=None):
    """仅返回展示必需的数据，不返回输入密文、账号、Cookie 或完整日志。"""
    from runtime.catalog import canonical, classification
    from runtime.maxun import fingerprint
    import hashlib
    store = store or MaxunRelations(catalog.root / '.maxun-relations')
    robots = client.request('/api/sdk/robots')['data']
    by_robot = {robot['recording_meta']['id']: robot for robot in robots}
    active = {item['id']: item for item in catalog.list()}
    publications = {item['template_id']: item for item in store.records('publications')}
    executions = store.records('executions')
    runs = {str(run.id): run for run in flow_runs}
    groups, by_template, linked = {}, {}, set()

    def robot_summary(identifier):
        robot = by_robot.get(identifier)
        if not robot:
            return {'id': identifier, 'name': '机器人已不存在或无法访问', 'missing': True}
        meta = robot['recording_meta']
        actions = Counter(action.get('action', '') for pair in robot.get('recording', {}).get('workflow', []) for action in pair.get('what', []))
        return {'id': identifier, 'name': meta['name'], 'missing': False, 'step_count': sum(actions.values()),
                'actions': dict(actions), 'updated_at': meta.get('updatedAt')}

    for path in sorted(catalog.root.glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        if document.get('engine') != 'maxun':
            continue
        template_id = path.stem
        metadata_path = catalog.root / '.metadata' / path.name
        metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else document
        info = active.get(template_id)
        if not info:
            labels = classification(metadata) if metadata.get('purpose') else {'purpose': 'unclassified', 'task_name': document.get('name', '')}
            info = dict(labels, id=template_id, name=document.get('name', ''), task_key=hashlib.sha256(canonical([labels['purpose'], labels['task_name']])).hexdigest())
        group = groups.setdefault(info['task_key'], {'task_key': info['task_key'], 'task_name': info['task_name'], 'purpose': info['purpose'], 'templates': [], 'drafts': [], 'publications': [], 'executions': []})
        group['templates'].append({'id': template_id, 'name': info['name'], 'active': template_id in active})
        by_template[template_id] = group
        reference = publications.get(template_id, {})
        published_id = document['task']['robot_id']
        if reference and reference['published_robot_id'] != published_id:
            raise ValueError('机器人关联与固定模板引用不一致')
        group['publications'].append(dict(robot_summary(published_id), template_id=template_id, active=template_id in active, source_robot_id=reference.get('source_robot_id')))
        linked.add(published_id)
        source_id = reference.get('source_robot_id')
        if source_id:
            linked.add(source_id)
            previous = next((item for item in group['drafts'] if item['id'] == source_id), None)
            draft_rank = (template_id in active, reference['linked_at'])
            if not previous or draft_rank > (previous['active_template_id'] is not None, previous['published_at']):
                source = by_robot.get(source_id)
                changed = fingerprint(source) != reference['source_fingerprint'] if source and reference.get('source_fingerprint') else None
                entry = dict(robot_summary(source_id), changed_since_publish=changed, published_at=reference['linked_at'],
                             active_template_id=template_id if template_id in active else None)
                if previous:
                    group['drafts'][group['drafts'].index(previous)] = entry
                else:
                    group['drafts'].append(entry)

    for reference in executions:
        group = by_template.get(reference['template_id'])
        if not group:
            continue
        robot_id = reference['robot_id']
        linked.add(robot_id)
        flow = runs.get(reference['prefect_run_id'])
        state = flow.state_type.value if flow and flow.state_type else None
        maxun_state = None
        if robot_id in by_robot and reference.get('maxun_run_id'):
            raw = client.request('/api/sdk/robots/' + robot_id + '/runs/' + reference['maxun_run_id'])['data']
            maxun_state = raw.get('dataValues', raw).get('status')
        at = (flow.start_time or flow.expected_start_time).isoformat() if flow else reference['linked_at']
        group['executions'].append(dict(reference, robot_name=robot_summary(robot_id)['name'], platform_state=state, maxun_state=maxun_state, at=at))
    for group in groups.values():
        group['templates'].sort(key=lambda item: not item['active'])
        group['executions'].sort(key=lambda item: item['at'], reverse=True)
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'robot_count': len(robots), 'groups': list(groups.values()),
            'independent': [robot_summary(identifier) for identifier in by_robot if identifier not in linked]}
