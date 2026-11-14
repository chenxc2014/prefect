"""从经官方清单校验的前端应用层提取静态文件，不下载重复的 Node 基础层。"""
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

root=Path('/opt/crawler-dev/maxun')
manifest=(root/'manifests/gcr-frontend.json').read_bytes()
assert hashlib.sha256(manifest).hexdigest()=='0bcb1fc2491780534ce2f031ee6e46280a0565e07a8fbdb3e32642e504917bd2'
data=json.loads(manifest);digest=data['layers'][-1]['digest'].split(':')[1]
source=next((root/'oci').rglob(digest),None)
if source is None:
    source=root/(digest+'.web-layer')
    with urlopen('https://mirror.gcr.io/v2/getmaxun/maxun-frontend/blobs/sha256:'+digest,timeout=60) as response,source.open('wb') as output:
        while chunk:=response.read(1024*1024):output.write(chunk)
assert hashlib.sha256(source.read_bytes()).hexdigest()==digest,'前端应用层摘要不符'
target=Path('/opt/crawler-dev/maxun-web');target.mkdir(exist_ok=True);count=0
with tarfile.open(source,'r:*') as archive:
    for item in archive:
        path=Path(item.name)
        if path.parts[:2]!=('app','build') or '..' in path.parts:continue
        destination=target.joinpath(*path.parts[2:])
        if not destination.resolve().is_relative_to(target.resolve()):raise RuntimeError('前端资源路径越界')
        if item.isfile():
            destination.parent.mkdir(parents=True,exist_ok=True)
            content=archive.extractfile(item).read()
            if destination.suffix in ('.js','.html'):
                content=content.replace(b'__VITE_BACKEND_URL__',b'https://192.168.1.169:9443')
            destination.write_bytes(content);destination.chmod(0o644);count+=1
if not (target/'index.html').exists():raise RuntimeError('未找到前端 index.html')
index=target/'index.html';text=index.read_text()
language="<script>if(!localStorage.getItem('i18nextLng'))localStorage.setItem('i18nextLng','zh');</script>"
if language not in text:index.write_text(text.replace('<head>','<head>'+language,1))
(root/'web.lock.json').write_text(json.dumps({'image_manifest':hashlib.sha256(manifest).hexdigest(),'application_layer':digest,'files':count},indent=2))
print('已校验并提取在线设计器前端：'+str(count)+' 个文件')
branding = root / 'apply-branding.py'
if branding.exists():
    import runpy
    runpy.run_path(str(branding), run_name='__main__')
