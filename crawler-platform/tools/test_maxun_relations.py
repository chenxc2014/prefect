"""验证明确关联、业务结果隔离与运行时自动登记，不访问实际服务。"""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as Record
import unittest
from uuid import uuid4
from runtime.catalog import Catalog
from runtime.maxun import execute, fingerprint
from runtime.maxun_relations import MaxunRelations, build_snapshot
from tools.test_maxun import robot, FakeClient


class MaxunRelationsTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.catalog = Catalog(self.root / 'catalog')
        self.draft, self.published, self.execution_robot = robot(), robot(), robot()
        self.draft['recording_meta']['name'] = '设计稿'
        self.draft['recording']['workflow'][0]['what'][0]['args'][1] = '不能出现在展示数据中的账号内容'
        self.published['recording_meta']['name'] = '发布副本'
        self.run_id, self.flow_id = str(uuid4()), str(uuid4())
        self.document = {'engine': 'maxun', 'name': '业务任务（Maxun）', 'purpose': 'business', 'task_name': '业务任务', 'node': 'linux-169', 'task': {'robot_id': self.published['recording_meta']['id'], 'workflow_sha256': fingerprint(self.published)}, 'checks': {'required_files': ['Data/result.csv']}}
        self.identifier = self.catalog.publish(self.document)
        self.store = MaxunRelations(self.catalog.root / '.maxun-relations')

    def test_execution_only_saves_public_dates(self):
        self.store.execution(self.identifier, self.flow_id, self.execution_robot['recording_meta']['id'], self.run_id, {'begindate': '2026-11-12', 'password': '私密值', 'account_ref': '账号引用'})
        record = self.store.records('executions')[0]
        self.assertEqual(record['parameters'], {'begindate': '2026-11-12'})
        self.assertNotIn('私密值', json.dumps(record, ensure_ascii=False))

    def test_snapshot_uses_ids_and_keeps_native_success_separate_from_platform_failure(self):
        self.store.publication(self.identifier, self.draft['recording_meta']['id'], self.published['recording_meta']['id'], fingerprint(self.draft))
        self.store.execution(self.identifier, self.flow_id, self.execution_robot['recording_meta']['id'], self.run_id)
        unrelated = robot()
        unrelated['recording_meta']['name'] = '平台执行 · 名字相似也不自动猜测关联'
        robots = [self.draft, self.published, self.execution_robot, unrelated]

        class Client:
            def request(inner, path):
                return {'data': robots if path == '/api/sdk/robots' else {'status': 'success'}}

        flow = Record(id=self.flow_id, state_type=Record(value='FAILED'), start_time=datetime.now(timezone.utc), expected_start_time=None)
        snapshot = build_snapshot(self.catalog, Client(), [flow], self.store)
        group = snapshot['groups'][0]
        self.assertEqual(len(group['drafts']), 1)
        self.assertEqual(len(group['publications']), 1)
        self.assertEqual(group['executions'][0]['platform_state'], 'FAILED')
        self.assertEqual(group['executions'][0]['maxun_state'], 'success')
        self.assertEqual(snapshot['independent'][0]['id'], unrelated['recording_meta']['id'])
        self.assertNotIn('不能出现在展示数据中的账号内容', json.dumps(snapshot, ensure_ascii=False))

    def test_publication_does_not_change_fixed_template(self):
        path = self.catalog.root / (self.identifier + '.json')
        before = path.read_bytes()
        self.store.publication(self.identifier, self.draft['recording_meta']['id'], self.published['recording_meta']['id'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(self.catalog.list()[0]['id'], self.identifier)

    def test_invalid_relation_identifiers_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.publication('../outside', str(uuid4()), str(uuid4()))
        with self.assertRaises(ValueError):
            self.store.execution(self.identifier, '../outside', str(uuid4()))

    def test_runtime_registers_execution_and_native_run_before_business_validation(self):
        task = dict(self.document['task'], parameters={})
        config = {'template_id': self.identifier, 'prefect_run_id': self.flow_id, 'relations_root': str(self.store.root)}
        with self.assertRaisesRegex(RuntimeError, '缺少成功产物'):
            execute(task, {'required_files': ['Data/*.xlsx']}, self.root / 'run', config, FakeClient(self.published))
        stored = self.store.records('executions')[0]
        self.assertEqual(stored['template_id'], self.identifier)
        self.assertEqual(stored['prefect_run_id'], self.flow_id)
        self.assertIsNotNone(stored['maxun_run_id'])


if __name__ == '__main__':
    unittest.main()
