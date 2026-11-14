"""以幂等方式创建本项目的工作池、队列并注册开发部署。"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys


async def setup(config):
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolCreate
    from prefect.exceptions import ObjectNotFound
    async with get_client() as client:
        await client.api_healthcheck()
        try:
            await client.read_work_pool(config['pool'])
        except ObjectNotFound:
            await client.create_work_pool(WorkPoolCreate(name=config['pool'], type='process'))
        try:
            await client.read_work_queue_by_name(config['queue'], work_pool_name=config['pool'])
        except ObjectNotFound:
            await client.create_work_queue(name=config['queue'], work_pool_name=config['pool'])


if __name__ == '__main__':
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    os.environ.update(config['env'])
    asyncio.run(setup(config))
    register = Path(__file__).with_name('register.py')
    subprocess.run([sys.executable, str(register), sys.argv[1]], check=True)
    print('开发工作池、队列和部署注册完成')
