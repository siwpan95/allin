"""repocheck —— 仓库体检对外门面。

本模块只暴露稳定 API，规则实现分散在 ``rules_*.py``，渲染在 ``report.py``。
**不 import tkinter**，所以无显示器环境（CI / 命令行）里 ``import scanner``
是安全的，也便于单独做单元测试。

主要对外函数
------------
``discover_projects(root, ...)``
    识别根目录下的一级子目录里哪些是「项目」。
``check_project(path, ...)``
    对单个项目跑全部 30 条规则，返回结构化结果（含健康分）。
``scan(root, ...)``
    发现 + 逐个体检，返回结果列表。
``dump_profile()``
    装配自省：规则清单、可选依赖能力、评分公式（agent 审计入口）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from report import render_text
from rulebase import (
    CAP_FULL,
    CAP_NO_GIT,
    CAP_PARTIAL,
    RANK,
    WEIGHTS,
    Rule,
    run_rules,
    score,
)
from rules_ci import RULES_CI
from rules_core import RULES_CORE
from rules_docs import RULES_DOCS
from rules_misc import RULES_MISC
from rules_vcs import RULES_VCS
from scanctx import ProjectContext

__version__ = "2.0.0"
SCHEMA_VERSION = 2

#: 默认排除的目录名（不扫描、不识别为项目、检查项目时跳过）。
#: 注意：这里排除的是**文件系统索引**；「构建产物是否被 git 跟踪」由规则 21
#: 走 ``git ls-files`` 判定，不依赖本集合，所以不会因为排除而漏检。
DEFAULT_EXCLUDE = frozenset({
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "_cleanup_trash",
    "node_modules",
    "dist",
    "build",
    # 虚拟环境与包安装目录：不排除会让索引和 import 扫描爆炸
    ".venv",
    "venv",
    ".tox",
    ".eggs",
    "site-packages",
    "__pypackages__",
    # 常见构建/缓存/IDE 目录
    "target",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".idea",
    ".vscode",
    ".cache",
})

#: 判定为「项目」的显式标记文件（出现在目录自身即算）。
PROJECT_MARKER_FILES = ("package.json", "Cargo.toml", "pyproject.toml")

#: 全部检查规则。id 必须从 1 连续（``--skip-rules`` 与 agent 按 id 引用）。
#: 各 ``rules_*.py`` 只负责自己的 id 段，这里按 id 排序拼装 —— 执行顺序即 id 顺序。
RULES: tuple[Rule, ...] = tuple(sorted(
    (*RULES_CORE, *RULES_DOCS, *RULES_VCS, *RULES_CI, *RULES_MISC),
    key=lambda r: r.id,
))


def _validate_rules(rules: tuple[Rule, ...]) -> None:
    """规则 id 必须 1..N 连续且无重复，否则装配期直接失败。"""
    ids = [r.id for r in rules]
    if ids != list(range(1, len(rules) + 1)):
        raise RuntimeError(f"规则 id 必须从 1 连续且唯一，实际：{ids}")
    keys = [r.key for r in rules]
    if len(set(keys)) != len(keys):
        raise RuntimeError(f"规则 key 重复：{keys}")


_validate_rules(RULES)


# ---------------------------------------------------------------------------
# 项目发现
# ---------------------------------------------------------------------------

def _merge_exclude(exclude: Iterable[str] | None) -> frozenset[str]:
    """把用户排除项并入默认排除集。"""
    merged = set(DEFAULT_EXCLUDE)
    if exclude:
        merged |= set(exclude)
    return frozenset(merged)


def discover_projects(root: str | os.PathLike, exclude: Iterable[str] | None = None,
                      max_py_depth: int = 2) -> list[str]:
    """识别根目录下的「项目」。

    判定规则：``root`` 的直接一级子目录（排除 ``exclude`` 中的名字）中，
    满足以下任一条件即视为项目：

    * 自身含 ``.git``；
    * 自身含 ``package.json`` / ``Cargo.toml`` / ``pyproject.toml``；
    * 其子树（限定深度 ``max_py_depth``）内存在任意 ``.py`` 文件。

    参数
    ----
    root: 根目录路径。
    exclude: 额外排除的目录名；会与 :data:`DEFAULT_EXCLUDE` 合并。
    max_py_depth: 为寻找 ``.py`` 而向下扫描的最大层级（顶层为 0）。

    返回
    ----
    list[str]: 各项目目录路径字符串，按名称（小写）排序。
    """
    merged = _merge_exclude(exclude)
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    projects: list[str] = []
    try:
        children = sorted(root_path.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []
    for child in children:
        try:
            if not child.is_dir() or child.name in merged:
                continue
        except OSError:
            continue
        if _is_project(child, merged, max_py_depth):
            projects.append(str(child))
    return projects


def _is_project(directory: Path, exclude: frozenset[str], max_py_depth: int) -> bool:
    """判断单个目录是否像一个项目（见 :func:`discover_projects`）。"""
    if (directory / ".git").exists():
        return True
    for marker in PROJECT_MARKER_FILES:
        if (directory / marker).exists():
            return True

    for depth, (_dirpath, dirnames, filenames) in enumerate(os.walk(directory)):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        if depth > max_py_depth:
            # 超过深度限制：既不下钻，也不检查本层文件
            # （旧实现先截断再检查，等于多扫了一层，与文档语义不符）
            dirnames[:] = []
            continue
        if any(f.endswith(".py") for f in filenames):
            return True
    return False


# ---------------------------------------------------------------------------
# 单项目体检
# ---------------------------------------------------------------------------

def check_project(path: str | os.PathLike, exclude: Iterable[str] | None = None,
                  *, skip_ids: Iterable[int] = ()) -> dict:
    """对一个项目跑全部规则，返回结构化结果。

    返回字典结构
    -------------
    ``name`` / ``path``
    ``issues``          仅 error/warn 级未通过项，形如 ``"标签：细节"``
    ``findings``        全部规则判定（含通过项），供 JSON / HTML / agent 使用
    ``score`` / ``pass_rate``
    ``severity_counts`` 未通过项的严重度计数
    ``skipped``         被跳过的规则及原因
    ``rule_errors``     规则自身异常
    ``metrics``         统计指标

    注意：import 断裂风险为静态启发式，只标记那些既不在项目内部、
    也不在标准库、也不在常见第三方清单中的顶层模块，**不执行代码**。
    """
    merged = _merge_exclude(exclude)
    proj = Path(path)
    ctx = ProjectContext(proj, merged)
    run = run_rules(ctx, RULES, skip_ids=frozenset(skip_ids))

    # 跳过项从分母剔除，但必须压上限，否则「越残缺分越高」
    cap = CAP_FULL
    git_reason = ctx.git.block_reason()
    if git_reason == "no-dotgit":
        cap = CAP_NO_GIT
    elif git_reason:
        cap = CAP_PARTIAL
    if run.degraded_ids or run.errors or ctx.truncated:
        cap = min(cap, CAP_PARTIAL)

    value, pass_rate = score(run.findings, cap=cap)

    counts = {"error": 0, "warn": 0, "info": 0}
    issues: list[str] = []
    for finding in sorted(run.findings, key=lambda f: (-RANK[f.severity], f.id)):
        if finding.passed:
            continue
        counts[finding.severity] += 1
        if finding.severity in ("error", "warn"):
            suffix = f"：{finding.detail}" if finding.detail else ""
            issues.append(f"{finding.label}{suffix}")

    has_git = (proj / ".git").exists()
    # Path(".").name 是空串，GUI/报告里会显示成 `==   (.)`，这里兜一下
    name = proj.name or proj.resolve().name or str(proj)
    metrics = {
        "py_files": len(ctx.py_files),
        "total_files": ctx.total_files,
        "findings_count": sum(1 for f in run.findings if not f.passed),
        "issues_count": len(issues),
        "has_git": has_git,
        "git_ok": ctx.git.ok,
        "git_files": len(ctx.git.ls_files),
        "skipped_count": len(run.skipped),
        "degraded": bool(run.degraded_ids),
        "truncated": ctx.truncated,
        "score": value,
        "pass_rate": pass_rate,
    }
    return {
        "name": name,
        "path": str(proj),
        "issues": issues,
        "findings": [f.to_dict() for f in run.findings],
        "score": value,
        "pass_rate": pass_rate,
        "severity_counts": counts,
        "skipped": run.skipped,
        "rule_errors": run.errors,
        "metrics": metrics,
    }


def _safe_check(proj: str, exclude: Iterable[str] | None,
                skip_ids: Iterable[int]) -> dict:
    """单个项目出错不中断整体扫描，转为一条伪问题。"""
    try:
        return check_project(proj, exclude=exclude, skip_ids=skip_ids)
    except Exception as exc:  # noqa: BLE001 - 兜底，避免一个项目毁掉整次扫描
        return {
            "name": os.path.basename(proj),
            "path": proj,
            "issues": [f"检查出错：{exc}"],
            "findings": [],
            "score": 0.0,
            "pass_rate": 0.0,
            "severity_counts": {"error": 1, "warn": 0, "info": 0},
            "skipped": [],
            "rule_errors": [{"id": 0, "label": "check_project", "error": str(exc)}],
            "metrics": {},
        }


def scan(root: str | os.PathLike, *, exclude: Iterable[str] | None = None,
         depth: int = 2, skip_ids: Iterable[int] = (),
         workers: int = 1, progress=None) -> list[dict]:
    """发现项目并逐个体检。

    ``workers > 1`` 时按项目并发（IO 与子进程为主，GIL 影响很小）。
    ``progress`` 为 ``callable(已完成数, 总数, 当前项目路径)``，供 GUI 显示进度。

    若根目录下没发现任何子项目、而根目录本身就像一个项目（有 ``.git`` 或
    marker 文件），则把根目录本身当作单个项目体检 —— 这样 ``cd myrepo`` 之后
    ``repocheck .`` 才符合直觉。
    """
    root_path = Path(root)
    projects = discover_projects(root, exclude=exclude, max_py_depth=depth)
    if not projects and root_path.is_dir() and _is_project(
            root_path, _merge_exclude(exclude), depth):
        projects = [str(root_path)]

    skip = tuple(skip_ids)
    total = len(projects)

    if workers > 1 and len(projects) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_safe_check, p, exclude, skip) for p in projects]
            results: list[dict] = []
            for index, (project, future) in enumerate(zip(projects, futures), 1):
                results.append(future.result())
                if progress:
                    progress(index, total, project)
            return results

    results = []
    for index, project in enumerate(projects, 1):
        results.append(_safe_check(project, exclude, skip))
        if progress:
            progress(index, total, project)
    return results


# ---------------------------------------------------------------------------
# 退出码判定
# ---------------------------------------------------------------------------

FAIL_ON_CHOICES = ("none", "any", "error", "warn", "score:N")


def evaluate_fail_on(results: list[dict], fail_on: str = "none") -> int:
    """按 ``--fail-on`` 语义判定退出码：触发返回 1，否则 0。

    取值
    ----
    ``none``      只要扫描跑完就返回 0（默认，保证向后兼容）
    ``any``       任一规则未通过
    ``error``     任一 error 级未通过
    ``warn``      任一 error 或 warn 级未通过
    ``score:N``   任一项目健康分低于 N
    """
    spec = (fail_on or "none").strip().lower()
    if spec in ("", "none"):
        return 0

    if spec == "any":
        hit = any(not f["passed"] for r in results for f in r.get("findings", []))
    elif spec in ("error", "warn"):
        floor = RANK[spec]
        hit = any(
            not f["passed"] and RANK.get(f["severity"], 0) >= floor
            for r in results for f in r.get("findings", [])
        )
    elif spec.startswith("score:"):
        raw = spec.split(":", 1)[1]
        try:
            threshold = float(raw)
        except ValueError:
            raise ValueError(f"--fail-on 阈值不是数字：{raw!r}") from None
        hit = any(float(r.get("score", CAP_FULL)) < threshold for r in results)
    else:
        raise ValueError(
            f"--fail-on 取值非法：{fail_on!r}（可选 none / any / error / warn / score:N）")
    return 1 if hit else 0


# ---------------------------------------------------------------------------
# 装配自省
# ---------------------------------------------------------------------------

def dump_profile() -> dict:
    """返回自身规则清单与能力矩阵（``--dump-profile`` 的数据来源）。

    ``rules`` 里每条的前三个键固定为 ``id`` / ``label`` / ``criteria``，
    顺序不变 —— 已有 agent 依赖这个约定。
    """
    from _optional import CAPABILITIES

    return {
        "tool": "repocheck",
        "schema": SCHEMA_VERSION,
        "version": __version__,
        "rules": [
            {
                "id": rule.id,
                "label": rule.label,
                "criteria": rule.criteria,
                "key": rule.key,
                "severity": rule.severity.value,
                "requires_git": rule.requires_git,
                "requires": list(rule.requires),
                "status": "active",
            }
            for rule in RULES
        ],
        "exclude_dirs": sorted(DEFAULT_EXCLUDE),
        "project_markers": list(PROJECT_MARKER_FILES),
        "severities": ["error", "warn", "info"],
        "severity_weights": dict(WEIGHTS),
        "score_formula": "10*log1p(passed_w)/log1p(total_w)",
        "caps": {"no_git": CAP_NO_GIT, "partial": CAP_PARTIAL},
        "fail_on": list(FAIL_ON_CHOICES),
        "optional": dict(CAPABILITIES),
    }


# ---------------------------------------------------------------------------
# 可选的命令行入口（非 GUI 场景可用；完整 CLI 见 cli.py）
# ---------------------------------------------------------------------------

def _console_scan(root: str, *, fail_on: str = "none",
                  min_severity: str = "info") -> int:
    """极简命令行扫描：打印文本报告并返回退出码。"""
    results = scan(root)
    print(render_text(results, root=root, min_severity=min_severity))
    return evaluate_fail_on(results, fail_on)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="repocheck 仓库体检（命令行）")
    parser.add_argument("root", nargs="?", default=".", help="根目录，默认当前目录")
    parser.add_argument("--fail-on", default="none",
                        help="none / any / error / warn / score:N")
    parsed = parser.parse_args()
    raise SystemExit(_console_scan(parsed.root, fail_on=parsed.fail_on))
