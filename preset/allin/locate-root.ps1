<#
.SYNOPSIS  allin_push 治理仓根自发现（零配置跨机）
.DESCRIPTION
  返回 allin_push 仓根绝对路径，供治理段「开卷必读」定位四份事实源。
  分层（命中即用）：① ALLIN_ROOT 环境变量 → ② 会话 cwd 的 git toplevel →
  ③ 从 cwd 向上走找含 docs/MEMORY.md 的 allin_push →
  ④ 本脚本自身位置 $PSScriptRoot/../../（脚本恒提交在 allin_push 内）→
  ⑤ 搜 $PROJECTS_ROOT / $HOME / 各逻辑盘 找 allin_push 仓。
  命中后打印仓根并缓存到 $DSH_HOME/.allin_root（下次秒回）。找不到 exit 2。
  设计要点：不写死任何盘符——换机克隆后靠脚本自身位置或 git/环境变量反推仓根，
  与铁律 5（去符盘）同源；不依赖 DSH 版本，抗上游破坏性变更。
.EXAMPLE
  pwsh -File locate-root.ps1
#>
[CmdletBinding()]
param([switch]$NoCache)
$ErrorActionPreference = 'Continue'

$Marker = 'docs/MEMORY.md'   # 仓根判据：该文件存在即视为 allin_push 仓根

function Test-Root {
  param([string]$root)
  if ($root -and (Test-Path -LiteralPath (Join-Path $root $Marker) -ErrorAction SilentlyContinue)) { return $true }
  return $false
}

$candidates = New-Object System.Collections.ArrayList

# ① ALLIN_ROOT 环境变量
if ($env:ALLIN_ROOT) { [void]$candidates.Add($env:ALLIN_ROOT.Trim().TrimEnd('\', '/')) }

# ② 会话 cwd 的 git toplevel
try {
  $tl = (& git -C $PWD rev-parse --show-toplevel 2>$null)
  if ($tl) { [void]$candidates.Add($tl.Trim().TrimEnd('\', '/')) }
} catch {}

# ③ 从 cwd 向上走
$d = $PWD
while ($d) {
  if ((Split-Path $d -Leaf) -eq 'allin_push') { [void]$candidates.Add($d.Path.TrimEnd('\', '/')) }
  $parent = Split-Path $d -Parent
  if (-not $parent -or $parent -eq $d.Path) { break }
  $d = Get-Item $parent -ErrorAction SilentlyContinue
  if (-not $d) { break }
}

# ④ 本脚本自身位置反推（最强：脚本恒在 allin_push/preset/allin/，故 ../../ 即仓根）
$selfDir = $PSScriptRoot                                   # preset/allin
$selfRoot = Split-Path (Split-Path $selfDir -Parent) -Parent   # allin_push
if ($selfRoot) { [void]$candidates.Add($selfRoot.TrimEnd('\', '/')) }

# ⑤ 搜常见根 + 各逻辑盘（动态枚举，不写死盘符）
$searchRoots = New-Object System.Collections.ArrayList
if ($env:PROJECTS_ROOT) { [void]$searchRoots.Add($env:PROJECTS_ROOT) }
if ($env:USERPROFILE)   { [void]$searchRoots.Add($env:USERPROFILE) }
if ($env:HOME)          { [void]$searchRoots.Add($env:HOME) }
try {
  foreach ($drv in [IO.DriveInfo]::GetDrives()) {
    if ($drv.DriveType -in @([IO.DriveType]::Fixed, [IO.DriveType]::Network, [IO.DriveType]::Removable)) {
      [void]$searchRoots.Add($drv.RootDirectory.FullName)
    }
  }
} catch {}

foreach ($sr in $searchRoots) {
  if (-not (Test-Path -LiteralPath $sr -ErrorAction SilentlyContinue)) { continue }
  $direct = Join-Path $sr 'allin_push'
  if (Test-Path -LiteralPath $direct -ErrorAction SilentlyContinue) { [void]$candidates.Add($direct.TrimEnd('\', '/')) }
  try {
    foreach ($child in (Get-ChildItem -LiteralPath $sr -Directory -ErrorAction SilentlyContinue |
                         Where-Object { $_.Name -match 'projects|repos|code|dev|src|work' })) {
      $sub2 = Join-Path $child.FullName 'allin_push'
      if (Test-Path -LiteralPath $sub2 -ErrorAction SilentlyContinue) { [void]$candidates.Add($sub2.TrimEnd('\', '/')) }
    }
  } catch {}
}

# 去重保序，取第一个有效根
$seen = @{}
$found = $null
foreach ($c in $candidates) {
  $norm = $c.TrimEnd('\', '/')
  if ($seen.ContainsKey($norm)) { continue }
  $seen[$norm] = $true
  if (Test-Root $norm) { $found = $norm; break }
}

if (-not $found) {
  Write-Error "未能自发现 allin_push 仓根（需 $Marker）。请设 ALLIN_ROOT，或把仓放在 cwd/git 仓内/常见 projects 目录。"
  exit 2
}

# 缓存（下次秒回）
if (-not $NoCache) {
  $cache = if ($env:DSH_HOME) { Join-Path $env:DSH_HOME '.allin_root' } else { Join-Path $env:USERPROFILE '.allin_root' }
  try { Set-Content -Path $cache -Value $found -Encoding UTF8 -ErrorAction SilentlyContinue } catch {}
}

Write-Output $found
exit 0
