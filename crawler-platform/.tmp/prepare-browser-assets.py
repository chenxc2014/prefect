"""在开发机准备固定版本浏览器资源，供无法访问元数据站点的节点使用。"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

root = Path('.local/browser-assets')
root.mkdir(parents=True, exist_ok=True)
urls = ['https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json', 'https://raw.githubusercontent.com/GoogleChromeLabs/chrome-for-testing/gh-pages/last-known-good-versions-with-downloads.json']
for url in urls:
    try:
        with urlopen(url, timeout=20) as response:
            stable = json.load(response)['channels']['Stable']
        break
    except Exception as error:
        print(type(error).__name__, flush=True)
else:
    raise RuntimeError('无法取得浏览器发布元数据')
(root / 'stable.json').write_text(json.dumps(stable), encoding='utf-8')
for kind, platform in [('chromedriver','linux64'),('chromedriver','win64'),('chrome','win64')]:
    entry = next(item for item in stable['downloads'][kind] if item['platform'] == platform)
    target = root / (kind+'-'+platform+'.zip')
    print('下载：'+entry['url'], flush=True)
    if not target.exists():
        with urlopen(entry['url'], timeout=90) as response, target.with_suffix('.partial').open('wb') as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
        target.with_suffix('.partial').rename(target)
    print(target.name + ' ' + hashlib.sha256(target.read_bytes()).hexdigest(), flush=True)
