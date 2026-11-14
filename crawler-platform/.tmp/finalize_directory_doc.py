"""同步目录导航与核验脚本中的章节数量。"""
from pathlib import Path

path = Path('doc/爬虫任务编排与执行平台.html')
text = path.read_text(encoding='utf-8')
text = text.replace('<a href="#environments">03-A 工作区与两台服务器的关系</a>', '<a href="#environments">03-A 工作区与两台服务器的关系</a><a href="#deployment-directories">03-B 三环境部署与目录说明</a>')
text = text.replace('补充三环境关系与中文界面，生产接管尚未启用', '补充三环境关系、实际部署目录与中文界面，生产接管尚未启用')
path.write_text(text, encoding='utf-8')
check = Path('.tmp/verify_plan.py')
text = check.read_text(encoding='utf-8').replace('assert p.sections == 20', 'assert p.sections == 22')
check.write_text(text, encoding='utf-8')
