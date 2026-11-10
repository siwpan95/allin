# ensure-mirror.ps1 - make sure the local npm mirror proxy is up (OPTIONAL).
#
# 2026-11-10 换机可移植整改：镜像代理此前是**强依赖**——启动器无条件把
# npm_config_registry 指向 127.0.0.1:8899，而代理脚本本身在**仓外**
# （%USERPROFILE%\.dsh\npm_local_mirror.py），新机必然装不上 ⇒ npm install 100% 失败。
# 现在语义改为「镜像可用就用，不可用就回退默认 registry」：
#   exit 0  = 镜像就绪（调用方可把 npm_config_registry 指向 127.0.0.1:8899）
#   exit 10 = 镜像不可用但这是**可接受**状态（调用方回退默认 registry，不阻断）
#   exit 1  = 以 -Required 调用且镜像启动后仍不就绪（真故障）
#
# The proxy ($env:USERPROFILE/.dsh/npm_local_mirror.py — 盘符与用户名随机器，
# 不写死绝对路径) is a loopback-only
# caching registry proxy on 127.0.0.1:8899. This script probes the port, starts
# the proxy if it is not listening, then waits (max 30s) until it really accepts
# connections, so npm never races a dead registry port and hangs.
# The proxy deliberately runs in a visible console window: a hidden
# window listening on a port is a classic malware heuristic, and a
# visible window keeps the process fully transparent.
# 2026-09-24: python/mirror paths are no longer hardcoded drive letters.
# Resolution: -Python/-MirrorScript params > env (PLATFORM_PYTHON / PLATFORM_NPM_MIRROR)
# > 'python' from PATH / %USERPROFILE%\.dsh\npm_local_mirror.py.

param(
    [string]$Python = $env:PLATFORM_PYTHON,
    [string]$MirrorScript = $env:PLATFORM_NPM_MIRROR,
    [switch]$Optional
)

if (-not $Python) { $Python = 'python' }
if (-not $MirrorScript) { $MirrorScript = Join-Path $env:USERPROFILE '.dsh\npm_local_mirror.py' }

$addr = '127.0.0.1'
$port = 8899

function Test-MirrorPort {
    try {
        $client = New-Object Net.Sockets.TcpClient($addr, $port)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

if (Test-MirrorPort) {
    Write-Output "[mirror] 127.0.0.1:$port 已就绪"
    exit 0
}

if (-not (Test-Path -LiteralPath $MirrorScript)) {
    $msg = "本地镜像脚本不在本机：$MirrorScript"
    if ($Optional) {
        Write-Output "[mirror] $msg —— 镜像可选，回退默认 registry（不影响功能，只是装包走公网）"
        exit 10
    }
    Write-Output "[mirror] $msg"
    exit 1
}

Write-Output "[mirror] 启动本地镜像：$MirrorScript"
try {
    $proc = Start-Process -FilePath $Python -ArgumentList $MirrorScript -PassThru
} catch {
    Write-Output "[mirror] 启动失败：$($_.Exception.Message)"
    if ($Optional) { exit 10 } else { exit 1 }
}

for ($i = 0; $i -lt 30; $i++) {
    if (Test-MirrorPort) {
        Write-Output "[mirror] 127.0.0.1:$port 已就绪（pid=$($proc.Id)）"
        exit 0
    }
    # 代理进程提前退出 = 启动失败，别再空等 30 秒
    if ($proc.HasExited) {
        Write-Output "[mirror] 代理进程已退出（exit=$($proc.ExitCode)）"
        if ($Optional) { exit 10 } else { exit 1 }
    }
    Start-Sleep -Seconds 1
}

Write-Output "[mirror] 等待 30s 后仍不就绪"
if ($Optional) { exit 10 } else { exit 1 }
