// 独立登录取证会话；凭据仅从受限文件读取，不写入控制台。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium}=require('@playwright/test');
const root='.local/sites/qjdyf';fs.mkdirSync(root,{recursive:true});
const account=JSON.parse(fs.readFileSync('.local/site-accounts.json','utf8').replace(/^\uFEFF/,'') )['qjdyf-test'];
if(!account.username||!account.password)throw Error('测试账号未填写');
const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},...(fs.existsSync(root+'/session.json')?{storageState:root+'/session.json'}:{})});
const page=await context.newPage();
async function snapshot(){
 await context.storageState({path:root+'/session.json'});
 await page.screenshot({path:root+'/current.png',fullPage:true});
 const data={url:page.url(),frames:[]};
 for(const frame of page.frames()){
  try{data.frames.push(await frame.evaluate(()=>({url:location.origin+location.pathname,inputs:[...document.querySelectorAll('input')].map(e=>({placeholder:e.placeholder,type:e.type,id:e.id,readonly:e.readOnly})),buttons:[...document.querySelectorAll('button')].map(e=>({text:e.textContent.trim(),class:e.className})),links:[...document.querySelectorAll('a')].slice(0,25).map(e=>({text:e.textContent.trim(),href:(e.getAttribute('href')||'').split('?')[0]})),canvases:[...document.querySelectorAll('canvas')].map(e=>({class:e.className,id:e.id})),messages:[...document.querySelectorAll('.el-message,.layui-layer-content')].map(e=>e.textContent)})))}catch{}
 }
 fs.writeFileSync(root+'/state.json',JSON.stringify(data,null,2));console.log('取证状态已保存，当前地址：'+page.url());
}
try{
 await page.goto('https://wx.qjdyf.cn/supplier-front-2.0/#/login',{waitUntil:'networkidle',timeout:60000});
 await page.getByPlaceholder('账号',{exact:true}).fill(account.username);
 await page.getByPlaceholder('密码',{exact:true}).fill(account.password);
 await snapshot();
 console.log('登录信息已填充，等待验证码操作');
 const until=Date.now()+20*60*1000;
 while(Date.now()<until){
  const commandFile=root+'/command.json';
  if(!fs.existsSync(commandFile)){await new Promise(r=>setTimeout(r,500));continue;}
  const cmd=JSON.parse(fs.readFileSync(commandFile,'utf8'));fs.unlinkSync(commandFile);
  try{
   if(cmd.action==='login'){await page.getByPlaceholder('验证码',{exact:true}).fill(cmd.captcha);await page.getByRole('button',{name:'登录',exact:true}).click();await page.waitForTimeout(2500);}
   if(cmd.action==='goods'){await page.goto('https://wx.qjdyf.cn/supplier-front-2.0/#/goodsFlow',{waitUntil:'networkidle',timeout:60000});}
   if(cmd.action==='click'){const frame=cmd.frame===undefined?page:page.frames()[cmd.frame];await frame.getByText(cmd.text,{exact:true}).click();await page.waitForTimeout(1000);}
   if(cmd.action==='query'){const frame=page.frames().find(f=>f!==page.mainFrame());await frame.locator('#startTime').fill(cmd.begin);await frame.locator('#endTime').fill(cmd.end);await frame.locator('[lay-filter="data-search-btn"]').click();await page.waitForTimeout(3000);}
   if(cmd.action==='selector'){const frame=cmd.frame===undefined?page:page.frames()[cmd.frame];await frame.locator(cmd.selector).click();await page.waitForTimeout(1000);}
   if(cmd.action==='export'){const frame=page.frames().find(f=>f!==page.mainFrame());const pending=page.waitForEvent('download',{timeout:120000});await frame.getByText(cmd.text,{exact:true}).click();const download=await pending;await download.saveAs(root+'/'+download.suggestedFilename());console.log('导出文件已保存在受限取证目录');}
   if(cmd.action==='stop')break;
   await snapshot();
  }catch(e){console.log('操作未完成：'+e.message.split('\n')[0]);await snapshot();}
 }
}finally{await browser.close();}
