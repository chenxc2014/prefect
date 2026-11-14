"""调整文档名称及引用，明确编排平台与爬虫框架的边界。"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
old_name = '网爬程序框架.html'
new_name = '爬虫任务编排与执行平台.html'
source = root / 'doc' / old_name
target = root / 'doc' / new_name
assert source.exists() and not target.exists()
source.rename(target)

for folder in ('doc', '.tmp'):
    for path in (root / folder).rglob('*'):
        if path == Path(__file__).resolve() or path.suffix not in {'.html', '.py', '.js', '.cjs'}:
            continue
        text = path.read_text(encoding='utf-8')
        if old_name in text:
            path.write_text(text.replace(old_name, new_name), encoding='utf-8')

text = target.read_text(encoding='utf-8')
text = text.replace('<title>网爬程序框架｜实施与部署方案</title>', '<title>爬虫任务编排与执行平台｜实施与部署方案</title>')
text = text.replace('<h1>网爬程序框架</h1>', '<h1>爬虫任务编排与执行平台</h1>')
text = text.replace('网爬程序框架 · 实施与部署方案', '爬虫任务编排与执行平台 · 实施与部署方案')
text = text.replace('基于 Prefect 的网爬平台实施部署方案：', '基于 Prefect 的爬虫任务编排与执行平台实施部署方案：')
marker = '<h1>爬虫任务编排与执行平台</h1>'
text = text.replace(marker, marker + '\n<p class="lead"><strong>平台定位：</strong>以 Prefect 工作流编排为底座，提供任务调度、分配、并发控制与运行监控。当前已完成基础环境与模拟任务验证；真实爬虫框架适配、网站采集及自动分析与代码生成仍待建设。</p>')
target.write_text(text, encoding='utf-8')
print(str(target))
