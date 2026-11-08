<#
.SYNOPSIS
  allin 每日数据备份 + 轮转（tools/deploy · P3 部署实施方案 §3 落地物）

.DESCRIPTION
  执行链：website 库 wal_checkpoint(TRUNCATE) → robocopy /MIR platform/data 与 website/data
  → manifest.json（逐文件 sha256 + robocopy 退出码 <8 判定）→ 按目录名 7 天轮转 → 运行日志。

  纪律：
  - 本脚本入仓（无密钥、MIT-0）；备份根 / 仓库根一律 env 或参数注入，禁止盘符字面量（g01 门禁）。
  - 敏感材质排除清单来自同目录 exclusion-policy.ps1（单一真相源）：backup / restore / drill
    三方共同 dot-source；platform 与 website 两条 robocopy 共用同一 $excludeArgs，彻底对称。
  - keys/ 由 /XD 排除，seed-accounts.json / credentials.json / *.pem / *.key / .env 等由 /XF 排除；
    密钥与种子口令绝不进 robocopy 主备份，走独立灾备通道 = website 的 npm run backup-key
    （0600 + 口令包 + 月度恢复演练），与 robocopy 主备份物理隔离。新增敏感材质只改策略文件一处。
  - robocopy 退出码 0-7 = 成功（含复制），>=8 = 失败——不能按传统退出码判成败。

.NOTES
  计划任务注册见同目录 register-tasks.ps1；手动用法见同目录 README.md。
  兼容 Windows PowerShell 5.1（计划任务缺省解释器）：全脚本无 6+ 语法。
#>
param(
  # 备份根（注册期实参，如 <BACKUP_ROOT>）；不给盘符默认值——未提供时 fail-loud 给注册指引
  [string]$BackupRoot = $env:ALLIN_BACKUP_ROOT,
  # 仓库根（ALLIN_ROOT）
  [string]$RepoRoot   = $env:ALLIN_ROOT,
  # 备份保留份数（按目录名轮转）
  [int]$KeepDays = 7,
  # 运行日志保留天数（拍板口径：14 天）
  [int]$LogKeepDays = 14,
  # 降级路径：跳过 wal_checkpoint。仅当 website 已停止、确认无 WAL 写入时使用；manifest 会如实标记
  [switch]$SkipCheckpoint
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "backup-allin: $Message" }

# ---------- 0) 入参与环境（fail-loud，给注册指引） ----------
if (-not $BackupRoot) {
  Fail ('备份根未提供：请 setx ALLIN_BACKUP_ROOT <BACKUP_ROOT> 或传 -BackupRoot <BACKUP_ROOT>' +
        '（注册期实参，盘符只进任务计划参数不进仓内代码；见 tools/deploy/README.md 与 g01 纪律）')
}
if (-not $RepoRoot) {
  Fail '仓库根未提供：请 setx ALLIN_ROOT <REPO_ROOT> 或传 -RepoRoot <REPO_ROOT>'
}
$platformData = Join-Path $RepoRoot 'platform\data'
$websiteData  = Join-Path $RepoRoot 'website\data'
foreach ($p in @($platformData, $websiteData)) {
  if (-not (Test-Path -LiteralPath $p)) { Fail "源目录不存在: $p（检查 ALLIN_ROOT 是否指到仓库根）" }
}

# 敏感材质排除清单（单一真相源）：三方共同 dot-source，缺文件即 fail-loud
$policy = Join-Path $PSScriptRoot 'exclusion-policy.ps1'
if (-not (Test-Path -LiteralPath $policy)) { Fail '排除策略文件缺失：exclusion-policy.ps1' }
. $policy
$excludeArgs = Get-AllinExcludeArgs

# 运行日志目录：ALLIN_LOG_DIR 优先，缺省回退到本机应用数据目录（不写盘符）
$logDir = $env:ALLIN_LOG_DIR
if (-not $logDir) { $logDir = Join-Path $env:LOCALAPPDATA 'allin\logs' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("backup-" + (Get-Date -Format 'yyyy-MM-dd') + ".log")

function Write-Log([string]$Message) {
  $line = ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message)
  Write-Output $line
  Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
}

Write-Log "开始备份：repo=$RepoRoot backup=$BackupRoot"

# ---------- 1) WAL checkpoint（把 WAL 合回主库再拷，快照确定性；website 在线可执行，免停机） ----------
# PS 5.1 陷阱：EAP=Stop 时原生命令 stderr 重定向会抛 NativeCommandError——node:sqlite 在 22.x
# 会往 stderr 打 experimental 警告，故本段先切回 Continue 再恢复。
$checkpoint = 'skipped'
$siteDb = Join-Path $websiteData 'site.db'
if (-not (Test-Path -LiteralPath $siteDb)) {
  $checkpoint = 'skipped (site.db 不存在，无库可 checkpoint)'
  Write-Log $checkpoint
}
elseif ($SkipCheckpoint) {
  $checkpoint = 'skipped (-SkipCheckpoint 显式指定；前提：website 已停止或确认无 WAL 写入)'
  Write-Log $checkpoint
}
else {
  $ErrorActionPreference = 'Continue'
  $ck = & node -e "const{DatabaseSync}=require('node:sqlite');const db=new DatabaseSync(process.argv[1]);db.exec('PRAGMA wal_checkpoint(TRUNCATE)');db.close();console.log('checkpoint-ok');" $siteDb 2>&1
  $ckCode = $LASTEXITCODE
  $ErrorActionPreference = 'Stop'
  if ($ckCode -ne 0) {
    # 降级路径说明：node 缺失或版本 <22.5（无 node:sqlite）在此失败。
    # 处置：升级 Node >= 22.5；或在确认 website 停止的前提下改用 -SkipCheckpoint（manifest 如实标记）。
    Fail ("wal_checkpoint 失败（node 需 >=22.5 才有 node:sqlite）。node 输出：" + ($ck | Out-String))
  }
  $checkpoint = 'ok'
  Write-Log 'wal_checkpoint(TRUNCATE) 完成'
}

