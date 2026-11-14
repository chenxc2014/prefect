// 用独立浏览器检查文档新增章节的桌面与手机布局。
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('../vendor/prefect/ui-v2/node_modules/@playwright/test');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const [name, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      await page.goto(pathToFileURL(path.resolve('doc/爬虫任务编排与执行平台.html')).href + '#deployment-directories');
      await page.locator('#deployment-directories h2').waitFor();
      await page.evaluate(() => {
        document.documentElement.style.scrollBehavior = 'auto';
        document.querySelector('#deployment-directories').scrollIntoView({ behavior: 'instant', block: 'start' });
      });
      const result = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        tables: document.querySelectorAll('#deployment-directories table').length,
        heading: document.querySelector('#deployment-directories h2').textContent,
      }));
      if (result.overflow || result.tables !== 4) throw new Error(JSON.stringify(result));
      await page.screenshot({ path: `.local/screenshots/directories-${name}.png` });
      console.log(JSON.stringify({ layout: name, passed: true, ...result }));
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
