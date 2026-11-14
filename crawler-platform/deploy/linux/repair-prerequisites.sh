#!/usr/bin/env bash
set -euo pipefail
dnf install -y postgresql-contrib
setsebool -P httpd_can_network_connect on
systemctl restart crawler-dev-server
echo '已补齐 PostgreSQL 扩展，并允许 HTTPS 反向代理访问本机 API；SELinux 保持启用'
