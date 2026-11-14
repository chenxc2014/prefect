#!/usr/bin/env bash
# 新增独立管理服务，仅通过现有 HTTPS 网关开放。
set -euo pipefail
mkdir -p /var/lib/crawler-dev/catalog
chown crawlerdev:crawlerdev /var/lib/crawler-dev/catalog
cat > /etc/systemd/system/crawler-dev-collector.service <<'UNIT'
[Unit]
Description=网站采集模板管理服务
After=network-online.target crawler-dev-server.service
[Service]
User=crawlerdev
Group=crawlerdev
WorkingDirectory=/opt/crawler-dev/releases/dev-v1
Environment=PYTHONUTF8=1
Environment=HOME=/var/lib/crawler-dev
ExecStart=/opt/crawler-dev/venv/bin/python -m uvicorn tools.collector:app --host 127.0.0.1 --port 8081
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/crawler-dev-demo.service <<'UNIT'
[Unit]
Description=采集平台本机模拟业务站点
[Service]
User=crawlerdev
WorkingDirectory=/opt/crawler-dev/releases/dev-v1
ExecStart=/opt/crawler-dev/venv/bin/python tools/demo_site.py
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
python3.12 - <<'PY'
from pathlib import Path
path = Path('/opt/crawler-dev/control/nginx.conf')
text = path.read_text()
if 'location /collector/' not in text:
    Path('/opt/crawler-dev/control/nginx.before-collector.conf').write_text(text)
    text = text.replace('    location / {', '''    location /collector/ {
      proxy_pass http://127.0.0.1:8081/;
      proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-Proto https;
      client_max_body_size 16m;
    }
    location / {''')
    path.write_text(text)
PY
/usr/sbin/nginx -t -c /opt/crawler-dev/control/nginx.conf
systemctl daemon-reload
systemctl enable --now crawler-dev-collector crawler-dev-demo
systemctl reload crawler-dev-gateway || systemctl restart crawler-dev-gateway
/opt/crawler-dev/venv/bin/python /opt/crawler-dev/releases/dev-v1/tools/register_collect.py /etc/crawler-dev/client.json
