"""在已生成手册中补充已核实的链接限制和日志修正，保持其他内容。"""
from pathlib import Path
for name in ('爬虫任务编排与执行平台.html','开发环境部署记录.html'):
    file=Path('doc')/name;text=file.read_text(encoding='utf-8')
    if 'id="qjdyf-maxun-native-links"' not in text:
        anchor='<p>详细步骤：<a href="千金商品流向Maxun操作说明.html">'
        assert anchor in text
        note='<p id="qjdyf-maxun-native-links">平台归档下载已通过。Maxun 原生结果页的中文对象链接仍有编码兼容问题，当前请从采集管理平台下载。原生录制器已移除按键值调试日志，历史受限日志仍按既有保留策略处理。</p>'
        text=text.replace(anchor,note+anchor,1)
    file.write_text(text,encoding='utf-8')
file=Path('doc/千金商品流向Maxun操作说明.html');text=file.read_text(encoding='utf-8')
if 'id="maxun-native-links"' not in text:
    text=text.replace('<h2>执行与维护边界</h2>','<h2>执行与维护边界</h2><p id="maxun-native-links">平台归档下载已通过。Maxun 原生结果页的中文对象链接仍有编码兼容问题，当前请从采集管理平台下载。原生录制器已移除按键值调试日志，历史受限日志仍按既有保留策略处理。</p>',1)
file.write_text(text,encoding='utf-8')
