<#
.SYNOPSIS
  ALLIN-monthly-audit 计划任务包装器（ERP 调研 P2 备用路线，2026-11-07）。
  只做三件事：仓根自发现 → Python 解析 → 调 monthly_audit.py 并透传退出码。

.DESCRIPTION
  - 跨机可复制：仓根由 $PSScriptRoot 上溯两级得到，解释器按
    ALLIN_PYTHON → 仓内 .venv → PATH 逐级探测；零盘符字面量（g01 门禁）。
  - 不依赖 WorkBuddy / npm / bash：盘点器本体是纯标准库 Python。
  - 运行日志按日落 $ALLIN_LOG_DIR（缺省本机应用数据目录），
    结构化留痕由 monthly_audit.py 落 tools/gate/audit/monthly-audit-runs.jsonl。
  - 月度语义由 Python 侧的幂等守卫保证（每周一触发 + 同月已 ok 则 skip）；
    -Force 可强制重跑，用于验收或修完复验。

.NOTES
  兼容 Windows PowerShell 5.1；本文件不自动注册，注册见同目录 register-tasks.ps1，
  注册动作由人在各机执行（ADR-0010 部署守护面同款纪律）。
  中文注释 ⇒ 必须 UTF-8 BOM（check_ps1_bom 门禁）。
#>
param(
  # 仓库根；缺省按脚本位置自发现（跨机 clone 后无需改路径）
  [string]$RepoRoot = $env:ALLIN_ROOT,
  # 强制重跑（忽略月度幂等守卫）
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'tools\deploy\monthly_audit.py'))) {
  Write-Error "monthly-audit-task: 仓根缺 tools\deploy\monthly_audit.py：$RepoRoot"
  exit 3
}

# 与 scripts/run_all_gates.sh 同源的解析链；路径由 env / 文件系统给出，不写死盘符。
$py = $env:ALLIN_PYTHON
if (-not $py) {
  foreach ($cand in @((Join-Path $RepoRoot '.venv\Scripts\python.exe'),
                      (Join-Path $RepoRoot '.venv\bin\python'))) {
    if (Test-Path -LiteralPath $cand) { $py = $cand; break }
  }
}
if (-not $py) {
  $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
  if (-not $cmd) { $cmd = Get-Command python -ErrorAction SilentlyContinue }
  if (-not $cmd) {
    Write-Error 'monthly-audit-task: 找不到 Python 3.9+；请 setx ALLIN_PYTHON <解释器>'
    exit 3
  }
  $py = $cmd.Source
}

$logDir = $env:ALLIN_LOG_DIR
if (-not $logDir) { $logDir = Join-Path $env:LOCALAPPDATA 'allin\logs' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("monthly-audit-" + (Get-Date -Format 'yyyy-MM-dd') + ".log")

$script = Join-Path $PSScriptRoot 'monthly_audit.py'
$pyArgs = @($script, '--repo-root', $RepoRoot)
if ($Force) { $pyArgs += '--force' }

# 两处编码纪律（2026-11-07 包装器实跑踩到，已修复）：
#  ① 本机控制台 OutputEncoding 是 gb2312（OEM 码页），而 monthly_audit.py 输出 UTF-8；
#     PowerShell 会按 gb2312 解码子进程 stdout，中文当场变成「SKIP锛?026-11」，
#     之后再写进日志也救不回来。故调用前临时切 UTF-8，拿到输出后立刻恢复。
#  ② PS 5.1 的 Tee-Object / Out-File 默认写 UTF-16LE 且不接受 -Encoding，
#     故文本日志改用 AppendAllText 显式 UTF-8（无 BOM），PS 5.1 / 7 行为一致。
$prevOut = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# EAP=Stop 时原生命令的 stderr 会抛 NativeCommandError（backup-allin.ps1 已踩过），
# 故这一段临时降为 Continue；退出码用 $LASTEXITCODE 原样透传给计划任务。
$ErrorActionPreference = 'Continue'
$lines = & $py @pyArgs 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

[Console]::OutputEncoding = $prevOut
$lines | ForEach-Object { $_.ToString() }
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$body = ($lines | ForEach-Object { "[$stamp] " + $_.ToString() }) -join "`n"
if ($body) {
  [System.IO.File]::AppendAllText($logFile, $body + "`n",
    [System.Text.UTF8Encoding]::new($false))
}
exit $code
