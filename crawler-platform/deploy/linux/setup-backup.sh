#!/usr/bin/env bash
set -euo pipefail
cat > /etc/systemd/system/crawler-dev-backup.service <<'UNIT'
[Unit]
Description=网爬开发环境数据库备份
After=postgresql.service
[Service]
Type=oneshot
ExecStart=/bin/bash /opt/crawler-dev/releases/dev-v1/deploy/linux/backup.sh
UNIT
cat > /etc/systemd/system/crawler-dev-backup.timer <<'UNIT'
[Unit]
Description=网爬开发环境每日备份计划
[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now crawler-dev-backup.timer
systemctl start crawler-dev-backup.service
systemctl list-timers crawler-dev-backup.timer --no-pager
