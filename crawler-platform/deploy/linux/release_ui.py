"""部署独立前端资源版本，保留原界面目录与回退指针。"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

CONFIG = Path('/etc/crawler-dev')
RECORD = CONFIG / 'ui-release.json'


def activate(directory):
    environment = CONFIG / 'ui.env'
    environment.write_text('PREFECT_SERVER_UI_ENABLED=true\nPREFECT_SERVER_UI_STATIC_DIRECTORY=' + str(directory) + '\n')
    environment.chmod(0o640)
    subprocess.run(['chown', 'root:crawlerdev', str(environment)], check=True)
    dropins = Path('/etc/systemd/system/crawler-dev-server.service.d')
    dropins.mkdir(exist_ok=True)
    (dropins / '10-ui-assets.conf').write_text('[Service]\nEnvironmentFile=/etc/crawler-dev/ui.env\n')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'restart', 'crawler-dev-server'], check=True)


def main():
    if sys.argv[1] == '--rollback':
        record = json.loads(RECORD.read_text())
        activate(Path(record['previous']))
        print('前端资源已回退至：' + record['previous'])
        return
    archive = Path(sys.argv[1]).resolve()
    if archive.parent != Path('/opt/crawler-dev-bootstrap'):
        raise ValueError('资源包必须来自本项目上传目录')
    previous = Path('/var/lib/crawler-dev/ui')
    if RECORD.exists():
        previous = Path(json.loads(RECORD.read_text())['current'])
    release = Path('/var/lib/crawler-dev/ui-releases') / ('zh-cn-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    release.mkdir(parents=True, exist_ok=False)
    if (previous / 'v1').is_dir():
        shutil.copytree(previous / 'v1', release / 'v1')
    target = release / 'v2'
    target.mkdir()
    with tarfile.open(archive, 'r:gz') as package:
        package.extractall(target, filter='data')
    if not (target / 'index.html').is_file():
        raise RuntimeError('前端资源包缺少入口文件')
    for file in target.rglob('*'):
        if file.is_file() and file.suffix in {'.html', '.js', '.css', '.json', '.webmanifest'}:
            content = file.read_text(encoding='utf-8')
            content = content.replace('/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER', '/v2')
            file.write_text(content, encoding='utf-8')
    (target / 'UI_SERVE_BASE').write_text('v2:3.9.2:/v2')
    subprocess.run(['chown', '-R', 'crawlerdev:crawlerdev', str(release)], check=True)
    record = {'current': str(release), 'previous': str(previous), 'framework_version': '3.9.2', 'locale': 'zh-CN'}
    RECORD.write_text(json.dumps(record, indent=2))
    RECORD.chmod(0o644)
    activate(release)
    print(json.dumps(record))


if __name__ == '__main__':
    main()
