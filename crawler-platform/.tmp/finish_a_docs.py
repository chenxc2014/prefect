"""记录已通过的真实网站验收与新的使用入口。"""
from pathlib import Path
import json
file=Path('doc/爬虫任务编排与执行平台.html')
s=file.read_text(encoding='utf-8')
s=s.replace('已通过：6 项模板版本、参数边界、秘密注入与账号锁测试','已通过：9 项模板版本、参数边界、秘密注入、账号锁与文件日期校验测试')
s=s.replace('已核实原项目存在 DataDownloadHNQJNEW、DataDownloadHNQJDYFLS，并已使用测试账号登录；查询、导出和模板自动执行的最终结果以站点验收记录为准。','已核实原项目存在 DataDownloadHNQJNEW、DataDownloadHNQJDYFLS。测试账号在当前页面可用的操作是“配送记录”，已通过 169 原生 EasySpider 模板自动执行：图片验证码识别、账号引用注入、登录、关闭公告、进入商品流向 iframe、填写单日日期、查询和下载 XLSX。导出 3 条数据，日期均为 2026-11-12；与独立浏览器人工取证文件逐字段比较一致。<a href="千金商品流向自动采集.json">真实网站自动验收结果</a>。')
s=s.replace('<h3>维护与回退</h3><p>新模板不修改已发布版本。','<h3>真实网站的日常运行</h3><p>打开采集管理入口，在“千金供应商 · 商品流向（配送记录）”活动模板中填写 <code>begindate</code>、<code>enddate</code>，账号引用填写 <code>qjdyf-test</code> 后运行。首次仅按已经验收的单日范围使用。下载文件需要管理平台认证；无需再次输入网站密码。当前尚未开启定时采集。</p><p>日期控件需选择“直接设置日期值”，防止日历按键事件修改日期；执行器已统一适配浏览器级下载目录，覆盖跨域 iframe。一般网站可继续使用模拟按键模式。初次未落地文件的失败运行保留，用于追溯修复，活动模板已切换到验收通过版本。</p><h3>维护与回退</h3><p>同名同节点模板默认展示最近发布的活动版本，历史不可变版本仍可按 ID 查询。新模板不修改已发布版本。')
file.write_text(s,encoding='utf-8')
file=Path('doc/开发环境部署记录.html')
s=file.read_text(encoding='utf-8')
section='''<section><h2>A 方案：可视化采集入口与首站验收</h2><p>采集管理入口：<a href="https://192.168.1.169:8443/collector/">https://192.168.1.169:8443/collector/</a>，使用现有开发管理账号。桌面设计器启动命令：<code>powershell -File tools/start-designer.ps1</code>。</p><p>EasySpider v0.6.5 已通过独立 Python 环境接入两个 Worker；模板发布、参数绑定、账号引用、单节点账号互斥、集中归档与认证下载已实现。169 新增 crawler-dev-collector 和 crawler-dev-demo；167 新增 CrawlerDev-Demo 本机模拟站点计划任务。</p><p>已验收千金供应商系统“商品流向 / 配送记录”：2026-11-12 单日、3 条数据、日期正确，与独立浏览器取证业务数据一致。运行 ID：f71c1f20-72fd-4049-bbe6-ed011e825a10。管理页使用活动站点模板、日期参数及账号引用 qjdyf-test 发起运行；网站密码保存在受限节点配置中。</p><p>当前归档上限每次 10MB，尚未开启业务定时计划；旧生产程序仍未接管，旧函数入口和完整业务后处理尚待专项回归。此前两次站点调试失败均因文件校验未通过，保留原状态；正式使用活动版本。</p><p><a href="爬虫任务编排与执行平台.html#implementation-a">完整使用与目录说明</a> · <a href="A方案双节点验收.json">双节点验收</a> · <a href="千金商品流向自动采集.json">真实站点验收</a></p></section>'''
if 'A 方案：可视化采集入口与首站验收' not in s:s=s.replace('</body>',section+'</body>')
file.write_text(s,encoding='utf-8')
