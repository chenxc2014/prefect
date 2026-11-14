"""同步 EasySpider 开发仓库说明，保留官方发布包来源。"""
from pathlib import Path
import json

path=Path('doc/开发环境部署记录.html')
text=path.read_text(encoding='utf-8')
marker='<h2>A 方案：可视化采集入口与首站验收</h2>'
note='<p>EasySpider 开发仓库已切换为 <a href="https://github.com/chenxc2014/EasySpider.git">chenxc2014/EasySpider</a>。本地 <code>vendor/easyspider</code> 的 origin 指向该仓库，官方 <code>NaiboWang/EasySpider</code> 保留为 upstream。运行基线继续固定 v0.6.5 / 191bd6d7547bb397e4c579dd2c70ae835be3f512，切换源码地址不自动发版；设计客户端已安装包仍保留官方来源记录。</p>'
assert marker in text
if note not in text:text=text.replace(marker,marker+note)
path.write_text(text,encoding='utf-8')
json.loads(Path('framework.lock.json').read_text(encoding='utf-8'))
