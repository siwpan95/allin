# -*- coding: utf-8 -*-
"""B1 覆盖率补充：allin_governance.cli 的调度/元路径（与 test_cli.py 互补）。

test_cli.py 已覆盖「退出码原样透传」「无参打印帮助退 0」「repocheck 源码在包内」
「repocheck --help 不被吞」。本文件补它没走的判定边界：

1. build_parser 返回 argparse 解析器、子命令 choices 与 SUBCOMMANDS 对齐；
2. `--version` 必须退 0（version action 走 SystemExit，main 不得改写）；
3. 非法子命令必须退 2（argparse choices 报错，退出码不得被吞）；
4. 子命令 `--help` 经 REMAINDER 透传后仍能退 0（REMAINDER 容易把 --help 吃掉）。

注：repocheck 缺目录参数时默认扫 CWD（不是干净报错），该路径与「退出码透传」语义
无关且易碎，故不在此测 —— 透传语义已由 test_cli.py 的
test_exit_code_passes_through_untouched 钉死。

跑法：python -m pytest packages/allin-governance/tests/test_cli_dispatch_coverage.py -q
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from allin_governance.cli import SUBCOMMANDS, build_parser, main  # noqa: E402


def test_build_parser_returns_parser_and_subcommand_choices_aligned() -> None:
    p = build_parser()
    assert isinstance(p, argparse.ArgumentParser)
    # 子命令 choices 必须与 SUBCOMMANDS 表逐项对齐（新增子命令忘登记会立刻暴露）
    sub = next(
        a for a in p._actions
        if isinstance(a, argparse._StoreAction) and a.dest == "subcommand"
    )
    assert set(sub.choices) == set(SUBCOMMANDS)


def test_version_flag_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """--version 不得改写退出码：argparse version action 抛 SystemExit(0)，main 须原样返回。"""
    assert main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "allin-governance" in out


def test_invalid_subcommand_returns_two(capsys: pytest.CaptureFixture[str]) -> None:
    """非法子命令：argparse choices 报错退 2，包装层不得假装成 0。"""
    code = main(["not-a-real-subcommand"])
    assert code == 2, f"非法子命令应退 2，实际 {code}"
    err = capsys.readouterr().err
    assert "not-a-real-subcommand" in err or "invalid choice" in err.lower()


def test_subcommand_help_reaches_repocheck_and_returns_zero() -> None:
    """子命令 --help 经 REMAINDER 透传：repocheck 自己处理 --help 并退 0。"""
    assert main(["repocheck", "--help"]) == 0
