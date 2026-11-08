<#
.SYNOPSIS
  ALLIN-monthly-restore-drill 计划任务包装器（审查残留 #21「月度恢复演练调度」闭环，2026-11-08）。
  每月把 tools/deploy/test_restore_drill.ps1 当子进程真跑一次，结构化留痕 + 文本日志 +
  退出码透传；月度语义由「同月已 ok 则 skip」幂等守卫保证（触发器仍是每周一）。

.DESCRIPTION
  语义边界（必须原样保留，不得删改）：
    这条自动化月度调度只证明「演练脚本逻辑按月回归」——即 test_restore_drill.ps1 的
    备份 / 恢复 / 备份排除 / 密钥通道独立断言按月被真跑过一遍、留痕可查、失败可见。
    它**不替代** P3 §4.1 的人工 SEV1 全链演练：真实灾备切换、密钥唯一通道
    （website 的 backup-key / restore-key）、异地恢复、以及真出事时按剧本人工接管，
    仍需人工按剧本执行并单独验收。绝不把本自动化包装成「灾备已验证 / DR 已闭环」。

  为什么必须子进程：test_restore_drill.ps1 内部用 exit 结束进程；若用 & <script>
  直接调用，exit 会连本包装器一起终止，写不出留痕。故固定用
  `& powershell.exe -NoProfile -ExecutionPolicy Bypass -File <绝对路径>` 后读 $LASTEXITCODE。

  月度语义：New-ScheduledTaskTrigger 没有 -Monthly（见 register-tasks.ps1 任务⑤同款），
  触发器取「每周一」，「每月一次」由本包装器读 tools/gate/audit/restore-drill-runs.jsonl
  里最后一次 status=ok 的 period(yyyy-MM) 实现：同月已 ok 且未 -Force ⇒ 打印 SKIP 并
  exit 0，**skip 不写 JSONL**；上次 failed 不阻断复验；-Force 强制重跑；坏行跳过
  而不是让整份留痕失效；5MB 轮转。

  退出码：0 = 演练通过或 skip；1 = 演练失败；2 = 用法错；3 = 环境错
  （缺脚本 / 缺 powershell.exe / 仓根找不到 / 日志目录不可创建 / 子进程启动失败）。
  Fail 一律 fail-loud：不写 exit 0 兜底，不吞 $LASTEXITCODE。

.NOTES
  兼容 Windows PowerShell 5.1；中文注释 ⇒ 必须 UTF-8 BOM（check_ps1_bom 门禁）。
  本文件不自动注册计划任务；注册见同目录 register-tasks.ps1 的任务⑥，动作由人在各机执行。
  零盘符字面量（g01）：仓根由 -RepoRoot / 自发现给出，日志根由 ALLIN_LOG_DIR 给出。
#>
param(
  # 仓库根；缺省 ALLIN_ROOT，再退 $PSScriptRoot 上溯两级自发现（与 monthly-audit-task.ps1 同口径）
  [string]$RepoRoot = $env:ALLIN_ROOT,
  # 强制重跑（忽略月度幂等守卫）
  [switch]$Force,
  # 捕获多余位置参数 ⇒ 用法错（exit 2），避免静默忽略错误调用
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'

function Fail-Usage([string]$Message) {
  [Console]::Error.WriteLine('[USAGE] restore-drill-task: ' + $Message)
  exit 2
}
function Fail-Env([string]$Message) {
  [Console]::Error.WriteLine('[ENV] restore-drill-task: ' + $Message)
  exit 3
}

# ---------- 0) 用法错（fail-loud，先于环境检查） ----------
if ($ExtraArgs -and $ExtraArgs.Count -gt 0) {
  Fail-Usage ('多余位置参数：' + ($ExtraArgs -join ' ') +
              '；用法：restore-drill-task.ps1 [-RepoRoot <仓根>] [-Force]')
}

# ---------- 1) 环境检查（缺什么就 3，不给「跑不起来却记 ok」的机会） ----------
if (-not $RepoRoot) {
  try { $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..') -ErrorAction Stop).Path }
  catch { Fail-Env ('仓根自发现失败：' + $_.Exception.Message) }
}
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container) -or
    -not (Test-Path -LiteralPath (Join-Path $RepoRoot 'tools\deploy') -PathType Container)) {
  Fail-Env ('仓根找不到（缺 tools\deploy）：' + $RepoRoot)
}

