"""取证完成后去除页面元信息中不需要的会话查询参数。"""
from pathlib import Path
import json
from urllib.parse import urlsplit
p=Path('.local/sites/qjdyf/state.json')
d=json.loads(p.read_text(encoding='utf-8'))
for frame in d.get('frames',[]):
    url=urlsplit(frame['url'])
    frame['url']=url.scheme+'://'+url.netloc+url.path
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
