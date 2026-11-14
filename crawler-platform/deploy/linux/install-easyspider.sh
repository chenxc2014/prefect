#!/usr/bin/env bash
# 独立安装，不改变现有 Prefect 或旧爬虫解释器。
set -euo pipefail
mkdir -p /opt/crawler-dev/easyspider /var/lib/crawler-dev/catalog
if ! command -v google-chrome >/dev/null; then
  curl --fail --location --max-time 120 https://dl.google.com/linux/linux_signing_key.pub -o /opt/crawler-dev/easyspider/google-key.pub
  rpm --import /opt/crawler-dev/easyspider/google-key.pub
  curl --fail --location --max-time 300 https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm -o /opt/crawler-dev/easyspider/chrome.rpm
  dnf install -y --setopt=localpkg_gpgcheck=1 /opt/crawler-dev/easyspider/chrome.rpm
fi
dnf install -y xorg-x11-server-Xvfb xorg-x11-xauth
test -f /opt/crawler-dev-bootstrap/easyspider-executor.zip || { echo '请先通过 push-easyspider 上传固定版本精简源码包'; exit 1; }
bash /opt/crawler-dev/releases/dev-v1/deploy/linux/finish-easyspider.sh
chown crawlerdev:crawlerdev /var/lib/crawler-dev/catalog
