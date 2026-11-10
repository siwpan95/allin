# -*- coding: utf-8 -*-
"""allin_cli.py 的回归测试（F1：第八轮变异测试显示该模块 320 个变异体全部 no_tests）。

策略：用假 ctx 替换 `allin_cli._boot`（避免触发完整 cordis 内核 boot），
从而在不依赖真实配置/网络的前提下，逐分支覆盖 dispatch / build_parser /
_exit_code / _configure_stdio / main。
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import allin_cli  # noqa: E402

import pytest  # noqa: E402


class _FakeService:
    """记录调用、按方法返回预设值的最小桩。"""

    def __init__(self, ret=0, apply_result=None):
        self.calls = []
        self.ret = ret
        self.apply_result = apply_result if apply_result is not None else {"ok": True}

    def gitee_release(self, rest):
        self.calls.append(("gitee_release", list(rest)))
        return self.ret

    def credential(self, name, action):
        self.calls.append(("credential", name, action))
        return self.ret

    def venv_audit(self, rest):
        self.calls.append(("venv_audit", list(rest)))
        return self.ret

    def skills(self):
        self.calls.append(("skills",))
        return self.ret

    def portfolio(self, apply):
        self.calls.append(("portfolio", apply))
        return self.ret

    def aliases(self):
        self.calls.append(("aliases",))
        return self.ret

    def index(self):
        self.calls.append(("index",))
        return self.ret

    def check_repos(self):
        self.calls.append(("check_repos",))
        return self.ret

    def registry_count(self):
        self.calls.append(("registry_count",))
        return self.ret

    def list(self):
        self.calls.append(("list",))
        return self.ret

    def show(self, name):
        self.calls.append(("show", name))
        return self.ret

    def apply(self, name, dry_run):
        self.calls.append(("apply", name, dry_run))
        return self.apply_result

    def summary(self, as_json=False, strict=False):
        self.calls.append(("summary", as_json, strict))
        return self.ret


class _FakeCtx:
    def __init__(self, tools=None, docs=None, platform=None, preset=None, status=None):
        self.tools = tools or _FakeService()
        self.docs = docs or _FakeService()
        self.platform = platform or _FakeService()
        self.preset = preset or _FakeService()
        self.status = status or _FakeService()


@pytest.fixture
def fake_ctx(monkeypatch):
    """把 async _boot 换成返回假 ctx 的协程，避免真实内核 boot。"""
    ctx = _FakeCtx()

    async def _fake_boot():
        return ctx

    monkeypatch.setattr(allin_cli, "_boot", _fake_boot)
    return ctx


# --------------------------------------------------------------------------
# _exit_code
# --------------------------------------------------------------------------
def test_exit_code_int():
    assert allin_cli._exit_code(3) == 3


def test_exit_code_returncode_attr():
    class _R:
        returncode = 7

    assert allin_cli._exit_code(_R()) == 7


def test_exit_code_none():
    assert allin_cli._exit_code(None) == 0


def test_exit_code_unknown_object():
    assert allin_cli._exit_code("not-a-code") == 0


# --------------------------------------------------------------------------
# _configure_stdio
# --------------------------------------------------------------------------
def test_configure_stdio_no_error(capsys):
    allin_cli._configure_stdio()
    print("中文输出不应崩溃")
    out = capsys.readouterr().out
    assert "中文" in out


# --------------------------------------------------------------------------
# build_parser
# --------------------------------------------------------------------------
def test_parser_preset_show():
    a = allin_cli.build_parser().parse_args(["preset", "show", "foo"])
    assert a.domain == "preset" and a.action == "show" and a.name == "foo"


def test_parser_preset_apply_yes():
    a = allin_cli.build_parser().parse_args(["preset", "apply", "foo", "--yes"])
    assert a.domain == "preset" and a.action == "apply" and a.name == "foo" and a.yes is True


def test_parser_preset_apply_default_no():
    a = allin_cli.build_parser().parse_args(["preset", "apply", "foo"])
    assert a.yes is False


def test_parser_tools_remainder():
    a = allin_cli.build_parser().parse_args(["tools", "gitee-release", "--", "status"])
    assert a.domain == "tools" and a.args == ["gitee-release", "--", "status"]


def test_parser_tools_empty_remainder():
    a = allin_cli.build_parser().parse_args(["tools"])
    assert a.domain == "tools" and a.args == []


def test_parser_status_flags():
    a = allin_cli.build_parser().parse_args(["status", "--json", "--strict"])
    assert a.domain == "status" and a.json is True and a.strict is True


def test_parser_docs_portfolio_apply():
    a = allin_cli.build_parser().parse_args(["docs", "portfolio", "--apply"])
    assert a.domain == "docs" and a.action == "portfolio" and a.apply is True


def test_parser_docs_index():
    a = allin_cli.build_parser().parse_args(["docs", "index"])
    assert a.domain == "docs" and a.action == "index"


def test_parser_missing_domain_exits():
    with pytest.raises(SystemExit):
        allin_cli.build_parser().parse_args([])


def test_parser_unknown_domain_exits():
    with pytest.raises(SystemExit):
        allin_cli.build_parser().parse_args(["bogus"])


# --------------------------------------------------------------------------
# dispatch —— tools
# --------------------------------------------------------------------------
def test_dispatch_tools_no_args(fake_ctx, capsys):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=[]))
    assert rc == 1
    assert "用法" in capsys.readouterr().out


def test_dispatch_tools_unknown(fake_ctx, capsys):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["bogus"]))
    assert rc == 2
    assert "未知工具" in capsys.readouterr().out


def test_dispatch_tools_gitee_release(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["gitee-release", "--", "status"]))
    assert rc == 0
    assert fake_ctx.tools.calls[-1] == ("gitee_release", ["status"])


def test_dispatch_tools_credential_default(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["credential"]))
    assert fake_ctx.tools.calls[-1] == ("credential", "gitee", "get")


def test_dispatch_tools_credential_explicit(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["credential", "tavily", "set"]))
    assert fake_ctx.tools.calls[-1] == ("credential", "tavily", "set")


def test_dispatch_tools_venv_audit(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["venv-audit", "scan", "x"]))
    assert fake_ctx.tools.calls[-1] == ("venv_audit", ["scan", "x"])


def test_dispatch_tools_skills(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="tools", args=["skills"]))
    assert fake_ctx.tools.calls[-1] == ("skills",)


# --------------------------------------------------------------------------
# dispatch —— docs
# --------------------------------------------------------------------------
def test_dispatch_docs_portfolio_no_apply(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="docs", action="portfolio", apply=False))
    assert fake_ctx.docs.calls[-1] == ("portfolio", False)


def test_dispatch_docs_portfolio_apply(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="docs", action="portfolio", apply=True))
    assert fake_ctx.docs.calls[-1] == ("portfolio", True)


def test_dispatch_docs_aliases(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="docs", action="aliases"))
    assert fake_ctx.docs.calls[-1] == ("aliases",)


def test_dispatch_docs_index(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="docs", action="index"))
    assert fake_ctx.docs.calls[-1] == ("index",)


def test_dispatch_docs_unknown_action_is_usage_error(fake_ctx, capsys):
    # 2026-11-10 深度审计 H-4：未命中分支必须非零 + 留痕，
    # 不能把「什么都没做」编码成成功（旧契约断言 rc is None，正是假绿来源）。
    rc = allin_cli.dispatch(argparse.Namespace(domain="docs", action="mystery", apply=False))
    assert rc == allin_cli.EXIT_USAGE == 2
    err = capsys.readouterr().err
    assert "未命中的子命令分支" in err and "docs" in err


# --------------------------------------------------------------------------
# dispatch —— platform
# --------------------------------------------------------------------------
def test_dispatch_platform_check_repos(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="platform", action="check-repos"))
    assert fake_ctx.platform.calls[-1] == ("check_repos",)


def test_dispatch_platform_registry_count(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="platform", action="registry-count"))
    assert fake_ctx.platform.calls[-1] == ("registry_count",)


# --------------------------------------------------------------------------
# dispatch —— preset
# --------------------------------------------------------------------------
def test_dispatch_preset_list(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="list", name=None, yes=False))
    assert fake_ctx.preset.calls[-1] == ("list",)


def test_dispatch_preset_show(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="show", name="foo", yes=False))
    assert fake_ctx.preset.calls[-1] == ("show", "foo")


def test_dispatch_preset_apply_dry_run_ok(fake_ctx):
    fake_ctx.preset = _FakeService(apply_result={"ok": True, "name": "foo"})
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="apply", name="foo", yes=False))
    assert rc == 0
    assert fake_ctx.preset.calls[-1] == ("apply", "foo", True)


def test_dispatch_preset_apply_real_fail(fake_ctx):
    fake_ctx.preset = _FakeService(apply_result={"ok": False, "reason": "WJ-01"})
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="apply", name="foo", yes=True))
    assert rc == 2
    assert fake_ctx.preset.calls[-1] == ("apply", "foo", False)


def test_dispatch_preset_apply_non_dict_result(fake_ctx):
    # apply 返回非 dict（如旧接口直接返回成功码）—— 覆盖第 101 行非 dict 兜底 return 0
    fake_ctx.preset = _FakeService(apply_result=0)
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="apply", name="foo", yes=True))
    assert rc == 0


# --------------------------------------------------------------------------
# dispatch —— status
# --------------------------------------------------------------------------
def test_dispatch_status(fake_ctx):
    rc = allin_cli.dispatch(argparse.Namespace(domain="status", json=True, strict=True))
    assert fake_ctx.status.calls[-1] == ("summary", True, True)


def test_dispatch_platform_unknown_action_is_usage_error(fake_ctx, capsys):
    # H-4：platform 分支内 action 不匹配任何已知项 ⇒ 用法错，不是 None⇒exit 0。
    rc = allin_cli.dispatch(argparse.Namespace(domain="platform", action="mystery"))
    assert rc == allin_cli.EXIT_USAGE == 2
    assert "未命中的子命令分支" in capsys.readouterr().err


def test_dispatch_preset_unknown_action_is_usage_error(fake_ctx, capsys):
    # H-4：preset 分支内 action 不匹配任何已知项 ⇒ 用法错，不是 None⇒exit 0。
    rc = allin_cli.dispatch(argparse.Namespace(domain="preset", action="mystery", name=None, yes=False))
    assert rc == allin_cli.EXIT_USAGE == 2
    assert "未命中的子命令分支" in capsys.readouterr().err


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
class _FakeParser:
    def parse_args(self, argv=None):
        return argparse.Namespace(domain="status", json=False, strict=False)


def test_main_returns_exit_code(monkeypatch):
    monkeypatch.setattr(allin_cli, "build_parser", lambda: _FakeParser())
    monkeypatch.setattr(allin_cli, "dispatch", lambda args: 5)
    assert allin_cli.main() == 5


def test_main_unknown_action_is_nonzero(fake_ctx, monkeypatch, capsys):
    """H-4 端到端：路由缺分支时进程退出码必须是 2，而不是 0。"""
    class _MysteryParser:
        def parse_args(self, argv=None):
            return argparse.Namespace(domain="docs", action="mystery", apply=False)

    monkeypatch.setattr(allin_cli, "build_parser", lambda: _MysteryParser())
    assert allin_cli.main() == allin_cli.EXIT_USAGE == 2
    assert "未命中的子命令分支" in capsys.readouterr().err


# --------------------------------------------------------------------------
# H-4：服务层「目录不存在」不得被映射成 exit 0（验收口径：allin preset list
#      目录缺失必须返回非 0）。同时保留「目录存在且正常列出」的干净路径。
# --------------------------------------------------------------------------
class _SvcReflect:
    def provide(self, *args, **kwargs):
        return None


class _SvcCtx:
    def __init__(self):
        self.reflect = _SvcReflect()


def test_preset_list_missing_dir_is_nonzero(monkeypatch, tmp_path, capsys):
    import kernel.services.preset_service as ps

    monkeypatch.setattr(ps, "PRESET_DIR", str(tmp_path / "no-preset-dir"))
    rc = ps.PresetService(_SvcCtx()).list()
    assert rc == allin_cli.EXIT_ENV == 3
    assert allin_cli._exit_code(rc) != 0
    assert "preset 目录不存在" in capsys.readouterr().err


def test_preset_list_present_dir_still_clean(monkeypatch, tmp_path):
    import kernel.services.preset_service as ps

    monkeypatch.setattr(ps, "PRESET_DIR", str(tmp_path))
    (tmp_path / "demo").mkdir()
    rc = ps.PresetService(_SvcCtx()).list()
    assert rc is None                      # 服务正常完成且无退出码
    assert allin_cli._exit_code(rc) == 0   # 不得误伤「成功列出」路径


def test_tools_skills_missing_dir_is_nonzero(monkeypatch, tmp_path, capsys):
    import kernel.services.tools_service as ts

    monkeypatch.setattr(ts, "ROOT", str(tmp_path))
    rc = ts.ToolService(_SvcCtx()).skills()
    assert rc == allin_cli.EXIT_ENV == 3
    assert allin_cli._exit_code(rc) != 0
    assert "技能目录不存在" in capsys.readouterr().err
