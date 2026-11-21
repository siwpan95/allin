r"""publish_area_cli.py —— 给发布区各仓补统一 CLI 入口（已有则跳过）

为什么有这个脚本
    发布区 139 仓里 65 仓已有真 CLI 入口（console_scripts / package.json bin /
    带 argparse 的 main），其余 74 仓只能靠"读 README 猜怎么跑"。全哥要求
    「给所有 repos 项目补 CLI 命令行接口，已经有的项目跳过」。

设计原则：不臆造业务功能
    这些仓多数是 GUI 小游戏（tkinter / pygame），它们的"业务"就是开窗口。
    给它们编造 `--render` / `--export` 之类子命令等于把不存在的接口写进代码。
    所以 CLI 只提供**能从仓自身事实推导**的四件事：

      info       版本 / 入口 / 自检 / 依赖 的机器可读概览（json）
      version    打印版本
      selfcheck  跑本仓 `selfcheck.py`（存在才有）
      launch     启动本仓 GUI 入口（存在才有）

    版本从 `pyproject.toml` / `package.json` / `__init__.py` 实读，
    入口从仓根候选（main.py / app.py / gui.py / run.py / __main__.py）实探测，
    全部写进生成文件顶部的常量 —— 生成后不依赖任何外部工具即可运行。

判定「已有 CLI」的口径（与 74 仓分档一致）
    满足任一条即跳过：
      1. pyproject/setup.py 声明 console_scripts 或 [project.scripts]
      2. package.json 声明 bin
      3. 仓内任一 .py 用 argparse / click / typer 且文件名属入口候选
    宁可错跳（少补一个）也不覆盖：覆盖别人的 CLI 是破坏性动作。

用法
    python tools/publish_area_cli.py --repos-root <发布区根> --dry-run
    python tools/publish_area_cli.py --repos-root <发布区根> --apply

退出码
    0 无待办
    1 有待补（预演）或已完成（--apply）
    2 用法/环境错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

CLI_NAME = "cli.py"

#: 仓根 GUI / 程序入口候选（按优先级）。命中第一个即用。
ENTRY_CANDIDATES = ("main.py", "app.py", "gui.py", "run.py", "__main__.py")

#: 判定「已有 CLI」时扫描的入口文件名（含子目录常见形态）
CLI_MARKERS = ("__main__.py", "cli.py", "main.py", "run.py", "app.py")

#: 扫描 CLI 时要跳过的路径段。
#: `allin_engine` / `expand_shared` 是**跨仓复制的共享引擎副本**（mahjong、fish、
#: sandbox 等都内嵌一份），它们的 cli.py 是引擎的接口，不是本仓的产品接口 ——
#: 实测若不排除，mahjong 会被误判为「已有 CLI」而漏补。
#: 引擎本体所在仓（an-engine、dwarf-scrolls）由 pyproject 的 entry_points 判定先行跳过。
_CLI_SKIP_SEGMENTS = (
    ".venv", "venv", "node_modules", "vendor", "dist", "build", "__pycache__",
    "allin_engine", "expand_shared", "dse_core", "_ref", "reference", ".orphan",
)

_CLI_LIB = re.compile(r"\b(argparse|click|typer)\b")

TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""{name} · 命令行接口。

由 allin 仓 `tools/publish_area_cli.py` 生成（2026-11-21）。
本文件只暴露**能从本仓自身事实推导**的能力，不含臆造的业务子命令：

    info        版本 / 入口 / 自检 / 依赖的机器可读概览（json）
    version     打印版本
    selfcheck   跑本仓无头自检（selfcheck.py）
    launch      启动本仓入口（{entry}）

来源事实：
    版本 = {version_source}
    入口 = {entry_source}
    自检 = {selfcheck_source}

直接运行：`python cli.py [子命令]`
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = {name!r}
VERSION = {version!r}
VERSION_SOURCE = {version_source!r}
ENTRY = {entry!r}
HAS_SELFCHECK = {has_selfcheck!r}


def _deps_count() -> int:
    """requirements.txt 里非注释非空行数（没有该文件则为 0）。"""
    req = ROOT / "requirements.txt"
    if not req.is_file():
        return 0
    n = 0
    for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def cmd_info(_args: argparse.Namespace) -> int:
    print(json.dumps({{
        "name": NAME,
        "version": VERSION,
        "version_source": VERSION_SOURCE,
        "entry": ENTRY,
        "selfcheck": HAS_SELFCHECK,
        "requirements": _deps_count(),
        "root": str(ROOT),
    }}, ensure_ascii=False, indent=2))
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(VERSION or "unknown")
    return 0


def _run(script: str, argv: list[str]) -> int:
    target = ROOT / script
    if not target.is_file():
        print(f"未找到 {{script}}", file=sys.stderr)
        return 3
    return subprocess.call([sys.executable, str(target), *argv])


def cmd_selfcheck(args: argparse.Namespace) -> int:
    if not HAS_SELFCHECK:
        print("本仓没有 selfcheck.py", file=sys.stderr)
        return 3
    return _run("selfcheck.py", args.passthrough)


def cmd_launch(args: argparse.Namespace) -> int:
    if not ENTRY:
        print("本仓无可识别的入口脚本（main.py / app.py / gui.py / run.py）", file=sys.stderr)
        return 3
    return _run(ENTRY, args.passthrough)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=NAME,
        description=f"{{NAME}} 命令行接口（由 allin publish_area_cli.py 生成）",
    )
    p.add_argument("--version", action="version", version=f"{{NAME}} {{VERSION or 'unknown'}}")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("info", help="机器可读的仓概览（json）").set_defaults(func=cmd_info)
    sub.add_parser("version", help="打印版本").set_defaults(func=cmd_version)

    sc = sub.add_parser("selfcheck", help="跑本仓无头自检")
    sc.add_argument("passthrough", nargs=argparse.REMAINDER, help="透传给 selfcheck.py 的参数")
    sc.set_defaults(func=cmd_selfcheck)

    lc = sub.add_parser("launch", help="启动本仓入口脚本")
    lc.add_argument("passthrough", nargs=argparse.REMAINDER, help="透传给入口脚本的参数")
    lc.set_defaults(func=cmd_launch)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _read_version(repo: Path) -> tuple[str, str]:
    """从本仓事实读版本，返回 (版本, 来源说明)。"""
    pj = repo / "pyproject.toml"
    if pj.is_file():
        text = pj.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.M)
        if m:
            return m.group(1), "pyproject.toml [project].version"
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data.get("version"), str):
                return data["version"], "package.json version"
        except (json.JSONDecodeError, OSError):
            pass
    for cand in sorted(repo.glob("*/__init__.py")) + [repo / "__init__.py"]:
        if not cand.is_file():
            continue
        # 与 CLI 判定同一排除集：内嵌共享引擎（allin_engine）的 __version__ 是**引擎**的
        # 版本，不是本仓的。实测 mahjong 读到了 allin_engine 的 1.0.0 —— 与本仓无关。
        if any(x in cand.parts for x in _CLI_SKIP_SEGMENTS):
            continue
        text = cand.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^__version__\s*=\s*[\'"]([^\'"]+)', text, re.M)
        if m:
            return m.group(1), f"{cand.relative_to(repo).as_posix()} __version__"
    return "", "未声明"


def _find_entry(repo: Path) -> str:
    """仓根入口候选，命中即返回文件名。"""
    for name in ENTRY_CANDIDATES:
        if (repo / name).is_file():
            return name
    return ""


def _has_cli(repo: Path) -> str | None:
    """已有 CLI 入口则返回证据串，否则 None。"""
    for fname in ("pyproject.toml", "setup.py", "setup.cfg"):
        p = repo / fname
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if "console_scripts" in text or "[project.scripts]" in text:
                return f"{fname}:entry-points"
    pj = repo / "package.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
            if data.get("bin"):
                return "package.json:bin"
        except (json.JSONDecodeError, OSError):
            pass
    # 仓根启动脚本本身就是命令行入口（dsh-release-archiver 的 run.sh/run.cmd 即此类），
    # 再补一个 cli.py 只会制造两个事实源。
    for fname in ("run.sh", "run.cmd", "run.ps1"):
        if (repo / fname).is_file():
            return fname
    for name in CLI_MARKERS:
        for p in repo.rglob(name):
            if any(x in p.parts for x in _CLI_SKIP_SEGMENTS):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if _CLI_LIB.search(text) and ("__main__" in text or "def main" in text):
                return p.relative_to(repo).as_posix()
    return None


def _has_python(repo: Path) -> bool:
    """仓内是否有可执行的 Python 源码（纯资产/纯文档仓不适合加 CLI）。"""
    for p in repo.rglob("*.py"):
        if any(x in p.parts for x in (".venv", "venv", "node_modules", "vendor", "__pycache__", "dist", "build")):
            continue
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区统一 CLI 入口铺设")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default="", help="只处理这些仓（逗号分隔）")
    args = ap.parse_args(argv)

    root = args.repos_root
    if not root or not Path(root).is_dir():
        print("用法错误：需 --repos-root 指向存在的发布区", file=sys.stderr)
        return 2
    rp = Path(root)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    todo: list[dict] = []
    skipped: list[dict] = []
    for repo in sorted(rp.iterdir()):
        if not repo.is_dir() or not (repo / ".git").exists():
            continue
        if only and repo.name not in only:
            continue
        if (repo / CLI_NAME).exists():
            skipped.append({"repo": repo.name, "why": "already-has-cli.py"})
            continue
        evidence = _has_cli(repo)
        if evidence:
            skipped.append({"repo": repo.name, "why": f"has-cli:{evidence}"})
            continue
        if not _has_python(repo):
            skipped.append({"repo": repo.name, "why": "no-python-source"})
            continue
        version, vsource = _read_version(repo)
        entry = _find_entry(repo)
        has_sc = (repo / "selfcheck.py").is_file()
        todo.append({
            "repo": repo.name,
            "version": version,
            "version_source": vsource,
            "entry": entry,
            "entry_source": f"仓根 {entry}" if entry else "无可识别入口",
            "has_selfcheck": has_sc,
            "selfcheck_source": "selfcheck.py" if has_sc else "无",
        })

    if args.json:
        print(json.dumps({"todo": todo, "skipped": skipped}, ensure_ascii=False, indent=2))
        if not todo:
            return 0
        if not args.apply:
            return 1
    else:
        print(f"待补 CLI: {len(todo)} 仓 ｜ 跳过 {len(skipped)} 仓")
        for t in todo:
            print(f"  {t['repo']:<26} v{t['version'] or '?':<10} 入口={t['entry'] or '-'} 自检={'有' if t['has_selfcheck'] else '无'}")
        if not todo:
            return 0
        if not args.apply:
            print("\n预演模式：加 --apply 实际写入 cli.py")
            return 1

    for t in todo:
        content = TEMPLATE.format(
            name=t["repo"],
            version=t["version"],
            version_source=t["version_source"],
            entry=t["entry"],
            entry_source=t["entry_source"],
            has_selfcheck=t["has_selfcheck"],
            selfcheck_source=t["selfcheck_source"],
        )
        (rp / t["repo"] / CLI_NAME).write_text(content, encoding="utf-8", newline="\n")
    print(f"\n已为 {len(todo)} 仓写入 {CLI_NAME}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
