#!/usr/bin/env python3
"""check_undefined_names.py —— 轻量「未定义名」检查（弥补 py_compile 只查语法的盲区）。

背景（2026-09-23 沉淀）：批量改路径来源时，若只跑 `py_compile`，像「用了 tempfile 却没 import」
「str / str 做除法」这类问题**编译期查不出来**，要到运行时才炸。ruff 二进制在本机不齐，
故自带一个 AST 级检查器：把文件里所有被加载（Load）的名字收集起来，与
「import / 赋值 / def / class / for / with / except / 形参 / 全局内建」对照，
报告**全文从未定义过**的名字。

局限（已知，避免误判）：
  · 不做作用域精确分析（按「全文件定义过即算定义」），因此只会漏报、不会误报未定义名；
  · `from x import *`、`globals().update()`、`exec()` 注入的名字会被列为疑似未定义 → 命中时人工复核。

用法：
  python check_undefined_names.py <file.py> [file2.py ...]
  python check_undefined_names.py --repo repos/musickit            # 检查该仓「paths)」提交里改过的 .py
退出码：0 = 无疑似未定义名；1 = 有；2 = 参数错误。
"""
from __future__ import annotations

import ast
import builtins
import subprocess
import sys
from pathlib import Path

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__", "__loader__", "__builtins__", "__debug__", "WindowsError", "self", "cls"}


def collect_defined(tree: ast.AST) -> set[str]:
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            defined.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
            defined.update(node.names)
        elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
    return defined


def collect_loaded(tree: ast.AST) -> dict[str, int]:
    loads: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loads[node.id] = loads.get(node.id, 0) + 1
    return loads


def check(path: Path) -> list[tuple[str, int]]:
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(path))
    defined = collect_defined(tree) | BUILTINS
    # `from x import *` 一律放行
    star = any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names) for n in ast.walk(tree))
    if star:
        return []
    missing = []
    for name, cnt in sorted(collect_loaded(tree).items()):
        if name not in defined:
            missing.append((name, cnt))
    return missing


def files_from_repo(repo: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--grep=paths)", "--name-only", "--pretty=format:"],
        capture_output=True, text=True, errors="replace",
    ).stdout
    files = {repo / f.strip() for f in out.splitlines() if f.strip().endswith(".py")}
    return sorted(p for p in files if p.is_file())


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    targets: list[Path] = []
    if argv[0] == "--repo":
        for r in argv[1:]:
            targets += files_from_repo(Path(r))
    else:
        targets = [Path(a) for a in argv]

    bad = 0
    for p in targets:
        try:
            missing = check(p)
        except SyntaxError as e:
            print(f"  语法错误 {p}: {e}")
            bad += 1
            continue
        except Exception as e:  # noqa: BLE001
            print(f"  读取失败 {p}: {type(e).__name__}: {e}")
            bad += 1
            continue
        if missing:
            bad += 1
            print(f"  ★ {p}")
            for name, cnt in missing:
                print(f"      疑似未定义: {name}（出现 {cnt} 次）")
    print(f"  检查文件 {len(targets)} 个，疑似未定义名文件 {bad} 个")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
