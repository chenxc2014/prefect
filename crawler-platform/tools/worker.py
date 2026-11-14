"""从本机受限配置加载 Worker 环境，不把凭据放在命令行。"""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    os.environ.update(config['env'])
    os.environ['PYTHONUTF8'] = '1'
    command = [sys.executable, '-m', 'prefect', 'worker', 'start', '--pool', config['pool'],
               '--work-queue', config['queue'], '--name', config['node'], '--limit', str(config['limit'])]
    if config.get('log_path'):
        with Path(config['log_path']).open('a', encoding='utf-8', buffering=1) as log:
            code = subprocess.call(command, cwd=config['release_root'], stdout=log, stderr=subprocess.STDOUT)
    else:
        code = subprocess.call(command, cwd=config['release_root'])
    raise SystemExit(code)


if __name__ == '__main__':
    main()
