# -*- coding: utf-8 -*-
"""P2 #21：repo_hygiene.py 纯函数单测（零 pytest 覆盖补齐）。

只测**纯内存比较**，不 mock 文件 / 网络：
``_value_looks_secret``（纯正则 / 字符串判断）与 ``is_exempted``（三元组匹配）。

隔离策略：repo_hygiene 顶部 ``import scanctx``。与 test_p2_convergence.py 一致，
scanctx 按共享语义登记（同名同文件则复用），repo_hygiene 用**唯一模块名**加载，
全程不占用 ``sys.modules["cli"]``，故不会污染 tools/repocheck 的 ``import cli``。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
REPOCHECK = TOOLS / "repocheck"


def _load_shared(name: str, path: Path):
    existing = sys.modules.get(name)
    if existing is not None and Path(getattr(existing, "__file__", "") or "/none").resolve() == path.resolve():
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_local(name: str, path: Path):
    uid = "_p2b_tests_" + name
    if uid in sys.modules:
        return sys.modules[uid]
    spec = importlib.util.spec_from_file_location(uid, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uid] = mod
    spec.loader.exec_module(mod)
    return mod


_load_shared("scanctx", REPOCHECK / "scanctx.py")
rh = _load_local("repo_hygiene", TOOLS / "repo_hygiene.py")


# --------------------------------------------------------- _value_looks_secret
@pytest.mark.parametrize("value", [
    "abc123",                                  # <20 短串
    "this_is_an_example_token_value_xxxx",     # 停用词 example
    "password_is_placeholder_string_here",     # 停用词 password/placeholder/string
    "sk-abcdefghijklmnop1234567890abcd",       # 合成顺序串 abcdefgh  # gov-credentials: allow
    "environment.DOWNLOAD_TEST_COS_SECRET_KEY",  # 点分标识符 = 环境引用
    "process.env.DSH_WORKSPACE_UPDATE_TOKEN",  # 环境引用
    "aaaaaaaaaaaaaaaaaaaaaaaa",                # 单一字符重复
    "0000000000000000000000000",               # 重复数字
    "my-long-descriptive-secret-slug-name-here",  # 长描述性 slug（含 g-z）
])
def test_value_looks_secret_negative(value):
    assert rh._value_looks_secret(value) is False


@pytest.mark.parametrize("value", [
    "a1b2c3d4e5f67890abcdef1234567890",        # 正例夹具：数字+字母混合  # gov-credentials: allow
    "0123456789abcdef0123456789abcdef",        # 长 hex（只用 a-f）  # gov-credentials: allow
    "AKIA1234567890MNOPQRST",                  # 类 AWS 令牌：数字+大写混合
])
def test_value_looks_secret_positive(value):
    assert rh._value_looks_secret(value) is True


# ---------------------------------------------------------------- is_exempted
def _finding(repo, check, path):
    return SimpleNamespace(repo=repo, check=check, path=path)


def test_is_exempted_absolute_repo_match():
    repo = "D:/work/deepseek-harness"  # gov-python: allow (path-match fixture)
    active = [("SEC", os.path.normcase(repo), "docs/*")]
    assert rh.is_exempted(_finding(repo, "SEC", "docs/x.md"), active) is True


def test_is_exempted_basename_repo_match():
    # 豁免表写仓名（不写死盘符，铁律 5）⇒ 应按 basename 命中
    active = [("SEC", "deepseek-harness", "docs/x.md")]
    finding = _finding("E:/some/other/path/deepseek-harness", "SEC", "docs/x.md")  # gov-python: allow (path-match fixture)
    assert rh.is_exempted(finding, active) is True


def test_is_exempted_wildcard_prefix():
    active = [("D14", "3dworld", "docs/记录/*")]
    assert rh.is_exempted(_finding("3dworld", "D14", "docs/记录/2026-09.md"), active) is True
    # 同前缀判定只在 path 上；不在前缀内应落空
    assert rh.is_exempted(_finding("3dworld", "D14", "docs/规范/x.md"), active) is False


def test_is_exempted_exact_path():
    active = [("D9", "allin", "INDEX.md")]
    assert rh.is_exempted(_finding("allin", "D9", "INDEX.md"), active) is True
    assert rh.is_exempted(_finding("allin", "D9", "INDEX2.md"), active) is False


@pytest.mark.parametrize("repo,check,path,why", [
    ("allin", "OTHER", "INDEX.md",        "check 不符"),
    ("not-allin", "D9", "INDEX.md",       "repo 不符"),
    ("allin", "D9", "OTHER.md",           "path 不符"),
])
def test_is_exempted_no_match(repo, check, path, why):
    active = [("D9", "allin", "INDEX.md")]
    assert rh.is_exempted(_finding(repo, check, path), active) is False, why


def test_is_exempted_empty_table():
    assert rh.is_exempted(_finding("allin", "D9", "INDEX.md"), []) is False
