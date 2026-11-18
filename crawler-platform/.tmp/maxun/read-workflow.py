from pathlib import Path
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
workflow=json.loads(Path('.local/sites/qjdyf-maxun/recorded-workflow.json').read_text(encoding='utf-8'))
for i,pair in enumerate(workflow['workflow']):
    print(i,json.dumps(pair['where'],ensure_ascii=False))
    for j,action in enumerate(pair['what']):
        args=action.get('args',[])
        print(' ',j,action['action'],args[0] if args and isinstance(args[0],str) else '', '[输入密文]' if action['action'] in ('type','press','platformInputDate') else '')
