# -*- coding: utf-8 -*-
"""P2 #18/#19 回归：消除重复实现、统一判据。

#18 统一 git 只读封装
---------------------
- ``scanctx.py`` 里只允许有一份 ``subprocess.run`` git 调用；
- ``watchdog`` / ``repo_hygiene`` 的只读 git 一律委托 ``scanctx.run_git``，
  共享 10s（可覆盖）/ GIT_OPTIONAL_LOCKS=0 / stdin=DEVNULL / CREATE_NO_WINDOW 口径；
- 两者的返回结构 ``(rc, output)`` 不变（文本 / 字节 / 失败 128 形态）。

#19 tools/facts 权威 YAML 单一实现
---------------------------------
- 5 个 ``build_*.py`` 的 ``_yaml_load`` 全部删除，import ``cli.yaml_load``（同一函数对象）；
- ``cli.yaml_load`` 四态：文件不存在→None / 缺 PyYAML / 在场解析失败→AuthUnavailable / 正常→dict；
- P1 #7 的「在场但解析失败 BLOCK」不得退回静默 None：注入坏权威 YAML，各模块必须非 0
  并输出可读诊断；文件缺席仍允许 SKIP（不误伤）。

隔离策略（重要）
---------------
仓内有多个同名顶层模块 ``cli``（``tools/facts/cli.py`` 与 ``tools/repocheck/cli.py``），
若在主 pytest 进程里把 ``sys.modules["cli"]`` 指向 facts 版，会污染
``tools/repocheck/test_scanner.py`` 的 ``import cli``。因此所有涉及 facts ``cli`` 的断言
一律在**全新解释器**里跑（``sys.executable -c``，仅该子进程把 ``tools/facts`` 置于
sys.path 首位）；#18 不涉及 cli，用显式文件路径加载模块，避免任何全局 sys.modules 污染。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FACTS = ROOT / "tools" / "facts"
REPOCHECK = ROOT / "tools" / "repocheck"
GATE = ROOT / "tools" / "gate"
TOOLS = ROOT / "tools"


# ---------------------------------------------------------------------------
# #18：按显式文件路径加载，避免与已加载模块的 sys.modules 冲突（不改全局 cli）
# ---------------------------------------------------------------------------
def _load_shared(name: str, path: Path):
    """共享模块 scanctx：同名且同文件则复用，否则按显式路径新建并登记 sys.modules。"""
    existing = sys.modules.get(name)
    if existing is not None and Path(getattr(existing, "__file__", "") or "/none").resolve() == path.resolve():
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_local(name: str, path: Path):
    """CLI 模块始终按显式路径加载，并用唯一名登记 —— 避免撞同名的第三方包。

    实测：全量 pytest 会先 import PyPI 的 ``watchdog``（文件监视器），若直接复用
    ``sys.modules["watchdog"]`` 会拿到第三方包而非 tools/gate/watchdog.py，导致
    ``_git`` 等属性缺失。唯一名 + 显式路径可彻底规避；模块内 ``import scanctx``
    仍命中上面登记好的 ``sys.modules["scanctx"]``。
    """
    uid = "_p2_undertest_" + name
    if uid in sys.modules:
        return sys.modules[uid]
    spec = importlib.util.spec_from_file_location(uid, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uid] = mod
    spec.loader.exec_module(mod)
    return mod


scanctx = _load_shared("scanctx", REPOCHECK / "scanctx.py")
watchdog = _load_local("watchdog", GATE / "watchdog.py")
repo_hygiene = _load_local("repo_hygiene", TOOLS / "repo_hygiene.py")


# ---------------------------------------------------------------------------
# #18 回归
# ---------------------------------------------------------------------------
def test_scanctx_single_subprocess_and_constants():
    """scanctx 里只有一份 subprocess.run git 调用；超时/env 口径集中且正确。"""
    src = (REPOCHECK / "scanctx.py").read_text(encoding="utf-8")
    assert src.count("subprocess.run(") == 1, "scanctx 出现多份 git subprocess.run"
    assert scanctx._GIT_TIMEOUT == 10
    assert scanctx._GIT_ENV.get("GIT_OPTIONAL_LOCKS") == "0"
    assert scanctx._GIT_ENV.get("GIT_TERMINAL_PROMPT") == "0"
    assert scanctx._CREATE_NO_WINDOW == (0x08000000 if sys.platform == "win32" else 0)


def test_watchdog_repo_hygiene_no_duplicate_impl():
    """watchdog 三份 git 闭包 + repo_hygiene 自写 180s 实现都已删除，只留委托。"""
    wd = (GATE / "watchdog.py").read_text(encoding="utf-8")
    assert "def git(" not in wd, "check_repo/check_sync 的 git() 闭包仍在"
    assert "def _g(" not in wd, "main-quick 的 _g() 闭包仍在"
    assert wd.count("def _git(") == 1, "应只留一份 _git 薄包装"
    assert "scanctx.run_git" in wd
    rh = (TOOLS / "repo_hygiene.py").read_text(encoding="utf-8")
    assert "scanctx.run_git" in rh
    assert "timeout=180" not in rh, "自写 180s subprocess 实现仍在"
    # 只读调用不再有裸 `["git"`；selfcheck 的写夹具（init/add/commit）不算，故只查 timeout 参数
    assert 'run_git(repo, "cat-file", "blob"' in rh, "line 668 cat-file 也应走统一入口"


def test_three_modules_share_one_scanctx():
    """watchdog / repo_hygiene 引用同一个 scanctx 模块，且各自只是薄包装（非重导出）。"""
    assert watchdog.scanctx is scanctx
    assert repo_hygiene.scanctx is scanctx
    # run_git 定义在各自模块里（是委托包装），不是把 scanctx.run_git 直接改名导出
    assert repo_hygiene.run_git.__globals__ is not scanctx.__dict__
    assert watchdog._git.__globals__ is not scanctx.__dict__


def test_unified_env_timeout_passthrough(monkeypatch):
    """三处调用汇聚到同一 subprocess.run，env/timeout/stdin/creationflags 完全一致。"""
    captured = []

    class FakeCompleted:
        returncode = 0
        stdout = b"stub"

    def fake_run(cmd, **kw):
        captured.append((list(cmd), kw))
        return FakeCompleted()

    monkeypatch.setattr(scanctx.subprocess, "run", fake_run)
    repo_hygiene.run_git("R", "status")                     # 默认 10s
    watchdog._git("R", "status")                            # 默认 10s
    watchdog._git("R", "fsck", timeout=300)                 # 显式覆盖（长操作）

    assert len(captured) == 3
    for cmd, kw in captured:
        assert kw["timeout"] in (10, 300)
        assert kw["env"] is scanctx._GIT_ENV or kw["env"].get("GIT_OPTIONAL_LOCKS") == "0"
        assert kw["stdin"] == subprocess.DEVNULL
        assert kw["capture_output"] is True
        assert kw["creationflags"] == scanctx._CREATE_NO_WINDOW
        assert cmd[1] == "-C" and "-c" in cmd and "core.quotepath=false" in cmd
    assert captured[0][1]["timeout"] == 10
    assert captured[1][1]["timeout"] == 10
    assert captured[2][1]["timeout"] == 300, "fsck 长操作须能显式放宽（仍走同一入口）"


def test_git_return_shapes_unchanged(monkeypatch):
    """watchdog / repo_hygiene 返回 (rc, output)：文本/字节、成功/失败 128 形态不变。"""

    class OK:
        returncode = 7
        stdout = b"payload"

    def ok_run(cmd, **kw):
        return OK()

    monkeypatch.setattr(scanctx.subprocess, "run", ok_run)
    assert repo_hygiene.run_git("R", "x") == (7, "payload")            # binary=False → str
    rc, out = repo_hygiene.run_git("R", "x", binary=True)
    assert (rc, out) == (7, b"payload")                                 # binary=True → bytes
    assert watchdog._git("R", "x") == (7, "payload")                   # watchdog → str

    def boom(cmd, **kw):
        raise OSError("kaboom")

    monkeypatch.setattr(scanctx.subprocess, "run", boom)
    rc, out = repo_hygiene.run_git("R", "x")
    assert rc == 128 and isinstance(out, str) and "kaboom" in out      # (128, 诊断串)
    rc, out = repo_hygiene.run_git("R", "x", binary=True)
    assert rc == 128 and out == b""                                     # (128, b"")
    rc, out = watchdog._git("R", "x")
    assert rc == 128 and isinstance(out, str) and "kaboom" in out


def test_three_modules_delegate_to_scanctx_run_git(monkeypatch):
    """打桩 scanctx.run_git 能同时拦住 watchdog 与 repo_hygiene —— 证明委托而非自写。"""
    seen = []

    def spy(repo, *args, **kw):
        seen.append((repo, args, kw))
        return (0, "spy")

    monkeypatch.setattr(scanctx, "run_git", spy)
    assert repo_hygiene.run_git("R", "status") == (0, "spy")
    assert watchdog._git("R", "status") == (0, "spy")
    assert len(seen) == 2
    assert seen[0][2].get("text") is True        # repo_hygiene binary=False → text=True
    assert "timeout" in seen[1][2]               # watchdog 薄包装透传 timeout


def test_watchdog_selftest_from_any_cwd(tmp_path):
    """从任意 cwd 直接 `python tools/gate/watchdog.py --selftest` 也能跑（跨目录 import 稳健）。"""
    r = subprocess.run(
        [sys.executable, str(GATE / "watchdog.py"), "--selftest"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(tmp_path), timeout=180,
    )
    assert r.returncode == 0, (r.stdout[-400:], r.stderr[-400:])
    assert "自测通过" in r.stdout


# ---------------------------------------------------------------------------
# #19：全部在全新解释器里跑，隔离 facts `cli` 与 repocheck `cli` 同名冲突
# ---------------------------------------------------------------------------
_FACTS_HEADER = "import sys\nsys.path.insert(0, %r)\n" % FACTS.as_posix()


def _py(script: str, timeout: int = 90):
    return subprocess.run(
        [sys.executable, "-c", _FACTS_HEADER + script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=timeout,
    )


_S_IDENTITY = """
import inspect
import cli
import build_ports, build_tiering, build_tools, build_licenses, build_projects
mods = (build_ports, build_tiering, build_tools, build_licenses, build_projects)
for m in mods:
    assert m.yaml_load is cli.yaml_load, m.__name__ + " 的 yaml_load 不是 cli.yaml_load"
    assert m.AuthUnavailable is cli.AuthUnavailable, m.__name__ + " 的异常类不是同一份"
    assert "def _yaml_load" not in inspect.getsource(m), m.__name__ + " 仍留自写 _yaml_load"
