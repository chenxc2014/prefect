"""统一网页登录与网关认证适配，服务端衔接 Prefect 和 Maxun 原有认证。"""
import base64
from http.cookies import SimpleCookie
import json
from pathlib import Path
import secrets
import re
from urllib.parse import parse_qs
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Request as WebRequest
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from runtime.auth import SessionStore

COOKIE = '__Host-crawler_session'
LOGIN_COOKIE = '__Host-crawler_login'
REMEMBER_TTL = 30 * 24 * 3600


def maxun_destination(query):
    """仅允许受控的机器人和任务定位，不接收任意跳转地址。"""
    from urllib.parse import urlencode
    from uuid import UUID
    if query.get('execution'):
        return '/runs/' + str(UUID(query['execution'])) + '/run/' + str(UUID(query.get('run', ''))), None
    robot = query.get('robot', '')
    if robot:
        return '/robots/' + str(UUID(robot)) + '/edit', str(UUID(robot))
    template = query.get('template', '')
    if re.fullmatch('[a-f0-9]{64}', template):
        section = query.get('section', 'published')
        section = section if section in ('published', 'history', 'design') else 'published'
        return '/robots?' + urlencode({'template': template, 'section': section}), None
    return '/robots', None


class PortalAuth:
    def __init__(self, auth_string, directory, config_path='/etc/crawler-dev/sso.json'):
        self.credentials = auth_string
        self.username = auth_string.split(':', 1)[0]
        self.store = SessionStore(directory)
        self.config_path = Path(config_path)
        self.router = APIRouter()
        self.install_routes()

    def settings(self):
        return json.loads(self.config_path.read_text(encoding='utf-8'))

    def session(self, request):
        return self.store.get(request.cookies.get(COOKIE, ''))

    def basic_valid(self, header):
        try:
            scheme, value = (header or '').split(' ', 1)
            actual = base64.b64decode(value, validate=True)
            return scheme.lower() == 'basic' and secrets.compare_digest(actual, self.credentials.encode())
        except (ValueError, UnicodeError):
            return False

    def origin_valid(self, request):
        return request.headers.get('origin', '') in self.settings()['origins']

    def csrf_valid(self, request, session):
        return secrets.compare_digest(request.headers.get('x-crawler-csrf', ''), session['csrf'])

    def require_browser(self, request):
        session = self.session(request)
        if not session:
            raise HTTPException(401, '统一登录已失效，请重新登录')
        return session

    def protect_write(self, request, session, method=None):
        method = method or request.method
        if method not in ('GET', 'HEAD', 'OPTIONS'):
            if not self.origin_valid(request) or not self.csrf_valid(request, session):
                raise HTTPException(403, '请求来源或会话校验失败，请刷新页面后重试')

    def target(self, name):
        return {'platform': '/collector/', 'prefect': '/v2/', 'maxun': '/collector/open/maxun'}.get(name, '/collector/')

    @staticmethod
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def login_redirect(self, next_app='platform'):
        return self.private(RedirectResponse('/collector/login?next=' + next_app, status_code=303))

    def logout(self, request):
        session = self.require_browser(request)
        self.protect_write(request, session)
        self.store.revoke(request.cookies.get(COOKIE, ''))
        response = JSONResponse({'ok': True})
        for name in (COOKIE, LOGIN_COOKIE, 'token', 'connect.sid'):
            response.delete_cookie(name, path='/', secure=True, httponly=True, samesite='lax')
        return self.private(response)

    def install_routes(self):
        router = self.router

        @router.get('/login')
        def login_page(request: WebRequest):
            next_app = request.query_params.get('next', 'platform')
            if self.session(request):
                return RedirectResponse(self.target(next_app), status_code=303)
            nonce = request.cookies.get(LOGIN_COOKIE, '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{43}', nonce):
                nonce = secrets.token_urlsafe(32)
            page = (Path(__file__).resolve().parents[1] / 'deploy/web/login.html').read_text(encoding='utf-8')
            # next 参数只允许固定应用名，不接受外部 URL。
            next_app = next_app if next_app in ('platform', 'prefect', 'maxun') else 'platform'
            page = page.replace('__LOGIN_NONCE__', nonce).replace('__NEXT_APP__', next_app)
            response = HTMLResponse(page)
            response.set_cookie(LOGIN_COOKIE, nonce, max_age=900, secure=True, httponly=True, samesite='lax', path='/')
            return self.private(response)

        @router.post('/login')
        async def login_submit(request: WebRequest):
            raw = await request.body()
            if len(raw) > 4096:
                raise HTTPException(413, '登录请求过大')
            try:
                form = parse_qs(raw.decode('utf-8'), max_num_fields=8)
            except (ValueError, UnicodeError):
                raise HTTPException(400, '登录请求格式不正确')
            value = lambda key: form.get(key, [''])[0]
            nonce = request.cookies.get(LOGIN_COOKIE, '')
            if not nonce or not secrets.compare_digest(nonce, value('csrf')) or not self.origin_valid(request):
                raise HTTPException(403, '登录页已失效，请刷新后重试')
            address = request.headers.get('x-real-ip') or request.client.host
            if self.store.limited(address):
                return JSONResponse({'detail': '尝试次数过多，请 15 分钟后重试'}, status_code=429)
            actual = value('username') + ':' + value('password')
            if not secrets.compare_digest(actual.encode(), self.credentials.encode()):
                self.store.failed(address)
                return self.private(JSONResponse({'detail': '用户名或密码不正确'}, status_code=401))
            self.store.clear_failures(address)
            # 每次登录更新会话，旧浏览器会话在服务端撤销。
            self.store.revoke(request.cookies.get(COOKIE, ''))
            remember = value('remember') == '1'
            token, session = self.store.create(self.username, ttl=REMEMBER_TTL if remember else None)
            target = self.target(value('next'))
            response = JSONResponse({'next': target}) if 'application/json' in request.headers.get('accept', '') else RedirectResponse(target, status_code=303)
            # 仅在勾选时跨浏览器重启保留登录，浏览器和服务端使用相同的有效期。
            response.set_cookie(COOKIE, token, max_age=REMEMBER_TTL if remember else None, secure=True, httponly=True, samesite='lax', path='/')
            response.delete_cookie(LOGIN_COOKIE, secure=True, httponly=True, samesite='lax', path='/')
            return self.private(response)

        @router.get('/api/auth/me')
        def me(request: WebRequest):
            return self.private(JSONResponse(self.require_browser(request)))

        @router.post('/api/auth/logout')
        def logout(request: WebRequest):
            return self.logout(request)

        @router.get('/auth/check')
        def gateway_check(request: WebRequest):
            if not secrets.compare_digest(request.headers.get('x-crawler-gateway-key', ''), self.settings()['gateway_key']):
                raise HTTPException(404)
            session = self.session(request)
            if session:
                self.protect_write(request, session, request.headers.get('x-original-method', 'GET'))
                if request.headers.get('x-original-upgrade') and not self.origin_valid(request):
                    raise HTTPException(403, '连接来源不匹配')
            elif not (request.headers.get('x-allow-machine') == '1' and self.basic_valid(request.headers.get('authorization'))):
                raise HTTPException(401, '请先登录采集管理平台')
            header = 'Basic ' + base64.b64encode(self.credentials.encode()).decode()
            return Response(status_code=204, headers={'X-Prefect-Authorization': header, 'Cache-Control': 'no-store'})

        @router.get('/auth/prefect/settings')
        def prefect_settings(request: WebRequest):
            self.require_browser(request)
            with urlopen('http://127.0.0.1:4200/ui-settings', timeout=5) as upstream:
                data = json.load(upstream)
            # 浏览器使用网关会话；Prefect 后端仍保留原有 API 认证。
            data.update(auth=None, api_url='/api')
            return self.private(JSONResponse(data))

        @router.get('/open/prefect')
        def open_prefect(request: WebRequest):
            if not self.session(request):
                return self.login_redirect('prefect')
            return RedirectResponse('/v2/', status_code=303)

        @router.get('/open/maxun')
        def open_maxun(request: WebRequest):
            if not self.session(request):
                return self.login_redirect('maxun')
            from urllib.parse import urlencode
            try:
                destination, robot = maxun_destination(request.query_params)
            except ValueError:
                raise HTTPException(400, '机器人编号无效')
            if request.query_params.get('execution'):
                parts = destination.split('/')
                query = urlencode({'execution': parts[2], 'run': parts[4]})
            elif robot:
                query = urlencode({'robot': robot})
            else:
                query = destination.partition('?')[2]
            return self.private(RedirectResponse(self.settings()['maxun_origin'] + '/_platform/enter' + ('?' + query if query else ''), status_code=303))

        @router.get('/auth/maxun/enter')
        def maxun_enter(request: WebRequest):
            if not self.session(request):
                return self.private(RedirectResponse(self.settings()['platform_origin'] + '/collector/login?next=maxun', status_code=303))
            from urllib.error import HTTPError, URLError
            try:
                destination, robot_id = maxun_destination(request.query_params)
                username, password = self.credentials.split(':', 1)
                payload = json.dumps({'email': username + '@crawler.local', 'password': password}).encode()
                with urlopen(Request('http://127.0.0.1:18080/auth/login', data=payload, headers={'Content-Type': 'application/json'}), timeout=12) as upstream:
                    user = json.load(upstream)
                    cookies = SimpleCookie()
                    for header in upstream.headers.get_all('Set-Cookie', []):
                        cookies.load(header)
                token = cookies['token'].value
                user.pop('password', None)
                user.pop('api_key', None)
            except (HTTPError, URLError, OSError, ValueError, KeyError):
                return self.private(HTMLResponse('<h2>在线设计器暂时无法进入</h2><p>统一登录仍有效，请稍后重试或返回采集管理平台。</p>', status_code=503))
            encoded = json.dumps(user, ensure_ascii=True).replace('<', '\\u003c')
            recording = 'sessionStorage.setItem("recordingId",' + json.dumps(json.dumps(robot_id)) + ');' if robot_id else ''
            page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>正在进入在线设计器</title><p>正在进入 Maxun 在线设计器…</p><script>localStorage.setItem("user",' + json.dumps(encoded) + ');localStorage.removeItem("prefect-password");' + recording + 'location.replace(' + json.dumps(destination) + ');</script></html>'
            response = HTMLResponse(page)
            response.set_cookie('token', token, max_age=self.store.ttl, secure=True, httponly=True, samesite='lax', path='/')
            return self.private(response)

        @router.post('/auth/maxun/logout')
        def maxun_logout(request: WebRequest):
            return self.logout(request)

        @router.get('/auth/client.js')
        def client_script(request: WebRequest):
            session = self.require_browser(request)
            source = (Path(__file__).resolve().parents[1] / 'deploy/web/auth-client.js').read_text(encoding='utf-8')
            source = source.replace('__CRAWLER_SESSION__', json.dumps(session)).replace('__PLATFORM_ORIGIN__', json.dumps(self.settings()['platform_origin']))
            return self.private(Response(source, media_type='application/javascript'))

        @router.get('/auth/theme.css')
        def theme_css(request: WebRequest):
            self.require_browser(request)
            source = (Path(__file__).resolve().parents[1] / 'deploy/web/suite-theme.css').read_text(encoding='utf-8')
            return self.private(Response(source, media_type='text/css'))

        @router.get('/auth/theme.js')
        def theme_script(request: WebRequest):
            self.require_browser(request)
            source = (Path(__file__).resolve().parents[1] / 'deploy/web/suite-theme.js').read_text(encoding='utf-8')
            source += '\n' + (Path(__file__).resolve().parents[1] / 'deploy/web/maxun-recorder.js').read_text(encoding='utf-8')
            source += '\n' + (Path(__file__).resolve().parents[1] / 'deploy/web/maxun-task-links.js').read_text(encoding='utf-8')
            return self.private(Response(source, media_type='application/javascript'))
