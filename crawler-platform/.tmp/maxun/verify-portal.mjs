// 通过 SSH 内部验收真实部署；不访问 Windows 167，不改变用户现有浏览器。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const configuration=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=configuration.env.PREFECT_API_AUTH_STRING,index=auth.indexOf(':');
const browser=await chromium.launch({channel:'chrome',headless:true});
const report={date:new Date().toISOString(),method:'经 SSH 隧道与校验 CA 的 HTTPS 代理访问实际部署',checks:[],windows_167_accessed:false};
try{
 const context=await browser.newContext({httpCredentials:{username:auth.slice(0,index),password:auth.slice(index+1)},locale:'zh-CN',viewport:{width:1440,height:1050}});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:18843/collector/');
 await expect(page.getByRole('heading',{name:'采集管理平台',exact:true})).toBeVisible();
 await expect(page.locator('#stat-templates')).not.toHaveText('—');
 await expect(page.locator('#stat-prefect')).toHaveText('正常运行',{timeout:15000});
 await expect(page.locator('#maxun-state')).toHaveText('Web 服务可用');
 await expect(page.locator('.engine-grid .engine-card')).toHaveCount(3);
 await expect(page.locator('#online-designer')).toHaveAttribute('href','https://192.168.1.169:9443/');
 await page.screenshot({path:'.local/screenshots/collector-redesign-desktop.png',fullPage:true});
 report.checks.push('三个引擎卡片、实时调度与设计服务状态、固定 Maxun 地址');
 for(const view of ['maxun','easyspider','legacy','templates','runs','architecture']){
  await page.locator('.sidebar [data-view="'+view+'"]').click();
  await expect(page.locator('[data-page="'+view+'"]')).toBeVisible();
 }
 await expect(page.getByRole('heading',{name:'架构与引擎关系',exact:true})).toBeVisible();
 await page.screenshot({path:'.local/screenshots/collector-redesign-architecture.png',fullPage:true});
 await page.locator('.sidebar [data-view="legacy"]').click();
 await expect(page.getByText('尚未开放直接发布与运行',{exact:true})).toBeVisible();
 report.checks.push('六个功能页面导航、架构说明及原有爬虫真实接入状态');
 await page.locator('.sidebar [data-view="maxun"]').click();
 await page.locator('#refresh-maxun').click();
 await expect(page.locator('#maxun-message')).toContainText(/已读取|尚无录制机器人/,{timeout:20000});
 await page.screenshot({path:'.local/screenshots/collector-redesign-maxun.png',fullPage:true});
 report.checks.push('真实 Maxun 机器人 API 与发布工作区');
 // 仅将测试浏览器的内网导航映射到真实服务隧道，页面输出的实际地址保持不变。
 await context.route('https://192.168.1.169:9443/**',route=>route.fulfill({status:302,headers:{location:'http://127.0.0.1:19943/'+new URL(route.request().url()).pathname.slice(1)}}));
 await page.locator('.sidebar [data-view="overview"]').click();
 const popupPromise=context.waitForEvent('page');
 await page.locator('#online-designer').click();
 const designer=await popupPromise;
 await designer.waitForLoadState('domcontentloaded');
 await designer.locator('input[name="email"]').fill(auth.slice(0,index)+'@crawler.local');
 await designer.locator('input[name="password"]').fill(auth.slice(index+1));
 await designer.locator('button[type="submit"]').click();
 await designer.waitForURL(url=>url.pathname==='/robots',{timeout:30000});
 await expect(designer.getByText('创建机器人',{exact:true})).toBeVisible();
 report.checks.push('从新首页点击入口打开真实 Maxun 登录并进入机器人页面');
 await designer.close();
 await page.locator('.sidebar [data-view="easyspider"]').click();
 await expect(page.locator('#designer-command')).toContainText('tools\\start-designer.ps1');
 await page.locator('#file').setInputFiles('deploy/examples/demo-task.json');
 await expect(page.locator('#steps .node')).toHaveCount(5);
 await page.locator('#name').fill('界面升级验收：日期查询与导出');
 await page.locator('#patterns').fill('Data/Task_0/result/files/*.csv');
 await page.locator('#minrows').fill('6');
 await page.locator('#columns').fill('id,quantity');
 await page.locator('#publish').click();
 await expect(page.locator('#message')).toContainText('已发布版本：',{timeout:20000});
 await page.locator('.sidebar [data-view="templates"]').click();
 await page.locator('#template-search').fill('界面升级验收：日期查询与导出');
 await page.locator('#engine-filter').selectOption('maxun');
 await expect(page.locator('#templates .empty')).toContainText('没有匹配的任务');
 await page.locator('#engine-filter').selectOption('easyspider');
 const entry=page.locator('#templates article').filter({has:page.getByText('界面升级验收：日期查询与导出',{exact:true})});
 await expect(entry).toHaveCount(1);
 await entry.locator('input').fill('2026-11-12');
 await entry.getByRole('button',{name:'运行',exact:true}).click();
 await expect(page.locator('[data-page="runs"]')).toBeVisible();
 await expect(page.locator('#runs')).toContainText('COMPLETED',{timeout:150000});
 const link=page.locator('#runs a.download').first();
 await expect(link).toBeVisible();
 const downloaded=await context.request.get('http://127.0.0.1:18843'+await link.getAttribute('href'));
 if(!downloaded.ok())throw Error('产物下载失败');
 const csv=(await downloaded.body()).toString('utf8');
 if(!csv.includes('2026-11-12')||csv.trim().split(/\r?\n/).length!==7)throw Error('实际 CSV 行数或日期不匹配');
 report.run_id=(await page.locator('#runs a').first().innerText()).match(/[0-9a-f-]{36}/)?.[0];
 report.checks.push('EasySpider 原生模板导入、发布、引擎筛选、Prefect Linux 执行及真实文件下载：6 行，2026-11-12');
 await page.screenshot({path:'.local/screenshots/collector-redesign-run.png',fullPage:true});
 for(const viewport of [{width:1920,height:1080},{width:1280,height:900},{width:768,height:1024},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  for(const view of ['overview','maxun','easyspider','legacy','templates','architecture']){
   await page.locator('.sidebar [data-view="'+view+'"]').click();
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
   if(overflow){
    await page.screenshot({path:'.local/screenshots/collector-overflow.png',fullPage:true});
    console.log(await page.locator('body *').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(n=>({tag:n.tagName,id:n.id,class:n.className,width:n.getBoundingClientRect().width}))));
    throw Error('页面横向溢出：'+viewport.width+' / '+view);
   }
  }
  if(viewport.width===390){await page.locator('.sidebar [data-view="overview"]').click();await page.screenshot({path:'.local/screenshots/collector-redesign-mobile.png',fullPage:true});}
 }
 if(errors.length)throw Error('前端脚本错误：'+errors.join('; '));
 report.checks.push('1920 / 1280 / 768 / 390 像素布局无横向溢出，页面脚本无异常');
 report.passed=true;
 fs.writeFileSync('doc/多引擎工作台界面验收.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
