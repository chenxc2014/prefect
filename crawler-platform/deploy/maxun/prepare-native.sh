#!/usr/bin/env bash
# 后端镜像已验证后，使用独立原生实例避免重复下载大型浏览器运行环境。
set -euo pipefail
cd /opt/crawler-dev/maxun
python3.12 install.py
python3.12 native-services.py
python3.12 - <<'PY'
import json,hashlib,subprocess
from pathlib import Path
image='getmaxun/maxun-backend:v0.1.0'
obj=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
config_digest='48e570aa002717dbb2100d4c724aee44b6b333221702d71ec4aaaa0acb265596'
source=next(Path('oci').rglob(config_digest))
assert hashlib.sha256(source.read_bytes()).hexdigest()==config_digest,'官方配置内容摘要不符'
expected=json.loads(source.read_bytes())
assert obj['RootFS']['Layers']==expected['rootfs']['diff_ids'],'导入后的文件系统层与官方镜像不同'
for key in ('Cmd','Entrypoint','Env','WorkingDir','User'):
    actual=obj['Config'].get(key);original=expected['config'].get(key)
    assert (actual or None)==(original or None),'导入后的运行配置不同：'+key
Path('images.lock.json').write_text(json.dumps({image:dict(id=obj['Id'],source_manifest='sha256:d10a2feab531205ddacd9b253c85f8dee3d7409d10e322879bbd1037ef12c189',source_config=config_digest,filesystem_layers_verified=True,runtime_config_verified=True)},indent=2))
Path('compose.resolved.yaml').write_text('''name: crawler-maxun
services:
  backend:
    image: '''+obj['Id']+'''
    pull_policy: never
    restart: unless-stopped
    env_file: .env
    ports: ['127.0.0.1:18080:8080']
    environment:
      CI: 'true'
      CONTAINER: 'true'
    mem_limit: 5g
    extra_hosts: ['host.docker.internal:host-gateway']
''')
PY
echo '独立原生实例与固定摘要后端配置已准备'
