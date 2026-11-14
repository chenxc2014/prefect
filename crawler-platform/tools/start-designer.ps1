# 供用户交互式启动已安装的可视化设计客户端。
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$directory=Join-Path $root '.local\designer\EasySpider_windows_x64'
$executable=Join-Path $directory 'EasySpider.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw '请先准备 EasySpider v0.6.5 官方 Windows 设计客户端' }
# 已有客户端仍在运行时避免再启动，固定端口由同一实例持续占用。
$clientExecutable=Join-Path $directory 'EasySpider\EasySpider.exe'
$running=Get-CimInstance Win32_Process -Filter "Name='EasySpider.exe'" | Where-Object { $_.ExecutablePath -eq $clientExecutable }
if ($running) {
    Write-Host 'EasySpider 已在运行，请切换到已打开的客户端或任务列表窗口。'
    return
}
# 此入口用于用户设计任务，需要显示交互窗口。
Start-Process -FilePath $executable -WorkingDirectory $directory
