"""执行固定版本的 Maxun 录制流程，复用平台的产物校验规则。"""
import base64
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit,quote
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from runtime.artifacts import validate_file
from runtime.catalog import canonical


def fingerprint(robot):
    meta=robot['recording_meta']
    return hashlib.sha256(canonical({'recording':robot['recording'], 'settings':{k:meta.get(k) for k in ('type','url','formats','isLLM','params')}})).hexdigest()


class MaxunClient:
    def __init__(self, config=None):
        self.config=config or json.loads(Path(os.environ.get('CRAWLER_MAXUN_CONFIG','/etc/crawler-dev/maxun.json')).read_text())
        self.base=self.config['base_url'].rstrip('/')

    def request(self, path, data=None, method=None):
        headers={'x-api-key':self.config['api_key'],'Content-Type':'application/json'}
        payload=json.dumps(data).encode() if data is not None else None
        try:
            with urlopen(Request(self.base+path,data=payload,headers=headers,method=method),timeout=45) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Maxun 接口请求失败（HTTP {error.code}），请查看服务端日志') from None

    def robot(self, identifier):
        return self.request('/api/sdk/robots/'+str(UUID(identifier)))['data']

    def duplicate(self, robot, name):
        meta=robot['recording_meta']
        url=meta.get('url') or next(a['args'][0] for pair in robot['recording']['workflow'] for a in pair['what'] if a['action']=='goto')
        result=self.request('/api/sdk/robots/'+meta['id']+'/duplicate',{'targetUrl':url})['data']
        identifier=result['recording_meta']['id']
        self.request('/api/sdk/robots/'+identifier,{'meta':{'name':name}},method='PUT')
        return self.robot(identifier)

    def encrypt(self,value):
        from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
        from cryptography.hazmat.primitives.padding import PKCS7
        iv=os.urandom(16);pad=PKCS7(128).padder();data=pad.update(str(value).encode())+pad.finalize()
        enc=Cipher(algorithms.AES(bytes.fromhex(self.config['encryption_key'])),modes.CBC(iv)).encryptor()
        return iv.hex()+':'+(enc.update(data)+enc.finalize()).hex()


def bind_inputs(robot, bindings, parameters, client):
    workflow=copy.deepcopy(robot['recording']['workflow'])
    for key, paths in bindings.items():
        for path in paths:
            match=re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)\.args\.1',path)
            if not match:
                raise ValueError('Maxun 参数只能绑定录制的文本输入步骤')
            i,j=map(int,match.groups());action=workflow[i]['what'][j]
            if action['action'] not in ('type','platformInputDate') or len(action['args'])<2:
                raise ValueError('参数绑定目标不是文本输入步骤')
            action['args'][1]=client.encrypt(parameters[key])
    return workflow


def storage_url(value,config):
    public=config.get('storage_public_url','https://192.168.1.169:9443/objects').rstrip('/')
    if not value.startswith(public+'/') or urlsplit(value).query or urlsplit(value).fragment:
        raise RuntimeError('Maxun 产物地址不属于已配置对象存储')
    # Maxun 的对象键已经包含 encodeURIComponent 生成的字面百分号。
    # 绕过 Nginx 直连 MinIO 时再编码一次，防止中文键被解码成另一个对象名。
    return config.get('storage_internal_url','http://172.17.0.1:19000').rstrip('/')+quote(value[len(public):],safe='/')


def execute(task, checks, directory, config=None, client=None):
    client=client or MaxunClient()
    robot=client.robot(task['robot_id'])
    if fingerprint(robot)!=task['workflow_sha256']:
        raise RuntimeError('已发布 Maxun 流程发生变化，请重新发布版本')
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=False);root.chmod(0o700)
    run_robot=client.duplicate(robot,'平台执行 · '+str(uuid4()))
    identifier=run_robot['recording_meta']['id']
    workflow=bind_inputs(run_robot,task.get('bindings',{}),task.get('parameters',{}),client)
    if task.get('secret_bindings'):
        workflow=bind_inputs({'recording':{'workflow':workflow}},task['secret_bindings'],task['secrets'],client)
    if task.get('bindings') or task.get('secret_bindings'):
        client.request('/api/sdk/robots/'+identifier,{'workflow':workflow},method='PUT')
    run_id=client.request('/api/sdk/robots/'+identifier+'/execute',{'wait':False})['data']['runId']
    deadline=time.monotonic()+int((config or {}).get('timeout',900))
    while True:
        result=client.request('/api/sdk/robots/'+identifier+'/runs/'+run_id)['data']
        state=result['status'].lower()
        if state in ('success','succeeded','completed','failed','aborted','cancelled','error'):
            break
        if time.monotonic()>deadline:
            client.request('/api/sdk/robots/'+identifier+'/runs/'+run_id+'/abort',{})
            raise TimeoutError('Maxun 任务超时，已请求停止')
        time.sleep(2)
    if state not in ('success','succeeded','completed'):
        raise RuntimeError('Maxun 运行未成功：'+state+'；运行编号 '+run_id)
    if re.search(r'Action .+ failed:',str(result.get('log') or '')):
        raise RuntimeError('Maxun 流程存在动作失败；运行编号 '+run_id)
    data=root/'Data';data.mkdir()
    serializable=result.get('serializableOutput') or {}
    (data/'result.json').write_text(json.dumps(serializable,ensure_ascii=False,indent=2),encoding='utf-8')
    lists=serializable.get('scrapeList') or serializable.get('scrape_list') or {}
    rows=lists if isinstance(lists,list) else next((v for v in lists.values() if isinstance(v,list) and v),[])
    if rows and all(isinstance(r,dict) for r in rows):
        with (data/'result.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
            writer.writeheader();writer.writerows(rows)
    binary=result.get('binaryOutput') or {}
    for index,(name,item) in enumerate(binary.items()):
        value=item.get('data') if isinstance(item,dict) else item
        if not isinstance(value,str):continue
        if value.startswith(('http://','https://')):
            internal=storage_url(value,client.config)
            with urlopen(internal,timeout=30) as response:
                content=response.read(10*1024*1024+1)
        else:
            content=base64.b64decode(value,validate=True)
        if len(content)>10*1024*1024:raise RuntimeError('产物超过开发归档上限 10MB')
        filename=Path(name).name
        if filename in ('','.', '..') or '\x00' in filename:raise ValueError('产物文件名不合法')
        downloads=data/'downloads';downloads.mkdir(exist_ok=True)
        (downloads/filename).write_bytes(content)
    artifacts=[]
    for pattern in checks['required_files']:
        files=[p for p in root.glob(pattern) if p.is_file() and p.stat().st_size]
        if not files:raise RuntimeError('缺少成功产物：'+pattern)
        for file in files:
            summary=validate_file(file,checks)
            artifacts.append(dict(path=str(file.relative_to(root)),size=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),**summary))
    return {'status':'completed','maxun_run_id':run_id,'directory':str(root),'artifacts':artifacts}
