"""在临时目录验证发布接口的用途约束，不访问服务或真实任务。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient


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
