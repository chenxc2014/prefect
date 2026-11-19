"""独立采集管理 API，复用现有开发认证，不改变 Prefect 服务。"""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from fastapi import Depends, FastAPI, HTTPException, Request as WebRequest
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from runtime.catalog import Catalog, materialize, classification
from tools.portal_auth import PortalAuth

ROOT = Path(__file__).resolve().parents[1]
config = json.loads(Path(os.environ.get('CRAWLER_CLIENT_CONFIG', '/etc/crawler-dev/client.json')).read_text(encoding='utf-8-sig'))
os.environ.update(config['env'])
catalog = Catalog(os.environ.get('CRAWLER_CATALOG_ROOT', '/var/lib/crawler-dev/catalog'))
app = FastAPI(docs_url=None, redoc_url=None)
MAXUN_DESIGNER_URL = os.environ.get('CRAWLER_MAXUN_DESIGNER_URL', 'https://192.168.1.169:9443/')
portal_auth = PortalAuth(config['env']['PREFECT_API_AUTH_STRING'], catalog.root.parent / 'auth')
app.include_router(portal_auth.router)


def authenticate(request: WebRequest):
    session = portal_auth.session(request)
    if session:
        portal_auth.protect_write(request, session)
    elif not portal_auth.basic_valid(request.headers.get('authorization')):
        raise HTTPException(401, '请先登录采集管理平台')
    if request.method != 'GET' and request.headers.get('origin'):
        from urllib.parse import urlparse
        if urlparse(request.headers['origin']).netloc != request.headers.get('host'):
            raise HTTPException(403, '请求来源不匹配')


@app.get('/')
def home(request: WebRequest):
    if not portal_auth.session(request):
        return portal_auth.login_redirect()
    return portal_auth.private(HTMLResponse((ROOT / 'deploy/web/collector.html').read_text(encoding='utf-8')))


@app.get('/api/templates', dependencies=[Depends(authenticate)])
def templates():
    return catalog.list()


@app.post('/api/templates', dependencies=[Depends(authenticate)])
def publish(document: dict):
    try:
        document = dict(document, **classification(document))
        return {'id': catalog.publish(document)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise HTTPException(400, str(error))


@app.get('/api/template-status', dependencies=[Depends(authenticate)])
async def template_status():
    import asyncio
    from prefect.client.orchestration import get_client
    from runtime.task_status import read_status
    try:
        async with get_client() as client:
            return await asyncio.wait_for(read_status(client, catalog.list()), timeout=20)
    except Exception:
        raise HTTPException(503, '运行与调度状态暂时无法读取，请稍后刷新或在 Prefect 查看')


@app.get('/api/templates/{identifier}', dependencies=[Depends(authenticate)])
def template(identifier: str):
    try:
        return catalog.get(identifier)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, '模板版本不存在')


