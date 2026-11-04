<#
.SYNOPSIS
  计划任务包装器：登录后拉起 website 常驻（9042），stdout/stderr 按日重定向，退出码透传给计划任务做失败重启判据
  （P3 部署实施方案 §2.3 / §3.4 落地物）

.NOTES
  纪律：本脚本入仓（无密钥、MIT-0），机器路径全部走 env（ALLIN_ROOT / ALLIN_LOG_DIR），零盘符字面量（g01）。
  守护语义：node 崩溃 → npm 非零退出 → 本脚本非零退出 → 计划任务 RestartOnFailure 拉起（间隔 1 分钟、最多 5 次）。
#>
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "start-website-task: $Message" }

# ---------- 0) 入参（fail-loud，给注册指引） ----------
if (-not $env:ALLIN_ROOT) {
  Fail '未设置 ALLIN_ROOT（请 setx ALLIN_ROOT <REPO_ROOT>，见 tools/deploy/README.md）'
}
$webDir = Join-Path $env:ALLIN_ROOT 'website'
if (-not (Test-Path -LiteralPath (Join-Path $webDir 'package.json'))) {
  Fail "website 目录不存在: $webDir（检查 ALLIN_ROOT 是否指到仓库根）"
}

# ---------- 1) Node 版本前置校验：node:sqlite 需 >= 22.5 ----------
# 把「Node 版本错」变成开机可发现的 fail-loud，而非网站 500。
$nodeVer = & node -v 2>$null
if (-not $nodeVer) { Fail '未找到 node（PATH），website 需要 Node >= 22.5' }
$v = (@($nodeVer)[0] -replace '^v', '')
$segs = $v.Split('.')
if ([int]$segs[0] -lt 22 -or ([int]$segs[0] -eq 22 -and [int]$segs[1] -lt 5)) {
  Fail "Node $v 不满足 >= 22.5（website 用 node:sqlite，npm scripts 已带 --experimental-sqlite）"
}

# ---------- 2) 日志目录与按日文件 ----------
$logDir = $env:ALLIN_LOG_DIR
if (-not $logDir) { $logDir = Join-Path $env:LOCALAPPDATA 'allin\logs' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("website-" + (Get-Date -Format 'yyyy-MM-dd') + ".log")

# ---------- 3) 前台跟随启动 ----------
# PS 5.1 陷阱：EAP=Stop 时原生命令 stderr 重定向会抛 NativeCommandError——node 的
# --experimental-sqlite 警告恰在 stderr，故本段切回 Continue，管道合并输出到按日日志。
$ErrorActionPreference = 'Continue'
& npm.cmd start 2>&1 | Out-File -Append -Encoding utf8 -FilePath $logFile
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
exit $code
