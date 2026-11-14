#!/usr/bin/env bash
# 仅安装开发环境前置软件，不修改现有业务服务。
set -euo pipefail
umask 077
dnf install -y dnf-plugins-core python3.12 python3.12-pip nginx openssl
if ! command -v docker >/dev/null; then
  dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
python3.12 --version
docker version --format '{{.Server.Version}}'
docker compose version
mkdir -p /opt/crawler-dev/{private,control,releases/dev-v1,backups} /var/lib/crawler-dev/runs
chmod 700 /opt/crawler-dev/private
if ! id crawlerdev >/dev/null 2>&1; then useradd --system --create-home --home-dir /var/lib/crawler-dev crawlerdev; fi
chown crawlerdev:crawlerdev /var/lib/crawler-dev/runs
if [ ! -x /opt/crawler-dev/venv/bin/python ]; then python3.12 -m venv /opt/crawler-dev/venv; fi
/opt/crawler-dev/venv/bin/python -m pip install 'prefect==3.9.2'
/opt/crawler-dev/venv/bin/python -m pip freeze > /opt/crawler-dev/private/linux-requirements.lock
echo 'Linux 开发环境前置安装完成'