# 四文件同目录校验：test_restore_drill.ps1 顶部靠 $PSScriptRoot dot-source 同目录
# exclusion-policy.ps1（共享排除策略单一真相源），backup-allin.ps1 / restore-allin.ps1 也依赖它；
# 且 drill 以 powershell.exe -File <同目录脚本> 启这两个子进程，子进程 $PSScriptRoot 同样落在
# deploy 目录 —— 即便将来去掉 dot-source，子进程路径也要求四者同在 tools\deploy\。缺任一 → 环境错 exit 3。
# 这是**诊断纵深增强**（把「运行期 exit 1」提前到「环境检查期指名缺哪个文件」），
# 不是假绿修复：真缺文件时 drill 自己 dot-source 失败 exit 1，包装器记 status=failed
# 并如实透传退出码，链路本身已 fail-loud、不存在静默假绿。
$drillFiles = @('test_restore_drill.ps1', 'backup-allin.ps1', 'restore-allin.ps1', 'exclusion-policy.ps1')
foreach ($f in $drillFiles) {
  $dep = Join-Path $PSScriptRoot $f
  if (-not (Test-Path -LiteralPath $dep -PathType Leaf)) {
    Fail-Env ('缺演练依赖文件 tools\deploy\' + $f + '：' + $dep +
              '（四文件须同目录：drill 顶部 dot-source exclusion-policy.ps1，backup/restore 亦依赖它；' +
              'drill 启 backup/restore 子进程按同目录解析）')
  }
}
$drillAbs = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'test_restore_drill.ps1') -ErrorAction Stop).Path

$psCmd = Get-Command powershell.exe -ErrorAction SilentlyContinue
if (-not $psCmd) { Fail-Env '找不到 powershell.exe（Windows PowerShell 5.1）' }
$psExe = $psCmd.Source

$logDir = $env:ALLIN_LOG_DIR
if (-not $logDir) { $logDir = Join-Path $env:LOCALAPPDATA 'allin\logs' }
try {
  New-Item -ItemType Directory -Force -Path $logDir -ErrorAction Stop | Out-Null
} catch {
  Fail-Env ('日志目录不可创建：' + $logDir + '；' + $_.Exception.Message)
}
$logFile = Join-Path $logDir ('restore-drill-' + (Get-Date -Format 'yyyy-MM-dd') + '.log')

$auditDir = Join-Path $RepoRoot 'tools\gate\audit'
$audit    = Join-Path $auditDir 'restore-drill-runs.jsonl'
$period   = Get-Date -Format 'yyyy-MM'
$stamp    = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$hostName = [System.Environment]::MachineName

# ---------- 2) 留痕读取：坏行跳过；只看最后一次 status=ok 的 period ----------
function Get-LastOkPeriod {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  try { $all = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8) }
  catch { return $null }
  $found = $null
  foreach ($line in $all) {
    $t = $line.Trim()
    if (-not $t) { continue }
    try { $rec = $t | ConvertFrom-Json -ErrorAction Stop }
    catch { continue }   # 轮转残留 / 半行 / 畸形行：跳过，不让整份留痕失效
    if ($null -eq $rec) { continue }
    $sp = $rec.PSObject.Properties['status']
    $pp = $rec.PSObject.Properties['period']
    if ($null -eq $sp -or $null -eq $pp) { continue }
    if ($sp.Value -eq 'ok' -and $pp.Value -is [string]) { $found = $pp.Value }
  }
  return $found
}

