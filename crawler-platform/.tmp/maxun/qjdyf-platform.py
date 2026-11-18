"""只通过平台 API 发布、手动运行并下载本次站点产物；不访问 Windows。"""
import base64
import json
from pathlib import Path
import sys
from urllib.request import Request,urlopen

sys.stdout.reconfigure(encoding='utf-8')
root=Path('.local/sites/qjdyf-maxun');base='http://127.0.0.1:18843/collector/api/'
auth=json.loads(Path('.local/client.json').read_text(encoding='utf-8-sig'))['env']['PREFECT_API_AUTH_STRING']
def call(path,data=None):
    headers={'Authorization':'Basic '+base64.b64encode(auth.encode()).decode(),'Content-Type':'application/json'}
    with urlopen(Request(base+path,headers=headers,data=json.dumps(data).encode() if data is not None else None),timeout=90) as response:return json.load(response)
action=sys.argv[1]
if action=='robots':
    robots=call('maxun/robots');(root/'robots.json').write_text(json.dumps(robots,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'id':r['id'],'name':r['name'],'inputs':len(r['inputs'])} for r in robots],ensure_ascii=False))
elif action=='publish':
    payload=json.loads((root/'publish.json').read_text(encoding='utf-8-sig'));result=call('maxun/publish',payload)
    (root/'published.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
elif action=='run':
    template=json.loads((root/'published.json').read_text())['id']
    result=call('templates/'+template+'/runs',{'begindate':'2026-11-12','enddate':'2026-11-12','account_ref':'qjdyf-test'})
    (root/'run.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
elif action=='status':
    identifier=json.loads((root/'run.json').read_text())['id'];result=call('runs/'+identifier)
    (root/'run-status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
elif action=='download':
    result=json.loads((root/'run-status.json').read_text(encoding='utf-8'))
    for file in result['artifacts']:
        with urlopen(Request('http://127.0.0.1:18843'+file['url'],headers={'Authorization':'Basic '+base64.b64encode(auth.encode()).decode()}),timeout=60) as response:
            (root/Path(file['name']).name).write_bytes(response.read())
    print('本次归档产物已下载到受限取证目录')
elif action=='export-template':
    template=json.loads((root/'published.json').read_text())['id'];document=call('templates/'+template)
    account=json.loads(Path('.local/site-accounts.json').read_text(encoding='utf-8-sig'))['qjdyf-test']
    content=json.dumps(document,ensure_ascii=False,indent=2)
    if any(value and value in content for value in (account.get('username'),account.get('password'))):raise RuntimeError('模板中出现账号值，拒绝导出')
    destination=Path('deploy/sites/qjdyf-maxun');destination.mkdir(parents=True,exist_ok=True)
    (destination/'template.json').write_text(content,encoding='utf-8')
    print('已导出仅含节点绑定和机器人引用的固定模板，不包含网站账号密码')
else:raise ValueError('未知操作')
