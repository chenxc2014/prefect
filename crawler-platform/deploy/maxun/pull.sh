#!/usr/bin/env bash
# 只启动独立验证环境，不替换现有 Prefect 数据库和服务。
set -euo pipefail
cd /opt/crawler-dev/maxun
python3.12 install.py
docker compose pull
python3.12 - <<'PY'
import json, subprocess
from pathlib import Path
images=['postgres:16-alpine','minio/minio:latest','getmaxun/maxun-backend:v0.1.0','getmaxun/maxun-frontend:v0.1.0','getmaxun/maxun-browser:v0.0.2']
resolved={}
for name in images:
    obj=json.loads(subprocess.check_output(['docker','image','inspect',name]))[0]
    resolved[name]=dict(id=obj['Id'],digests=obj.get('RepoDigests',[]))
Path('images.lock.json').write_text(json.dumps(resolved,indent=2))
# 使用内容摘要部署，避免 latest 或版本标签后续漂移。
compose=Path('compose.yaml').read_text()
for name,data in resolved.items():
    compose=compose.replace('image: '+name+'\n','image: '+data['digests'][0]+'\n')
Path('compose.resolved.yaml').write_text(compose)
PY
docker compose -f compose.resolved.yaml up -d
