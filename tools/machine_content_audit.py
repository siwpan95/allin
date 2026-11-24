#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器特化内容对账 —— 扫描公共文档，找出「该住各机事实源、却留在公共处」的内容。

## 为什么要有这个（三层分域在文档层的落地）

2026-11-24/25 全哥两次纠偏后的固化口径：

1. **指南是公共核**，不带任何机器特化内容（机器名、某机的实测数字、某机的事故经过）；
2. 各机事故/事件/现值 → **各机事实源**（`docs/事实源/机器/<机>/<机>.md`，铁律 6 各机自写）；
3. 手册只留**提炼后的通用案例**（教训进手册，经过进档案）。

「推而广之覆盖整个 allin」不能靠一次性人工清理 —— 那会像今天一样，
下个会话又把机器名写回公共文档。所以做成**对账工具**：持续扫描，持续点名。

## 扫描范围与豁免

- **扫**：`docs/` 下全部 `.md`。
- **豁免（属主正确，不点名）**：
  - `docs/事实源/机器/**` —— 各机事实源本尊，机器名就该在这；
  - `docs/记录/**` —— 交接卷/记忆/审计是时点记录，「只增不改」，
    历史里的机器名是证据不是污染；
  - `docs/INDEX.md` —— 索引要登记标题（标题含机名的文档条目合法）。

## 判定（侦察，不是判决）

本工具是**侦察**：找出「公共文档里出现机器标识」的行，报告文件/行号/标识/摘要，
由人（或 AI 协作者）对照各机事实源补登后**改写或移除**。
它不自动改写 —— 哪些内容值得提炼成案例、哪些直接删，是编辑判断。

零第三方依赖。退出码：0 无命中 / 1 有命中 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from .exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK
except ImportError:
    try:
        from exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK
    except ImportError:
        EXIT_OK, EXIT_FINDING, EXIT_ENV = 0, 1, 3

#: 机器标识（含 markdown 反引号包裹与裸写两种形态）
MACHINE_PAT = re.compile(r"@?`?(SIWPAN|DESKTOP-KQABATS|DESKTOP-8RSV60V|KQABATS|8RSV60V)`?")

#: 机器标识 → 各机事实源路径（报告里直接给出「该去哪」）
MACHINE_HOME = {
    "SIWPAN": "docs/事实源/机器/SIWPAN/SIWPAN.md",
    "DESKTOP-KQABATS": "docs/事实源/机器/DESKTOP-KQABATS/DESKTOP-KQABATS.md",
    "DESKTOP-8RSV60V": "docs/事实源/机器/DESKTOP-8RSV60V/DESKTOP-8RSV60V.md",
}

REPO_MARKERS = ("docs",)
#: 豁免清单（属主正确的位置）：
# - docs/记录/** 与 docs/记录的 ASCII 别名 docs/records/ —— 时点记录，机器名是证据
# - docs/事实源/机器/** 与别名 docs/facts/机器/** —— 各机事实源本尊
# - docs/事实源/机器分区索引.md —— **跨机共识**：机器清单与分区约定本来就住这里
# - docs/事实源/组合分级决策索引.md —— 分级台账，含各机盘位决策
# - docs/事实源/组合分级后续路线.md —— 同上族台账
# - docs/规范/SPEC-006-机器与路径约定.md —— 主题就是机器与路径，机器名是本体
# - docs/历史/**、docs/md/** —— 历史归档与外部工作区镜像（原样保全，SPEC-003）
# - docs/INDEX.md —— 索引登记标题
# ⚠ docs/spec|facts|records|md 是 junction 别名，不豁免就会把同一文件数两次。
EXEMPT = (
    "docs/记录/", "docs/records/",
    "docs/事实源/机器/", "docs/facts/机器/",
    "docs/事实源/机器分区索引.md", "docs/facts/机器分区索引.md",
    "docs/事实源/组合分级决策索引.md", "docs/facts/组合分级决策索引.md",
    "docs/事实源/组合分级后续路线.md", "docs/facts/组合分级后续路线.md",
    "docs/规范/SPEC-006-机器与路径约定.md", "docs/spec/SPEC-006-机器与路径约定.md",
    # SPEC-001 铁律里的「归属原点 / 跨机锚定」条：机器名是**规则的对象**（枚举三机目录），
    # 不是特化事实 —— 这条规则必须点名机器才成立。
    "docs/规范/SPEC-001-铁律.md", "docs/spec/SPEC-001-铁律.md",
    "docs/历史/", "docs/md/",
    "docs/INDEX.md",
)

