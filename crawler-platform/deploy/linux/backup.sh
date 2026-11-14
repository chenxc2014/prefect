#!/usr/bin/env bash
# 只备份本项目开发数据库，不读取业务数据库。
set -euo pipefail
umask 077
target="/opt/crawler-dev/backups/prefect-$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump -Fc crawler_dev > "$target"
sha256sum "$target" > "$target.sha256"
echo "开发数据库备份完成：$target"
