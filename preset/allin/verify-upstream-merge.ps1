# verify-upstream-merge.ps1 —— 上游 PR 合并门禁（对应 docs\DSH升级与插件不兼容_2026-09-24.md §八）
#
# 作用：给定「官方/上游 DeepSeek harness」的 web-app presets/cordis.patch.yml，
#   检查把它合入我们的主干前，是否与 allin 治理 overlay 冲突：
#     allin 引用的 capability id/name 若在上游已不存在 → 冲突
#     （上游移除/重命名了某个 plugin，合入后 allin 可能挂不上）。
#
# 退出码：
#   0 = 能力集无冲突，可走 PR 合并流程（仍须人工完成下方清单 3/4）；
#   1 = 冲突，PR 不得合并，须先在隔离副本重放验证、能挂载且治理段不丢才许合入；
#   2 = 环境/参数错误（缺 python、缺文件）。
#
# 用法：
#   .\verify-upstream-merge.ps1 -UpstreamCordis <上游 cordis.patch.yml 路径>
#   .\verify-upstream-merge.ps1 -UpstreamCordis D:\projects\deepseek-harness-master\packages\bundle\web-app\presets\cordis.patch.yml

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$UpstreamCordis,
  [string]$Allin = (Join-Path $PSScriptRoot 'allin.patch.yml'),
  [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Write-Step($m) { if (-not $Quiet) { Write-Host "==> $m" -ForegroundColor Cyan } }
function Write-Ok($m) { if (-not $Quiet) { Write-Host "  [OK] $m" -ForegroundColor DarkGreen } }
function Write-Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor DarkYellow }
function Write-Fail($m) { Write-Host "  [FAIL] $m" -ForegroundColor DarkRed }

$PY = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $PY) { $PY = Get-Command 'E:\Python314\python.exe' -ErrorAction SilentlyContinue }
if (-not $PY) { Write-Error '找不到 python（需 PyYAML 解析 patch）'; exit 2 }

if (-not (Test-Path $UpstreamCordis)) { Write-Error "找不到上游文件：$UpstreamCordis"; exit 2 }
if (-not (Test-Path $Allin)) { Write-Error "找不到 allin：$Allin"; exit 2 }

$PyParse = @'
import sys, json, yaml
def _js(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode): return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode): return loader.construct_sequence(node)
    return loader.construct_mapping(node)
yaml.SafeLoader.add_multi_constructor('!js', _js)
yaml.SafeLoader.add_multi_constructor('tag:yaml.org,2002:js', _js)
def collect(rows, acc):
    if rows is None: return
    for r in rows:
        if not isinstance(r, dict): continue
        acc.append({"id": r.get("id"), "name": r.get("name")})
        if r.get("group") is True: collect(r.get("config"), acc)
def walk(root):
    out = {"preset_ids": [], "plugin_rows": []}
    for layer in root:
        if not isinstance(layer, dict): continue
        if "insert" in layer and isinstance(layer["insert"], list):
            for row in layer["insert"]:
                if not isinstance(row, dict): continue
                if row.get("name") == "@deepseek-ai/dsh-agent-preset":
                    cfg = row.get("config") or {}
                    out["preset_ids"].append(cfg.get("id"))
                    collect(cfg.get("plugins"), out["plugin_rows"])
    return out
res = {"up": None, "allin": None}
res["up"] = walk(yaml.safe_load(open(sys.argv[1], encoding="utf-8").read()))
res["allin"] = walk(yaml.safe_load(open(sys.argv[2], encoding="utf-8").read()))
print(json.dumps(res))
'@

$tmp = Join-Path $env:TEMP ("upstream_merge_" + [guid]::NewGuid().ToString("N") + ".py")
Set-Content -Path $tmp -Value $PyParse -Encoding UTF8
try {
  $json = & $PY.Source $tmp $UpstreamCordis $Allin 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $json) { Write-Error "python 解析失败"; exit 2 }
  $obj = $json | ConvertFrom-Json
} finally {
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

$up = $obj.up
$al = $obj.allin
$upIds = @($up.plugin_rows | ForEach-Object { $_.id } | Where-Object { $_ } | Sort-Object -Unique)
$upNames = @($up.plugin_rows | ForEach-Object { $_.name } | Where-Object { $_ } | Sort-Object -Unique)

Write-Step "比对 capability 集（上游 vs allin）"
Write-Ok "上游 preset id(s): $($up.preset_ids -join ',')；allin preset id(s): $($al.preset_ids -join ',')"
Write-Ok "上游 capability 行 $($up.plugin_rows.Count)；allin capability 行 $($al.plugin_rows.Count)"

$conflict = @()
foreach ($pr in $al.plugin_rows) {
  if ($pr.name -and $upNames -notcontains $pr.name) { $conflict += "allin 引用上游不存在的 plugin name: $($pr.name) (id=$($pr.id))" }
  if ($pr.id -and $upIds -notcontains $pr.id) { $conflict += "allin 引用上游不存在的 plugin id: $($pr.id) (name=$($pr.name))" }
}

if ($conflict.Count -eq 0) {
  Write-Ok "能力集无冲突：allin 的所有 capability 在上游均存在对应。"
} else {
  foreach ($c in $conflict) { Write-Fail $c }
}

Write-Host ""
Write-Host "──── PR 合并前人工清单（脚本无法自动判定的项，须逐项确认）────" -ForegroundColor Magenta
Write-Host "1) 上游是否「重发同版本号不同物」？→ 先在隔离副本重放 allin 补丁，能挂载、治理段不丢才许合入。"
Write-Host "2) 是否有 renamed preset / 移除或新增 plugin id？→ 脚本已查 name+id，但 schema 漂移需人工看 diff。"
Write-Host "3) allin persona 里的 `{{variable}}` 在新版是否仍合法（未知引用会抛错）？"
Write-Host "4) 合入主干前须 `dsh --profile web --dump-config` + `.\verify-mount.ps1 -Boot` 双绿。"

if ($conflict.Count -gt 0) {
  Write-Host ""
  Write-Fail "CONFLICT：存在能力集冲突，PR 不得合并（须先消解）。"
  exit 1
}
Write-Ok "SAFE：能力集无冲突，可按 §八 走 PR 合并流程（仍须完成上述人工清单 3/4）。"
exit 0

