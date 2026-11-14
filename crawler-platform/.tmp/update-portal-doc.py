"""记录多引擎工作台改版与 Maxun 入口修复，不包含任何秘密配置。"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
portal = root / 'deploy/web/collector.html'
text = portal.read_text(encoding='utf-8')
text = text.replace('<option value="windows-167" disabled>Windows 167（当前未校验）</option>', '<option value="windows-167">Windows 167（本次未校验）</option>')
portal.write_text(text, encoding='utf-8')

fragment = '''
<div id="multi-engine-workspace" class="note">
<h3>2026-11-14 更新：多引擎采集工作台</h3>
<p>采集管理入口仍为 <a href="https://192.168.1.169:8443/collector/">https://192.168.1.169:8443/collector/</a>。首页已重构为侧栏导航、三个引擎卡片、实际服务状态、活动任务列表与架构说明；发布与运行功能分为独立工作区。</p>
<div class="table-wrap"><table><thead><tr><th>入口</th><th>设计方式与操作路径</th><th>当前边界</th></tr></thead><tbody>
<tr><td>Maxun</td><td>首页「进入 Maxun 在线设计器」→ Web 录制与保存机器人 → 回到 Maxun 工作区刷新、绑定参数并发布 → 已发布任务运行。</td><td>地址 <a href="https://192.168.1.169:9443/">https://192.168.1.169:9443/</a>。账号 crawlerdev@crawler.local，密码沿用开发管理账号，不在文档记录明文。服务可用不等于所有网站已完成业务验收。</td></tr>
<tr><td>EasySpider</td><td>首页「打开客户端启动指引」→ 开发机运行 tools/start-designer.ps1 → 客户端设计、导出 JSON → 平台导入与发布。</td><td>浏览器不能直接启动本机 exe；工作区提供启动命令和上游安装包链接。日常服务器执行不依赖本地客户端常开。</td></tr>
<tr><td>fetch-crawler</td><td>首页「查看原有爬虫接入」→ 查阅原路径、适配入口、隔离与成功检查要求 → 逐站登记、验证后再注册调度。</td><td>runtime/legacy.py 已提供适配代码，当前没有开放旧业务直接发布运行，没有接管生产队列。</td></tr>
</tbody></table></div>
<p><strong>关系：</strong>平台负责版本发布、参数与结果管理；Prefect 负责调度、队列、节点、运行状态和日志；Maxun、EasySpider、原有采集类分别执行网站操作。Maxun 与 EasySpider 模板格式独立，当前不支持自动互转。旧爬虫接入仍需逐站完成隔离与验收。</p>
<h4>Maxun 无法打开的原因与修复</h4>
<p>实际检查确认：169 的 9443 已监听，HTTPS 页面返回 200，但防火墙此前仅为 8443 配置了精确来源白名单。此次 deploy/maxun/gateway.py 将同一组来源规则应用到 9443，并同时写入运行时与持久化配置；未扩大到任意来源。首页入口改用部署配置中的固定地址，不再将当前浏览器访问主机机械拼接为 9443 地址；/collector/designer 也改为实际跳转。</p>
<p>现有允许来源为 192.168.1.74/32 和 192.168.1.167/32，8443 与 9443 一致。若堡垒机实际出口改变，应按准确来源追加两个入口的规则。内部浏览器通过 SSH 隧道及严格校验开发 CA 的代理验证；未从用户堡垒机发起连通性测试。</p>
<h4>Linux 169 的 Maxun 部署位置</h4>
<div class="table-wrap"><table><thead><tr><th>目录 / 服务</th><th>用途</th></tr></thead><tbody>
<tr><td>/opt/crawler-dev/maxun/</td><td>Maxun 部署脚本、解析后 Compose、受限环境变量与镜像补丁；backend 容器只监听本机 18080。</td></tr>
<tr><td>/opt/crawler-dev/maxun-web/</td><td>经镜像应用层摘要校验提取的 Web 静态资源，由 Nginx 9443 服务。</td></tr>
<tr><td>/opt/crawler-dev/control/maxun.conf</td><td>独立 HTTPS 入口与 API / WebSocket 代理，主配置仍为 control/nginx.conf。</td></tr>
<tr><td>/opt/crawler-dev/maxun-browser/</td><td>独立浏览器连接服务；crawler-maxun-browser 使用服务账户与已有 Chrome，监听 Docker 网桥地址。</td></tr>
<tr><td>/var/lib/pgsql/maxun-data/</td><td>独立 PostgreSQL 集群，crawler-maxun-database；不使用 Prefect 的原数据目录。</td></tr>
<tr><td>/var/lib/crawler-maxun/objects/</td><td>独立对象存储数据，crawler-maxun-storage；禁止随普通前端发布清理。</td></tr>
<tr><td>/etc/crawler-dev/maxun.json</td><td>受限集成凭据，由采集服务读取，不进入公开模板。</td></tr>
<tr><td>crawler-maxun-ocr</td><td>内部图片识别服务，业务网站适用性需逐站验证。</td></tr>
</tbody></table></div>
<p>改版前文件备份位于 <code>/opt/crawler-dev/backups/portal-20261114-231017/</code>，包含原 collector.html、collector.py、gateway.py。回退页面及采集 API 后仅重启 crawler-dev-collector；保留已修正的 9443 白名单规则和 Maxun 服务。其他发布时间的 portal-* 目录保存各次发布前文件。</p>
<p>验收记录：<a href="多引擎工作台界面验收.json">多引擎工作台界面验收</a>。本次未访问或操作 Windows 167，历史双节点验证结果仅作为历史记录；千金商品流向此前的业务验收属于 EasySpider，不代表 Maxun 已完成同站验收。</p>
</div>
'''
plan = root / 'doc/爬虫任务编排与执行平台.html'
text = plan.read_text(encoding='utf-8')
old = '<section id="implementation-a"><h2><span class="num">03-C / A 方案实施进展 · 2026-11-13</span>EasySpider 可视化采集与 Prefect 集成</h2>'
new = '<section id="implementation-a"><h2><span class="num">03-C / 采集平台实施进展 · 2026-11-14</span>多引擎采集工作台与 Prefect 集成</h2>'
if 'id="multi-engine-workspace"' not in text:
    assert old in text
    text = text.replace(old, new + fragment, 1)
text = text.replace('Docker Hub 不可达，当前没有使用 Compose 容器。', 'Prefect 继续使用原生服务；2026-11-14 新增 Maxun 后端容器及独立的数据库、浏览器和对象存储服务。')
plan.write_text(text, encoding='utf-8')

record = root / 'doc/开发环境部署记录.html'
text = record.read_text(encoding='utf-8')
if 'id="multi-engine-workspace"' not in text:
    assert '</body>' in text
    text = text.replace('</body>', '<section><h2>2026-11-14 多引擎工作台改版</h2>' + fragment + '</section></body>', 1)
record.write_text(text, encoding='utf-8')
print('页面节点选项及部署文档已更新；未写入秘密配置')
