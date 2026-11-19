"""仅更新 Linux 169 的记住密码功能，部署前核对旧版并备份，失败自动恢复。"""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
RELEASE = '/opt/crawler-dev/releases/dev-v1/'
FILES = ('runtime/auth.py', 'tools/portal_auth.py', 'deploy/web/login.html')
spec = importlib.util.spec_from_file_location('crawler_ssh', ROOT / '.tmp/crawler-dev/manage.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
client = ssh.connect('169')
originals = {}
changed = []
backup = '/opt/crawler-dev/backups/remember-login-' + datetime.now().strftime('%Y%m%d-%H%M%S')
try:
    with client.open_sftp() as sftp:
        for name in FILES:
            with sftp.open(RELEASE + name, 'rb') as handle:
                originals[name] = handle.read()
            baseline = (ROOT / 'vendor/prefect/crawler-platform' / name).read_bytes()
            if originals[name].replace(b'\r\n', b'\n') != baseline.replace(b'\r\n', b'\n'):
                raise RuntimeError('部署版本与仓库基线不符，停止覆盖：' + name)
        if ssh.execute(client, 'mkdir -m 700 ' + backup, timeout=20):
            raise RuntimeError('无法创建部署备份')
        for name, content in originals.items():
            with sftp.open(backup + '/' + name.replace('/', '__'), 'wb') as handle:
                handle.write(content)
        for name in FILES:
            remote = RELEASE + name
            with sftp.open(remote + '.remember.tmp', 'wb') as handle:
                handle.write((ROOT / name).read_bytes())
            sftp.chmod(remote + '.remember.tmp', sftp.stat(remote).st_mode & 0o777)
            sftp.posix_rename(remote + '.remember.tmp', remote)
            changed.append(name)
            with sftp.open(remote, 'rb') as handle:
                if sha256(handle.read()).digest() != sha256((ROOT / name).read_bytes()).digest():
                    raise RuntimeError('部署摘要不一致：' + name)
    command = (
        '/opt/crawler-dev/venv/bin/python -m py_compile '
        + ' '.join(RELEASE + name for name in FILES if name.endswith('.py'))
        + ' && systemctl restart crawler-dev-collector'
        + ' && systemctl is-active crawler-dev-collector crawler-dev-gateway crawler-dev-worker crawler-dev-server'
    )
    if ssh.execute(client, command, timeout=40):
        raise RuntimeError('服务检查失败')
    report = {
        'date': datetime.now(timezone.utc).isoformat(),
        'node': 'linux-169', 'backup': backup,
        'files': [{'path': name, 'sha256': sha256((ROOT / name).read_bytes()).hexdigest()} for name in FILES],
        'remember_days': 30, 'normal_session_hours': 8,
        'cookie': {'secure': True, 'httpOnly': True, 'sameSite': 'lax'},
        'password_stored_in_browser_storage': False,
        'windows_167_accessed': False, 'passed': True,
    }
    (ROOT / 'doc/记住密码部署记录.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
except Exception:
    if changed:
        with client.open_sftp() as sftp:
            for name in changed:
                remote = RELEASE + name
                with sftp.open(remote + '.remember.rollback', 'wb') as handle:
                    handle.write(originals[name])
                sftp.chmod(remote + '.remember.rollback', sftp.stat(remote).st_mode & 0o777)
                sftp.posix_rename(remote + '.remember.rollback', remote)
        result = ssh.execute(client, 'systemctl restart crawler-dev-collector && systemctl is-active crawler-dev-collector', timeout=40)
        print('部署失败，已还原原文件；恢复检查返回值：' + str(result))
    raise
finally:
    client.close()
