"""记录本次 Maxun 平台扩展版本，官方基础版本保持不变。"""
from pathlib import Path
import hashlib
import json
file=Path('framework.lock.json');data=json.loads(file.read_text(encoding='utf-8'))
data['online_engine']['platform_extensions']={'version':'2026.11.18','recorder':'deploy/maxun/recorder-compat.cjs','browser_actions':'deploy/maxun/browser-actions.cjs','backend_overlay':'deploy/maxun/patch-installed.py','workflow_adapter':'runtime/maxun.py','recording_timeout_minutes':30,'business_acceptance':'doc/千金商品流向Maxun验收.json','scheduled_collection_enabled':False,'keystroke_values_logged':False,'sha256':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in ['deploy/maxun/recorder-compat.cjs','deploy/maxun/browser-actions.cjs','deploy/maxun/patch-installed.py','runtime/maxun.py']}}
file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
