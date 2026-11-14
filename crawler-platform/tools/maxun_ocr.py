"""仅供在线设计器调用的本机图片验证码识别服务，图片和识别值不记录日志。"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import ddddocr

config=json.loads(Path('/etc/crawler-dev/maxun.json').read_text())
model=ddddocr.DdddOcr(show_ad=False)
lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        if self.path!='/recognize' or not secrets.compare_digest(self.headers.get('x-api-key',''),config['api_key']):
            self.send_error(403);return
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<1024*1024:self.send_error(413);return
        image=self.rfile.read(length)
        try:
            with lock:text=model.classification(image).strip()
            body=json.dumps({'text':text}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except Exception:
            self.send_error(422,'无法识别图片')
ThreadingHTTPServer(('172.17.0.1',18767),Handler).serve_forever()
