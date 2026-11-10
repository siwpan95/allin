# -*- coding: utf-8 -*-
"""P2 #20 回归：超时魔法数字收敛到单一事实源（审计 M-10）。

覆盖：权威源 schema、CLI 三档、坏源/缺席/缺 key 三类探针、gate 包装、
以及 8+9 处迁移「值不变 + 源码落地」。

隔离策略（同 tests/test_p2_convergence.py）：涉及 import 的断言一律在**全新解释器**
里跑（``sys.executable -c``，仅该子进程把 tools/ 置于 sys.path 首位），不污染主 pytest
进程的 sys.modules（仓内有多个同名顶层模块 cli / watchdog，主进程 import 有冲突风险）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
RTD = TOOLS / "runtime_defaults.py"
GATE = TOOLS / "gate" / "runtime_defaults_check.py"


def _run(script, *args, cwd=None, timeout=60):
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd or ROOT), timeout=timeout,
    )


def _py(body, *, cwd=None, timeout=60):
    """在全新解释器里把 tools/ 注入 sys.path 后执行 body（不污染主进程）。"""
    header = "import sys\nsys.path.insert(0, %r)\n" % TOOLS.as_posix()
    return subprocess.run(
        [sys.executable, "-c", header + body],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd or ROOT), timeout=timeout,
    )


# ------------------------------------------------------------------ CLI 三档
def test_selftest_pass():
    r = _run(RTD, "--selftest")
    assert r.returncode == 0, (r.stdout[-900:], r.stderr[-900:])
    assert "SELFTEST:" in r.stdout and "PASS" in r.stdout


def test_check_pass_and_prints_table():
    r = _run(RTD, "--check")
    assert r.returncode == 0, (r.stdout[-900:], r.stderr[-900:])
    assert "CHECK: PASS" in r.stdout
    assert "timeout('git_probe')" in r.stdout, "对照表未打印"
    assert "timeout('subprocess_install')" in r.stdout, "venv_security 追加项未进对照表"


def test_json_parseable():
    r = _run(RTD, "--json")
    assert r.returncode == 0, r.stderr[-400:]
    doc = json.loads(r.stdout)
    assert doc["unit"] == "seconds"
    assert doc["git_probe"] == 10 and doc["subprocess_archive_push"] == 3600


def test_authoritative_source_is_valid_json():
    doc = json.loads((ROOT / "docs" / "事实源" / "runtime_defaults.json").read_text(encoding="utf-8"))
    assert doc["unit"] == "seconds"
    for k, v in doc.items():
        if k == "unit":
            continue
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0, (k, v)


# ------------------------------------------------------------------ 三类探针
_S_PROBES = """
import tempfile
from pathlib import Path
import runtime_defaults as rd
d = Path(tempfile.mkdtemp(prefix="p2-rtd-"))
good = d / "good.json";    good.write_text('{"unit":"seconds","git_probe":10}', encoding="utf-8")
bad = d / "bad.json";      bad.write_text('{"unit":"seconds","git_probe":[unclosed', encoding="utf-8")
missing = d / "nope.json"
# ① 好样本
assert rd.load_defaults(good) == {"git_probe": 10}
assert rd.timeout("git_probe", auth=good) == 10
assert rd.timeout_ms("git_probe", auth=good) == 10000
# ② 坏源（在场解析失败）→ ConfigError(parse) + check 非 0
try:
    rd.load_defaults(bad)
    raise AssertionError("坏 JSON 未抛 ConfigError")
except rd.ConfigError as e:
    assert e.kind == "parse", e.kind
assert rd.check(bad)[0] != rd.EXIT_OK, "坏源被判绿"
# ③ 缺席 → ConfigError(missing) + check=EXIT_ENV（明确态，不假绿）
try:
    rd.load_defaults(missing)
    raise AssertionError("缺席未抛 ConfigError")
except rd.ConfigError as e:
    assert e.kind == "missing", e.kind
assert rd.check(missing)[0] == rd.EXIT_ENV, "缺席未明确判态"
# ④ 缺 key → timeout 抛 / timeout_or 回退
try:
    rd.timeout("no_such_key", auth=good)
    raise AssertionError("缺 key 未抛 ConfigError")
except rd.ConfigError as e:
    assert e.kind == "unknown_key", e.kind
assert rd.timeout_or("no_such_key", 7, auth=good) == 7
# ⑤ timeout_or 不掩盖在场损坏（对齐 P1 #7）
try:
    rd.timeout_or("git_probe", 7, auth=bad)
    raise AssertionError("timeout_or 用 fallback 掩盖了坏源")
except rd.ConfigError:
    pass
print("PROBES_OK")
"""


def test_three_probes():
    r = _py(_S_PROBES)
    assert r.returncode == 0, (r.stdout[-900:], r.stderr[-900:])
    assert "PROBES_OK" in r.stdout


def test_broken_auth_cli_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"unit":"seconds","git_probe":[unclosed', encoding="utf-8")
    r = _run(RTD, "--check", "--auth", bad)
    assert r.returncode != 0, (r.stdout, r.stderr)
    assert "不得判绿" in (r.stdout + r.stderr)


def test_absent_auth_cli_explicit(tmp_path):
    r = _run(RTD, "--check", "--auth", tmp_path / "nope.json")
    assert r.returncode == 3, (r.stdout, r.stderr)
    assert "缺席" in (r.stdout + r.stderr)


# ------------------------------------------------------------------ gate 包装
def test_gate_selftest():
    r = _run(GATE, "--selftest")
    assert r.returncode == 0, (r.stdout[-900:], r.stderr[-900:])


def test_gate_check_pass():
    r = _run(GATE, "--check")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "RUNTIME_DEFAULTS_GATE exit=0" in r.stdout


# ------------------------------------------------------------------ 迁移落地
_S_MIGRATED = """
import runtime_defaults as rd
rc, findings = rd.check()
assert rc == 0, findings
print("MIGRATIONS_OK", len(rd.MIGRATIONS))
"""


def test_migrations_landed():
    r = _py(_S_MIGRATED)
    assert r.returncode == 0, (r.stdout[-900:], r.stderr[-900:])
    # 17（P2 首批 8 + venv_security 9）+ 7（第二阶段：push_archives / facts cli / watchdog 3 / gitee_release 2）
    assert "MIGRATIONS_OK 24" in r.stdout


def test_no_bare_timeout_literals_in_migrated_files():
    """8+9+7 处迁移后，这些文件不应再残留被迁移的裸 timeout=<数字> 字面量。

    显式豁免（登记在 tools/runtime_defaults.py 注释，不列入下方 banned 集）：
    push_archives.py:36=300（归档后远端核对）、gitee_release.py:495=120（release POST）、
    watchdog.py:176=30（fsutil 本地探测，短于最小 key）。
    """
    targets = {
        "deploy/dolt/import_from_git.py": {10, 180},
        "deploy/graphrag/build_input.py": {60},
        "deploy/netbox/sync_from_git.py": {10, 15},
        "tools/build_portfolio.py": {60},
        "tools/security/venv_security.py": {60, 120, 300, 900},
        "tools/tier_archive/push_archives.py": {3600},
        "tools/facts/cli.py": {60},
        "tools/gate/watchdog.py": {300, 120, 180},
        "tools/gitee_release.py": {60, 1800},
    }
    rex = re.compile(r"timeout\s*=\s*(\d+)")
    for rel, banned in targets.items():
        src = (ROOT / rel).read_text(encoding="utf-8")
        hits = {int(m.group(1)) for m in rex.finditer(src)}
        left = sorted(hits & banned)
        assert not left, f"{rel} 仍残留裸超时字面量 {left}"
