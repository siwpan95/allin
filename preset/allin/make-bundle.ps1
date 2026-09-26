# make-bundle.ps1 —— 把 allin.patch.yml 封装成可安装的 DSH bundle 包
#
# DSH 0.1.7+ 的 preset 是「声明式」：要装进 profile，得把它包成一个 npm bundle
# （package.json 含 dsh.bundle.patch 指向一份 cordis.patch.yml），再 `dsh plugin add`。
# 本脚本自动生成这个 bundle 目录，可选顺手安装。
#
# 用法：
#   .\make-bundle.ps1                          # 仅生成 bundle 目录（默认 preset/allin/bundle）
#   .\make-bundle.ps1 -Install                 # 生成后运行 dsh plugin --profile web add <bundle>
#   .\make-bundle.ps1 -BundleDir X -Profile web
#
# 退出码：0 = 成功；1 = 要求 -Install 但 dsh 不在 PATH；2 = 找不到源 allin.patch.yml。

[CmdletBinding()]
param(
  [string]$BundleDir = (Join-Path $PSScriptRoot 'bundle'),
  [string]$Profile = 'web',
  [switch]$Install
)

$ErrorActionPreference = 'Stop'

$src = Join-Path $PSScriptRoot 'allin.patch.yml'
if (-not (Test-Path $src)) { Write-Error "找不到源文件：$src"; exit 2 }

New-Item -ItemType Directory -Path $BundleDir -Force | Out-Null
Copy-Item $src (Join-Path $BundleDir 'cordis.patch.yml') -Force

$manifest = [ordered]@{
  name    = 'allin-agent-preset'
  version = '0.1.0'
  private = $true
  dsh     = [ordered]@{ bundle = [ordered]@{ patch = 'cordis.patch.yml' } }
} | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $BundleDir 'package.json') -Value $manifest -Encoding UTF8

Write-Host "bundle 已生成：$BundleDir" -ForegroundColor Green
Write-Host ("  cordis.patch.yml = {0} B" -f (Get-Item (Join-Path $BundleDir 'cordis.patch.yml')).Length)
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

