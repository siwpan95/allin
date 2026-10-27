# -*- coding: utf-8 -*-
"""License compliance matrix over the registered projects.

The registry says which projects exist and where they publish; it does not say
what licence each one ships under. This tool closes that gap with the evidence
that is actually available locally: for every registered project that has a
clone beside this repository, detect the licence from its LICENSE file.

Detection is deliberately conservative -- it reports what it matched and marks
everything else ``unknown`` rather than guessing, because a wrong "MIT" in a
compliance matrix is worse than an honest blank.

Portability: the sibling clones live wherever ``ALLIN_REPOS_ROOT`` says,
defaulting to ``<this repo>/../repos`` -- the same convention ``g17-registry``
resolves, so the two tools can never disagree about where a project lives.

Output: ``tools/gate/audit/license-matrix.md`` (the audit directory is ignored).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "platform" / "registry" / "projects"
OUT = ROOT / "tools" / "gate" / "audit" / "license-matrix.md"


def repos_root() -> Path:
    """Where the sibling clones live: ALLIN_REPOS_ROOT, else <this repo>/../repos."""
    override = os.environ.get("ALLIN_REPOS_ROOT")
    return Path(override) if override else ROOT.parent / "repos"

SIGNATURES = [
    ("MIT-0", ["MIT No Attribution"]),
    ("MIT", ["Permission is hereby granted, free of charge", "MIT License"]),
    ("Apache-2.0", ["Apache License", "Version 2.0, January 2004"]),
    ("BSD-3-Clause", ["Redistribution and use in source and binary forms"]),
    ("GPL-3.0", ["GNU GENERAL PUBLIC LICENSE", "Version 3"]),
    ("GPL-2.0", ["GNU GENERAL PUBLIC LICENSE", "Version 2"]),
    ("LGPL-3.0", ["GNU LESSER GENERAL PUBLIC LICENSE"]),
    ("MPL-2.0", ["Mozilla Public License Version 2.0"]),
    ("Unlicense", ["This is free and unencumbered software released into the public domain"]),
    ("CC0-1.0", ["CC0 1.0 Universal"]),
    ("AGPL-3.0", ["GNU AFFERO GENERAL PUBLIC LICENSE"]),
]

SCALAR = {
    "id": re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE),
    "name": re.compile(r"^name:\s*(.+)\s*$", re.MULTILINE),
    "path": re.compile(r"^path:\s*(\S+)\s*$", re.MULTILINE),
    "category": re.compile(r"^category:\s*(\S+)\s*$", re.MULTILINE),
}


def fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, pattern in SCALAR.items():
        match = pattern.search(text)
        out[key] = match.group(1).strip() if match else ""
    return out


def detect(repo: Path) -> str:
    for candidate in sorted(repo.glob("LICENSE*")):
        if not candidate.is_file():
            continue
        try:
            head = candidate.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        for label, needles in SIGNATURES:
            if all(needle in head for needle in needles):
                return label
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="license compliance matrix over registered projects")
    parser.add_argument("--out", default=str(OUT), help=f"output path (default: {OUT})")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    repos = repos_root()
    rows: list[tuple[str, str, str, str, str]] = []
    for entry in sorted(REGISTRY.glob("*.yaml")):
        try:
            text = entry.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        meta = fields(text)
        identifier = meta.get("id") or entry.stem
        clone = None
        if meta.get("path"):
            # path: repos/<dir> —— 目录名可能与 id 不同（如 allin-engine -> an-engine），
            # 因此按 basename 解析，与 g17-registry 的判定口径一致。
            candidate = repos / Path(meta["path"]).name
            if (candidate / ".git").exists() or candidate.is_dir():
                clone = candidate
        licence = detect(clone) if clone else "unknown"
        rows.append((identifier, meta.get("name", ""), meta.get("category", ""),
                     licence, "local" if clone else "no-clone"))

    counts: dict[str, int] = {}
    for _id, _n, _c, licence, _src in rows:
        counts[licence] = counts.get(licence, 0) + 1
    unknown = counts.get("unknown", 0)
    with_clone = sum(1 for _id, _n, _c, _l, src in rows if src == "local")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    lines = [
        "# 许可合规矩阵（登记项目）",
        "",
        f"> 生成时点 {stamp} ｜ 判据：本地克隆的 LICENSE 文件特征匹配；匹配不上即记 unknown，不猜。",
        f"> 覆盖 {len(rows)} 条登记；有本地克隆 {with_clone} 条，unknown {unknown} 条。",
        "",
        "| 许可 | 条数 |",
        "| --- | --- |",
    ]
    for licence, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {licence} | {count} |")

    # 只把 unknown 铺开成表，读者要在一百多行里自己找问题；这里单独列出「有克隆却没有
    # 可识别许可」的条目——那才是能当场补 LICENSE 的动作项。无克隆的 unknown 属于数据缺口，
    # 不是待办，混在一起会让清单失去信噪比。
    todo = [(i, n) for i, n, _c, licence, src in rows if licence == "unknown" and src == "local"]
    lines += ["", f"## 待补：有本地克隆但无 LICENSE（{len(todo)} 条）", ""]
    if todo:
        lines += ["| id | 名称 |", "| --- | --- |"]
        lines += [f"| {i} | {n} |" for i, n in todo]
    else:
        lines.append("无。")
    lines += ["", "无克隆的 unknown 属数据缺口（需远端拉取），不计入待办。",
              "", "| id | 名称 | 分类 | 许可 | 来源 |", "| --- | --- | --- | --- | --- |"]
    for identifier, name, category, licence, source in rows:
        lines.append(f"| {identifier} | {name} | {category} | {licence} | {source} |")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if not args.quiet:
        print(f"许可矩阵 -> {out.relative_to(ROOT).as_posix()}  条目 {len(rows)}，unknown {unknown}")
        for licence, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:6]:
            print(f"   {licence}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
