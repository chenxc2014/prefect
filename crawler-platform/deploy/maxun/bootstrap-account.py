"""初始化开发账号及平台集成配置，不向终端输出密码或 API 密钥。"""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError

root=Path('/opt/crawler-dev/maxun')
client=json.loads(Path('/etc/crawler-dev/client.json').read_text())
username,password=client['env']['PREFECT_API_AUTH_STRING'].split(':',1)
email=username+'@crawler.local'
opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request(path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    try:
        with opener.open(Request('http://127.0.0.1:18080'+path,data=body,headers={'Content-Type':'application/json'}),timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code==400 and path=='/auth/register':return None
        raise RuntimeError('Maxun 账号初始化接口失败：'+str(error.code)) from None
request('/auth/register',{'email':email,'password':password})
request('/auth/login',{'email':email,'password':password})
current=request('/auth/api-key')
key=current.get('api_key')
if not key:key=request('/auth/generate-api-key',{})['api_key']
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line)
config={'base_url':'http://127.0.0.1:18080','api_key':key,'encryption_key':env['ENCRYPTION_KEY'],
        'email':email,'storage_public_url':'https://192.168.1.169:9443/objects','storage_internal_url':'http://172.17.0.1:19000'}
path=Path('/etc/crawler-dev/maxun.json');path.write_text(json.dumps(config));os.chmod(path,0o640)
import grp
os.chown(path,0,grp.getgrnam('crawlerdev').gr_gid)
env['CRAWLER_OCR_KEY']=key
(root/'.env').write_text(''.join(f'{k}={v}\n' for k,v in env.items()))
print('Maxun 开发账号已初始化：'+email+'；密码沿用采集管理开发账号，集成密钥仅保存在节点受限配置')
