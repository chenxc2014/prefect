"""验证用途与运行状态独立，且同节点的调度不串到其他版本。"""
from datetime import datetime, timezone
from types import SimpleNamespace as Record
import unittest
from runtime.task_status import summarize


class TaskStatusTest(unittest.TestCase):
    def setUp(self):
        self.templates = [{'id': 'version-a', 'node': 'linux-169'}, {'id': 'version-b', 'node': 'linux-169'}]
        self.deployment = Record(parameters={'template_id': 'version-a'}, paused=False)

    def run_record(self, version, state):
        return Record(parameters={'template_id': version}, state_type=Record(value=state), id='run-id', end_time=None, start_time=datetime.now(timezone.utc), expected_start_time=None)

    def summarize(self, schedules, runs):
        return summarize(self.templates, {'linux-169': self.deployment}, {'linux-169': schedules}, runs)['templates']

    def test_running_and_latest_results_are_isolated_by_version(self):
        result = self.summarize([], [self.run_record('version-a', 'RUNNING'), self.run_record('version-b', 'FAILED'), self.run_record('version-a', 'COMPLETED'), self.run_record('old-version', 'RUNNING')])
        self.assertEqual(result['version-a']['running'], 1)
        self.assertEqual(result['version-a']['latest']['state'], 'RUNNING')
        self.assertEqual(result['version-b']['running'], 0)
        self.assertEqual(result['version-b']['latest']['state'], 'FAILED')

    def test_schedule_parameters_override_deployment_and_do_not_leak(self):
        result = self.summarize([Record(parameters={'template_id': 'version-b'}, active=True)], [])
        self.assertEqual(result['version-a']['schedule'], 'none')
        self.assertEqual(result['version-b']['schedule'], 'enabled')

    def test_paused_and_missing_schedules_are_distinct(self):
        self.deployment.paused = True
        result = self.summarize([Record(parameters={}, active=True)], [])
        self.assertEqual(result['version-a']['schedule'], 'paused')
        self.assertEqual(result['version-b']['schedule'], 'none')
        self.assertIsNone(result['version-b']['latest'])

    def test_pending_and_paused_runs_are_reported_without_running(self):
        result = self.summarize([], [self.run_record('version-a', 'SCHEDULED'), self.run_record('version-a', 'PAUSED')])
        self.assertEqual(result['version-a']['queued'], 2)
        self.assertEqual(result['version-a']['running'], 0)


if __name__ == '__main__':
    unittest.main()
