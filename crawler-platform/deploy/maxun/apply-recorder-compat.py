"""向固定前端的现有录制 Socket 挂接兼容面板，不创建第二个录制连接。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

web=Path('/opt/crawler-dev/maxun-web')
changes=[]
for file in web.rglob('*.js'):
    before=file.read_text()
    if 'window.CrawlerRecorderSocket=' in before:continue
    pattern=r'([\w$]+)\.on\("connect",\(\)=>console\.log\("connected to socket"\)\)'
    matches=list(re.finditer(pattern,before))
    if not matches:continue
    if len(matches)!=1:raise RuntimeError('现有录制 Socket 挂接锚点数量不符')
    after=re.sub(pattern,lambda m:m[1]+'.on("connect",()=>{window.CrawlerRecorderSocket='+m[1]+';console.log("connected to socket")})',before)
    backup=Path('/opt/crawler-dev/backups')/('maxun-recorder-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True,mode=0o700,exist_ok=True);(backup/file.name).write_text(before)
    file.write_text(after)
    changes.append({'file':str(file.relative_to(web)),'backup':str(backup),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()})
if changes:Path('/opt/crawler-dev/maxun/recorder-compat.lock.json').write_text(json.dumps(changes,indent=2))
elif not any('window.CrawlerRecorderSocket=' in p.read_text() for p in web.rglob('*.js')):raise RuntimeError('未找到已验证的录制 Socket 挂接锚点')
print('兼容录制前端已挂接，修改文件数：'+str(len(changes)))
