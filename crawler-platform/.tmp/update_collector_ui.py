"""在现有模板界面增加账号引用绑定，秘密值仍只保存在节点配置。"""
from pathlib import Path
p=Path('deploy/web/collector.html')
s=p.read_text(encoding='utf-8')
s=s.replace('账号秘密绑定尚未开放，请勿将真实密码写入模板或运行参数。', '账号输入节点可填写 {{secret.username}}、{{secret.password}}，执行时通过账号引用读取节点受限配置。请勿将真实密码写入模板或运行参数。')
s=s.replace('const bindings={},defaults={};', 'const bindings={},defaults={},secret_bindings={};')
s=s.replace("for(const key of ['value','links','url']){const m=", "for(const key of ['value','links','url']){const secret=String(n.parameters?.[key]||'').match(/^\\{\\{secret\\.(username|password)\\}\\}$/);if(secret&&key==='value'){(secret_bindings[secret[1]]??=[]).push(`graph.${i}.parameters.value`);continue}const m=")
s=s.replace('task,bindings,defaults,checks:', 'task,bindings,defaults,secret_bindings,checks:')
s=s.replace("const inputs={};for(const key", "const inputs={};if(t.needs_account){const l=element('label','账号引用 ',a);inputs.account_ref=element('input','',l);inputs.account_ref.placeholder='由管理员配置的账号引用'}for(const key")
p.write_text(s,encoding='utf-8')
