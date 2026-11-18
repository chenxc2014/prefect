"""模板执行编排：节点主动取固定模板版本，不通过界面传递秘密值。"""
import base64
import json
import os
from pathlib import Path
import platform
import ssl
from urllib.request import Request, urlopen
from uuid import uuid4
from prefect import flow
from runtime.catalog import materialize, canonical, bind_account
from runtime.easyspider import execute
from runtime.locks import account_lock
import hashlib


@flow(name='website-collect', retries=0)
def collect(template_id: str, parameters: dict | None = None, required_os: str = 'Linux', account_ref: str = ''):
    if platform.system() != required_os:
        raise RuntimeError('执行节点系统不匹配')
    location = os.environ.get('CRAWLER_ENGINE_CONFIG', '/etc/crawler-dev/easyspider.json' if os.name != 'nt' else 'D:/CrawlerDev/private/easyspider.json')
    context = ssl.create_default_context(cafile=os.environ['SSL_CERT_FILE'])
    headers = {'Authorization': 'Basic ' + base64.b64encode(os.environ['PREFECT_API_AUTH_STRING'].encode()).decode()}
    request = Request(os.environ['PREFECT_API_URL'].removesuffix('/api') + '/collector/api/templates/' + template_id, headers=headers)
    with urlopen(request, context=context, timeout=30) as response:
        document = json.load(response)
    if hashlib.sha256(canonical(document)).hexdigest() != template_id:
        raise RuntimeError('模板内容与固定版本不一致')
    if document.get('engine')=='maxun':
        from runtime.maxun import execute as execute_engine
        from prefect.context import get_run_context
        config={'timeout':900}
        config.update(template_id=template_id, prefect_run_id=str(get_run_context().flow_run.id))
    else:
        execute_engine=execute
        if not Path(location).exists():raise RuntimeError('该节点尚未配置 EasySpider 执行环境')
        config=json.loads(Path(location).read_text(encoding='utf-8-sig'))
    config['timeout'] = min(900,max(1,int(document.get('timeout_seconds',config.get('timeout',300)))))
    expected_node = 'windows-167' if os.name == 'nt' else 'linux-169'
    if document['node'] != expected_node:
        raise RuntimeError('模板绑定节点不匹配')
    directory = Path(os.environ['CRAWLER_RUN_ROOT']) / ('collect-' + str(uuid4()))
    if document['checks'].get('date_columns'):
        values=dict(document.get('defaults',{}),**(parameters or {}))
        document['checks']['date_range']=[values['begindate'],values['enddate']]
    task = materialize(document, parameters or {})
    if document.get('secret_bindings'):
        accounts_file = Path(location).with_name('accounts.json')
        accounts = json.loads(accounts_file.read_text(encoding='utf-8-sig'))
        if not account_ref or account_ref not in accounts:
            raise RuntimeError('请先在执行节点配置指定账号引用')
        account = accounts[account_ref]
        task = bind_account(task, document, account)
        config['redact'] = [account.get('username', ''), account.get('password', '')]
    with account_lock(os.environ['CRAWLER_RUN_ROOT'], account_ref):
        result = execute_engine(task, document['checks'], directory, config)
    from prefect.context import get_run_context
    files = []
    for artifact in result['artifacts']:
        file = directory / artifact['path']
        if sum(item['size'] for item in result['artifacts']) > 10*1024*1024:
            raise RuntimeError('当前开发归档入口上限10MB，请配置专用产物存储后重试')
        files.append({'name':file.name, 'sha256':artifact['sha256'], 'content':base64.b64encode(file.read_bytes()).decode()})
    payload = json.dumps({'files':files}).encode()
    headers['Content-Type'] = 'application/json'
    endpoint = os.environ['PREFECT_API_URL'].removesuffix('/api') + '/collector/api/results/' + str(get_run_context().flow_run.id)
    with urlopen(Request(endpoint, data=payload, headers=headers), context=context, timeout=60) as response:
        result['downloads'] = json.load(response)
    return result
