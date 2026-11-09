#!/usr/bin/env python3
"""从 allin 仓生成 GraphRAG 叙述层语料（唯一入口，不手搬）。

硬规则：结构化取值文件不得进入图索引；冻结历史树默认排除；只取 git tracked 文件
（避开 docs/ 下的 junction 别名重复计入）。
零第三方依赖。退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INCLUDE = ("docs/规范/", "docs/记录/", "architecture/adr/", "docs/README.md", "README.md", "CHANGELOG.md")
EXCLUDE = ("docs/事实源/", "docs/md/", "docs/历史/", "docs/INDEX.md")
SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|[0-9a-f]{32,}|api[_-]?key\s*[:=]\s*\S+", re.I)


def tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", "ls-files", "-z"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    return [x for x in out.stdout.split("\0") if x] if out.returncode == 0 else []


def eligible(rel: str) -> bool:
    if rel.startswith(EXCLUDE):
        return False
    return rel.startswith(INCLUDE)


def build(root: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.txt"):
        old.unlink()
    written, skipped_secret, skipped_excluded = 0, 0, 0
    for rel in tracked(root):
        p = root / rel
        if not p.is_file():
            continue
        if not eligible(rel):
            skipped_excluded += 1
            continue
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = SECRET.findall(text)
        if hits:
            skipped_secret += 1
            continue
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel)[:120] + ".txt"
        (out / name).write_text(f"SOURCE: {rel}\n\n{text}", encoding="utf-8")
        written += 1
    return {"written": written, "skipped_excluded": skipped_excluded,
            "skipped_secret": skipped_secret, "out": str(out)}


def selftest() -> int:
    root = Path(tempfile.mkdtemp(prefix="allin-graphrag-input-"))
    for rel, body in [
        ("docs/规范/SPEC-005.md", "# 文档契约\n"),
        ("docs/记录/交接/2026-11.md", "# 交接卷\n"),
        ("docs/事实源/机器分区索引.md", "# 事实源 138 仓\n"),
        ("docs/事实源/_structured/facts.json", '{"x":1}\n'),
        ("docs/md/历史/旧.md", "# 冻结\n"),
        ("docs/规范/有密钥.md", "api_key = sk-abcdefghijklmnop123456\n"),
    ]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True)
    out = root / "input"
    r = build(root, out)
    names = sorted(p.name for p in out.glob("*.txt"))
    ok = (r["written"] == 2 and r["skipped_secret"] == 1 and r["skipped_excluded"] == 3
          and not any("事实源" in n or "_structured" in n for n in names))
    print(json.dumps({**r, "files": names, "selftest": "PASS" if ok else "FAIL"},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="allin -> GraphRAG 叙述层语料生成")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                    help="allin 仓根（从脚本位置自发现，不写死盘符：铁律 5 / g01-paths）")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.root / "docs").is_dir():
        print(f"ENV ERROR: 非 allin 仓根：{a.root}")
        return 3
    r = build(a.root, a.out or (a.root / "deploy" / "graphrag" / "input"))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["written"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
