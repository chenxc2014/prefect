"""生成仅供本项目使用的服务、证书和受限配置。"""
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path('/opt/crawler-dev')
PRIVATE = ROOT / 'private'
CONTROL = ROOT / 'control'


def write(path, text, mode=0o600):
    path.write_text(text, encoding='utf-8')
    path.chmod(mode)


def run(*args):
    subprocess.run(args, check=True)


def main():
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONTROL.mkdir(parents=True, exist_ok=True)
    credentials_file = PRIVATE / 'credentials.json'
    if not credentials_file.exists():
        write(credentials_file, json.dumps({'auth': 'crawlerdev:' + secrets.token_hex(24),
                                            'postgres': secrets.token_hex(24)}))
    credentials = json.loads(credentials_file.read_text())
    if not (PRIVATE / 'ca.pem').exists():
        run('openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '730',
            '-keyout', str(PRIVATE / 'ca.key'), '-out', str(PRIVATE / 'ca.pem'),
            '-subj', '/CN=Crawler Development CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    if not (PRIVATE / 'server.pem').exists():
        run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(PRIVATE / 'server.key'),
            '-out', str(PRIVATE / 'server.csr'), '-subj', '/CN=192.168.1.169')
        write(PRIVATE / 'server.ext', 'subjectAltName=IP:192.168.1.169,IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\n')
        run('openssl', 'x509', '-req', '-days', '365', '-in', str(PRIVATE / 'server.csr'),
            '-CA', str(PRIVATE / 'ca.pem'), '-CAkey', str(PRIVATE / 'ca.key'), '-CAcreateserial',
            '-out', str(PRIVATE / 'server.pem'), '-extfile', str(PRIVATE / 'server.ext'))
    for key in PRIVATE.glob('*.key'):
        key.chmod(0o600)
    auth = credentials['auth']
    postgres = credentials['postgres']
    write(CONTROL / '.env', f'POSTGRES_PASSWORD={postgres}\nPREFECT_AUTH={auth}\n')
    write(CONTROL / 'compose.yml', '''name: crawler-dev
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: prefect
      POSTGRES_DB: prefect
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U prefect -d prefect"]
      interval: 5s
      timeout: 5s
      retries: 20
  prefect:
    image: prefecthq/prefect:3.9.2-python3.12
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      PREFECT_SERVER_DATABASE_CONNECTION_URL: postgresql+asyncpg://prefect:${POSTGRES_PASSWORD}@postgres:5432/prefect
      PREFECT_SERVER_API_AUTH_STRING: ${PREFECT_AUTH}
      PREFECT_SERVER_UI_API_URL: https://192.168.1.169:8443/api
      PREFECT_SERVER_ANALYTICS_ENABLED: "false"
    command: ["prefect", "server", "start", "--host", "0.0.0.0"]
    ports:
      - "127.0.0.1:4200:4200"
volumes:
  postgres_data:
''')
    write(CONTROL / 'nginx.conf', f'''pid /run/crawler-dev-nginx.pid;
error_log /var/log/nginx/crawler-dev-error.log;
events {{ worker_connections 1024; }}
http {{
  access_log /var/log/nginx/crawler-dev-access.log;
  server {{
    listen 8443 ssl;
    server_name 192.168.1.169;
    ssl_certificate {PRIVATE}/server.pem;
    ssl_certificate_key {PRIVATE}/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    location / {{
      proxy_pass http://127.0.0.1:4200;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_read_timeout 300s;
    }}
  }}
}}
''')
    write(Path('/etc/systemd/system/crawler-dev-gateway.service'), '''[Unit]
Description=网爬开发环境 HTTPS 网关
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=simple
ExecStartPre=/usr/sbin/nginx -t -c /opt/crawler-dev/control/nginx.conf
ExecStart=/usr/sbin/nginx -c /opt/crawler-dev/control/nginx.conf -g "daemon off;"
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
''', 0o644)
    config = {'env': {'PREFECT_API_URL': 'https://192.168.1.169:8443/api',
                       'PREFECT_API_AUTH_STRING': auth,
                       'SSL_CERT_FILE': str(PRIVATE / 'ca.pem'),
                       'CRAWLER_RUN_ROOT': '/var/lib/crawler-dev/runs',
                       'PREFECT_SERVER_ANALYTICS_ENABLED': 'false'},
              'pool': 'dev-linux', 'queue': 'node-169', 'node': 'dev-linux-169', 'limit': 2,
              'release_root': str(ROOT / 'releases/dev-v1'), 'deployment': 'linux-169', 'os': 'Linux'}
    write(PRIVATE / 'client.json', json.dumps(config, indent=2))
    write(Path('/etc/systemd/system/crawler-dev-worker.service'), '''[Unit]
Description=网爬开发环境 Linux Worker
After=network-online.target crawler-dev-gateway.service
Wants=network-online.target
[Service]
Type=simple
User=crawlerdev
Group=crawlerdev
WorkingDirectory=/opt/crawler-dev/releases/dev-v1
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=HOME=/var/lib/crawler-dev
ExecStart=/opt/crawler-dev/venv/bin/python tools/worker.py /etc/crawler-dev/client.json
Restart=on-failure
RestartSec=10
KillMode=control-group
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
''', 0o644)
    client_directory = Path('/etc/crawler-dev')
    client_directory.mkdir(mode=0o750, exist_ok=True)
    public_client = dict(config)
    public_client['env'] = dict(config['env'], SSL_CERT_FILE=str(client_directory / 'ca.pem'))
    write(client_directory / 'client.json', json.dumps(public_client, indent=2), 0o640)
    write(client_directory / 'ca.pem', (PRIVATE / 'ca.pem').read_text(), 0o644)
    run('chown', '-R', 'root:crawlerdev', str(client_directory))
    run('chmod', '750', str(client_directory))
    run('chmod', '755', str(ROOT), str(ROOT / 'releases'), str(ROOT / 'releases/dev-v1'), str(ROOT / 'venv'))
    run('chown', 'crawlerdev:crawlerdev', '/var/lib/crawler-dev')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'crawler-dev-gateway')
    addresses = {'192.168.1.167'}
    connection = os.environ.get('SSH_CONNECTION', '').split()
    if connection:
        addresses.add(str(ipaddress.ip_address(connection[0])))
    for address in addresses:
        rule = f'rule family="ipv4" source address="{address}/32" port port="8443" protocol="tcp" accept'
        run('firewall-cmd', '--permanent', '--add-rich-rule', rule)
        run('firewall-cmd', '--add-rich-rule', rule)
    print('独立服务配置完成；认证信息只保存在受限配置文件')


if __name__ == '__main__':
    main()
