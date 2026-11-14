"""根据公开登录页、已登录菜单及iframe实际取证生成可编辑原生任务。"""
from pathlib import Path
import json

base=json.loads(Path('deploy/examples/demo-task.json').read_text(encoding='utf-8'))
common=base['graph'][1]['parameters']
def node(number,option,title,iframe=False,**parameters):
    values=dict(common)
    values.update(iframe=iframe,wait=1,useLoop=False,xpath='',beforeJS='',afterJS='',waitElement='',waitElementTime=20,waitElementIframeIndex=0)
    values.update(parameters)
    return dict(index=number,id=number,parentId=0,type=0,option=option,title=title,sequence=[],isInLoop=False,parameters=values)
login='https://wx.qjdyf.cn/supplier-front-2.0/#/login'
graph=[node(0,0,'根节点'),node(1,1,'打开千金供应商登录页',url=login,links=login,maxWaitTime=30,cookies=''),
node(2,4,'输入账号引用',xpath='//*[@placeholder="账号"]',value='{{secret.username}}',index=0),
node(3,4,'输入密码引用',xpath='//*[@placeholder="密码"]',value='{{secret.password}}',index=0)]
captcha=dict(nodeType=0,contentType=8,relative=False,name='captcha',desc='四位图片验证码',extractType=0,relativeXPath='//canvas[contains(@class,"cursor-pointer")]',default='',beforeJS='',beforeJSWaitTime=0,JS='',JSWaitTime=0,afterJS='',afterJSWaitTime=0,downloadPic=0,iframe=False,recordASField=False)
graph.append(node(4,3,'读取验证码（原生OCR）',params=[captcha],clear=0,newLine=0,recordASField=0))
graph.append(node(5,4,'填写验证码',xpath='//*[@placeholder="验证码"]',value='Field["captcha"]',index=0))
def click(number,title,xpath,iframe=False,wait=2):
    return node(number,2,title,iframe=iframe,xpath=xpath,clickWay=0,newTab=0,maxWaitTime=20,alertHandleType=0,wait=wait)
graph.extend([click(6,'登录','//button[normalize-space(.)="登录"]',wait=4),click(7,'关闭系统公告（如有）','//*[contains(@class,"close-icon")]',wait=1),click(8,'展开商品对接','(//*[normalize-space(text())="商品对接"])[1]'),click(9,'进入商品流向','(//a[contains(@href,"goodsFlow")])[1]',wait=5),click(10,'关闭查询说明（如有）','//*[text()="我知道了"]',iframe=True,wait=1),node(11,4,'填写开始日期',iframe=True,xpath='//*[@id="startTime"]',value='{{begindate}}',index=0,waitElement='//*[@id="startTime"]',waitElementIframeIndex=1),node(12,4,'填写结束日期',iframe=True,xpath='//*[@id="endTime"]',value='{{enddate}}',index=0),click(13,'查询日期范围','(//button[contains(@class,"layui-btn-primary")])[1]',iframe=True,wait=3),click(14,'下载配送记录','//button[normalize-space(.)="配送记录"]',iframe=True,wait=10)])
graph[0]['sequence']=list(range(1,len(graph)))
graph[11]['parameters']['waitElement']=''
graph[11]['parameters']['inputMode']='dom_value'
graph[12]['parameters']['inputMode']='dom_value'
graph[14]['parameters']['wait']=60
image=dict(captcha,name='execution_evidence',contentType=7,relativeXPath='//body',recordASField=False)
graph.append(node(15,3,'保存最终执行页面',params=[image],clear=0,newLine=0,recordASField=0))
graph[0]['sequence'].append(15)
task=dict(base,name='千金供应商-商品流向',graph=graph,links=login,url=[login],outputParameters=[dict(name='captcha',type='text',recordASField=False)],quitWaitTime=5)
document=dict(engine='easyspider',name='千金供应商 · 商品流向（配送记录）',node='linux-169',task=task,bindings={'begindate':['graph.11.parameters.value'],'enddate':['graph.12.parameters.value']},defaults={'begindate':'2026-11-12','enddate':'2026-11-12'},secret_bindings={'username':['graph.2.parameters.value'],'password':['graph.3.parameters.value']},checks={'required_files':['Data/Task_0/result/files/*.xlsx'],'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间']},evidence={'login':'公开页面登录控件取证','goods':'测试账号菜单与iframe取证','reference':['DataDownloadHNQJNEW','DataDownloadHNQJDYFLS'],'checked_date':'2026-11-13'})
document['timeout_seconds']=600
directory=Path('deploy/sites/qjdyf')
directory.mkdir(parents=True,exist_ok=True)
(directory/'task.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
(directory/'template.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf-8')
