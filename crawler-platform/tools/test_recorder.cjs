// 对真实控件跨框架路径和秘密输入的录制边界做回归。
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {install}=require('../deploy/maxun/recorder-compat.cjs');
test('兼容面板不接受未发现的控件或任意动作',async()=>{
 const handlers={};const socket={removeAllListeners(){},on(name,fn){handlers[name]=fn}};
 const remote={socket,getCurrentPage(){throw Error('不应访问页面')}};
 install(remote);let result;
 await handlers['platform:action']({id:'unknown',action:'evaluate',value:'private-value'},value=>result=value);
 assert.equal(result.ok,false);assert.equal(JSON.stringify(result).includes('private-value'),false);
});
