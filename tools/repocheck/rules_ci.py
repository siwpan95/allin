"""CI 与 workflow 类规则 19/24/25/26/27/28。

YAML 一律走**行级启发式**解析，不引入 PyYAML：这几条规则只需要看
触发条件、``uses:`` 的 ref、``permissions:`` 块和是否存在某个字符串，
用不着完整语法树；保持零运行时依赖比解析严谨性更重要。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext

MAX_DETAIL_ITEMS = 5

#: 除 .github/workflows 之外的 CI 配置位置（文件或目录）。
CI_MARKERS = (
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    ".travis.yml",
    "appveyor.yml",
    ".drone.yml",
    "bitbucket-pipelines.yml",
)
CI_MARKER_DIRS = (".gitee/workflows", ".circleci", ".github/workflows")

#: 依赖自动更新工具的配置文件（含前缀匹配）。
DEP_UPDATE_FILES = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    ".github/renovate.json",
    "renovate.json5",
)
DEP_UPDATE_PREFIXES = (".renovaterc",)

_WORKFLOW_SUFFIXES = (".yml", ".yaml")


def workflow_files(ctx: "ProjectContext") -> list[str]:
    """``.github/workflows`` 下的全部 workflow 文件。"""
    return sorted(
        f".github/workflows/{name}"
        for name in ctx.children(".github/workflows")
        if name.lower().endswith(_WORKFLOW_SUFFIXES)
    )


def _indented_block(text: str, start: int) -> str:
    """取 ``text[start:]`` 之后连续缩进的行（用于解析 ``permissions:`` 块）。"""
    lines = text[start:].splitlines()[1:]
    block: list[str] = []
    for line in lines:
        if not line.strip():
            block.append(line)
            continue
        if line[0] not in (" ", "\t"):
            break
        block.append(line)
    return "\n".join(block)


# ---------------------------------------------------------------------------
# 规则 19：CI 配置存在
# ---------------------------------------------------------------------------

def _check_ci_present(ctx: "ProjectContext") -> CheckResult:
    """规则 19：是否存在任一 CI 配置。"""
    if workflow_files(ctx):
        return CheckResult.ok()
    for marker in CI_MARKERS:
        if ctx.has(marker):
            return CheckResult.ok()
    for marker_dir in CI_MARKER_DIRS:
        if ctx.has_dir(marker_dir):
            return CheckResult.ok()
    return CheckResult.bad("无 CI 配置（.github/workflows / .gitee / .gitlab-ci.yml 等均未找到）")


# ---------------------------------------------------------------------------
# 规则 24：危险 workflow 写法
# ---------------------------------------------------------------------------

_DANGEROUS_TRIGGERS = ("pull_request_target", "workflow_run")

#: pull_request_target + checkout PR 头提交 = 典型的 secret 泄漏面。
_CHECKOUT_PR_REF_RE = re.compile(
    r"ref:\s*\$\{\{\s*github\.event\.pull_request\.(?:head|merge)", re.I)

#: 用户可控输入被直接插值进 run: 脚本（脚本注入）。
_USER_INPUT_INJECTION_RE = re.compile(
    r"\$\{\{\s*github\.(?:head_ref|event\.(?:issue|pull_request|comment|review)"
    r"\.(?:title|body|head\.ref))", re.I)


def _check_dangerous_workflow(ctx: "ProjectContext") -> CheckResult:
    """规则 24：workflow 是否存在脚本注入或 PR 头提交检出的危险写法。"""
    hits: list[str] = []
    for rel in workflow_files(ctx):
        text = ctx.text(rel)
        if not text:
            continue
        low = text.lower()
        if any(t in low for t in _DANGEROUS_TRIGGERS) and _CHECKOUT_PR_REF_RE.search(text):
            hits.append(f"{rel}(检出 PR 头提交)")
            continue
        if _USER_INPUT_INJECTION_RE.search(text):
            hits.append(f"{rel}(用户输入直接插值进脚本)")
        if len(hits) >= MAX_DETAIL_ITEMS:
            break

    if hits:
        return CheckResult.bad("；".join(hits))
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 25：Token 权限过宽
# ---------------------------------------------------------------------------

_PERMISSIONS_TOP_RE = re.compile(r"^permissions\s*:\s*(.*)$", re.M)
_WRITE_SCOPE_RE = re.compile(r"^\s+(?:contents|actions|packages|id-token)\s*:\s*write\b", re.M)
_JOB_PERMISSIONS_RE = re.compile(r"^\s{4,}permissions\s*:", re.M)


def _check_token_permissions(ctx: "ProjectContext") -> CheckResult:
    """规则 25：workflow 的 GITHUB_TOKEN 权限声明是否过宽。"""
    files = workflow_files(ctx)
    if not files:
        return CheckResult.skip("no-workflow")

    warns: list[str] = []
    infos: list[str] = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        match = _PERMISSIONS_TOP_RE.search(text)
        if not match:
            warns.append(f"{rel}(未声明 permissions)")
            continue
        inline = match.group(1).strip()
        if inline in ("write-all", "'write-all'", '"write-all"'):
            warns.append(f"{rel}(permissions: write-all)")
            continue
        block = _indented_block(text, match.end())
        if _WRITE_SCOPE_RE.search(block) and not _JOB_PERMISSIONS_RE.search(text):
            infos.append(f"{rel}(顶层写权限且无 job 级收窄)")

    if warns:
        return CheckResult.bad("；".join(warns[:MAX_DETAIL_ITEMS]), Severity.WARN)
    if infos:
        return CheckResult.bad("；".join(infos[:MAX_DETAIL_ITEMS]), Severity.INFO)
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 26：依赖未固定
# ---------------------------------------------------------------------------

_USES_RE = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([A-Za-z0-9_.-]+)")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")


def _check_pinned_dependencies(ctx: "ProjectContext") -> CheckResult:
    """规则 26：workflow 的 action 是否按 SHA 固定、requirements 是否锁版本。"""
    loose_actions: list[str] = []
    for rel in workflow_files(ctx):
        text = ctx.text(rel)
        if not text:
            continue
        for match in _USES_RE.finditer(text):
            ref = match.group(2)
            if not _SHA40_RE.match(ref):
                loose_actions.append(f"{match.group(1)}@{ref}")

    loose_reqs: list[str] = []
    for rel in ctx.files:
        name = rel.rsplit("/", 1)[-1]
        if "/" in rel or not name.startswith("requirements") or not name.endswith(".txt"):
            continue
        text = ctx.text(rel)
        if text is None:
            continue
        for line in text.splitlines():
            spec = line.split("#", 1)[0].strip()
            if not spec or spec.startswith("-"):
                continue
            if "==" not in spec and "--hash=" not in spec:
                loose_reqs.append(f"{rel}:{spec}")
        if loose_reqs:
            break

    if loose_actions:
        return CheckResult.bad(
            "未按 SHA 固定的 action：" + ", ".join(sorted(set(loose_actions))[:MAX_DETAIL_ITEMS]),
            Severity.WARN)
    if loose_reqs:
        return CheckResult.bad(
            "未锁定版本的依赖：" + ", ".join(loose_reqs[:MAX_DETAIL_ITEMS]), Severity.INFO)
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 27：依赖更新工具
# ---------------------------------------------------------------------------

def _check_dependabot(ctx: "ProjectContext") -> CheckResult:
    """规则 27：是否配置了 Dependabot / Renovate。"""
    for rel in DEP_UPDATE_FILES:
        if ctx.has(rel):
            return CheckResult.ok()
    for name in ctx.children(""):
        if name.lower().startswith(DEP_UPDATE_PREFIXES):
            return CheckResult.ok()
    return CheckResult.bad("无 dependabot / renovate 配置")


# ---------------------------------------------------------------------------
# 规则 28：SAST 配置
# ---------------------------------------------------------------------------

_SAST_FILES = (".semgrep.yml", ".semgrepignore", "sonar-project.properties")
_SAST_HOOK_RE = re.compile(r"semgrep|bandit|ruff|gosec|eslint|gitleaks", re.I)


def _check_sast(ctx: "ProjectContext") -> CheckResult:
    """规则 28：是否配置了静态分析（CodeQL / Semgrep / Sonar / pre-commit 钩子）。"""
    for rel in workflow_files(ctx):
        text = ctx.text(rel)
        if text and "github/codeql-action" in text:
            return CheckResult.ok()
    for rel in _SAST_FILES:
        if ctx.has(rel):
            return CheckResult.ok()

    pre_commit = ".pre-commit-config.yaml"
    if ctx.has(pre_commit):
        text = ctx.text(pre_commit)
        if text is None or _SAST_HOOK_RE.search(text):
            return CheckResult.ok()
    return CheckResult.bad("无 SAST 配置（CodeQL / Semgrep / Sonar / pre-commit 钩子）")


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------

RULES_CI: tuple[Rule, ...] = (
    Rule(19, "ci.missing", "无 CI 配置",
         "无 .github/workflows/*.yml、.gitee/workflows、.gitlab-ci.yml、Jenkinsfile 等",
         Severity.WARN, _check_ci_present),
    Rule(24, "ci.dangerous_workflow", "危险 workflow 写法",
         "pull_request_target/workflow_run 配合检出 PR 头提交，或用户可控输入直接插值进 run:",
         Severity.ERROR, _check_dangerous_workflow),
    Rule(25, "ci.token_permissions", "Token 权限过宽",
         "workflow 未声明 permissions、声明 write-all，或顶层写权限且无 job 级收窄",
         Severity.WARN, _check_token_permissions),
    Rule(26, "ci.unpinned_dependency", "依赖未固定",
         "workflow 的 uses:@ref 非 40 位 commit SHA；requirements*.txt 未用 == 或 --hash 锁定",
         Severity.WARN, _check_pinned_dependencies),
    Rule(27, "ci.no_dep_update", "无依赖更新工具",
         "无 .github/dependabot.yml 或 renovate 配置",
         Severity.INFO, _check_dependabot),
    Rule(28, "ci.no_sast", "无 SAST 配置",
         "无 CodeQL workflow、Semgrep/Sonar 配置，或 pre-commit 里没有静态分析钩子",
         Severity.INFO, _check_sast),
)
