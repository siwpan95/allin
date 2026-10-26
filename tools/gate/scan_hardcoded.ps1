<#
.SYNOPSIS
  硬编码本机路径门禁 —— 检出「代码里指向已失效根目录的绝对路径」，并按基线（ratchet）拦截**新增**死路径。

.DESCRIPTION
  判死口径（2026-09-23 第 1 批去本地化固化，堵住三个历史盲点）：
    1) 对**全量命中**判死，不限于某个严重度子集（旧口径漏掉赋值型行）；
    2) 分隔符容错 [\\/]{1,2}，兼容源码里 "<盘>:\\allin\\not\\OK" 这类转义写法（旧口径把根折叠成盘符根而误判为活）；
    3) 判据 = 路径前 1~2 段在盘上不存在（系统路径白名单除外）；
    4) 命中分三类：CODE 有效行 / CODE 注释行 / DOC·CFG；**只有 CODE 有效行算阻断**。

  为避免「门禁永远红」，默认走**基线棘轮**：`-Baseline` 记录已知命中（仓|文件|根），
  本次只对**基线之外的新增阻断项**返回 1；用 `-WriteBaseline` 在存量清理后刷新基线。

  自动排除的误报类型（每类都会在报告里计数，不会被静默丢弃）：
    · 系统路径白名单（%WINDIR% / Program Files / ProgramData 等）；
    · 测试夹具（文件位于 tests/ 或命名 *_test/_test_/test_*/conftest，且根指向 fake|nonexistent|dummy|tmp|x|y|z 等合成名）；
    · 占位符路径（含 {} <> $ % 或 <NAME> 形态）；
    · 转义伪影（如 Python 源码 "except ImportError as e:\n" 里的 `e:\n`）；
    · 散文提及（路径后紧跟空格与普通单词；`Program Files` 这类合法带空格目录除外）；
    · 审计注记（行内含「去本地化 / 已失效 / 已不存在 / 原…硬编码」等字样，-Strict 可关闭该豁免）。

  退出码：0 = 无新增阻断；1 = 有新增阻断；2 = 参数/环境错误；3 = 自测失败。

.PARAMETER Repos
  只扫这些仓名（相对 -ReposRoot）。默认扫 -ReposRoot 下全部 git 仓。

.PARAMETER Path
  额外扫描的自定义根（可为非 git 目录）。

.PARAMETER Baseline
  基线 CSV（默认 <脚本目录>\audit\hardcoded_gate_baseline.csv，随仓走）。不存在时视为空基线。

.PARAMETER WriteBaseline
  把本次全部阻断项写入基线文件（存量上线用），随后退出码恒为 0。

.PARAMETER NoBaseline
  忽略基线，全量报告（普查模式；有阻断即返回 1）。

.PARAMETER IncludeDocs
  把 DOC/CFG 命中也算作阻断（默认只报告不阻断）。与 -NoBaseline 同用即「全量普查」。

.PARAMETER Strict
  关闭「审计注记」豁免：注释行里的死路径也计入阻断。

.PARAMETER ListAll
  打印全部命中（默认只打印新增/阻断项）。

.PARAMETER OutCsv
  本次命中明细落盘（默认 <脚本目录>\audit\hardcoded_gate_<时间戳>.csv）。

.PARAMETER MaxPrint
  明细打印上限，默认 60。

.PARAMETER Quiet
  只输出汇总与退出码。

.PARAMETER SelfTest
  自测门禁本身（临时建仓验证：能抓死路径、不误报系统路径/URL/夹具/转义、基线棘轮生效）。

.EXAMPLE
  pwsh -File tools/gate/scan_hardcoded.ps1 -WriteBaseline      # 存量上线：写入基线
.EXAMPLE
  pwsh -File tools/gate/scan_hardcoded.ps1                    # 日常：只拦新增
.EXAMPLE
  pwsh -File tools/gate/scan_hardcoded.ps1 -NoBaseline -ListAll   # 普查：看全部存量
.EXAMPLE
  pwsh -File tools/gate/scan_hardcoded.ps1 -SelfTest
