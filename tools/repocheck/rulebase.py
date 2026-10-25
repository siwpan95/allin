"""repocheck 规则引擎底座。

本模块提供与具体规则无关的骨架：严重度、规则声明、检查结果、统一执行器
与健康分计算。具体规则见 ``rules_*.py``。

设计约束
--------
* 纯标准库；不 import tkinter，``import scanner`` 不会拉起 GUI。
* **规则即数据**：新增一条规则只需在 ``rules_*.py`` 里追加一个 ``Rule(...)``，
  执行、评分、报告渲染、``--dump-profile`` 自省都会自动跟上。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查期使用
    from scanctx import ProjectContext


# ---------------------------------------------------------------------------
# 状态、权重与分数上限
# ---------------------------------------------------------------------------

PASS = "pass"
FAIL = "fail"
SKIP = "skip"
ERROR = "error"

#: 严重度权重：健康分按权重累加（error 最重）。
WEIGHTS = {"error": 3, "warn": 2, "info": 1}

#: 严重度位次，用于 ``--min-severity`` 过滤与排序。
RANK = {"info": 0, "warn": 1, "error": 2}

#: 分数上限。跳过项从分母剔除，但不允许因此拿到满分（否则「越残缺分越高」）。
CAP_FULL = 10.0
CAP_NO_GIT = 6.0   # 无 .git：7 条 git 规则被迫跳过
CAP_PARTIAL = 9.0  # git 不可用 / 父仓嵌套 / 降级判定 / 规则自身异常


class Severity(str, Enum):
    """规则严重度。"""

    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    @property
    def weight(self) -> int:
        """该严重度在健康分里的权重。"""
        return WEIGHTS[self.value]


# ---------------------------------------------------------------------------
# 检查结果
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CheckResult:
    """单条规则的检查结果。

    规则实现只用 ``ok()`` / ``bad()`` / ``skip()`` 三个构造器，
    复杂规则再按需调用 ``with_degraded()`` 标注降级实现。
    """

    status: str
    detail: str = ""
    severity: Severity | None = None
    degraded: bool = False
    hint: str = ""

    @classmethod
    def ok(cls) -> "CheckResult":
        """规则通过。"""
        return cls(PASS)

    @classmethod
    def bad(cls, detail: str = "", severity: Severity | None = None) -> "CheckResult":
        """规则未通过。``severity`` 非空时覆盖规则默认严重度。"""
        return cls(FAIL, detail, severity)

    @classmethod
    def skip(cls, reason: str) -> "CheckResult":
        """该规则对本项目不适用（不计入评分分母）。"""
        return cls(SKIP, hint=reason)

    def with_degraded(self, hint: str) -> "CheckResult":
        """标记本次判定走的是降级实现，返回新对象。"""
        return replace(self, degraded=True, hint=hint)


# ---------------------------------------------------------------------------
# 规则声明
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Rule:
    """一条体检查规则（不可变数据）。

    用 dataclass 而非 NamedTuple 是有意为之：NamedTuple 可被
    ``for label, criteria in RULES`` 静默解包，漏字段也不报错；dataclass
    没有这个隐患，且能声明默认值与 ``field(compare=False)``。
    """

    id: int
    key: str
    label: str
    criteria: str
    severity: Severity
    check: Callable[["ProjectContext"], CheckResult] = field(compare=False, repr=False)
    requires_git: bool = False
    requires: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# 执行结果
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Finding:
    """一条规则的最终判定（含通过项，供 JSON / HTML / agent 使用）。"""

    id: int
    key: str
    label: str
    severity: str
    passed: bool
    status: str
    detail: str = ""
    degraded: bool = False

    def to_dict(self) -> dict:
        """转成可直接 JSON 序列化的字典。"""
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "severity": self.severity,
            "passed": self.passed,
            "status": self.status,
            "detail": self.detail,
            "degraded": self.degraded,
        }


@dataclass(slots=True)
class RunResult:
    """一批规则的执行汇总。"""

    findings: list[Finding] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    degraded_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------

def run_rules(ctx: "ProjectContext", rules: tuple[Rule, ...],
              *, skip_ids: frozenset[int] = frozenset()) -> RunResult:
    """在给定上下文上执行全部规则。

    逐条 ``try/except``：单条规则写崩只记为 ``errors``，不影响其他规则，
    也不进入评分分母。
    """
    result = RunResult()
    git_reason = ctx.git.block_reason() if any(r.requires_git for r in rules) else ""

    for rule in rules:
        if rule.id in skip_ids:
            result.skipped.append({"id": rule.id, "label": rule.label, "reason": "user"})
            continue
        if rule.requires_git and git_reason:
            result.skipped.append({"id": rule.id, "label": rule.label, "reason": git_reason})
            continue
        try:
            res = rule.check(ctx)
        except Exception as exc:  # noqa: BLE001 - 单条规则异常不应毁掉整次扫描
            result.errors.append({
                "id": rule.id,
                "label": rule.label,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        if res.status == SKIP:
            result.skipped.append({
                "id": rule.id, "label": rule.label, "reason": res.hint or "skip",
            })
            continue

        if res.degraded:
            result.degraded_ids.append(rule.id)
        severity = res.severity or rule.severity
        result.findings.append(Finding(
            id=rule.id,
            key=rule.key,
            label=rule.label,
            severity=severity.value,
            passed=res.status == PASS,
            status=res.status,
            detail=res.detail,
            degraded=res.degraded,
        ))
    return result


# ---------------------------------------------------------------------------
# 健康分
# ---------------------------------------------------------------------------

def score(findings: list[Finding], *, cap: float = CAP_FULL) -> tuple[float, float]:
    """按权重累加 + log 平滑，返回 ``(score, pass_rate)``。

    公式 ``10 * log1p(passed_w) / log1p(total_w)`` 取自 best-of 的布尔项累加
    模型并做 0~10 归一化。注意它压缩极强（30 条里挂 20 条仍有 9.4 分），
    所以报告另外并列输出 ``pass_rate``，阈值判断应两者一起看。
    """
    total_w = sum(WEIGHTS[f.severity] for f in findings)
    passed_w = sum(WEIGHTS[f.severity] for f in findings if f.passed)
    if total_w <= 0:
        return 0.0, 0.0
    raw = 10.0 * math.log1p(passed_w) / math.log1p(total_w)
    return round(min(raw, cap), 1), round(passed_w / total_w, 3)


def failing(findings: list[Finding], *, min_severity: str = "info") -> list[Finding]:
    """按最低严重度筛出未通过的条目。"""
    floor = RANK.get(min_severity, 0)
    return [f for f in findings if not f.passed and RANK[f.severity] >= floor]
