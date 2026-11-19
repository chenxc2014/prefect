"""在临时目录验证发布接口的用途约束，不访问服务或真实任务。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from copy import deepcopy
from uuid import uuid4
from fastapi.testclient import TestClient
from runtime.maxun import fingerprint
from runtime.maxun_relations import MaxunRelations


class CollectorCatalogTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        config = root / 'client.json'
        config.write_text(json.dumps({'env': {'PREFECT_API_AUTH_STRING': 'unit:unit-test-password'}}), encoding='utf-8')
        environment = patch.dict('os.environ', {'CRAWLER_CLIENT_CONFIG': str(config), 'CRAWLER_CATALOG_ROOT': str(root / 'catalog')})
        environment.start()
        self.addCleanup(environment.stop)
        spec = importlib.util.spec_from_file_location('collector_under_test', Path(__file__).with_name('collector.py'))
        self.collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.collector)
        self.client = TestClient(self.collector.app)
        self.addCleanup(self.client.close)
        self.document = json.loads((Path(__file__).resolve().parents[1] / 'deploy/examples/demo-template.json').read_text(encoding='utf-8'))

    def post(self, endpoint, payload):
        return self.client.post(endpoint, json=payload, auth=('unit', 'unit-test-password'))

    def test_guided_release_rechecks_draft_and_keeps_the_old_fixed_version(self):
        from tools.test_maxun import robot

        class Client:
            def __init__(self, *robots):
                self.robots = {item['recording_meta']['id']: deepcopy(item) for item in robots}
                self.duplicates = 0

            def robot(self, identifier):
                return deepcopy(self.robots[identifier])

            def duplicate(self, original, name):
                self.duplicates += 1
                copy = deepcopy(original)
                identifier = str(uuid4())
                copy['recording_meta'].update(id=identifier, name=name)
                self.robots[identifier] = copy
                return deepcopy(copy)

            def request(self, path, payload, method):
                self.robots[path.split('/')[-1]]['recording']['workflow'] = deepcopy(payload['workflow'])

            def encrypt(self, value):
                assert value == ''
                return '已加密空值'

        frozen, draft = robot(), robot()
        frozen_id, draft_id = [item['recording_meta']['id'] for item in (frozen, draft)]
        frozen_steps, draft_steps = [item['recording']['workflow'][0]['what'] for item in (frozen, draft)]
        password = {'action': 'type', 'args': ['#password', '测试密文', 'password']}
        frozen_steps[0].update(action='platformInputDate', args=['#date', '密文', 'text'])
        frozen_steps.append(deepcopy(password))
        doc = {'engine': 'maxun', 'name': '验收任务（Maxun）', 'purpose': 'acceptance', 'task_name': '验收任务',
               'node': 'linux-169', 'task': {'robot_id': frozen_id, 'workflow_sha256': fingerprint(frozen)},
               'bindings': {'begindate': ['workflow.0.what.0.args.1']}, 'defaults': {'begindate': '2026-11-01'},
               'secret_bindings': {'password': ['workflow.0.what.1.args.1']},
               'checks': {'required_files': ['Data/result.csv'], 'min_rows': 1}}
        draft_steps.append(deepcopy(password))
        catalog = self.collector.catalog
        version = catalog.publish(doc)
        store = MaxunRelations(catalog.root / '.maxun-relations')
        store.publication(version, draft_id, frozen_id, fingerprint(draft))
        draft_steps.insert(0, {'action': 'waitForTimeout', 'args': [250]})
        maxun = Client(frozen, draft)
        endpoint = '/api/maxun/releases/' + version
        auth = ('unit', 'unit-test-password')
        with patch('runtime.maxun.MaxunClient', return_value=maxun):
            preview = self.client.get(endpoint, params={'draft': draft_id}, auth=auth).json()
            self.assertTrue(preview['changed'])
            self.assertEqual(preview['issues'], [])
            self.assertNotIn('测试密文', str(preview))
            payload = {'draft': draft_id, 'fingerprint': preview['fingerprint']}
            current_steps = maxun.robots[draft_id]['recording']['workflow'][0]['what']
            current_steps[0]['args'] = [350]
            self.assertEqual(self.post(endpoint, payload).status_code, 409)
            self.assertEqual(maxun.duplicates, 0)
            current_steps[0]['args'] = [250]
            duplicate_date = deepcopy(current_steps[1])
            current_steps.append(duplicate_date)
            blocked = self.client.get(endpoint, params={'draft': draft_id}, auth=auth).json()
            self.assertIn('多个匹配', blocked['issues'][0])
            current_steps.pop()
            response = self.post(endpoint, payload)
            self.assertEqual(response.status_code, 200, response.text)
            renewed_id = response.json()['id']
            self.assertEqual(self.post(endpoint, payload).status_code, 409)
            status = self.client.get('/api/maxun/relations', params={'draft': draft_id}, auth=auth).json()
            self.assertEqual(status['versions'][0]['id'], renewed_id)
            self.assertFalse(status['versions'][0]['changed'])
        renewed = catalog.get(renewed_id)
        self.assertEqual(renewed['bindings']['begindate'], ['workflow.0.what.1.args.1'])
        self.assertEqual(renewed['secret_bindings']['password'], ['workflow.0.what.2.args.1'])
        self.assertEqual(renewed['checks'], doc['checks'])
        self.assertEqual(catalog.get(version), doc)
        actions = maxun.robot(renewed['task']['robot_id'])['recording']['workflow'][0]['what']
        self.assertEqual(actions[1]['action'], 'platformInputDate')
        self.assertEqual(actions[2]['args'][1], '已加密空值')

    def test_guided_release_blocks_missing_site_actions_and_calendar(self):
        from runtime.maxun_release import prepare
        where = {'url': 'https://example.com/delivery'}
        date = {'action': 'platformInputDate', 'args': ['#from', '示例密文', 'lbx-delivery']}
        export = {'action': 'platformLbxExport', 'args': []}
        before = [{'where': where, 'what': [date, export]}]
        current = [{'where': where, 'what': [{'action': 'type', 'args': ['#from', '示例密文', 'text']}]}]
        _, _, issues = prepare({'bindings': {'begindate': ['workflow.0.what.0.args.1']}}, before, current)
        self.assertEqual(len(issues), 2)
        self.assertIn('开始日期', issues[0])
        self.assertIn('老百姓配送数据导出', issues[1])

    def prefect_health(self, health_error=None, database_error=None):
        client = AsyncMock()
        client.api_healthcheck.return_value = health_error
        client.read_flow_runs.return_value = []
        client.read_flow_runs.side_effect = database_error
        with patch('prefect.client.orchestration.get_client') as get_client:
            get_client.return_value.__aenter__.return_value = client
            response = self.client.get('/api/platform', auth=('unit', 'unit-test-password'))
        self.assertEqual(response.status_code, 200)
        return response.json()['prefect']['state'], client

    def test_prefect_is_unavailable_when_database_fails_despite_healthy_process(self):
        state, client = self.prefect_health(database_error=RuntimeError('Service Unavailable'))
        self.assertEqual(state, 'unavailable')

    def test_prefect_is_ready_when_database_query_returns_empty_list(self):
        state, client = self.prefect_health()
        self.assertEqual(state, 'ready')
        client.read_flow_runs.assert_awaited_once_with(limit=1)

    def test_prefect_skips_database_query_when_http_healthcheck_fails(self):
        state, client = self.prefect_health(health_error=RuntimeError('Service Unavailable'))
        self.assertEqual(state, 'unavailable')
        client.read_flow_runs.assert_not_awaited()

    def test_valid_publish_preserves_classification_in_listing(self):
        self.document.update(purpose='business', task_name='千金商品流向')
        response = self.post('/api/templates', self.document)
        self.assertEqual(response.status_code, 200)
        listed = self.client.get('/api/templates', auth=('unit', 'unit-test-password')).json()
        self.assertEqual(listed[0]['purpose'], 'business')
        self.assertEqual(listed[0]['task_name'], '千金商品流向')
        self.assertEqual(listed[0]['id'], response.json()['id'])

    def test_unclassified_publish_is_rejected_without_writing(self):
        self.document.pop('purpose')
        response = self.post('/api/templates', self.document)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.collector.catalog.list(), [])

    def test_maxun_rejects_missing_purpose_before_duplicating_robot(self):
        with patch('runtime.maxun.MaxunClient') as maxun:
            response = self.post('/api/maxun/publish', {'robot_id': 'irrelevant'})
        self.assertEqual(response.status_code, 400)
        maxun.assert_not_called()

    def test_maxun_publish_registers_source_and_fixed_robot(self):
        import copy
        from uuid import uuid4
        from runtime.maxun_relations import MaxunRelations
        from tools.test_maxun import robot
        source = robot()
        published = copy.deepcopy(source)
        published['recording_meta']['id'] = str(uuid4())

        class Client:
            def robot(self, identifier):
                return copy.deepcopy(published if identifier == published['recording_meta']['id'] else source)

            def duplicate(self, original, name):
                return copy.deepcopy(published)

            def request(self, path, data=None, method=None):
                return {}

        payload = {'robot_id': source['recording_meta']['id'], 'purpose': 'business', 'task_name': '业务任务', 'name': '本地发布测试'}
        with patch('runtime.maxun.MaxunClient', return_value=Client()):
            response = self.post('/api/maxun/publish', payload)
        self.assertEqual(response.status_code, 200)
        reference = MaxunRelations(self.collector.catalog.root / '.maxun-relations').records('publications')[0]
        self.assertEqual(reference['template_id'], response.json()['id'])
        self.assertEqual(reference['source_robot_id'], source['recording_meta']['id'])
        self.assertEqual(reference['published_robot_id'], published['recording_meta']['id'])


if __name__ == '__main__':
    unittest.main()
