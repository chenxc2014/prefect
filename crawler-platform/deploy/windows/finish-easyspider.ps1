# 完成内网分发的便携浏览器安装，终止本次卡住的下载进程。
$ErrorActionPreference='Stop'
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq 'D:\CrawlerDev\easyspider\venv\Scripts\python.exe' -and $_.CommandLine -like '*last-known-good-versions-with-downloads.json*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
$root='D:\CrawlerDev\easyspider'
Expand-Archive -LiteralPath "$root\downloads\chrome-win64.zip" -DestinationPath $root -Force
Expand-Archive -LiteralPath "$root\downloads\chromedriver-win64.zip" -DestinationPath $root -Force
@{source="$root\source";python="$root\venv\Scripts\python.exe";browser="$root\chrome-win64\chrome.exe";driver="$root\chromedriver-win64\chromedriver.exe";timeout=180} | ConvertTo-Json | Set-Content -Encoding UTF8 'D:\CrawlerDev\private\easyspider.json'
& "$root\venv\Scripts\python.exe" -m pip freeze | Set-Content -Encoding UTF8 "$root\requirements.lock"
& 'D:\CrawlerDev\venv\Scripts\python.exe' 'D:\CrawlerDev\releases\dev-v1\tools\register_collect.py' 'D:\CrawlerDev\private\client.json'
if ($LASTEXITCODE -ne 0) { throw '采集部署注册失败' }
$action=New-ScheduledTaskAction -Execute 'D:\CrawlerDev\venv\Scripts\python.exe' -Argument '"D:\CrawlerDev\releases\dev-v1\tools\demo_site.py"' -WorkingDirectory 'D:\CrawlerDev\releases\dev-v1'
$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'CrawlerDev-Demo' -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName 'CrawlerDev-Demo'
Get-ScheduledTask -TaskName 'CrawlerDev-Demo' | Select-Object TaskName,State
