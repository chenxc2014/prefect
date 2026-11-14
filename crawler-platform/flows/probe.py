"""验证调度、独立进程和文件隔离，不连接生产业务。"""
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
from uuid import uuid4

from prefect import flow, get_run_logger
from prefect.context import get_run_context


def stop_tree(process):
    """只结束本次启动且仍存活的子进程树。"""
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, check=False)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


@flow(name='crawler-dev-probe', retries=0, log_prints=False)
def probe(required_os: str, hold_seconds: int = 8, timeout_seconds: int = 60,
          fail: bool = False) -> dict:
    if required_os != platform.system():
        raise RuntimeError('任务系统约束与实际执行节点不匹配')
    if not 0 <= hold_seconds <= 120 or not 1 <= timeout_seconds <= 180:
        raise ValueError('验证参数超过允许范围')
    run_id = str(uuid4())
    run_dir = Path(os.environ['CRAWLER_RUN_ROOT']) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).resolve().parents[1] / 'runtime' / 'probe.py'
    request = {'run_id': run_id, 'hold_seconds': hold_seconds, 'fail': fail,
               'flow_run_id': str(get_run_context().flow_run.id)}
    request_file = run_dir / 'request.json'
    request_file.write_text(json.dumps(request), encoding='utf-8')
    args = [sys.executable, str(script), str(run_dir)]
    get_run_logger().info('启动隔离验证，run_id=%s，系统=%s', run_id, required_os)
    with (run_dir / 'stdout.log').open('w', encoding='utf-8') as output:
        process = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT,
                                   cwd=str(run_dir), start_new_session=os.name != 'nt')
        try:
            process.wait(timeout=timeout_seconds)
            if process.returncode:
                raise RuntimeError(f'验证执行器失败，退出码={process.returncode}，run_id={run_id}')
            result = json.loads((run_dir / 'result.json').read_text(encoding='utf-8'))
            if result.get('status') != 'completed':
                raise RuntimeError('验证执行器没有确认完成')
            return result
        finally:
            stop_tree(process)
            (run_dir / 'supervisor.json').write_text(json.dumps({
                'flow_run_id': request['flow_run_id'], 'child_pid': process.pid,
                'child_returncode': process.poll(), 'child_reaped': process.poll() is not None,
            }), encoding='utf-8')
