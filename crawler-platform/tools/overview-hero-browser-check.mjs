// 验证概览关系图的可读性、响应式布局和入口，不触发采集运行。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium, expect} = require('@playwright/test');
const base = 'http://127.0.0.1:18843';
const preview = process.argv.includes('--preview');
const config = JSON.parse(fs.readFileSync('.local/client.json', 'utf8'));
const auth = config.env.PREFECT_API_AUTH_STRING;
const split = auth.indexOf(':');
const browser = await chromium.launch({channel: 'chrome', headless: true});
const report = {checked_at: new Date().toISOString(), preview, viewports: [], collection_runs_submitted: 0};
try {
  const context = await browser.newContext({locale: 'zh-CN', viewport: {width: 1692, height: 1000}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/collector/');
  await page.locator('[name="username"]').fill(auth.slice(0, split));
  await page.locator('[name="password"]').fill(auth.slice(split + 1));
  await page.getByRole('button', {name: '登录统一工作台', exact: true}).click();
  await page.waitForURL(base + '/collector/');
  if (preview) {
    await page.route(base + '/collector/', route => route.fulfill({contentType: 'text/html; charset=utf-8', body: fs.readFileSync('deploy/web/collector.html', 'utf8')}));
    await page.reload();
  }
  await expect(page.locator('#stat-prefect')).toHaveText('正常运行', {timeout: 30000});
  await expect(page.locator('.hero-engine')).toHaveCount(3);
  for (const width of [1920, 1692, 1440, 1280, 1024, 768, 600, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await page.evaluate(() => scrollTo(0, 0));
    const layout = await page.evaluate(() => {
      const hero = document.querySelector('.overview-hero');
      const graph = document.querySelector('.hero-diagram');
      const bounds = hero.getBoundingClientRect();
      const nodes = [...graph.querySelectorAll('strong, span, small')];
      return {
        width: innerWidth, hero_height: bounds.height, diagram_width: graph.getBoundingClientRect().width,
        minimum_label_font: Math.min(...nodes.map(node => parseFloat(getComputedStyle(node).fontSize))),
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
        clipped: nodes.some(node => {const rect = node.getBoundingClientRect(); return rect.left < bounds.left || rect.right > bounds.right || rect.bottom > bounds.bottom || node.scrollWidth > node.clientWidth + 1;})
      };
    });
    if (layout.overflow || layout.clipped || layout.minimum_label_font < 12) throw Error('关系图溢出或字体过小：' + JSON.stringify(layout));
    await expect(page.locator('.hero-orchestrator')).toBeVisible();
    await expect(page.locator('.hero-result')).toBeVisible();
    if (width >= 1400 && layout.hero_height > 340) throw Error('桌面横幅过高');
    if ([1692, 1440, 768, 390].includes(width)) {
      await page.screenshot({path: `.local/screenshots/overview-hero-${preview ? 'preview-' : ''}${width}.png`, fullPage: true});
    }
    report.viewports.push(layout);
  }
  await page.locator('.overview-hero [data-view="easyspider"]').click();
  await expect(page.locator('[data-page="easyspider"]')).toBeVisible();
  await expect(page.locator('#online-designer')).toHaveAttribute('target', '_blank');
  if (errors.length) throw Error(errors.join('\n'));
  report.passed = true;
  fs.writeFileSync(preview ? '.local/overview-hero-preview.json' : 'doc/概览横幅放大验收.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
