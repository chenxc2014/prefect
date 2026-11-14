"""每类系统独立注册固定代码目录和专用队列。"""
import json
import os
from pathlib import Path
import sys


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    os.environ.update(config['env'])
    from prefect import flow
    loaded = flow.from_source(source=config['release_root'], entrypoint='flows/probe.py:probe')
    loaded.deploy(name=config['deployment'], work_pool_name=config['pool'],
                  work_queue_name=config['queue'], build=False, push=False,
                  parameters={'required_os': config['os']})
