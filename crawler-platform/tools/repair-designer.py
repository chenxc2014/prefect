"""为本地 EasySpider 客户端安装可回滚的单实例启动保护。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / '.local/designer/EasySpider_windows_x64'
MAIN = CLIENT / 'EasySpider/resources/app/main.js'
MARKER = '// 采集平台：单实例启动保护'
ANCHOR = 'app.commandLine.appendSwitch("--disable-http-cache");'
GUARD = '''// 采集平台：单实例启动保护，避免重复打开争用 8074/8084。
if (!app.requestSingleInstanceLock()) {
    app.quit();
    process.exit(0);
}
app.on("second-instance", () => {
    const windows = BrowserWindow.getAllWindows().filter(win => !win.isDestroyed());
    const target = windows.find(win => win.isVisible()) || windows[0];
    if (target) {
        if (target.isMinimized()) target.restore();
        target.show();
        target.focus();
    }
});
'''

source = MAIN.read_text(encoding='utf-8')
backup = MAIN.with_name('main.before-single-instance.js')
if MARKER not in source:
    if source.count(ANCHOR) != 1:
        raise RuntimeError('客户端入口不符合预期，未修改任何源码')
    if not backup.exists():
        shutil.copy2(MAIN, backup)
    MAIN.write_text(source.replace(ANCHOR, GUARD + ANCHOR, 1), encoding='utf-8')

source = MAIN.read_text(encoding='utf-8')
if '// 采集平台：浏览器启动诊断' not in source:
    shutil.copy2(MAIN, MAIN.with_name('main.before-browser-diagnostics.js'))
    replacements = [
        ('const serviceBuilder = new ServiceBuilder(driverPath);', '''// 采集平台：浏览器启动诊断，日志保存在客户端目录。
    const serviceBuilder = new ServiceBuilder(driverPath)
        .enableVerboseLogging()
        .loggingTo(path.join(task_server.getDir(), "designer-chromedriver.log"));'''),
        ('function handleOpenBrowser(', 'let browserStarting = false;\nfunction handleOpenBrowser('),
        ('    const webContents = event.sender;\n    const win = BrowserWindow.fromWebContents(webContents);\n    runBrowser(lang, user_data_folder, mobile);', '''    if (browserStarting) return;
    browserStarting = true;
    const webContents = event.sender;
    const win = BrowserWindow.fromWebContents(webContents);
    runBrowser(lang, user_data_folder, mobile).catch(async error => {
        const errorPath = path.join(task_server.getDir(), "designer-startup-error.log");
        fs.appendFileSync(errorPath, new Date().toISOString() + " " + (error.stack || String(error)) + "\\n");
        if (driver) { try { await driver.quit(); } catch {} }
        if (flowchart_window && !flowchart_window.isDestroyed()) flowchart_window.destroy();
        mainWindow.show();
        dialog.showErrorBox("设计浏览器启动失败", String(error.message || error) + "\\n日志：" + errorPath);
    }).finally(() => { browserStarting = false; });'''),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError('浏览器诊断补丁锚点不符合预期，未写入入口')
        source = source.replace(old, new, 1)
    MAIN.write_text(source, encoding='utf-8')

source = MAIN.read_text(encoding='utf-8')
verbose = '''    const serviceBuilder = new ServiceBuilder(driverPath)
        .enableVerboseLogging()
        .loggingTo(path.join(task_server.getDir(), "designer-chromedriver.log"));'''
if verbose in source:
    source = source.replace(verbose, '''    const serviceBuilder = new ServiceBuilder(driverPath);
    // 采集平台：详细日志按需启用，正常设计时不持续记录页面交互。
    if (config.debug) {
        serviceBuilder.enableVerboseLogging()
            .loggingTo(path.join(task_server.getDir(), "designer-chromedriver.log"));
    }''', 1)
    MAIN.write_text(source, encoding='utf-8')

# 结束临时诊断，仅恢复日志开关，保留用户新改的其他配置。
config = CLIENT / 'config.json'
original = CLIENT / 'config.before-diagnose.json'
if original.exists():
    data = json.loads(config.read_text(encoding='utf-8'))
    data['debug'] = json.loads(original.read_text(encoding='utf-8')).get('debug', False)
    config.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

report = {
    'change': '单实例启动保护、启动中防重复点击、启动失败提示与错误日志；详细驱动日志按 debug 配置启用',
    'installed_main': str(MAIN.relative_to(ROOT)),
    'backup': str(backup.relative_to(ROOT)),
    'sha256': hashlib.sha256(MAIN.read_bytes()).hexdigest(),
    'takes_effect': '所有旧客户端进程退出后的下一次启动',
}
(CLIENT.parent / 'single-instance-patch.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
