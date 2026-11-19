// 由采集平台提供明确关联，使用独立节点展示，不搬移 Maxun 的 React 节点。
(()=>{
 'use strict';
 if(document.documentElement.dataset.crawlerApp!=='maxun'||!window.CrawlerAuth)return;
 const platform=window.CrawlerAuth.platform;
 const purposes={business:'业务采集',demo:'模拟演示',acceptance:'测试验收',unclassified:'待分类'};
 const actionLabels={goto:'打开页面',type:'输入文本',click:'点击',press:'按键',waitForSelector:'等待页面元素',waitForTimeout:'等待',platformInputDate:'填写查询日期',platformCaptcha:'识别验证码',platformSubmitLogin:'登录与验证',platformDownload:'下载原始文件',scrapeSchema:'提取数据',scroll:'滚动页面'};
 const stateLabels={COMPLETED:'成功',FAILED:'失败',CRASHED:'异常',CANCELLED:'已取消',RUNNING:'执行中',SCHEDULED:'等待调度',PENDING:'准备执行',PAUSED:'已暂停',CANCELLING:'取消中'};
 const editPath=/^\/robots\/([a-f0-9-]{36})\/edit\/?$/i;
 let data=null,busy=false,error='',mode='business',native=null,lastPath='';
 let returningDraft='',recordingWindow=null;
 const node=(tag,text,parent,cls)=>{const item=document.createElement(tag);if(text)item.textContent=text;if(cls)item.className=cls;if(parent)parent.append(item);return item};
 const button=(text,parent,action)=>{const item=node('button',text,parent,'mx-rel-button');item.type='button';item.onclick=action;return item};
 const link=(text,url,parent)=>{const item=node('a',text,parent,'mx-rel-button');item.href=url;item.target='_blank';item.rel='noopener';return item};
 const badge=(text,parent,state)=>node('span',text,parent,'mx-rel-badge '+(state||''));
 function statusClass(state){return state==='COMPLETED'?'good':['FAILED','CRASHED'].includes(state)?'bad':''}
 function releaseLink(versionId,robotId,parent){
  const action=link('检查并发布',platform+'/collector/?release='+versionId+'&draft='+robotId+'#templates',parent);
  action.classList.add('mx-draft-publish');
 }

 // Maxun 的基本设置保存成功后默认跳转列表。仅接管当前设计稿的保存回跳。
 const openRequest=XMLHttpRequest.prototype.open;
 XMLHttpRequest.prototype.open=function(method,url,...options){
  const id=editPath.exec(location.pathname)?.[1],target=new URL(String(url),location.href);
  const request=openRequest.call(this,method,url,...options);
  if(id&&method.toUpperCase()==='PUT'&&target.origin===location.origin&&target.pathname==='/storage/recordings/'+id){
   this.addEventListener('load',()=>{
    if(this.status===200&&editPath.exec(location.pathname)?.[1]===id&&document.querySelector('.mx-draft-maintenance:not([hidden])'))returningDraft=id;
   },{once:true});
  }
  return request;
 };

 async function readRobotResource(path, options={}){
  const response=await fetch(path,{...options,signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw new Error('请求未完成，请刷新后重试。');
  return response.json();
 }

 function openRetraining(robot, start, status, saved){
  // 录制页从新窗口的会话存储读取来源机器人，与 Maxun 原始 Retrain 入口使用相同数据。
  const workflow=robot.recording?.workflow||[];
  const url=workflow.at(-1)?.what?.find(step=>step.action==='goto')?.args?.[0]||robot.recording_meta.url;
  if(!/^https?:\/\//i.test(url||'')){
   status.textContent='请先在基本设置中保存有效的目标网址。';
   return;
  }
  const recording=window.open('','_blank');
  if(!recording){status.textContent='浏览器阻止了录制窗口，请允许弹出窗口后重试。';return;}
  recording.document.title='正在检查录制会话';
  recording.document.body.textContent='正在检查录制会话…';
  start.disabled=true;
  status.textContent='正在检查录制会话…';
  readRobotResource('/record/can-create/recording').then(result=>{
   if(result.canCreate!==true)throw new Error('已有录制会话。请先完成或关闭原录制窗口，再重新录制。');
   if(recording.closed)throw new Error('录制窗口已关闭。');
   const session=crypto.randomUUID();
   const fields={browserId:'new-recording',robotToRetrain:robot.recording_meta.id,robotName:robot.recording_meta.name,
    recordingUrl:url,initialUrl:url,recordingSessionId:session,recordingOriginPage:location.pathname};
   recording.sessionStorage.removeItem('tabMode');
   recording.sessionStorage.removeItem('nextTabIsRecording');
   for(const [key,value]of Object.entries(fields))recording.sessionStorage.setItem(key,value);
   recordingWindow={window:recording,saved,status};
   recording.location.replace('/recording-setup?session='+encodeURIComponent(session));
   status.textContent='已在新窗口打开录制。';
  }).catch(reason=>{recording.close();status.textContent=reason.message;})
   .finally(()=>{start.disabled=false;});
 }
 window.addEventListener('message',event=>{
  if(!recordingWindow||event.origin!==location.origin||event.source!==recordingWindow.window||event.data?.type!=='recording-notification')return;
  const recording=recordingWindow;
  recordingWindow=null;
  if(event.data.notification?.type==='success'){recording.status.textContent='';recording.saved();}
  else recording.status.textContent='录制未保存，请检查录制结果后重试。';
 });

 function confirmDraftDeletion(robotId, robotName, status){
  const dialog=node('dialog','',document.body,'mx-draft-dialog');
  const heading=node('h2','删除机器人',dialog);
  heading.id='mx-draft-delete-title';
  dialog.setAttribute('aria-labelledby',heading.id);
  node('p','确定删除「'+robotName+'」吗？删除后将无法继续编辑这份设计稿，已发布任务仍使用各自的固定版本。',dialog);
  const feedback=node('p','',dialog,'mx-draft-status');feedback.setAttribute('role','status');
  const controls=node('div','',dialog,'mx-draft-actions');
  const cancel=button('取消',controls,()=>dialog.close());
  cancel.autofocus=true;
  const confirm=button('确认删除',controls,async()=>{
   confirm.disabled=true;cancel.disabled=true;
   feedback.textContent='正在检查运行记录…';
   try{
    const path='/storage/recordings/'+robotId;
    const {runs}=await readRobotResource(path+'/runs');
    if(runs?.totalCount!==0)throw new Error(Number.isInteger(runs?.totalCount)
     ?'该机器人有关联的运行记录，无法删除。':'无法核对运行记录，请稍后重试。');
    if(await readRobotResource(path,{method:'DELETE'})!==true)throw new Error('删除未完成，请稍后重试。');
    dialog.close();
    location.assign('/robots');
   }catch(reason){feedback.textContent=reason.message;confirm.disabled=false;cancel.disabled=false;}
  });
  confirm.classList.add('mx-draft-danger');
  dialog.addEventListener('cancel',event=>{if(confirm.disabled)event.preventDefault();});
  dialog.addEventListener('close',()=>dialog.remove(),{once:true});
  try{dialog.showModal();}catch{dialog.remove();status.textContent='无法打开确认窗口，请刷新后重试。';}
 }

 function mountDraftMaintenance(robotId){
  const heading=[...document.querySelectorAll('h6')].find(item=>['编辑机器人','Edit Robot'].includes(item.textContent.trim()));
  const header=heading?.parentElement;
  const form=header?.parentElement;
  if(!form||form.querySelector('.mx-draft-maintenance'))return;
  form.classList.add('mx-draft-config');
  const area=node('section','',null,'mx-draft-maintenance');
  header.after(area);
  const release=node('div','',area,'mx-draft-release');
  const feedback=node('p','',release,'mx-draft-feedback');feedback.setAttribute('role','status');
  const releases=node('div','',release);
  const toolbar=node('div','',area,'mx-draft-toolbar');
  const tabs=node('div','',toolbar,'mx-draft-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','设计稿维护');
  const actions=node('div','',toolbar,'mx-draft-actions');
  const retrainPanel=node('div','',area,'mx-draft-retrain');
  retrainPanel.id='mx-draft-retrain';
  node('h2','重新录制网页操作',retrainPanel);
  node('p','在新的录制窗口中操作网站。保存时替换当前设计稿，业务任务在重新发布后使用新流程。',retrainPanel);
  const start=button('开始重新录制',retrainPanel,()=>openRetraining(robot,start,status,()=>{
   if(!area.isConnected)return;
   selectTab('basic');
   readRobotResource('/storage/recordings/'+robotId).then(item=>{robot=item;}).catch(()=>{});
   updateRelease('录制已保存');
  }));
  const status=node('p','',area,'mx-draft-status');status.setAttribute('role','status');
  const basic=button('基本设置',tabs,()=>selectTab('basic'));
  const retrain=button('重新录制',tabs,()=>selectTab('retrain'));
  retrain.setAttribute('aria-controls',retrainPanel.id);
  let robot,refreshToken=0,ready=false,lastSaved='';
  start.disabled=true;retrain.disabled=true;
  function selectTab(tab){
   form.dataset.draftTab=tab;
   basic.setAttribute('aria-pressed',String(tab==='basic'));
   retrain.setAttribute('aria-pressed',String(tab==='retrain'));
   retrainPanel.hidden=tab!=='retrain';
  }
  async function updateRelease(saved=''){
   if(saved)lastSaved=saved;
   const request=++refreshToken;
   if(!releases.children.length)feedback.textContent=lastSaved||'正在核对当前发布版本…';
   try{
    const result=await readRobotResource('/_platform/relations?draft='+robotId);
    if(!area.isConnected||request!==refreshToken)return;
    releases.replaceChildren();
    feedback.textContent=lastSaved;
    release.hidden=!lastSaved&&!result.versions.length;
    for(const version of result.versions){
     const row=node('div','',releases,'mx-draft-release-row');
     const summary=node('div','',row);
     node('strong',version.task_name,summary);
     const head=link('当前版本 '+version.id.slice(0,12),platform+'/collector/?template='+version.id+'#templates',summary);
     head.classList.add('mx-draft-version');
     badge(version.changed?'草稿待发布':'已与当前版本同步',summary,version.changed?'pending':'good');
     if(version.changed)releaseLink(version.id,robotId,row);
    }
    if(lastSaved&&!result.versions.length)node('p','此设计稿暂无关联的活动版本。',releases);
   }catch{
    if(!area.isConnected||request!==refreshToken)return;
    release.hidden=false;
    releases.replaceChildren();
    feedback.textContent=(lastSaved?lastSaved+'。':'')+'暂时无法读取发布状态。';
    button('重新检查',releases,()=>updateRelease(saved));
   }
  }
  area.addEventListener('crawler-draft-visible',()=>{if(ready)updateRelease();});
  selectTab('basic');
  readRobotResource('/storage/recordings/'+robotId).then(item=>{
   if(!area.isConnected)return;
   const meta=item?.recording_meta;
   if(meta?.id!==robotId||typeof meta.name!=='string')throw new Error('无法读取机器人维护信息，请刷新后重试。');
   if(/^(平台发布|平台执行) ·/.test(meta.name)){area.hidden=true;return;}
   robot=item;
   ready=true;
   const savedUrl=new URL(location.href);
   const justSaved=savedUrl.searchParams.has('draftSaved');
   if(justSaved){savedUrl.searchParams.delete('draftSaved');history.replaceState(history.state,'',savedUrl);}
   updateRelease(justSaved?'基本设置已保存':'');
   if(meta.type==='extract'&&!meta.isLLM){
    retrain.disabled=false;start.disabled=false;
    if(item.recording?.workflow?.some(pair=>pair.what?.some(step=>step.action?.startsWith('platform')))){
     const note=node('p','此设计稿含平台适配动作。覆盖前建议先复制机器人保留原流程。',null,'mx-draft-note');
     start.before(note);
    }
    link('复制机器人','/robots/'+robotId+'/duplicate',actions);
   }else retrain.hidden=true;
   button('删除机器人',actions,()=>confirmDraftDeletion(robotId,meta.name,status)).classList.add('mx-draft-danger');
  }).catch(reason=>{if(area.isConnected)status.textContent=reason.message;});
 }

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
   for(const draft of group.drafts){
    node('strong',draft.name,drafts);
    node('p',draft.missing?'机器人暂时无法访问':draft.changed_since_publish&&draft.active_template_id?'草稿待发布':'已关联发布版本',drafts,'mx-rel-note');
    if(!draft.missing)link('编辑设计稿 ↗',platform+'/collector/open/maxun?robot='+draft.id,drafts);
    if(!draft.missing&&draft.changed_since_publish&&draft.active_template_id)releaseLink(draft.active_template_id,draft.id,drafts);
   }
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
  const current=location.pathname.replace(/\/$/,'');
  const edit=editPath.exec(current);
  if(edit){mountDraftMaintenance(edit[1]);return;}
  if(returningDraft){
   const id=returningDraft;
   returningDraft='';
   if(current==='/robots'){location.replace('/robots/'+id+'/edit?draftSaved=1');return;}
  }
  if(current!=='/robots')return;
  const toolbar=document.querySelector('[data-crawler-robot-toolbar]');if(!toolbar)return;
  native=toolbar.parentElement;native.dataset.crawlerRobotNative='';
  if(!document.getElementById('crawler-maxun-relations')){const root=node('section');root.id='crawler-maxun-relations';native.parentElement.insertBefore(root,native);render();refresh()}
  if(lastPath!==location.href){lastPath=location.href;render()}
 }
 let pending=false;const observer=new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;mount()})}});
 function start(){mount();observer.observe(document.body,{childList:true,subtree:true});setInterval(mount,1200)}
 document.addEventListener('visibilitychange',()=>{if(document.hidden)return;
  if(location.pathname.replace(/\/$/,'')==='/robots')refresh();
  else document.querySelector('.mx-draft-maintenance')?.dispatchEvent(new Event('crawler-draft-visible'));
 });
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
