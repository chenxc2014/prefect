"""在 Linux 169 初始化独立 Maxun 配置，所有秘密仅保存在服务器。"""
import json
import os
from pathlib import Path
import secrets

ROOT = Path('/opt/crawler-dev/maxun')
ROOT.mkdir(parents=True, exist_ok=True)
env = ROOT / '.env'
if not env.exists():
    values = dict(NODE_ENV='production', DB_NAME='maxun', DB_USER='maxun', DB_PASSWORD=secrets.token_hex(24),
        DB_HOST='postgres', DB_PORT='5432', JWT_SECRET=secrets.token_hex(48), ENCRYPTION_KEY=secrets.token_hex(32),
        SESSION_SECRET=secrets.token_hex(32), MINIO_ENDPOINT='minio', MINIO_PORT='9000', MINIO_CONSOLE_PORT='9001',
        MINIO_ACCESS_KEY='crawler-maxun', MINIO_SECRET_KEY=secrets.token_hex(32),
        MINIO_PUBLIC_URL='https://192.168.1.169:9443/objects',
        BACKEND_PORT='8080', PUBLIC_URL='https://192.168.1.169:9443', BACKEND_URL='https://192.168.1.169:9443',
        BROWSER_WS_PORT='3001', BROWSER_HEALTH_PORT='3002', BROWSER_WS_HOST='browser', MAXUN_TELEMETRY='false')
    env.write_text(''.join(f'{k}={v}\n' for k,v in values.items()))
    os.chmod(env, 0o600)
print('Maxun 独立配置已准备，未输出任何秘密值')
lines=dict(line.split('=',1) for line in env.read_text().splitlines() if '=' in line)
lines.update(MINIO_ENDPOINT='host.docker.internal',MINIO_PORT='19000')
env.write_text(''.join(f'{k}={v}\n' for k,v in lines.items()))
private=ROOT/'minio.env'
private.write_text('MINIO_ROOT_USER='+lines['MINIO_ACCESS_KEY']+'\nMINIO_ROOT_PASSWORD='+lines['MINIO_SECRET_KEY']+'\n')
os.chmod(private,0o600)
