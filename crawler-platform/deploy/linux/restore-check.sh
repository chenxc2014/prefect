#!/usr/bin/env bash
# 仅还原到新建的独立验证数据库，不覆盖运行数据库。
set -euo pipefail
backup=$(find /opt/crawler-dev/backups -maxdepth 1 -type f -name 'prefect-*.dump' | sort | tail -n 1)
test -n "$backup"
sha256sum -c "$backup.sha256"
target="crawler_dev_restore_$(date -u +%Y%m%d%H%M%S)"
runuser -u postgres -- createdb "$target"
runuser -u postgres -- pg_restore --exit-on-error --no-owner --no-privileges -d "$target" < "$backup"
runuser -u postgres -- psql -d "$target" -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS restored_flow_runs FROM flow_run;'
echo "恢复演练完成，验证数据库保留为：$target"
