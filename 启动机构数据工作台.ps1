param(
    [switch]$NoBrowser,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$workbenchModule = "workspace.institution_catalog.workbench.server"
$workbenchUrl = "http://127.0.0.1:8765"
$workbenchPort = 8765

function Get-UvPath {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $uvCommand) {
        return $uvCommand.Source
    }
    $desktopDir = Split-Path $projectDir -Parent
    $candidate = Join-Path $desktopDir "software\uv-x86_64-pc-windows-msvc\uv.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    throw "未找到 uv。请将 uv 加入 PATH，或保留 Desktop\software\uv-x86_64-pc-windows-msvc\uv.exe。"
}

function Test-WorkbenchReady {
    try {
        $response = Invoke-WebRequest -Uri "$workbenchUrl/api/state" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Open-WorkbenchBrowser {
    if (-not $NoBrowser) {
        Start-Process $workbenchUrl
    }
}

function Get-WorkbenchListenerProcess {
    $connection = Get-NetTCPConnection -LocalPort $workbenchPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
}

function Get-WorkbenchServerProcesses {
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                ([string]$_.CommandLine).Contains($workbenchModule, [System.StringComparison]::OrdinalIgnoreCase)
            }
    )
}

function Stop-StaleWorkbench {
    foreach ($serverProcess in @(Get-WorkbenchServerProcesses)) {
        Stop-Process -Id $serverProcess.ProcessId -Force -ErrorAction SilentlyContinue
    }
    for ($attempt = 1; $attempt -le 50; $attempt++) {
        if (@(Get-WorkbenchServerProcesses).Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 100
    }
    $remainingProcesses = @(Get-WorkbenchServerProcesses)
    if ($remainingProcesses.Count -gt 0) {
        throw "旧版机构数据工作台进程未能停止（PID $($remainingProcesses.ProcessId -join '、')）。"
    }
    $listener = Get-WorkbenchListenerProcess
    if ($null -ne $listener) {
        throw "端口 $workbenchPort 已被其他程序占用（PID $($listener.ProcessId)）：$($listener.CommandLine)"
    }
}

function Start-Workbench {
    if (-not $ForceRestart -and (Test-WorkbenchReady)) {
        Open-WorkbenchBrowser
        return
    }
    $uvPath = Get-UvPath
    Stop-StaleWorkbench
    Start-Process -FilePath $uvPath -ArgumentList @("run", "python", "-m", $workbenchModule) -WorkingDirectory $projectDir -WindowStyle Hidden
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if (Test-WorkbenchReady) {
            Open-WorkbenchBrowser
            return
        }
    }
    throw "机构数据工作台未能在预期时间内启动，请查看 workspace\log 中最新的机构数据工作台日志。"
}

Start-Workbench
