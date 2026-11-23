#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则 51-53 —— 测试探针族（`--tests` 启用）。

为什么单开一族而不并进现有 30 条
--------------------------------
现有规则都是**静态**的：看目录、看文件、看声明。而「这个项目的测试到底能不能跑」
必须**执行**才能知道 —— 它慢（要拉起解释器）、可能写临时文件、且很多项目本来就没测试
（那不是缺陷）。所以默认关闭，`--tests` 显式开启；三档结论：
无测试=skip（不计入分母）/ 有测试但收集失败=FAIL / 收集成功=PASS。

为什么用 py_test_runner 的探针内核，而不是自己写 for 循环
----------------------------------------------------------
这层抽象它已经做完了（Probe 可注册、可按分类/标签筛选、批量跑并统一异常形态）。
内核已内联在 `tools/_shared/pytrunner/`（全哥指令「跨仓依赖改内联」——
门禁最不该引入「对方版本变了判据就变」的隐形变量）。

**刻意不用 ProbeManager**：它需要 LogManager，而 LogManager 的 __init__ 会
`mkdir(logs)` —— 体检器不该在别人仓里建目录。所以只取 `Probe` 这个抽象，
`check()` 直接调用，副作用为零。

规则一览
--------
| id | key | 判据 | severity |
|---|---|---|---|
| 51 | tests.exists | 项目内有测试文件或 tests/ 目录 | INFO（没有则 skip） |
| 52 | tests.collectable | 有测试文件时，`pytest --collect-only` 必须能收到用例 | ERROR |
| 53 | tests.runner-known | 有 pytest 配置或 Makefile 的 test 目标 | INFO（没有则 skip） |
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:
    from scanctx import ProjectContext

#: 探针内核在 tools/_shared 下；repocheck 的模块以**顶层模块**方式加载，
#: 所以必须把 tools/ 加进 sys.path 才能 `from _shared.pytrunner import ...`。
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from _shared.pytrunner.test_probe import Probe  # noqa: E402

TEST_FILE_PATTERNS = ("test_*.py", "*_test.py")
TEST_DIR_NAMES = frozenset({"tests", "test", "spec", "__tests__"})
PYTEST_CONFIG_NAMES = ("pytest.ini", "tox.ini", "setup.cfg", "conftest.py")
SKIP_WALK = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})


def _iter_dirs(root: Path):
    for dirpath, dirnames, _files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_WALK and not d.startswith(".")]
        yield Path(dirpath), dirnames


def _find_tests(root: Path) -> str:
    """返回测试存在性证据（空串 = 没有测试）。

    注意 repocheck 的**项目发现口径**：当传入目录有多个子目录时，评估的是子目录
    （父目录被视为容器）。所以本函数会遇到 root 本身就叫 ``tests`` 的情形
    （2026-11-24 实测：`repocheck packages/allin-governance` 评的是它的
    ``src`` 与 ``tests`` 两个子目录）—— 那种情况下 root 自己就是测试目录，
    再去找 ``root/tests/`` 当然找不到，会误报「无测试」。
    """
    if root.name.lower() in TEST_DIR_NAMES:
        pys = list(root.rglob("*.py"))
        if pys:
            return f"当前目录本身即测试目录（{len(pys)} 个 .py）"
    for base, dirnames in _iter_dirs(root):
        for d in list(dirnames):
            if d in TEST_DIR_NAMES:
                pys = [p for p in (base / d).rglob("*.py")]
                if pys:
                    rel = (base / d).relative_to(root).as_posix()
                    return f"测试目录 {rel}/（{len(pys)} 个 .py）"
    for pat in TEST_FILE_PATTERNS:
        hits = [p for p in root.rglob(pat) if not any(s in p.parts for s in SKIP_WALK)]
        if hits:
            return f"{len(hits)} 个测试文件，如 {hits[0].relative_to(root).as_posix()}"
    return ""


def _check_exists(ctx: "ProjectContext") -> tuple[bool, str]:
    ev = _find_tests(ctx.root)
    if ev:
        return True, ev
    return False, "未发现测试文件或 tests/ 目录"


def _check_collectable(ctx: "ProjectContext") -> tuple[bool, str]:
    if not _find_tests(ctx.root):
        return True, "无测试（跳过收集）"  # 交给规则 51 判定 skip，这里不重复报
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header",
             "-p", "no:cacheprovider"],
            cwd=str(ctx.root), capture_output=True, text=True, timeout=90, errors="replace",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except FileNotFoundError:
        return True, "环境未装 pytest，跳过"
    except subprocess.TimeoutExpired:
        return False, "pytest --collect-only 超过 90 秒（conftest 导入期可能做了重活）"
    if out.returncode == 0:
        return True, "收集成功"
    tail = " / ".join((out.stdout + out.stderr).strip().splitlines()[-5:])
    return False, tail[:400]


def _check_runner_known(ctx: "ProjectContext") -> tuple[bool, str]:
    for name in PYTEST_CONFIG_NAMES:
        if (ctx.root / name).is_file():
            return True, f"有 {name}"
    mk = ctx.root / "Makefile"
    if mk.is_file() and "test" in mk.read_text(encoding="utf-8", errors="replace"):
        return True, "Makefile 有 test 目标"
    return False, "未发现 pytest 配置或 Makefile test 目标"


def _probe_rule(rule_id: int, key: str, label: str, criteria: str,
                severity: Severity, check_fn) -> Rule:
    """把一条检查包成 Probe 再包成 Rule。

    用 Probe 是为了复用它的「检查函数签名 + 异常兜底」约定，
    同时保持零副作用（不建目录、不写日志）。
    """
    # Probe 的 check 是零参可调用，而 Rule 的 check 要吃 ctx —— 用一个单元素容器搭桥。
    ctx_holder: list = [None]
    probe = Probe(name=key, check=lambda: check_fn(ctx_holder[0]), category="repocheck.tests")

    def check(ctx: "ProjectContext") -> CheckResult:
        ctx_holder[0] = ctx
        try:
            passed, detail = probe.check()
        except Exception as exc:  # 探针自身炸了，按失败上报但标明原因
            return CheckResult.bad(f"探针异常：{type(exc).__name__}: {exc}")
        if passed:
            return CheckResult.ok()
        return CheckResult.bad(detail)

    return Rule(rule_id, key, label, criteria, severity, check)


RULES_TESTS: tuple[Rule, ...] = (
    _probe_rule(51, "tests.exists", "测试存在性",
                "项目内应有测试文件或 tests/ 目录（缺失不算缺陷，skip）",
                Severity.INFO, _check_exists),
    _probe_rule(52, "tests.collectable", "测试可收集",
                "有测试文件时，pytest --collect-only 必须能收到用例",
                Severity.ERROR, _check_collectable),
    _probe_rule(53, "tests.runner-known", "测试运行方式已知",
                "应有 pytest 配置或 Makefile 的 test 目标",
                Severity.INFO, _check_runner_known),
)
