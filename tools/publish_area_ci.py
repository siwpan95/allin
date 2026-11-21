r"""publish_area_ci.py —— 发布区最小 CI 批量铺设（CI 覆盖 13/139 → 全绿仓覆盖）

为什么有这个脚本
    发布区 139 仓中只有 13 仓有真 CI（`.github/workflows/*.yml`），
    21 仓的 `.gitee/` 只是 issue/PR 模板（不是 workflow），105 仓完全没有 CI。
    「CI 覆盖」此前统计成 34 仓就是把 Gitee 模板误当 CI 造成的虚高。

    本工具给**实测能通过本仓自检**的仓铺最小 CI：
      clean clone → 装 requirements.txt → `python selfcheck.py`。

先清零再接门禁（不铺假绿）
    ⚠ 不是给所有无 CI 仓铺 —— 只给 selfcheck **本地实测真绿**的仓铺。
    实测口径：临时 venv 装通用依赖后逐仓跑 selfcheck.py，只有 exit=0 的仓
    才进入铺设名单（名单见 --only-covered 参数传入的 CSV/逗号分隔）。
    跑不通的仓先记账为债务（依赖缺失 / 兄弟仓依赖 / 重构遗留），不铺 CI ——
    铺上去必红的 CI 比零 CI 更糟（既制造噪音又让人习惯红灯）。

    本工具**不判 selfcheck 能否通过**（那是运行时事实，不写死在工具里），
    只负责按给定名单生成 workflow 文件。名单由调用方实测后传入。

模板从各仓自身事实推导
    · 自检入口 = 仓根 `selfcheck.py`（各仓统一约定，实测 67 仓都有）；
    · 依赖清单 = 仓根 `requirements.txt`（上一轮已 AST 实测补齐）；
    · Python 钉 3.11：3.13 移除了 audioop，pydub 等音频依赖导入即失败（实测）。
    · 只**新增** `.github/workflows/selfcheck.yml`，不改任何既有 workflow。

用法
    python tools/publish_area_ci.py --repos-root <发布区根> --covered "repo1,repo2,..." --dry-run
    python tools/publish_area_ci.py --repos-root <发布区根> --covered-file covered.csv --apply

退出码
    0 无待办
    1 有待铺（预演）或已完成铺设（--apply）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

WORKFLOW_NAME = "selfcheck.yml"

TEMPLATE = '''name: selfcheck

# 本仓的最小 CI：clean clone → 装依赖 → 跑本仓自带的无头自检。
# 由 allin 仓 tools/publish_area_ci.py 生成（2026-11-21）；入口与依赖取自本仓自身事实。
# 钉 Python 3.11：3.13 移除了 audioop，pydub 等音频依赖在 3.13 上导入即失败。
on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:

jobs:
  selfcheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 安装依赖
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
      - name: 无头自检
        run: python selfcheck.py
        env:
          PYTHONIOENCODING: utf-8
          SDL_VIDEODRIVER: dummy
          SDL_AUDIODRIVER: dummy
'''


def has_ci(repo: Path) -> bool:
    wf = repo / ".github" / "workflows"
    return wf.is_dir() and any(wf.glob("*.yml")) or (wf.is_dir() and any(wf.glob("*.yaml")))


def load_covered(args) -> set[str]:
    names: set[str] = set()
    if args.covered:
        names |= {s.strip() for s in args.covered.split(",") if s.strip()}
    if args.covered_file:
        p = Path(args.covered_file)
        if not p.is_file():
            raise ValueError(f"名单文件不存在：{p}")
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.strip().split(",")[0].strip().strip('"')
            if name and not name.lower().startswith(("repo", "#")):
                names.add(name)
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区最小 CI 批量铺设")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--covered", default="", help="实测自检真绿的仓名（逗号分隔）")
    ap.add_argument("--covered-file", default="", help="同上，从 CSV/文本读（每行首列仓名）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = args.repos_root
    if not root or not Path(root).is_dir():
        print("用法错误：需 --repos-root 指向存在的发布区", file=sys.stderr)
        return 2
    try:
        covered = load_covered(args)
    except ValueError as exc:
        print(f"用法错误：{exc}", file=sys.stderr)
        return 2

    rp = Path(root)
    todos: list[dict] = []
    skipped: list[dict] = []
    for name in sorted(covered):
        repo = rp / name
        if not (repo / ".git").exists():
            skipped.append({"repo": name, "why": "not-a-repo"})
            continue
        if has_ci(repo):
            skipped.append({"repo": name, "why": "already-has-ci"})
            continue
        if not (repo / "selfcheck.py").is_file():
            skipped.append({"repo": name, "why": "no-selfcheck"})
            continue
        if not (repo / "requirements.txt").is_file():
            skipped.append({"repo": name, "why": "no-requirements"})
            continue
        todos.append({"repo": name})

    if args.json:
        import json
        print(json.dumps({"covered": len(covered), "todo": len(todos),
                          "todos": todos, "skipped": skipped}, ensure_ascii=False, indent=2))
    else:
        print(f"实测真绿名单 {len(covered)} 仓，待铺 {len(todos)} 仓")
        for t in todos:
            print(f"  {t['repo']}")
        if skipped:
            print(f"跳过 {len(skipped)}:")
            for s in skipped:
                print(f"  {s['repo']}: {s['why']}")

    if not todos:
        return 0
    if not args.apply:
        print("\n预演模式：加 --apply 实际写入 workflow")
        return 1

    for t in todos:
        repo = rp / t["repo"]
        wf = repo / ".github" / "workflows"
        wf.mkdir(parents=True, exist_ok=True)
        target = wf / WORKFLOW_NAME
        target.write_text(TEMPLATE, encoding="utf-8", newline="\n")
    print(f"\n已为 {len(todos)} 仓写入 .github/workflows/{WORKFLOW_NAME}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
