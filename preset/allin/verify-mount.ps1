# verify-mount.ps1 —— allin 治理 preset 挂载校验 + 兜底
#
# 作用：在 DeepSeek Harness 0.1.7+（声明式 preset）上，确认 allin 治理 preset
#   （即同目录 allin.patch.yml 装进 web profile 后产生的 `allin` agent-preset 行）
#   已经正确安装、治理段（GOVERNANCE:BEGIN/END）完好。
#
# 它回答用户的核心关切：「DeepSeek 升级有破坏性变更，可能让 allin 挂不上」。
#   本脚本做三层检查：
#     ① 安装层：allin 的声明式补丁是否真的进了 profile（三种安装路径 + 源文件都能查）。
#     ② 结构层：补丁是否合法、治理段是否还在（删了就退化成出厂 cordis，无治理）。
#     ③ 漂移层（尽力而为）：把 allin 引用的 capability 集合与随包 cordis preset 比对，
#        发现 allin 引用了随包里已不存在的 plugin id / name → 预警「上游破坏性变更」风险。
#
# 重要边界（诚实声明，不夸大）：
#   - `dsh --dump-config` 是「免启动」合成，不 eval `!!js`、不挂载 preset，
#     因此它只能证明「补丁能解析、进了 layer 树」，不能证明「运行时真的挂载成功」。
#   - 运行时挂载失败（registry 拒绝）只能靠「升级后 `dsh web` 实跑一次」发现：
#     若挂载失败，本 preset 是一个独立 id（不是 cordis），会话会**自动降级到工厂
#     standard/cordis**——部署不会崩，只是该会话没有治理段。这正是「独立建仓 + 独立 id」的兜底。
#
# 退出码：0 = PASS（allin 已挂且治理段完好）；1 = WARN（挂上了但有风险/需复核）；2 = FAIL（没挂上）。
#
# 用法：
#   .\verify-mount.ps1                 # 默认：自动发现 + 校验
#   .\verify-mount.ps1 -Patch <路径>   # 直接校验某个指定补丁文件（而不只是「已安装」的那个）
#   .\verify-mount.ps1 -Boot           # 额外跑一次 `dsh --profile web --dump-config` 做合成层检查
#   .\verify-mount.ps1 -Quiet          # 只在异常时输出