print("IDENTITY_OK")
"""


_S_FOUR_STATES = """
import builtins, tempfile
from pathlib import Path
import cli
d = Path(tempfile.mkdtemp(prefix="p2-states-"))
missing = d / "missing.yaml"
good = d / "good.yaml";     good.write_text("a: 1" + chr(10), encoding="utf-8")
broken = d / "broken.yaml"; broken.write_text("a: [unclosed" + chr(10), encoding="utf-8")
scalar = d / "scalar.yaml"; scalar.write_text("- x" + chr(10) + "- y" + chr(10), encoding="utf-8")
# ① 文件不存在 → None
assert cli.yaml_load(missing) is None
# ④ 正常 → dict
assert cli.yaml_load(good) == {"a": 1}
# ③ 在场但解析失败 / 顶层非 mapping → AuthUnavailable(parse / shape)
for label, p, kind in (("syntax", broken, "parse"), ("shape", scalar, "shape")):
    try:
        cli.yaml_load(p)
    except cli.AuthUnavailable as e:
        assert e.kind == kind, (label, e.kind)
        assert str(e), label + " 缺可读诊断"
    else:
        raise AssertionError(label + " 未抛 AuthUnavailable（判绿风险）")
# ② 缺 PyYAML → AuthUnavailable(no_pyyaml)：拦截 yaml import 模拟
real_import = builtins.__import__
def block_yaml(name, *a, **k):
    if name == "yaml":
        raise ImportError("simulated: no PyYAML")
    return real_import(name, *a, **k)
