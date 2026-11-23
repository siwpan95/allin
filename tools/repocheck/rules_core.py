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
    # LibreOffice 宿主自带的 UNO 桥（import uno / com.sun.star.*），随
    # LibreOffice 的 python 分发、不经项目 pip 声明；补 pip 名会引入假依赖。
    "uno",
    # repocheck 自身的可选依赖：在规则函数体内条件导入，不该被算成断裂风险
    "license_expression", "detect_secrets", "markdown_it", "requirements_parser",
})

#: distribution name → 真实 import 名的**精确**映射（2026-11-15 实战校验）。
#: 只在项目自己声明了该 distribution 时展开，绝不并入 COMMON_THIRD_PARTY：
#: 全局白名单会让「装了别的包却 import fitz」这种真缺口也判绿。
#: key 用 PEP 503 规范化形式（-_. 视作 _ 且小写），value 保留 import 名的大小写。
DIST_IMPORT_ALIASES: dict[str, frozenset[str]] = {
    "pygame_ce": frozenset({"pygame"}),
    "pymupdf": frozenset({"fitz"}),
    "pycryptodome": frozenset({"Crypto", "Cryptodome"}),
    "pywin32": frozenset({"win32com", "pythoncom", "win32api", "win32con", "com"}),
    "audioop_lts": frozenset({"audioop"}),
    "readability_lxml": frozenset({"readability"}),
    "pyopengl": frozenset({"OpenGL"}),
    "pyzmq": frozenset({"zmq"}),
    "pillow": frozenset({"PIL"}),
    "pyyaml": frozenset({"yaml"}),
    "opencv_python": frozenset({"cv2"}),
    "beautifulsoup4": frozenset({"bs4"}),
    "scikit_learn": frozenset({"sklearn"}),
    "cx_freeze": frozenset({"cx_Freeze"}),
    "fonttools": frozenset({"fontTools"}),
    # 2026-11-15 实战校验补充：distribution 名与 import 名不一致的正式发行包。
    # 3dworld（包名不能以数字开头）、allin-engine（旧名 alloy）、
    # audioop-lts（py3.13 标准库回移）、moviepy 等，仓里已正确声明发行名。
    "3dworld": frozenset({"world3d"}),
    "allin_engine": frozenset({"allin_engine", "alloy"}),
    "audioop_lts": frozenset({"audioop_lts", "audioop"}),
    "moviepy": frozenset({"moviepy"}),
    "dse_core": frozenset({"dse_core"}),
    "bloodmusic": frozenset({"bloodmusic"}),
    "python_vlc": frozenset({"vlc"}),          # python-vlc → import vlc
    "pyinstaller": frozenset({"PyInstaller"}), # 声明小写，import 保留大小写
    "pyexecjs": frozenset({"execjs"}),         # PyExecJS → import execjs
}

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

#: 历史留档 —— 整份文件记录的是「当时发生了什么」，里面的旧路径是**史实**而非
#: 待执行指令，改它等于篡改历史。与 ``tools/publish_area_stale_paths.py`` 的
#: ``is_historical_file`` 同源，避免出现「清洗工具不改、门禁一直红」的僵局。
#: 实测（2026-11-21 发布区全量）：an-engine 的 CHANGELOG 里「去掉内部路径 <旧仓根>」
#: 是变更条目、adventurelog 的运行日志、kard 的集成报告与 pq-multiverse 的
#: 项目总结是交付留档 —— 六条红线全部落在这类文件上，而它们一个字都不该动。
_HISTORICAL_NAME_PARTS = ("changelog", "change-log", "history", "news",
                          "report", "总结", "指导", "迁移")
_HISTORICAL_PATH_PARTS = (
    "audit/", "/audit", "记录/", "/records/", "/adr/", "adr-",
    # 2026-11-23 扩口：历史归档区与他机事实源。
    #   前者是整仓的历史快照（allin 的 `docs/md/` 就是 ASCII 别名「历史/」），
    #   里面的旧仓根（盘符 + allin）是"这份文档当年从哪来"的出处标注；
    #   后者描述的是**别的机器**的落点（`docs/facts/机器/<HOST>/`），在本机不成立
    #   也不该被判死 —— 与 g20「每台机只自验自己那份」同口径。
    #   两者都不是"照着做会失败"的可执行路径，判红只会逼人篡改历史。
    #   注意 `docs/facts` 是 junction（不入库），git 侧真身是 `docs/事实源`，两种形态都认。
    "docs/md/", "/历史/", "docs/history/",
    "docs/facts/机器/", "docs/事实源/机器/",
)
_HISTORICAL_SUFFIXES = (".log",)
_HISTORICAL_NAME_EXACT = ("log.txt", "log.md")


