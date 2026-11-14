// 验证真实统一登录部署；不访问 Windows 167，不操作真实业务网站。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const configuration=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=configuration.env.PREFECT_API_AUTH_STRING,split=auth.indexOf(':');
const base='http://127.0.0.1:18843',designerBase='http://127.0.0.1:19943';
const browser=await chromium.launch({channel:'chrome',headless:true});
const report={date:new Date().toISOString(),checks:[],method:'经 SSH 隧道及校验 CA 的 HTTPS 代理验证实际服务',windows_167_accessed:false};
const check=text=>{report.checks.push(text);console.log(text)};
try{
 const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/collector/');
 await expect(page.getByRole('heading',{name:'登录采集管理平台',exact:true})).toBeVisible();
 await page.screenshot({path:'.local/screenshots/unified-login.png',fullPage:true});
 for(const url of [base+'/collector/api/templates',base+'/collector/auth/check',designerBase+'/storage/recordings']){
  const response=await context.request.get(url,{maxRedirects:0});
  if(![401,404].includes(response.status()))throw Error('未登录接口未拒绝访问：'+url+' / '+response.status());
  if(response.headers()['www-authenticate'])throw Error('仍存在浏览器 Basic 登录弹窗');
 }
 check('未登录统一跳转中文登录页，受保护接口拒绝访问，无 Basic 弹窗');
 async function login(target=page){
  await target.locator('input[name="username"]').fill(auth.slice(0,split));
  await target.locator('input[name="password"]').fill(auth.slice(split+1));
  const completed=target.waitForResponse(response=>response.url().endsWith('/collector/login')&&response.request().method()==='POST');
  await target.getByRole('button',{name:'登录统一工作台',exact:true}).click();
  const result=await completed;if(!result.ok())throw Error('统一登录失败（HTTP '+result.status()+'）');
  await target.waitForURL(url=>url.pathname==='/collector/',{timeout:25000});
  await expect(target.locator('#stat-prefect')).toHaveText('正常运行',{timeout:15000});
 }
 await login();
 const cookies=await context.cookies();
 const sessionCookie=cookies.find(cookie=>cookie.name==='__Host-crawler_session');
 if(!sessionCookie?.httpOnly||!sessionCookie.secure)throw Error('缺少受保护的统一会话 Cookie');
 report.cookie_flags={secure:sessionCookie.secure,httpOnly:sessionCookie.httpOnly,sameSite:sessionCookie.sameSite};
 check('新浏览器仅输入一次平台账号密码，建立 Secure / HttpOnly 统一会话');
 const session=await (await context.request.get(base+'/collector/api/auth/me')).json();
 const denied=await context.request.post(base+'/api/flows/filter',{data:{},headers:{Origin:base,'X-Crawler-CSRF':'invalid'}});
 if(denied.status()!==403)throw Error('网关未拒绝错误 CSRF：'+denied.status());
 const allowed=await context.request.post(base+'/api/flows/filter',{data:{},headers:{Origin:base,'X-Crawler-CSRF':session.csrf}});
 if(!allowed.ok())throw Error('有效统一会话无法调用 Prefect API：'+allowed.status());
 check('Prefect 网关验证写请求的来源与 CSRF，有效会话可调用 API');
 const prefectPromise=context.waitForEvent('page');
 await page.locator('a.navitem').filter({hasText:'Prefect 调度监控'}).click();
 const prefect=await prefectPromise;
 await prefect.waitForURL(url=>url.pathname.startsWith('/v2')&&!url.pathname.includes('login'),{timeout:30000});
 await expect(prefect.getByRole('link',{name:'部署',exact:true}).first()).toBeVisible({timeout:30000});
 if(await prefect.locator('input[type="password"]').count())throw Error('Prefect 仍要求二次登录');
 const settings=await (await context.request.get(base+'/ui-settings')).json();
 if(settings.auth!==null||settings.api_url!=='/api')throw Error('Prefect 未使用网关会话设置');
 await prefect.screenshot({path:'.local/screenshots/unified-prefect.png',fullPage:true});
 check('从工作台进入 Prefect，直接显示中文管理界面，无需二次登录');
 const maxunPromise=context.waitForEvent('page');
 await page.locator('#online-designer').click();
 const maxun=await maxunPromise;
 await maxun.waitForURL(url=>url.origin===designerBase&&url.pathname==='/robots',{timeout:35000});
 await expect(maxun.getByText('创建机器人',{exact:true})).toBeVisible({timeout:15000});
 if(await maxun.locator('input[name="password"]').count())throw Error('Maxun 仍要求二次登录');
 await maxun.screenshot({path:'.local/screenshots/unified-maxun.png',fullPage:true});
 check('从工作台进入 Maxun，服务端自动衔接原有账号，直接进入机器人页面');
 for(const app of [page,prefect,maxun]){
  await app.reload();
  await app.waitForLoadState('domcontentloaded');
  const values=await app.evaluate(()=>Object.values(localStorage));
  if(values.some(value=>value.includes(auth)||value.includes(auth.slice(split+1))))throw Error('浏览器存储中出现平台密码');
  if(await app.locator('input[type="password"]').count())throw Error('刷新后出现二次登录');
 }
 check('三个界面刷新后仍免登录，浏览器 localStorage 无平台密码');
 if(!process.argv.includes('--quick')){
 const active=await (await context.request.get(designerBase+'/record/active')).text();
 if(active)throw Error('已有录制会话，保留现有会话并停止录制验收');
 await maxun.goto(designerBase+'/robots/create');
 await maxun.getByRole('textbox',{name:'Website address'}).fill('http://127.0.0.1:8766');
 const recordingPromise=context.waitForEvent('page');
 await maxun.getByRole('button',{name:'Start recording',exact:true}).click();
 const recording=await recordingPromise;
 try{
  await recording.waitForURL(url=>url.pathname==='/recording',{timeout:45000});
  await recording.frameLocator('iframe').getByRole('heading',{name:'销售查询演示'}).waitFor({timeout:90000});
  const demo=recording.frameLocator('iframe');
  // Maxun 转发真实键盘事件，直接修改镜像输入框的 value 不会操作远程页面。
  await demo.locator('#begindate').click();
  await demo.locator('#begindate').pressSequentially('2026-11-12',{delay:150});
  await demo.locator('#begindate').press('Tab');
  await demo.getByRole('button',{name:'查询',exact:true}).click();
  await expect(demo.getByRole('link',{name:'导出销售 CSV',exact:true})).toBeVisible({timeout:20000});
  await expect(demo.getByRole('link',{name:'导出销售 CSV',exact:true})).toHaveAttribute('href',/begin=2026-11-12/);
  await expect(recording.locator('div:has(> .MuiIconButton-root > svg[data-testid="MoreHorizIcon"])')).toHaveCSS('background-color','rgb(64, 91, 240)');
  await expect(recording.getByRole('button',{name:'放弃',exact:true})).toHaveCSS('color','rgb(255, 0, 0)');
  if(await demo.locator('html').getAttribute('data-crawler-app'))throw Error('共享主题不应注入被录制的网站');
  await recording.screenshot({path:'.local/screenshots/unified-recorder.png',fullPage:true});
 }finally{
  const own=await (await context.request.get(designerBase+'/record/active')).text();
  if(own)await context.request.get(designerBase+'/record/stop/'+own);
  await recording.close();
 }
 check('统一会话下 Maxun 可创建录制、建立 WebSocket，远程网页的日期输入与查询交互通过');
 await page.locator('.sidebar [data-view="templates"]').click();
 await page.locator('#template-search').fill('界面升级验收：日期查询与导出');
 const entry=page.locator('#templates article').filter({has:page.getByText('界面升级验收：日期查询与导出',{exact:true})});
 await expect(entry).toHaveCount(1);
 await entry.locator('input').fill('2026-11-12');
 await entry.getByRole('button',{name:'运行',exact:true}).click();
 await expect(page.locator('#runs')).toContainText('COMPLETED',{timeout:150000});
 const download=page.locator('#runs a.download').first();
 await expect(download).toBeVisible();
 const csv=await (await context.request.get(base+await download.getAttribute('href'))).text();
 if(!csv.includes('2026-11-12')||csv.trim().split(/\r?\n/).length!==7)throw Error('演示产物不匹配');
 report.run_id=(await page.locator('#runs a').first().innerText()).match(/[0-9a-f-]{36}/)?.[0];
 check('统一会话提交 EasySpider 演示任务，Prefect / Worker 执行完成并下载 6 行 CSV');
 }
 await maxun.goto(designerBase+'/robots');
 await maxun.locator('#crawler-unified-account').getByRole('button',{name:'退出统一登录',exact:true}).click();
 await maxun.waitForURL(url=>url.origin===base&&url.pathname==='/collector/login',{timeout:20000});
 await page.waitForURL(url=>url.pathname==='/collector/login',{timeout:20000});
 await prefect.waitForURL(url=>url.pathname==='/collector/login',{timeout:20000});
 const replay=await context.request.get(base+'/collector/api/auth/me',{headers:{Cookie:sessionCookie.name+'='+sessionCookie.value}});
 if(replay.status()!==401)throw Error('退出后旧会话仍有效');
 for(const url of [base+'/api/admin/version',designerBase+'/storage/recordings'])if((await context.request.get(url,{maxRedirects:0})).status()!==401)throw Error('退出后子系统接口仍可访问');
 check('从 Maxun 退出统一登录，三个界面同步回到登录页，旧会话重放及接口访问均被拒绝');
 const machine=await browser.newContext();
 try{
  const response=await machine.request.post(base+'/api/deployments/filter',{data:{},headers:{Authorization:'Basic '+Buffer.from(auth).toString('base64')}});
  if(!response.ok())throw Error('原有机器接口认证不兼容：'+response.status());
 }finally{await machine.close();}
 check('退出浏览器会话后，Worker 使用的原有 Basic 接口认证仍然有效');
 await login();
 await page.screenshot({path:'.local/screenshots/unified-workspace.png',fullPage:true});
 for(const width of [390,1920]){
  await page.setViewportSize({width,height:900});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('统一账号区域导致横向溢出：'+width);
 }
 if(process.argv.includes('--quick')){
  await page.setViewportSize({width:1440,height:1000});
  const nativePromise=context.waitForEvent('page');await page.locator('#online-designer').click();const native=await nativePromise;
  await native.waitForURL(url=>url.pathname==='/robots',{timeout:30000});
  await native.evaluate(()=>{const request=new XMLHttpRequest();request.open('GET','/auth/logout');request.send();});
  await native.waitForURL(url=>url.origin===base&&url.pathname==='/collector/login',{timeout:15000});
  if((await context.request.get(base+'/collector/api/auth/me')).status()!==401)throw Error('Maxun 原生退出请求未撤销统一会话');
  check('Maxun 原生退出请求已衔接统一退出，不会重新弹出独立邮箱登录');
 }
 report.frontend_errors=errors;
 if(errors.length)throw Error('工作台脚本异常：'+errors.join('; '));
 report.passed=true;
 fs.writeFileSync(process.argv.includes('--quick')?'doc/统一登录补充验收.json':'doc/统一登录部署验收.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
}catch(error){
 report.passed=false;report.error=error.message;fs.writeFileSync('.local/sso-verification-failure.json',JSON.stringify(report,null,2));throw error;
}finally{await browser.close();}
