<#
.SYNOPSIS
  注册 5 个 ALLIN-* 计划任务的配方脚本（P3 部署实施方案 §2 落地物）：
  ① ALLIN-website-autostart  登录拉起 website 常驻（9042）
  ② ALLIN-portal-autostart   登录拉起 portal 常驻（PORT=0 临时端口）
  ③ ALLIN-daily-backup       每日 02:00 备份 + 7 天轮转 + 日志 14 天清理
  ④ ALLIN-weekly-e2e         每周日 smoke:e2e 三面贯通防漂移（SC6）
  ⑤ ALLIN-monthly-audit      每周一触发 + 月度幂等守卫 = 月度治理盘点（ERP P2 备用路线）

.DESCRIPTION
  - 全部免管理员：当前用户、登录/定时触发、不提权（不注册「不登录也运行」类任务——拍板口径）。
  - 路径参数化：-RepoRoot / -BackupRoot / -LogDir，缺省读 ALLIN_ROOT / ALLIN_BACKUP_ROOT / ALLIN_LOG_DIR；
    缺参 fail-loud 给注册指引；盘符只进任务计划参数（注册期实参），绝不进仓内代码（g01）。
  - 回滚：-Unregister 一键注销全部 ALLIN-* 任务（P3 §5 回滚方案第 1 条）。
  - 本脚本只负责注册；运行行为由各包装器与 backup-allin.ps1 决定。
  - 任务⑤ 是**跨机可复制的仓内调度**：配方随仓 clone，注册动作仍由人在各机执行；
    不依赖 WorkBuddy 会话侧定时自动化（换机即失效，故 ERP P2 改走本备用路线）。

.NOTES
  兼容 Windows PowerShell 5.1；本文件只写不自动执行注册——由人确认参数后在计划任务机器上运行。
#>
param(
  # 仓库根（ALLIN_ROOT）
  [string]$RepoRoot   = $env:ALLIN_ROOT,
  # 备份根（ALLIN_BACKUP_ROOT 或注册期实参；不给盘符默认值）
  [string]$BackupRoot = $env:ALLIN_BACKUP_ROOT,
  # 计划任务日志目录（ALLIN_LOG_DIR；缺省时包装器自行回退到本机应用数据目录）
  [string]$LogDir     = $env:ALLIN_LOG_DIR,
  # 任务③ 每日触发时刻
  [string]$DailyAt    = '02:00',
  # 任务④ 周触发日
  [string]$WeeklyDay  = 'Sunday',
  # 任务④ 周触发时刻
  [string]$WeeklyAt   = '09:00',
  # 任务⑤ 周触发时刻（月度语义由 monthly_audit.py 的幂等守卫保证）
  [string]$MonthlyAt  = '09:00',
  # 回滚开关：注销全部 ALLIN-* 任务
  [switch]$Unregister
)

$ErrorActionPreference = 'Stop'
$Prefix = 'ALLIN-'

# ---------- 回滚路径：一键注销（P3 §5） ----------
if ($Unregister) {
  Get-ScheduledTask -TaskPath '\' -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like "$Prefix*" } |
    ForEach-Object {
      Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
      Write-Output "已注销计划任务: $($_.TaskName)"
    }
  Write-Output '回滚完成：ALLIN-* 计划任务已全部注销（仓内脚本与 env 未动，按 P3 §5 第 2/3 条另行回退）。'
  return
}

function Fail([string]$Message) { throw "register-tasks: $Message" }

# ---------- 0) 入参（fail-loud，给注册指引；不给盘符默认值，见 g01） ----------
if (-not $RepoRoot)   { Fail '仓库根未提供：请 setx ALLIN_ROOT <REPO_ROOT> 或传 -RepoRoot <REPO_ROOT>' }
if (-not $BackupRoot) { Fail ('备份根未提供：请 setx ALLIN_BACKUP_ROOT <BACKUP_ROOT> 或传 -BackupRoot <BACKUP_ROOT>' +
                             '（注册期实参，盘符只进任务计划参数不进仓内代码，见 tools/deploy/README.md）') }
if (-not $LogDir)     { Write-Warning '未设置 ALLIN_LOG_DIR——包装器将回退到本机应用数据目录 allin\logs（建议 setx 统一）' }

$deployDir   = Join-Path $RepoRoot 'tools\deploy'
$websiteDir  = Join-Path $RepoRoot 'website'
$platformDir = Join-Path $RepoRoot 'platform'
foreach ($f in @('backup-allin.ps1', 'start-website-task.ps1', 'start-portal-task.ps1',
                 'monthly-audit-task.ps1', 'monthly_audit.py')) {
  if (-not (Test-Path -LiteralPath (Join-Path $deployDir $f))) {
    Fail "缺少 $f —— 请确认 tools/deploy/ 部署物已随仓检出"
  }
}
$psExe = (Get-Command powershell.exe).Source

function New-AllinTask {
  param(
    [string]$Name, [hashtable]$Action, [object]$Trigger, [hashtable]$Settings, [string]$Description
  )
  $a = New-ScheduledTaskAction @Action
  $s = New-ScheduledTaskSettingsSet @Settings
  Register-ScheduledTask -TaskName $Name -Action $a -Trigger $Trigger -Settings $s -Description $Description | Out-Null
  Write-Output "已注册计划任务: $Name"
}

