// 为 Maxun 录制会话提供真实控件清单，覆盖 Canvas 和跨域 iframe。
const crypto = require('crypto');
const encrypted = value => {
  const iv=crypto.randomBytes(16), cipher=crypto.createCipheriv('aes-256-cbc',Buffer.from(process.env.ENCRYPTION_KEY,'hex'),iv);
  return iv.toString('hex')+':'+Buffer.concat([cipher.update(String(value)),cipher.final()]).toString('hex');
};
const describe = () => {
  const css = element => {
    const escape=CSS.escape;
    if(element.classList.contains('close-icon'))return '.close-icon';
    if(element.getAttribute('placeholder'))return element.tagName.toLowerCase()+'[placeholder='+JSON.stringify(element.getAttribute('placeholder'))+']';
    if(element.id&&!element.id.startsWith('el-id-'))return '#'+escape(element.id);
    if(element.getAttribute('lay-filter'))return '[lay-filter='+JSON.stringify(element.getAttribute('lay-filter'))+']';
    const text=element.innerText?.trim();
    if(element.tagName==='BUTTON'&&text&&[...document.querySelectorAll('button')].filter(e=>e.innerText.trim()===text).length===1)return 'button >> text='+JSON.stringify(text);
  const parts=[];
    for(let node=element;node&&node.tagName!=='HTML';node=node.parentElement){
      if(node.id&&!node.id.startsWith('el-id-')){parts.unshift('#'+escape(node.id));break;}
      const peers=node.parentElement?[...node.parentElement.children].filter(e=>e.tagName===node.tagName):[node];
      parts.unshift(node.tagName.toLowerCase()+':nth-of-type('+(peers.indexOf(node)+1)+')');
    }
    return parts.join(' > ');
  };
  return [...document.querySelectorAll('input,textarea,select,button,a[href],canvas,[role="menuitem"],.el-sub-menu__title,.close-icon,.layui-layer-btn0')].filter(element=>{
    const rect=element.getBoundingClientRect(),style=getComputedStyle(element);
    return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&element.type!=='hidden';
  }).slice(0,240).map(element=>({selector:css(element),label:(element.getAttribute('placeholder')||element.getAttribute('aria-label')||element.innerText||element.title||element.name||element.id||(element.tagName==='CANVAS'?'Canvas 图像':'网页控件')).trim().slice(0,100),kind:/^(INPUT|TEXTAREA)$/.test(element.tagName)?'input':element.tagName==='SELECT'?'select':'click',type:element.type||'',readonly:!!element.readOnly,options:element.tagName==='SELECT'?[...element.options].map(o=>({value:o.value,label:o.text})):undefined}));
};
async function framePrefix(frame,page){
  if(frame===page.mainFrame())return '';
  const handle=await frame.frameElement();
  const selector=await handle.evaluate(element=>{
    if(element.id)return '#'+CSS.escape(element.id);
    if(element.name)return 'iframe[name='+JSON.stringify(element.name)+']';
    const siblings=[...element.ownerDocument.querySelectorAll('iframe,frame')];
    return ':is(iframe,frame):nth-of-type('+(siblings.indexOf(element)+1)+')';
  });
  return await framePrefix(frame.parentFrame(),page)+selector+' >> internal:control=enter-frame >> ';
}
exports.install = remote => {
  const socket=remote.socket;
  socket.removeAllListeners('platform:inspect');socket.removeAllListeners('platform:action');
  let controls=[];let busy=false;
  async function inspect(){
    const page=remote.getCurrentPage();if(!page||page.isClosed())throw Error('没有活动网页');
    const result=[];
    for(const frame of page.frames()){
      if(!/^https?:/.test(frame.url()))continue;
      const prefix=await framePrefix(frame,page);
      const items=await frame.evaluate(describe).catch(()=>[]);
      for(const item of items)result.push({...item,selector:prefix+item.selector,frame:frame===page.mainFrame()?'主页面':'嵌入页面'});
    }
    controls=result.map((item,index)=>({...item,id:String(index)}));
    return {url:page.url(),controls,screenshot:(await page.screenshot({type:'png',fullPage:false})).toString('base64')};
  }
  socket.on('platform:inspect',async(_,reply)=>{
    if(typeof reply!=='function')return;
    try{reply({ok:true,...await inspect()});}catch{reply({ok:false,error:'页面尚未就绪，请稍后刷新兼容视图'});}
  });
  socket.on('platform:action',async(data,reply)=>{
    if(typeof reply!=='function')return;
    if(busy){reply({ok:false,error:'上一步仍在执行'});return;}
    busy=true;
    try{
      const item=controls.find(c=>c.id===data.id);
      if(!item)throw Error('控件已变化');
      const page=remote.getCurrentPage(),url=page.url(),target=page.locator(item.selector).first();
      let action;
      if(data.action==='click'&&item.kind==='click'){
        await target.click();action={action:'click',args:[item.selector]};
      }else if(data.action==='fill'&&item.kind==='input'){
        if(typeof data.value!=='string'||data.value.length>2000)throw Error('输入值无效');
        if(data.date){
          await target.evaluate((element,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(element,value);for(const name of ['input','change','blur'])element.dispatchEvent(new Event(name,{bubbles:true}));element.blur();},data.value);
        }else await target.fill(data.value);
        action={action:data.date?'platformInputDate':'type',args:[item.selector,encrypted(data.value),item.type]};
      }else if(data.action==='select'&&item.kind==='select'){
        await target.selectOption(data.value);action={action:'selectOption',args:[item.selector,data.value]};
      }else throw Error('操作与控件类型不匹配');
      await remote.generator.addPairToWorkflowAndNotifyClient({where:{url,selectors:[item.selector]},what:[action,{action:'waitForTimeout',args:[1200]}]},page);
      await page.waitForTimeout(1500);
      reply({ok:true,...await inspect()});
    }catch{reply({ok:false,error:'网页操作未完成，请刷新控件后重试；步骤未保存时请勿发布'});}
    finally{busy=false;}
  });
};
