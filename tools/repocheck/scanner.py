"""repocheck —— 仓库体检核心逻辑（纯标准库，无第三方依赖）。

本模块只负责“纯逻辑”，不依赖任何 GUI / 外部共享代码，便于在
无显示器的 CI / 命令行环境中直接 `import scanner` 做单元测试。

主要对外函数：
    discover_projects(root, exclude=None) -> list[str]
    check_project(path, exclude=None)     -> dict
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 默认排除的目录名（不扫描、不识别为项目、检查项目时跳过）。
DEFAULT_EXCLUDE = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    "_cleanup_trash",
    "node_modules",
    "dist",
    "build",
}

#: 判定为“项目”的显式标记文件（出现在目录自身即算）。
PROJECT_MARKER_FILES = ("package.json", "Cargo.toml", "pyproject.toml")

#: 常见第三方库清单（仅用于降低 import 断裂启发式的误报，非完整列表）。
COMMON_THIRD_PARTY = {
    "numpy", "pandas", "requests", "flask", "django", "PIL", "matplotlib",
    "pytest", "yaml", "bs4", "beautifulsoup4", "lxml", "sqlalchemy", "scipy",
    "sklearn", "torch", "tensorflow", "openpyxl", "xlsxwriter", "docx",
    "PyQt5", "PyQt6", "cv2", "selenium", "aiohttp", "fastapi", "uvicorn",
    "rich", "click", "tqdm", "loguru", "colorama", "redis", "pymongo",
    "jinja2", "werkzeug", "pydantic", "httpx", "playwright", "kivy",
}

#: Python 标准库模块名集合（3.10+ 内置；旧版本回退为空集合）。
STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", []) or [])

#: 全部检查规则（规则即数据）：label + 判定口径。--dump-profile 的自描述来源。
RULES = [
    ("无版本控制（缺 .git）", "项目目录内无 .git"),
    ("无 README", "目录自身无 README* 文件"),
    ("无测试", "无 tests/ 或 test/ 目录，且无 test_*.py / *_test.py"),
    ("无依赖声明", "无 requirements.txt / pyproject.toml / package.json / Cargo.toml"),
    ("无 LICENSE", "目录自身无 LICENSE* 文件"),
    ("疑似 import 断裂风险", "静态启发式：顶层模块不在项目内/标准库/常见第三方清单"),
    ("旧仓库路径残留(D:/allin)", "代码/配置/文档含 D:/allin 或 D:\\allin（仓库迁移残留）"),
    ("内联引擎副本缺 engine.patch.yaml", "项目内联 alloy/allin_engine 副本但无 patch 记录"),
]


def dump_profile() -> dict:
    """装配自省：返回自身规则清单（agent 审计入口，--dump-profile）。"""
    return {
        "tool": "repocheck",
        "rules": [
            {"id": i + 1, "label": label, "criteria": criteria}
            for i, (label, criteria) in enumerate(RULES)
        ],
        "exclude_dirs": sorted(DEFAULT_EXCLUDE),
        "project_markers": list(PROJECT_MARKER_FILES),
    }


# ---------------------------------------------------------------------------
# 项目发现
# ---------------------------------------------------------------------------

def discover_projects(root: str | os.PathLike, exclude: set[str] | None = None,
                      max_py_depth: int = 2) -> list[str]:
    """递归识别根目录下的“项目”。

    判定规则：``root`` 的直接一级子目录（排除 ``exclude`` 中的名字）中，
    满足以下任一条件即视为项目：
        * 自身含 ``.git`` 目录；
        * 自身含 ``package.json`` / ``Cargo.toml`` / ``pyproject.toml``；
        * 其子树（限定深度 ``max_py_depth``）内存在任意 ``.py`` 文件。

    参数
    ----
    root: 根目录路径。
    exclude: 额外排除的目录名；会与 :data:`DEFAULT_EXCLUDE` 合并。
    max_py_depth: 为寻找 ``.py`` 而在项目目录内向下扫描的最大层级
        （顶层为 0）。用于避免在巨型仓库上过度遍历。

    返回
    ----
    list[str]: 各项目目录的绝对/原始路径字符串，按名称排序。
    """
    exclude = _merge_exclude(exclude)
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    projects: list[str] = []
    for child in sorted(root_path.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name in exclude:
            continue
        if _is_project(child, exclude, max_py_depth):
            projects.append(str(child))
    return projects


def _is_project(directory: Path, exclude: set[str], max_py_depth: int) -> bool:
    """判断单个目录是否像一个项目（见 :func:`discover_projects`）。"""
    # 显式标记
    if (directory / ".git").exists():
        return True
    for marker in PROJECT_MARKER_FILES:
        if (directory / marker).exists():
            return True
    # 子树内是否存在 .py 文件（限定深度）
    for depth, (dirpath, dirnames, filenames) in enumerate(os.walk(directory)):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        if depth > max_py_depth:
            dirnames[:] = []  # 不再下钻
        if any(f.endswith(".py") for f in filenames):
            return True
    return False


# ---------------------------------------------------------------------------
# 单项目体检
# ---------------------------------------------------------------------------

def check_project(path: str | os.PathLike, exclude: set[str] | None = None) -> dict:
    """对一个项目目录做体检，返回结构化结果。

    返回字典结构
    -------------
    {
        "name":    <项目目录名>,
        "path":    <项目目录路径>,
        "issues":  [<问题标签字符串>, ...],   # 为空表示无明显问题
        "metrics": {                          # 一些统计指标
            "py_files":   <int>,
            "total_files":<int>,
            "issues_count": <int>,
            "has_git":    <bool>,
        },
    }

    检查项（标签文案）
    ----------------
        * 无版本控制（缺 .git）
        * 无 README
        * 无测试
        * 无依赖声明
        * 无 LICENSE
        * 疑似 import 断裂风险：<模块1, 模块2, ...>
        * 旧仓库路径残留(D:/allin)：<文件1, ...>
        * 内联引擎副本缺 engine.patch.yaml（定制不可见）

    注意：import 断裂风险为“静态启发式”，只标记那些既不在项目内部、
    也不在 Python 标准库、也不在常见第三方清单中的顶层模块，不实际执行代码。
    """
    exclude = _merge_exclude(exclude)
    proj = Path(path)
    name = proj.name
    issues: list[str] = []

    py_files = _collect_py_files(proj, exclude)

    # 1) 版本控制
    if not (proj / ".git").exists():
        issues.append("无版本控制（缺 .git）")

    # 2) README
    if not _has_readme(proj):
        issues.append("无 README")

    # 3) 测试
    if not _has_tests(proj, exclude):
        issues.append("无测试")

    # 4) 依赖声明
    if not _has_deps(proj):
        issues.append("无依赖声明")

    # 5) LICENSE
    if not _has_license(proj):
        issues.append("无 LICENSE")

    # 6) import 断裂风险（静态启发式）
    broken = _find_broken_imports(proj, py_files, exclude)
    if broken:
        issues.append("疑似 import 断裂风险：" + ", ".join(broken))

    # 7) 旧仓库路径残留（D:/allin → G:\ 迁移，规则即数据）
    stale = _stale_repo_path_hits(proj, exclude)
    if stale:
        issues.append("旧仓库路径残留(D:/allin)：" + ", ".join(stale))

    # 8) 内联引擎副本缺 patch 记录（补丁即差异纪律）
    if _inline_engine_without_patch(proj):
        issues.append("内联引擎副本缺 engine.patch.yaml（定制不可见）")

    metrics = {
        "py_files": len(py_files),
        "total_files": _count_files(proj, exclude),
        "issues_count": len(issues),
        "has_git": (proj / ".git").exists(),
    }
    return {
        "name": name,
        "path": str(proj),
        "issues": issues,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# 项目内文件收集与判定辅助
# ---------------------------------------------------------------------------

def _collect_py_files(directory: Path, exclude: set[str]) -> list[str]:
    """收集项目内所有 ``.py`` 文件（跳过排除目录）。"""
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            if f.endswith(".py"):
                result.append(os.path.join(dirpath, f))
    return result


def _count_files(directory: Path, exclude: set[str]) -> int:
    """统计项目内文件总数（跳过排除目录，含子目录中的文件）。"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        total += len(filenames)
    return total