builtins.__import__ = block_yaml
try:
    cli.yaml_load(good)
except cli.AuthUnavailable as e:
    assert e.kind == "no_pyyaml", e.kind
else:
    raise AssertionError("缺 PyYAML 未抛 AuthUnavailable")
finally:
    builtins.__import__ = real_import
print("FOUR_STATES_OK")
"""


_S_PORTS_BLOCK = """
import json, tempfile
from pathlib import Path
import cli, build_ports
d = Path(tempfile.mkdtemp(prefix="p2-ports-"))
data = d / "facts.json";    data.write_text(json.dumps({"ports": []}), encoding="utf-8")
mirror = d / "mirror.yaml"; mirror.write_text("ports: []" + chr(10), encoding="utf-8")
bad = d / "broken.yaml";    bad.write_text("ports: [ { port: [unclosed" + chr(10) + "  bad: : :" + chr(10), encoding="utf-8")
# ① P1 #7 调用链：check_sync / check_mirror 在场解析失败必须 BLOCK + 可读诊断
rc1, m1 = build_ports.check_sync(data, bad)
rc2, m2 = build_ports.check_mirror(mirror, bad)
assert rc1 != 0 and rc2 != 0, ("解析失败被判绿", rc1, rc2)
assert any("不得判绿" in x for x in (m1 + m2)), (m1, m2)
# ② collect 必须抛 AuthUnavailable，绝不返回空列表判绿
try:
    build_ports.collect_ports(bad)
