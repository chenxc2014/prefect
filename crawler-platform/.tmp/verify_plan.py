from pathlib import Path
from html.parser import HTMLParser
import ast
import json
import re

root = Path(__file__).resolve().parents[1]
target = root / 'doc' / '爬虫任务编排与执行平台.html'


class PlanParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.anchors = []
        self.blocks = []
        self.scripts = []
        self.current = None
        self.script = None
        self.sections = 0
        self.checks = 0

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if 'id' in attr:
            self.ids.append(attr['id'])
        if tag == 'a' and attr.get('href', '').startswith('#'):
            self.anchors.append(attr['href'][1:])
        if tag == 'section':
            self.sections += 1
        if tag == 'input' and 'data-check' in attr:
            self.checks += 1
        if tag == 'pre':
            self.current = [attr.get('data-lang', ''), '']
        if tag == 'script':
            assert 'src' not in attr, '页面不应依赖外部脚本'
            self.script = ''

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data
        if self.script is not None:
            self.script += data

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.blocks.append(self.current)
            self.current = None
        if tag == 'script':
            self.scripts.append(self.script)
            self.script = None


source = target.read_text(encoding='utf-8')
p = PlanParser()
p.feed(source)
assert len(p.ids) == len(set(p.ids)), '存在重复 HTML ID'
assert set(p.anchors) <= set(p.ids), '存在失效目录锚点'
assert p.sections == 23
assert p.checks == 12
assert '\ufffd' not in source, '存在编码替换字符'
python_count = 0
for lang, code in p.blocks:
    if lang == 'python':
        ast.parse(code)
        python_count += 1
    elif lang == 'json':
        json.loads(code)
(root / '.tmp' / 'plan-browser.js').write_text('\n'.join(p.scripts), encoding='utf-8')
print(json.dumps({
    '文件': str(target), '字节数': target.stat().st_size,
    '章节': p.sections, '检查项': p.checks,
    '目录锚点': len(p.anchors), '代码片段': len(p.blocks),
    'Python语法通过': python_count,
}, ensure_ascii=False))
