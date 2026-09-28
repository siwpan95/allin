#Requires -Version 5.1
<#
.SYNOPSIS
    文档枢纽 ASCII 别名并置（junction 真身映射）。

.DESCRIPTION
    按《SPEC-005 文档枢纽契约》§3.2，docs/ 同时提供中文目录名与 ASCII 目录名，
    内容只存一份（真身在中文目录），别名用 junction 实现、**不进 git**。

        真身（入库）    ASCII 别名（不入库）
        docs/规范/   -> docs/spec/
        docs/事实源/ -> docs/facts/
        docs/记录/   -> docs/records/
        docs/md/     -> docs/历史/     （历史树真身本就是 ASCII）

    为什么用 junction 而不是复制：同一份内容进两次库违反「单一事实源」。
    为什么别名要能重建：junction 不入库，换机/克隆后必须重跑本脚本。

.PARAMETER Root
    allin 仓根；默认由本脚本位置反推（工具在 <仓根>/tools/gate/ 下）。

.PARAMETER Check
    只校验不创建：四个别名都存在且指向正确 → exit 0；否则 exit 1（用于门禁/CI）。

.EXAMPLE
    pwsh -File tools/gate/make_doc_aliases.ps1
    pwsh -File tools/gate/make_doc_aliases.ps1 -Check

.NOTES
    2026-09-28 随文档枢纽大修建立。退出码：0 成功/一致 · 1 校验失败 · 2 用法错误 · 3 环境错误。
#>
[CmdletBinding()]
param(
    [string]$Root,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

try {
    if (-not $Root) {
        $Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    }
    $docs = Join-Path $Root 'docs'
    if (-not (Test-Path $docs)) { throw "找不到 docs 目录：$docs" }
} catch {
    Write-Host "ENV ERROR: $_" -ForegroundColor Red
    exit 3
}

# 真身 -> 别名（都在 docs/ 下）
$map = [ordered]@{
    '规范'   = 'spec'
    '事实源' = 'facts'
    '记录'   = 'records'
    'md'     = '历史'
}

$bad = 0
$made = 0
foreach ($real in $map.Keys) {
    $alias = $map[$real]
    $realPath = Join-Path $docs $real
    $aliasPath = Join-Path $docs $alias

    if (-not (Test-Path $realPath)) {
        Write-Host ("MISSING-REAL  docs/{0} 不存在（真身缺失）" -f $real) -ForegroundColor Red
        $bad++
        continue
    }

    $item = Get-Item -LiteralPath $aliasPath -Force -ErrorAction SilentlyContinue
    if ($item) {
        $target = $null
        if ($item.LinkType) { $target = @($item.Target)[0] }
        $ok = $false
        if ($target) {
            try { $ok = ((Resolve-Path $target).Path -eq (Resolve-Path $realPath).Path) } catch { $ok = $false }
        }
        if ($ok) {
            if (-not $Check) { Write-Host ("OK            docs/{0} -> docs/{1}" -f $alias, $real) -ForegroundColor Green }
            continue
        }
        Write-Host ("WRONG-TARGET  docs/{0} 存在但未指向 docs/{1}（实际：{2}）" -f $alias, $real, $target) -ForegroundColor Red
        $bad++
        continue
    }

    if ($Check) {
        Write-Host ("MISSING-ALIAS docs/{0} 不存在（请跑 make_doc_aliases.ps1 重建）" -f $alias) -ForegroundColor Red
        $bad++
        continue
    }

    New-Item -ItemType Junction -Path $aliasPath -Target $realPath | Out-Null
    Write-Host ("CREATED       docs/{0} -> docs/{1}" -f $alias, $real) -ForegroundColor Yellow
    $made++
}

if ($Check) {
    if ($bad -eq 0) {
        Write-Host ("ALIASES OK  {0} 个别名全部就位" -f $map.Count) -ForegroundColor Green
        exit 0
    }
    Write-Host ("ALIASES FAIL  {0}/{1} 异常" -f $bad, $map.Count) -ForegroundColor Red
    exit 1
}

Write-Host ("完成：新建 {0} 个，异常 {1} 个。" -f $made, $bad)
if ($bad -gt 0) { exit 1 }
exit 0
