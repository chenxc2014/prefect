"""保留故障现场，正常重启本项目原生数据库，核验查询并生成可恢复备份。"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shlex
import sys

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('crawler_ssh', root / '.tmp/crawler-dev/manage.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
client = ssh.connect('169')
backup = '/opt/crawler-dev/backups/postgres-shm-' + datetime.now().strftime('%Y%m%d-%H%M%S')
code = r'''
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

backup = Path(sys.argv[1])
backup.mkdir(mode=0o700)
def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

# 仅作为故障现场副本；恢复后的 pg_dump 才用于常规逻辑恢复。
run('tar', '-C', '/var/lib/pgsql', '-czf', str(backup / 'fault-snapshot.tgz'), 'data')
run('systemctl', 'restart', 'postgresql')
query = ('runuser', '-u', 'postgres', '--', 'psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', 'crawler_dev')
for attempt in range(20):
    result = subprocess.run((*query, '-c', 'SELECT 1'), capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip() == '1':
        break
    time.sleep(0.5)
else:
    raise RuntimeError('数据库重启后查询仍失败，保留故障副本，停止后续操作')
counts = run(*query, '-c', 'SELECT count(*) FROM flow_run; SELECT count(*) FROM deployment;', capture_output=True, text=True).stdout.splitlines()
dump = backup / 'crawler_dev.dump'
with dump.open('wb') as output:
    run('runuser', '-u', 'postgres', '--', 'pg_dump', '-Fc', 'crawler_dev', stdout=output)
dump.chmod(0o600)
run('pg_restore', '--list', str(dump), stdout=subprocess.DEVNULL)
digest = hashlib.sha256(dump.read_bytes()).hexdigest()
(backup / 'crawler_dev.dump.sha256').write_text(digest + '  crawler_dev.dump\n')
run('systemctl', 'start', 'crawler-dev-server')
run('systemctl', 'is-active', 'postgresql', 'crawler-dev-server', 'crawler-dev-collector', 'crawler-dev-worker', 'crawler-dev-gateway')
print(json.dumps({'database_query': 'passed', 'flow_runs': int(counts[0]), 'deployments': int(counts[1]), 'backup': str(backup), 'dump_sha256': digest, 'dump_catalog_valid': True}))
'''
try:
    _, output, error = client.exec_command('python3.12 -c ' + shlex.quote(code) + ' ' + shlex.quote(backup), timeout=55)
    result = output.read().decode('utf-8')
    errors = error.read().decode('utf-8')
    status = output.channel.recv_exit_status()
    print(result)
    if errors:
        print(errors)
    if status:
        raise RuntimeError('数据库恢复返回失败：' + str(status))
    details = json.loads(result.splitlines()[-1])
    report = {
        'date': datetime.now(timezone.utc).isoformat(), 'node': 'linux-169',
        'failure': 'PostgreSQL 共享内存段丢失，运行记录接口返回 503',
        'missing_segment': '/PostgreSQL.1543530526',
        'removal_trigger': '尚未确认，不推断为登录改动或定时清理',
        'recovery': details, 'windows_167_accessed': False,
    }
    (root / 'doc/Prefect调度监控恢复记录.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
finally:
    client.close()
