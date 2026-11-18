// 在线设计器的通用日期输入与图片验证码动作，秘密值不写入日志。
const crypto = require('crypto');
const decrypt = value => {
  const [iv, body] = value.split(':');
  const cipher = crypto.createDecipheriv('aes-256-cbc', Buffer.from(process.env.ENCRYPTION_KEY, 'hex'), Buffer.from(iv, 'hex'));
  return Buffer.concat([cipher.update(Buffer.from(body, 'hex')), cipher.final()]).toString();
};
function locate(page, selector) {
  if(selector.includes('internal:control=enter-frame'))return page.locator(selector).first();
  if(selector.includes(':>>'))return page.locator(selector.replace(/\s*:>>\s*/g,' >> internal:control=enter-frame >> ')).first();
  // 选择器来自真实网页的录制记录；跨框架优先由录制器保存的路径解析。
  const parts = selector.split(/\s*>>\s*/);
  let context = page;
  while (parts.length > 1) context = context.frameLocator(parts.shift());
  return context.locator(parts[0]).first();
}
function captureBlobDownloads(){
  if(window.__crawlerBlobDownloads)return;
  const state={enabled:false,files:[],blobs:new Map(),seen:new Set()};window.__crawlerBlobDownloads=state;
  const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
  URL.createObjectURL=function(blob){const url=create(blob);if(blob instanceof Blob&&blob.size<=10*1024*1024){state.blobs.set(url,blob);if(state.blobs.size>20)state.blobs.delete(state.blobs.keys().next().value)}return url};
  URL.revokeObjectURL=function(url){revoke(url);state.blobs.delete(url)};
  const capture=(url,name)=>{
    if(!state.enabled||!state.blobs.has(url)||state.seen.has(url))return;
    state.seen.add(url);const blob=state.blobs.get(url),reader=new FileReader();
    reader.onload=()=>state.files.push({name:(name||('下载文件'+(/spreadsheet|excel/.test(blob.type)?'.xlsx':'.bin'))).split(/[\\/]/).pop(),mimeType:blob.type||'application/octet-stream',data:String(reader.result).split(',')[1]});
    reader.readAsDataURL(blob);
  };
  const click=HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click=function(){if(this.href.startsWith('blob:'))capture(this.href,this.download);return click.call(this)};
  const dispatch=HTMLAnchorElement.prototype.dispatchEvent;
  HTMLAnchorElement.prototype.dispatchEvent=function(event){if(event.type==='click'&&this.href.startsWith('blob:'))capture(this.href,this.download);return dispatch.call(this,event)};
  document.addEventListener('click',event=>{const anchor=event.target?.closest?.('a');if(anchor?.href.startsWith('blob:'))capture(anchor.href,anchor.download)},true);
  const open=window.open;
  window.open=function(url,...args){if(typeof url==='string'&&url.startsWith('blob:'))capture(url,'');return open.call(this,url,...args)};
}
exports.install = (page,saveBinary) => {
  const initialize=saveBinary?Promise.resolve(page.context().addInitScript(captureBlobDownloads)).then(()=>Promise.all(page.frames().map(frame=>frame.evaluate(captureBlobDownloads).catch(()=>{})))):Promise.resolve();
  page.platformInputDate = async (selector, encrypted) => {
    const target = locate(page, selector);
    await target.evaluate((element, value) => {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      descriptor.set.call(element, value);
      for (const name of ['input', 'change', 'blur']) element.dispatchEvent(new Event(name, {bubbles: true}));
      element.blur();
    }, decrypt(encrypted));
  };
  page.platformCaptcha = async (selector, explicitImage) => {
    const input = locate(page, selector);
    const imagePath = explicitImage || await input.evaluate(element => {
      const box = element.getBoundingClientRect();
      let root = element.closest('form') || element.parentElement;
      let candidates = [];
      for (let depth = 0; root && depth < 6; depth++, root = root.parentElement) {
        candidates = [...root.querySelectorAll('canvas,img')].filter(node => {
          const rect = node.getBoundingClientRect();
          return rect.width >= 30 && rect.height >= 15 && rect.width <= 500 && rect.height <= 200 && getComputedStyle(node).visibility !== 'hidden';
        });
        if (candidates.length) break;
      }
      if (!candidates.length) throw new Error('未在验证码输入框附近找到图片，请重新录制或补充配置');
      const distance = node => {const r=node.getBoundingClientRect();return Math.abs(r.y-box.y)*2+Math.abs(r.x-box.x)};
      const node = candidates.sort((a,b) => distance(a)-distance(b))[0];
      const parts=[];
      for (let current=node; current && current.nodeType===1; current=current.parentElement) {
        if (current.id) {parts.unshift('#'+CSS.escape(current.id));break}
        const siblings=current.parentElement ? [...current.parentElement.children].filter(x=>x.tagName===current.tagName) : [current];
        parts.unshift(current.tagName.toLowerCase()+':nth-of-type('+(siblings.indexOf(current)+1)+')');
      }
      return parts.join(' > ');
    });
    const frame = await (await input.elementHandle()).ownerFrame();
    const image = frame.locator(imagePath);
    const content = await image.screenshot();
    const response = await fetch('http://host.docker.internal:18767/recognize', {
      method:'POST',headers:{'Content-Type':'image/png','x-api-key':process.env.CRAWLER_OCR_KEY},body:content
    });
    if (!response.ok) throw new Error('图片验证码识别服务未成功返回');
    const result = await response.json();
    await input.fill(result.text);
  };
  page.platformSubmitLogin = async options => {
    const attempts=Math.min(3,Math.max(1,Number(options.attempts)||3));
    for(let attempt=0;attempt<attempts;attempt++){
      if(attempt){
        await locate(page,options.imageSelector).click();
        await page.waitForTimeout(300);
        await page.platformCaptcha(options.captchaSelector,options.imageSelector);
      }
      await locate(page,options.submitSelector).click();
      const deadline=Date.now()+25000;let captchaError=false;
      while(Date.now()<deadline){
        if(page.url()===options.successUrl)return;
        const errors=await page.locator(options.errorSelector).allTextContents().catch(()=>[]);
        if(errors.length){
          if(errors.some(message=>message.includes('验证码'))){captchaError=true;break;}
          if(errors.some(message=>/账号|密码|权限|锁定|停用/.test(message)))throw Error('网站拒绝登录，请检查账号权限或受限配置');
        }
        await page.waitForTimeout(300);
      }
      if(!captchaError)throw Error('网站登录未到达已验证的成功页面，停止重试');
    }
    throw Error('图片验证码连续识别失败，已达到三次重试上限');
  };
  page.platformClick = async (selector,options={}) => {
    const target=locate(page,selector);
    if(options.optional&&!await target.isVisible().catch(()=>false))return;
    await target.click();
    if(options.delay)await page.waitForTimeout(Math.min(Number(options.delay),10000));
  };
  page.platformDownload = async selector => {
    await initialize;
    const context=page.context(),watched=new Set();let resolveDownload,rejectDownload;
    const pending=new Promise((resolve,reject)=>{resolveDownload=resolve;rejectDownload=reject});
    pending.catch(()=>{});
    const receive=download=>resolveDownload(download);
    const watch=target=>{if(watched.has(target))return;watched.add(target);target.on('download',receive)};
    context.pages().forEach(watch);context.on('page',watch);
    const timer=setTimeout(()=>rejectDownload(Error('网站导出未产生下载事件，请检查嵌入页面和导出返回')),120000);
    const trace=[];let resolveResponse;
    const responseResult=new Promise(resolve=>{resolveResponse=resolve});
    const onResponse=async response=>{
      try{
        const headers=response.headers(),type=headers['content-type']||'',disposition=headers['content-disposition']||'';
        const url=new URL(response.url());
        const item={path:url.origin+url.pathname,status:response.status(),type};trace.push(item);
        if(!saveBinary||!response.ok()||!(/spreadsheet|excel|octet-stream/.test(type)||/attachment/i.test(disposition)))return;
        if(Number(headers['content-length']||0)>10*1024*1024){item.tooLarge=true;return;}
        const bytes=await response.body();
        if(!bytes.length||bytes.length>10*1024*1024)return;
        // 只接受文件响应；JSON 错误页和普通网页不能冒充导出产物。
        if(bytes[0]!==0x50||bytes[1]!==0x4b){item.notZip=true;return;}
        const utf=disposition.match(/filename\*=UTF-8''([^;]+)/i),plain=disposition.match(/filename\s*=\s*"?([^";]+)/i);
        let name=utf?.[1]||plain?.[1]||url.pathname.split('/').pop()||'';
        try{name=decodeURIComponent(name)}catch{}
        if(!/\.[a-z0-9]{2,5}$/i.test(name))name='下载文件.xlsx';
        name=name.split(/[\\/]/).pop();
        await saveBinary({name,mimeType:type||'application/octet-stream',data:bytes.toString('base64')});
        resolveResponse({method:'network-response',files:[name]});
      }catch{trace.push({bodyUnavailable:true});}
    };
    context.on('response',onResponse);
    const deadline=Date.now()+120000;let stopped=false;
    const frames=()=>context.pages().flatMap(target=>target.frames());
    for(const frame of frames())await frame.evaluate(()=>{const state=window.__crawlerBlobDownloads;if(state){state.enabled=true;state.files=[];state.seen.clear()}}).catch(()=>{});
    const blobResult=(async()=>{
      while(!stopped&&Date.now()<deadline){
        for(const frame of frames()){
          const files=await frame.evaluate(()=>{const state=window.__crawlerBlobDownloads;return state?state.files.splice(0):[]}).catch(()=>[]);
          if(files.length&&saveBinary){for(const file of files)await saveBinary(file);return {method:'blob',files:files.map(file=>file.name)};}
        }
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      if(!stopped)throw Error('网站导出未返回完整文件');
      return await new Promise(()=>{});
    })();
    blobResult.catch(()=>{});
    try{
      await locate(page,selector).click();
      if(saveBinary){
        await page.waitForTimeout(2000);
        await saveBinary({name:'下载触发页面.png',mimeType:'image/png',data:(await page.screenshot({type:'png'})).toString('base64')});
      }
      const nativeResult=pending.then(async download=>{if(await download.failure())return await new Promise(()=>{});return {method:'browser-event',files:[download.suggestedFilename()]};});
      const captured=await Promise.race([nativeResult,blobResult,responseResult]);
      if(saveBinary)await saveBinary({name:'download-method.json',mimeType:'application/json',data:Buffer.from(JSON.stringify(captured)).toString('base64')});
    }finally{
      stopped=true;
      context.off('response',onResponse);
      clearTimeout(timer);context.off('page',watch);for(const target of watched)target.off('download',receive);
      if(saveBinary)await saveBinary({name:'download-trace.json',mimeType:'application/json',data:Buffer.from(JSON.stringify(trace)).toString('base64')});
      for(const frame of frames())await frame.evaluate(()=>{if(window.__crawlerBlobDownloads)window.__crawlerBlobDownloads.enabled=false}).catch(()=>{});
    }
  };
  return initialize;
};
