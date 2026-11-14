"""启用设计器诊断日志，保留原配置和用户任务。"""
import json
import shutil
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parents[1]
client = root / '.local/designer/EasySpider_windows_x64'
config = client / 'config.json'
if sys.argv[1] == 'enable':
    backup = client / 'config.before-diagnose.json'
    if not backup.exists():
        shutil.copy2(config, backup)
    data = json.loads(config.read_text(encoding='utf-8'))
    data['debug'] = True
    config.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    print('诊断日志已启用，原配置已备份')
elif sys.argv[1] == 'read':
    for name in ['info.log', 'designer.stderr.log', 'designer.stdout.log']:
        path = client / name
        if path.exists():
            print(name)
            print(path.read_text(encoding='utf-8', errors='replace')[-14000:])
