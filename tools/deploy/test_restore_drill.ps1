<#
.SYNOPSIS
  备份恢复演练（B3 闭环 · 2026-11-08 审查）：造假 → 备份 → 篡改 → 恢复 → 断言一致。

.DESCRIPTION
  在临时目录造一份 platform/data + website/data 并记录逐文件 sha256；
  调 backup-allin.ps1 备份；篡改（删一个文件 + 改一个文件）；调 restore-allin.ps1
  恢复；断言恢复后 sha256 与基线逐字节一致。证明「备份可还原、数据耐久性可验证」。

  纪律（对齐 backup/restore-allin.ps1）：零密钥、零盘符字面量、PS 5.1 兼容。
  退出码：0 = 演练通过；1 = 失败（供 run_all_gates.sh / 计划任务判定）。
#>
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { Write-Output ("[FAIL] " + $Message); exit 1 }
function Sha256([string]$p) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }

$stamp = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + $PID
$root   = Join-Path $env:TEMP ("allin-restore-drill-$stamp")
$repo   = Join-Path $root 'repo'
$backup = Join-Path $root 'Backup'

New-Item -ItemType Directory -Force -Path (Join-Path $repo 'platform\data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repo 'website\data')  | Out-Null

# ---------- 1) 造假数据 + 记录基线 sha256 ----------
$pa = Join-Path $repo 'platform\data\a.txt'
$pb = Join-Path $repo 'platform\data\b.txt'
$wa = Join-Path $repo 'website\data\w.txt'
Set-Content -LiteralPath $pa -Value 'alpha' -Encoding utf8
Set-Content -LiteralPath $pb -Value 'beta'  -Encoding utf8
Set-Content -LiteralPath $wa -Value 'omega' -Encoding utf8

$baseline = @{}
foreach ($f in @($pa, $pb, $wa)) { $baseline[$f] = (Sha256 $f) }

# ---------- 2) 备份（跳过 wal_checkpoint，避免依赖 node:sqlite） ----------
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'backup-allin.ps1') `
  -RepoRoot $repo -BackupRoot $backup -SkipCheckpoint
if ($LASTEXITCODE -ne 0) { Fail "backup-allin.ps1 失败（exit=$LASTEXITCODE）" }
Write-Output '[ok] 备份完成'

# ---------- 3) 篡改：删一个、改一个 ----------
Remove-Item -LiteralPath $pb -Force
Set-Content -LiteralPath $wa -Value 'TAMPERED' -Encoding utf8

# ---------- 4) 恢复（取最新备份） ----------
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'restore-allin.ps1') `
  -RepoRoot $repo -BackupRoot $backup
if ($LASTEXITCODE -ne 0) { Fail "restore-allin.ps1 失败（exit=$LASTEXITCODE）" }
Write-Output '[ok] 恢复完成'

# ---------- 5) 断言一致 ----------
$ok = $true
foreach ($f in @($pa, $pb, $wa)) {
  if (-not (Test-Path -LiteralPath $f)) { Write-Output ("[FAIL] 恢复后缺失：$f"); $ok = $false; continue }
  $h = (Sha256 $f)
  if ($h -ne $baseline[$f]) {
    Write-Output ("[FAIL] sha256 不一致：$f 期望 $($baseline[$f]) 实得 $h")
    $ok = $false
  }
  else { Write-Output ("[ok] 一致：$f") }
}

# 清理临时目录
Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue

if (-not $ok) { Fail '恢复演练未通过：存在不一致文件' }
Write-Output '[PASS] 备份恢复演练通过：篡改后的数据已还原至备份基线'
exit 0