@app.get('/api/maxun/relations', dependencies=[Depends(authenticate)])
async def maxun_relations(draft: str | None = None):
    import asyncio
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowFilter
    from prefect.client.schemas.sorting import FlowRunSort
    from runtime.maxun import MaxunClient
    from runtime.maxun_relations import build_snapshot

    if draft is not None:
        import re
        from runtime.maxun import fingerprint
        from runtime.maxun_relations import MaxunRelations

        def draft_status():
            if not re.fullmatch(r'[a-f0-9-]{36}', draft):
                raise HTTPException(400, '设计稿编号无效')
            store = MaxunRelations(catalog.root / '.maxun-relations')
            versions = store.draft_versions(catalog, draft)
            if not versions:
                return {'versions': []}
            source = fingerprint(MaxunClient().robot(draft))
            return {'versions': [dict(id=info['id'], task_name=info['task_name'], name=info['name'],
                                      published_at=reference['linked_at'],
                                      changed=source != reference['source_fingerprint'])
                                 for info, reference in versions]}

        try:
            return await asyncio.wait_for(asyncio.to_thread(draft_status), timeout=20)
        except (OSError, RuntimeError, ValueError, TimeoutError):
            raise HTTPException(503, '无法读取设计稿发布状态，请稍后刷新') from None

    async def read():
        runs = []
        async with get_client() as client:
            for offset in range(0, 10000, 200):
                page = await client.read_flow_runs(flow_filter=FlowFilter(name={'any_': ['website-collect']}), sort=FlowRunSort.EXPECTED_START_TIME_DESC, limit=200, offset=offset)
                runs.extend(page)
                if len(page) < 200:
                    break
            else:
                raise RuntimeError('执行历史超过当前查询范围')
        return await asyncio.to_thread(build_snapshot, catalog, MaxunClient(), runs)
    try:
        return await asyncio.wait_for(read(), timeout=30)
    except Exception:
        raise HTTPException(503, 'Maxun 与采集任务的关联暂时无法读取，请稍后刷新')


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
    return RedirectResponse('/collector/open/maxun', status_code=303)


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
            async with asyncio.timeout(4):
                async with get_client() as client:
                    if await client.api_healthcheck() is not None:
                        return 'unavailable'
                    # /health 仅代表 HTTP 进程存活，运行记录查询才能检验数据库可用性。
                    await client.read_flow_runs(limit=1)
            return 'ready'
        except Exception:
            return 'unavailable'

    maxun_state, prefect_state = await asyncio.gather(asyncio.to_thread(maxun_health), prefect_health())
    return {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'prefect': {'state': prefect_state, 'url': '/v2/'},
        'engines': {
            'maxun': {'state': maxun_state, 'designer_url': '/collector/open/maxun', 'direct_url': MAXUN_DESIGNER_URL, 'mode': 'web'},
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
        inputs=[];clicks=[]
        for i,pair in enumerate(robot['recording']['workflow']):
            for j,action in enumerate(pair.get('what',[])):
                if action.get('action') in ('type','platformInputDate') and len(action.get('args',[]))>1:
                    inputs.append({'path':f'workflow.{i}.what.{j}.args.1','label':'输入步骤 '+str(len(inputs)+1),'selector':str(action['args'][0])})
                elif action.get('action')=='click' and action.get('args'):
                    clicks.append({'path':f'workflow.{i}.what.{j}','selector':str(action['args'][0])})
        result.append({'id':meta['id'],'name':meta['name'],'inputs':inputs,'clicks':clicks,'urls':list(dict.fromkeys(pair.get('where',{}).get('url') for pair in robot['recording']['workflow'] if isinstance(pair.get('where',{}).get('url'),str) and pair['where']['url'].startswith(('https://','http://'))))})
    return result


@app.post('/api/maxun/publish', dependencies=[Depends(authenticate)])
def maxun_publish(payload: dict):
    from runtime.maxun import MaxunClient,fingerprint,bind_inputs
    from uuid import uuid4
    try:
        metadata = classification(payload)
        client=MaxunClient()
        robot=client.robot(payload['robot_id'])
        meta=robot['recording_meta']
        if meta.get('type')!='extract' or meta.get('isLLM'):raise ValueError('首期仅支持通过录制模式保存的提取机器人')
        bindings=payload.get('bindings',{})
        secret_bindings=payload.get('secret_bindings',{})
        defaults=payload.get('defaults',{})
        bind_inputs(robot,bindings,{k:defaults.get(k,'') for k in bindings},client)
        bind_inputs(robot,secret_bindings,{k:'' for k in secret_bindings},client)
        name=str(payload.get('name') or meta['name']).strip()
        if not name or len(name)>150:raise ValueError('模板名称无效')
        checks=payload.get('checks') or {'required_files':['Data/result.csv'],'min_rows':1,'required_columns':[]}
        # 先验证公开配置，再创建发布副本；录制草稿后续修改不会影响已发布版本。
        from runtime.catalog import validate
        document={'engine':'maxun','node':'linux-169','name':name+'（Maxun）','task':{'robot_id':meta['id'],'workflow_sha256':fingerprint(robot)},'bindings':bindings,'secret_bindings':secret_bindings,'defaults':defaults,'checks':checks,**metadata}
        validate(document)
        frozen=client.duplicate(robot,'平台发布 · '+name+' · '+str(uuid4())[:8])
        workflow=frozen['recording']['workflow']
        # 发布副本清除录制时的真实账号；每次运行由节点受限配置重新加密注入。
        workflow=bind_inputs({'recording':{'workflow':workflow}},secret_bindings,{k:'' for k in secret_bindings},client)
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
        login=payload.get('login')
        if login:
            # 登录按钮来自本次真实录制，只替换该动作；错误账号与超时不会盲重试。
            match=re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)',str(login.get('submit_path','')))
            if not match:raise ValueError('登录提交步骤路径无效')
            i,j=map(int,match.groups());action=workflow[i]['what'][j]
            if action['action']!='click':raise ValueError('登录提交步骤必须是录制的点击动作')
            options={key:login[key] for key in ('captchaSelector','imageSelector','successUrl','errorSelector')}
            options.update(submitSelector=action['args'][0],attempts=3)
            workflow[i]['what'][j]={'action':'platformSubmitLogin','args':[options]}
        for path in payload.get('download_paths',[]):
            match=re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)',path)
            if not match:raise ValueError('下载步骤路径无效')
            i,j=map(int,match.groups());action=workflow[i]['what'][j]
            if action['action']!='click':raise ValueError('下载步骤必须是录制的点击动作')
            workflow[i]['what'][j]={'action':'platformDownload','args':[action['args'][0]]}
        client.request('/api/sdk/robots/'+frozen['recording_meta']['id'],{'workflow':workflow},method='PUT')
        frozen=client.robot(frozen['recording_meta']['id'])
        document['task']={'robot_id':frozen['recording_meta']['id'],'workflow_sha256':fingerprint(frozen)}
        identifier=catalog.publish(document)
        from runtime.maxun_relations import MaxunRelations
        MaxunRelations(catalog.root / '.maxun-relations').publication(identifier, meta['id'], frozen['recording_meta']['id'], fingerprint(robot))
        return {'id':identifier,'engine':'maxun'}
    except (ValueError,KeyError,IndexError,TypeError) as error:
        raise HTTPException(400,str(error))
    except (FileNotFoundError,RuntimeError,OSError):
        raise HTTPException(503,'Maxun 发布未完成，请检查服务状态后重试')


