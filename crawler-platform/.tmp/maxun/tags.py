"""查询官方发布镜像标签，不输出认证信息。"""
import concurrent.futures
import json
from urllib.request import urlopen

def read(name):
    with urlopen('https://hub.docker.com/v2/repositories/getmaxun/maxun-'+name+'/tags?page_size=6', timeout=25) as response:
        data=json.load(response)
    return name, [x['name'] for x in data['results']]
with concurrent.futures.ThreadPoolExecutor() as pool:
    for future in [pool.submit(read, name) for name in ['backend','frontend','browser']]:
        try:
            print(future.result())
        except Exception as e:
            print(type(e).__name__, str(e))
