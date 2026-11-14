"""检查实际管理首页、SPA 路由、脚本样式和 API 认证。"""
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from tools.dev_api import DevApi


def check_ui():
    api = DevApi()
    origin = api.base.removesuffix('/api')
    results = []

    def fetch(url, content_kind=None):
        request = Request(url, headers={'Accept': 'text/html' if content_kind == 'text/html' else '*/*'})
        with urlopen(request, context=api.context, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get_content_type()
            if content_kind and content_kind not in content_type:
                raise AssertionError(f'资源类型不匹配：{response.url} {content_type}')
            results.append({'url': response.url, 'status': response.status,
                            'content_type': content_type, 'bytes': len(body)})
            assert response.status == 200 and body
            return response.url, body.decode('utf-8', errors='replace')

    final_url, html = fetch(origin + '/', 'text/html')
    assert '<html' in html.lower()
    assets = re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|css)(?:\?[^"\']*)?)["\']', html)
    assert assets, '首页没有 JS/CSS 资源引用'
    for asset in dict.fromkeys(assets):
        target = urljoin(final_url, asset)
        assert target.startswith(origin + '/'), '静态资源不应指向未知外部站点'
        fetch(target, 'javascript' if '.js' in asset else 'text/css')
    route = '/v2/deployments' if '/v2' in final_url else '/deployments'
    fetch(origin + route, 'text/html')
    with urlopen(origin + '/ui-settings', context=api.context, timeout=30) as response:
        settings = json.load(response)
    assert settings['api_url'] == api.base, settings['api_url']
    assert api.request('/health') is True
    try:
        api.request('/deployments/filter', {}, authenticated=False)
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError('API 认证回归失败')
    deployments = api.request('/deployments/filter', {})
    report = {'passed': True, 'pages_and_assets': results, 'ui_api_url': settings['api_url'],
              'api_health': True, 'unauthenticated_api_status': 401,
              'deployments': [item['name'] for item in deployments]}
    target = Path(__file__).resolve().parents[1] / 'doc' / '管理首页修复验证.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'checked_pages_and_assets': len(results),
                      'ui_api_url': settings['api_url'], 'api_health': True,
                      'unauthenticated_api_status': 401,
                      'report': str(target)}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    check_ui()
