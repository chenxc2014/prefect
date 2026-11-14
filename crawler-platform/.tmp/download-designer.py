"""读取官方发布资产清单，确定设计客户端的精确下载位置。"""
import json
from urllib.request import Request, urlopen
request = Request('https://api.github.com/repos/NaiboWang/EasySpider/releases/tags/v0.6.5', headers={'Accept':'application/vnd.github+json','User-Agent':'crawler-platform-setup'})
with urlopen(request, timeout=30) as response:
    data = json.load(response)
print(json.dumps([{'name':a['name'],'size':a['size'],'url':a['browser_download_url']} for a in data['assets']], ensure_ascii=False))