[CmdletBinding()]
param(
  [string]$Patch = '',
  [switch]$Boot,
  [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

# ---------- 颜色（light 主题下用深色字 + 背景高亮） ----------
function Write-Step($m){ if(-not $Quiet){ Write-Host "==> $m" -ForegroundColor Cyan } }
function Write-Ok($m){ if(-not $Quiet){ Write-Host "  [OK] $m" -ForegroundColor DarkGreen } }
function Write-Warn($m){ Write-Host "  [WARN] $m" -ForegroundColor DarkYellow }
function Write-Fail($m){ Write-Host "  [FAIL] $m" -ForegroundColor DarkRed }
function Write-Info($m){ if(-not $Quiet){ Write-Host "  $m" -ForegroundColor DarkGray } }

# ---------- 工具定位 ----------
function Find-Dsh {
  $c = Get-Command dsh -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  # 去符盘（铁律 5）：$env:DSH_REPO 显式指定 → 同级仓 deepseek-harness-master 相对推断（不写死盘符）
  $guess = @()
  if ($env:DSH_REPO) { $guess += (Join-Path $env:DSH_REPO 'apps\cli\bin\dsh.ps1') }
  $guess += "$PSScriptRoot\..\..\..\deepseek-harness-master\apps\cli\bin\dsh.ps1"
  foreach ($g in $guess) { if (Test-Path $g) { return (Resolve-Path $g).Path } }
  return $null
}

function Find-Python {
  foreach ($p in @('python.exe', 'py.exe')) {
    $c = Get-Command $p -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
  }
  # 去符盘（铁律 5）：PATH 无 python 时允许 $env:ALLIN_PYTHON 显式指定解释器
  if ($env:ALLIN_PYTHON -and (Test-Path $env:ALLIN_PYTHON)) { return $env:ALLIN_PYTHON }
  return $null
}

# ---------- YAML 解析（PyYAML 优先，正则兜底） ----------
$PY = Find-Python
$PyParse = $null
if ($PY) {
  # 一段把 patch 解析成结构并抽关键字段的 python；支持 `!!js` 透传构造器
  $PyParse = @'
import sys, json
try:
    import yaml
except Exception as e:
    print(json.dumps({"error": "no_pyyaml:" + str(e)})); sys.exit(0)

# 透传 !!js 自定义 tag（harness preset 用到），避免解析失败
# `!!js` 在 YAML 1.1 下解析为 tag:yaml.org,2002:js；`!js` 为本地 tag。两者都注册。
def _js(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode): return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode): return loader.construct_sequence(node)
    return loader.construct_mapping(node)
yaml.SafeLoader.add_multi_constructor('!js', _js)
yaml.SafeLoader.add_multi_constructor('tag:yaml.org,2002:js', _js)

def collect_ids(rows, acc):
    if rows is None: return
    for r in rows:
        if not isinstance(r, dict): continue
        acc.append({"id": r.get("id"), "name": r.get("name"), "disabled": r.get("disabled")})
        if r.get("group") is True:
            collect_ids(r.get("config"), acc)

def walk(root):
    out = {"inserts": [], "preset_ids": [], "persona_prefix": None, "plugin_rows": []}
    for layer in root:
        if not isinstance(layer, dict): continue
        if "insert" in layer and isinstance(layer["insert"], list):
            for row in layer["insert"]:
                if not isinstance(row, dict): continue
                out["inserts"].append(row.get("id"))
                if row.get("name") == "@deepseek-ai/dsh-agent-preset":
                    cfg = row.get("config") or {}
                    out["preset_ids"].append(cfg.get("id"))
                    pls = cfg.get("plugins") or []
                    collect_ids(pls, out["plugin_rows"])
                    for pr in pls:
                        if isinstance(pr, dict) and pr.get("id") == "persona":
                            out["persona_prefix"] = (pr.get("config") or {}).get("prefix")
    return out

if len(sys.argv) < 2:
    print(json.dumps({"error": "usage: parse.py <patch-file>"})); sys.exit(0)
with open(sys.argv[1], "r", encoding="utf-8") as f:
    raw = f.read()
try:
    data = yaml.safe_load(raw)
except Exception as e:
    print(json.dumps({"error": "yaml_error:" + str(e)})); sys.exit(0)
if not isinstance(data, list):
    print(json.dumps({"error": "not_a_list"})); sys.exit(0)
print(json.dumps(walk(data)))
'@
}

function Parse-Patch($filePath) {
  # 用临时 .py 文件法：把 patch 路径作为 argv 传入，避免 STDIN 管道问题
  $tmp = Join-Path $env:TEMP ("allin_verify_" + [guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $PyParse -Encoding UTF8
  try {
    $json = & $PY $tmp $filePath 2>$null
    if ($LASTEXITCODE -eq 0 -and $json) {
      try { $obj = $json | ConvertFrom-Json } catch { $obj = $null }
      # PyYAML 不可用 / YAML 解析失败 → 落到正则兜底（脚本设计如此），不要当致命错
      if ($obj -and -not $obj.error) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        return $obj
      }
      if ($obj -and $obj.error) { Write-Info "PyYAML/解析不可用（$($obj.error)），改用正则兜底。" }
    }
  } catch {}
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  # 正则兜底
  $txt = Get-Content -Path $filePath -Raw -Encoding UTF8
  $ids = [regex]::Matches($txt, '^\s*-\s*id:\s*(\S+)', [Text.RegularExpressions.RegexOptions]::Multiline) | ForEach-Object { $_.Groups[1].Value }
  $has = [PSCustomObject]@{
    inserts = @()
    preset_ids = @(if ($txt -match 'config:\s*\n\s*id:\s*allin') { 'allin' })
    persona_prefix = $(if ($txt -match 'prefix:\s*\|-\s*\n([\s\S]*?)\n\s*-\s*id:') { $Matches[1] } else { $null })
    plugin_rows = @()
    _regex = $true
  }
  return $has
}

# ---------- 重装 / 兜底 段落（须在调用前定义） ----------
function Get-GovBlock([string]$text) {
  # 取 <!-- GOVERNANCE:BEGIN ... <!-- GOVERNANCE:END 段并归一化（去公共缩进 / 行尾空白 / CRLF）。
  # 锚定「标记整行」而不是子串首次出现：正文上方的注释里也会写 GOVERNANCE:BEGIN/END 段，
  # 用子串定位会把块起点拉到注释上（2026-10-29 g16 侧踩过同一个坑）。
  if (-not $text) { return $null }
  $lines = $text -split "`r?`n"
  $start = -1; $stop = -1
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $trimmed = $lines[$i].TrimStart()
    if ($start -lt 0) {
      if ($trimmed.StartsWith('<!-- GOVERNANCE:BEGIN')) { $start = $i }
    } elseif ($trimmed.StartsWith('<!-- GOVERNANCE:END')) { $stop = $i; break }
  }
  if ($start -lt 0 -or $stop -lt 0) { return $null }
  $block = @(); for ($i = $start; $i -le $stop; $i++) { $block += $lines[$i].TrimEnd() }
  $min = -1
  foreach ($ln in $block) {
    if ($ln.Trim().Length -eq 0) { continue }
    $indent = $ln.Length - $ln.TrimStart().Length
    if ($min -lt 0 -or $indent -lt $min) { $min = $indent }
  }
  if ($min -lt 0) { $min = 0 }
  $normalized = @()
  foreach ($ln in $block) {
    if ($ln.Trim().Length -eq 0) { $normalized += '' }
    elseif ($ln.Length -ge $min) { $normalized += $ln.Substring($min) }
    else { $normalized += $ln.TrimStart() }
  }
  return ($normalized -join "`n")
}

function Render-Remediation {
  Write-Host ""
  Write-Host "──── 重装 allin（三选一，推荐 1）────" -ForegroundColor Magenta
  Write-Host "1) 声明式 bundle（持久，推荐）：把同目录 allin.patch.yml 包成一个 npm 包"
  Write-Host "   (package.json 含 `"dsh`": { `"bundle`": { `"patch`": `"cordis.patch.yml`" } }`) 后："
  Write-Host "     dsh plugin --profile web add <该包路径或发布名>"
  Write-Host "2) 启动 overlay（临时，每次启动带 --patch）："
  Write-Host "     dsh web --patch `"$src`""
  Write-Host "3) 直接写进 profile 用户层：把 allin.patch.yml 的 `- insert:` 块追加到"
  Write-Host "     $userLayer"
  Write-Host "装完：重启 DSH → Web GUI 设置 → Agent presets 应出现「allin」卡片 →"
  Write-Host "设默认 default:allin → 新建会话首条回复应带【工作区治理·铁律】。"
}

function Render-Fallback {
  Write-Host ""
  Write-Host "──── 无法挂载 / 破坏性变更 兜底（DeepSeek 升级后）────" -ForegroundColor Magenta
  Write-Host "• 本 preset 是独立 id（allin，非 cordis），挂不上时会话**自动降级到工厂 standard/cordis**，"
  Write-Host "  部署不崩，只是该会话无治理段。"
  Write-Host "• 升级后请实跑一次 `dsh web`：若 Web GUI 设置里 allin 卡片不出现 / 首条回复无治理段，"
  Write-Host "  说明本版 DSH 已破坏性变更。先回退 default 到 cordis 恢复可用，再按"
  Write-Host "  docs\DSH升级与插件不兼容_2026-09-24.md §六 检查清单回放补丁、核对 capability SHAPE。"
  Write-Host "• 独立 gitee 仓 siwpan/deepseek-harness 即为此而建：上游破坏性变更只动我们的 pin，"
  Write-Host "  不动源；比对 shipped cordis.patch.yml 即可定位漂移点。"
}

# ---------- 主流程 ----------
Write-Step "定位 dsh 与 python"
$dsh = Find-Dsh
if ($dsh) { Write-Ok "dsh = $dsh" } else { Write-Info "dsh 不在 PATH（合成层检查会被跳过；仍可校验磁盘上的补丁）" }
if ($PY) { Write-Ok "python = $PY" } else { Write-Warn "python 不可用，将用正则兜底解析（较弱）" }

# DSH_HOME 解析
$dshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE '.dsh' }
$webProfile = Join-Path $dshHome 'profiles\web'

Write-Step "① 安装层：发现 allin 声明式补丁"
$discovered = @()
if ($Patch -and (Test-Path $Patch)) {
  $discovered += [PSCustomObject]@{ Path = (Resolve-Path $Patch).Path; Kind = '指定文件' }
}
# 路径 A：profile 用户层 cordis.patch.yml 含 allin 行
$userLayer = Join-Path $webProfile 'cordis.patch.yml'
if (Test-Path $userLayer) {
  $t = Get-Content -Path $userLayer -Raw -Encoding UTF8
  if ($t -match 'dsh-agent-preset' -and ($t -match "id:\s*allin" -or $t -match 'preset-allin')) {
    $discovered += [PSCustomObject]@{ Path = $userLayer; Kind = 'profile 用户层' }
  }
}
# 路径 B：装成 bundle（node_modules 里某包含 allin id 的 cordis.patch.yml）
if (Test-Path $webProfile) {
  $nm = Join-Path $webProfile 'node_modules'
  if (Test-Path $nm) {
    Get-ChildItem -Path $nm -Recurse -Filter 'cordis.patch.yml' -ErrorAction SilentlyContinue | ForEach-Object {
      $t = Get-Content -Path $_.FullName -Raw -Encoding UTF8
      if ($t -match 'dsh-agent-preset' -and ($t -match "id:\s*allin" -or $t -match 'preset-allin')) {
        $discovered += [PSCustomObject]@{ Path = $_.FullName; Kind = 'bundle(node_modules)' }
      }
    }
  }
}
# 路径 C：同目录源文件（尚未安装时也能校验源本身）
$src = Join-Path $PSScriptRoot 'allin.patch.yml'
if (Test-Path $src) {
  $discovered += [PSCustomObject]@{ Path = (Resolve-Path $src).Path; Kind = '源文件(同目录)' }
}

if ($discovered.Count -eq 0) {
  Write-Fail "在任何安装路径 / 源文件里都没找到 allin 声明式补丁。"
  & Render-Remediation
  exit 2
}
# 去重（按 Path）
$discovered = $discovered | Sort-Object Path -Unique
foreach ($d in $discovered) { Write-Ok "$($d.Kind) -> $($d.Path)" }

# 选「已安装」的优先（排除纯源文件），否则退回源文件
$installed = $discovered | Where-Object { $_.Kind -ne '源文件(同目录)' }
$target = if ($installed) { $installed[0] } else { $discovered[0] }
Write-Info "校验对象：$($target.Path)（$($target.Kind)）"

Write-Step "② 结构层：校验补丁合法 + 治理段完好"
$parsed = Parse-Patch $target.Path
if ($parsed.error) {
  Write-Fail "补丁解析失败：$($parsed.error)"
  & Render-Remediation
  exit 2
}
$hasGov = $false
if ($parsed.persona_prefix -and $parsed.persona_prefix.Contains('GOVERNANCE:BEGIN') -and $parsed.persona_prefix.Contains('GOVERNANCE:END')) {
  $hasGov = $true
}
$isAllin = $parsed.preset_ids -contains 'allin'
$pluginCount = if ($parsed.plugin_rows) { $parsed.plugin_rows.Count } else { 0 }

if (-not $isAllin) {
  Write-Fail "补丁里没有 `config.id: allin` 的 @deepseek-ai/dsh-agent-preset 行（可能装错了，或装成了别的 id）。"
  & Render-Remediation
  exit 2
}
if ($pluginCount -lt 18) {
  Write-Warn "allin 的 capability 行只有 $pluginCount 个（期望 ≥18）；可能随版本被裁剪，治理段能力不全。"
}
if ($hasGov) {
  Write-Ok "治理段 GOVERNANCE:BEGIN/END 完好（persona.prefix 含治理铁律）。"
} else {
  Write-Warn "治理段 GOVERNANCE:BEGIN/END 缺失：allin 已装但退化成「无治理的出厂 cordis」——该会话不受治理约束。需重装带治理段的 allin.patch.yml。"
}

# ---------- ② 续：治理段可移植性（铁律 5 去符盘）+ 仓根自发现（自愈校验） ----------
Write-Step "② 续：治理段可移植性（铁律 5 去符盘）+ 仓根自发现"
$portFail = $false
if ($parsed.persona_prefix) {
  $driveHits = [regex]::Matches($parsed.persona_prefix, '[A-Za-z]:[\\/]')
  if ($driveHits.Count -gt 0) {
    Write-Fail "治理段含 $($driveHits.Count) 处硬编码盘符路径（[A-Za-z]:[\\/]），违反铁律 5（去符盘）；换机后失效/误导，须改为仓根相对路径 + locate-root.ps1 自发现。"
    $portFail = $true
  } else {
    Write-Ok "治理段无硬编码盘符路径（铁律 5 去符盘合规）。"
  }
} else {
  Write-Warn "无 persona.prefix 可校验（解析失败？），跳过可移植性检查。"
}
# 仓根自发现（自愈）：跑同目录 locate-root.ps1，断言四事实源存在
$locate = Join-Path $PSScriptRoot 'locate-root.ps1'
if (Test-Path $locate) {
  try {
    $root = & $locate -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -eq 0 -and $root) {
      Write-Ok "自发现仓根：$root"
      $four = @('docs/INDEX.md', 'docs/规范/SPEC-001-铁律.md', 'docs/规范/SPEC-002-协作工作流程.md', 'docs/事实源/本机事实.md')
      $missing = @()
      foreach ($f in $four) { if (-not (Test-Path (Join-Path $root $f))) { $missing += $f } }
      if ($missing.Count -eq 0) { Write-Ok "四份事实源在仓根齐全（agent 开卷必读可用）。" }
      else { Write-Warn "仓根 $root 下缺失：$($missing -join ', ')（agent 开卷必读可能读不到；请确认仓完整或设 ALLIN_ROOT）。" }
    } else {
      Write-Warn "locate-root.ps1 未能自发现仓根（exit $LASTEXITCODE）；agent 运行时将靠 ALLIN_ROOT / git toplevel 兜底。"
    }
  } catch { Write-Warn "运行 locate-root.ps1 失败：$_" }
} else {
  Write-Info "locate-root.ps1 不存在（跳过仓根自发现校验）。"
}
if ($portFail) {
  & Render-Remediation
  exit 2
}

# ---------- ② 再续：同源层（2026-10-29）—— 挂载段必须等于仓内规范段 ----------
# 「挂上了且完好」不等于「是最新一代」：2026-10-29 实测挂载层仍写「15 道门禁」，
# 而仓内正文早已 19 道，新建会话读到的正是旧的那份。这一层只比内容，不碰文件。
Write-Step "② 再续：同源层（挂载段 vs 仓内规范段）"
$sameOrigin = $null
$sourcePatch = Join-Path $PSScriptRoot 'allin.patch.yml'
if (-not (Test-Path -LiteralPath $sourcePatch)) {
  Write-Info "仓内正文不可得（同目录没有 allin.patch.yml，可能从 bundle 副本运行）—— 跳过同源检查。"
} elseif (-not $hasGov) {
  Write-Info "治理段缺失，同源比较无对象（上面已报 WARN）。"
} else {
  $installedText = [System.IO.File]::ReadAllText($target.Path, [System.Text.Encoding]::UTF8)
  $canonicalText = [System.IO.File]::ReadAllText($sourcePatch, [System.Text.Encoding]::UTF8)
  $installedGov = Get-GovBlock $installedText
  $canonicalGov = Get-GovBlock $canonicalText
  if ($null -eq $installedGov -or $null -eq $canonicalGov) {
    Write-Warn "同源检查跳过：挂载段或规范段的标记不成对。"
  } elseif ([string]::Equals($installedGov, $canonicalGov, 'Ordinal')) {
    Write-Ok "挂载段与仓内规范段同源一致（$(($installedGov -split "`n").Count) 行 / $($installedGov.Length) 字符）。"
    $sameOrigin = $true
  } else {
    $sameOrigin = $false
    $installedLines = $installedGov -split "`n"
    $canonicalLines = $canonicalGov -split "`n"
    $lineNo = -1
    for ($i = 0; $i -lt [Math]::Min($installedLines.Count, $canonicalLines.Count); $i++) {
      if (-not [string]::Equals($installedLines[$i], $canonicalLines[$i], 'Ordinal')) { $lineNo = $i + 1; break }
    }
    if ($lineNo -lt 0) { $lineNo = [Math]::Min($installedLines.Count, $canonicalLines.Count) + 1 }
    Write-Warn "挂载段落后于仓内规范段（首个差异在第 $lineNo 行；挂载 $($installedLines.Count) 行 / $($installedGov.Length) 字符，规范 $($canonicalLines.Count) 行 / $($canonicalGov.Length) 字符）：新建会话读到的仍是旧规则。刷新：python preset/allin/refresh-gov-block.py --write，然后重启 DSH。"
  }
}

