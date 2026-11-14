"""通过已授权的 SSH 连接管理本次开发环境，凭据不写入日志。"""
from pathlib import Path
import base64
import json
import sys
import time

import paramiko

ROOT = Path(__file__).resolve().parents[2]
KEY = Path(r'C:\Users\chenx\.ssh\id_ed25519_chenxc')
# 当前工作区位于外网，仅通过映射端口连接 169；167 暂停本地操作。
SSH_ENDPOINTS = {'169': ('cm800.gicp.net', 9722)}


def connect(host):
    if host == '167':
        raise RuntimeError('当前外网开发环境禁止连接 Windows 167；须等待用户恢复授权和网络条件')
    if host not in SSH_ENDPOINTS:
        raise ValueError('未配置该节点的 SSH 入口')
    hostname, port = SSH_ENDPOINTS[host]
    client = paramiko.SSHClient()
    client.load_system_host_keys(str(KEY.parent / 'known_hosts'))
    extra = ROOT / '.tmp' / 'ssh169_known_hosts'
    if extra.exists():
        client.load_host_keys(str(extra))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    # 外网映射必须仍匹配原内网节点的已信任主机密钥，不自动接受陌生服务器。
    trusted = client.get_host_keys().lookup('192.168.1.' + host)
    if not trusted:
        raise RuntimeError('缺少原节点的可信 SSH 主机密钥，停止连接')
    alias = hostname if port == 22 else f'[{hostname}]:{port}'
    for key_type, key in trusted.items():
        client.get_host_keys().add(alias, key_type, key)
    client.connect(hostname, port=port, username='root',
                   key_filename=str(KEY), look_for_keys=False, allow_agent=False,
                   timeout=20, banner_timeout=30, auth_timeout=30)
    return client


