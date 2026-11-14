"""补充文档导航并核验三环境关系章节的结构。"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

path = Path('doc/爬虫任务编排与执行平台.html')
text = path.read_text(encoding='utf-8')
text = text.replace('<a href="#architecture">03 目标架构与部署拓扑</a>', '<a href="#architecture">03 目标架构与部署拓扑</a><a href="#environments">03-A 工作区与两台服务器的关系</a>')
text = text.replace('2026-11-13 更新：开发基础环境已部署，生产接管尚未启用', '2026-11-13 更新：补充三环境关系与中文界面，生产接管尚未启用')
text = text.replace('官方源码位于工作区 vendor\\prefect（3.9.2）。', '框架源码位于工作区 vendor\\prefect（3.9.2），UI v2 已定制中文界面并发布到 169。<a href="#environments">查看工作区与两台服务器的关系</a>。')
path.write_text(text, encoding='utf-8')


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []
        self.sections = 0
        self.ends = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a' and attrs.get('href', '').startswith('#'):
            self.anchors.append(attrs['href'][1:])
        if tag == 'section':
            self.sections += 1

    def handle_endtag(self, tag):
        if tag == 'section':
            self.ends += 1


parser = Structure()
parser.feed(text)
assert parser.sections == parser.ends
assert not [key for key, count in Counter(parser.ids).items() if count > 1]
assert all(anchor in parser.ids for anchor in parser.anchors)
assert 'environments' in parser.ids
print(f'HTML 结构检查通过：{parser.sections} 个章节，目录锚点全部有效，无重复 ID。')