# ---------- ③ 漂移层（尽力而为） ----------
Write-Step "③ 漂移层：比对随包 cordis preset 的 capability 集合"
$shippedPaths = @(
  "$webProfile\node_modules\@deepseek-ai\dsh-web-app\presets\cordis.patch.yml",
  "$env:DSH_HOME\packages\bundle\web-app\presets\cordis.patch.yml",   # 由 DSH_HOME 指到检出（无盘符，2026-09-28 替换原写死盘符路径）
  "$PSScriptRoot\..\..\..\..\packages\bundle\web-app\presets\cordis.patch.yml"
)
$shipped = $null
foreach ($sp in $shippedPaths) { if (Test-Path $sp) { $shipped = Parse-Patch $sp; $shippedPath = $sp; break } }
$drift = @()
if ($shipped -and -not $shipped.error -and $shipped.plugin_rows) {
  $shippedNames = @($shipped.plugin_rows | ForEach-Object { $_.name } | Where-Object { $_ } | Sort-Object -Unique)
  $shippedIds = @($shipped.plugin_rows | ForEach-Object { $_.id } | Where-Object { $_ } | Sort-Object -Unique)
  Write-Ok "随包 cordis preset 参考：($shippedPath)，capability 行 $($shipped.plugin_rows.Count)"
  foreach ($pr in $parsed.plugin_rows) {
    if ($pr.name -and $shippedNames -notcontains $pr.name) {
      $drift += "allin 引用了随包不存在的 plugin name: $($pr.name) (id=$($pr.id))"
    }
    if ($pr.id -and $shippedIds -notcontains $pr.id) {
      $drift += "allin 引用了随包不存在的 plugin id: $($pr.id) (name=$($pr.name))"
    }
  }
  if ($drift.Count -eq 0) {
    Write-Ok "漂移检查通过：allin 的所有 capability 都能在随包 cordis preset 找到对应（无已知破坏性变更指纹）。"
  } else {
    foreach ($d in $drift) { Write-Warn $d }
    Write-Warn "以上指纹提示：上游可能重命名/移除了某些 plugin —— 升级后存在「挂载时 registry 拒绝」风险。"
  }
} else {
  Write-Info "未找到随包 cordis preset 作参照（跳过漂移检查）；可手动指定 harness 仓库路径后重跑。"
}

