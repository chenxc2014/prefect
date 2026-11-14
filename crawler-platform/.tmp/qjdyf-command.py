"""向独立测试会话发送有限页面操作，不接受账号密码参数。"""
from pathlib import Path
import json
import sys
command={'action':sys.argv[1]}
if command['action']=='login':
    command['captcha']=sys.argv[2]
if command['action']=='click':
    command['text']=sys.argv[2]
    if len(sys.argv)>3:
        command['frame']=int(sys.argv[3])
if command['action']=='query':
    command.update(begin=sys.argv[2],end=sys.argv[3])
if command['action']=='selector':
    command['selector']=sys.argv[2]
    if len(sys.argv)>3:
        command['frame']=int(sys.argv[3])
if command['action']=='export':
    command['text']=sys.argv[2]
if command.get('action') not in ('login','goods','click','query','stop','selector','export'):
    raise ValueError('不支持的操作')
Path('.local/sites/qjdyf/command.json').write_text(json.dumps(command),encoding='utf-8')
print('页面操作已排队')