# ---------- 2) robocopy /MIR（退出码 0-7=成功、>=8=失败） ----------
$stamp = Get-Date -Format 'yyyy-MM-dd'
$dest  = Join-Path $BackupRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$ErrorActionPreference = 'Continue'
# 两条 robocopy 共用同一 $excludeArgs（来自 exclusion-policy.ps1）：platform 与 website 同口径，
# 与 restore 完全对称；platform 分支因此也获得 /XF，杜绝 platform/data 下敏感材质进备份包与 manifest。
& robocopy $platformData (Join-Path $dest 'platform-data') /MIR @excludeArgs /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcPlatform = $LASTEXITCODE
& robocopy $websiteData (Join-Path $dest 'website-data') /MIR @excludeArgs /NFL /NDL /NJH /R:2 /W:5 /NP | Out-Null
$rcWebsite = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$copyOk = ($rcPlatform -lt 8) -and ($rcWebsite -lt 8)
Write-Log ("robocopy 完成：platform-data 退出码 $rcPlatform ｜ website-data 退出码 $rcWebsite（>=8 为失败）")

# ---------- 3) manifest.json：逐文件 sha256 + 退出码 + 成败标记（失败现场也落 manifest） ----------
# manifest 自身不进哈希清单（排除上一轮残留，避免 fileCount 虚增）
$manifestPath = Join-Path $dest 'manifest.json'
# 相对路径计算：以 $dest 为基准取相对路径。先剥除可能的长路径前缀 \\?\（路径 >260 字符时
# .NET/PowerShell 会给 FullName 加此前缀，而 $dest 字符串无此前缀，旧式
# Substring($dest.Length + 1) 会截错长度、产出如 "08\platform-data\a.txt" 的畸形前缀
# ⇒ 恢复预校验判定缺失 ⇒ N-02 在 CI runner（深临时目录，路径超 260）失败、本地短路径却通过。
# 剥前缀 + 去一个前导分隔符后，结果恒为 "platform-data\a.txt" / "website-data\a.txt"，
# 与 restore-allin.ps1 期望一致。）
function RelativeTo-Dest([string]$abs, [string]$base) {
  $a = $abs
  if ($a.StartsWith('\\?\')) { $a = $a.Substring(4) }
  $b = $base
  if ($b.StartsWith('\\?\')) { $b = $b.Substring(4) }
  if ($a.Length -gt $b.Length -and $a.StartsWith($b)) {
    $rel = $a.Substring($b.Length)
    if ($rel.StartsWith('\') -or $rel.StartsWith('/')) { $rel = $rel.Substring(1) }
    return $rel
  }
  # 兜底：无法相对化（路径不基于 $dest）⇒ fail-loud，不产畸形清单项
  throw "backup-allin: 无法将文件归一到备份目录：$abs（不基于 $base）"
}
$files = @(Get-ChildItem -LiteralPath $dest -Recurse -File |
  Where-Object { $_.FullName -ne $manifestPath } | ForEach-Object {
  [ordered]@{
    path   = RelativeTo-Dest $_.FullName $dest
    bytes  = $_.Length
    sha256 = (Get-AllinSha256 -LiteralPath $_.FullName)
  }
})
$manifest = [ordered]@{
  date         = $stamp
  completedAt  = (Get-Date -Format 'o')
  status       = $(if ($copyOk) { 'ok' } else { 'failed' })
  checkpoint   = $checkpoint
  keepDays     = $KeepDays
  robocopyExit = [ordered]@{ 'platform-data' = $rcPlatform; 'website-data' = $rcWebsite }
  fileCount    = $files.Count
  files        = $files
}
# 显式 UTF-8 BOM 写出（PS 5.1/7 双版本行为一致）
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding $true))
Write-Log ("manifest 写入完成：$($files.Count) 个文件，status=$($manifest.status)，checkpoint=$checkpoint")

# ---------- 4) 7 天轮转：按目录名排序删旧（不按 mtime，防 touch 干扰） ----------
# 语义：保留最近 $KeepDays 份（含当日）——对齐 P2 数据模型 §5.1「仅保留最近 7 份」。
# 当日目录排序在最前、天然落在保留窗口内；$KeepDays < 1 属配置错误，fail-loud。
if ($KeepDays -lt 1) { Fail "KeepDays=$KeepDays 不合法（须 >= 1，保留份数含当日）" }
$expired = @(Get-ChildItem -LiteralPath $BackupRoot -Directory |
  Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
  Sort-Object Name -Descending | Select-Object -Skip $KeepDays)
foreach ($d in $expired) {
  Remove-Item -LiteralPath $d.FullName -Recurse -Force -Confirm:$false
  Write-Log "轮转删除过期备份目录: $($d.Name)"
}

# ---------- 5) 运行日志轮转（14 天） ----------
$staleLogs = @(Get-ChildItem -LiteralPath $logDir -File -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$LogKeepDays) })
foreach ($f in $staleLogs) { Remove-Item -LiteralPath $f.FullName -Force -Confirm:$false }

# ---------- 6) 收口（fail-loud：robocopy >=8 时任务 Last Task Result 非 0） ----------
if (-not $copyOk) {
  Write-Log "备份失败：robocopy 退出码 >=8（platform=$rcPlatform website=$rcWebsite）；manifest 已标 failed"
  exit 1
}
Write-Log "备份成功：$dest（$($files.Count) 文件，manifest status=ok）"
exit 0
