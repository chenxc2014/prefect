// 只读取公开登录页，定位依据与截图保存到本工作区。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(path.resolve('vendor/prefect/ui-v2/package.json'));
const {chromium}=require('@playwright/test');
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('https://wx.qjdyf.cn/supplier-front-2.0/#/login',{waitUntil:'networkidle',timeout:60000});
 const evidence=await page.evaluate(()=>({url:location.href,title:document.title,inputs:[...document.querySelectorAll('input')].map(e=>({type:e.type,placeholder:e.placeholder,id:e.id,name:e.name})),buttons:[...document.querySelectorAll('button')].map(e=>({text:e.textContent.trim(),class:e.className})),canvases:[...document.querySelectorAll('canvas')].map(e=>({class:e.className,id:e.id})),images:[...document.querySelectorAll('img')].map(e=>({class:e.className,src:e.src.slice(0,80)}))}));
 fs.mkdirSync('.local/sites/qjdyf',{recursive:true});
 fs.writeFileSync('.local/sites/qjdyf/login-evidence.json',JSON.stringify(evidence,null,2));
 await page.screenshot({path:'.local/sites/qjdyf/login.png',fullPage:true});
 console.log(JSON.stringify(evidence));
}finally{await browser.close();}
