"""增加已归档文件下载入口，界面仅显示经过转义的文本。"""
from pathlib import Path
p=Path('deploy/web/collector.html')
s=p.read_text(encoding='utf-8')
s=s.replace("if(['COMPLETED','FAILED','CRASHED','CANCELLED'].includes(s.state))clearInterval(timer)", "if(['COMPLETED','FAILED','CRASHED','CANCELLED'].includes(s.state)){clearInterval(timer);for(const f of s.artifacts||[]){const link=element('a',`下载 ${f.name}（${f.size} 字节）`,box);link.href=f.url;link.style.display='block'}}")
p.write_text(s,encoding='utf-8')
