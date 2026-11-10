#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超时默认值门禁（P2 #20 / 审计 M-10）—— 包装 tools/runtime_defaults.py。

独立于 governance/gates/（g00-meta 沙箱只挂载 governance/，够不到 docs/事实源），
故落在 tools/gate/，从脚本位置自发现 tools/ 并 import **同一份**判据实现（单一事实源，
本文件不复制解析/校验逻辑）。

退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错（权威源缺席）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/ 根
import runtime_defaults as rd  # noqa: E402  单一事实源判据


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="runtime-defaults gate")
    ap.add_argument("--auth", type=Path, default=rd.DEFAULT_AUTH, help="权威源 JSON 路径")
    ap.add_argument("--check", action="store_true", help="默认动作：校验权威源 + 迁移一致性")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return rd.selftest()
    # 门禁语义：不显式跑判据就退 0 = 假绿，故未给 --check 也默认执行 check。
    rc, findings = rd.check(a.auth)
    print(f"RUNTIME_DEFAULTS_GATE exit={rc} findings={len(findings)}")
    for f in findings:
        print(f"  BLOCK {f}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