#: 行内「路径引用」形态（不算特化内容）：`机器/SIWPAN/...`、`(docs/...)`、别名路径等。
LINK_PAT = re.compile(r"(机器/|事实源/|docs/|/)(SIWPAN|DESKTOP-KQABATS|DESKTOP-8RSV60V)")


def is_path_reference(line: str, match: re.Match) -> bool:
    """命中位置看起来是**路径/链接**而非事实叙述 ⇒ 不算特化内容。

    例：`[机器/SIWPAN/README.md](...)` 是合法链接；「SIWPAN 实测 blocking=50」才是内容。
    """
    start = max(0, match.start() - 12)
    context = line[start:match.end() + 2]
    return bool(LINK_PAT.search(context))


def scan(root: Path) -> list[dict]:
    hits: list[dict] = []
    # ⚠ docs/spec|facts|records|md 是 junction。rglob 会跟随 junction 把别名树里的
    # 文件再扫一遍 —— 路径错位、计数翻倍（实测 0.4.0 版曾把别名下旧副本的行报成
    # 主文件的行号）。所以目录层先解析真实路径，已扫过的跳过。
    seen_dirs: set[str] = set()
    files: list[Path] = []
    for d in (root / "docs").iterdir():
        if not d.is_dir():
            continue
        real = str(Path(os.path.realpath(d)))
        if real in seen_dirs:
            continue
        seen_dirs.add(real)
        files.extend(d.rglob("*.md"))
    for path in sorted(files):
        rel = path.relative_to(root).as_posix().replace("\\", "/")
        if any(rel.startswith(e) or rel == e for e in EXEMPT):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in MACHINE_PAT.finditer(line):
                if is_path_reference(line, m):
                    continue  # 路径/链接引用，不是特化内容
                ident = m.group(1)
                hits.append({
                    "file": rel,
                    "line": lineno,
                    "machine": ident,
                    "home": MACHINE_HOME.get(ident, "?"),
                    "text": line.strip()[:160],
                })
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="machine_content_audit",
        description="扫公共文档里的机器特化内容（该住各机事实源的内容），侦察报告",
    )
    ap.add_argument("--root", help="allin 仓根（默认按脚本位置探测）")
    ap.add_argument("--json", action="store_true", help="机读输出")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve() if args.root else None
    if root is None:
        for parent in Path(__file__).resolve().parents:
            if all((parent / m).is_dir() for m in ("docs", "tools")):
                root = parent
                break
    if root is None or not (root / "docs").is_dir():
        print("ENV ERROR: 找不到 allin 仓根", file=sys.stderr)
        return EXIT_ENV

    hits = scan(root)
    by_file: dict[str, int] = {}
    for h in hits:
        by_file[h["file"]] = by_file.get(h["file"], 0) + 1

    if args.json:
        print(json.dumps({"status": "clean" if not hits else "finding",
                          "total": len(hits), "by_file": by_file, "hits": hits},
                         ensure_ascii=False, indent=2))
    elif hits:
        print(f"== 机器特化内容侦察 ==  命中 {len(hits)} 处（{len(by_file)} 个文件）\n")
        for f, n in sorted(by_file.items(), key=lambda kv: -kv[1]):
            print(f"  {f}: {n} 处")
        print("\n明细（按文件）：")
        cur = None
        for h in hits:
            if h["file"] != cur:
                cur = h["file"]
                print(f"\n[{h['file']}]")
            print(f"  L{h['line']} [{h['machine']}] → 该住 {h['home']}")
            print(f"      {h['text'][:120]}")
        print("\n处置：对照各机事实源补登后，公共处改写为泛化案例或移除（教训进手册，经过进档案）。")
    else:
        print("== 机器特化内容侦察 ==  公共文档零特化，clean")

    return EXIT_OK if not hits else EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main())