def _has_readme(directory: Path) -> bool:
    """目录自身是否存在 README*/readme* 文件（不进入子目录）。"""
    for f in directory.iterdir():
        if f.is_file() and f.name.lower().startswith("readme"):
            return True
    return False


def _has_tests(directory: Path, exclude: set[str]) -> bool:
    """是否存在测试：``tests/`` 或 ``test/`` 目录，或 ``test_*.py`` / ``*_test.py``。"""
    for child in directory.iterdir():
        if child.is_dir() and child.name in ("tests", "test") and child.name not in exclude:
            return True
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            if (f.startswith("test_") and f.endswith(".py")) or f.endswith("_test.py"):
                return True
    return False


def _has_deps(directory: Path) -> bool:
    """目录自身是否存在依赖声明文件。"""
    for marker in ("requirements.txt", "pyproject.toml", "package.json", "Cargo.toml"):
        if (directory / marker).exists():
            return True
    return False


def _has_license(directory: Path) -> bool:
    """目录自身是否存在 LICENSE* 文件（不进入子目录）。"""
    for f in directory.iterdir():
        if f.is_file() and f.name.upper().startswith("LICENSE"):
            return True
    return False


# ---------------------------------------------------------------------------
# 仓库纪律规则（2026-08-23 会话教训固化为规则：规则即数据）
# ---------------------------------------------------------------------------

