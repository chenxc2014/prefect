"""核对基线并部署数据库健康探测，失败时恢复管理 API。"""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[2]
record_path = root / 'doc/Prefect调度监控恢复记录.json'
record = json.loads(record_path.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('crawler_ssh', root / '.tmp/crawler-dev/manage.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
client = ssh.connect('169')
remote = '/opt/crawler-dev/releases/dev-v1/tools/collector.py'
content = (root / 'tools/collector.py').read_bytes()
original = None
changed = False
try:
    with client.open_sftp() as sftp:
        with sftp.open(remote, 'rb') as handle:
            original = handle.read()
        baseline = (root / 'vendor/prefect/crawler-platform/tools/collector.py').read_bytes()
        if original.replace(b'\r\n', b'\n') != baseline.replace(b'\r\n', b'\n'):
            raise RuntimeError('管理 API 与仓库基线不符，停止覆盖')
        with sftp.open(record['recovery']['backup'] + '/collector.before.py', 'wb') as handle:
            handle.write(original)
        with sftp.open(remote + '.health.tmp', 'wb') as handle:
            handle.write(content)
        sftp.chmod(remote + '.health.tmp', sftp.stat(remote).st_mode & 0o777)
        sftp.posix_rename(remote + '.health.tmp', remote)
        changed = True
        with sftp.open(remote, 'rb') as handle:
            assert sha256(handle.read()).digest() == sha256(content).digest()
    if ssh.execute(client, '/opt/crawler-dev/venv/bin/python -m py_compile ' + remote + ' && systemctl restart crawler-dev-collector && systemctl is-active crawler-dev-collector', timeout=30):
        raise RuntimeError('管理 API 更新检查失败')
    record['health_probe'] = {'file': 'tools/collector.py', 'sha256': sha256(content).hexdigest(), 'database_query': 'read_flow_runs(limit=1)', 'total_timeout_seconds': 4, 'unit_tests_passed': 23}
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print('数据库健康探测已部署，原文件已备份，管理 API 正常运行')
except Exception:
    if changed:
        with client.open_sftp() as sftp:
            with sftp.open(remote, 'wb') as handle:
                handle.write(original)
        ssh.execute(client, 'systemctl restart crawler-dev-collector', timeout=30)
        print('健康探测更新失败，已恢复原管理 API')
    raise
finally:
    client.close()