# ---------- 3) 留痕写入：5MB 轮转 + UTF-8 无 BOM 追加 ----------
function Write-Record {
  param([string]$Path, [object]$Rec)
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop | Out-Null
  }
  if ((Test-Path -LiteralPath $Path -PathType Leaf) -and
      ((Get-Item -LiteralPath $Path).Length -gt (5 * 1024 * 1024))) {
    Move-Item -LiteralPath $Path -Destination ($Path + '.1') -Force -ErrorAction Stop
  }
  $json = ConvertTo-Json -InputObject $Rec -Compress
  [System.IO.File]::AppendAllText($Path, $json + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Write-Log {
  param([string]$File, [string[]]$Lines, [string]$Stamp)
  $body = ($Lines | ForEach-Object { '[' + $Stamp + '] ' + $_ }) -join "`n"
  if ($body) {
    [System.IO.File]::AppendAllText($File, $body + "`n", [System.Text.UTF8Encoding]::new($false))
  }
}

function Get-HeadSha {
  param([string]$Root)
  # 取不到（非 git 仓 / git 不在 PATH）一律写 unknown，规格要求；与演练退出码无关。
  try {
    $ErrorActionPreference = 'Continue'   # 函数作用域；避免 stderr 抛 NativeCommandError
    $out = @(& git -C $Root rev-parse --short HEAD 2>$null)
    $code = $LASTEXITCODE
    if ($code -eq 0 -and $out.Count -gt 0) {
      $s = $out[0].ToString().Trim()
      if ($s) { return $s }
    }
  } catch { }
  return 'unknown'
}

# ---------- 4) 幂等守卫：同月已 ok 且未 -Force ⇒ SKIP，且不写 JSONL ----------
$lastOk = Get-LastOkPeriod -Path $audit
if (-not $Force -and $lastOk -eq $period) {
  $msg = ('SKIP：' + $period + ' 已有一次 status=ok 的恢复演练' +
          '（-Force 可强制重跑；上次 failed 不阻断复验）；本次不写 JSONL')
  Write-Output $msg
  Write-Log -File $logFile -Lines @($msg) -Stamp $stamp
  exit 0
}

# ---------- 5) 真跑：演练脚本内部 exit ⇒ 必须作为子进程启动 ----------
$commit = Get-HeadSha -Root $RepoRoot
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$code  = $null
$lines = @()
$prevOut = [Console]::OutputEncoding
$prevEap = $ErrorActionPreference
try {
  # 与 monthly-audit-task.ps1 的差异：那边子进程是 Python（stdout 明确 UTF-8，故父进程
  # 临时切 UTF-8）；这里子进程是 powershell.exe 5.1，stdout 走控制台 OEM 码页。若本包装器
  # 被 pwsh 7（默认 UTF-8）拉起会解错中文，故把父进程 OutputEncoding 对齐到本机 OEM，
  # 拿到输出后在 finally 恢复。纯 5.1→5.1 场景二者本就一致，此行不改变行为。
  [Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(
    [System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
  # EAP=Stop 时原生命令 stderr 会抛 NativeCommandError（backup-allin.ps1 已踩过），临时降 Continue。
  $ErrorActionPreference = 'Continue'
  $lines = @(& $psExe -NoProfile -ExecutionPolicy Bypass -File $drillAbs 2>&1)
  $code = $LASTEXITCODE
} catch {
  $lines = @('[ENV] 演练子进程启动/环境准备失败：' + $_.Exception.Message)
  $code = 3
} finally {
  [Console]::OutputEncoding = $prevOut
  $ErrorActionPreference = $prevEap
}
$sw.Stop()
$ms = [int]$sw.ElapsedMilliseconds
if ($null -eq $code) { $code = 1 }   # 拿不到退出码 ⇒ 判失败，绝不兜 0
$status = 'failed'
if ($code -eq 0) { $status = 'ok' }

# ---------- 6) 结构化留痕（真跑一次一行；skip 不在此处） ----------
$rec = [ordered]@{
  ts     = (Get-Date).ToString('o')
  period = $period
  host   = $hostName
  commit = $commit
  exit   = [int]$code
  ms     = $ms
  status = $status
  forced = [bool]$Force
}
Write-Record -Path $audit -Rec $rec

# ---------- 7) 文本日志（含演练子进程输出）+ 控制台回显 ----------
$logLines = @('=== restore-drill period=' + $period + ' host=' + $hostName +
              ' commit=' + $commit + ' forced=' + ([bool]$Force) + ' ===')
foreach ($l in $lines) { $logLines += $l.ToString() }
$logLines += ('exit=' + $code + ' ms=' + $ms + ' status=' + $status + ' 留痕=' + $audit)
Write-Log -File $logFile -Lines $logLines -Stamp $stamp
$lines | ForEach-Object { $_.ToString() }
Write-Output ('restore-drill: ' + $status + ' exit=' + $code + ' ms=' + $ms + ' 留痕=' + $audit)

# 透传演练退出码（脚本约定 0/1；非 0 一律 failed，绝不吞码、绝不 exit 0 兜底）
exit $code
