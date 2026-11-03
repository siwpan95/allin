#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""allin-governance 包映射对账（ADR-0008）：已安装包 ↔ 仓内真身逐文件 sha256。

「一份源码两处消费」靠 pyproject 的跨目录 package-dir 映射（tools/repocheck →
_repocheck、tools/gate/governance → _gatesuite）。映射一致性此前只有一次性实测记录，
本脚本把它变成退出码：装出来的包与仓内源码逐文件哈希对账，不等即非 0。

CI 接线：gates.yml 的 init 端到端 job 在 `pip install packages/allin-governance`
之后立即跑（装的就是刚构建的 wheel，正是"发布物 ↔ 仓内真身"的对应关系）。
本地跑法：先装包（任意 venv），再用**同一个解释器**执行本脚本：
    pip install packages/allin-governance
    python tools/check_pkg_parity.py            # 仓根为默认基准
    python tools/check_pkg_parity.py --root <仓根>

退出码：0 一致；1 有差异（明细见输出）；3 环境错（包未安装 / 仓内目录缺失）。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# 已安装包内模块 → 仓内真身目录
PAIRS = [
    ("allin_governance._repocheck", "tools/repocheck"),
    ("allin_governance._gatesuite", "tools/gate/governance"),
]

# 仓内侧允许存在而不进包的文件（合法排除：运行时产物 / 编辑器杂项 / 点目录——
# setuptools 不会把 .github/.pytest_cache 等点目录打进包，属正常非对称）
REPO_ONLY_OK = {"__pycache__"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(root: Path) -> dict:
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in REPO_ONLY_OK or part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        if p.suffix == ".pyc":
            continue
        out[rel.as_posix()] = sha256_of(p)
    return out


def installed_pkg_dir(module_name: str, override: dict | None = None) -> Path:
    if override and module_name in override:
        return Path(override[module_name]).resolve()
    import importlib

    mod = importlib.import_module(module_name)
    d = Path(getattr(mod, "__path__")[0])
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="仓库根（默认当前目录）")
    ap.add_argument(
        "--pkg-dir",
        action="append",
        default=[],
        metavar="MODULE=PATH",
        help="跳过 importlib 定位，直接指定已安装包目录（本地无 venv 时的等价验证口；"
        "可多次：如 allin_governance._repocheck=C:/tmp/_repocheck）",
    )
    args = ap.parse_args()
    repo_root = Path(args.root).resolve()
    overrides = dict(kv.split("=", 1) for kv in args.pkg_dir)

    problems = []
    for module_name, repo_rel in PAIRS:
        repo_dir = repo_root / repo_rel
        if not repo_dir.is_dir():
            print(f"ENV-ERROR: 仓内目录缺失 {repo_dir}")
            return 3
        try:
            pkg_dir = installed_pkg_dir(module_name, overrides)
        except ImportError as e:
            print(f"ENV-ERROR: {module_name} 未安装（先 pip install packages/allin-governance 再跑本脚本）：{e}")
            return 3
        pkg_files = collect(pkg_dir)
        repo_files = collect(repo_dir)
        for rel, h in sorted(pkg_files.items()):
            if rel not in repo_files:
                problems.append(f"[{module_name}] 包内有、仓内无：{rel}（陈旧打包）")
            elif repo_files[rel] != h:
                problems.append(f"[{module_name}] 哈希不等：{rel}")
        for rel in sorted(repo_files):
            if rel not in pkg_files:
                problems.append(f"[{module_name}] 仓内有、包内无：{rel}（映射漏收，pyproject packages/package-data 待补）")
        n = len(pkg_files)
        print(f"  {module_name} <-> {repo_rel}: 包内 {n} 文件已对账")

    if problems:
        print(f"\n对账失败 {len(problems)} 处（ wheel 是构建时点快照，仓内演进后须重新构建发布；"
              f"或 pyproject 映射/包数据清单需修正）：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n包映射对账通过：已安装包与仓内真身逐文件 sha256 一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