#>
[CmdletBinding()]
param(
  [string[]]$Repos,
  [string]$ReposRoot = '',
  [string[]]$Path,
  [string]$Baseline = '',
  [switch]$WriteBaseline,
  [switch]$NoBaseline,
  [switch]$IncludeDocs,
  # 深查模式：即使「前 1~3 段根」存在，也检查该路径的父目录是否存在；
  # 用于抓出 `C:\Users\<u>\WorkBuddy\<时间戳>\radio-apk` 这类「根存在但尾段已死」的引用。
  [switch]$Deep,
  # 只看「可动项」：把生成物/日志/测试夹具/注释注记等按规则不该改的命中过滤掉，
  # 让普查输出只剩真正可能下手的行（配合 -ListAll 使用）。
  [switch]$ExcludeGenerated,
  [switch]$Strict,
  [switch]$ListAll,
  [string]$OutCsv,
  [int]$MaxPrint = 60,
  [switch]$Quiet,
  [switch]$SelfTest
)

$ErrorActionPreference = 'Continue'

# ── 去符盘默认（铁律 5，2026-09-26）：默认目标 = 脚本自身所在仓（tools/gate → 上两级 = 仓根，单目标）──
if (-not $ReposRoot) { $Path = @($Path) + (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
$script:AuditDir = Join-Path $PSScriptRoot 'audit'
if (-not $Baseline) { $Baseline = Join-Path $script:AuditDir 'hardcoded_gate_baseline.csv' }

$script:CodeExts = @('.py','.pyw','.js','.mjs','.cjs','.ts','.tsx','.jsx','.cpp','.cc','.cxx','.h','.hpp','.c','.cs','.go','.rs','.java','.kt','.php','.rb','.lua','.bat','.cmd','.ps1','.psm1','.sh','.bash','.zsh','.pl','.r','.m','.mm','.swift','.sql','.vb','.vbs','.iss','.spec','.gradle','.cmake','.mk')
$script:SkipDirs = @('.git','node_modules','__pycache__','.venv','venv','env','dist','build','.next','.nuxt','target','out','.mypy_cache','.pytest_cache','.ruff_cache','.idea','.vs','.vscode')
$script:RxPath = [regex]'(?<![A-Za-z0-9])[A-Za-z]:[\\/]{1,2}[^\s"''`<>|,;]*'
$script:RxCjk = [regex]'[\u2E80-\u9FFF\uFF00-\uFFEF\u3000-\u303F]'
$script:RxTestFile = [regex]'(^|[\\/])(tests?|__tests__|spec|specs)[\\/]|(^|[._-])test[._-]|_test\.|\.test\.|\.spec\.|selftest|^conftest\.py$'
$script:RxFixtureSeg = [regex]'^(fake|nonexistent|dummy|nope|temp|tmp|test|tests?|example|examples?|foo|bar|baz|sample|samples|some|where|x|y|z|\d)$'
$script:RxEscapeSeg = [regex]'^[ntrsdwxaefvb0]$'
$script:RxPlaceholder = [regex]'[{}$%<>]'
# 「占位盘符」：单个字母 + 可选的冒号（`X:` / `X`）。
# 2026-10-06 补（用户拍板「改门禁自身正则」）：`X:\foo` 这类**示意写法**被判红 4 处 ——
# 实证 `tools/build_portfolio.py:52` 的 docstring「去符盘：X:\foo / X:/foo -> /foo（铁律 5）」。
# 它与真死根（如 `E:\D20`）的**分界不在盘符、在末段名字**：`foo` 在 RxFixtureSeg 占位表里，
# `D20` 是项目名不在表里 —— 所以本条只对「盘符 + 单个通用占位段」生效，不碰真死根。
$script:RxPlaceholderDrive = [regex]'^[A-Za-z]:?$'
# 正则转义伪影（如文本里的 \d \w \s）。
# ⚠ 2026-09-26 修：原式为 '[\(\)\[\]\+]|\\(w|d|s|W|D|S)(?![A-Za-z])'，会把**盘符路径**误判为转义伪影 ——
#   例 `E:\D20`（E: 在本机不存在，是真死根）因 `\D` 后跟 `2` 命中而整条被排除，
#   实测导致 d20 仓 3 处 `E:/D20` 漏检（死根路径门禁报 0 阻断，实为 3）。
#   修法：加负向后顾 (?<!:) —— 盘符分隔符前必是 `X:`，而真正的转义 `\d` 前不会是冒号。
$script:RxRegexArtifact = [regex]'[\(\)\[\]\+]|(?<!:)\\(w|d|s|W|D|S)(?![A-Za-z])'
$script:RxExampleLine = [regex]'(?i)^\s*(cd\b|python3?\b|py\b|node\b|npm\b|pnpm\b|yarn\b|git\b|>>>|\$ |>\s)|例如|示例|用法|example:|Example:|例[:：]|\.exe\s'
$script:ShellExts = @('.bat','.cmd','.ps1','.psm1','.sh','.bash','.zsh','.fish')
$script:RxSpaceTail = [regex]'^\s+(Files( \(x86\))?|Setup\s+\d|and Settings|Settings|Roaming)'
$script:ExtCache = @{}
$script:RxWhitelist = [regex]'^[A-Za-z]:\\?(Windows|Program Files|Program Files \(x86\)|ProgramData|PerfLogs|Recovery)(\\|$)'
$script:WhitelistDirs = @("$env:WINDIR", "$env:ProgramFiles", "${env:ProgramFiles(x86)}", "$env:ProgramData")
# 「审计注记」豁免（行内关键词）。
# 2026-10-06 扩：认**兄弟门禁的行内标记** —— `gov-paths: allow` / `repo-hygiene: allow` /
# `gov-credentials: allow`。实证：`deepseek-harness/governance/gates/g01_paths.py` 的自检夹具
# （故意指向不存在的路径来测门禁）**已经带** `# gov-paths: allow`，那是 DSH 那套门禁的既定豁免写法，
# 但本门禁原先不认 ⇒ 11 条夹具被反复判红。**标记名不同不代表豁免意图不同，认它**
# （与 repo_hygiene 当年认 `gov-credentials: allow` 同一处理）。豁免**只作用于该行**。
$script:RxAnnotation = [regex]'去本地化|已失效|已不存在|已删除|原.*硬编码|硬编码改|deprecated|placeholder|占位|内联自|复制自|整合自|选择性 vendor|vendor 自|源自|摘自|改编自|工程参考|门禁自检|gov-paths: allow|gov-python: allow|repo-hygiene: allow|gov-credentials: allow'
$script:RootCache = @{}
$script:Stat = @{}

function Add-Stat([string]$k) { if ($script:Stat.ContainsKey($k)) { $script:Stat[$k]++ } else { $script:Stat[$k] = 1 } }

function Get-RepoList {
  $list = New-Object System.Collections.ArrayList
  if ($Repos) {
    # 兼容 `pwsh -File ... -Repos a,b,c`（-File 绑定不会把逗号串拆成数组）与 `-Repos a,b` 两种写法
    $expanded = @()
    foreach ($r in $Repos) { $expanded += @($r -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) }
    foreach ($r in $expanded) {
      $p = Join-Path $ReposRoot $r
      if (Test-Path $p) { [void]$list.Add([pscustomobject]@{ Name = $r; Path = $p; Git = (Test-Path (Join-Path $p '.git')) }) }
      else { Write-Warning "仓不存在：$p（多个仓请用英文逗号分隔）" }
    }
  } elseif ($ReposRoot -and (Test-Path $ReposRoot)) {
    foreach ($d in (Get-ChildItem $ReposRoot -Directory -Force -ErrorAction SilentlyContinue | Sort-Object Name)) {
      [void]$list.Add([pscustomobject]@{ Name = $d.Name; Path = $d.FullName; Git = (Test-Path (Join-Path $d.FullName '.git')) })
    }
  } elseif ($ReposRoot) { Write-Warning "仓根不存在：$ReposRoot" }
  if ($Path) {
    foreach ($p in $Path) {
      if (Test-Path $p) { [void]$list.Add([pscustomobject]@{ Name = (Split-Path $p -Leaf); Path = (Resolve-Path $p).Path; Git = (Test-Path (Join-Path $p '.git')) }) }
      else { Write-Warning "路径不存在：$p" }
    }
  }
  return $list
}

function Test-DeadRoot([string]$root) {
  if ($script:RootCache.ContainsKey($root)) { return $script:RootCache[$root] }
  $dead = -not (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue)
  $script:RootCache[$root] = $dead
  return $dead
}

function Get-NormPath([string]$raw) {
  $p = $raw -replace '/', '\'
  while ($p -match '\\\\') { $p = $p -replace '\\\\', '\' }        # 转义双反斜杠 → 单
  if ($script:RxCjk.IsMatch($p)) { $p = ($script:RxCjk.Split($p, 2))[0] }   # 截断到首个中日韩字符
  $p = $p.TrimEnd('.', ',', ';', ':', ')', ']', '}', '>', '`', '"', "'", '，', '。', '、')
  return $p
}

function Get-Segments([string]$norm) {
  $segs = @($norm -split '\\' | Where-Object { $_ -ne '' })
  return $segs
}

function Test-Whitelisted([string]$norm) {
  if ($script:RxWhitelist.IsMatch($norm)) { return $true }
  foreach ($w in $script:WhitelistDirs) { if ($w -and $norm -like "$w*") { return $true } }
  return $false
}

function Invoke-Scan {
  param([object[]]$Targets)
  $hits = New-Object System.Collections.ArrayList
  $fileCount = 0
  foreach ($t in $Targets) {
    $lines = New-Object System.Collections.ArrayList
    if ($t.Git) {
      $fileCount += @(& git -C $t.Path ls-files 2>$null).Count
      # ⚠ 2026-09-26 修：PS 5.1 按 console 代码页(GBK)解码 git 输出，中文行文本变 mojibake，
      #   导致「审计注记」等中文豁免规则在 git-grep 模式下整体失效。临时切 OutputEncoding 到 UTF-8。
      $oldEnc = [Console]::OutputEncoding
      [Console]::OutputEncoding = [Text.Encoding]::UTF8
      try { $grepOut = @(& git -C $t.Path -c core.quotepath=false grep -n -I -E '[A-Za-z]:[\\/]' -- . 2>$null) }
      finally { [Console]::OutputEncoding = $oldEnc }
      foreach ($l in $grepOut) {
        if ($l -match '^([^:]+):(\d+):(.*)$') { [void]$lines.Add([pscustomobject]@{ File = $matches[1]; Line = [int]$matches[2]; Text = $matches[3] }) }
      }
    } else {
      $files = Get-ChildItem -LiteralPath $t.Path -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $e = $_.Extension.ToLower(); ($script:CodeExts -contains $e) -or ($e -in @('.md','.json','.yaml','.yml','.toml','.ini','.cfg','.txt','.conf','.env','.example')) } |
        Where-Object { $rel = $_.FullName.Substring($t.Path.Length); -not (@($script:SkipDirs) | Where-Object { $rel -like "*\$_\*" }) }
      $fileCount += @($files).Count
      foreach ($f in $files) {
        $i = 0
        foreach ($lt in ([IO.File]::ReadAllText($f.FullName, [Text.Encoding]::UTF8) -split "`r?`n")) {
          $i++
          if ($lt -match '[A-Za-z]:[\\/]') { [void]$lines.Add([pscustomobject]@{ File = $f.FullName.Substring($t.Path.Length).TrimStart('\'); Line = $i; Text = $lt }) }
        }
      }
    }
    foreach ($l in $lines) {
      $trim = $l.Text.TrimStart()
      # ⚠ 2026-09-26 修：GetExtension 对 git quotepath 引号路径（"\346..." 中文形态）抛
      #   「路径中具有非法字符」异常，$ext 会**残留上一个文件**的值 → 假阳性/假阴性。
      #   改用正则取扩展名，保证每行必有赋值。
      $fClean = $l.File.Trim('"')
      $ext = if ($fClean -match '\.([A-Za-z0-9]+)$') { '.' + $matches[1].ToLower() } else { '' }
      $isCode = ($script:CodeExts -contains $ext)
      $isComment = ($trim -match '^(#|//|/\*|\*|;|rem\b|::|@REM|<!--)|^["''`]\s*#' )
      # 行尾注释里提到的路径按注释看待（如 `GAME_ROOT = ...  # D:\allin\dwarf_scrolls`）
      $hashIdx = $l.Text.IndexOf('#')
      $slashIdx = $l.Text.IndexOf('//')
      $cmtFrom = @($hashIdx, $slashIdx | Where-Object { $_ -ge 0 } | Sort-Object | Select-Object -First 1)
      $cmtFrom = if ($cmtFrom.Count) { [int]$cmtFrom[0] } else { -1 }
      $isTestFile = ($script:RxTestFile.IsMatch($l.File))
      # PyInstaller 的 .spec 若不在 tests/ 下，不算测试夹具（否则 `legacy/spec/*.spec` 会被整片豁免）
      if ($isTestFile -and $ext -eq '.spec' -and $l.File -notmatch '(^|[\\/])tests?[\\/]') { $isTestFile = $false }
      $isAnnotation = ($script:RxAnnotation.IsMatch($l.Text))
      $isShell = ($script:ShellExts -contains $ext)
      # 非 shell 脚本里的 `cd X` / `python X` 只可能出现在字符串（用法示例）里 → 不算运行时路径
      $isExample = ($script:RxExampleLine.IsMatch($l.Text) -and -not $isShell)
      foreach ($m in $script:RxPath.Matches($l.Text)) {
        $raw = $m.Value
        if ($raw -match '^[A-Za-z]://') { continue }
        # ── 带空格路径修复：仅当后续文本是已知「带空格目录名」时才并入（如 C:\Program ← "Program Files"）──
        # 只在白名单续词上做，避免对 2.9 万处命中逐个 Test-Path（会拖成分钟级）
        # 只取后续 24 字符做续词判断（大行/压缩 JSON 下取整段会退化成 O(n²)）
        $tStart = $m.Index + $m.Length
        $tLen = [Math]::Min(24, $l.Text.Length - $tStart)
        $tail = if ($tLen -gt 0) { $l.Text.Substring($tStart, $tLen) } else { '' }
        $norm = Get-NormPath $(if ($raw.Length -gt 260) { $raw.Substring(0, 260) } else { $raw })
        if ($script:RxSpaceTail.IsMatch($tail)) {
          $mw = [regex]::Match($tail, '^\s+([A-Za-z][A-Za-z0-9 ()\.]*)')
          $cand = if ($mw.Success) { ("$norm " + $mw.Groups[1].Value.TrimEnd()) } else { $norm }
          if ($script:ExtCache.ContainsKey($cand)) { $norm = $script:ExtCache[$cand] }
          elseif (Test-Path -LiteralPath $cand -ErrorAction SilentlyContinue) { $script:ExtCache[$cand] = $cand; $norm = $cand }
          else { $script:ExtCache[$cand] = $norm }
        }
        $norm = Get-NormPath $norm
        if ($norm -match '^[A-Za-z]:\\?$' -or $norm -match '^[A-Za-z]:\\{2,}$') { continue }
        $segs = Get-Segments $norm
        if ($segs.Count -lt 2) { continue }
        $leaf = $segs[$segs.Count - 1]
        $firstSeg = $segs[1]
        # ── 逐条排除误报（每类计数 + 记 Reason，便于审计门禁本身） ──
        if (Test-Whitelisted $norm) { Add-Stat '排除·白名单'; continue }
        if ($script:RxEscapeSeg.IsMatch($firstSeg) -and $segs.Count -le 3 -and $raw -match '\\+[A-Za-z]$') { Add-Stat '排除·转义伪影'; continue }
        if ($script:RxPlaceholder.IsMatch($norm)) { Add-Stat '排除·占位符'; continue }
        if ($leaf -match '^[ntrs]$') { Add-Stat '排除·转义伪影(末段)'; continue }
        if ($script:RxRegexArtifact.IsMatch($norm) -and $segs.Count -le 3) { Add-Stat '排除·正则伪影'; continue }
        if ($segs.Count -eq 2 -and $firstSeg.Length -le 1) { Add-Stat '排除·过浅(单字符段)'; continue }
        if ($segs.Count -eq 2 -and $script:RxPlaceholderDrive.IsMatch($segs[0]) -and $script:RxFixtureSeg.IsMatch($firstSeg)) { Add-Stat '排除·占位盘符+通用段'; continue }
        if ($norm -match '\s' -and $norm -notmatch '\\Program Files' -and $norm -notmatch '\\Inno Setup') { Add-Stat '排除·散文提及'; continue }
        $root = if ($segs.Count -ge 3) { "$($segs[0])\$($segs[1])\$($segs[2])" } else { "$($segs[0])\$($segs[1])" }
        $deepMiss = $false
        if (-not (Test-DeadRoot $root)) {
          # 代码文件默认深查（2026-09-23：门禁原口径只看到「前 1~3 段根」，漏掉
          # `C:\Users\<u>\Desktop\allin\x.py` 这类根存在但尾段已死的引用）；-Deep 则连文档一起深查。
          if (-not ($Deep -or $isCode)) { continue }
          # 深查：父目录不存在即视为深层缺失
          $parent = if ($segs.Count -ge 2) { ($segs[0..($segs.Count - 2)] -join '\') } else { '' }
          if ($parent -and -not (Test-Path -LiteralPath $parent -ErrorAction SilentlyContinue)) { $deepMiss = $true }
          else { continue }
        }
        # ── 到此为「死根命中」 ──
        if ($isCode -and $isComment) { $kind = 'CODE-注释' }
        elseif ($isCode) { $kind = 'CODE-有效' }
        else { $kind = "DOC/CFG$ext" }
        $reason = ''
        $inTrailingComment = ($cmtFrom -ge 0 -and $m.Index -gt $cmtFrom)
        # 路径后紧跟中日韩字符（且不是引号/逗号收尾）→ 散文里提及，不是代码路径
        $afterIdx = $m.Index + $m.Length
        $afterCh = if ($afterIdx -lt $l.Text.Length) { $l.Text.Substring($afterIdx, 1) } else { '' }
        if (-not $isCode) { $reason = '文档/生成物' }
        elseif ($isComment -or $inTrailingComment) { $reason = '注释' }
        elseif ($afterCh -match '[\u2E80-\u9FFF\uFF00-\uFFEF]') { $reason = '散文提及' }
        elseif ($isTestFile) { $reason = '测试夹具' }
        elseif ($isExample) { $reason = '用法示例' }
        elseif ($isAnnotation -and -not $Strict) { $reason = '审计注记' }
        $blocking = ($isCode -and -not $reason)
        # 深查缺失：代码行里「根存在但父目录不存在」也算阻断（注释/测试/示例/注记仍豁免，仅在 Reason 里附注）
        if ($deepMiss) {
          if ($blocking) { $reason = '深层缺失(父目录不存在)' }
          else { $reason = "$reason+深层缺失" }
        }
        if ($blocking) { Add-Stat '阻断' } else { Add-Stat "非阻断·$reason" }
        [void]$hits.Add([pscustomobject]@{
          Repo = $t.Name; File = $l.File; Line = $l.Line; Kind = $kind; Blocking = $blocking; Reason = $reason
          Root = $root; Path = $norm; Identity = "$($t.Name)|$($l.File)|$root"
          Snippet = $trim.Substring(0, [Math]::Min(130, $trim.Length))
        })
      }
    }
  }
  return [pscustomobject]@{ Hits = $hits; Files = $fileCount }
}

# ───────────────────────── 自测 ─────────────────────────
if ($SelfTest) {
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ("gate-selftest-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  & git -C $tmp init -q 2>&1 | Out-Null
  # 门禁自检：死路径运行期拼接注入 —— 源码里不出现字面盘符路径，否则门禁扫自身时自举命中
  $bad = @'
"""selftest：死路径应为阻断项"""
import os
DEAD = r"@SELFTEST_DEAD_PATH@"           # 有效代码行 → 阻断
PLACEHOLDER = r"@SELFTEST_PLACEHOLDER@"  # 占位盘符 + 通用段 → **不**阻断（2026-10-06 补）
MARKED = r"@SELFTEST_MARKED@"            # 带兄弟门禁行内标记 gov-paths: allow → **不**阻断
GOOD = Path(__file__).resolve().parent      # 可推导 → 不阻断
'@
  $bad = $bad.Replace('@SELFTEST_DEAD_PATH@', 'Q' + ':\nope\engine\core.py')
  $bad = $bad.Replace('@SELFTEST_PLACEHOLDER@', 'X' + ':\foo')
  # 标记必须在**同一行**（与 DSH 门禁的既定语义一致）—— 拼 `# gov-paths: allow`
  $bad = $bad.Replace('@SELFTEST_MARKED@', 'W' + ':\marked\dead\path') + '  # gov-paths: allow' + "`n"
  $ok = @'
"""selftest：系统路径 / URL / 夹具 / 转义 不应误报"""
import os
W = r"C:\Windows\System32\cmd.exe"
U = "https://gitee.com/siwpan/projects"
FIX = "G:/fake/{pool}/f.wav"
try:
    pass
except ImportError as e:
    print("x")
'@
  [IO.File]::WriteAllText((Join-Path $tmp 'dead_paths.py'), $bad, (New-Object System.Text.UTF8Encoding($false)))
  New-Item -ItemType Directory -Force -Path (Join-Path $tmp 'tests') | Out-Null
  [IO.File]::WriteAllText((Join-Path $tmp 'tests\test_fixtures.py'), $ok, (New-Object System.Text.UTF8Encoding($false)))
  & git -C $tmp add -A 2>&1 | Out-Null
  & git -C $tmp -c user.email=t@t -c user.name=t commit -q -m selftest 2>&1 | Out-Null
  $target = @([pscustomobject]@{ Name = 'selftest'; Path = $tmp; Git = $true })
  $r = Invoke-Scan -Targets $target
  $blocking = @($r.Hits | Where-Object { $_.Blocking })
  $r2 = Invoke-Scan -Targets $target
  $t1 = (@($r2.Hits | Where-Object { $_.Blocking -and $_.Path -like ('Q' + ':\nope*') }).Count -eq 1)   # 门禁自检
  $t2 = (@($r2.Hits | Where-Object { $_.Path -like 'C:\Windows*' -or $_.Path -like 'http*' -or $_.Path -like 'G:\fake*' -or $_.Path -like '*\n' }).Count -eq 0)   # 门禁自检
  # 基线棘轮：把当前阻断写进基线后，同一目标不应再有「新增」
  $bl = Join-Path $tmp 'baseline.csv'
  $blocking | Export-Csv -LiteralPath $bl -NoTypeInformation -Encoding UTF8
  $known = @(Import-Csv -LiteralPath $bl | ForEach-Object { $_.Identity })
  $r3 = Invoke-Scan -Targets $target
  $newAfterBaseline = @($r3.Hits | Where-Object { $_.Blocking -and ($known -notcontains $_.Identity) })
  $t3 = (@($newAfterBaseline).Count -eq 0)
  # 占位盘符（X:\foo）不得阻断，同时真死根仍须阻断 —— **两个方向各一条断言**（调试铁律 61）
  # ⚠ 断言的**字面路径必须拼接**（`'X' + ':\foo*'`）：源码里写字面盘符路径会被门禁扫自身时自举命中
  #   —— 与文件上方夹具同一条纪律（2026-10-06 实测：直写时这条断言自己变成 2 条阻断项）。
  $t4 = (@($r2.Hits | Where-Object { $_.Blocking -and $_.Path -like ('X' + ':\foo*') }).Count -eq 0) -and $t1
  # 兄弟门禁标记（gov-paths: allow）同行即豁免，且不带标记的仍须判 —— 又是两个方向（调试铁律 61）
  $t5 = (@($r2.Hits | Where-Object { $_.Blocking -and $_.Path -like ('W' + ':\marked*') }).Count -eq 0) -and $t1
  Write-Output '== 门禁自测 =='
  Write-Output ("  死路径被检出（期望 1）: {0}  [实际 {1}]" -f $(if ($t1) { '✔' } else { '✗' }), @($blocking).Count)
  Write-Output ("  系统路径/URL/夹具/转义 零误报: {0}" -f $(if ($t2) { '✔' } else { '✗' }))
  Write-Output ("  基线棘轮生效（写入基线后新增 = 0）: {0}  [实际新增 {1}]" -f $(if ($t3) { '✔' } else { '✗' }), @($newAfterBaseline).Count)
  Write-Output ("  占位盘符不误报（X:\foo）且真死根仍判: {0}" -f $(if ($t4) { '✔' } else { '✗' }))
  Write-Output ("  兄弟门禁标记（gov-paths: allow）同行豁免: {0}" -f $(if ($t5) { '✔' } else { '✗' }))
  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
  if ($t1 -and $t2 -and $t3 -and $t4 -and $t5) { Write-Output '  自测通过'; exit 0 } else { Write-Output '  自测失败'; exit 3 }
}

# ───────────────────────── 主流程 ─────────────────────────
$targets = Get-RepoList
if (-not $targets -or @($targets).Count -eq 0) { Write-Error '没有可扫描的目标'; exit 2 }

$sw = [Diagnostics.Stopwatch]::StartNew()
$res = Invoke-Scan -Targets $targets
$dead = @($res.Hits)
$blocking = @($dead | Where-Object { $_.Blocking })
$filteredOut = 0
if ($ExcludeGenerated) {
  $before = $dead.Count
  $dead = @($dead | Where-Object { $_.Reason -notlike '文档/生成物*' -and $_.Reason -notlike '测试夹具*' -and $_.Reason -notlike '注释*' })
  $filteredOut = $before - $dead.Count
}

$known = @()
if (-not $NoBaseline -and -not $WriteBaseline -and (Test-Path $Baseline)) {
  $known = @((Import-Csv -LiteralPath $Baseline) | ForEach-Object { $_.Identity })
}
$new = @($blocking | Where-Object { $known -notcontains $_.Identity })

if (-not $OutCsv) { $OutCsv = Join-Path $script:AuditDir ("hardcoded_gate_{0:yyyyMMdd-HHmmss}.csv" -f (Get-Date)) }
if ($Quiet -and -not $PSBoundParameters.ContainsKey('OutCsv') -and -not $WriteBaseline) {
  $OutCsv = $null   # 静默模式（CI）默认不落盘，避免每次跑出一堆时间戳 CSV
}
# 0 条阻断时默认不落盘；显式给了 -OutCsv 才写（避免制造一堆 0 字节时间戳 CSV）
$export = if ($IncludeDocs -or $ExcludeGenerated) { $dead } else { @($dead | Where-Object { $_.Blocking }) }
if ($OutCsv -and -not $export.Count -and -not $PSBoundParameters.ContainsKey('OutCsv')) { $OutCsv = $null }
if ($OutCsv) {
  $outDir = Split-Path $OutCsv -Parent
  if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
  # 明细默认只落「阻断项」（DOC/CFG 的生成物命中单仓可达 2 万行，写全量会产出 10MB 级 CSV；
  # 需要全量普查时加 -IncludeDocs，或显式 -OutCsv 指定路径）
  $export | Export-Csv -LiteralPath $OutCsv -NoTypeInformation -Encoding UTF8
}

if ($WriteBaseline) {
  New-Item -ItemType Directory -Force -Path $script:AuditDir -ErrorAction SilentlyContinue | Out-Null
  $dead | Where-Object { $_.Blocking } | Export-Csv -LiteralPath $Baseline -NoTypeInformation -Encoding UTF8
  Write-Output ("基线已写入：{0}（阻断项 {1} 条）" -f $Baseline, $blocking.Count)
  if (-not $Quiet) { Write-Output ("明细：{0}" -f $OutCsv) }
  exit 0
}

if (-not $Quiet) {
  Write-Output '== 硬编码路径门禁（死根检测 · 基线棘轮）=='
  Write-Output ("  目标 {0} 个 / 跟踪文件 {1} 个 / 绝对路径命中 {2} 处 / 用时 {3:N1}s" -f @($targets).Count, $res.Files, $dead.Count, $sw.Elapsed.TotalSeconds)
  Write-Output ("  死根命中: 阻断(CODE有效) {0} · 非阻断 {1}" -f $blocking.Count, ($dead.Count - $blocking.Count))
  if ($ExcludeGenerated) { Write-Output ("  已按 -ExcludeGenerated 过滤掉生成物/夹具/注释类 {0} 处，下面只剩可动项" -f $filteredOut) }
  if ($script:Stat.Count) { Write-Output ("  排除/分类: " + (($script:Stat.GetEnumerator() | Sort-Object Name | ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }) -join '  ')) }
  Write-Output ''
  Write-Output ("  基线: {0}（已有 {1} 条）" -f $(if ($NoBaseline) { '(已禁用)' } else { $Baseline }), $known.Count)
  Write-Output ("  ★ 新增阻断项（本次要拦的）: {0}" -f $new.Count)
  if ($new.Count -gt 0) {
    $new | Group-Object Repo | Sort-Object Count -Descending | ForEach-Object { Write-Output ("      [{0}] {1} 处" -f $_.Name, $_.Count) }
  }
  $show = if ($ListAll) { $dead } else { if ($new.Count -gt 0) { $new } else { $blocking } }
  if (@($show).Count -gt 0) {
    Write-Output ''
    Write-Output ("  明细（前 {0} 条{1}）:" -f $MaxPrint, $(if ($ListAll) { '，-ListAll 全量' } elseif ($new.Count -eq 0) { '，为存量阻断项' } else { '' }))
    $show | Select-Object -First $MaxPrint | ForEach-Object {
      Write-Output ("    [{0}] {1}/{2}:{3}  root={4}  (根不存在)" -f $_.Kind, $_.Repo, $_.File, $_.Line, $_.Root)
      Write-Output ("        {0}" -f $_.Path)
    }
    if (@($show).Count -gt $MaxPrint) { Write-Output ("    … 其余 {0} 条见 {1}" -f (@($show).Count - $MaxPrint), $OutCsv) }
  }
  Write-Output ''
  Write-Output ("  明细落盘: {0}" -f $OutCsv)
}

$fail = if ($NoBaseline) { ($blocking.Count -gt 0) -or ($IncludeDocs -and $dead.Count -gt 0) } else { $new.Count -gt 0 }
if ($fail) { exit 1 } else { exit 0 }
