from pathlib import Path
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
state=json.loads(Path('.local/sites/qjdyf-maxun/state.json').read_text(encoding='utf-8'))
text=state['frames'][0]['text']
if '嵌入页面 ·' in text:
    begin=text.index('嵌入页面 ·');print(text[max(0,begin-100):][-8000:])
else:print(text[-2200:])
