#!/usr/bin/env bash
# Docker Hub 不可达时，使用发行版 PostgreSQL 和固定 Python 环境。
set -euo pipefail
dnf module install -y postgresql:16/server
dnf install -y postgresql-contrib
if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then postgresql-setup --initdb; fi
systemctl enable --now postgresql
setsebool -P httpd_can_network_connect on
python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/configure.py
python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/configure_native.py
systemctl daemon-reload
systemctl enable --now crawler-dev-server
systemctl is-active postgresql crawler-dev-server crawler-dev-gateway
