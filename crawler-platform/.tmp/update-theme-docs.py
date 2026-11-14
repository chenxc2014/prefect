"""记录共享界面主题、部署位置和回退方法。"""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
fragment = '''
<div id="unified-ui" class="note"><h3>2026-11-15 更新：三个应用统一视觉风格</h3>
<p>以采集工作台为主视觉，Prefect、Maxun 共用「采集管理 / COLLECTION HUB」品牌、深色侧栏、蓝色主操作、浅色背景、系统中文字体与圆角卡片。顶部提供采集工作台 / Prefect 调度 / Maxun 设计切换，以及当前账号和退出统一登录。各应用继续保留自己的专业导航与工作布局。</p>
<div class="table-wrap"><table><thead><tr><th>界面</th><th>统一内容</th><th>保留的能力</th></tr></thead><tbody>
<tr><td>采集工作台</td><td>沿用已有布局，增加共享应用切换栏。</td><td>三引擎入口、模板发布、参数、任务提交与产物下载。</td></tr>
<tr><td>Prefect</td><td>共用品牌、顶部导航、侧栏颜色、字体、卡片和表单外观。</td><td>调度、部署、工作池、运行状态、日志与原有状态颜色。</td></tr>
<tr><td>Maxun</td><td>共用品牌、导航、侧栏、表单与蓝色品牌色；明暗切换继续可用。</td><td>机器人与录制工作区；录制页保留原有浏览器区域和坐标布局。</td></tr>
</tbody></table></div>
<h4>主题文件与部署</h4>
<ul><li><code>deploy/web/suite-theme.css</code>：共享视觉变量及两个原生界面的组件样式适配。</li><li><code>deploy/web/suite-theme.js</code>：应用切换、品牌与组件标记；不搬移原应用的 React 节点，不向被录制网页的 iframe 注入主题。</li><li><code>tools/portal_auth.py</code>：通过现有统一会话提供主题资源；<code>deploy/linux/install-sso.py</code> 将其接入 8443、9443 的 HTML 入口。</li><li><code>deploy/maxun/apply-branding.py</code>：仅替换 Maxun 静态 JS / CSS 内已经确认的固定品牌色；不处理接口响应、被采集网站的网页或业务文件。提取新版前端后自动重新应用。</li><li>原有红色失败 / 放弃、绿色成功等语义颜色继续保留；品牌色替换规则和静态文件前后摘要记录在 <code>/opt/crawler-dev/maxun/branding.lock.json</code>。</li></ul>
<p>Maxun 静态资源修改前备份：<code>/opt/crawler-dev/backups/maxun-palette-20261115-005111/</code>。共享主题初次发布前的认证代码与网关备份分别为 <code>sso-code-20261115-004322/</code> 和 <code>sso-gateway-20261115-004325/</code>，均位于 /opt/crawler-dev/backups/。</p>
<p>如需仅停用共享外观，可将服务器发布目录中的 suite-theme.css、suite-theme.js 暂时替换为空的有效文件，并恢复上述 Maxun 静态资源备份，再刷新浏览器；保留统一登录模块、会话数据库与认证网关，不必重启采集执行引擎。主题样式修改后刷新生效，涉及认证路由或网关的变更仍按检查、重载流程发布。</p>
<p>验证记录：<a href="统一界面风格验收.json">统一界面风格验收</a>、<a href="统一登录部署验收.json">登录与采集回归</a>。主题验证覆盖桌面与窄屏、原生页面切换及明暗模式；演示网站验证日期输入、查询、远程录制与文件下载。本次仅操作当前工作区和 Linux 169。</p>
</div>
'''
for name in ('爬虫任务编排与执行平台.html', '开发环境部署记录.html'):
    path = root / 'doc' / name
    text = path.read_text(encoding='utf-8')
    if 'id="unified-ui"' not in text:
        marker = '<div id="unified-login" class="note">'
        assert marker in text
        text = text.replace(marker, fragment + marker, 1)
        path.write_text(text, encoding='utf-8', newline='\n')
path = root / 'framework.lock.json'
data = json.loads(path.read_text(encoding='utf-8'))
data['portal_theme'] = {'version': '2026.11.15', 'styles': 'deploy/web/suite-theme.css', 'navigation': 'deploy/web/suite-theme.js', 'maxun_palette_adapter': 'deploy/maxun/apply-branding.py', 'primary_color': '#405bf0', 'sidebar_color': '#111a32'}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
report_path = root / 'doc/统一界面风格验收.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
regression = json.loads((root / 'doc/统一登录部署验收.json').read_text(encoding='utf-8'))
assert report['passed'] and regression['passed']
report['regression_report'] = '统一登录部署验收.json'
report['verified_behavior'] = ['录制器日期输入与查询成功', '录制操作条使用统一蓝色，放弃操作保留红色', '被录制网页未注入主题', '演示任务执行及结果下载成功', '统一登录、退出及 Worker 认证保持可用']
report['screenshots'] = ['.local/screenshots/theme-platform.png', '.local/screenshots/theme-prefect.png', '.local/screenshots/theme-maxun.png', '.local/screenshots/theme-maxun-create.png', '.local/screenshots/theme-maxun-mobile.png', '.local/screenshots/unified-recorder.png']
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('共享主题使用、部署与回退说明已更新')
