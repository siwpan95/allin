#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs_backlinks.py —— 文档枢纽的**反向链接 / 影响面**查询（纯标准库，不写盘）。

为什么需要它
------------
``g19-docs-refs`` 保证「文档里的链接指向真实存在的东西」（正向可达）；``D1`` 保证
「每份文档都登记在 INDEX」（全量索引）。两者合起来解决了**找得到**的问题，
但没解决**改了会波及谁**的问题：

    改 ``规范/SPEC-001-铁律.md`` 之前，你需要知道哪些文档引用了它。
    在 122 份文档里正向 grep 一遍当然能得出答案 —— 但那要求你已经知道文件名，
    而真正危险的引用往往出现在你没想到的地方。

本工具把「入链」变成一条查询：给定文档，列出所有引用它的文档与行号。
2026-11-23 实测基线：122 份真身文档、301 条图内引用边、65 份零出链、
**零入链 0 份**（D1 强制登记使孤儿检测在本仓无收益 —— 所以本工具不做孤儿检测）。

与相邻判据的分工（刻意不重叠）
------------------------------
| 组件 | 管什么 | 不管什么 |
|---|---|---|
| ``D1``（docs_index） | 每份文档都登记 | 文档之间怎么互相引用 |
| ``g19-docs-refs`` | 链接目标存在（正向） | 反向关系、影响面 |
| 本工具 | **谁引用了我**（反向） | 不阻断、不入基线、不写盘 |

**不写盘是设计决定**：122 份文档扫描 < 0.2 s，按需算即可。若生成一份反链页面，
它自己也要被 D1 登记、被 g15 判契约、被 g19 判链接 —— 为一份随时可重算的派生数据
引入三处维护面，不值。

用法
----
    python tools/docs_backlinks.py SPEC-001          # 按名片段匹配（唯一命中才输出）
    python tools/docs_backlinks.py 规范/SPEC-001-铁律.md
    python tools/docs_backlinks.py --hub             # 全图度数排行（谁被引用最多）
    python tools/docs_backlinks.py SPEC-001 --json   # 机读

退出码：0 正常 · 1 未找到目标 / 匹配不唯一 · 2 用法错误 · 3 根目录异常。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

#: docs/ 下不参与图计算的顶层目录：
#:   facts/records/spec/历史 是 ASCII 别名（junction，指向真身，重复计数）
#:   md/ 是冻结历史树（232 篇，默认不参与现行知识图）
EXCLUDED_TOPS = frozenset({"facts", "records", "spec", "历史", "md"})

#: markdown 行内链接 [text](target)。图片与 HTML 不在内。
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

#: 只把 .md 目标算作图边；图片/JSON/YAML 等是资产引用，不是知识关联。
NON_DOC_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                    ".json", ".yaml", ".yml", ".mp4", ".pdf", ".html")


def iter_docs(root: Path) -> list[Path]:
    """docs/ 下的真身 markdown（排除别名与冻结历史树）。"""
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        parts = p.relative_to(root).parts
        if parts and parts[0] in EXCLUDED_TOPS:
            continue
        out.append(p)
    return out


def build_graph(root: Path) -> tuple[dict[str, set[str]], dict[str, list[tuple[str, int]]], int]:
    """返回 (出链图, 入链明细, 未解析条数)。

    入链明细保留行号 —— 没有行号的「谁引用了我」等于没给位置，还得再 grep 一遍。
    """
    docs = iter_docs(root)
    out_edges: dict[str, set[str]] = defaultdict(set)
    inbound: dict[str, list[tuple[str, int]]] = defaultdict(list)
    unresolved = 0
    root_abs = root.resolve()

    for path in docs:
        src = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        # 用行号定位，而不是靠 offset 反算 —— 反算在 CRLF 上会偏
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in LINK.finditer(line):
                target = m.group(1).split("#", 1)[0].strip()
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.lower().endswith(NON_DOC_SUFFIXES):
                    continue
                dst = (path.parent / target).resolve()
                try:
                    rel = dst.relative_to(root_abs).as_posix()
                except ValueError:
                    unresolved += 1
                    continue
                if rel.split("/")[0] in EXCLUDED_TOPS or dst.suffix != ".md" or not dst.exists():
                    unresolved += 1
                    continue
                out_edges[src].add(rel)
                if (src, lineno) not in inbound[rel]:
                    inbound[rel].append((src, lineno))
    return out_edges, inbound, unresolved


