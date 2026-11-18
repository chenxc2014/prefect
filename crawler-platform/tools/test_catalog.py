"""模板版本与参数边界回归，避免运行时污染已发布配置。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from runtime.catalog import Catalog, materialize, validate, classification
from runtime.catalog import bind_account
from runtime.locks import account_lock


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.document = json.loads((Path(__file__).resolve().parents[1] / 'deploy/examples/demo-template.json').read_text(encoding='utf-8'))

    def test_versions_are_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Catalog(directory)
            first = catalog.publish(self.document)
            self.assertEqual(first, catalog.publish(self.document))
            self.document['name'] = '第二版本'
            second = catalog.publish(self.document)
            self.assertNotEqual(first, second)
            self.assertNotEqual(catalog.get(first)['name'], catalog.get(second)['name'])

    def test_classifying_existing_version_preserves_content_and_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Catalog(directory)
            identifier = catalog.publish(self.document)
            version = Path(directory) / (identifier + '.json')
            before = version.read_bytes()
            heads = {path.name: path.read_bytes() for path in (Path(directory) / '.heads').glob('*.json')}
            catalog.classify(identifier, 'business', '千金商品流向')
            self.assertEqual(before, version.read_bytes())
            self.assertEqual(heads, {path.name: path.read_bytes() for path in (Path(directory) / '.heads').glob('*.json')})
            self.assertEqual(catalog.list()[0]['purpose'], 'business')
            self.assertEqual(catalog.list()[0]['id'], identifier)

    def test_grouping_uses_explicit_task_and_purpose_instead_of_name(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Catalog(directory)
            first = catalog.publish(self.document)
            second_document = dict(self.document, name='另一引擎实现')
            second = catalog.publish(second_document)
            catalog.classify(first, 'business', '千金商品流向')
            catalog.classify(second, 'business', '千金商品流向')
            self.assertEqual(len({item['task_key'] for item in catalog.list()}), 1)
            catalog.classify(second, 'acceptance', '千金商品流向')
            self.assertEqual(len({item['task_key'] for item in catalog.list()}), 2)

    def test_legacy_versions_are_unclassified_until_explicitly_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Catalog(directory)
            legacy = dict(self.document)
            legacy.pop('purpose', None)
            legacy.pop('task_name', None)
            catalog.publish(legacy)
            self.assertEqual(catalog.list()[0]['purpose'], 'unclassified')

    def test_invalid_classification_is_rejected(self):
        for metadata in ({}, {'purpose': 'business'}, {'purpose': 'invalid', 'task_name': '任务'}, {'purpose': 'business', 'task_name': '  '}, {'purpose': 'business', 'task_name': '长' * 151}):
            with self.assertRaises(ValueError):
                classification(metadata)
        self.assertEqual(classification({'purpose': 'business', 'task_name': ' 千金商品流向 '}), {'purpose': 'business', 'task_name': '千金商品流向'})

    def test_binding_does_not_change_template(self):
        before = copy.deepcopy(self.document)
        task = materialize(self.document, {'begindate': '2026-11-02'})
        self.assertEqual(task['graph'][2]['parameters']['value'], '2026-11-02')
        self.assertEqual(before, self.document)
        with self.assertRaises(ValueError):
            materialize(self.document, {'unexpected': 'x'})

    def test_active_pointer_keeps_old_version_available(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog=Catalog(directory)
            first=catalog.publish(self.document)
            self.document['defaults']['begindate']='2026-11-02'
            second=catalog.publish(self.document)
            self.assertEqual([item['id'] for item in catalog.list()],[second])
            self.assertEqual(catalog.get(first)['defaults']['begindate'],'2026-11-01')

    def test_binding_cannot_change_execution_configuration(self):
        self.document['bindings']['begindate'] = ['outputFormat']
        with self.assertRaises(ValueError):
            materialize(self.document, {'begindate': 'mysql'})

    def test_artifacts_cannot_escape_run(self):
        self.document['checks']['required_files'] = ['../outside.csv']
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_secret_values_are_injected_only_into_runtime_copy(self):
        self.document['secret_bindings'] = {'password': ['graph.2.parameters.value']}
        task = bind_account(materialize(self.document, {}), self.document, {'password':'private-test-value'})
        self.assertEqual(task['graph'][2]['parameters']['value'], 'private-test-value')
        self.assertNotIn('private-test-value', json.dumps(self.document))

    def test_account_lock_prevents_overlap_and_releases(self):
        with tempfile.TemporaryDirectory() as root:
            with account_lock(root, 'account-a'):
                with self.assertRaises(RuntimeError):
                    with account_lock(root, 'account-a'):
                        pass
                with account_lock(root, 'account-b'):
                    pass
            with account_lock(root, 'account-a'):
                pass


if __name__ == '__main__':
    unittest.main()
