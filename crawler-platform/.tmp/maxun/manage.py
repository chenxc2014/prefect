"""仅管理 Linux 169 的在线设计验证环境，不连接 Windows 节点。"""
from pathlib import Path
import importlib.util
import sys
import logging
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('crawler_ssh', ROOT / '.tmp/crawler-dev/manage.py')
ssh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssh)
action = sys.argv[1]
logging.getLogger('paramiko.transport').setLevel(logging.CRITICAL)
for attempt in range(3):
    try:
        client = ssh.connect('169')
        break
    except (ssh.paramiko.AuthenticationException,ssh.paramiko.BadHostKeyException):
        raise
    except (ssh.paramiko.SSHException,OSError,EOFError):
        if attempt==2:raise RuntimeError('169 SSH 握手连续中断，请检查外网映射；未更换主机密钥或连接其他节点') from None
        time.sleep(2+attempt*2)
try:
    if action == 'verify-release':
        import hashlib
        import json
        report={'node':'linux-169','windows_167_accessed':False,'files':[]}
        names=['runtime/catalog.py','runtime/maxun.py','tools/collector.py','tools/portal_auth.py','deploy/web/collector.html','deploy/web/maxun-recorder.js']
        mappings={name:'/opt/crawler-dev/releases/dev-v1/'+name for name in names}
        for name in ('browser-actions.cjs','recorder-compat.cjs','patch-installed.py','apply-recorder-compat.py','extract-web.py'):
            mappings['deploy/maxun/'+name]='/opt/crawler-dev/maxun/'+name
        with client.open_sftp() as sftp:
            for name,remote in mappings.items():
                local=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                with sftp.open(remote,'rb') as handle:deployed=hashlib.sha256(handle.read()).hexdigest()
                report['files'].append({'path':name,'sha256':local,'matches':local==deployed})
        report['passed']=all(item['matches'] for item in report['files'])
        (ROOT/'doc/千金商品流向部署一致性.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'passed':report['passed'],'checked_files':len(report['files']),'mismatch':[item['path'] for item in report['files'] if not item['matches']]},ensure_ascii=False))
        sys.exit(0 if report['passed'] else 1)
    elif action == 'artifact-diagnose':
        import shlex
        code='''import json,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote,unquote
sys.path.insert(0,"/opt/crawler-dev/releases/dev-v1")
from runtime.maxun import MaxunClient
client=MaxunClient();print({key:client.config.get(key) for key in ("storage_public_url","storage_internal_url")})
robots=client.request("/api/sdk/robots")["data"]
for robot in robots:
 if not robot["recording_meta"]["name"].startswith("平台执行 ·"):continue
 identifier=robot["recording_meta"]["id"]
 try:run=client.request("/api/sdk/robots/"+identifier+"/runs/1e888dca-6124-481f-8af9-cfa89d5c2db8")["data"]
 except RuntimeError:continue
 for name,item in (run.get("binaryOutput") or {}).items():
  value=item if isinstance(item,str) else item.get("data","")
  if not value.startswith("http"):continue
  relative=value[len(client.config["storage_public_url"]):]
  for label,suffix in [("原路径",relative),("百分号再次编码",quote(relative,safe="/")),("还原编码",unquote(relative))]:
   try:
    with urlopen(client.config["storage_internal_url"]+suffix,timeout=10) as response:print(name,label,response.status,len(response.read()))
   except Exception as error:print(name,label,type(error).__name__,getattr(error,"code",None))
'''
        sys.exit(ssh.execute(client,'python3.12 -c '+shlex.quote(code),timeout=45))
    elif action == 'inspect':
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
    elif action == 'sso-rollout':
        from datetime import datetime
        backup = '/opt/crawler-dev/backups/sso-code-' + datetime.now().strftime('%Y%m%d-%H%M%S')
        ssh.execute(client, 'mkdir -p ' + backup + ' && chmod 700 ' + backup, timeout=20)
        names = ['runtime/auth.py', 'tools/portal_auth.py', 'tools/collector.py', 'deploy/web/login.html', 'deploy/web/auth-client.js', 'deploy/web/collector.html', 'deploy/web/suite-theme.css', 'deploy/web/suite-theme.js', 'deploy/web/maxun-recorder.js', 'deploy/linux/install-sso.py']
        with client.open_sftp() as sftp:
            for name in names:
                remote = '/opt/crawler-dev/releases/dev-v1/' + name
                try:
                    with sftp.open(remote, 'rb') as handle:
                        data = handle.read()
                    with sftp.open(backup + '/' + name.replace('/', '__'), 'wb') as handle:
                        handle.write(data)
                except FileNotFoundError:
                    pass
                with sftp.open(remote, 'wb') as handle:
                    handle.write((ROOT / name).read_bytes())
            with sftp.open('/opt/crawler-dev/maxun/gateway.py', 'wb') as handle:
                handle.write((ROOT / 'deploy/maxun/gateway.py').read_bytes())
            for name in ('apply-branding.py', 'extract-web.py'):
                with sftp.open('/opt/crawler-dev/maxun/' + name, 'wb') as handle:
                    handle.write((ROOT / 'deploy/maxun' / name).read_bytes())
        code = ssh.execute(client, '/opt/crawler-dev/venv/bin/python -m py_compile /opt/crawler-dev/releases/dev-v1/tools/portal_auth.py /opt/crawler-dev/releases/dev-v1/tools/collector.py /opt/crawler-dev/releases/dev-v1/runtime/auth.py && python3.12 /opt/crawler-dev/maxun/apply-branding.py && systemctl restart crawler-dev-collector && python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/install-sso.py && systemctl is-active crawler-dev-collector crawler-dev-gateway crawler-dev-worker crawler-dev-server', timeout=50)
        print('认证代码变更前备份：' + backup)
        sys.exit(code)
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
