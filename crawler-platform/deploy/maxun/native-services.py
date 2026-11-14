"""为 Maxun 创建独立数据库和浏览器实例，复用已有程序，不改 Prefect 数据库。"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import shutil

root=Path('/opt/crawler-dev/maxun')
pgbin=Path(shutil.which('initdb') or '/usr/bin/initdb').parent
if not (pgbin/'initdb').exists():raise RuntimeError('未找到已安装的 PostgreSQL 初始化程序')
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line)
env.update(DB_HOST='host.docker.internal',DB_PORT='15432',BROWSER_WS_HOST='host.docker.internal',BROWSER_WS_PORT='13001',BROWSER_HEALTH_PORT='13002')
(root/'.env').write_text(''.join(f'{k}={v}\n' for k,v in env.items()))
data=Path('/var/lib/pgsql/maxun-data');data.mkdir(parents=True,exist_ok=True)
account=pwd.getpwnam('postgres');os.chown(data,account.pw_uid,account.pw_gid);data.chmod(0o700)
subprocess.run(['restorecon','-RF',str(data)],check=True)
if subprocess.check_output(['getenforce'],text=True).strip()=='Enforcing':
    if not shutil.which('semanage'):raise RuntimeError('请先安装 SELinux 管理工具，为新增专用端口配置标签')
    ports=subprocess.check_output(['semanage','port','-l'],text=True)
    if not any(line.startswith('postgresql_port_t') and '15432' in line for line in ports.splitlines()):
        subprocess.run(['semanage','port','-a','-t','postgresql_port_t','-p','tcp','15432'],check=True)
if not (data/'PG_VERSION').exists():
    password_file=data.parent/'maxun-init-password';password_file.write_text(env['DB_PASSWORD']);password_file.chmod(0o600);os.chown(password_file,account.pw_uid,account.pw_gid)
    subprocess.run(['restorecon',str(password_file)],check=True)
    try:
        subprocess.run(['runuser','-u','postgres','--',str(pgbin/'initdb'),'-D',str(data),'-U','maxun','--pwfile='+str(password_file),'--auth-host=scram-sha-256','--auth-local=peer','--encoding=UTF8','--locale=C'],check=True,stdout=subprocess.DEVNULL)
    finally:
        password_file.unlink(missing_ok=True)
    with (data/'pg_hba.conf').open('a') as handle:
        handle.write('\nhost maxun maxun 172.16.0.0/12 scram-sha-256\n')
hba=data/'pg_hba.conf'
for address in ('172.17.0.1/32','192.168.1.169/32'):
    admin_rule='host all maxun '+address+' scram-sha-256'
    if admin_rule not in hba.read_text():
        with hba.open('a') as handle:handle.write('\n'+admin_rule+'\n')
unit='''[Unit]
Description=在线采集设计器独立 PostgreSQL 数据库
After=network-online.target docker.service
[Service]
User=postgres
ExecStart=/usr/pgsql-16/bin/postgres -D /var/lib/crawler-maxun/postgres -p 15432 -h 172.17.0.1
Restart=on-failure
[Install]
WantedBy=multi-user.target
'''
Path('/etc/systemd/system/crawler-maxun-database.service').write_text(unit.replace('/usr/pgsql-16/bin/',str(pgbin)+'/').replace('/var/lib/crawler-maxun/postgres',str(data)))
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','reset-failed','crawler-maxun-database'],check=False,stdout=subprocess.DEVNULL)
subprocess.run(['systemctl','enable','--now','crawler-maxun-database'],check=True)
subprocess.run(['runuser','-u','postgres','--',str(pgbin/'pg_ctl'),'reload','-D',str(data)],check=True,stdout=subprocess.DEVNULL)
import time
connection_env=dict(os.environ,PGPASSWORD=env['DB_PASSWORD'])
for _ in range(30):
    result=subprocess.run([str(pgbin/'psql'),'-h','172.17.0.1','-p','15432','-U','maxun','-d','postgres','-tAc',"SELECT 1 FROM pg_database WHERE datname='maxun'"],env=connection_env,capture_output=True,text=True)
    if result.returncode==0:break
    time.sleep(1)
else:raise RuntimeError('Maxun 独立数据库未就绪：'+result.stderr.strip()[-700:])
if not result.stdout.strip():
    subprocess.run([str(pgbin/'createdb'),'-h','172.17.0.1','-p','15432','-U','maxun','maxun'],env=connection_env,check=True)

runtime=Path('/opt/crawler-dev/maxun-browser');runtime.mkdir(exist_ok=True);runtime.chmod(0o755)
container=subprocess.check_output(['docker','create','getmaxun/maxun-backend:v0.1.0'],text=True).strip()
try:
    if not (runtime/'node').exists():subprocess.run(['docker','cp',container+':/usr/local/bin/node',str(runtime/'node')],check=True)
    if not (runtime/'node_modules/playwright-core').exists():
        (runtime/'node_modules').mkdir(exist_ok=True)
        subprocess.run(['docker','cp',container+':/app/node_modules/playwright-core',str(runtime/'node_modules/playwright-core')],check=True)
finally:subprocess.run(['docker','rm',container],check=True,stdout=subprocess.DEVNULL)
(runtime/'node').chmod(0o755)
import shutil
shutil.copy2(root/'native-browser.cjs',runtime/'server.cjs')
unit='''[Unit]
Description=在线采集设计器独立浏览器服务
After=network-online.target docker.service
[Service]
User=crawlerdev
WorkingDirectory=/opt/crawler-dev/maxun-browser
ExecStart=/opt/crawler-dev/maxun-browser/node /opt/crawler-dev/maxun-browser/server.cjs
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
'''
Path('/etc/systemd/system/crawler-maxun-browser.service').write_text(unit)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','--now','crawler-maxun-browser'],check=True)
print('Maxun 独立数据库 15432 与浏览器服务 13001/13002 已配置')