def resolve_target(root: Path, needle: str) -> list[str]:
    """把用户输入解析成文档相对路径。唯一命中才算解析成功。"""
    norm = needle.replace("\\", "/").lstrip("./")
    docs = [p.relative_to(root).as_posix() for p in iter_docs(root)]
    if norm in docs:
        return [norm]
    hits = [d for d in docs if norm in d]
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="文档枢纽反向链接 / 影响面查询（不写盘）")
    ap.add_argument("target", nargs="?", help="文档路径或其名片段，如 SPEC-001")
    ap.add_argument("--docs-root", default=None, help="docs 目录（默认 <仓根>/docs）")
    ap.add_argument("--hub", action="store_true", help="输出全图被引排行，而不是单个目标")
    ap.add_argument("--json", action="store_true", help="机读输出")
    ap.add_argument("--limit", type=int, default=30, help="列表上限（默认 30）")
    args = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    root = Path(args.docs_root) if args.docs_root else (here.parent / "docs")
    if not root.is_dir():
        print(f"[ERR] docs 目录不存在: {root}", file=sys.stderr)
        return 3

    out_edges, inbound, unresolved = build_graph(root)
    docs = iter_docs(root)
    total = len(docs)
    edges = sum(len(v) for v in out_edges.values())

    if args.hub:
        ranked = sorted(inbound.items(), key=lambda kv: (-len(kv[1]), kv[0]))[: args.limit]
        if args.json:
            print(json.dumps({
                "docs": total, "edges": edges, "unresolved": unresolved,
                "ranking": [{"doc": d, "inbound": len(v)} for d, v in ranked],
            }, ensure_ascii=False, indent=2))
            return 0
        print(f"文档 {total} 份 · 图内引用 {edges} 条 · 未解析 {unresolved} 条")
        print(f"{'入链':>5}  {'出链':>5}  文档")
        for doc, refs in ranked:
            print(f"{len(refs):>5}  {len(out_edges.get(doc, ())):>5}  {doc}")
        return 0

    if not args.target:
        ap.print_usage(sys.stderr)
        print("需要 target 或 --hub", file=sys.stderr)
        return 2

    hits = resolve_target(root, args.target)
    if not hits:
        print(f"[ERR] 未找到匹配文档: {args.target}", file=sys.stderr)
        return 1
    if len(hits) > 1:
        print(f"[ERR] 匹配不唯一（{len(hits)} 个），请写更具体的路径：", file=sys.stderr)
        for h in hits[: args.limit]:
            print("  " + h, file=sys.stderr)
        return 1

    doc = hits[0]
    refs = sorted(inbound.get(doc, []))
    out = sorted(out_edges.get(doc, ()))
    if args.json:
        print(json.dumps({
            "doc": doc,
            "inbound": [{"from": s, "line": n} for s, n in refs],
            "outbound": out,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"目标：{doc}")
    print(f"  被引用 {len(refs)} 处 · 引用他文 {len(out)} 处")
    if refs:
        print("\n  ← 谁引用了我（改动波及面）：")
        for src, lineno in refs[: args.limit]:
            print(f"    {src}:{lineno}")
        if len(refs) > args.limit:
            print(f"    …共 {len(refs)} 处，用 --limit 调整")
    else:
        print("\n  ← 无入链（仅由 INDEX 登记，无正文引用）")
    if out:
        print("\n  → 我引用了（依赖面）：")
        for dst in out[: args.limit]:
            print(f"    {dst}")
        if len(out) > args.limit:
            print(f"    …共 {len(out)} 处，用 --limit 调整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
