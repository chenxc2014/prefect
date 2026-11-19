// 在实际开发环境验证复选框、浏览器重启记忆、退出撤销及统一登录兼容性。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';

const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium, expect} = require('@playwright/test');
const configuration = JSON.parse(fs.readFileSync('.local/client.json', 'utf8'));
const auth = configuration.env.PREFECT_API_AUTH_STRING;
const separator = auth.indexOf(':');
const base = 'http://127.0.0.1:18843';
const cookieName = '__Host-crawler_session';
const report = {date: new Date().toISOString(), checks: [], frontend_errors: [], passed: false};
const check = message => {report.checks.push(message); console.log(message);};
const options = {channel: 'chrome', headless: true, locale: 'zh-CN', viewport: {width: 1440, height: 1000}};
let context;

async function launch(profile) {
  context = await chromium.launchPersistentContext(profile, options);
  const page = context.pages()[0] || await context.newPage();
  page.on('pageerror', error => report.frontend_errors.push(error.message));
  return page;
}

async function signIn(page, remember) {
  await page.goto(base + '/collector/login');
  await page.locator('[name="username"]').fill(auth.slice(0, separator));
  await page.locator('[name="password"]').fill(auth.slice(separator + 1));
  await page.getByRole('checkbox', {name: '记住密码', exact: true}).setChecked(remember);
  const posted = page.waitForRequest(request => request.url() === base + '/collector/login' && request.method() === 'POST');
  await page.getByRole('button', {name: '登录统一工作台', exact: true}).click();
  const form = new URLSearchParams((await posted).postData());
  assert.equal(form.get('remember'), remember ? '1' : null);
  await page.waitForURL(base + '/collector/');
  await expect(page.getByRole('heading', {name: '采集管理平台', exact: true})).toBeVisible();
  return (await context.cookies()).find(cookie => cookie.name === cookieName);
}

async function logout() {
  const me = await context.request.get(base + '/collector/api/auth/me');
  const session = await me.json();
  const response = await context.request.post(base + '/collector/api/auth/logout', {
    headers: {Origin: base, 'X-Crawler-CSRF': session.csrf},
  });
  assert.equal(response.status(), 200);
}

try {
  fs.mkdirSync('.local/screenshots', {recursive: true});
  const normalProfile = fs.mkdtempSync(path.resolve('.local/remember-normal-'));
  let page = await launch(normalProfile);
  await page.goto(base + '/collector/login');
  const checkbox = page.getByRole('checkbox', {name: '记住密码', exact: true});
  await expect(checkbox).toBeVisible();
  await expect(checkbox).not.toBeChecked();
  await checkbox.focus();
  await checkbox.press('Space');
  await expect(checkbox).toBeChecked();
  await checkbox.press('Space');
  await expect(checkbox).not.toBeChecked();
  await expect(page.locator('[name="username"]')).toHaveAttribute('autocomplete', 'username');
  await expect(page.locator('[name="password"]')).toHaveAttribute('autocomplete', 'current-password');
  for (const width of [390, 1440]) {
    await page.setViewportSize({width, height: 1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    const box = await checkbox.boundingBox();
    assert.equal(box.width, 16);
    assert.equal(box.height, 16);
    await page.screenshot({path: `.local/screenshots/remember-login-${width}.png`, fullPage: true});
  }
  check('桌面和手机宽度显示正常；复选框默认不勾选，支持键盘，保留浏览器密码自动填充标记');

  await page.locator('[name="username"]').fill(auth.slice(0, separator));
  await page.locator('[name="password"]').fill('incorrect-remember-login-test');
  await checkbox.check();
  await page.getByRole('button', {name: '登录统一工作台', exact: true}).click();
  await expect(page.getByRole('alert')).toHaveText('用户名或密码不正确');
  await expect(page.getByRole('button', {name: '登录统一工作台', exact: true})).toBeEnabled();
  assert.equal((await context.cookies()).some(cookie => cookie.name === cookieName), false);
  check('错误密码仅提示失败，不生成记忆登录凭证，按钮可继续操作');

  const normalCookie = await signIn(page, false);
  assert.equal(normalCookie.expires, -1);
  const normalSession = await (await context.request.get(base + '/collector/api/auth/me')).json();
  assert.ok(Math.abs(normalSession.expires - Date.now() / 1000 - 8 * 3600) < 60);
  await context.close();
  context = null;
  page = await launch(normalProfile);
  await page.goto(base + '/collector/');
  await page.waitForURL(url => url.pathname === '/collector/login');
  const normalLogout = await context.request.post(base + '/collector/api/auth/logout', {
    headers: {Origin: base, Cookie: `${cookieName}=${normalCookie.value}`, 'X-Crawler-CSRF': normalSession.csrf},
  });
  assert.equal(normalLogout.status(), 200);
  await context.close();
  context = null;
  check('未勾选时为普通会话，有效期 8 小时；完全关闭浏览器并重开同一配置后要求重新登录');

  const rememberedProfile = fs.mkdtempSync(path.resolve('.local/remember-persistent-'));
  page = await launch(rememberedProfile);
  const rememberedCookie = await signIn(page, true);
  assert.ok(Math.abs(rememberedCookie.expires - Date.now() / 1000 - 30 * 86400) < 60);
  assert.equal(rememberedCookie.secure, true);
  assert.equal(rememberedCookie.httpOnly, true);
  assert.equal(rememberedCookie.sameSite, 'Lax');
  const rememberedSession = await (await context.request.get(base + '/collector/api/auth/me')).json();
  assert.ok(Math.abs(rememberedSession.expires - Date.now() / 1000 - 30 * 86400) < 60);
  assert.equal(await page.evaluate(password => {
    const values = [...Object.values(localStorage), ...Object.values(sessionStorage), document.cookie];
    return values.some(value => value.includes(password));
  }, auth.slice(separator + 1)), false);
  await context.close();
  context = null;
  page = await launch(rememberedProfile);
  await page.goto(base + '/collector/');
  await expect(page.getByRole('heading', {name: '采集管理平台', exact: true})).toBeVisible();
  await page.goto(base + '/collector/login?next=prefect');
  await page.waitForURL(url => url.pathname.startsWith('/v2'));
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  check('勾选后 Cookie 与服务端均为 30 天；完全关闭并重开同一浏览器后，工作台及 Prefect 继续免登录');

  await page.goto(base + '/collector/');
  await page.locator('[data-crawler-logout]').click();
  await page.waitForURL(url => url.pathname === '/collector/login');
  const replay = await context.request.get(base + '/collector/api/auth/me', {
    headers: {Cookie: `${cookieName}=${rememberedCookie.value}`},
  });
  assert.equal(replay.status(), 401);
  await context.close();
  context = null;
  page = await launch(rememberedProfile);
  await page.goto(base + '/collector/');
  await page.waitForURL(url => url.pathname === '/collector/login');
  check('主动退出清除记忆且撤销服务端令牌；旧令牌重放被拒绝，再次重开浏览器仍要求登录');
  assert.deepEqual(report.frontend_errors, []);
  report.passed = true;
} finally {
  if (context) {
    try {await logout();} catch {}
    await context.close();
  }
  fs.writeFileSync('doc/记住密码浏览器验收.json', JSON.stringify(report, null, 2));
}