def _stale_repo_path_hits(directory: Path, exclude: set[str]) -> list[str]:
    """扫描代码/配置/文档中的旧仓库路径残留（D:/allin → G:\ 迁移）。

    命中文件限 5 个（报告不刷屏）。只读文本文件，不执行代码。
    """
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            if not f.endswith((".py", ".json", ".bat", ".md", ".toml", ".txt")):
                continue
            p = Path(dirpath) / f
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "D:/allin" in text or "D:\\allin" in text:
                hits.append(str(p.relative_to(directory)))
                if len(hits) >= 5:
                    break
        if len(hits) >= 5:
            break
    return hits


def _inline_engine_without_patch(directory: Path) -> bool:
    """项目内联引擎副本（alloy/ 或 allin_engine/，含 tools/vendor 子位）但无 patch 记录。

    补丁即差异纪律：内联引擎的项目定制应显式记录在 engine.patch.yaml，
    否则升级时定制不可见、漂移不可审计。
    """
    engine_dirs = (
        directory / "alloy",
        directory / "allin_engine",
        directory / "tools" / "alloy",
        directory / "vendor" / "alloy",
    )
    if not any(d.is_dir() for d in engine_dirs):
        return False
    return not ((directory / "engine.patch.yaml").exists()
                or (directory / "engine.patch.yml").exists())


# ---------------------------------------------------------------------------
# import 断裂风险（静态启发式）
# ---------------------------------------------------------------------------

def _internal_module_bases(directory: Path, exclude: set[str]) -> set[str]:
    """收集项目内“可被 import 的顶层模块名”。

    包括：所有 ``.py`` 文件的文件名（去后缀），以及含 ``__init__.py``
    的包目录名。用于判断某个 import 是否指向项目内部模块。
    """
    bases: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for f in filenames:
            if f.endswith(".py"):
                bases.add(f[:-3])
        for d in list(dirnames):
            if (Path(dirpath) / d / "__init__.py").exists():
                bases.add(d)
    return bases


def _scan_imports(py_files: list[str]) -> dict[str, set[str]]:
    """用 ``ast`` 静态扫描所有 ``.py`` 的 import，返回 ``{顶层模块: {完整模块名}}``。

    相对导入（``from . import x``）视为项目内部，直接忽略，不计入风险。
    文件无法读取或存在语法错误时安全跳过。
    """
    imported: dict[str, set[str]] = {}
    for pf in py_files:
        try:
            source = Path(pf).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    imported.setdefault(base, set()).add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # 相对导入 -> 项目内部
                if node.module:
                    base = node.module.split(".")[0]
                    imported.setdefault(base, set()).add(node.module)
    return imported


def _find_broken_imports(directory: Path, py_files: list[str],
                         exclude: set[str]) -> list[str]:
    """返回“疑似断裂”的顶层模块名列表。

    规则：在 import 的顶层模块中，剔除标准库、剔除项目内部模块、
    剔除常见第三方清单后，剩余的即视为“疑似 import 断裂风险”。
    这是启发式，会存在误报（少见但未收录的合法第三方库）。
    """
    imported = _scan_imports(py_files)
    internal = _internal_module_bases(directory, exclude)
    risky: list[str] = []
    for base in imported:
        if base in STDLIB_MODULES:
            continue
        if base in internal:
            continue
        if base in COMMON_THIRD_PARTY:
            continue
        risky.append(base)
    return sorted(risky)


# ---------------------------------------------------------------------------
# 公共小工具
# ---------------------------------------------------------------------------

def _merge_exclude(exclude: set[str] | None) -> set[str]:
    """将用户排除项与默认排除集合并，返回新集合。"""
    merged = set(DEFAULT_EXCLUDE)
    if exclude:
        merged |= set(exclude)
    return merged


# ---------------------------------------------------------------------------
# 可选的命令行入口（非 GUI 场景可用）
# ---------------------------------------------------------------------------

def _console_scan(root: str) -> None:
    """极简命令行扫描，方便无 GUI 时快速查看结果。"""
    projects = discover_projects(root)
    print(f"根目录：{root}")
    print(f"发现项目数：{len(projects)}\n")
    for proj in projects:
        r = check_project(proj)
        print(f"== {r['name']}  ({r['path']})")
        if r["issues"]:
            for issue in r["issues"]:
                print(f"   - {issue}")
        else:
            print("   ✓ 无明显问题")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="repocheck 仓库体检（命令行）")
    parser.add_argument("root", nargs="?", default="G:\\", help="根目录，默认 G:\\")
    args = parser.parse_args()
    _console_scan(args.root)
