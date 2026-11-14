"""为主工作台载入共享主题资源，原有页面内容继续保留。"""
from pathlib import Path
path = Path(__file__).resolve().parents[1] / 'deploy/web/collector.html'
text = path.read_text(encoding='utf-8')
original = '<script src="auth/client.js" data-app="platform"></script>'
updated = '<link rel="stylesheet" href="auth/theme.css">' + original + '<script src="auth/theme.js" defer></script>'
if 'href="auth/theme.css"' not in text:
    assert original in text
    text = text.replace(original, updated, 1)
    path.write_text(text, encoding='utf-8', newline='\n')
print('主工作台已接入共享主题和应用切换栏')