def _is_historical_archive(path: str) -> bool:
    """该文件是否属于历史留档（整份不判旧路径残留）。"""
    low = path.replace("\\", "/").lower()
    name = low.rsplit("/", 1)[-1]
    if name.endswith(_HISTORICAL_SUFFIXES) or name in _HISTORICAL_NAME_EXACT:
        return True
    if any(part in name for part in _HISTORICAL_NAME_PARTS):
        return True
    return any(part in low for part in _HISTORICAL_PATH_PARTS)

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

    统计四类：所有 .py 文件的文件名、含 ``__init__.py`` 的目录名、
    **项目根本身是包**时（根下有 ``__init__.py``）的目录名 —— 后者对应
    ``my_pkg/__init__.py`` + ``my_pkg/tests/test_x.py`` 里
    ``from my_pkg import x`` 的常见布局；以及 PEP 420 namespace package
    —— 一级目录含 .py 但无 ``__init__.py`` 时 Python 3 仍可 import 它。

    namespace 那类是 2026-11-15 实战校验发现的误报源：多个仓的
    ``core/`` / ``engines/`` / ``rendering/`` 内部目录没有 ``__init__.py``，
    被稳定误报成 import 断裂。只认一级目录，避免把子目录名误当顶层包。
    """
    bases = {p.rsplit("/", 1)[-1][:-3] for p in ctx.py_files}
    for rel_dir in ctx.dirs:
        if rel_dir and f"{rel_dir}/__init__.py" in ctx.file_set:
            bases.add(rel_dir.rsplit("/", 1)[-1])
    if "__init__.py" in ctx.file_set:
        bases.add(ctx.root.name)
    for rel_dir in ctx.dirs:
        if not rel_dir or "/" in rel_dir:
            continue
        if any(p.startswith(f"{rel_dir}/") and p.endswith(".py") for p in ctx.py_files):
            bases.add(rel_dir)
    # src-layout / lib-layout：src/<pkg>/ 下的 <pkg> 是合法顶层 import 名。
    # 只认确实含 .py 的包目录，不做全局通用名（core/ui）放行。
    for rel_dir in ctx.dirs:
        parts = rel_dir.split("/")
        if len(parts) >= 2 and parts[0] in ("src", "lib") and parts[1]:
            if any(p.startswith(f"{rel_dir}/") and p.endswith(".py") for p in ctx.py_files):
                bases.add(parts[1])
    return bases


def _declared_dependency_bases(ctx: "ProjectContext") -> set[str]:
    """项目自己声明的第三方依赖，规范化成可能的 import 顶层名。

    规则 6 原本只认一张全局白名单 ``COMMON_THIRD_PARTY``，于是任何
    「白名单外、但已在 pyproject.toml / requirements*.txt 里声明」的包
    都会被误报成 import 断裂。白名单是全局知识，不该为单个项目增补；
    正确的事实源是项目自己的依赖声明（2026-11-15 实战校验发现）。

    PEP 503 规范化：``-`` / ``_`` / ``.`` 视作同一分隔符并转小写，
    故 ``dse-core`` → ``dse_core``。distribution name 与 import name
    不一致的少数情况（如 PyYAML → yaml）仍由全局白名单兜底。

    除标准依赖声明外，还识别 ``# r6-local: name1, name2`` 注释，用于
    声明运行时经 sys.path 注入、仓内无静态包目录的本地模块（聚合仓子项目、
    兄弟仓源码注入）。这是逐仓显式声明的真实依赖事实，不是全局放行。
    """
    import re

    def normalize(spec: str) -> str:
        spec = spec.split(";", 1)[0]             # 丢掉环境标记
        spec = re.sub(r"\[[^\]]*\]", "", spec)   # 丢掉 extras
        spec = re.split(r"[<>=!~ \t(@]", spec, maxsplit=1)[0].strip()
        return re.sub(r"[-_.]+", "_", spec).lower() if spec else ""

    specs: list[str] = []
    # 本地模块声明：运行时经 sys.path 注入、仓内无静态包目录的模块名
    # （聚合仓子项目、兄弟仓源码注入等）。语法：
    #   # r6-local: core, save, shared
    # 这不是全局白名单——只在该仓 requirements 里显式声明时才放行，
    # 且声明的是「本仓确实 import 并靠注入解析」的真实依赖关系，可审计。
    for rel in ctx.files:
        if "/" in rel or not rel.lower().startswith("requirements") or not rel.lower().endswith(".txt"):
            continue
        for line in (ctx.text(rel) or "").splitlines():
            if "#" not in line:
                continue
            comment = line.split("#", 1)[1].strip()
            if comment.lower().startswith("r6-local:"):
                for tok in comment.split(":", 1)[1].split(","):
                    tok = tok.strip()
                    if tok and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok):
                        specs.append(tok)
    text = ctx.text("pyproject.toml")
    if text:
        try:
            import tomllib
            data = tomllib.loads(text)
        except Exception:  # noqa: BLE001 - 清单不可读时不猜，交给白名单
            data = {}
        project = data.get("project") or {}
        deps = list(project.get("dependencies") or [])
        for group in (project.get("optional-dependencies") or {}).values():
            deps.extend(group or [])
        poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        if isinstance(poetry, dict):
            deps.extend(poetry.keys())
        specs.extend(str(d) for d in deps)

    for rel in ctx.files:
        if "/" in rel:
            continue
        low = rel.lower()
        if not (low.startswith("requirements") and low.endswith(".txt")):
            continue
        body = ctx.text(rel)
        if body:
            for line in body.splitlines():
                spec = line.split("#", 1)[0].strip()
                if not spec:
                    continue
                if spec.startswith("-e ") or spec.startswith("--editable "):
                    # 本地可编辑安装（工作区兄弟仓）：-e ../world3d → world3d。
                    # 这是合法的依赖声明事实源，不是白名单；未声明的本地仓仍报红。
                    target = spec.split(None, 1)[1].strip().rstrip("/\\")
                    leaf = target.replace("\\", "/").rsplit("/", 1)[-1]
                    if leaf and leaf not in (".", ".."):
                        specs.append(leaf)
                    continue
                if spec.startswith("-"):
                    continue
                specs.append(spec)

    declared = {n for n in (normalize(s) for s in specs) if n}
    # PEP 503 规范化名与 import 名不一致的包，只在本项目确实声明了该
    # distribution 时才展开对应 import 名（如 pygame-ce → pygame、
    # PyMuPDF → fitz）。未声明的包不会因这张表被放行。
    for dist in tuple(declared):
        declared.update(DIST_IMPORT_ALIASES.get(dist, ()))
    return declared


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
    declared = _declared_dependency_bases(ctx)
    risky = sorted(
        base for base in imported
        if base not in STDLIB_MODULES
        and base not in internal
        and base not in COMMON_THIRD_PARTY
        and base not in declared
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
    """规则 7：代码/配置/文档里是否残留旧仓库根路径。

    2026-11-21 修订：原实现只要**字面出现旧仓根**就报红，连下面这类
    **正确的治理留痕**也报：

        # 原 <旧仓根> 已失效；现由环境变量 FAU_JSONL 指定
        > （如「从 `<旧仓根>` 下多项目提炼」）—— 那是上游文本

    这些是在**记录**去符盘这件事、警告后来者别照抄，抹掉反而丢治理痕迹。
    新版按行判定：只有「看起来是可执行的死路径」才算残留；
    说明性语境（含「已失效/原/历史/上游文本/去符盘」等标记）跳过。

    与 ``tools/publish_area_stale_paths.py`` 的口径同源（同一套语境标记），
    避免「清洗工具说已清干净、门禁还在报」。
    """
    candidates = [p for p in ctx.files
                  if p.endswith(STALE_SUFFIXES) and not _is_historical_archive(p)]
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
        if _has_actionable_stale_path(text):
            hits.append(path)

    if not hits:
        return CheckResult.ok()
    return CheckResult.bad(", ".join(hits))


#: 说明性语境标记 —— 命中即视为「治理留痕」而非「可执行死路径」。
#: 与 tools/publish_area_stale_paths.py 同源。
_STALE_EXPLANATION_MARKERS = (
    "已失效", "失效", "不再是", "上游文本", "不要这样", "禁止", "反面教材",
    "原 ", "旧 ", "历史", "曾", "已迁移", "已改为", "改由", "去符盘", "本地化",
    "个项目中提炼", "项目中提炼", "下 100", "中提炼",
    # 本工具刚写入的去符盘记账注释（含旧路径字面量，但已处理过）
    "原 `cd <旧仓根> &&", "原路径指向旧仓根", "已改为仓内相对路径",
)
_STALE_COMMENT_PREFIXES = ("#", "//", "*", ">", "|", ";")


def _has_actionable_stale_path(text: str) -> bool:
    """文本里是否有「照着做会失败」的旧路径（而非说明性留痕）。"""
    for line in text.splitlines():
        if _LEGACY_ROOT not in line and _LEGACY_ROOT_WIN not in line:
            continue
        stripped = line.strip()
        low = stripped.lower()
        if any(marker in low for marker in _STALE_EXPLANATION_MARKERS):
            continue
        if stripped.startswith(_STALE_COMMENT_PREFIXES):
            continue
        return True
    return False


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
