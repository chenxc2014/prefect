#!/usr/bin/env bash
set -euo pipefail
chmod 755 /opt/crawler-dev /opt/crawler-dev/releases /opt/crawler-dev/releases/dev-v1 /opt/crawler-dev/venv
chown crawlerdev:crawlerdev /var/lib/crawler-dev
find /opt/crawler-dev/venv -type d -exec chmod a+rx '{}' +
find /opt/crawler-dev/venv -type f -exec chmod a+r '{}' +
/opt/crawler-dev/venv/bin/python /opt/crawler-dev/releases/dev-v1/tools/setup_node.py /etc/crawler-dev/client.json
systemctl enable --now crawler-dev-worker
systemctl is-active crawler-dev-worker
