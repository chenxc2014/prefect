#!/usr/bin/env bash
set -euo pipefail
python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/configure.py
cd /opt/crawler-dev/control
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
docker inspect --format '{{index .RepoDigests 0}}' postgres:16 prefecthq/prefect:3.9.2-python3.12 > /opt/crawler-dev/private/image-digests.txt
echo '开发控制中心已启动，等待健康检查'
