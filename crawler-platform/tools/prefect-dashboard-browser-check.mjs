// 验证真实调度首页内容、数据库接口及邻近页面，避免只检查 URL 就误报通过。
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium, expect} = require('@playwright/test');
const configuration = JSON.parse(fs.readFileSync('.local/client.json', 'utf8'));
const auth = configuration.env.PREFECT_API_AUTH_STRING;
const split = auth.indexOf(':');
const base = 'http://127.0.0.1:18843';
const browser = await chromium.launch({channel: 'chrome', headless: true});
const report = {date: new Date().toISOString(), checks: [], api_errors: [], frontend_errors: [], passed: false};
const check = message => {report.checks.push(message); console.log(message);};
let context;
try {
  context = await browser.newContext({viewport: {width: 1600, height: 1000}, locale: 'zh-CN'});
  const page = await context.newPage();
  page.on('pageerror', error => report.frontend_errors.push(error.message));
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 400) {
      report.api_errors.push({url: new URL(response.url()).pathname, status: response.status()});
    }
  });
  await page.goto(base + '/collector/login');
  await page.locator('[name="username"]').fill(auth.slice(0, split));
  await page.locator('[name="password"]').fill(auth.slice(split + 1));
  await page.getByRole('button', {name: '登录统一工作台', exact: true}).click();
  await page.waitForURL(base + '/collector/');

  for (const endpoint of ['/api/flow_runs/filter', '/api/deployments/filter', '/api/work_pools/filter']) {
    const response = await context.request.post(base + endpoint, {data: {limit: 1}, headers: {Origin: base, 'X-Crawler-CSRF': (await (await context.request.get(base + '/collector/api/auth/me')).json()).csrf}});
    assert.equal(response.status(), 200, endpoint);
    assert.ok(Array.isArray(await response.json()), endpoint);
  }
  check('运行记录、部署、工作池的数据库查询接口均返回 200，原有数据可读取');

  await page.goto(base + '/v2/dashboard?seconds=-86400');
  await expect(page.locator('#hide-subflows')).toBeVisible({timeout: 45000});
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0, {timeout: 45000});
  await expect(page.getByText('Something went wrong', {exact: true})).toHaveCount(0);
  await page.screenshot({path: '.local/screenshots/prefect-dashboard-recovered.png', fullPage: true});
  check('按用户截图中的完整地址打开，监控筛选和实际卡片成功加载，无错误页或残留加载占位');

  await page.reload();
  await expect(page.locator('#hide-subflows')).toBeVisible({timeout: 30000});
  await page.goto(base + '/v2/deployments');
  await expect(page.getByText('linux-169', {exact: true}).first()).toBeVisible({timeout: 30000});
  await page.goto(base + '/v2/work-pools');
  await expect(page.getByText('dev-linux', {exact: true}).first()).toBeVisible({timeout: 30000});
  check('刷新监控首页、部署列表及工作池列表均正常显示');

  await page.goto(base + '/collector/');
  await expect(page.getByRole('heading', {name: '采集管理平台', exact: true})).toBeVisible();
  await expect(page.locator('#stat-prefect')).toHaveText('正常运行', {timeout: 15000});
  const platform = await (await context.request.get(base + '/collector/api/platform')).json();
  assert.equal(platform.prefect.state, 'ready');
  const machine = await browser.newContext();
  try {
    const response = await machine.request.post(base + '/api/flow_runs/filter', {data: {limit: 1}, headers: {Authorization: 'Basic ' + Buffer.from(auth).toString('base64')}});
    assert.equal(response.status(), 200);
  } finally {await machine.close();}
  check('采集工作台健康显示正常，Worker 原有机器认证可读取调度记录');
  assert.deepEqual(report.api_errors, []);
  assert.deepEqual(report.frontend_errors, []);
  report.passed = true;
} finally {
  if (context) {
    try {
      const session = await (await context.request.get(base + '/collector/api/auth/me')).json();
      await context.request.post(base + '/collector/api/auth/logout', {headers: {Origin: base, 'X-Crawler-CSRF': session.csrf}});
    } catch {}
  }
  await browser.close();
  fs.writeFileSync('doc/Prefect调度监控浏览器验收.json', JSON.stringify(report, null, 2));
}
