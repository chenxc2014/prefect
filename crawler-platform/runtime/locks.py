"""固定节点内账号互斥，操作系统锁在进程结束后自动释放。"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path


@contextmanager
def account_lock(root, reference):
    if not reference:
        yield
        return
    directory = Path(root) / '.account-locks'
    directory.mkdir(exist_ok=True)
    file = directory / (hashlib.sha256(reference.encode()).hexdigest() + '.lock')
    with file.open('a+b') as handle:
        handle.seek(0)
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('同一节点上的该账号已有任务运行，请稍后提交') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
