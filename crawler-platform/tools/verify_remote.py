"""开发环境真实联调：双系统路由、并发、文件隔离、失败和超时回收。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError

from tools.dev_api import DevApi


def peak(results):
    events = []
    for result in results:
        events.extend([(datetime.fromisoformat(result['started_at']), 1),
                       (datetime.fromisoformat(result['finished_at']), -1)])
    current = maximum = 0
    for _, change in sorted(events, key=lambda item: (item[0], item[1])):
        current += change
        maximum = max(current, maximum)
    return maximum


def collect(connect):
    records = {}
    for host in ('169', '167'):
        root = '/var/lib/crawler-dev/runs' if host == '169' else 'D:/CrawlerDev/runs'
        client = connect(host)
        try:
            with client.open_sftp() as sftp:
                for name in sftp.listdir(root):
                    directory = root + '/' + name
                    try:
                        with sftp.open(directory + '/request.json') as handle:
                            request = json.loads(handle.read())
                        item = {'host': host, 'request': request}
                        for filename in ('result', 'supervisor', 'started'):
                            try:
                                with sftp.open(directory + '/' + filename + '.json') as handle:
                                    item[filename] = json.loads(handle.read())
                            except FileNotFoundError:
                                pass
                        if 'result' in item:
                            with sftp.open(directory + '/download/export.csv', 'rb') as handle:
                                item['actual_sha256'] = hashlib.sha256(handle.read()).hexdigest()
                        records[request['flow_run_id']] = item
                    except (FileNotFoundError, NotADirectoryError):
                        pass
        finally:
            client.close()
    return records


def verify(connect, root):
    from tools.check_ui import check_ui
    check_ui()
    api = DevApi()
    assert api.request('/health') is True
    try:
        api.request('/deployments/filter', {}, authenticated=False)
    except HTTPError as error:
        assert error.code == 401, error.code
    else:
        raise AssertionError('未认证 API 请求未被拒绝')
    deployments = {d['name']: d for d in api.request('/deployments/filter', {})}
    cases = []
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    for deployment, required_os, count in [('linux-169', 'Linux', 4), ('windows-167', 'Windows', 3)]:
        for index in range(count):
            cases.append({'name': f'{stamp}-{deployment}-{index}', 'deployment': deployment,
                          'parameters': {'required_os': required_os, 'hold_seconds': 20},
                          'expected': 'COMPLETED'})
    cases.extend([
        {'name': f'{stamp}-failure', 'deployment': 'linux-169',
         'parameters': {'required_os': 'Linux', 'hold_seconds': 0, 'fail': True}, 'expected': 'FAILED'},
        {'name': f'{stamp}-timeout', 'deployment': 'windows-167',
         'parameters': {'required_os': 'Windows', 'hold_seconds': 30, 'timeout_seconds': 2}, 'expected': 'FAILED'},
    ])
    for case in cases:
        deployment_id = deployments[case['deployment']]['id']
        run = api.request(f'/deployments/{deployment_id}/create_flow_run',
                          {'name': case['name'], 'parameters': case['parameters']})
        case['flow_run_id'] = run['id']
    print(f'已投递 {len(cases)} 个隔离验证任务', flush=True)
    deadline = time.monotonic() + 360
    terminal = {'COMPLETED', 'FAILED', 'CRASHED', 'CANCELLED'}
    previous = None
    while time.monotonic() < deadline:
        for case in cases:
            run = api.request('/flow_runs/' + case['flow_run_id'])
            case['actual'] = run['state']['type']
            case['state_message'] = run['state'].get('message')
        counts = {state: sum(c['actual'] == state for c in cases) for state in sorted({c['actual'] for c in cases})}
        if counts != previous:
            print(json.dumps(counts, ensure_ascii=False), flush=True)
            previous = counts
        if all(c['actual'] in terminal for c in cases):
            break
        time.sleep(2)
    records = collect(connect)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'cases': cases, 'checks': {}, 'artifacts': {}}
    report['checks']['authenticated_https'] = True
    report['checks']['expected_terminal_states'] = all(c.get('actual') == c['expected'] for c in cases)
    success = []
    for case in cases:
        record = records.get(case['flow_run_id'], {})
        report['artifacts'][case['flow_run_id']] = record
        if case['expected'] == 'COMPLETED' and record.get('result'):
            success.append(record['result'])
    report['checks']['all_success_artifacts_present'] = len(success) == 7
    report['checks']['os_routing_correct'] = all(
        records.get(c['flow_run_id'], {}).get('result', {}).get('os') == c['parameters']['required_os']
        for c in cases if c['expected'] == 'COMPLETED')
    report['checks']['unique_run_directories'] = len({r['run_dir'] for r in success}) == 7
    report['checks']['csv_complete_and_hash_verified'] = all(
        records.get(c['flow_run_id'], {}).get('result', {}).get('row_count') == 6 and
        records.get(c['flow_run_id'], {}).get('actual_sha256') == records.get(c['flow_run_id'], {}).get('result', {}).get('sha256')
        for c in cases if c['expected'] == 'COMPLETED')
    report['checks']['child_processes_reaped'] = all(
        records.get(c['flow_run_id'], {}).get('supervisor', {}).get('child_reaped') is True for c in cases)
    report['max_concurrency'] = {os_name: peak([r for r in success if r['os'] == os_name]) for os_name in ('Linux', 'Windows')}
    report['checks']['single_host_concurrency'] = all(value == 2 for value in report['max_concurrency'].values())
    report['checks']['cross_host_overlap'] = peak(success) >= 3
    report['passed'] = all(report['checks'].values())
    report_path = Path(root) / 'doc' / '开发环境验证结果.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'checks': report['checks'],
                      'max_concurrency': report['max_concurrency'], 'report': str(report_path)}, ensure_ascii=False), flush=True)
    if not report['passed']:
        raise RuntimeError('开发环境联调未全部通过，详见验证报告')
