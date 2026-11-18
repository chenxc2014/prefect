// 核验真实部署的用途分类、业务归组和运行状态，不提交采集运行或发布新版本。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const config=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=config.env.PREFECT_API_AUTH_STRING,index=auth.indexOf(':');
const base='http://127.0.0.1:18843';
const browser=await chromium.launch({channel:'chrome',headless:true});
const report={checked_at:new Date().toISOString(),checks:[],windows_167_accessed:false,collection_runs_submitted:0,versions_published:0};
const check=message=>{report.checks.push(message);console.log(message)};
try{
 const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1050}});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/collector/');
 await page.locator('input[name="username"]').fill(auth.slice(0,index));
 await page.locator('input[name="password"]').fill(auth.slice(index+1));
 await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();
 await page.waitForURL(url=>url.pathname==='/collector/');
 await expect(page.locator('#stat-business-tasks')).toHaveText('1');
 await expect(page.locator('#stat-templates')).toHaveText('2');
 await expect(page.locator('#stat-demo')).toHaveText('1');
 await expect(page.locator('#stat-acceptance')).toHaveText('5');
 await expect(page.locator('#task-status-note')).toContainText('状态更新于',{timeout:25000});
 await expect(page.locator('#stat-current-runs')).toHaveText('正在执行 0 个 · 等待或暂停 0 个');
 const templates=await (await context.request.get(base+'/collector/api/templates')).json();
 const statuses=await (await context.request.get(base+'/collector/api/template-status')).json();
 if(templates.length!==8||Object.keys(statuses.templates).length!==8)throw Error('活动版本数量改变或状态缺失');
 if(new Set(templates.filter(t=>t.purpose==='business').map(t=>t.task_key)).size!==1)throw Error('业务归组不正确');
 report.classification_counts=Object.fromEntries(['business','demo','acceptance'].map(p=>[p,templates.filter(t=>t.purpose===p).length]));
 report.version_ids=templates.map(t=>t.id);
 check('真实接口保留8个版本：业务2、演示1、验收5；千金两种引擎归为1项业务');
 await page.screenshot({path:'.local/screenshots/task-catalog-overview.png',fullPage:true});
 await page.locator('.sidebar [data-view="templates"]').click();
 await expect(page.locator('#templates .task-group')).toHaveCount(1);
 await expect(page.locator('#templates .template-card')).toHaveCount(2);
 await expect(page.locator('#templates')).toContainText('未配置定时调度');
 await expect(page.locator('#templates')).toContainText('最近运行：成功');
 await expect(page.locator('#templates .badge').filter({hasText:'业务采集'})).toHaveCount(2);
 await page.screenshot({path:'.local/screenshots/task-catalog-business.png',fullPage:true});
 check('任务列表默认只显示业务，展开同一业务的两种引擎，运行和调度状态独立展示');
 await page.locator('.purpose-tabs [data-purpose-filter="demo"]').click();
 await expect(page.locator('#templates .template-card')).toHaveCount(1);
 await expect(page.locator('#templates summary')).toContainText('模拟演示');
 await page.locator('.purpose-tabs [data-purpose-filter="acceptance"]').click();
 await expect(page.locator('#templates .template-card')).toHaveCount(5);
 await expect(page.locator('#templates .task-group')).toHaveCount(4);
 await page.locator('#template-search').fill('故障注入');
 await expect(page.locator('#templates .template-card')).toHaveCount(1);
 await page.locator('#templates summary').click();
 await expect(page.locator('#templates')).toContainText('最近运行：失败');
 await page.locator('.purpose-tabs [data-purpose-filter="all"]').click();
 await expect(page.locator('#templates .template-card')).toHaveCount(8);
 await page.locator('#engine-filter').selectOption('maxun');
 await expect(page.locator('#templates .template-card')).toHaveCount(1);
 check('用途切换、数量、搜索与引擎筛选正确；故障注入仍显示真实失败结果');
 await page.locator('.sidebar [data-view="overview"]').click();
 await page.locator('.stats [data-purpose-filter="acceptance"]').click();
 await expect(page.locator('[data-page="templates"]')).toBeVisible();
 await expect(page.locator('.purpose-tabs [data-purpose-filter="acceptance"]')).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('#templates .template-card')).toHaveCount(5);
 check('概览用途数字可直接进入对应筛选列表');
 await page.locator('.sidebar [data-view="easyspider"]').click();
 await page.locator('#file').setInputFiles('deploy/examples/demo-task.json');
 await page.locator('#publish').click();
 await expect(page.locator('#message')).toContainText('请选择任务用途');
 await page.locator('#easyspider-purpose').selectOption('acceptance');
 await page.locator('#publish').click();
 await expect(page.locator('#message')).toContainText('请填写所属任务名称');
 for(const prefix of ['easyspider-','maxun-']){
  await expect(page.locator('#'+prefix+'purpose')).toHaveAttribute('required','');
  await expect(page.locator('#'+prefix+'task-name')).toHaveAttribute('required','');
 }
 const session=await (await context.request.get(base+'/collector/api/auth/me')).json();
 const headers={Origin:base,'X-Crawler-CSRF':session.csrf};
 for(const endpoint of ['templates','maxun/publish']){
  const response=await context.request.post(base+'/collector/api/'+endpoint,{data:{},headers});
  if(response.status()!==400||!(await response.json()).detail.includes('请选择任务用途'))throw Error('发布接口未拒绝缺少用途的请求：'+endpoint+' / '+response.status());
 }
 check('两个发布入口必选用途和所属任务，服务端拒绝绕过界面的缺少用途请求');
 await page.locator('.sidebar [data-view="overview"]').click();
 await page.locator('.stats [data-purpose-filter="business"]').first().click();
 for(const viewport of [{width:1440,height:1050},{width:768,height:1024},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  for(const view of ['overview','templates','easyspider','maxun']){
   await page.locator('.sidebar [data-view="'+view+'"]').click();
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('页面横向溢出：'+viewport.width+'/'+view);
  }
 }
 await page.locator('.sidebar [data-view="templates"]').click();
 await page.screenshot({path:'.local/screenshots/task-catalog-mobile.png',fullPage:true});
 if(errors.length)throw Error('页面脚本错误：'+errors.join(' / '));
 check('桌面、平板、手机布局无横向溢出，页面无脚本异常');
 const after=await (await context.request.get(base+'/collector/api/templates')).json();
 if(after.map(t=>t.id).join()!==report.version_ids.join())throw Error('验收改变了现有版本');
 report.passed=true;
 fs.writeFileSync('doc/任务用途分类界面验收.json',JSON.stringify(report,null,2));
}finally{await browser.close()}
