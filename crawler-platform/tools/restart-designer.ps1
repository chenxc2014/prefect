# 仅重启工作区内的设计器及其内置浏览器，不影响其他浏览器。
param([switch]$StopOnly)
$ErrorActionPreference='Stop'
$directory=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.local\designer\EasySpider_windows_x64'))
$boundary=$directory.TrimEnd('\')+'\'
$clientExecutable=Join-Path $directory 'EasySpider\EasySpider.exe'
if (-not (Test-Path -LiteralPath $clientExecutable)) { throw '工作区设计器不存在' }
$targets=Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($boundary,[StringComparison]::OrdinalIgnoreCase) }
foreach ($target in $targets) {
    Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($StopOnly) { return }
# 用户正在排查交互客户端，重启后显示可见窗口。
Start-Process -FilePath $clientExecutable -WorkingDirectory $directory -RedirectStandardOutput (Join-Path $directory 'designer.stdout.log') -RedirectStandardError (Join-Path $directory 'designer.stderr.log')
