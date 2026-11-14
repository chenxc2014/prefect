"""更新本次界面汉化的交付记录。"""
from pathlib import Path

path = Path('doc/开发环境部署记录.html')
text = path.read_text(encoding='utf-8')
text = text.replace('vendor 中的官方源码保持未修改，运行仍使用固定版本的发布包。原有 fetch-crawler 目录没有修改。', 'vendor 中的 Prefect UI v2 已在 ui-v2/chinese-localization 分支进行中文界面定制，后端运行固定版本 3.9.2 的发布包。原有 fetch-crawler 目录没有修改。')
section = '''<section><h2>中文管理界面</h2><p>2026-11-13 已发布中文界面版本 <code>3.9.2-zh.1</code>，默认简体中文。访问原管理地址，使用 Ctrl+F5 刷新；登录页及左下角均可切换中文 / English，语言选择保存在当前浏览器。</p><p>覆盖常用导航、登录、部署、运行状态、工作池及表单提示。业务任务名称、自定义状态名称、运行日志、API 参数与技术标识保留原值；旧版 v1 界面仍为英文，部分高级功能或动态文案后续继续补充。</p><p>源码位置：<code>vendor/prefect/ui-v2/localization</code>（词典及构建转换）、<code>src/i18n</code>（语言选择与状态翻译）。构建转换仅针对可显示文案，不替换接口枚举、业务名称或路由值。后端与数据库结构未更改。</p><p>169 当前资源目录：<code>/var/lib/crawler-dev/ui-releases/zh-cn-20261113T025217Z</code>，之前目录 <code>/var/lib/crawler-dev/ui</code> 保留；配置为 <code>/etc/crawler-dev/ui.env</code>，版本指针为 <code>/etc/crawler-dev/ui-release.json</code>。</p><pre># 在 UI 源码目录构建
npm ci
npm run build

# 在工作区同步发布脚本、发布前端、验证实际部署
python .tmp/crawler-dev/manage.py 169 push
python .tmp/crawler-dev/manage.py 169 release-ui
python .tmp/crawler-dev/manage.py 169 check-ui
python .tmp/crawler-dev/manage.py 169 ui-browser remote

# 在 169 回退界面（会重启开发控制中心）
python3.12 /opt/crawler-dev/releases/dev-v1/deploy/linux/release_ui.py --rollback</pre><p>验证：8 个测试文件、52 项测试通过；TypeScript 与生产构建通过；ESLint 无错误，保留上游已有 64 项警告。发布后通过首页、静态资源、API 健康及未认证 401 检查。浏览器验收结果见 <a href="界面汉化浏览器验证.json">界面汉化浏览器验证</a>。</p><p>后续升级 Prefect 时需重新构建并复验定制界面；直接切换官方前端资源会恢复英文。</p></section>'''
text = text.replace('</body>', section + '</body>')
path.write_text(text, encoding='utf-8')
