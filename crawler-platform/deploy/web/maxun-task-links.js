// 由采集平台提供明确关联，使用独立节点展示，不搬移 Maxun 的 React 节点。
(()=>{
 'use strict';
 if(document.documentElement.dataset.crawlerApp!=='maxun'||!window.CrawlerAuth)return;
 const platform=window.CrawlerAuth.platform;
 const purposes={business:'业务采集',demo:'模拟演示',acceptance:'测试验收',unclassified:'待分类'};
 const actionLabels={goto:'打开页面',type:'输入文本',click:'点击',press:'按键',waitForSelector:'等待页面元素',waitForTimeout:'等待',platformInputDate:'填写查询日期',platformCaptcha:'识别验证码',platformSubmitLogin:'登录与验证',platformDownload:'下载原始文件',scrapeSchema:'提取数据',scroll:'滚动页面'};
 const stateLabels={COMPLETED:'成功',FAILED:'失败',CRASHED:'异常',CANCELLED:'已取消',RUNNING:'执行中',SCHEDULED:'等待调度',PENDING:'准备执行',PAUSED:'已暂停',CANCELLING:'取消中'};
 let data=null,busy=false,error='',mode='business',native=null,lastPath='';
 const node=(tag,text,parent,cls)=>{const item=document.createElement(tag);if(text)item.textContent=text;if(cls)item.className=cls;if(parent)parent.append(item);return item};
 const button=(text,parent,action)=>{const item=node('button',text,parent,'mx-rel-button');item.type='button';item.onclick=action;return item};
 const link=(text,url,parent)=>{const item=node('a',text,parent,'mx-rel-button');item.href=url;item.target='_blank';item.rel='noopener';return item};
 const badge=(text,parent,state)=>node('span',text,parent,'mx-rel-badge '+(state||''));
 function statusClass(state){return state==='COMPLETED'?'good':['FAILED','CRASHED'].includes(state)?'bad':''}
 function render(){
  const root=document.getElementById('crawler-maxun-relations');if(!root)return;
  root.replaceChildren();const heading=node('div','',root,'mx-rel-heading'),intro=node('div','',heading);node('h2','我的机器人',intro);node('p','按业务理解设计稿、发布版本和执行历史，并与采集平台双向关联。',intro);
  const tools=node('div','',heading,'mx-rel-actions');link('创建机器人',location.origin+'/robots/create',tools);button(busy?'刷新中…':'刷新关联',tools,refresh).disabled=busy;
  const tabs=node('div','',root,'mx-rel-tabs');tabs.setAttribute('aria-label','机器人展示方式');
  for(const [value,label,count]of [['business','业务关联',data?.groups.length],['independent','独立机器人',data?.independent.length],['raw','全部原始记录',data?.robot_count]]){const tab=button(label+' '+(count??'—'),tabs,()=>{mode=value;render()});tab.dataset.relationView=value;tab.setAttribute('aria-pressed',String(mode===value))}
  if(native)native.dataset.relationsHidden=String(mode!=='raw'&&!!data&&!error);
  if(error){node('p',error+'。原始列表仍可使用。',root,'mx-rel-error');return}
  if(!data){node('p','正在读取采集任务与机器人的关联…',root,'mx-rel-empty');return}
  if(mode==='raw'){node('p','这里保留 Maxun 的原始列表，包含设计稿、发布副本和每次运行的执行副本。',root,'mx-rel-note');return}
  if(mode==='independent'){
   if(!data.independent.length)node('p','当前没有未关联的独立机器人。',root,'mx-rel-empty');
   for(const robot of data.independent){const card=node('article','',root,'mx-rel-group');node('h3',robot.name,card);node('p','尚未关联采集平台任务 · '+robot.id.slice(0,8),card,'mx-rel-note');link('编辑机器人',platform+'/collector/open/maxun?robot='+robot.id,card)}
   return;
  }
  if(!data.groups.length){node('p','尚无关联的采集任务。发布机器人后会自动显示设计、发布和运行关系。',root,'mx-rel-empty');return}
  const query=new URLSearchParams(location.search),target=query.get('template'),section=query.get('section');
  for(const group of data.groups){
   const template=group.templates.find(item=>item.id===target)||group.templates.find(item=>item.active)||group.templates[0];
   const card=node('article','',root,'mx-rel-group');card.dataset.relationTask=group.task_key;
   const header=node('div','',card,'mx-rel-group-header');const title=node('div','',header);node('h3',group.task_name,title);const tags=node('div','',title,'mx-rel-actions');badge(purposes[group.purpose]||'待分类',tags);badge(template.active?'已发布 · 活动版本':'历史版本',tags,'good');
   link('查看采集任务 ↗',platform+'/collector/?template='+template.id+'#templates',header);
   node('p','关联平台任务：'+template.name,card,'mx-rel-task-name');
   const stats=node('div','',card,'mx-rel-counts');for(const text of ['设计稿 '+group.drafts.length+' 个','发布版本 '+group.publications.length+' 个','历史执行 '+group.executions.length+' 次'])node('span',text,stats);
   node('p','设计稿 → 固定发布版本 → 每次执行副本 → 文件校验与归档',card,'mx-rel-flow');
   const stages=node('div','',card,'mx-rel-stages');
   const drafts=node('section','',stages,'mx-rel-stage');node('h4','设计稿',drafts);node('p','修改流程后重新发布，业务任务才会使用新版本。',drafts,'mx-rel-note');
   if(!group.drafts.length)node('p','来源设计稿尚未登记',drafts);
   for(const draft of group.drafts){node('strong',draft.name,drafts);node('p',draft.missing?'机器人暂时无法访问':draft.changed_since_publish?'设计稿已变更，尚未重新发布':'已关联发布版本',drafts,'mx-rel-note');if(!draft.missing)link('编辑设计稿 ↗',platform+'/collector/open/maxun?robot='+draft.id,drafts)}
   const published=node('section','',stages,'mx-rel-stage');node('h4','发布版本',published);node('p','采集平台按固定版本引用；此处展示流程摘要。',published,'mx-rel-note');
   for(const version of group.publications){const details=node('details','',published,'mx-rel-publication');details.dataset.publishedRobot=version.id;details.open=version.template_id===target&&section==='published';node('summary',(version.active?'当前活动版本':'历史版本')+' · '+version.template_id.slice(0,12),details);node('p',version.name,details);node('p','机器人 ID：'+version.id,details,'mx-rel-note');node('p','流程包含 '+(version.step_count??'未知')+' 个操作步骤',details);for(const [action,count]of Object.entries(version.actions||{}))node('span',(actionLabels[action]||action)+' × '+count,details,'mx-rel-action-chip')}
   const history=node('details','',card,'mx-rel-history');history.dataset.relationHistory=template.id;history.open=target===template.id&&section==='history';node('summary','执行历史 '+group.executions.length+' 次 · 平台业务结果与 Maxun 流程状态分别展示',history);
   if(!group.executions.length)node('p','尚无平台执行记录',history,'mx-rel-note');
   for(const run of group.executions){const row=node('article','',history,'mx-rel-run');row.dataset.platformState=run.platform_state||'UNKNOWN';const meta=node('div','',row);node('strong',new Date(run.at).toLocaleString('zh-CN',{hour12:false}),meta);node('p',(run.parameters?.begindate||'未指定')+' ～ '+(run.parameters?.enddate||'未指定'),meta,'mx-rel-note');const results=node('div','',row,'mx-rel-run-states');badge('平台结果：'+(stateLabels[run.platform_state]||'待核对'),results,statusClass(run.platform_state));badge('Maxun 流程：'+({success:'成功',failed:'失败',running:'执行中'}[run.maxun_state]||run.maxun_state||'待核对'),results);const actions=node('div','',row,'mx-rel-actions');link('平台日志 ↗',platform+'/v2/runs/flow-run/'+run.prefect_run_id,actions);if(run.maxun_run_id)link('Maxun 执行详情 ↗',location.origin+'/runs/'+run.robot_id+'/run/'+run.maxun_run_id,actions)}
  }
  node('p','关联更新于 '+new Date(data.checked_at).toLocaleTimeString('zh-CN',{hour12:false})+' · 原始记录未删除',root,'mx-rel-note');
 }
 async function refresh(){if(busy)return;busy=true;error='';render();try{const response=await fetch('/_platform/relations');if(!response.ok)throw Error('关联读取失败（HTTP '+response.status+'）');data=await response.json()}catch(reason){error=reason.message}finally{busy=false;render()}}
 function mount(){
  if(location.pathname.replace(/\/$/,'')!=='/robots')return;
  const toolbar=document.querySelector('[data-crawler-robot-toolbar]');if(!toolbar)return;
  native=toolbar.parentElement;native.dataset.crawlerRobotNative='';
  if(!document.getElementById('crawler-maxun-relations')){const root=node('section');root.id='crawler-maxun-relations';native.parentElement.insertBefore(root,native);render();refresh()}
  if(lastPath!==location.href){lastPath=location.href;render()}
 }
 let pending=false;const observer=new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;mount()})}});
 function start(){mount();observer.observe(document.body,{childList:true,subtree:true});setInterval(mount,1200)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
