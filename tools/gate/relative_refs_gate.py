#!/usr/bin/env python3
"""relative-refs gate -- 文档内相对路径引用判据（g19 补强 / 独立门禁候选）。

为什么不能直接给 g19 加一条正则：本仓实测（2026-11-09，343 份 tracked md）
  422 个内部链接目标里，按 cwd / docs / root 三种基准解析：
    cwd+docs 歧义 193、仅 cwd 184、仅 docs 3、三基准命中 6、三基准都不存在 36
  而那 36 个里混着示例占位（path.md / … / output/xxx.png）、只增不改的
  docs/记录/ 历史卷旧路径，以及真正的断链。一次性全判 = 一堆假红 = 门禁被关掉。

因此本判据：
  1. 只判 规范/ + 事实源/ + docs 根件（与 D9 同范围），排除 记录/ 与 md/ 历史树；
  2. 显式豁免示例占位与行内代码；
  3. 基准按契约优先 cwd，兼容 docs/ 与仓根；多基准命中记 note 不报错；
  4. baseline 棘轮：存量挂账，只阻断新增（同仓内 Baseline 机制）。

退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
PLACEHOLDER = re.compile(r"^(path\.md|xxx\.png|\.\.\.|data|output/|\[\^.*|.*\{\{.*\}\}.*)$")
JUDGED = ("docs/规范/", "docs/事实源/")
EXCLUDED = ("docs/记录/", "docs/md/", "docs/历史/")


def tracked_docs(root: Path) -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false",
                              "ls-files", "-z", "docs/*.md"],
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        if out.returncode == 0 and out.stdout:
            return [x for x in out.stdout.split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        pass
    return [p.relative_to(root).as_posix() for p in (root / "docs").rglob("*.md")]


def in_scope(rel: str) -> bool:
    if rel.startswith(EXCLUDED):
        return False
    return rel.startswith(JUDGED) or rel.count("/") == 1


def normalize(t: str) -> str:
    return t.split("#")[0].split("?")[0].strip().strip("<>").strip("`")


def scan(root: Path) -> dict:
    findings, notes = [], []
    stats = collections.Counter()
    for rel in tracked_docs(root):
        if not in_scope(rel):
            stats["excluded"] += 1
            continue
        p = (root / rel).resolve()
        if not p.is_file():
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        in_code = False
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or "`" in line and "](`" in line:
                stats["code-exempt"] += 1
                continue
            for raw in LINK.findall(line):
                t = normalize(raw)
                if (not t or t.startswith(("http://", "https://", "mailto:", "#", "data:"))
                        or re.match(r"^[A-Za-z]:[\\/]", t) or t.startswith("/")):
                    stats["external-or-absolute"] += 1
                    continue
                if PLACEHOLDER.match(t) or "…" in t:
                    stats["placeholder-exempt"] += 1
                    continue
                bases = {"cwd": p.parent, "docs": root / "docs", "root": root}
                hits = []
                for name, base in bases.items():
                    try:
                        if (base / t).resolve().exists():
                            hits.append(name)
                    except OSError:
                        pass
                if not hits:
                    stats["missing"] += 1
                    findings.append({"file": rel, "line": i, "target": t,
                                     "claim": "文档内相对路径在三基准下均不存在"})
                else:
                    stats["resolved"] += 1
                    if len(hits) > 1:
                        stats["ambiguous"] += 1
                        notes.append({"file": rel, "line": i, "target": t, "bases": hits})
    return {"findings": findings, "notes": notes, "stats": dict(stats)}


def load_baseline(path: Path | None) -> set[str]:
    if not path or not path.is_file():
        return set()
    return {l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def key(f: dict) -> str:
    return f"{f['file']}:{f['line']}:{f['target']}"


def run(root: Path, baseline: Path | None, write_baseline: bool, as_json: bool) -> int:
    if not (root / "docs").is_dir():
        print(f"ENV ERROR: 非 allin 仓根：{root}")
        return EXIT_ENV
    result = scan(root)
    findings = result["findings"]
    if write_baseline and baseline:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text("# facts relative-refs baseline（棘轮：只阻断新增）\n" +
                            "\n".join(sorted(key(f) for f in findings)) + "\n", encoding="utf-8")
        print(f"BASELINE WRITTEN: {len(findings)} 条 -> {baseline}")
        return EXIT_OK
    known = load_baseline(baseline)
    new = [f for f in findings if key(f) not in known]
    if as_json:
        print(json.dumps({"stats": result["stats"], "total_findings": len(findings),
                          "baselined": len(findings) - len(new), "new_findings": new,
                          "ambiguous": len(result["notes"])}, ensure_ascii=False, indent=2))
    else:
        print(f"relative-refs: scanned stats={result['stats']}")
        print(f"  total={len(findings)} baselined={len(findings)-len(new)} new={len(new)} "
              f"ambiguous={len(result['notes'])}")
        for f in new[:30]:
            print(f"  BLOCK {f['file']}:{f['line']} -> {f['target']}")
    return EXIT_BLOCKING if new else EXIT_OK


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-relrefs-selftest-"))
    (root / "docs" / "规范").mkdir(parents=True)
    (root / "docs" / "事实源" / "机器").mkdir(parents=True)
    (root / "docs" / "记录" / "交接").mkdir(parents=True)
    (root / "docs" / "规范" / "SPEC-001.md").write_text("# spec\n", encoding="utf-8")
    (root / "docs" / "INDEX.md").write_text(
        "# index\n[ok](规范/SPEC-001.md)\n[bad](missing.md)\n[example](`path.md`)\n", encoding="utf-8")
    (root / "docs" / "事实源" / "机器" / "A.md").write_text(
        "# A\n[up](../../规范/SPEC-001.md)\n", encoding="utf-8")
    (root / "docs" / "记录" / "交接" / "2026-11.md").write_text(
        "# 历史卷（只增不改，应豁免）\n[old](../事实源/机器分区索引.md)\n", encoding="utf-8")
    res = scan(root)
    bad = [f for f in res["findings"] if f["target"] == "missing.md"]
    false_positive = [f for f in res["findings"] if "记录/" in f["file"] or "path.md" in f["target"]]
    ok = len(bad) == 1 and not false_positive and len(res["findings"]) == 1
    print(json.dumps({"caught": len(bad), "false_positives": len(false_positive),
                      "findings": res["findings"], "selftest": "PASS" if ok else "FAIL"},
                     ensure_ascii=False, indent=2))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="relative-refs gate")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                    help="allin 仓根（从脚本位置自发现，不写死盘符：铁律 5 / g01-paths）")
    ap.add_argument("--baseline", type=Path,
                    default=Path(__file__).resolve().parents[2] / "tools/gate/baseline/relative-refs.txt",
                    help="棘轮基线：存量挂账，只阻断新增")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return run(a.root, a.baseline, a.write_baseline, a.json)


if __name__ == "__main__":
    raise SystemExit(main())
