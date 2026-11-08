<#
.SYNOPSIS
  allin 备份恢复（tools/deploy · B3 闭环 · 2026-11-08 审查）

.DESCRIPTION
  读最新（或 -SourceDir 指定）备份目录的 manifest.json，先校验逐文件 sha256
  一致性，再 robocopy /MIR 还原 platform/data 与 website/data。敏感材质排除清单
  来自同目录 exclusion-policy.ps1（单一真相源，backup / restore / drill 三方共用）；
  keys/ 与 seed-accounts.json / *.pem / *.key / .env / credentials.json 等由
  /XD /XF 按备份同口径排除——它们走独立灾备通道，恢复不碰它们，/MIR 也不删它们。

  纪律（对齐 backup-allin.ps1）：
  - 本脚本入仓（无密钥、MIT-0）；备份根 / 仓库根一律参数或 env 注入，禁盘符字面量。
  - 排除清单来自 exclusion-policy.ps1（单一真相源），platform 与 website 两条 robocopy
    共用同一 $excludeArgs，与 backup 完全对称；新增敏感材质只改策略文件一处。
  - status 准入：只认 manifest.status=ok 的备份，缺失或非 ok 一律 fail-closed 拒绝恢复。
  - 恢复前先校验 sha256：任一项不一致即拒绝恢复（备份可能损坏），fail-loud。
  - 还原后复核（3b）：只按 manifest.files 单向核对目标侧存在性与 sha256，不反向枚举
    目标目录；畸形清单项/未知前缀直接 Fail 不吞，任一目标侧缺失或不一致即拒绝判定成功。
  - 兼容 Windows PowerShell 5.1（计划任务缺省解释器）：全脚本无 6+ 语法。
#>
param(
  # 备份根（注册期实参，如 <BACKUP_ROOT>）；不给盘符默认值——未提供时 fail-loud
  [string]$BackupRoot = $env:ALLIN_BACKUP_ROOT,
  # 仓库根（ALLIN_ROOT）
  [string]$RepoRoot   = $env:ALLIN_ROOT,
  # 指定备份目录（缺省取 BackupRoot 下最新 yyyy-mm-dd）
  [string]$SourceDir  = '',
  # 仅校验 sha256，不执行 robocopy
  [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "restore-allin: $Message" }
function Write-Log([string]$Message) {
  Write-Output ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
}

if (-not $BackupRoot) {
  Fail '备份根未提供：请 setx ALLIN_BACKUP_ROOT <BACKUP_ROOT> 或传 -BackupRoot <BACKUP_ROOT>'
}
if (-not $RepoRoot) {
  Fail '仓库根未提供：请 setx ALLIN_ROOT <REPO_ROOT> 或传 -RepoRoot <REPO_ROOT>'
}

# 敏感材质排除清单（单一真相源）：三方共同 dot-source，缺文件即 fail-loud；
# 须在 VerifyOnly 早退之前加载，保证任何分支口径一致。
$policy = Join-Path $PSScriptRoot 'exclusion-policy.ps1'
if (-not (Test-Path -LiteralPath $policy)) { Fail '排除策略文件缺失：exclusion-policy.ps1' }
. $policy
$excludeArgs = Get-AllinExcludeArgs

# ---------- 0) 定位备份目录 ----------
$src = $SourceDir
if (-not $src) {
  $cands = @(Get-ChildItem -LiteralPath $BackupRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } | Sort-Object Name -Descending)
  if ($cands.Count -eq 0) { Fail "备份根 $BackupRoot 下无 yyyy-mm-dd 备份目录" }
  $src = $cands[0].FullName
}
$manifestPath = Join-Path $src 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { Fail "备份目录 $src 无 manifest.json" }

