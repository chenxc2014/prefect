"""输出页面控件及框架数量，不输出账号或业务行数据。"""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
d=json.loads(Path('.local/sites/qjdyf/state.json').read_text(encoding='utf-8'))
from urllib.parse import urlsplit
for frame in d['frames']:
    url=urlsplit(frame['url'])
    frame['url']=url.scheme+'://'+url.netloc+url.path
print(json.dumps(d['frames'][1:] or d['frames'],ensure_ascii=False))
