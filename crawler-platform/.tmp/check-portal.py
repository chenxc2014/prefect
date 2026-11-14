"""检查最终页面结构、脚本语法及真实管理 API；不输出认证信息。"""
import ast
import base64
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

root = Path(__file__).resolve().parents[1]


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.views = set()
        self.pages = set()
        self.script = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'data-view' in attrs:
            self.views.add(attrs['data-view'])
        if 'data-page' in attrs:
            self.pages.add(attrs['data-page'])
        if tag == 'script':
            self.script = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.script = False

    def handle_data(self, data):
        if self.script:
            self.scripts.append(data)


source = (root / 'deploy/web/collector.html').read_text(encoding='utf-8')
parser = Parser()
parser.feed(source)
assert '\ufffd' not in source
assert all(count == 1 for count in Counter(parser.ids).values()), '页面存在重复 ID'
assert parser.views == parser.pages, '导航与页面不一致'
script = root / '.tmp/portal-script.js'
script.write_text('\n'.join(parser.scripts), encoding='utf-8')
subprocess.run(['node', '--check', str(script)], check=True)
for name in ('tools/collector.py', 'deploy/maxun/gateway.py'):
    ast.parse((root / name).read_text(encoding='utf-8'))

config = json.loads((root / '.local/client.json').read_text(encoding='utf-8-sig'))
authorization = 'Basic ' + base64.b64encode(config['env']['PREFECT_API_AUTH_STRING'].encode()).decode()
base = 'http://127.0.0.1:18843/collector/'
try:
    urlopen(base + 'api/platform', timeout=10)
    raise AssertionError('状态接口不应允许未认证访问')
except HTTPError as error:
    assert error.code == 401
with urlopen(Request(base + 'api/platform', headers={'Authorization': authorization}), timeout=20) as response:
    platform = json.load(response)
assert platform['prefect']['state'] == 'ready'
assert platform['engines']['maxun']['state'] == 'ready'
assert platform['engines']['legacy']['state'] == 'adapter_only'
assert platform['windows_node'] == 'not_checked'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


try:
    build_opener(NoRedirect).open(Request(base + 'designer', headers={'Authorization': authorization}), timeout=15)
    raise AssertionError('设计器入口应跳转到部署地址')
except HTTPError as error:
    assert error.code == 307
    assert error.headers['Location'] == 'https://192.168.1.169:9443/'

report_file = root / 'doc/多引擎工作台界面验收.json'
report = json.loads(report_file.read_text(encoding='utf-8'))
assert report['passed']
report['additional_checks'] = ['最终 HTML ID 唯一、导航与页面一致、脚本语法通过', '状态 API 未认证为 401，认证后返回实际服务状态', '设计器入口为 307 跳转至固定部署地址', 'Maxun 登录、新建及远程录制器显示模拟查询页已通过独立浏览器验证', '9443 与 8443 使用相同精确来源白名单，运行时和持久化规则均已核对']
report['screenshots'] = ['.local/screenshots/collector-redesign-desktop.png', '.local/screenshots/collector-redesign-mobile.png', '.local/screenshots/collector-redesign-architecture.png', '.local/screenshots/collector-redesign-maxun.png', '.local/screenshots/collector-redesign-run.png']
report['limits'] = ['未从用户堡垒机直接验证访问链路', '未访问 Windows 167', '本次没有执行旧生产任务，未完成 Maxun 千金站点业务验收']
report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('最终页面结构、脚本、认证、状态与跳转检查通过')
