// Maxun 的兼容录制面板使用同一录制会话；不向网站镜像注入脚本。
(()=>{
 'use strict';
 if(document.documentElement.dataset.crawlerApp!=='maxun')return;
 let panel,button,controls,status,image,items=[],socket,refreshing=false;
 function el(tag,text,parent){const node=document.createElement(tag);if(text)node.textContent=text;if(parent)parent.append(node);return node;}
 function message(text){status.textContent=text;}
 async function request(event,data={}){
  socket=window.CrawlerRecorderSocket;if(!socket?.connected)throw Error('录制会话尚未连接，请稍后重试');
  return await new Promise((resolve,reject)=>socket.timeout(event==='platform:inspect'?10000:60000).emit(event,data,(error,result)=>error?reject(Error('兼容录制请求超时，请刷新后重试')):result?.ok?resolve(result):reject(Error(result?.error||'操作失败'))));
 }
 function render(result){
  items=result.controls;image.src='data:image/png;base64,'+result.screenshot;controls.replaceChildren();
  for(const item of items){
   const row=el('div','',controls);row.className='crawler-control';row.dataset.control=item.id;
   el('strong',item.label,row);el('small',item.frame+' · '+item.selector,row);
   let input,date;
   if(item.kind==='input'){
    input=el('input','',row);input.type=item.type==='password'?'password':'text';input.autocomplete='off';input.setAttribute('aria-label',item.label);input.placeholder=item.label;
    date=el('label','按日期控件设置',row);const checkbox=el('input','');checkbox.type='checkbox';checkbox.checked=/Time|date/i.test(item.selector);date.prepend(checkbox);date=checkbox;
   }else if(item.kind==='select'){
    input=el('select','',row);for(const value of item.options||[]){const option=el('option',value.label,input);option.value=value.value;}
   }
   const action=el('button',item.kind==='click'?'点击并录制':'填写并录制',row);action.type='button';
   action.onclick=async()=>{action.disabled=true;message('正在操作真实网页并保存录制步骤…');try{render(await request('platform:action',{id:item.id,action:item.kind==='click'?'click':item.kind==='select'?'select':'fill',value:input?.value,date:!!date?.checked}));message('步骤已保存到当前 Maxun 录制，请核对真实页面。');}catch(error){message(error.message);}finally{action.disabled=false;}};
  }
 }
 async function refresh(){if(refreshing)return;refreshing=true;message('正在获取真实截图与控件…');try{render(await request('platform:inspect'));message('截图来自服务器真实浏览器；每次操作都会保存到当前录制。');}catch(error){message(error.message);}finally{refreshing=false;}}
 function mount(){
  if(location.pathname!=='/recording'){panel?.remove();button?.remove();panel=button=null;return;}
  if(button)return;
  button=el('button','兼容录制 · 验证码 / 嵌入页面',document.body);button.id='crawler-recorder-toggle';
  button.style.cssText='position:fixed;right:24px;bottom:20px;z-index:1501;padding:12px 18px;background:#405bf0;color:white;border:0;border-radius:10px;box-shadow:0 6px 24px #23316644;cursor:pointer';
  panel=el('section','',document.body);panel.id='crawler-recorder-panel';panel.hidden=true;panel.style.cssText='position:fixed;inset:100px 24px 76px 24px;background:#fff;border:1px solid #dbe2ee;border-radius:14px;z-index:1500;padding:18px;overflow:auto;color:#172b4d;box-shadow:0 12px 60px #172b4d55';
  const heading=el('div','',panel);el('strong','兼容录制：真实截图与控件',heading);const close=el('button','返回 Maxun 录制器',heading);close.onclick=()=>panel.hidden=true;
  const reload=el('button','刷新真实网页',heading);reload.onclick=refresh;
  status=el('p','',panel);status.setAttribute('role','status');
  const grid=el('div','',panel);grid.style.cssText='display:grid;grid-template-columns:minmax(0,1.5fr) minmax(320px,1fr);gap:20px;align-items:start';
  image=el('img','',grid);image.alt='服务器浏览器真实页面截图';image.style.cssText='width:100%;border:1px solid #e2e8f0;border-radius:8px;position:sticky;top:0';controls=el('div','',grid);
  const style=el('style','',panel);style.textContent='#crawler-recorder-panel button{padding:8px 12px;border:1px solid #b9c6da;border-radius:6px;background:#f5f7ff;color:#253b75;margin:4px;cursor:pointer}#crawler-recorder-panel .crawler-control{border:1px solid #dbe2ee;border-radius:8px;margin-bottom:10px;padding:12px}#crawler-recorder-panel small{display:block;color:#66758a;overflow-wrap:anywhere;margin:5px 0}#crawler-recorder-panel input:not([type=checkbox]),#crawler-recorder-panel select{display:block;padding:8px;width:95%;border:1px solid #bdc9da;border-radius:5px}#crawler-recorder-panel label{font-size:12px;display:block;margin-top:6px}';
  button.onclick=()=>{panel.hidden=!panel.hidden;if(!panel.hidden)refresh();};
 }
 setInterval(()=>{mount();if(panel&&!panel.hidden&&!items.length&&window.CrawlerRecorderSocket?.connected)refresh();},1500);mount();
})();
