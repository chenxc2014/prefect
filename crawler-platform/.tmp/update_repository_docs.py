"""同步开发仓库说明，保留官方资料作为上游依据。"""
from pathlib import Path

path = Path('doc/开发环境部署记录.html')
text = path.read_text(encoding='utf-8')
text = text.replace('<td>官方 Prefect 源码</td>', '<td>Prefect 开发仓库源码</td>')
marker = '<section><h2>源码与代码位置</h2>'
addition = '<p>当前开发仓库：<a href="https://github.com/chenxc2014/prefect.git">chenxc2014/prefect</a>；本地 <code>vendor/prefect</code> 的 <code>origin</code> 已指向该地址。<code>upstream</code> 保留为官方 <code>https://github.com/PrefectHQ/prefect.git</code>，供后续合并上游更新。现有中文定制分支和未提交修改均保留，尚未推送到远端；服务器当前运行版本继续为 3.9.2，不因仓库地址切换而自动升级。</p>'
assert marker in text
text = text.replace(marker, marker + addition)
path.write_text(text, encoding='utf-8')

path = Path('doc/爬虫任务编排与执行平台.html')
text = path.read_text(encoding='utf-8')
text = text.replace('>Prefect GitHub 仓库</a>', '>Prefect 官方上游仓库</a>')
text = text.replace('<td>维护项目源码、部署脚本、测试工具和方案文档；保存 Prefect 源码及中文 UI 定制；', '<td>维护项目源码、部署脚本、测试工具和方案文档；保存 chenxc2014/prefect 仓库源码及中文 UI 定制；')
path.write_text(text, encoding='utf-8')
print('仓库地址与部署文档已同步。')
