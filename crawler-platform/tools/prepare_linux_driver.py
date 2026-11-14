"""根据已安装浏览器构建号下载匹配驱动，避免下载另一套浏览器。"""
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen
import zipfile
import io

base = Path('/opt/crawler-dev/easyspider')
version = re.search(r'\d+\.\d+\.\d+\.\d+', subprocess.check_output(['google-chrome', '--version'], text=True)).group()
with urlopen('https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json', timeout=60) as response:
    data = json.load(response)
build = data['builds']['.'.join(version.split('.')[:3])]
url = next(item['url'] for item in build['downloads']['chromedriver'] if item['platform'] == 'linux64')
with urlopen(url, timeout=120) as response:
    package = response.read()
with zipfile.ZipFile(io.BytesIO(package)) as archive:
    archive.extractall(base)
driver = base / 'chromedriver-linux64/chromedriver'
driver.chmod(0o755)
config = dict(source=str(base/'source'), python=str(base/'venv/bin/python'), browser='/usr/bin/google-chrome', driver=str(driver), timeout=180)
Path('/etc/crawler-dev/easyspider.json').write_text(json.dumps(config))
print('匹配驱动已就绪：' + build['version'])
