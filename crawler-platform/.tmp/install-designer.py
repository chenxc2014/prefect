"""准备官方可视化设计客户端，校验资产摘要后解压到本工作区。"""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
import py7zr
import subprocess

root = Path('.local/designer')
root.mkdir(exist_ok=True)
req = Request('https://api.github.com/repos/NaiboWang/EasySpider/releases/tags/v0.6.5', headers={'User-Agent':'crawler-platform-setup'})
with urlopen(req, timeout=30) as response:
    release = json.load(response)
asset = next(item for item in release['assets'] if item['name'].endswith('Windows_x64.7z'))
target = root / asset['name']
if not target.exists():
    print('下载官方 Windows 设计器：'+asset['name'], flush=True)
    with urlopen(asset['browser_download_url'], timeout=120) as response, target.with_suffix('.partial').open('wb') as output:
        while chunk := response.read(1024*1024):
            output.write(chunk)
    target.with_suffix('.partial').rename(target)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
if asset.get('digest') and asset['digest'] != 'sha256:'+digest:
    raise RuntimeError('官方资产摘要不匹配')
with py7zr.SevenZipFile(target) as archive:
    for name in archive.getnames():
        if not (root / name).resolve().is_relative_to(root.resolve()):
            raise RuntimeError('压缩包路径越界')
    try:
        archive.extractall(root)
    except py7zr.exceptions.UnsupportedCompressionMethodError:
        # 官方包使用 BCJ2，改用官方精简命令行解压器。
        extractor = root / '7zr.exe'
        if not extractor.exists():
            with urlopen('https://www.7-zip.org/a/7zr.exe', timeout=30) as response:
                extractor.write_bytes(response.read())
        subprocess.run([str(extractor.resolve()), 'x', str(target.resolve()), '-o'+str(root.resolve()), '-y'], check=True, stdout=subprocess.DEVNULL)
(root/'release.json').write_text(json.dumps(dict(tag='v0.6.5', url=asset['browser_download_url'],sha256=digest),indent=2),encoding='utf-8')
print('设计器已准备：'+str(root.resolve()), flush=True)
