// 验证验证码重试有上限，账号错误不会反复登录。
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {install}=require('../deploy/maxun/browser-actions.cjs');
function fakePage(error,successAt){
 let submits=0,refreshes=0;
 const page={url:()=>submits===successAt?'https://site.test/welcome':'https://site.test/login',waitForTimeout:async()=>{},locator(selector){return {first(){return this},async click(){if(selector==='#submit')submits++;else refreshes++},async allTextContents(){return [error]}}}};
 install(page);let ocr=0;page.platformCaptcha=async()=>{ocr++};
 return {page,counts:()=>({submits,refreshes,ocr})};
}
const options={submitSelector:'#submit',captchaSelector:'#captcha',imageSelector:'#image',successUrl:'https://site.test/welcome',errorSelector:'.error',attempts:99};
test('验证码失败最多提交三次且刷新后重新识别',async()=>{
 const {page,counts}=fakePage('验证码错误',3);await page.platformSubmitLogin(options);
 assert.deepEqual(counts(),{submits:3,refreshes:2,ocr:2});
});
test('连续验证码失败停止并报告失败',async()=>{
 const {page,counts}=fakePage('验证码错误',99);
 await assert.rejects(page.platformSubmitLogin(options),/三次重试上限/);
 assert.equal(counts().submits,3);
});
test('账号密码错误只提交一次',async()=>{
 const {page,counts}=fakePage('账号或密码错误',99);
 await assert.rejects(page.platformSubmitLogin(options),/拒绝登录/);
 assert.deepEqual(counts(),{submits:1,refreshes:0,ocr:0});
});
