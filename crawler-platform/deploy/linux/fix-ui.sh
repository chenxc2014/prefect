#!/usr/bin/env bash
# 只将 UI 生成目录迁至数据目录，不给服务账户开放安装目录写权限。
set -euo pipefail
python3.12 - <<'PY'
from pathlib import Path
import subprocess
directory = Path('/var/lib/crawler-dev/ui')
directory.mkdir(mode=0o750, exist_ok=True)
subprocess.run(['chown', 'crawlerdev:crawlerdev', str(directory)], check=True)
environment = Path('/etc/crawler-dev/server.env')
text = environment.read_text()
prefix = 'PREFECT_SERVER_UI_STATIC_DIRECTORY='
lines = [line for line in text.splitlines() if not line.startswith(prefix)]
lines.append(prefix + str(directory))
environment.write_text('\n'.join(lines) + '\n')
dropin = Path('/etc/systemd/system/crawler-dev-server.service.d')
dropin.mkdir(exist_ok=True)
(dropin / 'working-directory.conf').write_text('[Service]\nWorkingDirectory=/var/lib/crawler-dev\n')
print('已配置独立可写 UI 目录')
PY
systemctl daemon-reload
systemctl restart crawler-dev-server
for attempt in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:4200/api/health >/dev/null; then
    curl -sSL -o /dev/null -w 'root_status=%{http_code}\n' http://127.0.0.1:4200/
    exit 0
  fi
  sleep 2
done
exit 1
