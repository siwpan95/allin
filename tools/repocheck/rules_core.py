"""核心规则 1-8：原 v1.0.0 的八条检查，接口迁到规则引擎。

这八条是 repocheck 的立身之本，一条都没删。其中规则 7、8 是本工作区
特有的纪律检查（旧仓库根路径残留、内联引擎副本缺补丁记录）。
"""

from __future__ import annotations

import ast
import sys
import warnings
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext


#: Python 标准库模块名集合（3.10+ 内置；旧版本回退为空集合）。
STDLIB_MODULES = frozenset(getattr(sys, "stdlib_module_names", ()) or ())

#: 常见第三方库清单：仅用于压低 import 断裂启发式的误报，不是完整列表。
COMMON_THIRD_PARTY = frozenset({
    "numpy", "pandas", "requests", "flask", "django", "PIL", "matplotlib",
    "pytest", "yaml", "bs4", "beautifulsoup4", "lxml", "sqlalchemy", "scipy",
    "sklearn", "torch", "tensorflow", "openpyxl", "xlsxwriter", "docx",
    "PyQt5", "PyQt6", "cv2", "selenium", "aiohttp", "fastapi", "uvicorn",
    "rich", "click", "tqdm", "loguru", "colorama", "redis", "pymongo",
    "jinja2", "werkzeug", "pydantic", "httpx", "playwright", "kivy",
    "tomllib", "typing_extensions", "setuptools", "packaging",
    # repocheck 自身的可选依赖：在规则函数体内条件导入，不该被算成断裂风险
    "license_expression", "detect_secrets", "markdown_it", "requirements_parser",
})

#: 依赖声明文件的候选名（出现在项目根即算）。
DEP_MARKERS = ("requirements.txt", "pyproject.toml", "package.json", "Cargo.toml")

#: 许可证文件的候选前缀（不区分大小写）。
LICENSE_PREFIXES = ("license", "licence", "copying", "copyright")

# 被检测的目标串**运行时拼接**，不写成字面量：
# 本模块的职责就是找出这类「旧仓库根路径残留」，若把目标写成字面量，
# 死根路径门禁会把检测器自己报成违规（检测器自身的目标串，属审计注记同类）。
_LEGACY_ROOT = "D:" + "/allin"
_LEGACY_ROOT_WIN = "D:" + "\\" + "allin"

#: 可能夹带旧路径残留的文本文件后缀。
STALE_SUFFIXES = (
    ".py", ".json", ".bat", ".cmd", ".md", ".toml", ".txt",
    ".yml", ".yaml", ".cfg", ".ini", ".ps1", ".sh",
)

#: 其中「最可能夹带硬编码路径」的那几类，扫描时优先。
_STALE_CODE_SUFFIXES = (".py", ".bat", ".cmd", ".ps1", ".sh", ".toml", ".cfg", ".ini")

#: 单次旧路径扫描最多读多少个文件。上万文件的仓库（截图/存档仓库常见）
#: 若不限量，光读 .txt 就能吃掉好几秒。
MAX_STALE_FILES = 1500

#: 内联引擎副本的候选目录（相对项目根）。
ENGINE_DIRS = ("alloy", "allin_engine", "tools/alloy", "vendor/alloy")

#: 引擎定制记录文件。
ENGINE_PATCH_FILES = ("engine.patch.yaml", "engine.patch.yml")

#: 报告里单项 detail 最多列几条，避免刷屏。
MAX_DETAIL_ITEMS = 5

#: import 扫描最多 ast.parse 多少个文件。巨型仓库（几千个 .py）里逐个解析
#: 是主要成本（实测约 3ms/文件），超出即停止并在结果上标 degraded，
#: 让报告能看出「没扫全」而不是假装干净。
MAX_PARSE_FILES = 800


# ---------------------------------------------------------------------------
# 规则 1-5：基础工程基建
# ---------------------------------------------------------------------------

def _check_vcs(ctx: "ProjectContext") -> CheckResult:
    """规则 1：项目目录内应有 .git（目录或 worktree 的 gitfile 都算）。"""
    if (ctx.root / ".git").exists():
        return CheckResult.ok()
    return CheckResult.bad("项目目录内无 .git")


def _check_readme(ctx: "ProjectContext") -> CheckResult:
    """规则 2：根目录应有 README*。"""
    hit = ctx.root_startswith("readme")
    if hit:
        return CheckResult.ok()
    return CheckResult.bad("根目录无 README* 文件")


