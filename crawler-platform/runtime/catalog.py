"""采集模板的不可变版本存储与参数绑定。"""
import copy
import hashlib
import json
import re
from pathlib import Path
from runtime.locks import account_lock


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


PURPOSES = {'business': '业务采集', 'demo': '模拟演示', 'acceptance': '测试验收'}


def classification(document):
    purpose = document.get('purpose')
    task_name = document.get('task_name')
    if purpose not in PURPOSES:
        raise ValueError('请选择任务用途：业务采集、模拟演示或测试验收')
    if not isinstance(task_name, str) or not task_name.strip() or len(task_name.strip()) > 150:
        raise ValueError('请填写所属任务名称（最多150字），同一业务的不同引擎请使用相同名称')
    return {'purpose': purpose, 'task_name': task_name.strip()}


def validate(document):
    if 'purpose' in document or 'task_name' in document:
        classification(document)
    if document.get('engine') == 'maxun':
        from uuid import UUID
        task=document['task']
        UUID(task['robot_id'])
        if not re.fullmatch('[a-f0-9]{64}',task['workflow_sha256']):raise ValueError('Maxun 流程校验值无效')
        if document.get('node')!='linux-169':raise ValueError('在线设计验证仅开放 Linux 169')
        for key,paths in document.get('bindings',{}).items():
            if key in ('username','password'):raise ValueError('账号密码必须使用秘密绑定')
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}',key):raise ValueError('参数名称不合法')
            if not isinstance(paths,list) or not paths or any(not re.fullmatch(r'workflow\.\d+\.what\.\d+\.args\.1',p) for p in paths):raise ValueError('Maxun 参数绑定路径无效')
        public_paths={p for paths in document.get('bindings',{}).values() for p in paths}
        for key,paths in document.get('secret_bindings',{}).items():
            if key not in ('username','password') or not isinstance(paths,list) or not paths:raise ValueError('秘密绑定只支持账号和密码')
            if any(not re.fullmatch(r'workflow\.\d+\.what\.\d+\.args\.1',p) or p in public_paths for p in paths):raise ValueError('秘密绑定路径无效或与公开参数重叠')
        if set(document.get('defaults',{}))-set(document.get('bindings',{})):raise ValueError('默认值包含未声明的公开参数')
        patterns=document.get('checks',{}).get('required_files',[])
        if not patterns or any(Path(p).is_absolute() or '..' in Path(p).parts or not p.startswith('Data/') for p in patterns):raise ValueError('必须配置运行目录内的成功产物规则')
        return document
    if document.get('engine') != 'easyspider':
        raise ValueError('当前仅接受 EasySpider 模板；旧爬虫需由管理员登记入口')
    task = document['task']
    if not isinstance(task.get('graph'), list) or not 1 <= len(task['graph']) <= 1000:
        raise ValueError('缺少 EasySpider graph 或节点数超限')
    if task.get('cloudflare', 0) or task.get('outputFormat', 'csv') not in ('csv', 'json', 'xlsx', 'txt'):
        raise ValueError('当前执行器不支持此浏览器模式或数据库直写')
    if not document.get('checks', {}).get('required_files'):
        raise ValueError('必须配置至少一个成功产物规则，不能仅按进程退出判断成功')
    for pattern in document['checks']['required_files']:
        if Path(pattern).is_absolute() or '..' in Path(pattern).parts or not pattern.startswith('Data/'):
            raise ValueError('产物规则必须位于本次运行目录')
    graph = task['graph']
    for node in graph:
        for index in node.get('sequence', []):
            if not isinstance(index, int) or index < 0 or index >= len(graph):
                raise ValueError('流程节点引用无效')
    for key in document.get('bindings', {}):
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}', key):
            raise ValueError('参数名称不合法')
    if document.get('node') not in ('linux-169', 'windows-167'):
        raise ValueError('请选择已配置执行节点')
    return document


def materialize(document, parameters):
    task = copy.deepcopy(document['task'])
    bindings = document.get('bindings', {})
    if set(parameters) - set(bindings):
        raise ValueError('包含未声明的参数')
    if document.get('engine')=='maxun':
        values=dict(document.get('defaults',{}),**parameters)
        if any(values.get(k) is None for k in bindings):raise ValueError('缺少 Maxun 运行参数')
        return dict(task,bindings=bindings,parameters=values)
    for name, destinations in bindings.items():
        value = parameters.get(name, document.get('defaults', {}).get(name))
        if value is None:
            raise ValueError('缺少参数：' + name)
        for destination in destinations:
            # 仅支持录制图中的输入文本与网址，不允许改任意执行器配置。
            match = re.fullmatch(r'graph\.(\d+)\.parameters\.(value|links|url)', destination)
            if not match:
                raise ValueError('绑定路径只允许 graph.N.parameters.value/links/url')
            index, field = int(match[1]), match[2]
            task['graph'][index]['parameters'][field] = str(value)
    return task


