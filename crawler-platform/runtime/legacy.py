"""旧类式入口适配：保留原构造参数和 run/finish 链路，默认禁止生产接管。"""
import importlib
import json
import os
from pathlib import Path
import sys


def run(request_file):
    request = json.loads(Path(request_file).read_text(encoding='utf-8-sig'))
    if request.get('isolation_verified') is not True:
        raise RuntimeError('旧爬虫尚未通过路径隔离预检，禁止执行')
    root = Path(request['source_root']).resolve()
    if not root.is_dir():
        raise RuntimeError('旧爬虫源码目录不存在')
    sys.path.insert(0, str(root))
    os.chdir(root)
    module = importlib.import_module(request['module'])
    factory = getattr(module, request['class'])
    values = request['constructor']
    expected = {'username', 'password', 'begindate', 'enddate', 'data', 'getFlowB', 'browser', 'need_login'}
    if set(values) - expected:
        raise ValueError('构造参数不符合旧项目约定')
    instance = factory(**values)
    try:
        # 与现有 FetchresultBatch.batch_finish 的入口及有限重试语义保持一致。
        result = -1
        for attempt in range(3):
            result = instance.run(0, result, None)
            if result in (0, 1, 2002) or (attempt == 1 and result == 10):
                break
        instance.finish()
        if result not in request['success_codes']:
            raise RuntimeError('旧爬虫未确认业务成功，结果码=' + str(result))
        # 成功码与原下载检查、上传/入库回执需逐站确认，不能统一猜测。
        return {'legacy_result': result}
    finally:
        browser = getattr(instance, 'browser', None)
        if browser is not None:
            browser.quit()


if __name__ == '__main__':
    run(sys.argv[1])
