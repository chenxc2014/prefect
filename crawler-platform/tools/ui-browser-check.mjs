// 使用独立无头浏览器验证中文展示，不复用用户浏览器或关闭证书验证。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=process.cwd();
const require=createRequire(path.join(root,'vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const configuration=JSON.parse(fs.readFileSync(path.join(root,'.local/client.json'),'utf8'));
const output=path.join(root,'.local/screenshots');
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://127.0.0.1:18843/v2/',{waitUntil:'networkidle'});
  await expect(page.getByRole('button',{name:'登录',exact:true})).toBeVisible();
  await page.getByPlaceholder('请输入账号:密码').fill(configuration.env.PREFECT_API_AUTH_STRING);
  await page.getByRole('button',{name:'登录',exact:true}).click();
  await expect(page.getByRole('link',{name:'概览',exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByText('概览',{exact:true})).toHaveCount(2,{timeout:30000});
  await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0,{timeout:45000});
  await page.screenshot({path:path.join(output,'zh-dashboard.png'),fullPage:true});
  await page.getByRole('link',{name:'部署',exact:true}).click();
  await expect(page.getByText('linux-169',{exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByText('windows-167',{exact:true})).toBeVisible();
  await page.screenshot({path:path.join(output,'zh-deployments.png'),fullPage:true});
  await page.getByRole('link',{name:'工作池',exact:true}).click();
  await expect(page.getByText('dev-linux',{exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByText('dev-windows',{exact:true})).toBeVisible();
  await page.screenshot({path:path.join(output,'zh-work-pools.png'),fullPage:true});
  await page.getByRole('button',{name:'语言：简体中文 / English',exact:true}).click();
  await expect(page.getByRole('link',{name:'Dashboard',exact:true})).toBeVisible({timeout:20000});
  await page.getByRole('button',{name:'Language: English / 中文',exact:true}).click();
  await expect(page.getByRole('link',{name:'概览',exact:true})).toBeVisible({timeout:20000});
  const report={passed:true,source:process.env.CRAWLER_UI_TEST_SOURCE,checks:['中文登录','中文导航','概览内容加载','部署列表与业务名称保留','工作池列表与业务名称保留','英文切换','切回中文'],screenshots:output};
  fs.writeFileSync(path.join(root,'doc/界面汉化浏览器验证.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
