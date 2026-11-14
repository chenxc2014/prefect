#!/usr/bin/env bash
# MinIO 社区镜像已下架，按官方固定标签从源码构建，避免使用陌生镜像。
set -euo pipefail
cd /opt/crawler-dev/maxun
mkdir -p toolchain
export HTTPS_PROXY=http://127.0.0.1:28080 HTTP_PROXY=http://127.0.0.1:28080
export NO_PROXY=localhost,127.0.0.1
if [ ! -x toolchain/go/bin/go ]; then
  if [ ! -f toolchain/go.tar.gz ]; then
    curl --noproxy '*' --connect-timeout 15 --max-time 180 -fsSL --retry 3 https://go.dev/dl/go1.24.8.linux-amd64.tar.gz -o toolchain/go.tar.gz
  fi
  python3.12 - <<'PY'
import hashlib,json
from pathlib import Path
# 摘要来自 Go 官方发布元数据：https://go.dev/dl/?mode=json&include=all
expected='6842c516ca66c89d648a7f1dbe28e28c47b61b59f8f06633eb2ceb1188e9251d'
assert hashlib.sha256(Path('toolchain/go.tar.gz').read_bytes()).hexdigest()==expected,'Go 工具链摘要不符'
PY
  tar -xzf toolchain/go.tar.gz -C toolchain
fi
export PATH=$PWD/toolchain/go/bin:$PATH GOPATH=$PWD/go-cache GOMAXPROCS=4 GOCACHE=$PWD/go-build-cache CGO_ENABLED=0
export GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org
go install github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z
id crawlermaxun >/dev/null 2>&1 || useradd --system --home-dir /var/lib/crawler-maxun --shell /sbin/nologin crawlermaxun
install -d -o crawlermaxun -g crawlermaxun /var/lib/crawler-maxun/objects
install -m 755 go-cache/bin/minio /usr/local/bin/crawler-maxun-minio
python3.12 install.py
cat > /etc/systemd/system/crawler-maxun-storage.service <<'UNIT'
[Unit]
Description=在线采集设计器独立对象存储
After=network-online.target docker.service
[Service]
User=crawlermaxun
EnvironmentFile=/opt/crawler-dev/maxun/minio.env
ExecStart=/usr/local/bin/crawler-maxun-minio server /var/lib/crawler-maxun/objects --address 172.17.0.1:19000 --console-address 127.0.0.1:19001
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now crawler-maxun-storage
/usr/local/bin/crawler-maxun-minio --version | head -1
