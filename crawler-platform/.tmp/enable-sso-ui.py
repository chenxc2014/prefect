"""将采集管理界面的入口与账号操作接入统一登录。"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'deploy/web/collector.html'
text = path.read_text(encoding='utf-8')
script = '<script src="auth/client.js" data-app="platform"></script>'
if script not in text:
    text = text.replace('</style></head>', '</style>' + script + '</head>', 1)
text = text.replace('<div class="avatar" title="开发环境工作台">C</div>', '<span data-crawler-user>crawlerdev</span><button class="btn small" data-crawler-logout>退出统一登录</button>')
text = text.replace('href="/v2/"', 'href="open/prefect"')
text = text.replace('data-maxun-link href="designer"', 'data-maxun-link href="open/maxun"')
text = text.replace('<strong>设计器独立登录</strong>开发账号：crawlerdev@crawler.local；密码沿用采集管理平台开发账号的密码。保存机器人后，发布与调度在本平台完成。', '<strong>已接入统一登录</strong>登录采集管理平台后，进入 Maxun 无需再次输入邮箱和密码。保存机器人后，返回这里发布并交给 Prefect 调度。')
text = text.replace('通过堡垒机时，访问端须能连接 Linux 169 的 9443 端口，并信任与采集平台相同的开发证书 CA。', '通过本平台进入设计器时自动衔接登录。堡垒机访问端须能连接 169 的 8443、9443 端口，并信任相同的开发证书 CA。')
text = text.replace('@media(max-width:520px){.footer{display:flex;flex-direction:column;gap:5px}}', '@media(max-width:520px){.footer{display:flex;flex-direction:column;gap:5px}.topright [data-crawler-user]{display:none}.topright [data-crawler-logout]{font-size:10px;padding:6px 8px}}')
path.write_text(text, encoding='utf-8', newline='\n')
print('工作台入口与退出按钮已接入统一登录')
