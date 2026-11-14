"""仅替换 Maxun 静态界面的品牌色，不处理接口响应、录制网页或业务文件。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path

web = Path('/opt/crawler-dev/maxun-web')
backup = Path('/opt/crawler-dev/backups') / ('maxun-palette-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
colors = {
    '#ff00c3': '#405bf0', '#FF00C3': '#405bf0',
    '#ff66d9': '#657dff', '#FF66D9': '#657dff',
    '255, 0, 195': '64, 91, 240', '255,0,195': '64,91,240',
}
changes = []
for path in sorted(web.rglob('*')):
    if not path.is_file() or path.suffix not in ('.js', '.css'):
        continue
    if not path.resolve().is_relative_to(web.resolve()):
        raise RuntimeError('静态资源路径越界')
    before = path.read_bytes()
    text = before.decode('utf-8')
    for original, replacement in colors.items():
        text = text.replace(original, replacement)
    after = text.encode('utf-8')
    if before == after:
        continue
    backup.mkdir(parents=True, mode=0o700, exist_ok=True)
    archived = backup / path.relative_to(web)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_bytes(before)
    path.write_bytes(after)
    changes.append({'path': str(path.relative_to(web)), 'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(after).hexdigest()})
if changes:
    record = Path('/opt/crawler-dev/maxun/branding.lock.json')
    record.write_text(json.dumps({'palette': colors, 'backup': str(backup), 'changes': changes}, ensure_ascii=False, indent=2))
print('Maxun 品牌色适配完成，更新静态文件数：' + str(len(changes)))
if changes:
    print('原静态文件备份：' + str(backup))