def bind_account(task, document, account):
    """秘密值仅在执行节点注入，不进入模板版本或 Prefect 参数。"""
    if document.get('engine')=='maxun':
        task['secret_bindings']=copy.deepcopy(document.get('secret_bindings',{}))
        task['secrets']={}
        for name in task['secret_bindings']:
            if name not in ('username','password') or not account.get(name):raise ValueError('账号配置不完整')
            task['secrets'][name]=account[name]
        return task
    for name, destinations in document.get('secret_bindings', {}).items():
        if name not in ('username', 'password') or name not in account:
            raise ValueError('账号配置不完整')
        for destination in destinations:
            match = re.fullmatch(r'graph\.(\d+)\.parameters\.value', destination)
            if not match:
                raise ValueError('秘密绑定只允许输入节点 value')
            task['graph'][int(match[1])]['parameters']['value'] = account[name]
    return task


class Catalog:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, document, expected=None):
        validate(document)
        body = canonical(document)
        identifier = hashlib.sha256(body).hexdigest()
        heads=self.root/'.heads'
        heads.mkdir(exist_ok=True)
        key=hashlib.sha256((document.get('name','')+'|'+document['node']).encode()).hexdigest()
        pointer=heads/(key+'.json')
        with account_lock(self.root, 'catalog:' + key, '同一任务正在发布，请刷新版本后重试'):
            if expected is not None and (not pointer.exists() or json.loads(pointer.read_text(encoding='utf-8'))['id'] != expected):
                raise ValueError('活动版本已更新，请返回任务重新检查并发布')
            path = self.root / (identifier + '.json')
            if not path.exists():
                temporary = self.root / (identifier + '.' + __import__('uuid').uuid4().hex + '.tmp')
                temporary.write_bytes(body)
                temporary.replace(path)
            # 同名同节点的新发布只切换活动指针，旧版本文件继续用于运行追溯。
            temporary=heads/(key+'.'+__import__('uuid').uuid4().hex+'.tmp')
            temporary.write_text(json.dumps({'id':identifier}),encoding='utf-8')
            temporary.replace(pointer)
        return identifier

    def get(self, identifier):
        if not re.fullmatch('[a-f0-9]{64}', identifier):
            raise ValueError('模板版本无效')
        return json.loads((self.root / (identifier + '.json')).read_text(encoding='utf-8'))

    def classify(self, identifier, purpose, task_name):
        """为已有版本补充用途，不修改版本内容、摘要或活动指针。"""
        self.get(identifier)
        metadata = classification({'purpose': purpose, 'task_name': task_name})
        directory = self.root / '.metadata'
        directory.mkdir(exist_ok=True)
        temporary = directory / (identifier + '.' + __import__('uuid').uuid4().hex + '.tmp')
        temporary.write_bytes(canonical(metadata))
        temporary.replace(directory / (identifier + '.json'))

    def list(self):
        heads=self.root/'.heads'
        active={json.loads(p.read_text(encoding='utf-8'))['id'] for p in heads.glob('*.json')} if heads.exists() else None
        result = []
        for path in sorted(self.root.glob('*.json')):
            if active is not None and path.stem not in active:
                continue
            document = json.loads(path.read_text(encoding='utf-8'))
            metadata_path = self.root / '.metadata' / path.name
            metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else document
            if 'purpose' in metadata or 'task_name' in metadata:
                metadata = classification(metadata)
            else:
                metadata = {'purpose': 'unclassified', 'task_name': document.get('name', '')}
            task_key = hashlib.sha256(canonical([metadata['purpose'], metadata['task_name']])).hexdigest()
            result.append(dict(id=path.stem, name=document.get('name', ''), engine=document.get('engine','easyspider'), node=document['node'], bindings=document.get('bindings', {}), defaults=document.get('defaults', {}), needs_account=bool(document.get('secret_bindings')), task_key=task_key, **metadata))
        return result
