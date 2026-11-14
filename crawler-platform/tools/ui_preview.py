"""仅监听本机的界面验收代理：本地构建 + 验证 CA 的远端开发 API。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from tools.dev_api import DevApi


def create_preview(port=18843, remote_ui=False):
    api = DevApi()
    directory = Path(__file__).resolve().parents[1] / 'vendor/prefect/ui-v2/dist'
    origin = api.base.removesuffix('/api')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            if status == 401:
                self.send_header('WWW-Authenticate', 'Basic realm="crawler-dev"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # 页面导航会主动取消尚未结束的请求，此时不再向已关闭连接写入。
                pass

        def do_GET(self):
            self.handle_request()

        def do_POST(self):
            self.handle_request()

        def handle_request(self):
            path = urlparse(self.path).path
            if path.startswith('/collector/'):
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length) if length else None
                headers = {key: self.headers[key] for key in ('Authorization', 'Content-Type', 'Accept') if self.headers.get(key)}
                if self.headers.get('Origin'):
                    headers['Origin'] = origin
                request = Request(origin + self.path, data=body, headers=headers, method=self.command)
                try:
                    response = urlopen(request, context=api.context, timeout=30)
                except HTTPError as error:
                    response = error
                with response:
                    return self.reply(response.code, response.read(), response.headers.get('Content-Type', 'application/json'))
            if path in ('/ui-settings', '/v2/ui-settings'):
                with urlopen(origin + '/ui-settings', context=api.context, timeout=30) as response:
                    settings = json.load(response)
                settings['api_url'] = f'http://127.0.0.1:{port}/api'
                return self.reply(200, json.dumps(settings).encode(), 'application/json')
            if path.startswith('/api/'):
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length) if length else None
                headers = {key: self.headers[key] for key in ('Authorization', 'Content-Type', 'x-prefect-api-version') if self.headers.get(key)}
                request = Request(origin + self.path, data=body, headers=headers, method=self.command)
                try:
                    response = urlopen(request, context=api.context, timeout=30)
                except HTTPError as error:
                    response = error
                with response:
                    return self.reply(response.code, response.read(), response.headers.get('Content-Type', 'application/json'))
            if remote_ui:
                request = Request(origin + self.path, headers={'Accept': self.headers.get('Accept', '*/*')})
                try:
                    response = urlopen(request, context=api.context, timeout=30)
                except HTTPError as error:
                    response = error
                with response:
                    return self.reply(response.code, response.read(), response.headers.get('Content-Type', 'application/octet-stream'))
            relative = unquote(path).removeprefix('/v2/').lstrip('/')
            if path in ('/', '/v2', '/v2/'):
                relative = 'index.html'
            target = (directory / relative).resolve()
            if not target.is_relative_to(directory.resolve()):
                return self.reply(403, b'Forbidden', 'text/plain')
            if not target.is_file():
                if '.' in Path(relative).name:
                    return self.reply(404, b'Not Found', 'text/plain')
                target = directory / 'index.html'
            body = target.read_bytes()
            if target.suffix in ('.html', '.js', '.css', '.json', '.webmanifest'):
                body = body.replace(b'/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER', b'/v2')
            return self.reply(200, body, mimetypes.guess_type(target.name)[0] or 'application/octet-stream')

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