$manifest = $null
try { $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { Fail "manifest.json 解析失败：$_" }

Write-Log "恢复源：$src（status=$($manifest.status) fileCount=$($manifest.fileCount)）"

# ---------- 0b) status 准入：只认 status=ok 的备份（fail-closed） ----------
# PS 里属性缺失取到 $null，-ne 'ok' 成立 ⇒ 自动拒绝；无 6+ 语法。
if ($manifest.status -ne 'ok') {
  Fail "备份 manifest.status 非 ok（实为 '$($manifest.status)'），拒绝恢复：只认 status=ok 的备份"
}

# ---------- 1) 校验 sha256（恢复前先证明备份自洽） ----------
$bad = 0
foreach ($f in $manifest.files) {
  $fp = Join-Path $src $f.path
  if (-not (Test-Path -LiteralPath $fp)) { Write-Log "  缺失：$($f.path)"; $bad++; continue }
  $h = (Get-AllinSha256 -LiteralPath $fp)
  if ($h -ne $f.sha256) { Write-Log "  校验失败：$($f.path) 期望 $($f.sha256) 实得 $h"; $bad++ }
}
if ($bad -gt 0) { Fail "$bad 个文件 sha256 不一致，拒绝恢复（备份可能损坏）" }
Write-Log "sha256 校验通过：$($manifest.files.Count) 个文件"

if ($VerifyOnly) { Write-Log 'VerifyOnly：跳过 robocopy。'; exit 0 }

# ---------- 2) 还原（robocopy /MIR，敏感材质排除，与备份同口径） ----------
# 两条 robocopy 共用同一 $excludeArgs（来自 exclusion-policy.ps1）：/XD keys 与 /XF
# seed-accounts.json / credentials.json / *.pem / *.key / .env 等按备份同口径排除；
# 独立灾备通道材质还原不碰，/MIR 也不会因排除项而删除目标侧现存密钥。
$ErrorActionPreference = 'Continue'
& robocopy (Join-Path $src 'platform-data') (Join-Path $RepoRoot 'platform\data') /MIR @excludeArgs /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcPlatform = $LASTEXITCODE
& robocopy (Join-Path $src 'website-data') (Join-Path $RepoRoot 'website\data') /MIR @excludeArgs /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcWebsite = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$copyOk = ($rcPlatform -lt 8) -and ($rcWebsite -lt 8)
Write-Log ("还原完成：platform-data 退出码 $rcPlatform ｜ website-data 退出码 $rcWebsite（>=8 为失败）")

# ---------- 3) 收口（fail-loud） ----------
if (-not $copyOk) {
  Write-Log "恢复失败：robocopy 退出码 >=8（platform=$rcPlatform website=$rcWebsite）"
  exit 1
}

# ---------- 3b) 还原后复核（目标侧 vs manifest，单向、fail-loud） ----------
# 只按 $manifest.files 正向核对目标侧，绝不反向枚举目标目录——独立灾备通道的
# keys/ 与 seed-accounts.json 等被 /XD /XF 排除、本就不在 manifest 里，反向枚举
# 会把它们当成「多出来的文件」误判或误删。畸形清单项/未知前缀直接 Fail，不 continue 吞掉。
$verifyBad = 0
foreach ($f in $manifest.files) {
  $parts = ($f.path -replace '/', '\') -split '\\', 2
  if ($parts.Count -lt 2) {
    Fail "manifest 清单项无法解析：$($f.path)（清单被改坏或备份被篡改）"
  }
  if ($parts[0] -eq 'platform-data') {
    $targetRoot = Join-Path $RepoRoot 'platform\data'
  }
  elseif ($parts[0] -eq 'website-data') {
    $targetRoot = Join-Path $RepoRoot 'website\data'
  }
  else {
    Fail "manifest 清单项前缀未知：$($f.path)（期望 platform-data / website-data）"
  }
  $target = Join-Path $targetRoot $parts[1]
  if (-not (Test-Path -LiteralPath $target)) {
    Write-Log "  目标侧缺失：$($f.path)"
    $verifyBad++
    continue
  }
  $h = (Get-AllinSha256 -LiteralPath $target)
  if ($h -ne $f.sha256) {
    Write-Log "  目标侧校验失败：$($f.path) 期望 $($f.sha256) 实得 $h"
    $verifyBad++
  }
}
if ($verifyBad -gt 0) {
  Fail "还原后复核失败：$verifyBad 个文件目标侧缺失或 sha256 与 manifest 不一致"
}
Write-Log "还原后复核通过：$($manifest.files.Count) 个文件目标侧 sha256 与 manifest 一致"

Write-Log "恢复成功：$src → $RepoRoot"
exit 0
