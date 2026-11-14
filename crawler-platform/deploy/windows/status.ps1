$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Get-ScheduledTask -TaskName 'CrawlerDev-Worker' | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName 'CrawlerDev-Worker' | Select-Object LastRunTime,LastTaskResult
Get-Content -Encoding UTF8 -LiteralPath 'D:\CrawlerDev\logs\worker.log' -Tail 15
& 'D:\CrawlerDev\venv\Scripts\python.exe' -m pip check
