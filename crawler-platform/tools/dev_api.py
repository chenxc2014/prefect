"""本地开发 API 客户端；自动验证开发 CA，认证不写入控制台。"""
import base64
import json
from pathlib import Path
import ssl
from urllib.request import Request, urlopen


class DevApi:
    def __init__(self, config_file=None):
        path = Path(config_file) if config_file else Path(__file__).resolve().parents[1] / '.local' / 'client.json'
        self.config = json.loads(path.read_text(encoding='utf-8-sig'))
        env = self.config['env']
        self.base = env['PREFECT_API_URL']
        self.context = ssl.create_default_context(cafile=env['SSL_CERT_FILE'])
        self.auth = 'Basic ' + base64.b64encode(env['PREFECT_API_AUTH_STRING'].encode()).decode()

    def request(self, path, data=None, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = self.auth
        body = json.dumps(data).encode('utf-8') if data is not None else None
        request = Request(self.base + path, data=body, headers=headers)
        with urlopen(request, context=self.context, timeout=30) as response:
            return json.load(response)


if __name__ == '__main__':
    import sys
    api = DevApi()
    print(json.dumps({'health': api.request('/health'),
                      'deployments': [d['name'] for d in api.request('/deployments/filter', {})]}, ensure_ascii=False))
