"""运行上游执行器副本，按本次实例隔离资源并核验文件。"""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from runtime.artifacts import validate_file


def execute(task, checks, directory, config):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    if os.name != 'nt':
        root.chmod(0o700)
    stage = Path(config['source']) / 'ExecuteStage'
    work = root / 'engine'
    shutil.copytree(stage, work, ignore=shutil.ignore_patterns('__pycache__', '.vscode'))
    # 只调整浏览器资源定位，保持固定版本上游原目录不变，并保存变更副本。
    script = work / 'easyspider_executestage.py'
    code = script.read_text(encoding='utf-8')
    code = code.replace('options.binary_location = "./chrome.exe"', 'options.binary_location = ' + repr(config['browser']))
    code = code.replace('driver_path = "./chromedriver.exe"', 'driver_path = ' + repr(config['driver']))
    code = code.replace('options.add_extension("XPathHelper.crx")', 'pass  # 服务执行无需设计辅助扩展')
    code = code.replace('options = webdriver.ChromeOptions()', 'options = webdriver.ChromeOptions()\n    options.add_argument("--window-size=1440,1000")')
    # 浏览器级下载行为同时覆盖跨域 iframe，避免仅主页面获得下载目录。
    code = code.replace('self.browser.execute("send_command", self.paramss)', 'self.browser.execute("send_command", self.paramss)\n        self.browser.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior":"allow", "downloadPath":path, "eventsEnabled":True})')
    # 日期控件的按键会改变日历选择，提供通用 DOM 值输入模式。
    assignment = '''            if param.get("inputMode") == "dom_value":
                self.browser.execute_script("Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(arguments[0],arguments[1]);arguments[0].dispatchEvent(new Event('input',{bubbles:true}));arguments[0].dispatchEvent(new Event('change',{bubbles:true}));arguments[0].blur();",textbox,replaced_text)
            else:
                textbox.send_keys(replaced_text)'''
    code = code.replace('            textbox.send_keys(replaced_text)', assignment)
    script.write_text(code, encoding='utf-8')
    shutil.copyfile(Path(config['source']) / 'ElectronJS/stealth.min.js', work / 'stealth.min.js')
    # 上游根据 driver_path 推导 stealth.min.js 路径，适配驱动所在目录的只读资源副本。
    code = script.read_text(encoding='utf-8').replace('with open(stealth_path,', 'with open(' + repr(str(work / 'stealth.min.js')) + ',')
    script.write_text(code, encoding='utf-8')
    (work / 'execution_instances').mkdir(exist_ok=True)
    (work / 'execution_instances/0.json').write_text(json.dumps(task, ensure_ascii=False), encoding='utf-8')
    (work / 'config.json').write_text(json.dumps({'mysql_config_path': '', 'absolute_user_data_folder': str(root / 'profile')}), encoding='utf-8')
    command = [config['python'], str(script), '--ids', '[0]', '--read_type', 'local', '--headless', '1', '--keyboard', '0', '--saved_file_name', 'result']
    env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    display = None
    process = None
    try:
        if os.name != 'nt':
            with (root / 'display').open('w') as output:
                display = subprocess.Popen(['Xvfb', '-displayfd', str(output.fileno()), '-screen', '0', '1440x1000x24'], pass_fds=(output.fileno(),), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                value = (root / 'display').read_text().strip()
                if value:
                    env['DISPLAY'] = ':' + value
                    break
                if display.poll() is not None:
                    raise RuntimeError('虚拟显示启动失败')
                time.sleep(.05)
            else:
                raise TimeoutError('虚拟显示启动超时')
        with (root / 'stdout.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
            code = process.wait(timeout=int(config.get('timeout', 300)))
        if code:
            raise RuntimeError('EasySpider 执行失败，退出码=' + str(code))
        artifacts = []
        for pattern in checks['required_files']:
            files = [p for p in work.glob(pattern) if p.is_file() and p.stat().st_size > 0]
            if not files:
                raise RuntimeError('缺少成功产物：' + pattern)
            for file in files:
                if file.suffix in ('.crdownload', '.part', '.tmp'):
                    raise RuntimeError('下载尚未完成')
                if file.suffix == '.csv':
                    with file.open(encoding='utf-8-sig', newline='') as handle:
                        rows = list(csv.DictReader(handle))
                    if len(rows) < checks.get('min_rows', 1):
                        raise RuntimeError('采集行数未达到成功条件')
                    for field in checks.get('required_columns', []):
                        if not rows or any(not row.get(field) for row in rows):
                            raise RuntimeError('关键字段缺失：' + field)
                    for field, expected in checks.get('expected_values', {}).items():
                        if not rows or any(row.get(field) != str(expected) for row in rows):
                            raise RuntimeError('字段值不符合运行参数：' + field)
                summary=validate_file(file,checks)
                artifacts.append({'path': str(file.relative_to(root)), 'size': file.stat().st_size, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), **summary})
        result = {'status': 'completed', 'directory': str(root), 'artifacts': artifacts}
        (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        if process is not None:
            if os.name == 'nt':
                if process.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if display is not None:
            display.terminate()
            display.wait(timeout=10)
        sensitive = [root/'stdout.log',work/'execution_instances/0.json',*work.rglob('*.log')]
        for log in sensitive:
            if log.exists() and config.get('redact'):
                content = log.read_text(encoding='utf-8', errors='replace')
                for secret in config['redact']:
                    if secret:
                        content = content.replace(secret, '[已隐藏]')
                log.write_text(content, encoding='utf-8')


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    execute(request['task'], request['checks'], request['directory'], request['config'])
