#!/usr/bin/env python3
"""verify_facts -- 命令行入口：校验 `docs/事实源/机器/*.md` 的断言是否与磁盘一致。

判据**不在本文件**，在门禁 `tools/gate/governance/gates/g20_facts.py`。
这里只是把它包成可直接跑的 CLI。

为什么不各写一份
----------------
* 两套判据会同时报绿、冲突时无人判定谁为准 —— 正是 `SPEC-003 §新建三查` 要防的形态；
* 门禁那边必须自包含 —— `g00-meta` 把每个 `--selfcheck` 放进只有 `governance/` 的沙箱里跑，
  够不到 `tools/facts/`。

所以依赖方向是：**门禁定义判据，本 CLI 复用门禁。**

判据范围（详见门禁模块 docstring）
---------------------------------
只判两类可机械判的断言，作用域是文件头部**日期最新的时点块**：

* ``path-exists`` —— 行内声称某机器绝对路径「现已存在 / 现存 / 仍在位」则必须存在；
  声称「现已不存在 / 已不存在 / 均不存在 / MISSING / 已删 / 已移除」则必须不存在。
* ``count`` —— 绝对路径后跟 ``**N**`` 或 ``N 项`` 时，实际条目数必须等于 N。
  口径按单位切换：``项`` 数全部条目，无单位或 ``个仓`` / ``个目录`` 只数目录。

用法
----
    python tools/facts/verify_facts.py                 # 只校验**当前机器**的分区文件
    python tools/facts/verify_facts.py --all           # 显式校验全部机器文件（跨机诊断）
    python tools/facts/verify_facts.py --file x.md     # 只校验一份（自检用）
    python tools/facts/verify_facts.py --json
    python tools/facts/verify_facts.py --selftest      # 跑门禁同一套夹具

机器过滤（2026-10-30，与 g20 门禁同口径）
----------------------------------------
分区文件描述**一台机器**的磁盘；在本机验别机的文件 = 拿错盘对账，永远报假红
（g20 门禁 2026-10-30 已修，本 CLI 同步）。默认只验文件名与当前主机名匹配
（大小写不敏感）的那份；``--all`` 显式关闭过滤，用于有意查看别机文件在本机的
判定结果（其 finding 只说明「该路径在本机不存在」，不代表别机事实有错）。

退出码：0 干净，1 有 finding，2 用法错误，3 环境错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GATE_MODULE_DIR = Path(__file__).resolve().parents[2] / "tools" / "gate" / "governance" / "gates"
EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3


def load_gate():
    """把门禁模块当库导入 —— 判据唯一来源。"""
    candidate = GATE_MODULE_DIR / "g20_facts.py"
    if not candidate.is_file():
        print(f"ENV ERROR: 找不到判据实现：{candidate}", file=sys.stderr)
        return None
    if str(GATE_MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(GATE_MODULE_DIR))
    import g20_facts  # noqa: PLC0415  (deliberately late: path fixed up above)

    return g20_facts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_facts", description="校验机器事实源的断言")
    parser.add_argument("--root", help="仓根（默认自动探测）")
    parser.add_argument("--file", help="只校验指定文件")
    parser.add_argument("--all", action="store_true",
                        help="校验全部机器文件（默认只验当前机器那份；见模块 docstring）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--selftest", action="store_true", help="跑与门禁同一套夹具")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print("ENV ERROR: 只支持 Windows（判据是 Windows 绝对路径）", file=sys.stderr)
        return EXIT_ENV

    gate = load_gate()
    if gate is None:
        return EXIT_ENV

    if args.selftest:
        return EXIT_OK if gate.selfcheck() == 0 else EXIT_FINDING

    if args.file:
        target = Path(args.file)
        if not target.is_file():
            print(f"USAGE ERROR: 文件不存在：{target}", file=sys.stderr)
            return EXIT_USAGE
        files = [target]
        skipped: list[str] = []
    else:
        root = Path(args.root).resolve() if args.root else None
        if root is None:
            for candidate in Path(__file__).resolve().parents:
                if (candidate / "docs").is_dir() and (candidate / "preset").is_dir():
                    root = candidate
                    break
        if root is None:
            print("ENV ERROR: 找不到仓根（需含 docs/ 与 preset/）", file=sys.stderr)
            return EXIT_ENV
        target_dir = root / gate.TARGET_DIR
        candidates = sorted(target_dir.glob("*.md"))
        if not candidates:
            print(f"ENV ERROR: {target_dir} 下没有 md 文件", file=sys.stderr)
            return EXIT_ENV
        if args.all:
            files, skipped = candidates, []
        else:
            me = gate.current_machine()
            files = [p for p in candidates if p.stem.lower() == me]
            skipped = [p.name for p in candidates if p.stem.lower() != me]
            if not files:
                print(f"ENV ERROR: {target_dir} 下没有当前机器（{me}）的分区文件 —— "
                      f"新增机器流程见 docs/事实源/机器分区索引.md §1（或用 --all 显式跨机诊断）",
                      file=sys.stderr)
                return EXIT_ENV

    all_findings: list[dict] = []
    freshness: dict[str, str] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        findings, stamp = gate.check_text(text, path.name)
        all_findings.extend(findings)
        freshness[path.name] = gate.evaluate_staleness(stamp)

    if args.json:
        print(json.dumps({"findings": all_findings, "freshness": freshness,
                          "skipped": skipped}, ensure_ascii=False, indent=2))
    else:
        for name, note in freshness.items():
            print(f"[{name}] {note}")
        for name in skipped:
            print(f"[skip] {name}: 非当前机器（{gate.current_machine()}）的分区文件，留待该机自验"
                  f"（--all 可显式跨机诊断）")
        print(f"scanned {len(files)} file(s); findings {len(all_findings)}")
        for finding in all_findings:
            print(f"  {finding['file']}:{finding['line']}  {finding['kind']}  {finding['claim']}")

    return EXIT_OK if not all_findings else EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main())
