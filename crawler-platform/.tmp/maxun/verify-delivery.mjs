// 仅读取已完成运行和发布配置；检查文档布局，不创建新的采集任务。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const auth=JSON.parse(fs.readFileSync('.local/client.json','utf8')).env.PREFECT_API_AUTH_STRING,split=auth.indexOf(':');
const report=JSON.parse(fs.readFileSync('doc/千金商品流向Maxun验收.json','utf8'));
const base='http://127.0.0.1:18843',designer='http://127.0.0.1:19943';
const result={passed:false,new_collection_runs_created:0,checks:[],document_layout:[]};
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
 const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/collector/');
 await page.locator('input[name="username"]').fill(auth.slice(0,split));await page.locator('input[name="password"]').fill(auth.slice(split+1));
 await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();await page.waitForURL(url=>url.pathname==='/collector/');
 const run=await (await context.request.get(base+'/collector/api/runs/'+report.prefect_run_id)).json();
 assert.equal(run.state,'COMPLETED');assert.equal(run.artifacts[0].sha256,report.artifact.sha256);
 const file=await context.request.get(base+run.artifacts[0].url);assert.ok(file.ok());
 assert.equal(createHash('sha256').update(await file.body()).digest('hex'),report.artifact.sha256);
 result.checks.push('统一登录后可读取真实 COMPLETED 状态及归档 Excel，摘要一致');
 const template=await (await context.request.get(base+'/collector/api/templates/'+report.template_id)).json();
 assert.deepEqual(Object.keys(template.secret_bindings).sort(),['password','username']);
 await page.locator('.sidebar [data-view="maxun"]').click();await page.locator('#refresh-maxun').click();
 await page.locator('#maxun-robot').selectOption(report.source_robot_id);
 await expect(page.locator('#maxun-inputs .node')).toHaveCount(5);
 for(const key of ['username','password','captcha','begindate','enddate'])assert.ok(await page.locator('#maxun-inputs select').first().locator('option[value="'+key+'"]').count());
 assert.ok(await page.locator('#maxun-login-step option').count()>1);assert.ok(await page.locator('#maxun-download-steps option').count()>0);
 await page.screenshot({path:'.local/sites/qjdyf-maxun/delivery-platform.png',fullPage:true});
 result.checks.push('发布界面可配置账号注入、日期、验证码、真实登录点击及下载步骤');
 const pending=context.waitForEvent('page');pending.catch(()=>{});await page.locator('a[data-maxun-link]:visible').first().click();const maxun=await pending;
 await maxun.waitForURL(url=>url.origin===designer&&url.pathname==='/robots');
 assert.equal(await maxun.locator('input[type="password"]').count(),0);result.checks.push('Maxun 统一登录入口正常，无二次邮箱密码登录');
 const active=await (await context.request.get(designer+'/record/active')).text();assert.equal(active,'','保留他人活动录制，停止部署验收');
 const nativeRuns=await (await context.request.get(designer+'/storage/runs')).json();assert.ok(nativeRuns.every(run=>!['running','queued','aborting'].includes(run.status)),'存在活动执行，暂停服务重载');
 result.checks.push('没有活动录制或执行，可安全应用仅日志文本的补丁');
 const machine=await browser.newContext();
 const deployments=await machine.request.post(base+'/api/deployments/filter',{data:{},headers:{Authorization:'Basic '+Buffer.from(auth).toString('base64')}});
 assert.ok(deployments.ok());const matches=(await deployments.json()).filter(d=>d.name==='linux-169'&&d.entrypoint==='flows/collect.py:collect');
 assert.equal(matches.length,1);assert.ok((matches[0].schedules||[]).every(schedule=>!schedule.active));
 result.checks.push('通用 Linux 采集部署未启用定时计划');await machine.close();
 const docs=await browser.newPage();
 for(const name of ['千金商品流向Maxun操作说明.html','爬虫任务编排与执行平台.html','开发环境部署记录.html']){
  await docs.goto(pathToFileURL(path.resolve('doc',name)).href);
  for(const width of [1440,390]){
   await docs.setViewportSize({width,height:1000});
   const overflow=await docs.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
   result.document_layout.push({file:name,width,overflow});
   if(name==='千金商品流向Maxun操作说明.html'){assert.equal(overflow,false);await docs.screenshot({path:'.local/sites/qjdyf-maxun/guide-'+width+'.png',fullPage:width===1440});}
  }
 }
 assert.deepEqual(errors,[]);result.passed=true;
 fs.writeFileSync('doc/千金商品流向交付检查.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
