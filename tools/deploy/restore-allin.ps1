<#
.SYNOPSIS
  allin 备份恢复（tools/deploy · B3 闭环 · 2026-11-08 审查）

.DESCRIPTION
  读最新（或 -SourceDir 指定）备份目录的 manifest.json，先校验逐文件 sha256
  一致性，再 robocopy /MIR 还原 platform/data 与 website/data。密钥（keys）
  与种子口令（seed-accounts.json）按备份同口径排除——它们是独立灾备通道，
  恢复不碰它们。

  纪律（对齐 backup-allin.ps1）：
  - 本脚本入仓（无密钥、MIT-0）；备份根 / 仓库根一律参数或 env 注入，禁盘符字面量。
  - 恢复前先校验 sha256：任一项不一致即拒绝恢复（备份可能损坏），fail-loud。
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

# ---------- 1) 校验 sha256（恢复前先证明备份自洽） ----------
$bad = 0
foreach ($f in $manifest.files) {
  $fp = Join-Path $src $f.path
  if (-not (Test-Path -LiteralPath $fp)) { Write-Log "  缺失：$($f.path)"; $bad++; continue }
  $h = (Get-FileHash -LiteralPath $fp -Algorithm SHA256).Hash
  if ($h -ne $f.sha256) { Write-Log "  校验失败：$($f.path) 期望 $($f.sha256) 实得 $h"; $bad++ }
}
if ($bad -gt 0) { Fail "$bad 个文件 sha256 不一致，拒绝恢复（备份可能损坏）" }
Write-Log "sha256 校验通过：$($manifest.files.Count) 个文件"

if ($VerifyOnly) { Write-Log 'VerifyOnly：跳过 robocopy。'; exit 0 }

# ---------- 2) 还原（robocopy /MIR，密钥/种子口令排除，与备份同口径） ----------
# /XD keys + /XF seed-accounts.json：密钥/种子口令走独立灾备通道，
# 还原不碰它们，/MIR 也不会因排除项而删除目标侧现存密钥。
$ErrorActionPreference = 'Continue'
& robocopy (Join-Path $src 'platform-data') (Join-Path $RepoRoot 'platform\data') /MIR /XD keys /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcPlatform = $LASTEXITCODE
& robocopy (Join-Path $src 'website-data') (Join-Path $RepoRoot 'website\data') /MIR /XD keys /XF seed-accounts.json /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcWebsite = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$copyOk = ($rcPlatform -lt 8) -and ($rcWebsite -lt 8)
Write-Log ("还原完成：platform-data 退出码 $rcPlatform ｜ website-data 退出码 $rcWebsite（>=8 为失败）")

# ---------- 3) 收口（fail-loud） ----------
if (-not $copyOk) {
  Write-Log "恢复失败：robocopy 退出码 >=8（platform=$rcPlatform website=$rcWebsite）"
  exit 1
}
Write-Log "恢复成功：$src → $RepoRoot"
exit 0
