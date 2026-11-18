"""仅生成独立挂载的运行补丁，保留官方镜像和固定源码不变。"""
from pathlib import Path
import subprocess

root=Path('/opt/crawler-dev/maxun')
overlay=root/'overlay';overlay.mkdir(exist_ok=True)
container=subprocess.check_output(['docker','create','getmaxun/maxun-backend:v0.1.0'],text=True).strip()
try:
    files={'server.js':'/app/server/dist/server/src/server.js','Interpreter.js':'/app/server/dist/server/src/workflow-management/classes/Interpreter.js','core-interpret.js':'/app/node_modules/maxun-core/build/interpret.js','RemoteBrowser.js':'/app/server/dist/server/src/browser-management/classes/RemoteBrowser.js','controller.js':'/app/server/dist/server/src/browser-management/controller.js','inputHandlers.js':'/app/server/dist/server/src/browser-management/inputHandlers.js'}
    for name,source in files.items():
        subprocess.run(['docker','cp',container+':'+source,str(overlay/name)],check=True)
finally:
    subprocess.run(['docker','rm',container],check=True,stdout=subprocess.DEVNULL)

server=overlay/'server.js';code=server.read_text()
anchor='app.use(cors(CORS_CONFIG));'
if anchor not in code:
    anchor='app.use((0, cors_1.default)(CORS_CONFIG));'
if code.count(anchor)!=1:raise RuntimeError('服务器反向代理补丁锚点不匹配')
server.write_text(code.replace(anchor,'app.set("trust proxy", 1);\n'+anchor,1))

interpreter=overlay/'Interpreter.js';code=interpreter.read_text()
anchor='const status = await interpreter.run(page, params);'
if code.count(anchor) not in (1,2):raise RuntimeError('文件下载监听补丁锚点不匹配')
replacement='''// 采集平台：保存网站原始下载文件，并等待所有下载完成。
        const crawlerDownloads = [];
        const crawlerHandlers = new Map();
        const crawlerWatch = target => {
            if (crawlerHandlers.has(target)) return;
            const handler = download => {
                const pending = (async () => {
                    const stream = await download.createReadStream();
                    if (!stream) throw new Error("文件下载未完成");
                    const chunks = []; let size = 0;
                    for await (const chunk of stream) {
                        size += chunk.length;
                        if (size > 10 * 1024 * 1024) throw new Error("原始下载文件超过开发归档上限 10MB");
                        chunks.push(chunk);
                    }
                    const name = require("path").basename(download.suggestedFilename());
                    const item = {name, mimeType: name.endsWith(".xlsx") ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" : "application/octet-stream", data: Buffer.concat(chunks).toString("base64")};
                    await crawlerSaveBinary(item);
                })();
                pending.catch(() => {});
                crawlerDownloads.push(pending);
            };
            target.on("download", handler);
            crawlerHandlers.set(target, handler);
        };
        const crawlerContext = page.context();
        crawlerContext.pages().forEach(crawlerWatch);
        crawlerContext.on("page", crawlerWatch);
        let status;
        try {
            status = await interpreter.run(page, params);
            await Promise.all(crawlerDownloads);
        } finally {
            crawlerContext.off("page", crawlerWatch);
            for (const [target,handler] of crawlerHandlers) target.off("download", handler);
        }'''
replacement='const crawlerSaveBinary = async item => { if (this.binaryData.some(saved => saved.data === item.data)) return; this.binaryData.push(item); await this.persistBinaryDataToDatabase(item); };\nawait require("/app/platform/browser-actions.cjs").install(page, crawlerSaveBinary);\n'+replacement
interpreter.write_text(code.replace(anchor,replacement))
core=overlay/'core-interpret.js';code=core.read_text()
import re
for label in ['Executing action:','MATCHED ACTION:','Carrying out:']:
    code=re.sub(r'^[ \t]*console\.log\([\"\x27]'+re.escape(label)+r'[\"\x27][^\n]*\);[ \t]*$', '// 采集平台：不记录解密后的流程或输入值。',code,flags=re.M)
core.write_text(code)
remote=overlay/'RemoteBrowser.js';code=remote.read_text()
anchor='this.registerEditorEvents = () => {'
if code.count(anchor)!=1:raise RuntimeError('兼容录制补丁锚点不匹配')
code=code.replace(anchor,anchor+'\nrequire("/app/platform/recorder-compat.cjs").install(this);',1)
anchor='.fromLists(cross_fetch_1.default,'
if code.count(anchor)!=1:raise RuntimeError('浏览器可选资源超时补丁锚点不匹配')
remote.write_text(code.replace(anchor,'.fromLists((url, options) => cross_fetch_1.default(url, {...options, signal: AbortSignal.timeout(5000)}),',1))
controller=overlay/'controller.js';code=controller.read_text()
anchor='const RECORDING_TIMEOUT_MS = 10 * 60 * 1000;'
if code.count(anchor)!=1:raise RuntimeError('录制会话期限补丁锚点不匹配')
controller.write_text(code.replace(anchor,'const RECORDING_TIMEOUT_MS = 30 * 60 * 1000;',1))
inputs=overlay/'inputHandlers.js';code=inputs.read_text()
for original,replacement in [('`Key ${key} unpressed`','"按键已释放"'),('`Keyboard action processed: ${data.key} on ${data.selector}`','"键盘输入步骤已处理"')]:
    if code.count(original)!=1:raise RuntimeError('按键日志脱敏补丁锚点不匹配')
    code=code.replace(original,replacement,1)
inputs.write_text(code)
for name in files:
    subprocess.run(['docker','run','--rm','-v',str(overlay/name)+':/tmp/check.js:ro,z','--entrypoint','node','getmaxun/maxun-backend:v0.1.0','--check','/tmp/check.js'],check=True)
compose=root/'compose.resolved.yaml';text=compose.read_text()
anchor='    ports: [\'127.0.0.1:18080:8080\']'
mount='''    volumes:
      - ./overlay/server.js:/app/server/dist/server/src/server.js:ro,z
      - ./overlay/Interpreter.js:/app/server/dist/server/src/workflow-management/classes/Interpreter.js:ro,z
      - ./overlay/core-interpret.js:/app/node_modules/maxun-core/build/interpret.js:ro,z
      - ./browser-actions.cjs:/app/platform/browser-actions.cjs:ro,z
'''
if 'overlay/server.js' not in text:
    if anchor not in text:raise RuntimeError('容器挂载补丁锚点不匹配')
    compose.write_text(text.replace(anchor,mount+anchor,1))
text=compose.read_text()
extra={'RemoteBrowser.js':'/app/server/dist/server/src/browser-management/classes/RemoteBrowser.js','controller.js':'/app/server/dist/server/src/browser-management/controller.js','inputHandlers.js':'/app/server/dist/server/src/browser-management/inputHandlers.js','recorder-compat.cjs':'/app/platform/recorder-compat.cjs'}
for name,destination in extra.items():
    source=('./overlay/' if name.endswith('.js') else './')+name
    if source+':' not in text:text=text.replace('    volumes:\n','    volumes:\n      - '+source+':'+destination+':ro,z\n',1)
compose.write_text(text)
print('HTTPS 会话与原始文件下载补丁已生成，官方镜像未修改')
