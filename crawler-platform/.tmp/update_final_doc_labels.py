"""同步首页能力定位与最终验收数量，避免沿用早期阶段说明。"""
from pathlib import Path
p=Path('doc/爬虫任务编排与执行平台.html')
s=p.read_text(encoding='utf-8')
s=s.replace('当前已完成基础环境与模拟任务验证；真实爬虫框架适配、网站采集及自动分析与代码生成仍待建设。','当前已完成基础环境、可视化模板执行和首个真实网站验证；原爬虫全面适配、生产接管及自动分析与代码生成仍待建设。')
s=s.replace('下方是完整实施设计，其中真实业务适配、领取防重与生产接管仍待开发验证。','A 方案已进一步完成 EasySpider 双节点接入及千金商品流向真实采集，详见 <a href="#implementation-a">03-C 实施与使用</a>。原业务队列适配、领取防重与生产接管仍待开发验证。')
p.write_text(s,encoding='utf-8')
