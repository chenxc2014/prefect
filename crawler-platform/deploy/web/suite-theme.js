// 统一应用外观。只给真实存在的组件加标记，不搬移原应用的 React 节点。
(()=>{
  'use strict';
  const auth=window.CrawlerAuth;if(!auth)return;
  const root=document.documentElement,app=root.dataset.crawlerApp||'platform';
  const platform=auth.platform;
  const icons={platform:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',prefect:'<rect x="8" y="2" width="8" height="6" rx="1"/><rect x="1" y="16" width="8" height="6" rx="1"/><rect x="15" y="16" width="8" height="6" rx="1"/><path d="M12 8v4m-7 4v-4h14v4"/>',maxun:'<rect x="2" y="3" width="20" height="17" rx="3"/><path d="M2 8h20m-12 4-3 3 3 3m4-6 3 3-3 3"/>'};
  const apps=[{id:'platform',label:'采集工作台',url:platform+'/collector/'},{id:'prefect',label:'Prefect 调度',url:platform+'/collector/open/prefect'},{id:'maxun',label:'Maxun 设计',url:platform+'/collector/open/maxun'}];
  function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;}
  function links(parent,withIcon){for(const item of apps){const a=el('a','',item.label);a.href=item.url;if(item.id===app){a.setAttribute('aria-current','page');a.onclick=e=>e.preventDefault();}else{a.target='_blank';a.rel='noopener';a.title='在新标签页打开'+item.label;}if(withIcon){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.innerHTML=icons[item.id];a.prepend(svg);}parent.append(a);}}
  function switcher(){const nav=el('nav','crawler-app-switcher');nav.setAttribute('aria-label','应用切换');const tabs=el('div','crawler-app-tabs');links(tabs,true);nav.append(tabs);const menu=el('details','crawler-app-menu');menu.append(el('summary','','切换应用 ▾'));const choices=el('div');links(choices,false);menu.append(choices);nav.append(menu);return nav;}
  function account(){let bar=document.getElementById('crawler-unified-account');if(!bar){bar=el('div');bar.id='crawler-unified-account';const home=el('a','','返回采集平台');home.href=platform+'/collector/';bar.append(home,el('span','',auth.username));const button=el('button','','退出统一登录');button.type='button';button.onclick=()=>auth.logout().catch(()=>alert('退出失败，请重试。'));bar.append(button);}bar.removeAttribute('style');bar.className='crawler-suite-account';return bar;}
  function chrome(){
    if(app==='platform'){const top=document.querySelector('.topbar');if(top&&!top.querySelector('.crawler-app-switcher'))top.insertBefore(switcher(),top.querySelector('.topright'));return;}
    if(!document.getElementById('crawler-suite-brand')){const brand=el('a');brand.id='crawler-suite-brand';brand.href=platform+'/collector/';brand.setAttribute('aria-label','返回采集工作台');const mark=el('span','crawler-brand-icon');mark.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 10 5v10l-10 5-10-5V7l10-5Zm0 10 10-5M12 12 2 7m10 5v10M7 4.5l10 5"/></svg>';const copy=el('span','crawler-brand-copy','采集管理');copy.append(el('small','','COLLECTION HUB'));brand.append(mark,copy);document.body.append(brand);}
    let header=document.getElementById('crawler-suite-header');if(!header){header=el('header');header.id='crawler-suite-header';const title=el('div','crawler-suite-title');title.append(el('small','','采集工作台 / '+(app==='prefect'?'任务编排':'在线设计')),el('strong','',app==='prefect'?'Prefect 调度监控':'Maxun 在线设计器'));header.append(title,switcher());document.body.append(header);}if(!header.querySelector('#crawler-unified-account'))header.append(account());
  }
  function mark(){
    const recording=app==='maxun'&&location.pathname.startsWith('/recording');root.dataset.crawlerWorkspace=recording?'recording':'dashboard';
    const mode=app==='prefect'&&root.classList.contains('dark')||app==='maxun'&&localStorage.getItem('darkMode')==='true'?'dark':'light';if(root.dataset.crawlerColor!==mode)root.dataset.crawlerColor=mode;
    if(app==='prefect'){const main=document.querySelector('main');if(main&&!main.hasAttribute('data-crawler-content'))main.dataset.crawlerContent='prefect';}
    if(app==='maxun'){
      const logo=document.querySelector('img[src*="maxunlogo"]');if(logo){const brand=logo.parentElement,header=brand?.parentElement;if(header&&!header.hasAttribute('data-crawler-native-header')){header.dataset.crawlerNativeHeader='';brand.dataset.crawlerNativeBrand='';}for(const node of header?.querySelectorAll('p,span')||[]){if(node.children.length===0&&node.textContent.includes('@crawler.local'))node.dataset.crawlerNativeEmail='';}}
      const tabs=document.querySelector('[role="tablist"][aria-orientation="vertical"]');const paper=tabs?.closest('.MuiPaper-root');if(paper&&!paper.hasAttribute('data-crawler-nav')){paper.dataset.crawlerNav='';const wrap=paper.parentElement;wrap.dataset.crawlerNavWrap='';const layout=wrap.parentElement;layout.dataset.crawlerLayout='';const main=wrap.nextElementSibling;if(main)main.dataset.crawlerMain='';}
      const create=document.querySelector('.MuiIconButton-root[aria-label="new"]');if(create&&!create.parentElement.hasAttribute('data-crawler-robot-actions')){create.parentElement.dataset.crawlerRobotActions='';create.parentElement.parentElement.dataset.crawlerRobotToolbar='';}
    }
    chrome();
  }
  let scheduled=false;const observer=new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;mark();});}});
  function mount(){mark();observer.observe(document.body,{childList:true,subtree:true});setInterval(mark,1200);window.addEventListener('popstate',mark);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
