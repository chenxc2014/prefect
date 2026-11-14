#!/usr/bin/env bash
# 临时出口仅用于官方镜像下载，内容摘要和镜像 ID 均记录到锁文件。
set -euo pipefail
cd /opt/crawler-dev/maxun
export HTTPS_PROXY=http://127.0.0.1:28080 HTTP_PROXY=http://127.0.0.1:28080
export NO_PROXY=localhost,127.0.0.1
mkdir -p manifests oci
for image in getmaxun/maxun-backend:v0.1.0 getmaxun/maxun-frontend:v0.1.0 getmaxun/maxun-browser:v0.0.2 postgres:16-alpine; do
  name=${image//\//_}
  case "$image" in
    getmaxun/maxun-backend:*) digest=d10a2feab531205ddacd9b253c85f8dee3d7409d10e322879bbd1037ef12c189 ;;
    getmaxun/maxun-frontend:*) digest=0bcb1fc2491780534ce2f031ee6e46280a0565e07a8fbdb3e32642e504917bd2 ;;
    getmaxun/maxun-browser:*) digest=748446bda2b83cd7af8ef716971b32ef8e427852802520f49335e01c74ca2355 ;;
    postgres:*) digest=a2f7e20374cd8fd8ed4a588b79549e10589bea7b1686e77922f5ac741b80b8a1 ;;
  esac
  repository=${image%:*}
  if [ "$repository" = postgres ]; then repository=library/postgres; fi
  source=mirror.gcr.io/$repository@sha256:$digest
  skopeo --command-timeout 60s inspect --raw docker://$source > "manifests/$name.json"
  printf '%s  %s\n' "$digest" "manifests/$name.json" | sha256sum -c -
  if [ "$image" = getmaxun/maxun-backend:v0.1.0 ] && docker image inspect "$image" >/dev/null 2>&1; then continue; fi
  for attempt in 1 2 3 4 5; do
    if skopeo copy --override-arch amd64 --override-os linux --retry-times 3 docker://$source oci:$PWD/oci/$name:locked; then break; fi
    sleep 5
  done
  skopeo copy oci:$PWD/oci/$name:locked docker-daemon:$image
done
python3.12 install.py
python3.12 - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
images=['postgres:16-alpine','getmaxun/maxun-backend:v0.1.0','getmaxun/maxun-frontend:v0.1.0','getmaxun/maxun-browser:v0.0.2']
resolved={};compose=Path('compose.yaml').read_text()
for name in images:
    obj=json.loads(subprocess.check_output(['docker','image','inspect',name]))[0]
    manifest=Path('manifests/'+name.replace('/','_')+'.json').read_bytes()
    resolved[name]=dict(id=obj['Id'],manifest_sha256=hashlib.sha256(manifest).hexdigest())
    compose=compose.replace('image: '+name+'\n','image: '+obj['Id']+'\n    pull_policy: never\n')
Path('images.lock.json').write_text(json.dumps(resolved,indent=2))
Path('compose.resolved.yaml').write_text(compose)
PY
docker compose -f compose.resolved.yaml up -d
