"""杂项规则 30：Python 目录命名规范。

只检查**项目内相对路径的父目录链**（会跳过项目根自身与点目录），
否则工作区里 ``my-tool/src/a.py`` 这类合法场景会大面积误报 ——
连字符在**分发名**里合法，在**导入路径**里不合法。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext

#: Python 标识符（可作为包/模块目录名）。
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_DETAIL_ITEMS = 5


def _check_directory_names(ctx: "ProjectContext") -> CheckResult:
    """规则 30：含 .py 的目录名必须是合法 Python 标识符。"""
    offenders: dict[str, list[str]] = {}
    for path in ctx.py_files:
        parts = path.split("/")[:-1]
        for part in parts:
            if part.startswith("."):
                continue  # .github / .venv 之类的点目录不在 PEP 8 范围内
            if not IDENTIFIER_RE.match(part):
                offenders.setdefault(part, []).append(path)

    if not offenders:
        return CheckResult.ok()

    details = [
        f"{name}（如 {paths[0]}）"
        for name, paths in sorted(offenders.items())
    ]
    return CheckResult.bad(
        f"{len(offenders)} 个目录名不是合法标识符：" + ", ".join(details[:MAX_DETAIL_ITEMS]))


RULES_MISC: tuple[Rule, ...] = (
    Rule(30, "layout.bad_dir_name", "目录命名不合规",
         "含 .py 的目录名不是合法 Python 标识符（连字符/空格/中文目录会导致无法 import）",
         Severity.WARN, _check_directory_names),
)
