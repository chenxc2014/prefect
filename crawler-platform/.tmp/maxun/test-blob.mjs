// 复现 iframe 内生成 Blob、未发出原生下载事件的情况，核对完整原始字节。
import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium}=require('@playwright/test');
const actions=require(path.resolve('deploy/maxun/browser-actions.cjs'));
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const context=await browser.newContext();const page=await context.newPage();const captured=[];
 await actions.install(page,async file=>captured.push(file));
 await page.setContent('<iframe id="target"></iframe>');
 const frame=page.frames().find(frame=>frame!==page.mainFrame());
 await frame.setContent('<button id="export">导出</button>');
 await frame.evaluate(()=>{document.querySelector('#export').onclick=()=>{
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['原始导出字节，2026-11-12'],{type:'text/csv'}));a.download='中文文件.csv';a.addEventListener('click',e=>e.preventDefault());document.body.append(a);a.click();URL.revokeObjectURL(a.href);a.remove();
  const detached=document.createElement('a');detached.href=URL.createObjectURL(new Blob(['分离节点导出字节'],{type:'text/csv'}));detached.download='分离节点.csv';detached.addEventListener('click',e=>e.preventDefault());detached.dispatchEvent(new MouseEvent('click'));URL.revokeObjectURL(detached.href);
 }});
 await page.platformDownload('#target >> internal:control=enter-frame >> #export');
 const file=captured.find(file=>file.name==='中文文件.csv');assert.ok(file,'必须捕获文件');
 assert.equal(Buffer.from(file.data,'base64').toString(),'原始导出字节，2026-11-12');
 assert.equal(Buffer.from(captured.find(file=>file.name==='分离节点.csv').data,'base64').toString(),'分离节点导出字节');
 const raw=Buffer.from([0x50,0x4b,0x03,0x04,1,2,3,4,5]);
 await page.route('https://test.invalid/export',route=>route.fulfill({status:200,headers:{'content-type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','content-disposition':"attachment;filename*=UTF-8''%E4%B8%AD%E6%96%87.xlsx",'access-control-allow-origin':'*'},body:raw}));
 await frame.evaluate(()=>{document.querySelector('#export').onclick=async()=>{await fetch('https://test.invalid/export')}});
 await page.platformDownload('#target >> internal:control=enter-frame >> #export');
 assert.deepEqual(Buffer.from(captured.find(file=>file.name==='中文.xlsx').data,'base64'),raw);
 assert.ok(captured.filter(file=>file.name==='download-method.json').some(file=>JSON.parse(Buffer.from(file.data,'base64')).method==='network-response'));
 console.log('跨域路径解析、Blob 文件名与完整原始字节校验通过；未使用原生下载事件。');
}finally{await browser.close();}
