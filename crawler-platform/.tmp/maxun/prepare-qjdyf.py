"""从真实录制的节点自动整理发布参数，账号值不写入发布文档。"""
import json
from pathlib import Path
root=Path('.local/sites/qjdyf-maxun')
robots=json.loads((root/'saved-recordings.json').read_text(encoding='utf-8'))
robot=next(r for r in robots if r['recording_meta']['id']=='66af1f99-bd71-4c86-b190-8d96a7b6176d')
bindings={};secrets={};captcha=[];downloads=[];login=None
for i,pair in enumerate(robot['recording']['workflow']):
    for j,action in enumerate(pair['what']):
        args=action.get('args',[]);selector=args[0] if args and isinstance(args[0],str) else ''
        path=f'workflow.{i}.what.{j}'
        if action['action'] in ('type','platformInputDate'):
            key=next((key for part,key in [('placeholder="账号"','username'),('placeholder="密码"','password'),('#startTime','begindate'),('#endTime','enddate')] if part in selector),None)
            if key in ('username','password'):secrets.setdefault(key,[]).append(path+'.args.1')
            elif key:bindings.setdefault(key,[]).append(path+'.args.1')
            elif 'placeholder="验证码"' in selector:captcha.append(path+'.args.1')
        if action['action']=='click' and pair['where'].get('url','').endswith('/#/login'):
            login={'submit_path':path,'captchaSelector':'input[placeholder="验证码"]','imageSelector':'canvas.cursor-pointer','successUrl':'https://wx.qjdyf.cn/supplier-front-2.0/#/welcome','errorSelector':'.el-message'}
        if action['action']=='click' and '配送记录' in selector:downloads.append(path)
assert all(key in secrets for key in ('username','password')) and len(captcha)==1 and len(downloads)==1 and login
payload={'robot_id':robot['recording_meta']['id'],'name':'千金 · 商品流向','bindings':bindings,'secret_bindings':secrets,'captcha_paths':captcha,'login':login,'download_paths':downloads,'defaults':{'begindate':'2026-11-12','enddate':'2026-11-12'},'checks':{'required_files':['Data/downloads/*.xlsx'],'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间']}}
(root/'publish.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('已从真实录制生成发布配置：两个日期参数、两个账号绑定、动态验证码及原始文件下载')
