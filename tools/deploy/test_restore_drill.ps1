<#
.SYNOPSIS
  备份恢复演练（B3 闭环 · 2026-11-08 审查，安全域复评补充）：
  造假 → 备份 → 断言备份排除 → 篡改 → 恢复 → 断言数据一致 + 密钥通道独立。

.DESCRIPTION
  在临时目录造一份 platform/data + website/data（含三个假密钥夹具：两个 keys/secret.key
  与 seed-accounts.json，均为演练专用假值、零真实凭据），记录普通文件逐字节 sha256 基线；
  调 backup-allin.ps1 备份；先断言备份包内不含任何 keys 与 seed-accounts.json（证明
  /XD keys + /XF seed-accounts.json 排除生效，与 restore 排除口径对称）；
  篡改（删一个普通文件 + 改一个普通文件 + 把三个密钥夹具独立更新为新值）；
  调 restore-allin.ps1 恢复；断言普通文件 sha256 与基线一致，且三个密钥夹具
  仍存在、内容等于篡改后的值（证明 restore 的排除让 /MIR 既不删也不覆盖目标侧密钥）。
  收口为 fail-closed：单一 $drillPass 默认 $false，仅当 2b 排除断言已执行、普通文件
  sha256 一致、密钥通道 3 项断言全部执行且全过、结论为「密钥通道独立」时才置 $true；
  判据写 -not $drillPass，故变量缺失（$null）仍判失败，无需「守卫的守卫」。
  PASS 文案由实际计数与结论生成，杜绝「写了不跑」的静默假绿。

  纪律（对齐 backup/restore-allin.ps1）：零密钥、零盘符字面量、PS 5.1 兼容、UTF-8 BOM。
  退出码：0 = 演练通过；1 = 失败（供 run_all_gates.sh / 计划任务判定）。
#>
$ErrorActionPreference = 'Stop'

# 演练门禁（fail-closed）：默认拒绝。$drillPass 仅在收口处所有断言条件同时满足时置 $true。
# 收口判据用 -not $drillPass——即便本行被误删、变量为 $null，-not $null 仍为 True → Fail。
$drillPass = $false
# 各断言段「已执行」标志与计数：段外初始化，段跑完才置位（不依赖 $null 隐式行为）。
$backupExclusionChecked = $false
$keyAssertionCount      = 0
$keyAssertionExpected   = 3
$keyConclusion          = '密钥通道未通过'

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
# 假密钥夹具（演练专用，零真实凭据）：验证 backup 排除与 restore 密钥通道独立性
$pk   = Join-Path $repo 'platform\data\keys\secret.key'
$wk   = Join-Path $repo 'website\data\keys\secret.key'
$seed = Join-Path $repo 'website\data\seed-accounts.json'
$origPlatform   = 'PLATFORM-KEY-V1'
$origWebsite    = 'WEBSITE-KEY-V1'
$origSeed       = '{"seed":"ORIGINAL"}'
$tamperPlatform = 'PLATFORM-KEY-V2'
$tamperWebsite  = 'WEBSITE-KEY-V2'
$tamperSeed     = '{"seed":"TAMPERED"}'

New-Item -ItemType Directory -Force -Path (Join-Path $repo 'platform\data\keys') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repo 'website\data\keys')  | Out-Null
Set-Content -LiteralPath $pa -Value 'alpha' -Encoding utf8
Set-Content -LiteralPath $pb -Value 'beta'  -Encoding utf8
Set-Content -LiteralPath $wa -Value 'omega' -Encoding utf8
Set-Content -LiteralPath $pk   -Value $origPlatform -Encoding utf8
Set-Content -LiteralPath $wk   -Value $origWebsite  -Encoding utf8
Set-Content -LiteralPath $seed -Value $origSeed     -Encoding utf8

$baseline = @{}
foreach ($f in @($pa, $pb, $wa)) { $baseline[$f] = (Sha256 $f) }

