<#
.SYNOPSIS
  计划任务包装器：登录后拉起 portal 常驻（PORT=0 临时端口 + data/portal.port 文件发现），按日重定向日志，
  退出码透传给计划任务做失败重启判据（P3 部署实施方案 §2.4 / §3.4 落地物）

.NOTES
  纪律：本脚本入仓（无密钥、MIT-0），机器路径全部走 env（ALLIN_ROOT / ALLIN_LOG_DIR），零盘符字面量（g01）。
  拍板口径（2026-11-04）：portal 进程登录常驻、端口临时——零新增常驻端口红线不破（ports.yaml 不动），
  website 治理看板登录即用；website 代理经 portal.port 文件发现端口，机制零改动。
#>
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "start-portal-task: $Message" }

# ---------- 0) 入参（fail-loud，给注册指引） ----------
if (-not $env:ALLIN_ROOT) {
  Fail '未设置 ALLIN_ROOT（请 setx ALLIN_ROOT <REPO_ROOT>，见 tools/deploy/README.md）'
}
$platformDir = Join-Path $env:ALLIN_ROOT 'platform'
if (-not (Test-Path -LiteralPath (Join-Path $platformDir 'package.json'))) {
  Fail "platform 目录不存在: $platformDir（检查 ALLIN_ROOT 是否指到仓库根）"
}

# ---------- 1) PORT=0：临时端口形态（与 start-platform.bat 同款；绝不写死任何固定端口） ----------
$env:PORT = '0'

# ---------- 2) 日志目录与按日文件 ----------
$logDir = $env:ALLIN_LOG_DIR
if (-not $logDir) { $logDir = Join-Path $env:LOCALAPPDATA 'allin\logs' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("portal-" + (Get-Date -Format 'yyyy-MM-dd') + ".log")

# ---------- 3) 前台跟随启动 ----------
# PS 5.1 陷阱：EAP=Stop 时原生命令 stderr 重定向会抛 NativeCommandError，本段切回 Continue。
$ErrorActionPreference = 'Continue'
& npm.cmd run portal 2>&1 | Out-File -Append -Encoding utf8 -FilePath $logFile
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
exit $code
