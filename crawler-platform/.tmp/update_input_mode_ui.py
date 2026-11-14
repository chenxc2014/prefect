"""把通用日期值输入模式显示为界面选项，不要求用户编写脚本。"""
from pathlib import Path
p=Path('deploy/web/collector.html')
s=p.read_text(encoding='utf-8')
needle="input.oninput=()=>n.parameters[key]=input.value}}show('已导入"
replacement="input.oninput=()=>n.parameters[key]=input.value}if(n.option===4){const l=element('label','输入方式 ',block);const select=element('select','',l);for(const [v,t]of [['send_keys','模拟按键'],['dom_value','直接设置日期值']]){const o=element('option',t,select);o.value=v}select.value=n.parameters.inputMode||'send_keys';select.onchange=()=>n.parameters.inputMode=select.value}}show('已导入"
assert needle in s
p.write_text(s.replace(needle,replacement),encoding='utf-8')
