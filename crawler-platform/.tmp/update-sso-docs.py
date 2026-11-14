"""补充统一登录的使用方式、认证边界、部署与回退记录。"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
fragment = '''
<div id="unified-login" class="note"><h3>2026-11-15 更新：统一主入口与登录</h3>
<p><strong>日常主入口：</strong><a href="https://192.168.1.169:8443/collector/">https://192.168.1.169:8443/collector/</a>。原 8443 根地址现在也跳转到采集工作台。未登录访问 Prefect 或 Maxun，会引导到同一个中文登录页。</p>
<p>使用现有平台用户名 <code>crawlerdev</code> 和原平台密码登录。登录后，点击「Prefect 调度监控」或「进入 Maxun 在线设计器」，均无需再次填写账号、邮箱或密码。设计器的底层开发账号仍保留，由平台服务端衔接，不需要用户另行登录。</p>
<p>会话默认有效期 8 小时。平台右上角，以及 Prefect、Maxun 的「退出统一登录」按钮，可撤销当前统一会话；已打开的其他界面最迟在下一次会话检查时回到登录页，检查间隔为 10 秒。退出后，旧会话不能再次调用受保护接口；重新登录后方可继续使用。</p>
<h4>实现与兼容边界</h4>
<ul><li>统一会话由采集管理 API 管理。浏览器仅保存 Secure、HttpOnly、SameSite=Lax 的随机会话 Cookie；平台密码不进入 URL 或 localStorage。</li><li>Nginx 对 Prefect 浏览器请求检查统一会话，再在服务端转发原有 API 认证；Prefect 后端认证保持开启。Worker 的 Basic 接口认证继续保留，不要求执行节点使用浏览器会话。</li><li>Maxun 通过服务端登录衔接获取原生 Cookie，并初始化其界面用户状态；公开入口由统一会话保护。仅访问 9443 且未登录时也会返回统一登录页。</li><li>会话写请求校验来源与 CSRF，登录失败进行限速；SQLite 仅保存会话令牌摘要，支持到期与退出撤销。当前仍为单开发账号模式，尚未建设企业身份源及多用户角色权限。</li><li>SSO Cookie 不区分端口。日常请使用同一台 169 的内网 IP 地址访问两个端口，避免混用不同域名、IP 或不同浏览器配置。证书与防火墙来源白名单要求继续沿用。</li></ul>
<h4>代码与服务位置</h4>
<div class="table-wrap"><table><thead><tr><th>位置</th><th>作用</th></tr></thead><tbody>
<tr><td>runtime/auth.py</td><td>会话摘要、到期与撤销、登录失败限速。</td></tr>
<tr><td>tools/portal_auth.py</td><td>统一登录、退出、内部网关校验、Prefect 设置适配与 Maxun 进入桥接。</td></tr>
<tr><td>deploy/web/login.html / auth-client.js</td><td>中文登录页、统一账号操作、跨界面会话失效检查。</td></tr>
<tr><td>deploy/linux/install-sso.py</td><td>生成统一网关配置，检查认证服务就绪后平滑重载；失败时恢复原配置文件。</td></tr>
<tr><td>/etc/crawler-dev/sso.json</td><td>受限网关密钥与两个应用的允许来源，不入代码仓库。</td></tr>
<tr><td>/var/lib/crawler-dev/auth/sessions.sqlite</td><td>受限会话数据库，不保存明文平台密码或明文会话令牌。</td></tr>
<tr><td>/opt/crawler-dev/control/nginx.conf / maxun.conf</td><td>统一登录网关；deploy/maxun/gateway.py 检测到 SSO 配置后保持该网关，避免普通发版恢复旧认证。</td></tr>
</tbody></table></div>
<p>网关初次切换前备份：<code>/opt/crawler-dev/backups/sso-gateway-20261115-001033/</code>。代码首次变更前备份：<code>/opt/crawler-dev/backups/sso-code-20261115-000952/</code>。如需回退，先恢复两份网关配置并检查、平滑重载，再恢复 collector.py 与 collector.html 并重启 crawler-dev-collector；新增认证文件可留存，不要清理业务运行目录。回退期间应保持原来源白名单和原 API 认证。</p>
<p>实际验证见 <a href="统一登录部署验收.json">统一登录部署验收</a>：一次登录、两个子系统免登录、刷新保留状态、WebSocket 录制、Linux 演示任务与文件下载、统一退出及旧会话拒绝均通过。本次未连接 Windows 167，未执行真实业务网站任务。</p>
<p class="small">网关采用 Nginx 官方支持的 <a href="https://nginx.org/en/docs/http/ngx_http_auth_request_module.html">auth_request 子请求认证</a>和 <a href="https://nginx.org/en/docs/http/ngx_http_proxy_module.html">反向代理配置</a>。浏览器免二次登录不等于取消后端认证。</p>
</div>
'''
for name in ('爬虫任务编排与执行平台.html', '开发环境部署记录.html'):
    path = root / 'doc' / name
    text = path.read_text(encoding='utf-8')
    if 'id="unified-login"' not in text:
        marker = '<div id="multi-engine-workspace" class="note">'
        assert marker in text
        text = text.replace(marker, fragment + marker, 1)
    text = text.replace('账号 crawlerdev@crawler.local，密码沿用开发管理账号，不在文档记录明文。', '通过采集管理平台统一登录进入，无需手动输入 Maxun 邮箱与密码。')
    text = text.replace('用户名为 <code>crawlerdev</code>。随机生成的认证值', '统一网页登录用户名为 <code>crawlerdev</code>。随机生成的认证值')
    text = text.replace('恢复 collector.py 与 collector.html 并重启 crawler-dev-collector；新增认证文件可留存', '恢复 collector.py 与 collector.html 并重启 crawler-dev-collector，并将 /etc/crawler-dev/sso.json 改名留存以停用普通发版时的 SSO 自动恢复；新增认证文件可留存')
    path.write_text(text, encoding='utf-8', newline='\n')

report = root / 'doc/统一登录部署验收.json'
assert report.is_file()
print('统一登录使用、部署、边界及回退说明已补充到现有 HTML 文档')
