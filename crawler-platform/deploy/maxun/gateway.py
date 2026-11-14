"""增加独立 HTTPS 在线设计器入口，检查通过后平滑重载现有网关。"""
from pathlib import Path
import subprocess
if Path('/etc/crawler-dev/sso.json').exists():
    # 后续普通发版继续保留已安装的统一登录网关。
    subprocess.run(['python3.12', '/opt/crawler-dev/releases/dev-v1/deploy/linux/install-sso.py'], check=True)
    raise SystemExit(0)
if subprocess.check_output(['getenforce'],text=True).strip()=='Enforcing':
    ports=subprocess.check_output(['semanage','port','-l'],text=True)
    if not any(line.startswith('http_port_t') and '9443' in line for line in ports.splitlines()):
        subprocess.run(['semanage','port','-a','-t','http_port_t','-p','tcp','9443'],check=True)
    path='/opt/crawler-dev/maxun-web(/.*)?'
    contexts=subprocess.check_output(['semanage','fcontext','-l'],text=True)
    if path not in contexts:subprocess.run(['semanage','fcontext','-a','-t','httpd_sys_content_t',path],check=True)
    subprocess.run(['restorecon','-RF','/opt/crawler-dev/maxun-web'],check=True)

directory=Path('/opt/crawler-dev/control')
configuration=directory/'nginx.conf'
original=configuration.read_text()
include='  include /opt/crawler-dev/control/maxun.conf;'
fragment='''server {
  listen 9443 ssl;
  server_name 192.168.1.169;
  ssl_certificate /opt/crawler-dev/private/server.pem;
  ssl_certificate_key /opt/crawler-dev/private/server.key;
  ssl_protocols TLSv1.2 TLSv1.3;
  client_max_body_size 16m;
  include /etc/nginx/mime.types;
  root /opt/crawler-dev/maxun-web;
  index index.html;
  location = /auth/register { return 403; }
  location /objects/ {
    auth_request /_maxun_auth;
    proxy_pass http://172.17.0.1:19000/;
    proxy_set_header Host $http_host;
    proxy_request_buffering off;
  }
  location = /_maxun_auth {
    internal;
    proxy_pass http://127.0.0.1:18080/auth/current-user;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header Cookie $http_cookie;
  }
  location ~ ^/(auth|storage|record|workflow|proxy|api|api-docs|webhook|socket.io)(/|$) {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300s;
    proxy_cookie_flags ~ secure httponly samesite=lax;
  }
  location / {
    try_files $uri $uri/ /index.html;
  }
}
'''
(directory/'maxun.conf').write_text(fragment)
if include not in original:
    (directory/'nginx.before-maxun.conf').write_text(original)
    configuration.write_text(original.replace('http {','http {\n'+include,1))
try:
    subprocess.run(['/usr/sbin/nginx','-t','-c',str(configuration)],check=True)
except Exception:
    configuration.write_text(original)
    raise
pid=int(Path('/run/crawler-dev-nginx.pid').read_text())
import os,signal
os.kill(pid,signal.SIGHUP)
print('在线设计器 HTTPS 网关已配置：9443；原 8443 路由保留')

# 在线设计器沿用采集平台的精确来源白名单，不将新端口开放给任意来源。
if subprocess.run(['firewall-cmd', '--state'], capture_output=True).returncode == 0:
    zone = subprocess.check_output(['firewall-cmd', '--get-default-zone'], text=True).strip()
    rules = subprocess.check_output(['firewall-cmd', '--zone=' + zone, '--list-rich-rules'], text=True)
    copied = 0
    for rule in rules.splitlines():
        if 'port="8443"' in rule and 'source address=' in rule and rule.endswith('accept'):
            target = rule.replace('port="8443"', 'port="9443"')
            for scope in ([], ['--permanent']):
                command = ['firewall-cmd', '--zone=' + zone, *scope]
                if subprocess.run(command + ['--query-rich-rule=' + target], capture_output=True).returncode != 0:
                    subprocess.run(command + ['--add-rich-rule=' + target], check=True)
            copied += 1
    if copied == 0:
        raise RuntimeError('未找到 8443 的精确来源白名单，未扩大 9443 访问范围；请检查网关防火墙配置')
    print('9443 已沿用 8443 的来源白名单，运行时与持久化规则均已配置')
