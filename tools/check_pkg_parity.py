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
import os
import sys
from pathlib import Path

# P3 L-4：文件字节摘要委托 tools/sha256util.py 的同族实现（完整 64 位 + LF 归一，铁律 12）。
# 本脚本与 sha256util 同在 tools/ 根，作为脚本运行时该目录即 sys.path[0]，可直接导入。
from sha256util import file_sha256

# Windows CI runner 的 stdout 默认 ANSI(cp1252)：本脚本逐文件打印中文进度，
# 不 reconfigure 会在第一行「包内 N 文件已对账」就 UnicodeEncodeError，独立 step
# 直接 exit 1 且看不到任何差异明细（2026-11-04 CI 实测）。与 check_gate_drift.py
# 同一层兜底；reconfigure 是 3.7+ API，仓要求 3.9+，被替换的流没有该方法时静默跳过。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 已安装包内模块 → 仓内真身目录
PAIRS = [
    ("allin_governance._repocheck", "tools/repocheck"),
    ("allin_governance._gatesuite", "tools/gate/governance"),
]

# 仓内侧允许存在而不进包的文件（合法排除：运行时产物 / 编辑器杂项 / 点目录——
# setuptools 不会把 .github/.pytest_cache 等点目录打进包，属正常非对称）。
#
# 另有一类：tools/repocheck 自身作为独立包携带的开发/构建元数据。映射成
# allin_governance._repocheck 后，包内只需 .py 源码 + pyproject 已列的
# README/LICENSE/CHANGELOG；下面这些是 repocheck 自己的发布/贡献/打包文件，
# 与治理门禁运行时无关，刻意不随 wheel（2026-11-04 对账首跑定位，8 处）。
# 注意别把运行时事实源加进来 —— exceptions.yml / registry-known-gaps.txt /
# preset/* 属于必须进包的那一侧，已由 pyproject 的 package-data 补齐。
REPO_ONLY_OK = {
    "__pycache__",
    "CONTRIBUTING.md", "SECURITY.md", "SKILL.md", "pyproject.toml",
    "repocheck-dbg.spec", "repocheck.spec",
    "requirements-dev.txt", "requirements.txt",
}


def sha256_of(path: Path) -> str:
    """文件字节摘要（完整 64 位 + LF 归一）—— 委托 tools/sha256util.py（P3 L-4）。

    铁律 12（见 tools/gate/check_gate_drift.py）：跨副本比对不归一化 EOL 会得出
    假差异。Windows 上 setuptools 以文本模式构建 wheel 会把 .py 写成 CRLF，而
    仓内 .gitattributes 强制 eol=lf；两侧是同一份源码，只是换行形态不同，不是漂移。
    实测：把已装包内一份 .py 改 CRLF，旧实现即报「哈希不等」（Linux 全 LF 不复现）。
    这两个目录全是文本源码（.py/.md/.txt/.yml/.json/.ts/.spec/.toml），无二进制。
    """
    return file_sha256(path)


def gh_escape(s: str) -> str:
    # GitHub Actions 的 ::error:: workflow command 数据里 % / CR / LF 必须百分号编码，
    # 否则 annotation 会被截断。job logs 端点匿名 403，annotations 是唯一公开可读通道。
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


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
        "可多次，格式 MODULE=<已安装包目录>，如 allin_governance._repocheck 指向拷贝出的 _repocheck 目录）",
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
            print(
                "  ⚠ 若你用的是**可编辑安装**（pip install -e packages/allin-governance），"
                "本脚本多半仍会报此错 —— 可编辑安装不把跨目录 package-dir 映射"
                "（allin_governance._repocheck / _gatesuite）落进 site-packages，"
                "而对账的正是**已落盘的发布物**。请改用真实 wheel 安装：\n"
                "      pip install --force-reinstall --no-deps packages/allin-governance\n"
                "  （CI 的口径即如此，见 gates.yml 的『可安装包映射对账』步骤；"
                "另可用 --pkg-dir 直接指定已装包目录绕过 importlib 定位。）"
            )
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
        if os.environ.get("GITHUB_ACTIONS") == "true":
            # 这个 step 是 gates.yml 里独立的 run:，不经 run_all_gates.sh 的 run()，
            # 上面的明细落在 job logs 里匿名 403；逐条推成 annotation 才能直接定位。
            for p in problems:
                print(f"::error::包映射对账失败：{gh_escape(p)}")
        return 1
    print("\n包映射对账通过：已安装包与仓内真身逐文件 sha256 一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
