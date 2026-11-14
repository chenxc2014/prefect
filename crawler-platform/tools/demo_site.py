"""仅在执行节点回环地址提供可验证的模拟业务页面。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PAGE = '''<!doctype html><meta charset="utf-8"><title>采集平台演示站</title><h1>销售查询演示</h1><label>开始日期<input id="begindate"></label><button id="search" onclick="let e=document.getElementById('export');e.hidden=false;e.href='/export?begin='+encodeURIComponent(document.getElementById('begindate').value)">查询</button><a id="export" href="/export" download="sales.csv" hidden>导出销售 CSV</a>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == '/export':
            begin = parse_qs(urlparse(self.path).query).get('begin', [''])[0]
            body = ('id,quantity,begindate\n' + ''.join(f'{i},{i+1},{begin}\n' for i in range(6))).encode()
            content = 'text/csv'
        else:
            body, content = PAGE.encode(), 'text/html; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8766), Handler).serve_forever()
