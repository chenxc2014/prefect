"""验证模板发布、版本绑定和真实浏览器导出，不访问生产网站。"""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from tools.dev_api import DevApi


def verify():
    api = DevApi()
    root = Path(__file__).resolve().parents[1]
    base = api.base.removesuffix('/api') + '/collector/api/'
    def request(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        req = Request(base + path, data=body, headers={'Content-Type':'application/json', 'Authorization':api.auth})
        with urlopen(req, context=api.context, timeout=30) as response:
            return json.load(response)
    document = json.loads((root / 'deploy/examples/demo-template.json').read_text(encoding='utf-8'))
    identifier = request('templates', document)['id']
    assert request('templates', document)['id'] == identifier
    run = request('templates/' + identifier + '/runs', {'begindate':'2026-11-01'})
    print('已提交真实浏览器采集验证：' + run['id'], flush=True)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        status = request('runs/' + run['id'])
        if status['state'] in ('COMPLETED','FAILED','CRASHED','CANCELLED'):
            break
        time.sleep(2)
    report = dict(template_id=identifier, run=run, status=status, passed=status['state']=='COMPLETED')
    (root / 'doc/A方案采集验证.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if not report['passed']:
        logs = api.request('/logs/filter', {'logs':{'flow_run_id':{'any_':[run['id']]}},'limit':30,'sort':'TIMESTAMP_ASC'})
        for log in logs:
            print(log['message'])
        raise RuntimeError('真实浏览器采集验证失败')


def verify_matrix():
    """双节点实际浏览器导出、参数传递、归档哈希及缺失文件故障注入。"""
    import copy
    import csv
    import hashlib
    import io
    from urllib.error import HTTPError
    api = DevApi()
    root = Path(__file__).resolve().parents[1]
    base = api.base.removesuffix('/api') + '/collector'
    def request(path, data=None, authenticated=True, raw=False):
        headers={'Content-Type':'application/json'}
        if authenticated:
            headers['Authorization']=api.auth
        req=Request(base+path, data=None if data is None else json.dumps(data).encode(),headers=headers)
        with urlopen(req,context=api.context,timeout=30) as response:
            return response.read() if raw else json.load(response)
    original=json.loads((root/'deploy/examples/demo-template.json').read_text(encoding='utf-8'))
    cases=[]
    for node, date in [('linux-169','2026-11-01'),('linux-169','2026-11-02'),('windows-167','2026-11-03')]:
        document=copy.deepcopy(original)
        document.update(node=node,name='验收：日期查询与导出 · '+node,purpose='acceptance',task_name='验收：日期查询与导出')
        identifier=request('/api/templates',document)['id']
        run=request('/api/templates/'+identifier+'/runs',{'begindate':date})
        cases.append(dict(node=node,date=date,id=run['id'],expected='COMPLETED'))
    bad=copy.deepcopy(original)
    bad.update(name='故障注入验收：缺少文件（预期失败）',purpose='acceptance',task_name='故障注入验收：缺少文件（预期失败）')
    bad['checks']['required_files']=['Data/Task_0/不存在的产物.csv']
    identifier=request('/api/templates',bad)['id']
    deployments={d['name']:d for d in api.request('/deployments/filter',{}) if d.get('entrypoint') == 'flows/collect.py:collect'}
    # 命名明确的故障记录，保留用于审计；不把失败状态改为成功。
    run=api.request('/deployments/'+deployments['linux-169']['id']+'/create_flow_run', {'name':'验收-预期失败-缺少文件','tags':['故障注入','预期失败'],'parameters':{'template_id':identifier,'parameters':{'begindate':'2026-11-04'},'required_os':'Linux'}})
    cases.append(dict(node='linux-169',id=run['id'],expected='FAILED'))
    print('已投递双节点实际浏览器验收，共4项（含1项预期失败）',flush=True)
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        for case in cases:
            case['status']=request('/api/runs/'+case['id'])
        print([case['status']['state'] for case in cases],flush=True)
        if all(c['status']['state'] in ('COMPLETED','FAILED','CRASHED','CANCELLED') for c in cases):
            break
        time.sleep(5)
    for case in cases:
        assert case['status']['state']==case['expected'],case
        if case['expected']=='COMPLETED':
            artifact=case['status']['artifacts'][0]
            data=request(artifact['url'].removeprefix('/collector'),raw=True)
            assert hashlib.sha256(data).hexdigest()==artifact['sha256']
            rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
            assert len(rows)==6 and all(row['begindate']==case['date'] for row in rows)
            try:
                request(artifact['url'].removeprefix('/collector'),authenticated=False,raw=True)
            except HTTPError as error:
                assert error.code==401
            else:
                raise AssertionError('未认证下载未被拒绝')
    report=dict(passed=True,cases=cases,checks=['双节点浏览器真实执行','日期参数与CSV字段一致','集中归档与哈希验证','未认证下载拒绝','缺失产物正确失败'])
    (root/'doc/A方案双节点验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('双节点真实采集、文件校验和故障注入均通过',flush=True)
