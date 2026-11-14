$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = 'D:\CrawlerDev'
& "$root\venv\Scripts\python.exe" "$root\releases\dev-v1\tools\setup_node.py" "$root\private\client.json"
if ($LASTEXITCODE -ne 0) { throw '开发部署注册失败' }
$action = New-ScheduledTaskAction -Execute "$root\venv\Scripts\python.exe" -Argument '"D:\CrawlerDev\releases\dev-v1\tools\worker.py" "D:\CrawlerDev\private\client.json"' -WorkingDirectory "$root\releases\dev-v1"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'CrawlerDev-Worker' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'CrawlerDev-Worker'
Get-ScheduledTask -TaskName 'CrawlerDev-Worker' | Select-Object TaskName,State