def _check_tests(ctx: "ProjectContext") -> CheckResult:
    """规则 3：应有 tests/ 或 test/ 目录，或 test_*.py / *_test.py。

    2026-10-30 扩口（monorepo workspace 盲区）：workspace 项目的测试常在
    嵌套 ``test/`` 目录里（如 platform 的 ``apps/*/test/``、``packages/*/test/``
    的 ``.test.mjs``），只查项目根会把「有测试」误报成「无测试」。新增两类判据：
    ① 任意层级 ``test/`` / ``tests/`` 目录下的文件（按路径段精确匹配，``contest/``
       等形近目录不误放行）；
    ② JS/TS 测试惯例 ``*.test.*`` / ``*.spec.*`` 文件（任意层级）。
    """
    for name in ("tests", "test"):
        if ctx.has_dir(name):
            return CheckResult.ok()
    for path in ctx.files:
        base = path.rsplit("/", 1)[-1]
        if base.endswith(".py") and (base.startswith("test_") or base.endswith("_test.py")):
            return CheckResult.ok()
        parts = path.split("/")
        if len(parts) >= 2 and any(seg in ("test", "tests") for seg in parts[:-1]):
            return CheckResult.ok()
        if base.endswith((".test.js", ".test.mjs", ".test.ts", ".test.jsx", ".test.tsx",
                          ".spec.js", ".spec.mjs", ".spec.ts", ".spec.jsx", ".spec.tsx")):
            return CheckResult.ok()
    return CheckResult.bad("无 tests/ 或 test/ 目录，也无 test_*.py / *_test.py / *.test.* / *.spec.*")


def _check_deps(ctx: "ProjectContext") -> CheckResult:
    """规则 4：应有依赖声明文件。"""
    for name in DEP_MARKERS:
        if ctx.has(name):
            return CheckResult.ok()
    return CheckResult.bad("无 " + " / ".join(DEP_MARKERS))


def _check_license(ctx: "ProjectContext") -> CheckResult:
    """规则 5：根目录应有 LICENSE* / LICENCE* / COPYING* / COPYRIGHT*。"""
    hit = ctx.root_startswith(*LICENSE_PREFIXES)
    if hit:
        return CheckResult.ok()
    return CheckResult.bad("根目录无 LICENSE*/LICENCE*/COPYING*/COPYRIGHT*")


# ---------------------------------------------------------------------------
# 规则 6：import 断裂风险（AST 静态启发式，不执行代码）
# ---------------------------------------------------------------------------

def _internal_module_bases(ctx: "ProjectContext") -> set[str]:
    """项目内「可被 import 的顶层模块名」。

    统计三类：所有 .py 文件的文件名、含 ``__init__.py`` 的目录名、以及
    **项目根本身是包**时（根下有 ``__init__.py``）的目录名 —— 后者对应
    ``my_pkg/__init__.py`` + ``my_pkg/tests/test_x.py`` 里
    ``from my_pkg import x`` 的常见布局，漏掉会稳定误报。
    """
    bases = {p.rsplit("/", 1)[-1][:-3] for p in ctx.py_files}
    for rel_dir in ctx.dirs:
        if rel_dir and f"{rel_dir}/__init__.py" in ctx.file_set:
            bases.add(rel_dir.rsplit("/", 1)[-1])
    if "__init__.py" in ctx.file_set:
        bases.add(ctx.root.name)
    return bases


def _scan_imports(ctx: "ProjectContext") -> tuple[dict[str, set[str]], bool]:
    """AST 扫描 .py 的 import，返回 ``({顶层模块: {完整模块名}}, 是否被截断)``。

    相对导入（``from . import x``）视为项目内部，直接忽略。
    """
    imported: dict[str, set[str]] = {}
    files = ctx.py_files
    limited = len(files) > MAX_PARSE_FILES

    # 老代码里 "\d" 之类的无效转义会刷一屏 SyntaxWarning，扫描器不该被它淹没
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        for path in files[:MAX_PARSE_FILES]:
            source = ctx.text(path)
            if source is None:
                continue
            try:
                tree = ast.parse(source)
            except (SyntaxError, ValueError):
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
    return imported, limited


