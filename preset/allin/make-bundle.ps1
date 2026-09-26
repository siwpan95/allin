# make-bundle.ps1 —— 把 allin.patch.yml 封装成可安装的 DSH bundle 包
#
# DSH 0.1.7+ 的 preset 是「声明式」：要装进 profile，得把它包成一个 npm bundle
# （package.json 含 dsh.bundle.patch 指向一份 cordis.patch.yml），再 `dsh plugin add`。
# 本脚本自动生成这个 bundle 目录，可选顺手安装。
#
# ⚠️ CI 提醒：bundle 是 allin.patch.yml 的「派生副本」，改了 allin.patch.yml 必须重跑本脚本刷新，
#    否则装进去的是旧治理段。CI 门禁用 `.\make-bundle.ps1 -Check` 拦截「bundle 落后」——
#    比对 bundle/cordis.patch.yml 与源 allin.patch.yml 的内容哈希，不一致即非零退出。
#
# 用法：
#   .\make-bundle.ps1                          # 仅生成 bundle 目录（默认 preset/allin/bundle）
#   .\make-bundle.ps1 -Install                 # 生成后运行 dsh plugin --profile web add <bundle>
#   .\make-bundle.ps1 -BundleDir X -Profile web
#   .\make-bundle.ps1 -Check                   # CI 门禁：仅比对新鲜度，落后则 exit 3（不写入）
#   .\make-bundle.ps1 -Force                   # 忽略新鲜度警告、强制覆盖
#
# 退出码：0 = 成功/新鲜；1 = 要求 -Install 但 dsh 不在 PATH；2 = 找不到源 allin.patch.yml；3 = -Check 发现 bundle 落后。

[CmdletBinding()]
param(
  [string]$BundleDir = (Join-Path $PSScriptRoot 'bundle'),
  [string]$Profile = 'web',
  [switch]$Install,
  [switch]$Check,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'allin.patch.yml'
if (-not (Test-Path $src)) { Write-Error "找不到源文件：$src"; exit 2 }

$bundlePatch = Join-Path $BundleDir 'cordis.patch.yml'

# 计算源哈希，用于新鲜度比对（bundle 是 allin.patch.yml 的派生副本）
$srcHash = (Get-FileHash -Algorithm SHA256 $src).Hash
$stale = $false
if (Test-Path $bundlePatch) {
  $curHash = (Get-FileHash -Algorithm SHA256 $bundlePatch).Hash
  if ($curHash -ne $srcHash) { $stale = $true }
}

# CI 门禁模式：仅比对，不写入
if ($Check) {
  if ($stale) {
    Write-Host "STALE：bundle/cordis.patch.yml 与 allin.patch.yml 内容不一致（派生副本落后）。请重跑 `.\make-bundle.ps1` 刷新 bundle 后再提交。" -ForegroundColor DarkYellow
    exit 3
  }
  Write-Host "FRESH：bundle/cordis.patch.yml 与 allin.patch.yml 一致。" -ForegroundColor DarkGreen
  exit 0
}

if ($stale -and -not $Force) {
  Write-Host "bundle 已落后（allin.patch.yml 改过但 bundle 没刷新）。正在覆盖；CI 请用 -Check 拦截此类提交。" -ForegroundColor DarkYellow
}
if ($stale -and $Force) {
  Write-Host "（已 -Force 覆盖落后 bundle）" -ForegroundColor DarkYellow
}

New-Item -ItemType Directory -Path $BundleDir -Force | Out-Null
Copy-Item $src $bundlePatch -Force

# 一并打包 locate-root.ps1（治理段自发现引擎；agent 按 prefix 第 3 步调用，需随 bundle 走）
$locateSrc = Join-Path $PSScriptRoot 'locate-root.ps1'
if (Test-Path $locateSrc) { Copy-Item $locateSrc (Join-Path $BundleDir 'locate-root.ps1') -Force }

$manifest = [ordered]@{
  name    = 'allin-agent-preset'
  version = '0.1.0'
  private = $true
  dsh     = [ordered]@{ bundle = [ordered]@{ patch = 'cordis.patch.yml' } }
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $BundleDir 'package.json') -Value $manifest -Encoding UTF8

Write-Host "bundle 已生成：$BundleDir" -ForegroundColor Green
Write-Host ("  cordis.patch.yml = {0} B" -f (Get-Item $bundlePatch).Length)
Write-Host "  package.json    = dsh.bundle.patch -> cordis.patch.yml"

if ($Install) {
  $dsh = Get-Command dsh -ErrorAction SilentlyContinue
  if (-not $dsh) {
    Write-Error "dsh 不在 PATH，无法自动 -Install。请手动执行：`dsh plugin --profile $Profile add `"$BundleDir`""
    exit 1
  }
  Write-Host "==> dsh plugin --profile $Profile add `"$BundleDir`"" -ForegroundColor Cyan
  & $dsh plugin --profile $Profile add $BundleDir
  Write-Host ("install exit=$LASTEXITCODE")
  if ($LASTEXITCODE -eq 0) {
    Write-Host "装完：重启 DSH → Web GUI 设置 → Agent presets 应出现 allin 卡片 → 设 default:allin。" -ForegroundColor DarkGreen
  }
}

