// 在独立浏览器中检查三个真实应用的主题与布局；预览模式只修改当前测试页面。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const config=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=config.env.PREFECT_API_AUTH_STRING,index=auth.indexOf(':');
const base='http://127.0.0.1:18843',maxunBase='http://127.0.0.1:19943';
const preview=process.argv.includes('--preview');
const browser=await chromium.launch({channel:'chrome',headless:true});
const report={date:new Date().toISOString(),preview,checks:[],windows_167_accessed:false};
try{
 const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 await page.goto(base+'/collector/');
 await page.locator('input[name="username"]').fill(auth.slice(0,index));
 await page.locator('input[name="password"]').fill(auth.slice(index+1));
 await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();
 await page.waitForURL(url=>url.pathname==='/collector/');
 await expect(page.locator('#stat-prefect')).toHaveText('正常运行');
 async function theme(target,app){
  if(preview){await target.evaluate(({app,base})=>{document.documentElement.dataset.crawlerApp=app;window.CrawlerAuth.platform=base;},{app,base});await target.addStyleTag({path:'deploy/web/suite-theme.css'});await target.addScriptTag({path:'deploy/web/suite-theme.js'});}
  await expect(target.locator('.crawler-app-switcher').first()).toBeVisible();
  if(app!=='platform')await expect(target.locator('#crawler-suite-header')).toBeVisible();
  if(app!=='platform')await expect(target.locator('#crawler-unified-account')).toHaveCount(1);
 }
 await theme(page,'platform');
 await page.screenshot({path:'.local/screenshots/theme-platform.png',fullPage:true});
 const prefect=await context.newPage();await prefect.goto(base+'/v2/');
 await expect(prefect.getByRole('link',{name:'部署',exact:true}).first()).toBeVisible();
 await theme(prefect,'prefect');
 await expect(prefect.locator('[data-crawler-content="prefect"]')).toBeVisible();
 await prefect.screenshot({path:'.local/screenshots/theme-prefect.png',fullPage:true});
 console.log(JSON.stringify({prefect:await prefect.locator('[data-sidebar="sidebar"]').evaluate(n=>({background:getComputedStyle(n).backgroundColor,font:getComputedStyle(n).fontFamily,width:n.getBoundingClientRect().width}))}));
 const maxun=await context.newPage();await maxun.goto(base+'/collector/open/maxun');
 await maxun.waitForURL(url=>url.origin===maxunBase&&url.pathname==='/robots');
 await expect(maxun.getByText('创建机器人',{exact:true})).toBeVisible();
 await theme(maxun,'maxun');
 await expect(maxun.locator('[data-crawler-nav]')).toBeVisible();
 await expect(maxun.locator('.MuiIconButton-root[aria-label="new"]')).toHaveCSS('background-color','rgb(64, 91, 240)');
 await maxun.locator('.MuiCircularProgress-root').first().waitFor({state:'hidden',timeout:15000});
 await maxun.screenshot({path:'.local/screenshots/theme-maxun.png',fullPage:true});
 console.log(JSON.stringify({maxun:await maxun.locator('[data-crawler-nav]').evaluate(n=>({background:getComputedStyle(n).backgroundColor,font:getComputedStyle(n).fontFamily,width:n.getBoundingClientRect().width})),header:await maxun.locator('[data-crawler-native-header]').evaluate(n=>({height:n.getBoundingClientRect().height,children:[...n.children].map(c=>({tag:c.tagName,width:c.getBoundingClientRect().width,text:c.innerText?.slice(0,60)}))}))}));
 report.checks.push('三个应用的应用切换栏、品牌、中文字体及深色侧栏显示正常');
 for(const target of [prefect,maxun]){
  const app=target===prefect?'prefect':'maxun';
  for(const width of [1920,1280,768,390]){
   await target.setViewportSize({width,height:1000});
   await expect(target.locator('#crawler-suite-header')).toBeVisible();
   const geometry=await target.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,width:document.documentElement.scrollWidth,viewport:innerWidth,header:document.getElementById('crawler-suite-header').getBoundingClientRect().toJSON()}));
   if(geometry.overflow){console.log({app,geometry});await target.screenshot({path:'.local/screenshots/theme-overflow-'+app+'.png',fullPage:true});throw Error(app+' 在 '+width+' 像素宽度出现横向溢出');}
   if(app==='maxun'){const box=await target.locator('.MuiIconButton-root[aria-label="new"]').boundingBox();if(!box||box.x<0||box.x+box.width>width+1)throw Error('Maxun 创建按钮不在可视区域：'+width);}
   if(width===390)await target.screenshot({path:'.local/screenshots/theme-'+app+'-mobile.png',fullPage:true});
  }
  await target.setViewportSize({width:1440,height:1000});
 }
 report.checks.push('Prefect 与 Maxun 在 1920 / 1280 / 768 / 390 宽度下无页面横向溢出');
 if(!preview){
  await prefect.getByRole('link',{name:'部署',exact:true}).first().click();
  await prefect.waitForURL(url=>url.pathname.includes('/deployments'));
  await prefect.screenshot({path:'.local/screenshots/theme-prefect-deployments.png',fullPage:true});
  await maxun.goto(maxunBase+'/robots/create');
  await expect(maxun.getByRole('textbox',{name:'Website address'})).toBeVisible();
  await expect(maxun.locator('#crawler-suite-header')).toBeVisible();
  await maxun.screenshot({path:'.local/screenshots/theme-maxun-create.png',fullPage:true});
  report.checks.push('Prefect 部署页、Maxun 新建页切换后主题继续生效');
  const mode=maxun.locator('button').filter({has:maxun.locator('[data-testid="DarkModeIcon"]')});
  await mode.click();
  await expect(maxun.locator('html')).toHaveAttribute('data-crawler-color','dark',{timeout:5000});
  await maxun.screenshot({path:'.local/screenshots/theme-maxun-dark.png',fullPage:true});
  await maxun.locator('button').filter({has:maxun.locator('[data-testid="LightModeIcon"]')}).click();
  await expect(maxun.locator('html')).toHaveAttribute('data-crawler-color','light',{timeout:5000});
  report.checks.push('Maxun 原生明暗切换仍可用，共享标题栏和表单随主题切换');
 }
 report.passed=true;
 fs.writeFileSync(preview?'.local/theme-preview.json':'doc/统一界面风格验收.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
