#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deps_doctor.py —— 依赖体检：声明 / 实装 / 实际 import 三者对账。

为什么需要它
------------
``requirements-dev.txt`` 的注释里写着一段真实的历史：

> 此前新人只能从报错信息反推该装什么。

本仓的依赖集很小（7 个包），但**缺一个就有一类门禁静默失效**：
缺 PyYAML → g18 报 `ledger-unusable` 假红；缺 pytest-cov → 覆盖率步骤退化成普通跑测。
这些都不是"装不上就崩"，而是"装不上就少查一层"—— 比崩溃更危险。

``scripts/bootstrap.sh`` 已经会按 ``requirements-dev.txt`` 一次性装齐。本工具补的是
**装完之后**和**换机之后**的那一段：

| 场景 | 靠什么发现 |
|---|---|
| 声明了但没装（有人手动跳过了某一步） | 声明集 − 实装集 |
| 代码 import 了既没声明也没装的包 | import 集 − (声明 ∪ 实装) |
| 装了但没声明（传递依赖被误当直接依赖） | 实装集 − 声明集，且被直接 import（**这才是真问题**） |

第三类最隐蔽：某天上游把传递依赖换了，代码就突然 ImportError。

设计取舍
--------
- **只报告，不自动安装。** 自动 pip install 会掩盖「依赖清单本身错了」这个更根本的问题，
  也会在离线/受限网络下把诊断变成噪音。
- **不把「装了很多但没声明」一律判红。** .venv 里天然有传递依赖（pytest 会带一堆）；
  只有「被本仓代码直接 import 却没声明」才算问题。
- 标准库判断用 ``sys.stdlib_module_names``（3.10+），不维护手工清单。

用法
----
    python tools/deps_doctor.py                  # 检查仓内 .venv
    python tools/deps_doctor.py --python /path/to/python.exe
    python tools/deps_doctor.py --json
    python tools/deps_doctor.py --fix-hint       # 只打印「该装什么」的 pip 命令

退出码：0 无缺失 / 1 有缺失或未声明依赖 / 3 环境无法读取。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

#: 扫描 import 时跳过的目录：第三方内联副本与产物不算「本仓代码」。
SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "vendor", "dist", "build", "site-packages", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "archive-fragments", "audit-fragments",
})

#: 导入名 → 发行名的常见映射（两者不同名是最常见的误判来源）。
IMPORT_TO_DIST = {
    "yaml": "PyYAML",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "attr": "attrs",
    "jwt": "PyJWT",
    "dateutil": "python-dateutil",
    "git": "GitPython",
    "serial": "pyserial",
    "OpenSSL": "pyOpenSSL",
    "Crypto": "pycryptodome",
    "watchdog": "watchdog",
    "pytest_cov": "pytest-cov",
    "pip_audit": "pip-audit",
}

_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)")

#: requirements 文件的注释里用「包名 —— 用途」声明可选依赖（见该文件末尾那段）。
#: 它们按设计允许缺失（缺失时对应能力降级），所以单列一类，不计入「缺失」。
_OPTIONAL_LINE = re.compile(r"^#\s*([A-Za-z0-9_.\-]+)\s+——")


def normalize(name: str) -> str:
    """PEP 503 归一化：大小写、下划线/点/连字符等价。"""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def parse_requirements(path: Path) -> list[str]:
    """读 requirements 文件，返回发行名列表（忽略注释/空行/选项行）。"""
    out: list[str] = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _REQ_LINE.match(line)
        if m:
            out.append(m.group(1).split("[", 1)[0])
    return out


def parse_optional(path: Path) -> set[str]:
    """解析 requirements 注释里的可选依赖名（归一化）。"""
    out: set[str] = set()
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _OPTIONAL_LINE.match(line.strip())
        if m:
            out.add(normalize(m.group(1)))
    return out


def installed_dists(py: str) -> dict[str, str]:
    """实装发行名 → 版本。用 pip list --format=json，解析比 freeze 稳。"""
    try:
        out = subprocess.run(
            [py, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
            capture_output=True, text=True, timeout=120, errors="replace",
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout)
        return {normalize(d["name"]): d["version"] for d in data}
    except Exception:
        return {}


def local_module_names(root: Path) -> set[str]:
    """本仓**自己的**模块名集合，用于把「同仓 import」从第三方里剔除。

    覆盖三类，缺一类就会误报：
    1. 所有 ``.py`` 的 stem（`tools/gate/govlib.py` → ``govlib``）
    2. 所有目录名（`packages/allin-governance/src/allin_governance/` → ``allin_governance``）
    3. ``vendor/`` 下的内联包（`vendor/cordis/` → ``cordis``）—— 它们刻意不入依赖清单，
       因为随仓分发、离线可审计。

    遍历时**不跳过 vendor**：跳过是为了「不扫它的代码」，但它的**包名**恰恰必须被收集。
    """
    names: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}]
        for d in dirnames:
            names.add(d)
        for fn in filenames:
            if fn.endswith(".py"):
                names.add(fn[:-3])
    return names


