# -*- coding: utf-8 -*-
"""tools/auto_flow.py 的纯逻辑回归：判定口径与参数面，不跑外部命令。

与仓内其它门禁同纪律 —— SKIP ≠ pass、finding 不被洗成 clean、高风险动作不入脚本。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.auto_flow as af  # noqa: E402

import pytest  # noqa: E402


def _step(label, rc=0, status="ok"):
    return {"label": label, "exit": rc, "status": status}


@pytest.mark.parametrize("steps,expected", [
    ([], af.EXIT_OK),
    ([_step("sync")], af.EXIT_OK),
    ([_step("sync", 1, "finding")], af.EXIT_BLOCKING),
    ([_step("gates", 2, "finding")], af.EXIT_BLOCKING),  # incomplete 不算绿
    ([_step("status", 3, "error")], af.EXIT_BLOCKING),
    ([_step("a"), _step("b", 1, "finding")], af.EXIT_BLOCKING),
])
def test_verdict(steps, expected):
    assert af._verdict(steps) == expected


def test_verdict_skip_is_not_pass():
    """SKIP/未知状态即便 exit=0 也不得判 clean。"""
    assert af._verdict([{"label": "x", "exit": 0, "status": "error"}]) == af.EXIT_BLOCKING


def test_verdict_not_applicable_does_not_fail():
    """场景不适用（发版专属检查）单列，不判红也不冒充通过。"""
    assert af._verdict([{"label": "preflight", "exit": 3,
                         "status": "not_applicable"}]) == af.EXIT_OK
    assert af._verdict([{"label": "sync", "exit": 0, "status": "ok"},
                        {"label": "preflight", "exit": 3,
                         "status": "not_applicable"}]) == af.EXIT_OK


def test_classify_preflight_incomplete(monkeypatch):
    """preflight 的 INCOMPLETE（无 FAIL）归类为 not_applicable，真失败仍 finding。"""
    import subprocess

    def fake(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 3, "[ok]  版本单一来源\nPREFLIGHT ok=5 fail=0 skip=2\n"
            "RESULT: INCOMPLETE —— 有项未判", "",
        )
    monkeypatch.setattr(af.subprocess, "run", fake)
    step = af._run("preflight", [sys.executable, "x.py"], release_preflight=True)
    assert step["status"] == "not_applicable"

    def fake_fail(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 1, "[FAIL] 版本单一来源\nRESULT: BLOCKED", "",
        )
    monkeypatch.setattr(af.subprocess, "run", fake_fail)
    step = af._run("preflight", [sys.executable, "x.py"], release_preflight=True)
    assert step["status"] == "finding"


def test_preflight_step_is_not_applicable_not_ok(capsys):
    """发版预检已随公共核迁仓：标 not_applicable，不冒充 ok，也不判红。"""
    step = af._preflight_step()
    capsys.readouterr()
    assert step["status"] == "not_applicable"
    assert step["exit"] != af.EXIT_OK
    assert "独立仓" in step["tail"][0]
    assert "未验证 ≠ 通过" in step["tail"][0]


def test_main_full_preflight_not_applicable(monkeypatch, capsys):
    """全流程汇总：not_applicable=1 且 verdict=clean，理由随汇总行如实单列。"""
    def fake_step(label):
        return {"label": label, "exit": 0, "status": "ok", "ms": 1, "tail": []}
    monkeypatch.setattr(af, "_sync_step", lambda no_fetch: fake_step("sync"))
    monkeypatch.setattr(af, "_gate_step", lambda with_platform: fake_step("gates"))
    monkeypatch.setattr(af, "_run", lambda label, argv, **kw: fake_step(label))
    monkeypatch.setattr(af, "_head", lambda: "testhead")
    monkeypatch.setattr(af, "_append_run", lambda rec: None)
    rc = af.main(["--json"])
    out = capsys.readouterr().out
    assert rc == af.EXIT_OK
    assert "ALLIN_AUTO_FLOW_SUMMARY status=clean" in out
    assert '"not_applicable": 1' in out
    assert "未验证 ≠ 通过" in out
    assert "ALLIN_AUTO_FLOW_SUMMARY status=finding" not in out


def test_selfcheck_all_green():
    assert af._selfcheck() == af.EXIT_OK


def test_parser_flags():
    p = af.argparse.ArgumentParser()  # 只验证 main 内的参数面经真实解析可达
    del p  # 实际断言在下方用 main --selfcheck 走通
    assert af.main(["--selfcheck"]) == af.EXIT_OK


def test_main_json_with_finding_emits_summary(monkeypatch, capsys):
    """回归：--json + 有 finding 时也必须打印汇总行（曾因 na_n 定义晚于使用而崩）。"""
    def fake_sync(no_fetch):
        return {"label": "sync", "exit": 2, "status": "finding", "ms": 1, "tail": []}
    monkeypatch.setattr(af, "_sync_step", fake_sync)
    monkeypatch.setattr(af, "_head", lambda: "testhead")
    monkeypatch.setattr(af, "_append_run", lambda rec: None)
    rc = af.main(["--quick", "--json"])
    out = capsys.readouterr().out
    assert rc == af.EXIT_BLOCKING
    assert "ALLIN_AUTO_FLOW_SUMMARY status=finding" in out
    assert '"verdict": "finding"' in out


def test_no_push_in_source():
    """无人值守脚本不得包含 push 调用（源码级护栏）。"""
    src = (ROOT / "tools" / "auto_flow.py").read_text(encoding="utf-8")
    for banned in ("git', 'push'", "git push", "gitee_release", "github_release"):
        assert banned not in src, f"auto_flow.py 不得调用高风险动作：{banned}"


def test_cli_entry_registered():
    """CLI dispatch 必须注册 auto-flow 分支（防止文档写了入口却没接）。"""
    src = (ROOT / "allin_cli.py").read_text(encoding="utf-8")
    assert "tool == 'auto-flow'" in src
    svc = (ROOT / "kernel" / "services" / "tools_service.py").read_text(encoding="utf-8")
    assert "def auto_flow(" in svc
