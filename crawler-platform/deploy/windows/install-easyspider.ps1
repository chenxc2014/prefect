# 在独立目录安装便携浏览器和执行器，不替换旧爬虫环境。
$ErrorActionPreference = 'Stop'
$root = 'D:\CrawlerDev\easyspider'
New-Item -ItemType Directory -Force -Path "$root\source", "$root\downloads" | Out-Null
Expand-Archive -LiteralPath 'D:\CrawlerDev\bootstrap\easyspider-executor.zip' -DestinationPath "$root\source" -Force
if (-not (Test-Path -LiteralPath "$root\venv\Scripts\python.exe")) { & 'D:\CrawlerDev\Python312\python.exe' -m venv "$root\venv" }
& "$root\venv\Scripts\python.exe" -m pip install 'commandline_config==2.2.3' 'requests==2.32.3' 'selenium==4.27.1' 'Pillow==10.2.0' 'xlsxwriter==3.2.0' 'openpyxl==3.1.2' 'pymysql==1.1.1' 'lxml==5.3.0' 'pynput==1.7.6' 'beautifulsoup4==4.12.2' 'undetected-chromedriver==3.4.7' 'setuptools<81' 'pandas==2.2.3'
if ($LASTEXITCODE -ne 0) { throw '独立依赖安装失败' }
& "$root\venv\Scripts\python.exe" -c "import json,urllib.request,zipfile,pathlib; root=pathlib.Path(r'D:\CrawlerDev\easyspider'); data=json.load(urllib.request.urlopen('https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json',timeout=60)); stable=data['channels']['Stable']; [(urllib.request.urlretrieve(next(a['url'] for a in stable['downloads'][name] if a['platform']=='win64'),root/'downloads'/(name+'.zip')),zipfile.ZipFile(root/'downloads'/(name+'.zip')).extractall(root)) for name in ('chrome','chromedriver')]; config={'source':str(root/'source'),'python':str(root/'venv/Scripts/python.exe'),'browser':str(root/'chrome-win64/chrome.exe'),'driver':str(root/'chromedriver-win64/chromedriver.exe'),'timeout':180}; pathlib.Path(r'D:\CrawlerDev\private\easyspider.json').write_text(json.dumps(config),encoding='utf-8'); print('已安装便携浏览器版本：'+stable['version'])"
if ($LASTEXITCODE -ne 0) { throw '便携浏览器安装失败' }
& "$root\venv\Scripts\python.exe" -m pip freeze | Set-Content -Encoding UTF8 "$root\requirements.lock"
& 'D:\CrawlerDev\venv\Scripts\python.exe' 'D:\CrawlerDev\releases\dev-v1\tools\register_collect.py' 'D:\CrawlerDev\private\client.json'
if ($LASTEXITCODE -ne 0) { throw '采集部署注册失败' }
