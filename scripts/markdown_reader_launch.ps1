<#
Markdown 阅读器启动器。

做四件事：
1. 找一个真正能跑的 Python（跳过 Microsoft Store 的 0 字节占位程序）；
2. 桌面上的阅读器页面丢了就从仓库副本恢复；
3. 挑一个可用端口（8765 起，已被本阅读器占用就直接开页面，被别的程序占用就顺延）；
4. 启动服务端、等它就绪，然后打开浏览器。
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [int]$Port = 8765
)

$ErrorActionPreference = 'Continue'

$repo     = 'D:\factor'
$server   = Join-Path $repo 'scripts\markdown_reader_server.py'
$uiSource = Join-Path $repo 'scripts\markdown_reader_ui.html'
$logPath  = Join-Path $env:TEMP 'markdown_reader_server.log'
$errPath  = "$logPath.err"

if (-not (Test-Path -LiteralPath $server)) {
    Write-Host "[错误] 找不到服务端脚本：$server"
    Write-Host "       如果 factor 仓库换过位置，请修改本脚本里的 `$repo 变量。"
    exit 1
}

Write-Host '[1/3] 选择 Python 解释器 ...'
$candidates = New-Object System.Collections.Generic.List[string]
foreach ($literal in @(
        'D:\anaconda3\python.exe',
        'D:\anaconda3\envs\easyrl4rec\python.exe',
        'C:\ProgramData\anaconda3\python.exe',
        (Join-Path $env:USERPROFILE 'anaconda3\python.exe'))) {
    if ($literal -and (Test-Path -LiteralPath $literal)) { $candidates.Add($literal) }
}
foreach ($pattern in @(
        "$env:LOCALAPPDATA\Programs\Python\*\python.exe",
        'C:\Python3*\python.exe',
        'D:\Python3*\python.exe',
        'D:\anaconda3\envs\*\python.exe')) {
    foreach ($item in (Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue)) {
        $candidates.Add($item.FullName)
    }
}
foreach ($command in (Get-Command python.exe -All -ErrorAction SilentlyContinue)) {
    if ($command.Source -and $command.Source -notmatch 'WindowsApps') { $candidates.Add($command.Source) }
}

$python = $null
$pythonArgs = @()
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    try {
        & $candidate -c 'import sys' *> $null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    } catch { }
}
if (-not $python) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            & $launcher.Source -3 -c 'import sys' *> $null
            if ($LASTEXITCODE -eq 0) { $python = $launcher.Source; $pythonArgs = @('-3') }
        } catch { }
    }
}
if (-not $python) {
    Write-Host '[错误] 没有可用的 Python：PATH 里可能只剩 Microsoft Store 的占位程序。'
    Write-Host '       请安装 Python，或把可用的 python.exe 路径告诉 Codex。'
    exit 1
}
Write-Host "      解释器：$python $($pythonArgs -join ' ')"

$desktop = [Environment]::GetFolderPath('Desktop')
$uiPath = Join-Path $desktop 'Markdown阅读器.html'
if (-not (Test-Path -LiteralPath $uiPath)) {
    if (Test-Path -LiteralPath $uiSource) {
        try {
            Copy-Item -LiteralPath $uiSource -Destination $uiPath -Force
            Write-Host '      桌面页面文件缺失，已从仓库副本恢复。'
        } catch {
            Write-Host "      桌面页面文件缺失且无法恢复：$($_.Exception.Message)"
        }
    } else {
        Write-Host '      桌面页面文件缺失，仓库副本也不在。'
    }
}

function Get-ReaderPortState([int]$candidatePort) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect('127.0.0.1', $candidatePort)
        $client.Close()
    } catch {
        return 'free'
    }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$candidatePort/api/health" -TimeoutSec 2
        if ([string]$health.server -like 'markdown-reader*') { return 'ours' }
    } catch { }
    return 'foreign'
}

Write-Host '[2/3] 选择端口 ...'
$chosen = 0
$alreadyRunning = $false
foreach ($candidatePort in ($Port..($Port + 2))) {
    $state = Get-ReaderPortState $candidatePort
    if ($state -eq 'ours') { $chosen = $candidatePort; $alreadyRunning = $true; break }
    if ($state -eq 'free') { $chosen = $candidatePort; break }
    Write-Host "      端口 $candidatePort 被其它程序占用，试下一个。"
}
if ($chosen -eq 0) {
    Write-Host "[错误] $Port~$($Port + 2) 都被其它程序占用，请先关掉占用程序。"
    exit 1
}

if ($alreadyRunning) {
    Write-Host "      服务端已在运行（端口 $chosen）。"
} else {
    Write-Host "      启动服务端（端口 $chosen）..."
    $argumentList = @()
    if ($pythonArgs.Count -gt 0) { $argumentList += $pythonArgs }
    $argumentList += @("`"$server`"", '--host', '127.0.0.1', '--port', "$chosen")
    if (Test-Path -LiteralPath $uiPath) { $argumentList += @('--html', "`"$uiPath`"") }
    Start-Process -FilePath $python -ArgumentList ($argumentList -join ' ') `
        -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath

    $ready = $false
    foreach ($attempt in 1..30) {
        Start-Sleep -Milliseconds 700
        if ((Get-ReaderPortState $chosen) -ne 'free') { $ready = $true; break }
    }
    if (-not $ready) {
        Write-Host '[错误] 服务端 30 秒内没有就绪，日志如下：'
        Write-Host '------------------------------------------------------------'
        if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Tail 30 }
        if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -Tail 30 }
        Write-Host '------------------------------------------------------------'
        Write-Host "日志文件：$logPath"
        exit 1
    }
}

$url = "http://127.0.0.1:$chosen/"
Write-Host "[3/3] 服务端就绪：$url"
if ($NoBrowser) {
    Write-Host '      已按 -NoBrowser 跳过浏览器。'
    exit 0
}
Start-Process $url
exit 0