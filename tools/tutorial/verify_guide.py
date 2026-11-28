#!/usr/bin/env python
"""逐条执行 `docs/新人开发上手指南.md` 里带 verify 标记的命令。

为什么要有这个脚本：调研的结论很硬——**命令不会失效的唯一可靠办法，是让它真的被执行一遍**。
写得再好只能降低腐坏速度。所以指南里的命令块不是给人看的装饰，而是被这个脚本跑的输入。

约定：
- 只有 ```` ```bash verify ```` 围栏里的行会被执行（其余代码块是示例文本，不跑）；
- 每行一条命令，按出现顺序执行；任一条退出码非 0 即失败并打印上下文；
- 断言输出：`--expect` 文件里「步号 → 必须出现的子串」，避免把整段输出写死。

用法：
    python tools/tutorial/verify_guide.py            # 只跑「快」的步（跳过 npm run check）
    python tools/tutorial/verify_guide.py --full     # 全跑（含门禁，约 70 秒）
    python tools/tutorial/verify_guide.py --list     # 只列出会执行什么
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "新人开发上手指南.md"
ROOT = GUIDE.parents[1]


def _env() -> dict:
    import os
    env = dict(os.environ)
    for cand in (ROOT / ".venv" / "Scripts", ROOT / ".venv" / "bin"):
        if cand.is_dir():
            env["PATH"] = str(cand) + os.pathsep + env.get("PATH", "")
            break
    return env

#: 标记为「慢」的命令：默认跳过，--full 才跑
SLOW = ("npm run check",)

#: 步号（从 1 起，按 verify 块出现顺序）→ 该步输出里必须出现的子串
EXPECT = {
    1: "Python 3.",
    2: "v22.",
    3: "git version 2.",
    4: "allin-governance 2.",
    5: "gate(s) clean",
    6: "健康分",
    7: "findings 0",
    8: "gate(s) clean",
}


def blocks(text: str) -> list[list[str]]:
    """取出所有 ```bash verify 块里的命令行。"""
    out, cur, inside = [], [], False
    for line in text.splitlines():
        if line.strip().startswith("```bash verify"):
            inside, cur = True, []
            continue
        if inside and line.strip().startswith("```"):
            inside = False
            if cur:
                out.append(cur)
            continue
        if inside and line.strip():
            cur.append(line.rstrip())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="包含慢命令（npm run check）")
    ap.add_argument("--list", action="store_true", help="只列出命令")
    args = ap.parse_args(argv)

    if not GUIDE.is_file():
        print(f"找不到指南：{GUIDE}", file=sys.stderr)
        return 2

    groups = blocks(GUIDE.read_text(encoding="utf-8"))
    if not groups:
        print("指南里没有任何 verify 块——要么标记丢了，要么路径变了", file=sys.stderr)
        return 2

    ran = skipped = 0
    for idx, cmds in enumerate(groups, start=1):
        for cmd in cmds:
            slow = any(cmd.strip().startswith(s) for s in SLOW)
            if slow and not args.full:
                print(f"  [skip {idx}] {cmd}（慢命令，--full 才跑）")
                skipped += 1
                continue
            if args.list:
                print(f"  [list {idx}] {cmd}")
                continue
            # 把仓内 venv 放到 PATH 最前：指南里的 `python` 应当就是装了治理核的那个解释器，
            # 否则新人会得到「命令存在但版本是系统的」这种最难查的错。
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=_env())
            out = (proc.stdout or "") + (proc.stderr or "")
            # `git status --short` 在干净工作树时无输出且退出码 0：不是失败
            ok = proc.returncode == 0
            want = EXPECT.get(idx)
            matched = (want in out) if want else True
            if not ok or not matched:
                print(f"FAIL 第 {idx} 步：{cmd}")
                print(f"  exit={proc.returncode}")
                print("  ---- 输出（前 20 行）----")
                for line in out.splitlines()[:20]:
                    print("  " + line)
                if want and not matched:
                    print(f"  期望输出里包含：{want!r}")
                return 1
            ran += 1
            print(f"  ok  [{idx}] {cmd}")

    if not args.list:
        print(f"== 教程校验通过：执行 {ran} 条，跳过 {skipped} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
