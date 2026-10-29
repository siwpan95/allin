# ensure-mirror.ps1 - make sure the local npm mirror proxy is up.
#
# The proxy ($env:USERPROFILE/.dsh/npm_local_mirror.py — 盘符与用户名随机器，
# 不写死绝对路径) is a loopback-only
# caching registry proxy on 127.0.0.1:8899; npm installs on this network
# must go through it. This script probes the port, starts the proxy if it
# is not listening, then waits (max 30s) until it really accepts
# connections, so npm never races a dead registry port and hangs.
# The proxy deliberately runs in a visible console window: a hidden
# window listening on a port is a classic malware heuristic, and a
# visible window keeps the process fully transparent.
# Exit codes: 0 = proxy ready, 1 = not ready after 30s.
# 2026-09-24: python/mirror paths are no longer hardcoded drive letters.
# Resolution: -Python/-MirrorScript params > env (PLATFORM_PYTHON / PLATFORM_NPM_MIRROR)
# > 'python' from PATH / %USERPROFILE%\.dsh\npm_local_mirror.py.

param(
    [string]$Python = $env:PLATFORM_PYTHON,
    [string]$MirrorScript = $env:PLATFORM_NPM_MIRROR
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

if (-not (Test-MirrorPort)) {
    Start-Process -FilePath $Python -ArgumentList $MirrorScript
}

for ($i = 0; $i -lt 30; $i++) {
    if (Test-MirrorPort) { exit 0 }
    Start-Sleep -Seconds 1
}
exit 1
