"""检查已发布 Maxun 任务能否使用最新设计稿重新发布。"""
from collections import Counter
from copy import deepcopy
import re


def preview_duplicate(workflow, target):
    """复制 API 会将进入页面后的连续规则改为目标网址，预检按相同规则定位控件。"""
    workflow = deepcopy(workflow)
    entry = next((pair for pair in reversed(workflow) if pair.get('where', {}).get('url') == 'about:blank'), {})
    url = next((action['args'][0] for action in entry.get('what', []) if action['action'] == 'goto' and action.get('args')), None)
    if url and url != target:
        for pair in reversed(workflow):
            where = pair.get('where', {})
            if where.get('url') == 'about:blank':
                continue
            if where.get('url') != url:
                break
            where['url'] = target
    return workflow


def steps(workflow):
    return {(i, j): (pair.get('where', {}), action)
            for i, pair in enumerate(workflow) for j, action in enumerate(pair.get('what', []))}


def selector(action):
    args = action.get('args', [])
    if action.get('action') == 'platformSubmitLogin':
        return args[0].get('submitSelector') if args and isinstance(args[0], dict) else None
    return args[0] if args and isinstance(args[0], str) else None


def matches(old, new, old_where, new_where):
    kind = old['action']
    allowed = {
        'type': ('type',),
        'platformInputDate': ('type', 'platformInputDate'),
        'platformCaptcha': ('type', 'platformCaptcha'),
        'platformSubmitLogin': ('click', 'platformSubmitLogin'),
        'platformDownload': ('click', 'platformDownload'),
    }
    if kind not in allowed:
        return old_where == new_where and old == new
    target = selector(old)
    if not target or target != selector(new) or new['action'] not in allowed[kind]:
        return False
    if old_where.get('url') is None or old_where['url'] != new_where.get('url'):
        return False
    if kind == 'platformInputDate':
        old_calendar = old.get('args', [])[2:3]
        new_calendar = new.get('args', [])[2:3] if new['action'] == kind else []
        # 通用录制会把 HTML 输入类型放在第三项，只有老百姓日历使用专用适配。
        return ('lbx-delivery' in old_calendar) == ('lbx-delivery' in new_calendar)
    if kind in ('platformSubmitLogin', 'platformCaptcha', 'platformDownload') and new['action'] == kind:
        return old['args'] == new.get('args')
    if kind == 'type':
        return old['args'][2:] == new.get('args', [])[2:]
    return True


def prepare(document, frozen, draft):
    """从已发布流程定位受保护的动作，再在草稿中查找唯一的实际步骤。"""
    original = steps(frozen)
    updated = deepcopy(draft)
    candidates = steps(updated)
    required = {}
    issues = []
    bindings = {'bindings': {}, 'secret_bindings': {}}
    labels = {'begindate': '开始日期', 'enddate': '结束日期', 'username': '账号', 'password': '密码'}
    for section in bindings:
        for name, paths in document.get(section, {}).items():
            bindings[section][name] = []
            for path in paths:
                position = tuple(map(int, re.fullmatch(r'workflow\.(\d+)\.what\.(\d+)\.args\.1', path).groups()))
                required.setdefault(position, []).append((section, name))

    action_labels = {
        'platformCaptcha': '验证码输入', 'platformSubmitLogin': '登录提交', 'platformDownload': '文件下载',
        'platformLbxPrepare': '老百姓工作台准备', 'platformLbxExport': '老百姓配送数据导出',
        'platformInputDate': '日期输入',
    }
    for position, (_, action) in original.items():
        if action['action'].startswith('platform'):
            required.setdefault(position, [])
    used = set()
    position_map = {}
    for position, parameters in sorted(required.items()):
        where, action = original[position]
        kind = action['action']
        label = '、'.join(labels.get(name, name) for _, name in parameters) or action_labels.get(kind, kind)
        possible = [index for index, (condition, step) in candidates.items() if matches(action, step, where, condition)]
        if len(possible) != 1 or possible[0] in used:
            issues.append(f'{label}：{("录制中有多个匹配步骤" if possible else "录制中找不到原步骤")}，请核对页面、控件和录制顺序。')
            continue
        index = possible[0]
        _, current = candidates[index]
        args = current.get('args', [])
        if parameters and (kind not in ('type', 'platformInputDate') or len(args) < 2):
            issues.append(f'{label}：匹配的步骤无法输入运行参数。')
            continue
        i, j = index
        used.add(index)
        position_map[position] = index
        if kind in ('platformCaptcha', 'platformSubmitLogin', 'platformDownload'):
            updated[i]['what'][j] = deepcopy(action)
        elif kind == 'platformInputDate':
            updated[i]['what'][j] = {'action': kind, 'args': args[:2] + action['args'][2:]}
        for section, name in parameters:
            bindings[section][name].append(f'workflow.{i}.what.{j}.args.1')

    if list(position_map.values()) != sorted(position_map.values()):
        issues.append('登录、取数或参数输入步骤的相对顺序发生变化，请恢复正确顺序后重新检查。')
    for position, (_, action) in candidates.items():
        if position not in used and action['action'] == 'type' and 'password' in action.get('args', [])[2:]:
            issues.append('录制中含未绑定的密码输入步骤，请把账号凭据配置到秘密绑定。')
            break
    return updated, bindings, issues


def summarize(frozen, updated):
    def counts(workflow):
        return Counter(action['action'] for _, action in steps(workflow).values())
    before, after = counts(frozen), counts(updated)
    return {'before': sum(before.values()), 'after': sum(after.values()),
            'actions': [{'name': name, 'before': before[name], 'after': after[name]}
                        for name in sorted(before.keys() | after.keys()) if before[name] != after[name]]}
