"""核对明确清单的机器人、模板和运行时间后补关联；默认只预览。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from runtime.catalog import Catalog
from runtime.maxun import MaxunClient, fingerprint
from runtime.maxun_relations import MaxunRelations
from tools.dev_api import DevApi


def backfill(catalog, client, api, mapping, apply=False):
    document = catalog.get(mapping['template_id'])
    if document['task']['robot_id'] != mapping['published_robot_id']:
        raise ValueError('发布机器人与模板引用不一致')
    if fingerprint(client.robot(mapping['published_robot_id'])) != document['task']['workflow_sha256']:
        raise ValueError('发布流程与模板校验值不一致')
    source = client.robot(mapping['source_robot_id'])
    plan = []
    for item in mapping['executions']:
        flow = api.request('/flow_runs/' + item['prefect_run_id'])
        if flow.get('parameters', {}).get('template_id') != mapping['template_id']:
            raise ValueError('历史运行所属模板不一致')
        native = client.request('/api/sdk/robots/' + item['robot_id'] + '/runs/' + item['maxun_run_id'])['data']
        native = native.get('dataValues', native)
        if native.get('robotMetaId') != item['robot_id'] or native.get('runId') != item['maxun_run_id']:
            raise ValueError('Maxun 运行与机器人不一致')
        started = datetime.strptime(native['startedAt'], '%m/%d/%Y, %I:%M:%S %p').replace(tzinfo=timezone.utc)
        flow_started = datetime.fromisoformat(flow['start_time'].replace('Z', '+00:00'))
        if abs((started - flow_started).total_seconds()) > 2:
            raise ValueError('两侧执行时间不匹配，拒绝猜测关联')
        plan.append(dict(item, template_id=mapping['template_id'], parameters=flow.get('parameters', {}).get('parameters', {})))
    snapshot = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for pattern in ('*.json', '.heads/*.json') for path in catalog.root.glob(pattern)}
    if apply:
        store = MaxunRelations(catalog.root / '.maxun-relations')
        store.publication(mapping['template_id'], mapping['source_robot_id'], mapping['published_robot_id'], fingerprint(source))
        for item in plan:
            store.execution(**item)
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for pattern in ('*.json', '.heads/*.json') for path in catalog.root.glob(pattern)}
        if after != snapshot:
            raise RuntimeError('原模板或活动指针发生变化，请核对')
    return {'applied': apply, 'verified_executions': len(plan), 'versions_and_heads_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--mapping', default='deploy/maxun-relations-backfill.json')
    parser.add_argument('--catalog', default='/var/lib/crawler-dev/catalog')
    parser.add_argument('--client-config', default='/etc/crawler-dev/client.json')
    args = parser.parse_args()
    print(json.dumps(backfill(Catalog(args.catalog), MaxunClient(), DevApi(args.client_config), json.loads(Path(args.mapping).read_text(encoding='utf-8')), args.apply), ensure_ascii=False))