# ---------- ④ 合成层（可选，-Boot） ----------
if ($Boot -and $dsh) {
  Write-Step "④ 合成层：dsh --profile web --dump-config（免启动，仅验证 layer 可解析）"
  try {
    $out = & $dsh --profile web --dump-config 2>&1
    if ($LASTEXITCODE -eq 0) {
      if ($out -match 'allin') { Write-Ok "dump-config 成功且包含 allin 痕迹。" }
      else { Write-Info "dump-config 成功，但输出未直接出现 allin（dump 为合成树、未必显式列 insert id，属正常）。" }
    } else {
      Write-Warn "dump-config 返回非零（$LASTEXITCODE）：profile 合成层可能已损坏（不仅是 preset 问题）。"
    }
  } catch {
    Write-Warn "无法执行 dsh dump-config：$_"
  }
}

# ---------- 结论 + 兜底 ----------
Write-Step "结论"
if (-not $hasGov) {
  Write-Fail "FAIL：allin 已安装但治理段缺失 —— 等同未治理。"
  & Render-Remediation
  exit 2
}
if ($drift.Count -gt 0 -or $sameOrigin -eq $false) {
  if ($sameOrigin -eq $false) {
    Write-Warn "WARN：allin 已挂载、治理段完好，但**挂载段落后于仓内规范段**（同源层未过）。刷新后重启 DSH 即生效。"
  } else {
    Write-Warn "WARN：allin 已挂载且治理段完好，但存在上游破坏性变更指纹。"
  }
  & Render-Fallback
  exit 1
}
Write-Ok "PASS：allin 治理 preset 已挂载，治理段完好，capability 与随包一致。"
& Render-Fallback
exit 0