# ---- 任务① website 常驻（登录触发 + 失败重启 5 次/1 分钟；ExecutionTimeLimit Zero 关闭默认 72h 时限，防到点杀常驻） ----
$t1 = $Prefix + 'website-autostart'
New-AllinTask -Name $t1 `
  -Action @{ Execute           = $psExe
             Argument          = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f (Join-Path $deployDir 'start-website-task.ps1'))
             WorkingDirectory  = $websiteDir } `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
  -Settings @{ RestartCount       = 5
               RestartInterval    = (New-TimeSpan -Minutes 1)
               ExecutionTimeLimit = [TimeSpan]::Zero
               MultipleInstances  = 'IgnoreNew'
               StartWhenAvailable = $true } `
  -Description 'allin website 9042 登录自启 + 失败重启（P3 §2.3）'

# ---- 任务② portal 常驻（PORT=0 临时端口 + portal.port 发现；零新增常驻端口，已拍板） ----
$t2 = $Prefix + 'portal-autostart'
New-AllinTask -Name $t2 `
  -Action @{ Execute           = $psExe
             Argument          = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f (Join-Path $deployDir 'start-portal-task.ps1'))
             WorkingDirectory  = $platformDir } `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
  -Settings @{ RestartCount       = 5
               RestartInterval    = (New-TimeSpan -Minutes 1)
               ExecutionTimeLimit = [TimeSpan]::Zero
               MultipleInstances  = 'IgnoreNew'
               StartWhenAvailable = $true } `
  -Description 'allin portal 登录常驻（PORT=0 临时端口 + portal.port 文件发现，P3 §2.4）'

# ---- 任务③ 每日备份（02:00；-StartWhenAvailable 关机补跑；备份根为注册期实参） ----
$t3 = $Prefix + 'daily-backup'
New-AllinTask -Name $t3 `
  -Action @{ Execute           = $psExe
             Argument          = ('-NoProfile -ExecutionPolicy Bypass -File "{0}" -BackupRoot "{1}"' -f (Join-Path $deployDir 'backup-allin.ps1'), $BackupRoot)
             WorkingDirectory  = $RepoRoot } `
  -Trigger (New-ScheduledTaskTrigger -Daily -At $DailyAt) `
  -Settings @{ ExecutionTimeLimit = (New-TimeSpan -Hours 1)
               MultipleInstances  = 'IgnoreNew'
               StartWhenAvailable = $true } `
  -Description 'allin 每日数据备份 + 7 天轮转 + 日志 14 天清理（P3 §2.5；备份根为注册期实参，密钥唯一通道 backup-key）'

# ---- 任务④ 周度 smoke:e2e（周日 09:00；防长周期漂移——「B) 红了 30 天」事故对冲，已拍板） ----
# 内联命令说明：单引号字符串内嵌（PS 5.1 -Command 解析安全），运行时展开 $env:*；
# 与常驻 website（9042）不冲突——冒烟自身用临时端口，不占常驻口。
$t4 = $Prefix + 'weekly-e2e'
$e2eInner = 'Set-Location $env:ALLIN_ROOT; & npm.cmd run smoke:e2e 2>&1 | Out-File -Append -Encoding utf8 (Join-Path $env:ALLIN_LOG_DIR (''e2e-'' + (Get-Date -Format yyyy-MM-dd) + ''.log'')); exit $LASTEXITCODE'
New-AllinTask -Name $t4 `
  -Action @{ Execute           = $psExe
             Argument          = ('-NoProfile -ExecutionPolicy Bypass -Command "{0}"' -f $e2eInner)
             WorkingDirectory  = $RepoRoot } `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $WeeklyDay -At $WeeklyAt) `
  -Settings @{ ExecutionTimeLimit = (New-TimeSpan -Hours 2)
               MultipleInstances  = 'IgnoreNew'
               StartWhenAvailable = $true } `
  -Description 'allin 周度 smoke:e2e 三面贯通防漂移（P3 §2.6；SC6 北极星；CI 侧 gates-windows 单 step 双向对齐）'

# ---- 任务⑤ 月度治理盘点（ERP 调研 P2 备用路线，2026-11-07）----
# 触发器取「每周一」而不是「每月 1 日」：New-ScheduledTaskTrigger 没有 -Monthly，
# 改走 XML / schtasks 会引入第二套配方与用户上下文；这里用纯 cmdlet 触发 +
# monthly_audit.py 的「同月已有 status=ok 则 skip」守卫实现月度语义。附带好处：
# StartWhenAvailable 关机补跑落到本月任意一天都照样能真跑，不会被「非 1 日」误 skip。
$t5 = $Prefix + 'monthly-audit'
New-AllinTask -Name $t5 `
  -Action @{ Execute           = $psExe
             Argument          = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -RepoRoot "{1}"' -f (Join-Path $deployDir 'monthly-audit-task.ps1'), $RepoRoot)
             WorkingDirectory  = $RepoRoot } `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $MonthlyAt) `
  -Settings @{ ExecutionTimeLimit = (New-TimeSpan -Hours 1)
               MultipleInstances  = 'IgnoreNew'
               StartWhenAvailable = $true } `
  -Description 'allin 月度治理盘点（ERP P2 备用路线）：verify_facts + docs_index + repocheck + 组合分级对账；留痕 tools/gate/audit/monthly-audit-runs.jsonl；每周一触发，同月已 ok 则 skip'

# ---------- 收口提示 ----------
Write-Output ''
Write-Output '全部注册完成。验证命令：'
Write-Output '  Get-ScheduledTask -TaskName "ALLIN-*" | Format-Table TaskName,State'
Write-Output '  Get-ScheduledTaskInfo -TaskName ALLIN-website-autostart,ALLIN-portal-autostart,ALLIN-daily-backup,ALLIN-weekly-e2e,ALLIN-monthly-audit | Format-Table TaskName,LastRunTime,LastTaskResult'
Write-Output '试跑：Start-ScheduledTask -TaskName ALLIN-daily-backup；月度盘点首跑建议先手工执行 monthly-audit-task.ps1 -Force 看产物；回滚：pwsh -File register-tasks.ps1 -Unregister'
