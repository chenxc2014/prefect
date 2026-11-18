"""为现有 HTTPS 网关安装统一会话适配，保留服务端和 Worker 的原认证。"""
from datetime import datetime
import grp
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess

directory = Path('/opt/crawler-dev/control')
private = Path('/etc/crawler-dev/sso.json')
if not private.exists():
    private.write_text(json.dumps({'gateway_key': secrets.token_urlsafe(48), 'platform_origin': 'https://192.168.1.169:8443', 'maxun_origin': 'https://192.168.1.169:9443', 'origins': ['https://192.168.1.169:8443', 'https://192.168.1.169:9443']}))
    private.chmod(0o640)
    os.chown(private, 0, grp.getgrnam('crawlerdev').gr_gid)
settings = json.loads(private.read_text())
key = settings['gateway_key']
backup = Path('/opt/crawler-dev/backups') / ('sso-gateway-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(mode=0o700, parents=True)
paths = (directory / 'nginx.conf', directory / 'maxun.conf')
originals = {path: path.read_bytes() for path in paths}
for path, data in originals.items():
    (backup / path.name).write_bytes(data)


def auth_location(name, machine):
    return '''  location = /_crawler_''' + name + ''' {
    internal;
    proxy_pass http://127.0.0.1:8081/auth/check;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header Cookie $http_cookie;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-Original-Method $request_method;
    proxy_set_header X-Original-Upgrade $http_upgrade;
    proxy_set_header X-Allow-Machine "''' + machine + '''";
    proxy_set_header X-Crawler-Gateway-Key "''' + key + '''";
  }
'''


tls = '''  server_name 192.168.1.169;
  ssl_certificate /opt/crawler-dev/private/server.pem;
  ssl_certificate_key /opt/crawler-dev/private/server.key;
  ssl_protocols TLSv1.2 TLSv1.3;
  client_max_body_size 16m;
'''
proxy_headers = '''    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300s;
'''

main = '''pid /run/crawler-dev-nginx.pid;
error_log /var/log/nginx/crawler-dev-error.log;
events { worker_connections 1024; }
http {
  include /opt/crawler-dev/control/maxun.conf;
  access_log /var/log/nginx/crawler-dev-access.log;
  server {
  listen 8443 ssl;
''' + tls + auth_location('browser', '0') + auth_location('machine', '1') + '''
  location = / { return 302 /collector/; }
  location = /collector { return 302 /collector/; }
  location = /collector/auth/check { return 404; }
  location /collector/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
  }
  location = /ui-settings {
    proxy_pass http://127.0.0.1:8081/auth/prefect/settings;
    proxy_set_header Host $http_host;
  }
  location = /v2/ui-settings {
    proxy_pass http://127.0.0.1:8081/auth/prefect/settings;
    proxy_set_header Host $http_host;
  }
  location = /api/health { proxy_pass http://127.0.0.1:4200; }
  location /api/ {
    auth_request /_crawler_machine;
    auth_request_set $crawler_authorization $upstream_http_x_prefect_authorization;
    proxy_set_header Authorization $crawler_authorization;
    proxy_pass http://127.0.0.1:4200;
''' + proxy_headers + '''  }
  location = /login { return 303 /collector/login?next=prefect; }
  location = /v2/login { return 303 /collector/open/prefect; }
  location / {
    auth_request /_crawler_browser;
    error_page 401 = @platform_login;
    proxy_pass http://127.0.0.1:4200;
    proxy_set_header Accept-Encoding "";
    sub_filter_once on;
    sub_filter '</head>' '<link rel="stylesheet" href="/collector/auth/theme.css"><script src="/collector/auth/client.js" data-app="prefect"></script><script src="/collector/auth/theme.js" defer></script></head>';
    add_header Cache-Control "no-store" always;
''' + proxy_headers + '''  }
  location @platform_login { return 303 /collector/login?next=prefect; }
  }
}
'''
maxun = '''server {
  listen 9443 ssl;
''' + tls + auth_location('browser', '0') + '''
  include /etc/nginx/mime.types;
  root /opt/crawler-dev/maxun-web;
  index index.html;
  location = /_platform/enter {
    proxy_pass http://127.0.0.1:8081/auth/maxun/enter;
    proxy_set_header Host $http_host;
  }
  location = /_platform/client.js {
    proxy_pass http://127.0.0.1:8081/auth/client.js;
    proxy_set_header Host $http_host;
  }
  location = /_platform/theme.css {
    proxy_pass http://127.0.0.1:8081/auth/theme.css;
    proxy_set_header Host $http_host;
  }
  location = /_platform/theme.js {
    proxy_pass http://127.0.0.1:8081/auth/theme.js;
    proxy_set_header Host $http_host;
  }
  location = /_platform/session {
    proxy_pass http://127.0.0.1:8081/api/auth/me;
    proxy_set_header Host $http_host;
  }
  location = /_platform/relations {
    proxy_pass http://127.0.0.1:8081/api/maxun/relations;
    proxy_set_header Host $http_host;
  }
  location = /_platform/logout {
    proxy_pass http://127.0.0.1:8081/auth/maxun/logout;
    proxy_set_header Host $http_host;
  }
  location = /login { return 303 /_platform/enter; }
  location = /register { return 303 /_platform/enter; }
  location = /auth/login { return 403; }
  location = /auth/register { return 403; }
  location = /auth/logout { return 405; }
  location /objects/ {
    auth_request /_crawler_browser;
    proxy_pass http://172.17.0.1:19000/;
    proxy_set_header Host $http_host;
    proxy_request_buffering off;
  }
  location ~ ^/(auth|storage|record|workflow|proxy|api|api-docs|webhook|socket.io)(/|$) {
    auth_request /_crawler_browser;
    proxy_pass http://127.0.0.1:18080;
''' + proxy_headers + '''    proxy_cookie_flags ~ secure httponly samesite=lax;
  }
  location / {
    auth_request /_crawler_browser;
    error_page 401 = @maxun_login;
    if ($cookie_token = "") { return 303 /_platform/enter; }
    sub_filter_once on;
    sub_filter '</head>' '<link rel="stylesheet" href="/_platform/theme.css"><script src="/_platform/client.js" data-app="maxun"></script><script src="/_platform/theme.js" defer></script></head>';
    add_header Cache-Control "no-store" always;
    try_files $uri $uri/ /index.html;
  }
  location @maxun_login { return 303 ''' + settings['platform_origin'] + '''/collector/login?next=maxun; }
}
'''
try:
    (directory / 'nginx.conf').write_text(main)
    (directory / 'maxun.conf').write_text(maxun)
    for path in paths:
        path.chmod(0o640)
    subprocess.run(['/usr/sbin/nginx', '-t', '-c', str(directory / 'nginx.conf')], check=True)
    # 先确认新版认证服务就绪，再让网关开始使用它。
    from urllib.request import urlopen
    from urllib.error import URLError
    import time
    for attempt in range(20):
        try:
            with urlopen('http://127.0.0.1:8081/login', timeout=2) as response:
                assert response.status == 200
            break
        except (URLError, OSError):
            if attempt == 19:
                raise
            time.sleep(0.3)
    os.kill(int(Path('/run/crawler-dev-nginx.pid').read_text()), signal.SIGHUP)
except Exception:
    for path, data in originals.items():
        path.write_bytes(data)
    raise
print('统一登录网关已安装；旧配置备份：' + str(backup))
