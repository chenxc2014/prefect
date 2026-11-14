"""仅管理 Linux 169 的在线设计验证环境，不连接 Windows 节点。"""
from pathlib import Path
import importlib.util
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('crawler_ssh', ROOT / '.tmp/crawler-dev/manage.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
action = sys.argv[1]
client = ssh.connect('169')
try:
    if action == 'inspect':
        command = '''hostname
free -m
nproc
df -h /opt /var
command -v docker podman node npm git || true
docker version --format '{{.Server.Version}}' 2>/dev/null || true
systemctl is-active crawler-dev-server crawler-dev-collector crawler-dev-worker nginx
ss -lnt | head -25
ls -l /etc/nginx/conf.d
openssl x509 -in /etc/crawler-dev/server.crt -noout -ext subjectAltName 2>/dev/null || true
'''
        sys.exit(ssh.execute(client, command, timeout=40))
    elif action == 'command':
        sys.exit(ssh.execute(client, ' '.join(sys.argv[2:]), timeout=50))
    elif action == 'gateway-info':
        sys.exit(ssh.execute(client, '''systemctl list-unit-files | grep crawler
find /etc/crawler-dev -maxdepth 2 -type f -printf '%f\\n'
docker ps --format '{{.Names}} {{.Image}}'
''', timeout=30))
    elif action == 'portal-rollout':
        from datetime import datetime
        backup = '/opt/crawler-dev/backups/portal-' + datetime.now().strftime('%Y%m%d-%H%M%S')
        ssh.execute(client, 'mkdir -p ' + backup + ' && chmod 700 ' + backup, timeout=20)
        files = {
            'deploy/web/collector.html': '/opt/crawler-dev/releases/dev-v1/deploy/web/collector.html',
            'tools/collector.py': '/opt/crawler-dev/releases/dev-v1/tools/collector.py',
            'deploy/maxun/gateway.py': '/opt/crawler-dev/maxun/gateway.py',
        }
        with client.open_sftp() as sftp:
            for local, remote in files.items():
                with sftp.open(remote, 'rb') as original:
                    content = original.read()
                with sftp.open(backup + '/' + Path(local).name, 'wb') as archived:
                    archived.write(content)
                with sftp.open(remote, 'wb') as handle:
                    handle.write((ROOT / local).read_bytes())
        code = ssh.execute(client, 'python3.12 /opt/crawler-dev/maxun/gateway.py && /opt/crawler-dev/venv/bin/python -m py_compile /opt/crawler-dev/releases/dev-v1/tools/collector.py && systemctl restart crawler-dev-collector && systemctl is-active crawler-dev-collector crawler-dev-gateway', timeout=50)
        print('变更前文件备份：' + backup)
        sys.exit(code)
    elif action in ('stage','transfer','storage-build','prepare-native','finalize','sync'):
        ssh.execute(client, 'mkdir -p /opt/crawler-dev/maxun && chmod 700 /opt/crawler-dev/maxun', timeout=20)
        with client.open_sftp() as sftp:
            for path in (ROOT / 'deploy/maxun').iterdir():
                if path.is_file():
                    with sftp.open('/opt/crawler-dev/maxun/'+path.name, 'wb') as handle:
                        handle.write(path.read_bytes())
        scripts={'stage':('install','pull.sh'),'transfer':('transfer','transfer.sh'),'storage-build':('storage-build','build-storage.sh'),'prepare-native':('prepare-native','prepare-native.sh'),'finalize':('finalize','finalize.sh')}
        if action != 'sync':
            unit,script=scripts[action]
            sys.exit(ssh.execute(client, f'systemd-run --unit=crawler-maxun-{unit} --property=WorkingDirectory=/opt/crawler-dev/maxun /bin/bash /opt/crawler-dev/maxun/{script}', timeout=20))
    elif action == 'progress':
        sys.exit(ssh.execute(client, 'systemctl show crawler-maxun-install -p ActiveState -p Result; journalctl -u crawler-maxun-install -n 18 --no-pager; df -h /', timeout=25))
    else:
        raise ValueError('未知操作')
finally:
    client.close()
