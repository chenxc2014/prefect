// 使用独立无头浏览器验证在线设计界面，不操作用户正在使用的浏览器。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium}=require('@playwright/test');
const client=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=client.env.PREFECT_API_AUTH_STRING;const split=auth.indexOf(':');
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:19943/',{waitUntil:'domcontentloaded'});
  await page.locator('input').first().waitFor({timeout:30000});
  console.log(JSON.stringify({url:page.url(),text:(await page.locator('body').innerText()).slice(0,1800),inputs:await page.locator('input').evaluateAll(nodes=>nodes.map(n=>({type:n.type,placeholder:n.placeholder,name:n.name,id:n.id})))},null,2));
  await page.screenshot({path:'.local/screenshots/maxun-login.png',fullPage:true});
  if(process.argv.includes('--login')){
    await page.locator('input[name="email"]').fill(auth.slice(0,split)+'@crawler.local');
    await page.locator('input[name="password"]').fill(auth.slice(split+1));
    await page.locator('button[type="submit"]').click();
    await page.waitForURL(url=>url.pathname==='/robots',{timeout:30000});
    await page.getByText(/Create Robot|创建机器人/).first().waitFor({timeout:30000});
    await context.storageState({path:'.local/maxun-ui-state.json'});
    console.log(JSON.stringify({logged_in:true,url:page.url(),text:(await page.locator('body').innerText()).slice(0,2200)},null,2));
    await page.screenshot({path:'.local/screenshots/maxun-dashboard.png',fullPage:true});
    if(process.argv.includes('--create')){
      await page.goto('http://127.0.0.1:19943/robots/create',{waitUntil:'domcontentloaded'});
      await page.locator('input').first().waitFor();
      console.log(JSON.stringify({create_text:(await page.locator('body').innerText()).slice(0,2600),inputs:await page.locator('input,textarea').evaluateAll(nodes=>nodes.map(n=>({type:n.type,placeholder:n.placeholder,name:n.name,id:n.id})))},null,2));
      await page.screenshot({path:'.local/screenshots/maxun-create.png',fullPage:true});
      if(process.argv.includes('--record')){
        const old=(await (await page.request.get('http://127.0.0.1:19943/record/active')).text());
        if(old){
          const oldUrl=await (await page.request.get('http://127.0.0.1:19943/record/active/url')).text();
          if(!oldUrl.includes('127.0.0.1:8766') && oldUrl!=='about:blank')throw Error('已有非演示录制会话，保留它并停止本次验收');
          await page.request.get('http://127.0.0.1:19943/record/stop/'+old);
        }
        await page.getByRole('textbox',{name:'Website address'}).fill('http://127.0.0.1:8766');
        const opened=context.waitForEvent('page');
        await page.getByRole('button',{name:'Start recording',exact:true}).click();
        const recording=await opened;
        await recording.waitForLoadState('domcontentloaded');
        await recording.waitForURL(url=>url.pathname==='/recording',{timeout:40000});
        await recording.frameLocator('iframe').getByRole('heading',{name:'销售查询演示'}).waitFor({timeout:90000});
        console.log(JSON.stringify({recording_url:recording.url(),text:(await recording.locator('body').innerText()).slice(0,3000),frames:await Promise.all(recording.frames().map(async f=>({url:f.url(),text:(await f.locator('body').innerText().catch(()=>'' )).slice(0,800)})))},null,2));
        await recording.screenshot({path:'.local/screenshots/maxun-recorder.png',fullPage:true});
        const active=await page.request.get('http://127.0.0.1:19943/record/active');
        const id=await active.text();if(id)await page.request.get('http://127.0.0.1:19943/record/stop/'+id);
      }
    }
  }
}finally{await browser.close()}
