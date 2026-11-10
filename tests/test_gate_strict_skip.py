# -*- coding: utf-8 -*-
"""P1 #6 回归：`ALLIN_GATE_STRICT_SKIP=1` 下，SKIP 不得被当成 pass。

2026-11-10 深度审计 H-2：此前 11 道门禁绕过 ``govlib.Report.exit_code()``，
直接返回 ``EXIT_BLOCKING if new_findings else EXIT_OK`` —— 同一个环境变量在
不同门禁上语义不一致，有 skip 也判绿。另有一道（g15）用的是自有 Report，
需显式对齐同一口径。本测试把「统一出口」与「严格模式语义」都钉成回归，
避免整改只验证一次就随下次改动漂移。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES_DIR = ROOT / "tools" / "gate" / "governance" / "gates"
RUNTIME_DIR = ROOT / "tools" / "gate" / "governance" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import govlib  # noqa: E402


def test_exit_code_semantics(monkeypatch):
    """clean / skip / strict / findings 四种组合的优先级，全部在统一出口判定。"""
    def report(skip=False):
        rep = govlib.Report(title="probe")
        if skip:
            rep.skip("injected skip")
        return rep

    monkeypatch.delenv("ALLIN_GATE_STRICT_SKIP", raising=False)
    assert report().exit_code([]) == govlib.EXIT_OK
    assert report(True).exit_code([]) == govlib.EXIT_OK  # 默认兼容：skip 留痕但不拖红

    monkeypatch.setenv("ALLIN_GATE_STRICT_SKIP", "1")
    assert report().exit_code([]) == govlib.EXIT_OK                       # 无 skip 判绿
    assert report(True).exit_code([]) == govlib.EXIT_USAGE                 # skip ⇒ 2
    assert report(True).exit_code(["blocking"]) == govlib.EXIT_BLOCKING    # blocking 优先


def test_every_gate_routes_through_unified_exit():
    """20 道门禁：19 道走 Report.exit_code，g15 自有 Report 显式对齐严格口径。"""
    files = sorted(GATES_DIR.glob("g??_*.py"))
    assert len(files) == 20, f"门禁文件数变化（{len(files)}），需同步复核统一出口与编号白名单"
    unified = [p.name for p in files if "report.exit_code(" in p.read_text(encoding="utf-8")]
    special = [p.name for p in files if p.name not in unified]
    assert len(unified) == 19
    assert special == ["g15_docs_contract.py"]
    g15 = (GATES_DIR / "g15_docs_contract.py").read_text(encoding="utf-8")
    assert "ALLIN_GATE_STRICT_SKIP" in g15 and "EXIT_USAGE" in g15


def test_strict_skip_is_exposed_by_real_gates():
    """端到端：真实产生 skip 的门禁，严格模式必须非 0、非严格模式仍 0。

    g12 默认关闭 --deep ⇒ 记一条 skip；g15 用自有 Report 且 --no-aliases 触发 skip，
    正好覆盖「统一出口」与「特例显式对齐」两条实现路径。
    """
    cases = [
        ("g12_integrity.py", []),
        ("g15_docs_contract.py", ["--no-aliases"]),
    ]
    kw = dict(cwd=str(ROOT), capture_output=True, text=True,
              encoding="utf-8", errors="replace", timeout=180)
    for name, extra in cases:
        base = [sys.executable, str(GATES_DIR / name), "--quiet", *extra]
        normal = subprocess.run(base, **kw)
        strict = subprocess.run(base, env=dict(os.environ, ALLIN_GATE_STRICT_SKIP="1"), **kw)
        assert normal.returncode == govlib.EXIT_OK, (name, normal.stdout[-300:], normal.stderr[-300:])
        assert strict.returncode == govlib.EXIT_USAGE, (name, strict.stdout[-300:], strict.stderr[-300:])
