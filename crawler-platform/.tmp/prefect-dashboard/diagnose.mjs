// 复现真实调度首页，记录浏览器异常与失败接口，不输出登录凭据。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium} = require('@playwright/test');
const configuration = JSON.parse(fs.readFileSync('.local/client.json', 'utf8'));
const auth = configuration.env.PREFECT_API_AUTH_STRING;
const split = auth.indexOf(':');
const base = 'http://127.0.0.1:18843';
const browser = await chromium.launch({channel: 'chrome', headless: true});
const report = {errors: [], console: [], failures: [], api: []};
try {
  const context = await browser.newContext({viewport: {width: 1600, height: 1000}});
  const page = await context.newPage();
  page.on('pageerror', error => report.errors.push(error.stack || error.message));
  page.on('console', message => {if (['error', 'warning'].includes(message.type())) report.console.push(message.text());});
  page.on('requestfailed', request => report.failures.push({url: request.url(), error: request.failure()?.errorText}));
  page.on('response', async response => {
    if (response.url().includes('/api/') || response.status() >= 400) {
      const item = {url: response.url(), status: response.status()};
      report.api.push(item);
      if (response.status() >= 400) item.body = (await response.text().catch(() => '')).slice(0, 2000);
    }
  });
  await page.goto(base + '/collector/login');
  await page.locator('[name="username"]').fill(auth.slice(0, split));
  await page.locator('[name="password"]').fill(auth.slice(split + 1));
  await page.getByRole('button', {name: '登录统一工作台', exact: true}).click();
  await page.waitForURL(base + '/collector/');
  await page.goto(base + '/v2/dashboard?seconds=-86400');
  await page.waitForTimeout(12000);
  report.url = page.url();
  report.text = (await page.locator('body').innerText()).slice(0, 7000);
  await page.screenshot({path: '.local/screenshots/prefect-dashboard-before.png', fullPage: true});
  const session = await (await context.request.get(base + '/collector/api/auth/me')).json();
  await context.request.post(base + '/collector/api/auth/logout', {headers: {Origin: base, 'X-Crawler-CSRF': session.csrf}});
  fs.writeFileSync('.local/prefect-dashboard-diagnose.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
