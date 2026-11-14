"""补充已经验收的A方案部署与操作入口，保留真实网站状态说明。"""
from pathlib import Path
import json
path=Path('framework.lock.json')
path.write_text(json.dumps(json.loads(path.read_text(encoding='utf-8')),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=Path('doc/爬虫任务编排与执行平台.html')
text=path.read_text(encoding='utf-8')
section='''<section id="implementation-a"><h2><span class="num">03-C / A 方案实施进展 · 2026-11-13</span>EasySpider 可视化采集与 Prefect 集成</h2>
<p><strong>新增采集管理入口：</strong><a href="https://192.168.1.169:8443/collector/">https://192.168.1.169:8443/collector/</a>，使用现有开发平台账号认证。原 Prefect 中文界面仍在根地址，负责查看运行状态、日志和调度。</p>
<h3>可视化新增网站的操作</h3><ol><li>在工作区执行 <code>powershell -File tools/start-designer.ps1</code>，启动官方 EasySpider v0.6.5 设计客户端。</li><li>在真实网站点选元素，配置登录、输入、点击、循环、分页和提取，保存任务 JSON；所有定位以真实页面为依据。</li><li>打开采集管理入口，导入 JSON。页面会列出流程节点，可修改 XPath、输入值或链接。使用 <code>{{begindate}}</code>、<code>{{enddate}}</code> 声明公开运行参数。</li><li>账号输入使用 <code>{{secret.username}}</code>、<code>{{secret.password}}</code>；运行时填写账号引用，秘密值只在执行节点注入。</li><li>选择 Linux 169 或 Windows 167，设置相对执行目录的产物规则（例如 <code>Data/Task_0/result/files/*.csv</code>）、最少行数和必填列，发布为 SHA-256 标识的不可变版本。</li><li>填写日期等参数并运行。成功后可在管理页下载集中归档文件；每次修改模板都生成新版本，历史版本保持不变。</li></ol>
<p>客户端实际入口：<code>.local/designer/EasySpider_windows_x64/EasySpider.exe</code>。设计器是桌面交互软件，管理页不是远程桌面录制器；复杂流程在设计器中配置后导入。不要把网页保存为 JSON 的浏览器菜单误当作导出 EasySpider 任务。</p>
<h3>已经部署的组件</h3><div class="table-wrap"><table><thead><tr><th>组件</th><th>实际位置与职责</th></tr></thead><tbody>
<tr><td>框架源码</td><td>工作区 <code>vendor/easyspider</code>，固定 v0.6.5 / 191bd6d7547bb397e4c579dd2c70ae835be3f512，保留 AGPL-3.0 许可证。上游源码不直接改写；浏览器资源定位仅在每次执行的副本中适配。</td></tr>
<tr><td>169 模板管理服务</td><td><code>crawler-dev-collector</code>，仅监听 127.0.0.1:8081；Nginx 的 /collector/ 路由提供 HTTPS 访问。代码 <code>tools/collector.py</code>，界面 <code>deploy/web/collector.html</code>。</td></tr>
<tr><td>模板与集中产物</td><td><code>/var/lib/crawler-dev/catalog</code> 保存不可变模板；<code>results/&lt;flow_run_id&gt;</code> 保存校验后的归档及清单。下载同样要求认证，当前开发版每次归档上限 10MB。</td></tr>
<tr><td>169 独立执行器</td><td><code>/opt/crawler-dev/easyspider/source</code>、<code>venv</code>、<code>requirements.lock</code>；运行配置 <code>/etc/crawler-dev/easyspider.json</code>。Chrome、匹配驱动与 Xvfb 用于 Rocky Linux 的真实浏览器执行。</td></tr>
<tr><td>167 独立执行器</td><td><code>D:\\CrawlerDev\\easyspider</code> 下 source、venv、chrome-win64、chromedriver-win64、downloads；运行配置 <code>D:\\CrawlerDev\\private\\easyspider.json</code>。使用便携 Chrome，不替换原爬虫浏览器。</td></tr>
<tr><td>账号配置</td><td>本地录入 <code>.local/site-accounts.json</code>；169 使用 <code>/etc/crawler-dev/accounts.json</code>，167 按需使用 <code>D:\\CrawlerDev\\private\\accounts.json</code>。配置受权限保护，不进入版本库、模板或 Prefect 明文参数。同节点同账号引用采用操作系统锁互斥；跨节点统一账号锁尚待补充。</td></tr>
<tr><td>编排与适配</td><td><code>flows/collect.py</code>、<code>runtime/catalog.py</code>、<code>runtime/easyspider.py</code>、<code>runtime/locks.py</code>；部署名称 <code>website-collect/linux-169</code>、<code>website-collect/windows-167</code>。</td></tr>
<tr><td>模拟业务站点</td><td>169 的 <code>crawler-dev-demo</code>、167 的 <code>CrawlerDev-Demo</code>，仅监听各自 127.0.0.1:8766，供浏览器验收，不对外开放。</td></tr>
</tbody></table></div>
<h3>验收与实际边界</h3><p>已通过：6 项模板版本、参数边界、秘密注入与账号锁测试；管理页导入、编辑、发布及运行的浏览器验收；Linux 与 Windows 实际浏览器日期查询、CSV 下载、6 行数据及日期值核对、集中归档哈希与未认证下载拒绝。另有一项明确命名的“缺少文件”故障注入按预期失败，故障记录保持真实状态。</p><p><a href="A方案双节点验收.json">双节点验收结果</a> · <a href="A方案界面验证.json">管理界面验收结果</a></p>
<div class="note warn"><strong>旧爬虫接管状态：</strong><code>runtime/legacy.py</code> 已提供保留原构造参数及 run/finish 的受控类式入口，默认要求隔离预检通过。尚未自动接管生产队列，也未验证全部旧函数入口、旧后处理或生产业务回写。真实网站成功不能替代对这些能力的单独验收。</div>
<p><strong>首个真实网站：</strong>千金供应商系统 <code>wx.qjdyf.cn</code> 的“商品流向”，验证日期为 2026-11-12。已核实原项目存在 DataDownloadHNQJNEW、DataDownloadHNQJDYFLS，并已使用测试账号登录；查询、导出和模板自动执行的最终结果以站点验收记录为准。</p>
<h3>维护与回退</h3><p>新模板不修改已发布版本。执行文件保存在各节点 runs/collect-&lt;uuid&gt; 下，归档失败会使工作流失败，不伪报成功。当前服务为单开发管理员入口，模板可含上游自定义脚本，仅向受信任开发人员开放；尚无完整多角色权限或生产级租约防重。</p><p>回退 A 方案时，先停止新的采集投递，核实已运行任务，再停止 crawler-dev-collector 与模拟站点；恢复 <code>/opt/crawler-dev/control/nginx.before-collector.conf</code> 并校验/重启网关，可移除采集入口。保留执行记录和产物。原 Prefect 服务及旧生产爬虫不需要删除或回滚数据库。</p></section>'''
if 'id="implementation-a"' not in text:
 text=text.replace('<section id="capacity">',section+'\n<section id="capacity">')
 text=text.replace('<a href="#deployment-directories">03-B 三环境部署与目录说明</a>','<a href="#deployment-directories">03-B 三环境部署与目录说明</a><a href="#implementation-a">03-C A方案实施与使用</a>')
path.write_text(text,encoding='utf-8')
check=Path('.tmp/verify_plan.py')
check.write_text(check.read_text(encoding='utf-8').replace('assert p.sections == 22','assert p.sections == 23'),encoding='utf-8')