def release_candidate(identifier, draft_id, client, store):
    from runtime.maxun import duplicate_target, fingerprint
    from runtime.maxun_release import prepare, preview_duplicate, summarize

    matches = [(info, relation) for info, relation in store.draft_versions(catalog, draft_id)
               if info['id'] == identifier and info['engine'] == 'maxun']
    if not matches:
        raise HTTPException(409, '设计稿或活动版本已变更，请重新打开当前采集任务')
    info, relation = matches[0]
    document = catalog.get(identifier)
    draft = client.robot(draft_id)
    meta = draft['recording_meta']
    frozen = client.robot(document['task']['robot_id'])
    if fingerprint(frozen) != document['task']['workflow_sha256'] or relation['published_robot_id'] != frozen['recording_meta']['id']:
        raise HTTPException(409, '当前发布副本与固定版本不一致，请联系管理员核对')
    source = fingerprint(draft)
    original = frozen['recording']['workflow']
    try:
        target = duplicate_target(draft)
        prospective = preview_duplicate(draft['recording']['workflow'], target)
    except StopIteration:
        target = None
        prospective = draft['recording']['workflow']
    updated, bindings, issues = prepare(document, original, prospective)
    if not target:
        issues.append('请为设计稿保存有效的起始网址。')
    if meta.get('type') != 'extract' or meta.get('isLLM') or not updated or not any(pair.get('what') for pair in updated):
        issues.append('请保存有效的网页提取录制后再发布。')
    document.update(bindings)
    if info['purpose'] != 'unclassified':
        document.update(classification(info))
    return draft, document, original, {
        'id': identifier, 'task_name': info['task_name'], 'name': info['name'],
        'draft_name': meta['name'], 'draft_id': draft_id, 'published_at': relation['linked_at'],
        'fingerprint': source, 'changed': source != relation['source_fingerprint'],
        'settings_changed': target != frozen['recording_meta'].get('url'),
        'issues': issues, 'changes': summarize(original, updated),
        'defaults': document.get('defaults', {}), 'parameters': list(document['bindings']),
        'needs_account': bool(document['secret_bindings']), 'checks': document['checks'],
    }


@app.get('/api/maxun/releases/{identifier}', dependencies=[Depends(authenticate)])
def preview_maxun_release(identifier: str, draft: str):
    from runtime.maxun import MaxunClient
    from runtime.maxun_relations import MaxunRelations

    try:
        return release_candidate(identifier, draft, MaxunClient(), MaxunRelations(catalog.root / '.maxun-relations'))[-1]
    except (RuntimeError, OSError, ValueError, KeyError, IndexError, AttributeError, TypeError):
        raise HTTPException(503, '暂时无法检查发布配置，请刷新后重试') from None


