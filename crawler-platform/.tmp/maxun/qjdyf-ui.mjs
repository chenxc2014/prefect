// 通过真实 Maxun 在线录制器操作网站，凭据与页面快照仅保存到受限目录。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium}=require('@playwright/test');
const root='.local/sites/qjdyf-maxun';fs.mkdirSync(root,{recursive:true});
const account=JSON.parse(fs.readFileSync('.local/site-accounts.json','utf8').replace(/^\uFEFF/,''))['qjdyf-test'];
if(!account.username||!account.password)throw Error('本地受限账号配置不完整');
const configuration=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=configuration.env.PREFECT_API_AUTH_STRING,split=auth.indexOf(':');
const base='http://127.0.0.1:18843',designer='http://127.0.0.1:19943';
const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({locale:'zh-CN',viewport:{width:1600,height:1100}});
const page=await context.newPage();let recorder;
const clean=s=>String(s).replaceAll(account.password,'[已隐藏]').replaceAll(account.username,'[账号]');
async function snapshot(){
 const p=recorder&&!recorder.isClosed()?recorder:page;
 const state={url:p.url(),frames:[]};
 for(const f of p.frames()){
  try{state.frames.push(await f.evaluate(()=>({url:location.origin+location.pathname,text:document.body.innerText.slice(0,14000),inputs:[...document.querySelectorAll('input')].map(e=>({placeholder:e.placeholder,type:e.type,id:e.id,name:e.name,readonly:e.readOnly})),buttons:[...document.querySelectorAll('button')].map(e=>({text:e.textContent.trim(),aria:e.getAttribute('aria-label'),title:e.title})),iframes:[...document.querySelectorAll('iframe')].map(e=>({id:e.id,src:e.src})),canvases:[...document.querySelectorAll('canvas')].map(e=>({class:e.className,id:e.id}))})));}catch{}
 }
 fs.writeFileSync(root+'/state.json',clean(JSON.stringify(state,null,2)));
 await p.screenshot({path:root+'/current.png',fullPage:true});
 console.log('页面状态已保存；框架数 '+state.frames.length);
}
try{
 await page.goto(base+'/collector/');
 await page.locator('input[name="username"]').fill(auth.slice(0,split));
 await page.locator('input[name="password"]').fill(auth.slice(split+1));
 await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();
 await page.waitForURL(u=>u.pathname==='/collector/');
 const pending=context.waitForEvent('page');await page.locator('#online-designer').click();
 const maxun=await pending;await maxun.waitForURL(u=>u.pathname==='/robots');
 if(process.argv.includes('--submit')){
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const published=JSON.parse(fs.readFileSync(root+'/published.json','utf8'));
  await page.locator('.sidebar [data-view="templates"]').click();
  await page.locator('#template-search').fill('千金 · 商品流向');
  const entry=page.locator('#templates article').filter({has:page.getByText('千金 · 商品流向（Maxun）',{exact:true})});
  await entry.waitFor();
  await entry.getByPlaceholder('管理员配置的账号引用').fill('qjdyf-test');
  for(const key of ['begindate','enddate'])await entry.getByLabel(key,{exact:true}).fill('2026-11-12');
  const created=page.waitForResponse(response=>response.url().includes('/api/templates/'+published.id+'/runs')&&response.request().method()==='POST');
  await entry.getByRole('button',{name:'运行',exact:true}).click();
  const response=await created;if(!response.ok())throw Error('工作台提交失败：'+response.status());
  const run=await response.json();fs.writeFileSync(root+'/run.json',JSON.stringify(run));console.log('工作台已提交 Prefect 运行 '+run.id);
  await page.waitForFunction(()=>/COMPLETED|FAILED|CRASHED|CANCELLED/.test(document.querySelector('#runs')?.innerText||''),null,{timeout:420000});
  if(!(await page.locator('#runs').innerText()).includes('COMPLETED'))throw Error('工作台显示任务未完成，请查询实际错误');
  const download=page.locator('#runs a.download').first();await download.waitFor();
  const pendingDownload=page.waitForEvent('download');await download.click();const file=await pendingDownload;
  await file.saveAs(root+'/商品流向_20261112_Maxun.xlsx');
  await page.screenshot({path:root+'/workbench-completed.png',fullPage:true});
  if(errors.length)throw Error('工作台出现脚本异常');
  fs.writeFileSync(root+'/ui-acceptance.json',JSON.stringify({passed:true,run_id:run.id,template_id:published.id,file_downloaded:true,browser_errors:errors}));
  console.log('工作台提交、Prefect COMPLETED 和实际 Excel 下载通过');
  await browser.close();process.exit(0);
 }
 if(process.argv.includes('--observe')){
  const response=await context.request.get(designer+'/storage/runs');
  const body=await response.text();fs.writeFileSync(root+'/maxun-runs.json',body);
  console.log('运行查询状态 '+response.status());
  if(response.ok()){
   const data=JSON.parse(body);const runs=Array.isArray(data)?data:data.runs||data.data||[];
   for(const run of runs.slice(-5)){
    const detail=await (await context.request.get(designer+'/storage/runs/run/'+run.runId)).json();
    fs.writeFileSync(root+'/maxun-'+run.runId+'.json',JSON.stringify(detail,null,2));
    for(const [name,item] of Object.entries(detail.binaryOutput||{})){
     const value=typeof item==='string'?item:item.data;
     if(!value)continue;
     const file=root+'/'+run.runId+'-'+path.basename(name);
     if(value.startsWith('https://192.168.1.169:9443/')||value.startsWith(designer+'/')){const address=value.replace('https://192.168.1.169:9443',designer);let response=await context.request.get(address);if(response.status()===404&&address.includes('%')){const encoded=new URL(address);encoded.pathname=encoded.pathname.replaceAll('%','%25');response=await context.request.get(encoded.toString());}if(response.ok())fs.writeFileSync(file,await response.body());}
     else if(!value.startsWith('http'))fs.writeFileSync(file,Buffer.from(value,'base64'));
    }
    console.log(clean(JSON.stringify({runId:run.runId,status:run.status,log:String(run.log||'').slice(-4000),binaryNames:Object.keys(detail.binaryOutput||{})})));
   }
  }
  await browser.close();process.exit(0);
 }
 let active=await (await context.request.get(designer+'/record/active')).text();
 if(active&&process.argv.includes('--restart-own')){
  if(fs.readFileSync(root+'/owned-session.txt','utf8').trim()!==active)throw Error('录制会话归属不匹配');
  await context.request.get(designer+'/record/stop/'+active);active='';
 }
 if(active&&!process.argv.includes('--resume'))throw Error('已有录制会话，保留并停止本次启动');
 if(process.argv.includes('--resume')){
  const owned=fs.readFileSync(root+'/owned-session.txt','utf8').trim();
  if(active!==owned)throw Error('录制会话归属不匹配');
  recorder=await context.newPage();
  await recorder.goto(designer+'/robots');
  await recorder.evaluate(()=>sessionStorage.setItem('recordingUrl','https://wx.qjdyf.cn/supplier-front-2.0/#/login'));
  await recorder.goto(designer+'/recording');
 }else{
 await maxun.goto(designer+'/robots/create');
 await maxun.getByRole('textbox',{name:'Website address'}).fill('https://wx.qjdyf.cn/supplier-front-2.0/#/login');
 const recording=context.waitForEvent('page');await maxun.getByRole('button',{name:'Start recording',exact:true}).click();
 recorder=await recording;await recorder.waitForURL(u=>u.pathname==='/recording',{timeout:60000});
 }
 await recorder.screenshot({path:root+'/startup.png'});console.log('已进入录制页，正在等待真实浏览器控件');
 if(!process.argv.includes('--resume'))await recorder.frameLocator('iframe').getByPlaceholder('账号',{exact:true}).waitFor({timeout:90000});
 if(process.argv.includes('--compat')){
  await recorder.waitForFunction(()=>window.CrawlerRecorderSocket?.connected,null,{timeout:60000});
  await recorder.locator('#crawler-recorder-toggle').click();
  await snapshot();
  await recorder.locator('#crawler-recorder-panel .crawler-control').first().waitFor({timeout:60000});
 }
 await snapshot();console.log('Maxun真实网站录制已就绪');
 fs.writeFileSync(root+'/owned-session.txt',await (await context.request.get(designer+'/record/active')).text());
 const deadline=Date.now()+90*60*1000;
 while(Date.now()<deadline){
  const file=root+'/command.json';if(!fs.existsSync(file)){await new Promise(r=>setTimeout(r,300));continue;}
  const commands=JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));fs.unlinkSync(file);
  for(const cmd of (Array.isArray(commands)?commands:[commands])){
  try{
   const p=cmd.platform?page:recorder;
   let f=cmd.frame===undefined?p:p.frames()[cmd.frame];
   let target=cmd.selector?f.locator(cmd.selector):cmd.placeholder?f.getByPlaceholder(cmd.placeholder,{exact:true}):cmd.role?f.getByRole(cmd.role,{name:cmd.name,exact:true}):cmd.text?f.getByText(cmd.text,{exact:true}):null;
   if(cmd.action==='type'){
    const value=cmd.secret?account[cmd.secret]:cmd.value;
    await target.click();if(cmd.clear)await target.press('Control+A');await target.pressSequentially(value,{delay:150});if(cmd.tab)await target.press('Tab');
   }
   else if(cmd.action==='compat'){
    const panel=recorder.locator('#crawler-recorder-panel');
    if(!await panel.isVisible())await recorder.locator('#crawler-recorder-toggle').click();
    const row=panel.locator('.crawler-control').filter({has:recorder.getByText(cmd.label,{exact:true})});
    const selected=cmd.index===undefined?row.first():row.nth(cmd.index);
    if(cmd.value!==undefined||cmd.secret){await selected.locator('input:not([type="checkbox"])').fill(cmd.secret?account[cmd.secret]:cmd.value);}
    await selected.getByRole('button').click();
    await panel.getByRole('status').filter({hasText:'步骤已保存到当前 Maxun 录制'}).waitFor({timeout:60000});
   }
   else if(cmd.action==='click')await target.click(cmd.position?{position:cmd.position}:{});
   else if(cmd.action==='key'){if(target)await target.press(cmd.key);else await p.keyboard.press(cmd.key);}
   else if(cmd.action==='inspect'){
    const result=await f.evaluate(()=>[...document.querySelectorAll('canvas,img,iframe')].map(e=>({tag:e.tagName,cls:e.className,id:e.id,style:e.getAttribute('style'),rect:JSON.stringify(e.getBoundingClientRect()),src:e.tagName==='IMG'?e.src.slice(0,200):undefined})));
    fs.writeFileSync(root+'/inspect.json',clean(JSON.stringify(result,null,2)));
   }
   else if(cmd.action==='screenshot')await target.screenshot({path:root+'/'+cmd.file});
   else if(cmd.action==='request'){
    const session=await (await context.request.get(base+'/collector/api/auth/me')).json();
    const response=await context.request.fetch((cmd.platform?base:designer)+cmd.path,{method:cmd.method||'GET',data:cmd.data,headers:{Origin:cmd.platform?base:designer,'X-Crawler-CSRF':session.csrf}});
    fs.writeFileSync(root+'/'+(cmd.file||'response.json'),await response.body());console.log('接口状态 '+response.status());
   }
   else if(cmd.action==='save'){
    await recorder.getByRole('button',{name:'完成',exact:true}).click();
    await recorder.locator('#title').fill(cmd.name);
    await recorder.getByRole('button',{name:'保存',exact:true}).click();
    await recorder.waitForEvent('close',{timeout:30000});console.log('录制草稿已保存');
   }
   else if(cmd.action==='stop'){await browser.close();process.exit(0);}
   else if(cmd.action!=='snapshot')throw Error('未知操作');
   await new Promise(r=>setTimeout(r,cmd.wait??1200));await snapshot();
   fs.writeFileSync(root+'/done.json',JSON.stringify({id:cmd.id,ok:true}));
  }catch(e){console.log(clean('操作未完成：'+e.message.split('\n')[0]));fs.writeFileSync(root+'/done.json',JSON.stringify({id:cmd.id,ok:false,error:clean(e.message)}));await snapshot().catch(()=>{});}
  }
 }
}finally{await browser.close();}
