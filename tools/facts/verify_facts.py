#!/usr/bin/env python3
"""verify_facts -- 校验 `docs/事实源/机器/*.md` 里的断言是否与磁盘现状一致。

它补的是 2026-10-30 查出来的三个盲区
--------------------------------------
当天对 `DESKTOP-8RSV60V.md` 做了全量复测，9 处断言与磁盘不符，而 19 道门禁 `exit 0`：

* ``g07_doc_freshness`` 只验「有没有写时点」，不验「时点之后还成不成立」；
* ``g19_docs_refs`` 的 ``PATH_REF`` 只认 ``docs/`` ``tools/`` 这类**仓内相对路径**，
  ``G:\\…`` 这种**机器绝对路径**一条都不解析；
* ``g01_paths`` 判的是「死盘符」，管不了「活盘符下的语义过期」（路径语法对、目录没了）。

所以本脚本只盯两类**可机械判**的断言，宁可窄也不制造噪声：

  PATH-EXISTS  行内含「现已存在 / 现存 / 仍在位」⇒ 该绝对路径必须存在；
               含「现已不存在 / 已不存在 / MISSING / 已删 / 已移除 / 均不存在」⇒ 必须不存在。
  COUNT        ``<绝对路径>`` 之后最近的 ``**N**`` 或 ``N 项`` ⇒ 实际条目数必须等于 N。

作用域刻意收窄到**文件头部最新的那个「时点」块**（第一个 ``> **时点**`` 起的连续引用块）——
那是全文件唯一承诺「这是现值」的地方；章节体里保留着大量历史时点块，判它们等于逼人改历史。

用法
----
    python tools/facts/verify_facts.py                 # 校验 docs/事实源/机器/*.md
    python tools/facts/verify_facts.py --file x.md     # 只校验一份（自检用）
    python tools/facts/verify_facts.py --json          # 机器可读
    python tools/facts/verify_facts.py --selftest      # 造一个必错样本，验证本脚本真能报

退出码：0 干净，1 有 finding，2 用法错误，3 环境错误（非 Windows / 找不到仓根）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

TARGET_DIR = Path("docs") / "事实源" / "机器"

# 一个机器绝对路径：盘符 + 分隔符 + 直到遇到空白/反引号/中文标点为止
ABS_PATH = re.compile(r"([A-Za-z]:[\\/][^`\s，。、；：（）【】「」]*)")

POSITIVE = re.compile(r"现已存在|现存|仍在位|EXISTS")
NEGATIVE = re.compile(r"现已不存在|已不存在|均不存在|MISSING|已删|已移除")

# 计数断言：优先取行内第一处 **N**，退而取「N 项 / N 个仓 / N 个目录」
COUNT_BOLD = re.compile(r"\*\*(\d+)\*\*\s*(项|个仓|个目录|个)?")
COUNT_PLAIN = re.compile(r"(\d+)\s*(项|个仓|个目录)")

STALE_DAYS = 90


def strip_tail(p: str) -> str:
    return p.rstrip("`.,;:)]}'\"、）。】")


def header_scope(text: str) -> tuple[str, str]:
    """返回 (作用域正文, 命中的时点字符串)。

    作用域 = **日期最新的一批** `> **时点**` 块（同日多块则一并纳入），到下一个
    `> **时点**` 或第一个 `## ` 标题为止。日期较早的块一律不判 —— 那是历史留档，
    判它等于逼人改历史。

    ⚠ 已知边界：若最新一块只是结构性说明（无任何数字/路径断言），旧块里的断言不会被检查。
    ⇒ 约定：**每次复测必须把现值写进最新的时点块**。
    """
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(">") and "**时点**" in ln]

    if not starts:
        end = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        return "\n".join(lines[:end]), ""

    blocks: list[tuple[tuple[int, ...], str, str]] = []
    for idx, s in enumerate(starts):
        e = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        for j in range(s + 1, e):
            if lines[j].startswith("## "):
                e = j
                break
        chunk = "\n".join(lines[s:e])
        d = re.search(r"20\d\d[-/年]\d{1,2}[-/月]\d{1,2}", chunk)
        key = tuple(int(x) for x in re.findall(r"\d+", d.group(0))[:3]) if d else (0, 0, 0)
        blocks.append((key, chunk, d.group(0) if d else ""))

    newest = max(b[0] for b in blocks)
    kept = [b for b in blocks if b[0] == newest]
    return "\n".join(b[1] for b in kept), kept[0][2]


def count_entries(p: Path, mode: str = "dirs") -> int:
    """数条目。

    mode="dirs"（默认）只数目录 —— 仓数、仓目录数都按这个口径（目录旁的文件不算）。
    mode="all" 数全部条目 —— 说「N 项」时是"归档区里有多少个东西"，含散文件。
    """
    try:
        if mode == "all":
            return sum(1 for _ in p.iterdir())
        return sum(1 for c in p.iterdir() if c.is_dir())
    except OSError:
        return -1


def check_text(text: str, label: str) -> tuple[list[dict], str]:
    block, stamp = header_scope(text)
    findings: list[dict] = []

    for lineno, line in enumerate(block.splitlines(), 1):
        if not line.strip():
            continue

        # --- PATH-EXISTS ---
        for raw in ABS_PATH.findall(line):
            path = strip_tail(raw)
            if not path or len(path) < 4:
                continue
            if NEGATIVE.search(line):
                if Path(path).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称不存在但实际存在：{path}", "path": path})
            elif POSITIVE.search(line):
                if not Path(path).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称存在但实际缺失：{path}", "path": path})

        # --- COUNT ---
        paths = [strip_tail(x) for x in ABS_PATH.findall(line)]
        paths = [p for p in paths if len(p) >= 4]
        if paths:
            target = Path(paths[0])
            if target.is_dir():
                m = COUNT_BOLD.search(line) or COUNT_PLAIN.search(line)
                if m:
                    claimed = int(m.group(1))
                    unit = (m.group(2) or "")
                    mode = "all" if unit.startswith("项") else "dirs"
                    actual = count_entries(target, mode)
                    if actual >= 0 and actual != claimed:
                        findings.append({"kind": "COUNT", "file": label, "line": lineno,
                                         "claim": f"声称 {claimed}（口径 {mode}），实际 {actual}：{target}",
                                         "path": str(target), "claimed": claimed,
                                         "actual": actual, "mode": mode})
    return findings, stamp


def evaluate_staleness(stamp: str) -> str:
    """时点距今多少天。只做提示，不阻断 —— 新鲜度是否可接受由人定。"""
    if not stamp:
        return "时点：未识别"
    digits = re.findall(r"\d+", stamp)
    if len(digits) < 3:
        return f"时点：{stamp}"
    try:
        d = date(int(digits[0]), int(digits[1]), int(digits[2]))
    except ValueError:
        return f"时点：{stamp}（无法解析）"
    age = (date.today() - d).days
    flag = "⚠ 超 90 天" if age > STALE_DAYS else "在窗口内"
    return f"时点：{stamp}（{age} 天前，{flag}）"


def selftest() -> int:
    """造一个必然出错的样本，证明本脚本不是永远返回 0 的摆设。"""
    tmp = Path(tempfile.mkdtemp(prefix="facts-selftest-"))
    probe = tmp / "probe-dir"
    probe.mkdir()
    (probe / "a.txt").write_text("x", encoding="utf-8")
    fake_missing = tmp / "definitely-not-here-xyz"
    doc = tmp / "sample.md"
    payload = (
        "> **时点** 2026-10-30（自检样本）\n"
        f"> `{probe}` 共 **99 项**\n"
        f"> `{fake_missing}` 现已存在\n"
        "## 正文\n"
        f"> `{probe}` 共 **1 项**（此块应被忽略）\n"
    )
    doc.write_text(payload, encoding="utf-8")
    findings, _ = check_text(doc.read_text(encoding="utf-8"), "selftest")
    kinds = sorted({f["kind"] for f in findings})
    ok = kinds == ["COUNT", "PATH-EXISTS"] and len(findings) == 2
    print(f"selftest: findings={len(findings)} kinds={kinds} -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        for f in findings:
            print("  ", f["claim"])
    return EXIT_OK if ok else EXIT_FINDING


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verify_facts", description="校验机器事实源的断言")
    ap.add_argument("--root", help="仓根（默认自动探测）")
    ap.add_argument("--file", help="只校验指定文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="跑自检样本")
    args = ap.parse_args(argv)

    if sys.platform != "win32":
        print("ENV ERROR: 只支持 Windows（判据是 Windows 绝对路径）", file=sys.stderr)
        return EXIT_ENV

    if args.selftest:
        return selftest()

    if args.file:
        target = Path(args.file)
        if not target.is_file():
            print(f"USAGE ERROR: 文件不存在：{target}", file=sys.stderr)
            return EXIT_USAGE
        files = [target]
        root = target.parent
    else:
        root = Path(args.root).resolve() if args.root else None
        if root is None:
            for p in Path(__file__).resolve().parents:
                if (p / "docs").is_dir() and (p / "preset").is_dir():
                    root = p
                    break
        if root is None:
            print("ENV ERROR: 找不到仓根（需含 docs/ 与 preset/）", file=sys.stderr)
            return EXIT_ENV
        files = sorted((root / TARGET_DIR).glob("*.md"))
        if not files:
            print(f"ENV ERROR: {root / TARGET_DIR} 下没有 md 文件", file=sys.stderr)
            return EXIT_ENV

    all_findings: list[dict] = []
    stamps: dict[str, str] = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        findings, stamp = check_text(text, f.name)
        all_findings.extend(findings)
        stamps[f.name] = evaluate_staleness(stamp)

    if args.json:
        print(json.dumps({"findings": all_findings, "freshness": stamps},
                         ensure_ascii=False, indent=2))
    else:
        for name, note in stamps.items():
            print(f"[{name}] {note}")
        print(f"scanned {len(files)} file(s); findings {len(all_findings)}")
        for fd in all_findings:
            print(f"  {fd['file']}:{fd['line']}  {fd['kind']}  {fd['claim']}")

    return EXIT_OK if not all_findings else EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main())
