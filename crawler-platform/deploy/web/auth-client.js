// 统一登录适配：在浏览器中仅使用会话与 CSRF 值，不存储平台密码。
(()=>{
  'use strict';
  const session=__CRAWLER_SESSION__,platform=__PLATFORM_ORIGIN__;
  const app=document.currentScript?.dataset.app||'platform';
  document.documentElement.dataset.crawlerApp=app;
  const isMaxun=app==='maxun';
  const paths={me:isMaxun?'/_platform/session':'/collector/api/auth/me',logout:isMaxun?'/_platform/logout':'/collector/api/auth/logout'};
  const originalFetch=window.fetch.bind(window),originalOpen=XMLHttpRequest.prototype.open,originalSend=XMLHttpRequest.prototype.send;
  let leaving=false;
  localStorage.removeItem('prefect-password');
  function leave(){if(leaving)return;leaving=true;localStorage.removeItem('user');localStorage.removeItem('prefect-password');location.replace(platform+'/collector/login');}
  async function logout(){const response=await originalFetch(paths.logout,{method:'POST',credentials:'same-origin',headers:{'X-Crawler-CSRF':session.csrf}});if(response.ok||response.status===401)leave();else alert('退出未完成，请刷新页面后重试。');}
  window.CrawlerAuth={username:session.username,logout,platform};
  if(isMaxun){for(const key of ['pushState','replaceState']){const original=history[key];history[key]=function(...args){const result=original.apply(this,args);if(!leaving&&['/login','/register'].includes(location.pathname))location.replace('/_platform/enter');return result;};}}
  window.fetch=async(input,options)=>{
    const url=new URL(typeof input==='string'?input:input instanceof URL?input.href:input.url,location.href);
    const method=(options?.method||(input instanceof Request?input.method:'GET')).toUpperCase();
    if(url.origin===location.origin&&!['GET','HEAD','OPTIONS'].includes(method)){
      const headers=new Headers(options?.headers||(input instanceof Request?input.headers:undefined));headers.set('X-Crawler-CSRF',session.csrf);options={...options,headers};
    }
    const response=await originalFetch(input,options);
    if(response.status===401&&url.origin===location.origin)leave();
    return response;
  };
  XMLHttpRequest.prototype.open=function(method,url,...rest){
    const target=new URL(String(url),location.href);this.crawlerSameOrigin=target.origin===location.origin;
    this.crawlerLogout=isMaxun&&this.crawlerSameOrigin&&target.pathname==='/auth/logout';
    this.crawlerMethod=(this.crawlerLogout?'POST':method).toUpperCase();
    this.addEventListener('loadend',()=>{if(this.crawlerLogout||this.status===401&&this.crawlerSameOrigin)leave();});
    return originalOpen.call(this,this.crawlerMethod,this.crawlerLogout?paths.logout:url,...rest);
  };
  XMLHttpRequest.prototype.send=function(body){
    if(this.crawlerSameOrigin&&!['GET','HEAD','OPTIONS'].includes(this.crawlerMethod))this.setRequestHeader('X-Crawler-CSRF',session.csrf);
    return originalSend.call(this,body);
  };
  function mount(){
    document.querySelectorAll('[data-crawler-user]').forEach(n=>n.textContent=session.username);
    document.querySelectorAll('[data-crawler-logout]').forEach(n=>n.onclick=()=>logout().catch(()=>alert('网络连接失败，请重试。')));
    if(app!=='platform'&&!location.pathname.startsWith('/recording')&&!document.getElementById('crawler-unified-account')){
      const bar=document.createElement('div');bar.id='crawler-unified-account';bar.style.cssText='position:fixed;bottom:14px;right:18px;z-index:2147483000;display:flex;align-items:center;gap:12px;padding:8px 13px;background:#17233fee;color:#d8e2ff;border:1px solid #61719a;border-radius:8px;font:11px/1.6 system-ui;box-shadow:0 4px 20px #0002';
      const home=document.createElement('a');home.textContent='返回采集平台';home.href=platform+'/collector/';home.style.color='#d8e2ff';bar.append(home);
      const user=document.createElement('span');user.textContent=session.username;bar.append(user);
      const button=document.createElement('button');button.textContent='退出统一登录';button.style.cssText='border:0;background:none;color:#d8e2ff;font:inherit;cursor:pointer;padding:0';button.onclick=()=>logout().catch(()=>alert('退出失败，请重试。'));bar.append(button);document.body.append(bar);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
  async function check(){if(leaving)return;try{const result=await originalFetch(paths.me,{credentials:'same-origin',cache:'no-store'});if(result.status===401)leave();}catch{}}
  setInterval(check,10000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)void check();});
})();
