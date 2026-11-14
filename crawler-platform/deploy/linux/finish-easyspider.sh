#!/usr/bin/env bash
# 使用已核验标签的精简执行器，不下载媒体和桌面安装包。
set -euo pipefail
dnf install -y gcc kernel-headers python3.12-devel
mkdir -p /opt/crawler-dev/easyspider/source
python3.12 -m zipfile -e /opt/crawler-dev-bootstrap/easyspider-executor.zip /opt/crawler-dev/easyspider/source
if [ ! -x /opt/crawler-dev/easyspider/venv/bin/python ]; then python3.12 -m venv /opt/crawler-dev/easyspider/venv; fi
/opt/crawler-dev/easyspider/venv/bin/pip install 'commandline_config==2.2.3' 'requests==2.32.3' 'selenium==4.27.1' 'Pillow==10.2.0' 'xlsxwriter==3.2.0' 'openpyxl==3.1.2' 'pymysql==1.1.1' 'lxml==5.3.0' 'pynput==1.7.6' 'beautifulsoup4==4.12.2' 'undetected-chromedriver==3.4.7' 'setuptools<81' 'pandas==2.2.3'
/opt/crawler-dev/easyspider/venv/bin/pip freeze > /opt/crawler-dev/easyspider/requirements.lock
chown -R crawlerdev:crawlerdev /opt/crawler-dev/easyspider/venv
runuser -u crawlerdev -- /opt/crawler-dev/easyspider/venv/bin/python - <<'PY'
from selenium.webdriver.common.selenium_manager import SeleniumManager
import json
from pathlib import Path
paths = SeleniumManager().binary_paths(['--browser', 'chrome'])
Path('/var/lib/crawler-dev/easyspider-paths.json').write_text(json.dumps(paths))
print(paths)
PY
python3.12 - <<'PY'
from pathlib import Path
import json
paths = json.loads(Path('/var/lib/crawler-dev/easyspider-paths.json').read_text())
config = dict(source='/opt/crawler-dev/easyspider/source', python='/opt/crawler-dev/easyspider/venv/bin/python', browser=paths['browser_path'], driver=paths['driver_path'], timeout=180)
Path('/etc/crawler-dev/easyspider.json').write_text(json.dumps(config))
PY
chown root:crawlerdev /etc/crawler-dev/easyspider.json
chmod 640 /etc/crawler-dev/easyspider.json
