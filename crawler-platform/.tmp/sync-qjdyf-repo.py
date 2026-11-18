"""仅同步本次业务接入的白名单文件，不覆盖仓库中其他未提交工作。"""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
repo=root/'vendor/prefect';target=repo/'crawler-platform'
refresh='--refresh-final' in sys.argv
if not refresh:subprocess.run(['git','-C',str(repo),'diff','--quiet','HEAD','--','crawler-platform'],check=True)
names=[
 'runtime/catalog.py','runtime/maxun.py','tools/collector.py','tools/portal_auth.py','tools/test_maxun.py','tools/test_recorder.cjs','tools/test_maxun_actions.cjs',
 'deploy/maxun/browser-actions.cjs','deploy/maxun/recorder-compat.cjs','deploy/maxun/patch-installed.py','deploy/maxun/apply-recorder-compat.py','deploy/maxun/extract-web.py',
 'deploy/web/collector.html','deploy/web/maxun-recorder.js','deploy/sites/qjdyf-maxun/template.json','deploy/sites/qjdyf-maxun/README.md',
 'doc/爬虫任务编排与执行平台.html','doc/开发环境部署记录.html','doc/千金商品流向Maxun操作说明.html','doc/千金商品流向Maxun验收.json','doc/千金商品流向部署一致性.json','doc/千金商品流向交付检查.json','framework.lock.json',
 '.tmp/maxun/manage.py','.tmp/maxun/qjdyf-ui.mjs','.tmp/maxun/qjdyf-platform.py','.tmp/maxun/prepare-qjdyf.py','.tmp/maxun/read-ui-state.py','.tmp/maxun/read-workflow.py','.tmp/maxun/compare-qjdyf.py','.tmp/maxun/finalize-qjdyf.py','.tmp/maxun/update-business-doc.py','.tmp/maxun/update-publish-ui.py','.tmp/maxun/test-blob.mjs',
 '.tmp/sync-qjdyf-repo.py','.tmp/maxun/verify-delivery.mjs','.tmp/maxun/update-lock.py','.tmp/maxun/fix-doc-layout.py','.tmp/maxun/finalize-delivery-notes.py',
]
if refresh:
    # 只刷新首次同步后由本任务继续调整的收尾文件，其余仓库文件不再写入。
    final_names={'deploy/maxun/patch-installed.py','.tmp/maxun/verify-delivery.mjs','.tmp/maxun/update-lock.py','.tmp/maxun/finalize-qjdyf.py','.tmp/maxun/update-business-doc.py','.tmp/maxun/finalize-delivery-notes.py','.tmp/sync-qjdyf-repo.py','framework.lock.json','doc/爬虫任务编排与执行平台.html','doc/开发环境部署记录.html','doc/千金商品流向Maxun操作说明.html','doc/千金商品流向Maxun验收.json','doc/千金商品流向部署一致性.json','doc/千金商品流向交付检查.json'}
    names=[name for name in names if name in final_names]
for name in names:
    source=root/name;destination=target/name
    assert destination.resolve().is_relative_to(target.resolve())
    data=source.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode('utf-8')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    assert sha256(data).digest()==sha256(destination.read_bytes()).digest()
readme=target/'README.html';text=readme.read_text(encoding='utf-8')
old='<p>Maxun Web 录制服务已部署并验证登录、创建及远程页面显示；EasySpider 已验收真实商品流向采集。原有爬虫仍需逐站隔离接入，Maxun 同站业务验收尚未完成。</p>'
new='<p>Maxun 已完成千金商品流向 2026-11-12 单日端到端验收：工作台提交、Prefect COMPLETED、认证下载与 3 行数据逐字段对账通过。新增 Canvas / iframe 兼容录制、运行时账号注入、验证码有限重试与原始导出捕获。此前重复导出仍有失败记录，不宣称长期无人值守已稳定；定时未开启。操作见 <a href="doc/千金商品流向Maxun操作说明.html">站点操作说明</a>，证据见 <a href="doc/千金商品流向Maxun验收.json">验收记录</a>。原有爬虫仍需逐站隔离接入。</p>'
if old in text:readme.write_text(text.replace(old,new),encoding='utf-8',newline='\n')
else:assert new in text
print(json.dumps({'已同步源码与材料':len(names),'提交推送':'未执行'},ensure_ascii=False))
