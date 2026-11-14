"""独立采集管理 API，复用现有开发认证，不改变 Prefect 服务。"""
import json
import os
from pathlib import Path
import secrets
from urllib.request import Request, urlopen
from fastapi import Depends, FastAPI, HTTPException, Request as WebRequest
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from runtime.catalog import Catalog, materialize

ROOT = Path(__file__).resolve().parents[1]
config = json.loads(Path(os.environ.get('CRAWLER_CLIENT_CONFIG', '/etc/crawler-dev/client.json')).read_text(encoding='utf-8-sig'))
os.environ.update(config['env'])
catalog = Catalog(os.environ.get('CRAWLER_CATALOG_ROOT', '/var/lib/crawler-dev/catalog'))
app = FastAPI(docs_url=None, redoc_url=None)
security = HTTPBasic()
MAXUN_DESIGNER_URL = os.environ.get('CRAWLER_MAXUN_DESIGNER_URL', 'https://192.168.1.169:9443/')


def authenticate(request: WebRequest, credentials: HTTPBasicCredentials = Depends(security)):
    actual = (credentials.username + ':' + credentials.password).encode()
    if not secrets.compare_digest(actual, config['env']['PREFECT_API_AUTH_STRING'].encode()):
        raise HTTPException(401, '认证失败', headers={'WWW-Authenticate': 'Basic'})
    if request.method != 'GET' and request.headers.get('origin'):
        from urllib.parse import urlparse
        if urlparse(request.headers['origin']).netloc != request.headers.get('host'):
            raise HTTPException(403, '请求来源不匹配')


@app.get('/', dependencies=[Depends(authenticate)])
def home():
    return HTMLResponse((ROOT / 'deploy/web/collector.html').read_text(encoding='utf-8'))


@app.get('/api/templates', dependencies=[Depends(authenticate)])
def templates():
    return catalog.list()


@app.post('/api/templates', dependencies=[Depends(authenticate)])
def publish(document: dict):
    try:
        return {'id': catalog.publish(document)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise HTTPException(400, str(error))


@app.get('/api/templates/{identifier}', dependencies=[Depends(authenticate)])
def template(identifier: str):
    try:
        return catalog.get(identifier)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, '模板版本不存在')


@app.post('/api/templates/{identifier}/runs', dependencies=[Depends(authenticate)])
async def run(identifier: str, parameters: dict):
    from prefect.client.orchestration import get_client
    parameters = dict(parameters)
    account_ref = parameters.pop('account_ref', '')
    try:
        document = catalog.get(identifier)
        materialize(document, parameters)
    except (ValueError, KeyError, FileNotFoundError, IndexError) as error:
        raise HTTPException(400, str(error))
    async with get_client() as client:
        deployment = await client.read_deployment_by_name('website-collect/' + document['node'])
        if document.get('secret_bindings') and not account_ref:
            raise HTTPException(400, '此模板需要账号引用')
        result = await client.create_flow_run_from_deployment(deployment.id, parameters={'template_id': identifier, 'parameters': parameters, 'account_ref': account_ref})
        return {'id': str(result.id), 'url': '/v2/runs/flow-run/' + str(result.id)}


@app.get('/api/runs/{identifier}', dependencies=[Depends(authenticate)])
async def status(identifier: str):
    from prefect.client.orchestration import get_client
    from uuid import UUID
    async with get_client() as client:
        result = await client.read_flow_run(UUID(identifier))
        artifact_file = catalog.root / 'results' / identifier / 'manifest.json'
        artifacts = json.loads(artifact_file.read_text()) if artifact_file.exists() else []
        return {'id': identifier, 'state': result.state.type.value, 'message': result.state.message, 'artifacts': artifacts}


@app.post('/api/results/{identifier}', dependencies=[Depends(authenticate)])
def save_results(identifier: str, payload: dict):
    import base64
    import hashlib
    from uuid import UUID
    identifier = str(UUID(identifier))
    files = payload.get('files', [])
    if len(files) > 30:
        raise HTTPException(400, '产物数量超过上限')
    destination = catalog.root / 'results' / identifier
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    total = 0
    for index, item in enumerate(files):
        content = base64.b64decode(item['content'], validate=True)
        total += len(content)
        if total > 10*1024*1024:
            raise HTTPException(413, '当前开发入口单次归档上限10MB')
        digest = hashlib.sha256(content).hexdigest()
        if digest != item['sha256']:
            raise HTTPException(400, '产物校验失败')
        (destination / str(index)).write_bytes(content)
        manifest.append({'name': Path(item['name']).name, 'sha256': digest, 'size': len(content), 'url': '/collector/api/results/' + identifier + '/' + str(index)})
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    return manifest


@app.get('/api/results/{identifier}/{index}', dependencies=[Depends(authenticate)])
def download(identifier: str, index: int):
    from uuid import UUID
    directory = catalog.root / 'results' / str(UUID(identifier))
    try:
        manifest = json.loads((directory / 'manifest.json').read_text())
        if index < 0:
            raise IndexError()
        return FileResponse(directory / str(index), filename=manifest[index]['name'], media_type='application/octet-stream')
    except (FileNotFoundError, IndexError):
        raise HTTPException(404, '产物不存在')


@app.get('/designer', dependencies=[Depends(authenticate)])
def designer():
    # 入口固定使用部署地址，避免堡垒机或本地转发域名被拼成错误的 9443 地址。
    return RedirectResponse(MAXUN_DESIGNER_URL, status_code=307)


