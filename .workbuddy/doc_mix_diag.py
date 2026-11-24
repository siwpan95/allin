#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档混写诊断（临时侦察，不进仓）：三种形态实测。

形态 A 体裁混装：一个文件里同时出现 ≥3 类特征（操作指令 / 修订史 / 案例叙事 / 待办 / 判据）
形态 B 同一事实多源：同一段（表格行/清单行）在 ≥2 个非记录文件里逐字重复
形态 C 层级混居：跨机共识（应属 B）与机器特化/时点值同文件（§212/213 已抓过一部分）
"""
from __future__ import annotations
import hashlib, re, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
EXEMPT_PREFIX = ("docs/记录/", "docs/records/", "docs/历史/", "docs/md/", "docs/INDEX.md")

# 体裁特征
SIG = {
    "操作指令": re.compile(r"^\s*```(bash|powershell|sh|python)|^>\s*`?[a-z.]+\s+(docs|tools|platform)"),
    "修订史": re.compile(r"^\|\s*20\d\d-\d\d-\d\d\s*\|\s*v?\d|^###?\s*.*(修订|变更)记录|^- \*\*新增\*\*|改后复验"),
    "案例叙事": re.compile(r"实测(核出|发现|抓出)|曾(有|因|撞)|当时|事故|踩到|坑在"),
    "待办": re.compile(r"待办|TODO|⏳|暂缓|留待|待定"),
    "判据": re.compile(r"判据|门禁[^数]|必须|不得|exit [0-9]|blocking"),
    "纯数据表": re.compile(r"^\|\s*[^|]+\|\s*[^|]+\|\s*$"),
}


def files():
    seen = set()
    out = []
    for d in DOCS.iterdir():
        if not d.is_dir():
            continue
        real = str(Path(__import__("os").path.realpath(d)))
        if real in seen:
            continue
        seen.add(real)
        out.extend(d.rglob("*.md"))
    return sorted(out)


def main() -> int:
    print("=" * 70)
    print("形态 A · 体裁混装（同一文件里 ≥3 类特征并存）")
    print("=" * 70)
    for p in files():
        rel = p.relative_to(REPO).as_posix()
        if any(rel.startswith(e) or rel == e for e in EXEMPT_PREFIX):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = {k: len(v.findall(text)) for k, v in SIG.items()}
        kinds = [k for k, n in hits.items() if n >= 3 and k != "纯数据表"]
        if len(kinds) >= 3:
            detail = " / ".join(f"{k}×{hits[k]}" for k in kinds)
            print(f"  {rel}\n      {detail}")

    print()
    print("=" * 70)
    print("形态 B · 同一事实多源（≥2 个非记录文件逐字重复的行）")
    print("=" * 70)
    line_map = defaultdict(set)
    for p in files():
        rel = p.relative_to(REPO).as_posix()
        if any(rel.startswith(e) or rel == e for e in EXEMPT_PREFIX):
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if len(s) < 40 or s.startswith("| ---") or s.startswith("---"):
                continue
            line_map[s].add(rel)
    dup = {k: v for k, v in line_map.items() if len(v) >= 2}
    by_pair = defaultdict(list)
    for s, fs in dup.items():
        key = tuple(sorted(fs))
        by_pair[key].append(s)
    ranked = sorted(by_pair.items(), key=lambda kv: -len(kv[1]))[:12]
    for pair, lines in ranked:
        print(f"  {' ↔ '.join(x.split('/')[-1] for x in pair)}  （{len(lines)} 行逐字重复）")
        print(f"      例: {lines[0][:100]}")
    print(f"\n  合计 {len(dup)} 行在 ≥2 个文件里逐字重复")
    return 0


if __name__ == "__main__":
    sys.exit(main())
