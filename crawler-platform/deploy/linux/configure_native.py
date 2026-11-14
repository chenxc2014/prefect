"""为开发系统创建专用数据库和原生服务，不覆盖其他数据库。"""
import json
from pathlib import Path
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    private = Path('/opt/crawler-dev/private')
    credentials = json.loads((private / 'credentials.json').read_text())
    password = credentials['postgres']
    sql = f"""DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='crawlerdev') THEN
        CREATE ROLE crawlerdev LOGIN PASSWORD '{password}';
    END IF;
    END $$;
    """
    run('runuser', '-u', 'postgres', '--', 'psql', '-v', 'ON_ERROR_STOP=1', input=sql, text=True)
    found = run('runuser', '-u', 'postgres', '--', 'psql', '-tAc',
                "SELECT 1 FROM pg_database WHERE datname='crawler_dev'", capture_output=True, text=True)
    if found.stdout.strip() != '1':
        run('runuser', '-u', 'postgres', '--', 'createdb', '-O', 'crawlerdev', 'crawler_dev')
    hba = Path('/var/lib/pgsql/data/pg_hba.conf')
    original = hba.read_text()
    rule = 'host crawler_dev crawlerdev 127.0.0.1/32 scram-sha-256'
    if rule not in original:
        backup = private / 'pg_hba.before-crawler-dev.conf'
        if not backup.exists():
            backup.write_text(original)
            backup.chmod(0o600)
        hba.write_text('# 网爬开发系统专用认证\n' + rule + '\n' + original)
        run('systemctl', 'reload', 'postgresql')
    env = Path('/etc/crawler-dev/server.env')
    env.write_text(f'''PREFECT_SERVER_DATABASE_CONNECTION_URL=postgresql+asyncpg://crawlerdev:{password}@127.0.0.1:5432/crawler_dev
PREFECT_SERVER_API_AUTH_STRING={credentials['auth']}
PREFECT_SERVER_UI_API_URL=https://192.168.1.169:8443/api
PREFECT_SERVER_UI_STATIC_DIRECTORY=/var/lib/crawler-dev/ui
PREFECT_SERVER_ANALYTICS_ENABLED=false
PREFECT_HOME=/var/lib/crawler-dev/prefect-server
HOME=/var/lib/crawler-dev
''')
    env.chmod(0o640)
    run('chown', 'root:crawlerdev', str(env))
    service = Path('/etc/systemd/system/crawler-dev-server.service')
    service.write_text('''[Unit]
Description=网爬开发环境 Prefect 控制中心
After=network-online.target postgresql.service
Requires=postgresql.service
[Service]
Type=simple
User=crawlerdev
Group=crawlerdev
WorkingDirectory=/var/lib/crawler-dev
EnvironmentFile=/etc/crawler-dev/server.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/crawler-dev/venv/bin/prefect server start --host 127.0.0.1 --port 4200
Restart=on-failure
RestartSec=10
TimeoutStopSec=90
[Install]
WantedBy=multi-user.target
''')
    service.chmod(0o644)
    for path in (Path('/opt/crawler-dev'), Path('/opt/crawler-dev/releases'),
                 Path('/opt/crawler-dev/releases/dev-v1')):
        path.chmod(0o755)
    run('chmod', '-R', 'a+rX', '/opt/crawler-dev/venv')
    ui_directory = Path('/var/lib/crawler-dev/ui')
    ui_directory.mkdir(mode=0o750, exist_ok=True)
    run('chown', 'crawlerdev:crawlerdev', str(ui_directory))
    print('已生成本项目专用原生控制中心配置')


if __name__ == '__main__':
    main()
