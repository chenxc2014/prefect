"""发布实际取证的网站模板并提交单日验证，账号以引用传递。"""
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen
from urllib.error import URLError
from tools.dev_api import DevApi


def run(resume_id=None):
    api=DevApi()
    root=Path(__file__).resolve().parents[1]
    base=api.base.removesuffix('/api')+'/collector/api/'
    def request(path,data=None):
        req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':api.auth,'Content-Type':'application/json'})
        for attempt in range(3 if data is None else 1):
            try:
                with urlopen(req,context=api.context,timeout=30) as response:return json.load(response)
            except URLError:
                if data is not None or attempt==2:raise
                time.sleep(2)
    document=json.loads((root/'deploy/sites/qjdyf/template.json').read_text(encoding='utf-8'))
    if resume_id:
        from runtime.catalog import canonical
        import hashlib
        identifier=hashlib.sha256(canonical(document)).hexdigest()
        result={'id':resume_id,'url':'/v2/runs/flow-run/'+resume_id}
    else:
        document.update(purpose='business',task_name='千金商品流向')
        identifier=request('templates',document)['id']
        result=request('templates/'+identifier+'/runs',{'begindate':'2026-11-12','enddate':'2026-11-12','account_ref':'qjdyf-test'})
    (root/'doc/千金商品流向自动采集.json').write_text(json.dumps({'template_id':identifier,'run':result,'passed':None},ensure_ascii=False,indent=2),encoding='utf-8')
    print('已提交千金商品流向自动采集，运行ID：'+result['id'],flush=True)
    deadline=time.monotonic()+660
    while time.monotonic()<deadline:
        status=request('runs/'+result['id'])
        if status['state'] in ('COMPLETED','FAILED','CRASHED','CANCELLED'):break
        time.sleep(3)
    report=dict(template_id=identifier,run=result,status=status,passed=status['state']=='COMPLETED',date_range=['2026-11-12','2026-11-12'])
    (root/'doc/千金商品流向自动采集.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise RuntimeError('站点自动采集未通过，需查看受限执行日志')