except cli.AuthUnavailable:
    pass
else:
    raise AssertionError("collect_ports 吞掉了解析失败")
# ③ CLI --check 与默认 collect 都非 0
base = ["--auth", str(bad), "--data", str(data), "--mirror", str(mirror)]
assert build_ports.main(["--check"] + base) != 0, "--check 判绿"
assert build_ports.main(base) != 0, "默认 collect 判绿"
print("PORTS_BLOCK_OK")
"""


def test_yaml_load_is_single_object():
    r = _py(_S_IDENTITY)
    assert r.returncode == 0, (r.stdout[-500:], r.stderr[-500:])
    assert "IDENTITY_OK" in r.stdout


def test_yaml_load_four_states():
    r = _py(_S_FOUR_STATES)
    assert r.returncode == 0, (r.stdout[-500:], r.stderr[-500:])
    assert "FOUR_STATES_OK" in r.stdout


def test_build_ports_parse_failure_blocks():
    """注入语法错误的权威 YAML，P1 #7 的整个调用链仍 BLOCK、非 0、可读诊断。"""
    r = _py(_S_PORTS_BLOCK)
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])
    assert "PORTS_BLOCK_OK" in r.stdout


@pytest.mark.parametrize("name", ["build_ports", "build_tiering", "build_tools", "build_licenses"])
@pytest.mark.parametrize("mode", ["--check", "default"])
def test_broken_auth_cli_nonzero(tmp_path, name, mode):
    """4 个单权威源 builder：坏权威 YAML 下 --check 与默认路径都必须非 0。"""
    bad = tmp_path / "broken.yaml"
    bad.write_text("x: [unclosed" + chr(10) + "  y: : :" + chr(10), encoding="utf-8")
    script = ROOT / "tools" / "facts" / (name + ".py")
    args = [sys.executable, str(script), "--auth", str(bad)]
    if mode == "--check":
        args.append("--check")
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), timeout=60)
    assert r.returncode != 0, (name, mode, r.stdout[-300:], r.stderr[-300:])
    assert "不得判绿" in (r.stdout + r.stderr), (name, mode, r.stdout[-300:], r.stderr[-300:])


def test_build_projects_broken_registry_nonzero(tmp_path):
    """build_projects：registry 内单个权威 YAML 在场但解析失败 → collect/main 非 0。

    刻意限域：build_projects 的 check_sync 是「无 yaml 依赖」的轻量对账（只比 stem /
    source_file），本就**不解析** YAML，故其 --check 不在此断言内；BLOCK 落在唯一
    解析 YAML 的 collect/默认/--write 路径上（由 main 转 EXIT_ENV）。
    """
    reg = tmp_path / "registry"
    reg.mkdir()
    (reg / "oops.yaml").write_text("id: x" + chr(10) + "name: [unclosed" + chr(10), encoding="utf-8")
    script = ROOT / "tools" / "facts" / "build_projects.py"
    r = subprocess.run([sys.executable, str(script), "--registry", str(reg)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), timeout=60)
    assert r.returncode != 0, (r.stdout[-300:], r.stderr[-300:])
    assert "不得判绿" in (r.stdout + r.stderr)


@pytest.mark.parametrize("name", ["build_ports", "build_tiering"])
def test_absent_auth_still_skips(tmp_path, name):
    """文件不存在（缺席）仍允许 SKIP / rc=0 —— 证明四态没被一刀切成 BLOCK。"""
    script = ROOT / "tools" / "facts" / (name + ".py")
    r = subprocess.run([sys.executable, str(script), "--check", "--auth", str(tmp_path / "nope.yaml")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), timeout=60)
    assert r.returncode == 0, (name, r.stdout[-300:], r.stderr[-300:])