def scan_imports(root: Path, local: set[str]) -> dict[str, set[str]]:
    """扫本仓 .py 的顶层 import。返回 ``import名 → {来源文件}``。"""
    found: dict[str, set[str]] = {}
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = Path(dirpath) / fn
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:  # 相对导入，跳过
                        continue
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for name in names:
                    if not name or name in stdlib or name.startswith("_"):
                        continue
                    # 本仓自有模块（含 vendor 内联包）不算第三方
                    if name in local:
                        continue
                    found.setdefault(name, set()).add(
                        path.relative_to(root).as_posix())
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="依赖体检：声明/实装/import 三者对账")
    ap.add_argument("--root", default=None, help="仓根（默认本文件上级）")
    ap.add_argument("--python", default=None, help="要检查的解释器（默认仓内 .venv，否则当前）")
    ap.add_argument("--req", default=None, help="requirements 文件（默认 requirements-dev.txt）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-hint", action="store_true", help="只打印安装命令")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    req_path = Path(args.req) if args.req else root / "requirements-dev.txt"

    if args.python:
        py = args.python
    else:
        cand = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        py = str(cand) if cand.exists() else sys.executable

    declared = parse_requirements(req_path)
    optional = parse_optional(req_path)
    installed = installed_dists(py)
    if not installed:
        print(f"[ERR] 读不到解释器的已装包列表：{py}", file=sys.stderr)
        return 3
    local = local_module_names(root)
    imports = scan_imports(root, local)

    declared_n = {normalize(d) for d in declared}
    missing = [d for d in declared if normalize(d) not in installed]

    # import 到的第三方 → 尝试映射到发行名，判断是否「既没声明也没装」
    undeclared: list[tuple[str, str, set[str]]] = []
    for mod, files in sorted(imports.items()):
        dist = IMPORT_TO_DIST.get(mod, mod)
        dn = normalize(dist)
        if dn in installed or normalize(mod) in installed:
            if dn not in declared_n and normalize(mod) not in declared_n:
                undeclared.append((mod, dist, files))
            continue
        # 没装：若也没声明，才是真缺失
        if dn not in declared_n:
            undeclared.append((mod, dist, files))

    if args.fix_hint:
        if missing:
            print("pip install " + " ".join(missing))
        return 1 if (missing or undeclared) else 0

    # 可选依赖单列：在 requirements 注释里以「包名 —— 用途」声明，按设计允许缺失。
    # 它们不计入「缺失」，否则每次跑都红一遍，人就会开始无视这个工具。
    optional_missing = [m for m in missing if normalize(m) in optional]
    missing = [m for m in missing if normalize(m) not in optional]
    undeclared_opt = [(m, d, f) for m, d, f in undeclared if normalize(d) in optional]
    undeclared = [(m, d, f) for m, d, f in undeclared if normalize(d) not in optional]

    if args.json:
        print(json.dumps({
            "python": py,
            "requirements": str(req_path),
            "declared": declared,
            "missing": missing,
            "imports_third_party": sorted(imports),
            "undeclared": [{"import": m, "dist": d, "files": sorted(f)[:5]}
                           for m, d, f in undeclared],
        }, ensure_ascii=False, indent=2))
        return 1 if (missing or undeclared) else 0

    print(f"解释器　：{py}")
    print(f"依赖清单：{req_path}（{len(declared)} 条）")
    print(f"实装包数：{len(installed)}")
    print(f"第三方 import：{len(imports)} 个模块")
    if optional_missing or undeclared_opt:
        names = sorted({d for _, d, _ in undeclared_opt} | set(optional_missing))
        print(f"可选依赖未装：{', '.join(names)}（对应能力降级，不阻断）")

    if missing:
        print(f"\n✗ 声明了但没装（{len(missing)}）：")
        for d in missing:
            print(f"    - {d}")
        print(f"  修：pip install {' '.join(missing)}")
    if undeclared:
        print(f"\n✗ 用了但既没声明也没装（{len(undeclared)}）：")
        for mod, dist, files in undeclared[:12]:
            where = next(iter(sorted(files)))
            print(f"    - import {mod}（发行名应为 {dist}）← {where}")
        if len(undeclared) > 12:
            print(f"    …共 {len(undeclared)}")
        print("  说明：可能是 stdlib 新模块、可选依赖内联，或真的漏了声明。")
    if not missing and not undeclared:
        print("\n依赖体检通过：声明、实装、import 三者一致。")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
