// 真实页面读取已有任务，保存、发布和试跑使用浏览器拦截的测试响应。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';

const require = createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium, expect} = require('@playwright/test');
const config = JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const credential = config.env.PREFECT_API_AUTH_STRING;
const separator = credential.indexOf(':');
const base = 'http://127.0.0.1:18843';
const maxun = 'http://127.0.0.1:19943';
const browser = await chromium.launch({channel:'chrome',headless:true});

try {
  const context = await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:900}});
  const errors = [];
  context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));
  const page = await context.newPage();
  await page.goto(base+'/collector/');
  await page.locator('[name="username"]').fill(credential.slice(0,separator));
  await page.locator('[name="password"]').fill(credential.slice(separator+1));
  await page.getByRole('button',{name:'登录统一工作台',exact:true}).click();
  await page.waitForURL(base+'/collector/');
  const api = '/collector/api/';
  const snapshot = await (await context.request.get(base+api+'maxun/relations')).json();
  const existing = ['千金商品流向','老百姓 · 配送数据'].map(name=>{
    const group=snapshot.groups.find(item=>item.task_name===name);
    const draft=group.drafts.find(item=>item.active_template_id&&!item.missing);
    return {group,draft};
  });
  for(const {group,draft} of existing){
    const response=await context.request.get(base+api+'maxun/releases/'+draft.active_template_id,{params:{draft:draft.id}});
    expect(response.ok(),group.task_name+' 的真实预检接口').toBeTruthy();
    const preflight=await response.json();
    expect(preflight.task_name).toBe(group.task_name);
    expect(preflight.issues,group.task_name+' 的已保存流程').toEqual([]);
  }
  const {group,draft}=existing[1];
  const endpoint=base+api+'maxun/releases/'+draft.active_template_id;
  const preview=await (await context.request.get(endpoint,{params:{draft:draft.id}})).json();
  const latest=await (await context.request.get(endpoint+'/trial-defaults')).json();
  expect(latest.from_success).toBe(true);
  expect(latest.parameters.begindate).toBeTruthy();
  expect(latest.account_ref).toBeTruthy();
  console.log('真实千金、老百姓设计稿通过预检；真实老百姓最近一次成功运行可带入日期和账号引用');

  const changedSnapshot=structuredClone(snapshot);
  changedSnapshot.groups.find(item=>item.task_key===group.task_key).drafts.find(item=>item.id===draft.id).changed_since_publish=true;
  await context.route(base+api+'maxun/relations',route=>route.fulfill({json:changedSnapshot}));
  await page.goto(base+'/collector/?template='+preview.id+'#templates');
  const taskCard=page.locator('[data-maxun-relation="'+preview.id+'"]');
  await expect(taskCard.getByText('草稿待发布',{exact:true})).toBeVisible();
  await expect(taskCard.getByRole('button',{name:'检查并发布',exact:true})).toBeVisible();
  await context.route(maxun+'/_platform/relations',route=>route.fulfill({json:changedSnapshot}));
  await page.goto(base+'/collector/open/maxun');
  await page.waitForURL(maxun+'/robots');
  const groupCard=page.locator('[data-relation-task="'+group.task_key+'"]');
  await expect(groupCard.getByText('草稿待发布',{exact:true})).toBeVisible();
  await expect(groupCard.getByRole('link',{name:'检查并发布',exact:true})).toBeVisible();
  const realStatus=await context.request.get(maxun+'/_platform/relations',{params:{draft:draft.id}});
  expect(realStatus.ok()).toBeTruthy();
  expect((await realStatus.json()).versions[0].id).toBe(preview.id);

  await context.route(url=>url.origin===maxun&&url.pathname==='/_platform/relations'&&url.searchParams.get('draft')===draft.id,
    route=>route.fulfill({json:{versions:[{id:preview.id,task_name:preview.task_name,name:preview.name,changed:true}]}}));
  await page.goto(base+'/collector/open/maxun?robot='+draft.id);
  const editorPath=maxun+'/robots/'+draft.id+'/edit';
  await page.waitForURL(editorPath);
  const status=page.locator('.mx-draft-release');
  await expect(status.getByText('草稿待发布',{exact:true})).toBeVisible();
  let basicSaves=0;
  await page.route(maxun+'/storage/recordings/'+draft.id,route=>{
    if(route.request().method()==='PUT'){basicSaves++;return route.fulfill({json:true});}
    return route.fallback();
  });
  await page.getByLabel('更改机器人名称',{exact:true}).fill('浏览器验收草稿');
  await page.getByRole('button',{name:'保存更改',exact:true}).click();
  await expect(status.getByText('基本设置已保存',{exact:true})).toBeVisible({timeout:15000});
  expect(page.url()).toBe(editorPath);
  expect(basicSaves).toBe(1);
  await page.route(maxun+'/record/can-create/recording',route=>route.fulfill({json:{canCreate:true}}));
  await context.route(maxun+'/recording-setup?session=*',route=>route.fulfill({
    contentType:'text/html; charset=utf-8',body:'<title>录制保存验收</title>',
  }));
  await page.getByRole('button',{name:'重新录制',exact:true}).click();
  const capture=context.waitForEvent('page');
  await page.getByRole('button',{name:'开始重新录制',exact:true}).click();
  const popup=await capture;
  await popup.waitForURL(url=>url.pathname==='/recording-setup');
  await popup.evaluate(()=>window.opener.postMessage({type:'recording-notification',notification:{type:'success'}},location.origin));
  await popup.close();
  await expect(status.getByText('录制已保存',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'基本设置',exact:true})).toHaveAttribute('aria-pressed','true');

  let issue=true,publishes=0,trialPayload;
  const newVersion='9'.repeat(64),runId='1a456718-866e-460a-80aa-377c83eda245';
  await context.route(url=>url.origin===base&&url.pathname===new URL(endpoint).pathname,route=>{
    if(route.request().method()==='POST'){
      publishes++;
      expect(route.request().postDataJSON()).toEqual({draft:draft.id,fingerprint:preview.fingerprint});
      return route.fulfill({json:{id:newVersion}});
    }
    return route.fulfill({json:{...preview,changed:true,
      issues:issue?['老百姓配送数据导出：录制中找不到原步骤。']:[],
      changes:{before:8,after:9,actions:[{name:'waitForTimeout',before:0,after:1}]}}});
  });
  await context.route(base+api+'maxun/releases/'+newVersion+'/trial-defaults',route=>route.fulfill({
    json:{parameters:{begindate:'2026-10-01',enddate:'2026-10-31'},account_ref:'sample-account',from_success:true},
  }));
  await context.route(base+api+'templates/'+newVersion+'/runs',route=>{
    trialPayload=route.request().postDataJSON();
    return route.fulfill({json:{id:runId,url:'/v2/runs/flow-run/'+runId}});
  });
  await context.route(base+api+'runs/'+runId,route=>route.fulfill({json:{state:'COMPLETED',artifacts:[]}}));
  const next=context.waitForEvent('page');
  await status.getByRole('link',{name:'检查并发布',exact:true}).click();
  const release=await next;
  const dialog=release.getByRole('dialog');
  await expect(dialog.getByText('发布前需要处理')).toBeVisible();
  await expect(dialog.getByText(/找不到原步骤/)).toBeVisible();
  await expect(dialog.getByRole('button',{name:'确认发布新版'})).toHaveCount(0);
  expect(publishes).toBe(0);
  issue=false;
  await dialog.getByRole('button',{name:'重新检查'}).click();
  await expect(dialog.getByText('变更摘要')).toBeVisible();
  await expect(dialog.getByText('录制步骤 8 → 9')).toBeVisible();
  await expect(dialog.getByText('必需文件',{exact:true})).toBeHidden();
  await dialog.getByText('查看沿用的参数、账号和文件校验',{exact:true}).click();
  await expect(dialog.getByText('必需文件',{exact:true})).toBeVisible();
  await release.setViewportSize({width:390,height:844});
  expect(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth+1)).toBe(true);
  await dialog.getByRole('button',{name:'确认发布新版'}).click();
  await expect(dialog.getByRole('heading',{name:'新版已发布'})).toBeVisible();
  await expect(dialog.getByText(newVersion,{exact:true})).toBeVisible();
  await expect(dialog.getByRole('link',{name:'查看版本历史 ↗'})).toHaveAttribute('href','open/maxun?template='+newVersion+'&section=published');
  await dialog.getByRole('button',{name:'试跑新版'}).click();
  await expect(dialog.getByLabel('开始日期')).toHaveValue('2026-10-01');
  await expect(dialog.getByLabel('结束日期')).toHaveValue('2026-10-31');
  await expect(dialog.getByLabel('账号引用')).toHaveValue('sample-account');
  await dialog.getByLabel('开始日期').fill('2026-10-02');
  expect(trialPayload).toBeUndefined();
  await dialog.getByRole('button',{name:'提交试跑'}).click();
  await expect(dialog.getByRole('link',{name:'查看试跑日志 ↗'})).toHaveAttribute('href','/v2/runs/flow-run/'+runId);
  expect(trialPayload).toEqual({begindate:'2026-10-02',enddate:'2026-10-31',account_ref:'sample-account'});
  expect(publishes).toBe(1);
  const finalSnapshot=await (await context.request.get(base+api+'maxun/relations')).json();
  const finalGroup=finalSnapshot.groups.find(item=>item.task_key===group.task_key);
  expect(finalGroup.publications).toEqual(group.publications);
  expect(finalGroup.executions.map(item=>item.prefect_run_id)).toEqual(group.executions.map(item=>item.prefect_run_id));
  expect(errors).toEqual([]);
  console.log('保存回跳、录制保存、阻断与确认、手机版发布、试跑参数编辑和运行跳转通过；真实版本与执行记录未变');
} finally {
  await browser.close();
}
