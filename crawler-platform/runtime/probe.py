"""标准库执行器：本地模拟接口分页和 CSV 下载，不访问生产网站。"""
import csv
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import platform
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


class SampleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        page = int(parse_qs(urlparse(self.path).query).get('page', ['1'])[0])
        data = {'rows': [{'id': page * 10 + i, 'quantity': i + 1} for i in range(2)],
                'total_pages': 3}
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    root = Path(sys.argv[1]).resolve()
    request = json.loads((root / 'request.json').read_text(encoding='utf-8'))
    started = datetime.now(timezone.utc).isoformat()
    (root / 'started.json').write_text(json.dumps({
        'flow_run_id': request['flow_run_id'], 'pid': os.getpid(), 'started_at': started,
    }), encoding='utf-8')
    for directory in ('download', 'captcha', 'screenshots', 'logs', 'temp'):
        (root / directory).mkdir(exist_ok=False)
    server = ThreadingHTTPServer(('127.0.0.1', 0), SampleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rows = []
        for page in range(1, 4):
            with urlopen('http://127.0.0.1:%s/data?page=%s' % (server.server_port, page), timeout=5) as response:
                rows.extend(json.load(response)['rows'])
        sample = root / 'download' / 'export.csv'
        with sample.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['id', 'quantity'])
            writer.writeheader()
            writer.writerows(rows)
        with sample.open(encoding='utf-8', newline='') as handle:
            read_rows = list(csv.DictReader(handle))
        if len(read_rows) != 6 or len({row['id'] for row in read_rows}) != 6:
            raise RuntimeError('分页与文件完整性验证失败')
        time.sleep(request['hold_seconds'])
        if request.get('fail'):
            raise RuntimeError('主动注入的开发验证失败')
        result = {'status': 'completed', 'kind': 'synthetic-probe',
                  'run_id': request['run_id'], 'hostname': socket.gethostname(),
                  'flow_run_id': request['flow_run_id'],
                  'os': platform.system(), 'pid': os.getpid(), 'run_dir': str(root),
                  'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                  'row_count': len(read_rows), 'sha256': hashlib.sha256(sample.read_bytes()).hexdigest()}
        temporary = root / 'result.tmp'
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(root / 'result.json')
        print('独立进程、接口分页和文件校验已完成')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
