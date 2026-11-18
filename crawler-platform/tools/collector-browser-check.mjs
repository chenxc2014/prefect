// 验证导入、节点编辑、发布、参数输入和运行完成；使用独立浏览器。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=process.cwd();
const require=createRequire(path.join(root,'vendor/prefect/ui-v2/package.json'));
const {chromium,expect}=require('@playwright/test');
const configuration=JSON.parse(fs.readFileSync('.local/client.json','utf8'));
const auth=configuration.env.PREFECT_API_AUTH_STRING;
const index=auth.indexOf(':');
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage({httpCredentials:{username:auth.slice(0,index),password:auth.slice(index+1)},viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:18843/collector/');
 await expect(page.getByRole('heading',{name:'采集管理平台',exact:true})).toBeVisible();
 await page.locator('#file').setInputFiles('deploy/examples/demo-task.json');
 await expect(page.locator('#steps .node')).toHaveCount(5);
 await page.locator('#name').fill('浏览器验收：日期查询与导出');
 await page.locator('#easyspider-purpose').selectOption('acceptance');
 await page.locator('#easyspider-task-name').fill('浏览器验收：日期查询与导出');
 await page.locator('#patterns').fill('Data/Task_0/result/files/*.csv');
 await page.locator('#minrows').fill('6');
 await page.locator('#columns').fill('id,quantity');
 await page.getByRole('button',{name:'发布不可变版本'}).click();
 await expect(page.locator('#message')).toContainText('已发布版本');
 const entry=page.locator('#templates article').filter({has:page.getByText('浏览器验收：日期查询与导出 · linux-169',{exact:true})});
 await entry.locator('input').fill('2026-11-01');
 await entry.getByRole('button',{name:'运行',exact:true}).click();
 await expect(page.locator('#runs')).toContainText('COMPLETED',{timeout:120000});
 await page.screenshot({path:'.local/screenshots/collector-platform.png',fullPage:true});
 fs.writeFileSync('doc/A方案界面验证.json',JSON.stringify({passed:true,checks:['中文管理页','导入原生EasySpider任务','节点参数编辑','发布不可变版本','填写运行日期','浏览器提交并完成真实采集']},null,2));
 console.log('采集管理界面与真实浏览器执行验收通过');
}finally{await browser.close();}
