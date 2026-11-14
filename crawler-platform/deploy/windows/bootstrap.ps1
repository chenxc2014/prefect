# 安装到独立目录，不修改旧爬虫环境、PATH 或默认文件关联。
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = 'D:\CrawlerDev'
New-Item -ItemType Directory -Force -Path "$root\downloads", "$root\private", "$root\runs", "$root\logs", "$root\releases\dev-v1" | Out-Null
$python = "$root\Python312\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $installer = "$root\downloads\python-3.12.10-amd64.exe"
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'Python 安装包签名验证失败，停止安装'
    }
    $arguments = '/quiet InstallAllUsers=0 TargetDir=D:\CrawlerDev\Python312 Include_launcher=0 PrependPath=0 Shortcuts=0 Include_test=0 AssociateFiles=0'
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Python 安装失败：$($process.ExitCode)" }
}
& $python --version
if (-not (Test-Path -LiteralPath "$root\venv\Scripts\python.exe")) { & $python -m venv "$root\venv" }
if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败' }
& "$root\venv\Scripts\python.exe" -m pip install 'prefect==3.9.2'
if ($LASTEXITCODE -ne 0) { throw 'Prefect 安装失败' }
& "$root\venv\Scripts\python.exe" -m pip freeze | Set-Content -Encoding UTF8 "$root\private\windows-requirements.lock"
& icacls "$root\private" /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
Write-Output 'Windows 开发环境前置安装完成'
