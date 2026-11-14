#!/usr/bin/env bash
# 在镜像和对象存储就绪后启用 Web 入口并初始化开发账号。
set -euo pipefail
cd /opt/crawler-dev/maxun
systemctl is-active --quiet crawler-maxun-storage
test -f compose.resolved.yaml
python3.12 extract-web.py
python3.12 patch-installed.py
docker compose -f compose.resolved.yaml up -d
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:18080/ >/dev/null; then break; fi
  sleep 2
done
for attempt in $(seq 1 20); do
  if python3.12 bootstrap-account.py; then break; fi
  if [ "$attempt" = 20 ]; then exit 1; fi
  sleep 2
done
cat > /etc/systemd/system/crawler-maxun-ocr.service <<'UNIT'
[Unit]
Description=在线采集设计器图片识别服务
After=network-online.target
[Service]
User=crawlerdev
WorkingDirectory=/opt/crawler-dev/releases/dev-v1
ExecStart=/opt/crawler-dev/easyspider/venv/bin/python tools/maxun_ocr.py
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now crawler-maxun-ocr
docker compose -f compose.resolved.yaml up -d backend
python3.12 gateway.py
systemctl is-active crawler-dev-server crawler-dev-collector crawler-dev-worker crawler-maxun-storage
