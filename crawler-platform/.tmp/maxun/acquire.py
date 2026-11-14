"""从 Docker 官方仓库校验下载镜像并生成可离线导入的归档。"""
import concurrent.futures
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time
from urllib.request import Request, urlopen

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'.local/maxun-images'
CACHE.mkdir(parents=True, exist_ok=True)
IMAGES=['getmaxun/maxun-backend:v0.1.0','getmaxun/maxun-frontend:v0.1.0','getmaxun/maxun-browser:v0.0.2','library/postgres:16-alpine','minio/minio:latest']
ACCEPT=', '.join(['application/vnd.oci.image.index.v1+json','application/vnd.docker.distribution.manifest.list.v2+json','application/vnd.oci.image.manifest.v1+json','application/vnd.docker.distribution.manifest.v2+json'])

def request(url,headers=None):
    return urlopen(Request(url,headers=headers or {}),timeout=60)

def resolve(name):
    repo,tag=name.rsplit(':',1)
    with request('https://auth.docker.io/token?service=registry.docker.io&scope=repository:'+repo+':pull') as response:
        token=json.load(response)['token']
    headers={'Authorization':'Bearer '+token,'Accept':ACCEPT}
    base='https://registry-1.docker.io/v2/'+repo
    with request(base+'/manifests/'+tag,headers) as response:
        body=response.read()
    index=json.loads(body)
    if 'manifests' in index:
        digest=next(x['digest'] for x in index['manifests'] if x.get('platform',{}).get('os')=='linux' and x.get('platform',{}).get('architecture')=='amd64')
        with request(base+'/manifests/'+digest,headers) as response:
            body=response.read()
    else:
        digest='sha256:'+hashlib.sha256(body).hexdigest()
    if 'sha256:'+hashlib.sha256(body).hexdigest()!=digest:
        raise RuntimeError('镜像清单摘要不一致')
    manifest=json.loads(body)
    return dict(name=name,digest=digest,manifest=manifest),base,headers

def blob(base,headers,item):
    target=CACHE/item['digest'].split(':')[1]
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==target.name:
        return target
    partial=target.with_suffix('.partial')
    for attempt in range(4):
        try:
            with request(base+'/blobs/'+item['digest'],headers) as response,partial.open('wb') as output:
                digest=hashlib.sha256()
                while chunk:=response.read(1024*1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest()!=target.name:
                raise RuntimeError('镜像层摘要不一致')
            partial.replace(target)
            return target
        except Exception:
            if attempt==3: raise
            time.sleep(2)

def acquire(name):
    data,base,headers=resolve(name)
    print('已校验清单：'+name+' '+data['digest'],flush=True)
    if '--probe' in sys.argv:
        return data
    manifest=data['manifest']
    config=blob(base,headers,manifest['config'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        layers=list(pool.map(lambda item:blob(base,headers,item),manifest['layers']))
    target=CACHE/(name.replace('/','_').replace(':','_')+'.tar')
    def add_bytes(archive,path,content):
        info=tarfile.TarInfo(path); info.size=len(content)
        archive.addfile(info,io.BytesIO(content))
    if not target.exists():
        with tarfile.open(target.with_suffix('.partial'),'w') as archive:
            config_name=config.name+'.json'
            archive.add(config,arcname=config_name)
            config_data=json.loads(config.read_bytes())
            layer_names=[]
            for layer,diffid in zip(layers,config_data['rootfs']['diff_ids'],strict=True):
                uncompressed=CACHE/(diffid.split(':')[1]+'.layer')
                if not uncompressed.exists():
                    digest=hashlib.sha256()
                    opener=gzip.open if layer.open('rb').read(2)==b'\x1f\x8b' else open
                    with opener(layer,'rb') as source,uncompressed.open('wb') as output:
                        while chunk:=source.read(1024*1024):
                            digest.update(chunk);output.write(chunk)
                    if 'sha256:'+digest.hexdigest()!=diffid:
                        raise RuntimeError('解压层摘要不一致')
                path=diffid.split(':')[1]+'/layer.tar'
                archive.add(uncompressed,arcname=path);layer_names.append(path)
            repo_tag=name.removeprefix('library/')
            add_bytes(archive,'manifest.json',json.dumps([{'Config':config_name,'RepoTags':[repo_tag],'Layers':layer_names}]).encode())
        target.with_suffix('.partial').replace(target)
    data['archive']=str(target.relative_to(ROOT));data['archive_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    print('离线镜像已生成：'+name+' '+str(target.stat().st_size),flush=True)
    return data

records=[]
for name in IMAGES:
    records.append(acquire(name))
    (CACHE/'images.lock.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