# ---------- 2) 备份（跳过 wal_checkpoint，避免依赖 node:sqlite） ----------
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'backup-allin.ps1') `
  -RepoRoot $repo -BackupRoot $backup -SkipCheckpoint
if ($LASTEXITCODE -ne 0) { Fail "backup-allin.ps1 失败（exit=$LASTEXITCODE）" }
Write-Output '[ok] 备份完成'

# ---------- 2b) 断言：备份侧排除（/XD keys + /XF seed-accounts.json 生效，密钥不进备份包） ----------
# /XD keys 生效时 robocopy 不会创建 keys 目录、/XF 生效时不会复制 seed-accounts.json；
# 目录或文件任一出现即证明排除口径失效（未修复的 backup 会漏拷 platform/data/keys 明文）。
$latestBak = Get-ChildItem -LiteralPath $backup -Directory |
  Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
  Sort-Object Name -Descending | Select-Object -First 1
if (-not $latestBak) { Fail "备份根下无 yyyy-MM-dd 备份目录：$backup" }
$forbidden = @(
  (Join-Path $latestBak.FullName 'platform-data\keys'),
  (Join-Path $latestBak.FullName 'platform-data\keys\secret.key'),
  (Join-Path $latestBak.FullName 'website-data\keys'),
  (Join-Path $latestBak.FullName 'website-data\keys\secret.key'),
  (Join-Path $latestBak.FullName 'website-data\seed-accounts.json')
)
$leaked = @($forbidden | Where-Object { Test-Path -LiteralPath $_ })
if ($leaked.Count -gt 0) {
  Fail ("备份包含密钥/种子口令材质：排除口径失效（泄漏项：" + ($leaked -join '、') + "）")
}
Write-Output '[ok] 备份侧排除：platform-data / website-data 的 keys 与 seed-accounts.json 均未进备份包'
$backupExclusionChecked = $true

# ---------- 3) 篡改：删一个、改一个 + 模拟密钥通道独立更新（备份后） ----------
Remove-Item -LiteralPath $pb -Force
Set-Content -LiteralPath $wa -Value 'TAMPERED' -Encoding utf8
Set-Content -LiteralPath $pk   -Value $tamperPlatform -Encoding utf8
Set-Content -LiteralPath $wk   -Value $tamperWebsite  -Encoding utf8
Set-Content -LiteralPath $seed -Value $tamperSeed     -Encoding utf8

# ---------- 4) 恢复（取最新备份） ----------
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'restore-allin.ps1') `
  -RepoRoot $repo -BackupRoot $backup
if ($LASTEXITCODE -ne 0) { Fail "restore-allin.ps1 失败（exit=$LASTEXITCODE）" }
Write-Output '[ok] 恢复完成'

# ---------- 5) 断言一致（普通文件 sha256 基线，语义不变） ----------
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

# ---------- 6) 断言：密钥通道独立性 ----------
# restore 的 /XD keys + /XF seed-accounts.json 应让 /MIR 既不删除也不覆盖目标侧密钥：
# 篡改后的密钥值必须原样保留；若被还原成 ORIGINAL 或文件消失 → 排除口径失效 → Fail。
$keyChecks = @(
  @{ path = $pk;   label = 'platform/data/keys/secret.key';   expected = $tamperPlatform },
  @{ path = $wk;   label = 'website/data/keys/secret.key';    expected = $tamperWebsite },
  @{ path = $seed; label = 'website/data/seed-accounts.json'; expected = $tamperSeed }
)
foreach ($k in $keyChecks) {
  $keyAssertionCount++   # 循环体最前面递增：成功/失败/continue 都算「这一项断言确实跑过」
  if (-not (Test-Path -LiteralPath $k.path)) {
    Write-Output ("[FAIL] 密钥通道被破坏：$($k.label) 恢复后消失（/MIR 不应删除独立通道材质）")
    $ok = $false
    continue
  }
  # 去 UTF-8 BOM 字符（兼容 PS 5.1 写带 BOM / PS 7 写无 BOM）与首尾换行后精确比较
  $actual = (Get-Content -LiteralPath $k.path -Raw -Encoding UTF8).TrimStart([char]0xFEFF).Trim()
  if ($actual -ne $k.expected) {
    Write-Output ("[FAIL] 密钥通道被覆盖：$($k.label) 期望 $($k.expected) 实得 $actual（被还原/覆写即证明排除口径失效）")
    $ok = $false
  }
  else { Write-Output ("[ok] 密钥通道独立：$($k.label) 保持篡改值，restore 未删未覆盖") }
}
if ($ok -and $keyAssertionCount -eq 3) {
  $keyConclusion = '密钥通道独立'
}

# 清理临时目录
Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue

# ---------- 收口（fail-closed：默认拒绝，显式授权） ----------
# 仅当 2b 已执行、5 段 $ok、6 段 3 项全跑（字面量 3）且结论为「密钥通道独立」时置 $true。
# 比较一律用字面量/显式布尔值；变量缺失（$null）或取值漂移都不会让条件成立。
if ($backupExclusionChecked -eq $true -and
    $ok -eq $true -and
    $keyAssertionCount -eq 3 -and
    $keyConclusion -eq '密钥通道独立') {
  $drillPass = $true
}
if (-not $drillPass) {
  Fail '演练门禁未通过：断言未完整执行或存在失败，拒绝判定通过'
}
# PASS 只在显式授权且结论正确时打印，项数由实际计数生成，绝不出现「未通过」却 PASS。
if ($drillPass -eq $true -and $keyConclusion -eq '密钥通道独立') {
  Write-Output ("[PASS] 备份恢复演练通过：数据还原至备份基线，且" + $keyConclusion + "（断言 " + $keyAssertionCount + "/" + $keyAssertionExpected + " 项通过；备份排除 + 恢复不删不覆盖）")
}
else {
  Fail '演练门禁与结论不一致，拒绝判定通过'
}
exit 0