def execute(client, command, timeout=120):
    _, out, err = client.exec_command(command, timeout=timeout)
    channel = out.channel
    start = time.monotonic()
    while True:
        if channel.recv_ready():
            sys.stdout.write(channel.recv(65536).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if channel.recv_stderr_ready():
            sys.stdout.write(channel.recv_stderr(65536).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            return channel.recv_exit_status()
        if time.monotonic() - start > timeout:
            raise TimeoutError('远端命令超时；请核查远端是否仍在执行')
        time.sleep(.1)


def powershell(code):
    prefix = "$ProgressPreference='SilentlyContinue'; $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new(); "
    payload = base64.b64encode((prefix + code).encode('utf-16-le')).decode('ascii')
    return 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + payload


def main():
    host, action = sys.argv[1:3]
    if host not in {'169', '167'}:
        raise ValueError('仅允许本次授权的两台服务器')
    client = connect(host)
    try:
        if action == 'connection-check':
            return execute(client, 'hostname; uname -sr; systemctl is-active crawler-dev-server crawler-dev-collector crawler-dev-worker', timeout=30)
        if action == 'verify-qjdyf-result':
            sys.path.insert(0, str(ROOT))
            from tools.verify_qjdyf_result import verify
            verify()
            return 0
        if action == 'collect-debug' and host == '169':
            import stat
            with client.open_sftp() as sftp:
                roots = sorted((item for item in sftp.listdir_attr('/var/lib/crawler-dev/runs') if item.filename.startswith('collect-')), key=lambda item:item.st_mtime,reverse=True)
                remote='/var/lib/crawler-dev/runs/'+roots[0].filename+'/engine/Data/Task_0/result/screenshots'
                shots=sftp.listdir(remote)
                if shots:
                    sftp.get(remote+'/'+shots[-1],str(ROOT/'.local/sites/qjdyf/automatic.png'))
            print('自动执行截图已保存到受限目录')
            return 0
        if action == 'snapshot-engine':
            remote = '/opt/crawler-dev/easyspider/requirements.lock' if host == '169' else 'D:/CrawlerDev/easyspider/requirements.lock'
            with client.open_sftp() as sftp:
                with sftp.open(remote,'rb') as handle:
                    (ROOT / 'deploy/locks' / ('easyspider-linux.lock.txt' if host == '169' else 'easyspider-windows.lock.txt')).write_bytes(handle.read())
            print('执行器依赖快照已保存：'+host)
            return 0
        if action == 'run-qjdyf':
            sys.path.insert(0, str(ROOT))
            from tools.run_qjdyf import run
            run(sys.argv[3] if len(sys.argv)>3 else None)
            return 0
        if action == 'prepare-site-account':
            path = ROOT / '.local/site-accounts.json'
            if not path.exists():
                path.write_text(json.dumps({'qjdyf-test': {'username': '', 'password': ''}}, ensure_ascii=False, indent=2), encoding='utf-8')
            print('账号占位配置已准备：.local/site-accounts.json，未输出认证值')
            return 0
        if action == 'sync-accounts':
            accounts = json.loads((ROOT / '.local/site-accounts.json').read_text(encoding='utf-8-sig'))
            if any(not item.get('username') or not item.get('password') for item in accounts.values()):
                raise ValueError('请先填写账号配置；不输出配置内容')
            target = '/etc/crawler-dev/accounts.json' if host == '169' else 'D:/CrawlerDev/private/accounts.json'
            with client.open_sftp() as sftp:
                with sftp.open(target, 'wb') as handle:
                    handle.write(json.dumps(accounts, ensure_ascii=False).encode())
                if host == '169':
                    sftp.chmod(target, 0o640)
            if host == '169':
                return execute(client, 'chown root:crawlerdev /etc/crawler-dev/accounts.json')
            return 0
        if action == 'verify-collect-matrix':
            sys.path.insert(0, str(ROOT))
            from tools.verify_collect import verify_matrix
            verify_matrix()
            return 0
        if action == 'push-browser' and host == '167':
            with client.open_sftp() as sftp:
                for name in ('chrome-win64.zip', 'chromedriver-win64.zip', 'stable.json'):
                    sftp.put(str(ROOT / '.local/browser-assets' / name), 'D:/CrawlerDev/easyspider/downloads/' + name)
            print('固定版本浏览器资源已通过内网分发')
            return 0
        if action == 'verify-collect':
            sys.path.insert(0, str(ROOT))
            from tools.verify_collect import verify
            verify()
            return 0
        if action == 'push-easyspider':
            import zipfile
            package = ROOT / '.local/easyspider-executor.zip'
            source = ROOT / 'vendor/easyspider'
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in (source / 'ExecuteStage').rglob('*.py'):
                    archive.write(file, file.relative_to(source).as_posix())
                archive.write(source / 'ElectronJS/stealth.min.js', 'ElectronJS/stealth.min.js')
                archive.write(source / 'LICENSE', 'LICENSE')
            remote = '/opt/crawler-dev-bootstrap/easyspider-executor.zip' if host == '169' else 'D:/CrawlerDev/bootstrap/easyspider-executor.zip'
            with client.open_sftp() as sftp:
                sftp.put(str(package), remote)
            print('固定版本执行器源码包已上传，包含许可证')
            return 0
        if action == 'api':
            sys.path.insert(0, str(ROOT))
            from tools.dev_api import DevApi
            api = DevApi()
            print(json.dumps({'health': api.request('/health'),
                'deployments': [d['name'] for d in api.request('/deployments/filter', {})]}, ensure_ascii=False))
            return 0
        if action == 'check-ui':
            sys.path.insert(0, str(ROOT))
            from tools.check_ui import check_ui
            check_ui()
            return 0
        if action in ('ui-browser', 'collector-browser'):
            import subprocess
            import threading
            sys.path.insert(0, str(ROOT))
            from tools.ui_preview import create_preview
            remote_ui = len(sys.argv) > 3 and sys.argv[3] == 'remote'
            server = create_preview(remote_ui=remote_ui)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                import os
                env = dict(os.environ, CRAWLER_UI_TEST_SOURCE='169-deployed-ui' if remote_ui else 'local-build')
                return subprocess.call(['node', 'tools/collector-browser-check.mjs' if action == 'collector-browser' else 'tools/ui-browser-check.mjs'], cwd=str(ROOT), env=env)
            finally:
                server.shutdown()
                server.server_close()
        if action == 'release-ui' and host == '169':
            import hashlib
            import tarfile
            source = ROOT / 'vendor' / 'prefect' / 'ui-v2' / 'dist'
            if not (source / 'index.html').is_file():
                raise RuntimeError('必须先构建前端')
            output = ROOT / '.local' / 'prefect-ui-zh-cn.tar.gz'
            with tarfile.open(output, 'w:gz') as package:
                for file in source.rglob('*'):
                    if file.is_file():
                        package.add(file, arcname=file.relative_to(source).as_posix())
            remote = '/opt/crawler-dev-bootstrap/prefect-ui-zh-cn.tar.gz'
            with client.open_sftp() as sftp:
                sftp.put(str(output), remote)
            print('前端资源包 SHA-256：' + hashlib.sha256(output.read_bytes()).hexdigest())
            return execute(client, 'python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/release_ui.py ' + remote, timeout=180)
        if action == 'verify':
            sys.path.insert(0, str(ROOT))
            from tools.verify_remote import verify
            verify(connect, ROOT)
            return 0
        if action == 'snapshot':
            directory = ROOT / 'deploy' / 'locks'
            directory.mkdir(exist_ok=True)
            remote = '/opt/crawler-dev/private/linux-requirements.lock' if host == '169' else 'D:/CrawlerDev/private/windows-requirements.lock'
            with client.open_sftp() as sftp:
                with sftp.open(remote, 'rb') as handle:
                    content = handle.read()
            (directory / ('linux.lock.txt' if host == '169' else 'windows.lock.txt')).write_bytes(content)
            print('节点 ' + host + ' 完整依赖清单已保存')
            return 0
        if action == 'inventory' and host == '167':
            code = r"""
$ErrorActionPreference='Continue'
hostname
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory | Format-List
Get-Command python,python3,py,docker -All -ErrorAction SilentlyContinue | Select-Object Name,Source | Format-Table
Get-ChildItem 'C:\','D:\' -Directory -ErrorAction SilentlyContinue | Select-Object FullName | Format-Table
Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw|chrome|firefox|chromedriver|geckodriver).*'} | Group-Object Name,ExecutablePath | Select-Object Name,Count | Format-Table
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in 4200,4201,5432,8080,8099} | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table
Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free | Format-Table
"""
            return execute(client, powershell(code))
        if action == 'inventory' and host == '169':
            return execute(client, "python3 --version; nproc; systemctl is-active firewalld; getenforce; curl -I --max-time 15 https://pypi.org/simple/prefect/; curl -I --max-time 15 https://download.docker.com/linux/centos/docker-ce.repo; ls -ld /opt/crawler* /etc/crawler* 2>/dev/null")
        if action == 'script':
            local = Path(sys.argv[3]).resolve()
            if not local.is_relative_to(ROOT):
                raise ValueError('只上传工作区内脚本')
            remote_root = '/opt/crawler-dev-bootstrap' if host == '169' else 'D:/CrawlerDev/bootstrap'
            if host == '169':
                code = 'mkdir -p /opt/crawler-dev-bootstrap && chmod 700 /opt/crawler-dev-bootstrap'
            else:
                code = powershell("New-Item -ItemType Directory -Force -Path 'D:\\CrawlerDev\\bootstrap' | Out-Null")
            if execute(client, code):
                return 1
            remote = remote_root + '/' + local.name
            with client.open_sftp() as sftp:
                if local.suffix.lower() == '.ps1':
                    with sftp.open(remote, 'wb') as handle:
                        handle.write(local.read_text(encoding='utf-8-sig').encode('utf-8-sig'))
                else:
                    sftp.put(str(local), remote)
            command = 'bash ' + remote if host == '169' else powershell("& '" + remote.replace('/', '\\') + "'")
            return execute(client, command, timeout=1800)
        if action == 'push':
            remote_root = '/opt/crawler-dev/releases/dev-v1' if host == '169' else 'D:/CrawlerDev/releases/dev-v1'
            with client.open_sftp() as sftp:
                def mkdir(path):
                    try:
                        sftp.stat(path)
                    except FileNotFoundError:
                        parent = path.rsplit('/', 1)[0]
                        if parent and parent != path:
                            mkdir(parent)
                        sftp.mkdir(path)
                for name in ('flows', 'runtime', 'tools', 'deploy'):
                    for local in (ROOT / name).rglob('*'):
                        if local.is_file() and '__pycache__' not in local.parts:
                            relative = local.relative_to(ROOT).as_posix()
                            target = remote_root + '/' + relative
                            mkdir(target.rsplit('/', 1)[0])
                            with sftp.open(target, 'wb') as handle:
                                data = local.read_bytes()
                                if local.suffix.lower() == '.ps1':
                                    data = local.read_text(encoding='utf-8-sig').encode('utf-8-sig')
                                handle.write(data)
            print('开发代码已同步到节点 ' + host)
            return 0
        if action == 'share-config' and host == '169':
            with client.open_sftp() as sftp:
                config = json.loads(sftp.open('/opt/crawler-dev/private/client.json').read())
                ca = sftp.open('/opt/crawler-dev/private/ca.pem').read()
            local_directory = ROOT / '.local'
            local_directory.mkdir(exist_ok=True)
            (local_directory / 'ca.pem').write_bytes(ca)
            local_config = dict(config)
            local_config['env'] = dict(config['env'], SSL_CERT_FILE=str(local_directory / 'ca.pem'))
            (local_directory / 'client.json').write_text(json.dumps(local_config, indent=2), encoding='utf-8')
            windows = connect('167')
            try:
                config['env'] = dict(config['env'], SSL_CERT_FILE='D:\\CrawlerDev\\private\\ca.pem',
                                     CRAWLER_RUN_ROOT='D:\\CrawlerDev\\runs')
                config.update(pool='dev-windows', queue='node-167', node='dev-windows-167', limit=2,
                              release_root='D:\\CrawlerDev\\releases\\dev-v1', deployment='windows-167', os='Windows',
                              log_path='D:\\CrawlerDev\\logs\\worker.log')
                with windows.open_sftp() as sftp:
                    with sftp.open('D:/CrawlerDev/private/client.json', 'wb') as handle:
                        handle.write(json.dumps(config, indent=2).encode('utf-8'))
                    with sftp.open('D:/CrawlerDev/private/ca.pem', 'wb') as handle:
                        handle.write(ca)
            finally:
                windows.close()
            print('开发客户端配置与公开 CA 已保存到本地和 167；未复制 CA 私钥')
            return 0
        raise ValueError('未知操作')
    finally:
        client.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main() or 0)