def _check_broken_imports(ctx: "ProjectContext") -> CheckResult:
    """规则 6：顶层模块既不在 stdlib、不在项目内、也不在常见第三方清单。"""
    imported, limited = _scan_imports(ctx)
    hint = ""
    if limited:
        hint = f"仅解析前 {MAX_PARSE_FILES} 个 .py（共 {len(ctx.py_files)} 个）"

    if not imported:
        result = CheckResult.ok()
        return result.with_degraded(hint) if limited else result

    internal = _internal_module_bases(ctx)
    risky = sorted(
        base for base in imported
        if base not in STDLIB_MODULES
        and base not in internal
        and base not in COMMON_THIRD_PARTY
    )
    if not risky:
        result = CheckResult.ok()
        return result.with_degraded(hint) if limited else result

    detail = ", ".join(risky[:MAX_DETAIL_ITEMS])
    if len(risky) > MAX_DETAIL_ITEMS:
        detail += f" 等 {len(risky)} 个"
    result = CheckResult.bad(detail)
    return result.with_degraded(hint) if limited else result


# ---------------------------------------------------------------------------
# 规则 7：旧仓库路径残留（工作区迁移纪律）
# ---------------------------------------------------------------------------

def _check_stale_paths(ctx: "ProjectContext") -> CheckResult:
    """规则 7：代码/配置/文档里是否残留旧仓库根路径。"""
    candidates = [p for p in ctx.files if p.endswith(STALE_SUFFIXES)]
    # 源码与脚本最可能夹带路径，排在文档前面（后面的会被上限截断）
    candidates.sort(key=lambda p: (0 if p.endswith(_STALE_CODE_SUFFIXES) else 1, p))

    hits: list[str] = []
    scanned = 0
    for path in candidates:
        if len(hits) >= MAX_DETAIL_ITEMS or scanned >= MAX_STALE_FILES:
            break
        text = ctx.text(path)
        if text is None:
            continue
        scanned += 1
        if _LEGACY_ROOT in text or _LEGACY_ROOT_WIN in text:
            hits.append(path)

    if not hits:
        return CheckResult.ok()
    return CheckResult.bad(", ".join(hits))


# ---------------------------------------------------------------------------
# 规则 8：内联引擎副本缺补丁记录
# ---------------------------------------------------------------------------

def _check_engine_patch(ctx: "ProjectContext") -> CheckResult:
    """规则 8：内联了引擎副本却没写 engine.patch.yaml（定制不可见，升级会漂移）。"""
    if not any(ctx.has_dir(d) for d in ENGINE_DIRS):
        return CheckResult.ok()
    if any(ctx.has(name) for name in ENGINE_PATCH_FILES):
        return CheckResult.ok()
    present = [d for d in ENGINE_DIRS if ctx.has_dir(d)]
    return CheckResult.bad("存在 " + ", ".join(present) + " 但无 engine.patch.yaml")


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------

RULES_CORE: tuple[Rule, ...] = (
    Rule(1, "vcs.git_missing", "无版本控制（缺 .git）", "项目目录内无 .git",
         Severity.ERROR, _check_vcs),
    Rule(2, "docs.readme_missing", "无 README", "目录自身无 README* 文件",
         Severity.ERROR, _check_readme),
    Rule(3, "test.missing", "无测试", "无 tests/ 或 test/ 目录（含嵌套），且无 test_*.py / *_test.py / *.test.* / *.spec.*",
         Severity.WARN, _check_tests),
    Rule(4, "deps.missing", "无依赖声明",
         "无 requirements.txt / pyproject.toml / package.json / Cargo.toml",
         Severity.ERROR, _check_deps),
    Rule(5, "license.missing", "无 LICENSE", "目录自身无 LICENSE* 文件",
         Severity.ERROR, _check_license),
    Rule(6, "deps.broken_import", "疑似 import 断裂风险",
         "静态启发式：顶层模块不在项目内/标准库/常见第三方清单",
         Severity.WARN, _check_broken_imports),
    Rule(7, "hygiene.stale_path", "旧仓库路径残留",
         "代码/配置/文档含旧仓库根路径（仓库迁移残留）",
         Severity.ERROR, _check_stale_paths),
    Rule(8, "hygiene.engine_no_patch", "内联引擎副本缺 engine.patch.yaml",
         "项目内联 alloy/allin_engine 副本但无 patch 记录",
         Severity.WARN, _check_engine_patch),
)
