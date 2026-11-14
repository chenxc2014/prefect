"""独立注册业务模板执行部署，保留原有 probe 部署。"""
import json
import os
from pathlib import Path
import sys

if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    os.environ.update(config['env'])
    sys.path.insert(0, config['release_root'])
    from prefect import flow
    loaded = flow.from_source(source=config['release_root'], entrypoint='flows/collect.py:collect')
    loaded.deploy(name=config['deployment'], work_pool_name=config['pool'], work_queue_name=config['queue'], build=False, push=False,
                  parameters={'required_os': config['os'], 'template_id': ''})
