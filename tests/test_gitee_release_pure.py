# -*- coding: utf-8 -*-
"""P2 #21：gitee_release.py 纯函数单测（零 pytest 覆盖补齐）。

**只测两个纯函数**，刻意不碰其它入口：
``build_parser``（argparse 纯构造，无 IO）与 ``repo_path``（纯字符串格式化）。

限域说明（刻意不测，避免与 test_p2_sec_remediation.py 重复）：
``upload_file`` / ``api`` / ``load_token`` / URL 令牌拼接 / 重定向策略
这些**有 IO / 安全语义**的入口，已由 test_p2_sec_remediation.py 覆盖，此处不重复。

隔离策略：gitee_release.py 仅依赖标准库（argparse/http.client/urllib/...），
用唯一模块名 + 显式路径加载，不占用 ``sys.modules["cli"]``，主进程零污染。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "gitee_release.py"


def _load_gitee_release():
    uid = "_p2b_tests_gitee_release"
    if uid in sys.modules:
        return sys.modules[uid]
    spec = importlib.util.spec_from_file_location(uid, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uid] = mod
    spec.loader.exec_module(mod)
    return mod


gr = _load_gitee_release()


@pytest.fixture(scope="module")
def parser():
    return gr.build_parser()


# -------------------------------------------------------------- build_parser
def test_build_parser_defaults(parser):
    args = parser.parse_args(["whoami"])
    assert args.owner == "siwpan"
    assert args.name == "pluginplayer"
    # --repo 默认是空串哨兵（→ cwd），不是工具自身仓根：2026-10-06 事故回归点
    assert args.repo == ""
    assert args.token == ""
    assert args.token_file == ""
    assert args.cmd == "whoami"


def test_build_parser_requires_subcommand(parser):
    with pytest.raises(SystemExit) as ei:
        parser.parse_args([])
    assert ei.value.code == 2


def test_build_parser_regular_subcommands(parser):
    for name in ("whoami", "create", "remote", "public", "status", "selfcheck"):
        assert parser.parse_args([name]).cmd == name


def test_build_parser_release_flags(parser):
    args = parser.parse_args(["release", "--tag", "v1.0", "--title", "T"])
    assert args.cmd == "release"
    assert args.tag == "v1.0"
    assert args.title == "T"
    assert args.notes_file == ""
    assert args.branch == ""        # 留空由 Gitee 从 tag 推断
    assert args.pre is False
    # --pre 是 store_true
    assert parser.parse_args(["release", "--tag", "v", "--title", "t", "--pre"]).pre is True


def test_build_parser_release_requires_tag_and_title(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["release"])
    with pytest.raises(SystemExit):
        parser.parse_args(["release", "--tag", "v1"])   # 缺 --title
    with pytest.raises(SystemExit):
        parser.parse_args(["release", "--title", "T"])  # 缺 --tag


def test_build_parser_attach_upload_flags(parser):
    att = parser.parse_args(["attach", "--tag", "v1", "--file", "a.zip", "--file", "b.zip"])
    assert att.file == ["a.zip", "b.zip"]     # action=append
    up = parser.parse_args(["upload", "--tag", "v1"])
    assert up.dir == ""


# ------------------------------------------------------------------ repo_path
def test_repo_path_formats_owner_and_name(parser):
    assert gr.repo_path(parser.parse_args(["whoami"])) == "/repos/siwpan/pluginplayer"
    custom = parser.parse_args(["--owner", "cat", "--name", "dog", "whoami"])
    assert gr.repo_path(custom) == "/repos/cat/dog"
