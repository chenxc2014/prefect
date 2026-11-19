"""验证统一登录的会话边界、撤销、请求校验与原有机器认证兼容性。"""
import base64
from email.message import Message
from http.cookies import SimpleCookie
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from runtime.auth import SessionStore
from tools.portal_auth import PortalAuth, COOKIE, LOGIN_COOKIE, REMEMBER_TTL, maxun_destination


class UnifiedAuthTest(unittest.TestCase):
    def test_maxun_destination_only_accepts_known_internal_routes(self):
        identifier = '66af1f99-bd71-4c86-b190-8d96a7b6176d'
        self.assertEqual(maxun_destination({'robot': identifier}), ('/robots/' + identifier + '/edit', identifier))
        self.assertEqual(maxun_destination({'execution': identifier, 'run': identifier}), ('/runs/' + identifier + '/run/' + identifier, None))
        self.assertEqual(maxun_destination({'template': 'a' * 64, 'section': 'https://outside.test'})[0], '/robots?template=' + 'a' * 64 + '&section=published')
        self.assertEqual(maxun_destination({'template': '../outside'}), ('/robots', None))
        with self.assertRaises(ValueError):
            maxun_destination({'robot': '../outside'})

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        config = root / 'sso.json'
        config.write_text(json.dumps({'gateway_key': 'unit-test-gateway', 'platform_origin': 'https://platform.test', 'maxun_origin': 'https://designer.test', 'origins': ['https://platform.test', 'https://designer.test']}))
        self.auth = PortalAuth('developer:unit-test-password', root / 'sessions', config)
        app = FastAPI()
        app.include_router(self.auth.router)
        self.client = TestClient(app, base_url='https://platform.test', follow_redirects=False)
        self.addCleanup(self.client.close)

    def login(self, password='unit-test-password', next_app='platform', origin='https://platform.test', remember=None):
        # 获取独立的登录表单校验值，同时允许 POST 携带原会话以测试替换行为。
        self.client.get('/login', headers={'Cookie': ''})
        nonce = self.client.cookies.get(LOGIN_COOKIE)
        data = {'username': 'developer', 'password': password, 'csrf': nonce, 'next': next_app}
        if remember is not None:
            data['remember'] = remember
        return self.client.post('/login', data=data, headers={'Origin': origin, 'Accept': 'application/json'})

    def session_cookie(self, response):
        cookies = SimpleCookie()
        for header in response.headers.get_list('set-cookie'):
            cookies.load(header)
        return cookies[COOKIE]

    def test_normal_login_uses_browser_session_cookie_and_eight_hour_expiry(self):
        self.auth.store.clock = lambda: 1000
        response = self.login()
        cookie = self.session_cookie(response)
        self.assertEqual(cookie['max-age'], '')
        self.assertEqual(cookie['expires'], '')
        self.assertEqual(self.auth.store.get(cookie.value)['expires'], 1000 + 8 * 3600)
        self.auth.store.clock = lambda: 1000 + 8 * 3600
        self.assertIsNone(self.auth.store.get(cookie.value))

    def test_remembered_login_survives_restart_and_expires_after_thirty_days(self):
        self.auth.store.clock = lambda: 1000
        response = self.login(remember='1')
        cookie = self.session_cookie(response)
        self.assertEqual(cookie['max-age'], str(REMEMBER_TTL))
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'lax')
        self.assertEqual(self.auth.store.get(cookie.value)['expires'], 1000 + REMEMBER_TTL)
        restarted = SessionStore(self.auth.store.path.parent, clock=lambda: 1000 + REMEMBER_TTL - 1)
        self.assertIsNotNone(restarted.get(cookie.value))
        with TestClient(self.client.app, base_url='https://platform.test', follow_redirects=False) as reopened:
            reopened.cookies.set(COOKIE, cookie.value)
            self.assertEqual(reopened.get('/api/auth/me').status_code, 200)
            self.assertEqual(reopened.get('/login?next=prefect').headers['location'], '/v2/')
        restarted.clock = lambda: 1000 + REMEMBER_TTL
        self.assertIsNone(restarted.get(cookie.value))
        self.assertNotIn(b'unit-test-password', self.auth.store.path.read_bytes())

    def test_unchecked_or_unrecognized_remember_values_do_not_persist(self):
        for value in ('', '0', 'false', 'unexpected'):
            with self.subTest(value=value):
                response = self.login(remember=value)
                self.assertEqual(self.session_cookie(response)['max-age'], '')

    def test_remembered_login_is_revoked_on_logout_and_old_token_cannot_be_replayed(self):
        response = self.login(remember='1')
        token = self.session_cookie(response).value
        session = self.client.get('/api/auth/me').json()
        response = self.client.post('/api/auth/logout', headers={'Origin': 'https://platform.test', 'X-Crawler-CSRF': session['csrf']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session_cookie(response)['max-age'], '0')
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_normal_login_replaces_and_revokes_previous_remembered_session(self):
        previous = self.session_cookie(self.login(remember='1')).value
        response = self.login()
        self.assertEqual(self.session_cookie(response)['max-age'], '')
        self.assertIsNone(self.auth.store.get(previous))
        self.assertIsNotNone(self.auth.store.get(self.session_cookie(response).value))

    def test_failed_remembered_login_does_not_issue_session(self):
        response = self.login(password='incorrect', remember='1')
        self.assertEqual(response.status_code, 401)
        self.assertIsNone(self.client.cookies.get(COOKIE))

    def gateway_headers(self):
        return {'X-Crawler-Gateway-Key': 'unit-test-gateway'}

    def test_session_cookie_is_secure_and_password_never_returned(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        header = response.headers['set-cookie']
        self.assertIn('HttpOnly', header)
        self.assertIn('Secure', header)
        self.assertIn('SameSite=lax', header)
        self.assertNotIn('unit-test-password', response.text)
        self.assertEqual(self.client.get('/api/auth/me').json()['username'], 'developer')
        token = self.client.cookies.get(COOKIE)
        self.assertNotIn(token.encode(), self.auth.store.path.read_bytes())

    def test_invalid_nonce_origin_and_external_redirect_are_rejected(self):
        self.client.get('/login')
        bad = self.client.post('/login', data={'username': 'developer', 'password': 'unit-test-password', 'csrf': 'wrong'}, headers={'Origin': 'https://platform.test'})
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(self.login(origin='https://untrusted.test').status_code, 403)
        self.assertEqual(self.login(next_app='https://untrusted.test').json()['next'], '/collector/')

    def test_login_is_limited_and_bad_password_does_not_create_session(self):
        for _ in range(8):
            self.assertEqual(self.login(password='incorrect').status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        self.assertIsNone(self.client.cookies.get(COOKIE))

    def test_login_challenge_remains_valid_across_parallel_page_loads(self):
        first = self.client.get('/login').text
        nonce = self.client.cookies.get(LOGIN_COOKIE)
        self.client.get('/login?next=prefect')
        self.assertEqual(self.client.cookies.get(LOGIN_COOKIE), nonce)
        self.assertIn(nonce, first)

    def test_logout_revokes_cookie_replay_and_requires_csrf(self):
        self.login()
        token = self.client.cookies.get(COOKIE)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': 'https://platform.test'}).status_code, 403)
        session = self.client.get('/api/auth/me').json()
        response = self.client.post('/api/auth/logout', headers={'Origin': 'https://platform.test', 'X-Crawler-CSRF': session['csrf']})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.auth.store.get(token))
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_gateway_secret_and_machine_auth_scope(self):
        self.assertEqual(self.client.get('/auth/check').status_code, 404)
        headers = self.gateway_headers()
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 401)
        headers['Authorization'] = 'Basic ' + base64.b64encode(b'developer:unit-test-password').decode()
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 401)
        headers['X-Allow-Machine'] = '1'
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 204)
        headers['Authorization'] = 'Basic invalid'
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 401)

    def test_gateway_checks_mutations_and_websocket_origin(self):
        self.login()
        session = self.client.get('/api/auth/me').json()
        headers = self.gateway_headers() | {'X-Original-Method': 'POST', 'Origin': 'https://platform.test'}
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 403)
        headers['X-Crawler-CSRF'] = session['csrf']
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 204)
        headers.update({'X-Original-Method': 'GET', 'X-Original-Upgrade': 'websocket', 'Origin': 'https://untrusted.test'})
        self.assertEqual(self.client.get('/auth/check', headers=headers).status_code, 403)

    def test_expiry_and_service_restart_preserve_correct_boundary(self):
        now = [1000]
        store = SessionStore(Path(self.directory.name) / 'clocked', ttl=60, clock=lambda: now[0])
        token, _ = store.create('developer')
        restarted = SessionStore(Path(self.directory.name) / 'clocked', ttl=60, clock=lambda: now[0])
        self.assertIsNotNone(restarted.get(token))
        now[0] = 1060
        self.assertIsNone(restarted.get(token))
        self.assertIsNone(store.get(token + 'tampered'))

    def test_maxun_bridge_keeps_password_and_integration_key_server_side(self):
        self.login()
        response = io.BytesIO(json.dumps({'id': 'test-user', 'email': 'developer@crawler.local', 'password': 'unexpected-secret', 'api_key': 'integration-secret'}).encode())
        response.headers = Message()
        response.headers.add_header('Set-Cookie', 'token=test-native-token; HttpOnly; Path=/')
        with patch('tools.portal_auth.urlopen', return_value=response) as upstream:
            result = self.client.get('/auth/maxun/enter')
        self.assertEqual(result.status_code, 200)
        sent = json.loads(upstream.call_args.args[0].data)
        self.assertEqual(sent['password'], 'unit-test-password')
        for value in ('unit-test-password', 'unexpected-secret', 'integration-secret', 'test-native-token'):
            self.assertNotIn(value, result.text)
        cookies = SimpleCookie()
        cookies.load(result.headers['set-cookie'])
        self.assertEqual(cookies['token'].value, 'test-native-token')
        self.assertTrue(cookies['token']['httponly'])


if __name__ == '__main__':
    unittest.main()