@app.post('/api/maxun/releases/{identifier}', dependencies=[Depends(authenticate)])
def publish_maxun_release(identifier: str, payload: dict):
    import hashlib
    from uuid import uuid4
    from runtime.catalog import canonical, validate
    from runtime.maxun import MaxunClient, bind_inputs, fingerprint
    from runtime.maxun_relations import MaxunRelations
    from runtime.maxun_release import prepare

    store = MaxunRelations(catalog.root / '.maxun-relations')
    client = None
    frozen_id = None
    version_id = None
    try:
        client = MaxunClient()
        draft_id = payload['draft']
        draft, document, original, preview = release_candidate(identifier, draft_id, client, store)
        if payload.get('fingerprint') != preview['fingerprint']:
            raise HTTPException(409, '设计稿在检查后又被保存，请重新检查')
        if not preview['changed'] or preview['issues']:
            raise HTTPException(409, '设计稿暂无待发布的修改或仍有预检问题，请重新检查')
        frozen = client.duplicate(draft, '平台发布 · ' + document['name'].removesuffix('（Maxun）') + ' · ' + uuid4().hex[:8])
        frozen_id = frozen['recording_meta']['id']
        workflow, actual_bindings, issues = prepare(catalog.get(identifier), original, frozen['recording']['workflow'])
        if issues or any(actual_bindings[key] != document[key] for key in actual_bindings):
            raise HTTPException(409, 'Maxun 复制后关键步骤发生变化，请重新核对录制')
        validate(document)
        secrets = document['secret_bindings']
        workflow = bind_inputs({'recording': {'workflow': workflow}}, secrets, dict.fromkeys(secrets, ''), client)
        client.request('/api/sdk/robots/' + frozen_id, {'workflow': workflow}, method='PUT')
        frozen = client.robot(frozen_id)
        if fingerprint(client.robot(draft_id)) != preview['fingerprint']:
            raise HTTPException(409, '设计稿在发布期间又被保存，请重新检查')
        document['task'] = {'robot_id': frozen_id, 'workflow_sha256': fingerprint(frozen)}
        version_id = hashlib.sha256(canonical(document)).hexdigest()
        store.publication(version_id, draft_id, frozen_id, preview['fingerprint'])
        catalog.publish(document, expected=identifier)
        frozen_id = None
        return {'id': version_id}
    except (ValueError, KeyError, IndexError, AttributeError, TypeError) as error:
        detail = str(error) if isinstance(error, ValueError) and str(error).startswith('活动版本') else '发布配置无效，请重新检查'
        raise HTTPException(409, detail) from None
    except (RuntimeError, OSError):
        raise HTTPException(503, '新版本未完成发布，请刷新任务状态后重试') from None
    finally:
        if frozen_id:
            # 已写入版本文件时保留其副本和关联，供管理员追查未激活的版本。
            if not version_id or not (catalog.root / (version_id + '.json')).exists():
                try:
                    client.request('/api/sdk/robots/' + frozen_id, method='DELETE')
                    if version_id:
                        (store.root / 'publications' / (version_id + '.json')).unlink(missing_ok=True)
                except (RuntimeError, OSError):
                    pass


@app.get('/api/maxun/releases/{identifier}/trial-defaults', dependencies=[Depends(authenticate)])
async def maxun_trial_defaults(identifier: str):
    import asyncio
    from uuid import UUID
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowRunFilter
    from prefect.client.schemas.sorting import FlowRunSort
    from runtime.maxun_relations import MaxunRelations

    try:
        document = catalog.get(identifier)
        if document['engine'] != 'maxun':
            raise ValueError
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, 'Maxun 发布版本不存在') from None
    result = {'parameters': document.get('defaults', {}), 'account_ref': '', 'from_success': False}
    store = MaxunRelations(catalog.root / '.maxun-relations')
    references = store.records('publications')
    current = next((item for item in references if item['template_id'] == identifier), None)
    if not current:
        return result
    versions = set()
    for item in references:
        if item['source_robot_id'] == current['source_robot_id']:
            try:
                previous = catalog.get(item['template_id'])
            except FileNotFoundError:
                continue
            if (previous['name'], previous['node']) == (document['name'], document['node']):
                versions.add(item['template_id'])
    runs = {UUID(item['prefect_run_id']) for item in store.records('executions') if item['template_id'] in versions}

    async def latest():
        async with get_client() as client:
            return await client.read_flow_runs(flow_run_filter=FlowRunFilter(
                id={'any_': list(runs)}, state={'type': {'any_': ['COMPLETED']}}),
                sort=FlowRunSort.END_TIME_DESC, limit=1)

    if runs:
        try:
            recent = await asyncio.wait_for(latest(), timeout=5)
            if recent and recent[0].parameters.get('template_id') in versions:
                saved = recent[0].parameters
                result['parameters'] = dict(result['parameters'], **{
                    name: value for name, value in saved.get('parameters', {}).items() if name in document.get('bindings', {})})
                result.update(account_ref=saved.get('account_ref', ''), from_success=True)
        except Exception:
            pass
    return result