@app.get('/api/platform', dependencies=[Depends(authenticate)])
async def platform_info():
    import asyncio
    from datetime import datetime, timezone
    from prefect.client.orchestration import get_client

    def maxun_health():
        try:
            private = Path(os.environ.get('CRAWLER_MAXUN_CONFIG', '/etc/crawler-dev/maxun.json'))
            backend = json.loads(private.read_text())['base_url'].rstrip('/')
            for url in (backend + '/', 'http://172.17.0.1:13002/health'):
                with urlopen(url, timeout=3) as response:
                    if response.status != 200:
                        return 'unavailable'
            return 'ready'
        except (OSError, ValueError, KeyError):
            return 'unavailable'

    async def prefect_health():
        try:
            async with get_client() as client:
                error = await asyncio.wait_for(client.api_healthcheck(), timeout=4)
            return 'ready' if error is None else 'unavailable'
        except Exception:
            return 'unavailable'

    maxun_state, prefect_state = await asyncio.gather(asyncio.to_thread(maxun_health), prefect_health())
    return {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'prefect': {'state': prefect_state, 'url': '/v2/'},
        'engines': {
            'maxun': {'state': maxun_state, 'designer_url': MAXUN_DESIGNER_URL, 'mode': 'web'},
            'easyspider': {'state': 'configured' if Path(os.environ.get('CRAWLER_ENGINE_CONFIG', '/etc/crawler-dev/easyspider.json')).is_file() else 'unavailable', 'mode': 'desktop'},
            'legacy': {'state': 'adapter_only', 'mode': 'python'},
        },
        # 不探测 Windows 167；本页展示的状态不代表该节点的健康情况。
        'windows_node': 'not_checked',
    }


@app.get('/api/maxun/robots', dependencies=[Depends(authenticate)])
def maxun_robots():
    from runtime.maxun import MaxunClient
    try:
        robots=MaxunClient().request('/api/sdk/robots')['data']
    except (FileNotFoundError,RuntimeError,OSError):
        raise HTTPException(503,'在线设计服务尚未就绪，请稍后重试')
    result=[]
    for robot in robots:
        meta=robot['recording_meta']
        if meta.get('type')!='extract' or meta.get('isLLM') or meta['name'].startswith(('平台执行 ·','平台发布 ·')):continue
        inputs=[]
        for i,pair in enumerate(robot['recording']['workflow']):
            for j,action in enumerate(pair.get('what',[])):
                if action.get('action')=='type' and len(action.get('args',[]))>1:
                    inputs.append({'path':f'workflow.{i}.what.{j}.args.1','label':'输入步骤 '+str(len(inputs)+1),'selector':str(action['args'][0])})
        result.append({'id':meta['id'],'name':meta['name'],'inputs':inputs})
    return result


@app.post('/api/maxun/publish', dependencies=[Depends(authenticate)])
def maxun_publish(payload: dict):
    from runtime.maxun import MaxunClient,fingerprint,bind_inputs
    from uuid import uuid4
    try:
        client=MaxunClient()
        robot=client.robot(payload['robot_id'])
        meta=robot['recording_meta']
        if meta.get('type')!='extract' or meta.get('isLLM'):raise ValueError('首期仅支持通过录制模式保存的提取机器人')
        bindings=payload.get('bindings',{})
        defaults=payload.get('defaults',{})
        bind_inputs(robot,bindings,{k:defaults.get(k,'') for k in bindings},client)
        name=str(payload.get('name') or meta['name']).strip()
        if not name or len(name)>150:raise ValueError('模板名称无效')
        checks=payload.get('checks') or {'required_files':['Data/result.csv'],'min_rows':1,'required_columns':[]}
        # 先验证公开配置，再创建发布副本；录制草稿后续修改不会影响已发布版本。
        from runtime.catalog import validate
        document={'engine':'maxun','node':'linux-169','name':name+'（Maxun）','task':{'robot_id':meta['id'],'workflow_sha256':fingerprint(robot)},'bindings':bindings,'defaults':defaults,'checks':checks}
        validate(document)
        frozen=client.duplicate(robot,'平台发布 · '+name+' · '+str(uuid4())[:8])
        workflow=frozen['recording']['workflow']
        import re
        for path in payload.get('captcha_paths',[]):
            match=re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)\.args\.1',path)
            if not match:raise ValueError('验证码步骤必须选自录制的输入框')
            i,j=map(int,match.groups());action=workflow[i]['what'][j]
            if action['action']!='type':raise ValueError('验证码目标不是输入步骤')
            workflow[i]['what'][j]={'action':'platformCaptcha','args':[action['args'][0]]}
        for key,paths in bindings.items():
            if key in ('begindate','enddate'):
                for path in paths:
                    i,j=map(int,re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)\.args\.1',path).groups())
                    workflow[i]['what'][j]['action']='platformInputDate'
        client.request('/api/sdk/robots/'+frozen['recording_meta']['id'],{'workflow':workflow},method='PUT')
        frozen=client.robot(frozen['recording_meta']['id'])
        document['task']={'robot_id':frozen['recording_meta']['id'],'workflow_sha256':fingerprint(frozen)}
        identifier=catalog.publish(document)
        return {'id':identifier,'engine':'maxun'}
    except (ValueError,KeyError,IndexError,TypeError) as error:
        raise HTTPException(400,str(error))
    except (FileNotFoundError,RuntimeError,OSError):
        raise HTTPException(503,'Maxun 发布未完成，请检查服务状态后重试')
