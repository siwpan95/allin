# -*- coding: utf-8 -*-
"""P2 深度审计整改回归（#13/#14/#15/#16/#22 + #21 单测覆盖）。

零新增第三方依赖。不联网、不依赖真实 Gitee 令牌、不依赖 node/npm 已安装、
不依赖 PowerShell：网络面用假连接 / 静态断言，命令解析面用 monkeypatch 伪造
which()，shell 语义实测用抽取出的真实函数（不执行整份门禁）。

三个被测模块不在包的 import 路径上，用 importlib 按文件加载，避免污染 sys.path。
"""
from __future__ import annotations

import http.client
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gitee_release = _load("_p2sec_gitee_release", "tools/gitee_release.py")
verify_projects = _load("_p2sec_verify_projects", "tools/verify_projects.py")

_MISSING = object()


def _load_isolated(name: str, relpath: str, extra_path: str):
    """加载会污染全局 sys.path / sys.modules 的模块，并在加载后还原现场。

    facts_parity.py 顶层会 `sys.path.insert(0, tools/facts)` 且 `import cli as F`；
    仓库里另有多个同名 `cli`，pytest 全量收集时若副作用残留，会让别的测试
    `import cli` 误拿到 facts CLI。这里回滚加载期间的全局变更，只保留已加载
    模块对象本身（F 仍指向正确的 tools/facts/cli.py），不改被测源码的依赖。
    """
    before = set(sys.modules)
    saved_path = list(sys.path)
    saved_cli = sys.modules.pop("cli", _MISSING)
    sys.path.insert(0, extra_path)
    try:
        return _load(name, relpath)
    finally:
        sys.path[:] = saved_path
        for key in set(sys.modules) - before - {name}:
            sys.modules.pop(key, None)
        if saved_cli is not _MISSING:
            sys.modules["cli"] = saved_cli


facts_parity = _load_isolated("_p2sec_facts_parity",
                              "tools/gate/facts_parity.py",
                              str(ROOT / "tools" / "facts"))

SHELL_NAMES = {"cmd", "sh", "bash", "zsh", "pwsh", "powershell"}


# ---------------------------------------------------------------- #14 令牌不进 URL
class _FakeResp:
    status = 201
    def read(self):
        return b"{}"


class _FakeConn:
    seen = None
    def __init__(self, *a, **k):
        _FakeConn.seen = self
        self.headers = []
        self.request_line = None
    def putrequest(self, method, path):
        self.request_line = (method, path)
    def putheader(self, k, v):
        self.headers.append((k, v))
    def endheaders(self, *a, **k):
        pass
    def send(self, *a, **k):
        pass
    def getresponse(self):
        return _FakeResp()


def test_attach_url_has_no_token_and_keeps_api_prefix():
    url = gitee_release.attach_files_url("/api/v5", "/repos/siwpan/pluginplayer", "12345")
    assert url == "/api/v5/repos/siwpan/pluginplayer/releases/12345/attach_files"
    assert "access_token" not in url.lower()
    assert "token" not in url.lower()


def test_upload_still_sends_authorization_header(tmp_path, monkeypatch):
    """假连接：上传 URL 无令牌，但请求头仍带 Authorization。"""
    payload = tmp_path / "attach.bin"
    payload.write_bytes(b"x")
    monkeypatch.setattr(http.client, "HTTPSConnection", _FakeConn)
    url = gitee_release.attach_files_url("/api/v5", "/repos/o/r", "7")
    st, _ = gitee_release.upload_file(url, "DUMMY_TOKEN_HEX", str(payload))
    assert st == 201
    conn = _FakeConn.seen
    assert ("Authorization", "token DUMMY_TOKEN_HEX") in conn.headers
    assert "token" not in conn.request_line[1].lower()


def test_no_token_concatenation_left_in_source():
    src = (ROOT / "tools" / "gitee_release.py").read_text(encoding="utf-8")
    assert "access_token=" not in src
    assert "attach_files?access_token" not in src
    assert "token=" not in src


# ---------------------------------------------------------------- #15 去掉 cmd /c
def _assert_no_shell(argv):
    assert isinstance(argv, list) and argv
    head = Path(argv[0]).stem.lower()
    assert head not in SHELL_NAMES
    assert not any(p.lower() == "/c" for p in argv[1:])


@pytest.mark.parametrize("raw", [
    "echo a ; b", "echo a | b", "echo a && b", "node -e 1 ; whoami",
])
def test_prepare_metachars_are_plain_args(raw, tmp_path):
    argv = verify_projects.prepare(raw, tmp_path)
    _assert_no_shell(argv)
    assert any(any(m in p for m in (";", "|", "&")) for p in argv)


@pytest.mark.parametrize("raw", ["npm run build", "node -v", "tool.bat --flag"])
def test_prepare_never_returns_cmd(raw, tmp_path):
    _assert_no_shell(verify_projects.prepare(raw, tmp_path))


def test_npm_cmd_resolves_to_npm_cli_via_node(tmp_path, monkeypatch):
    """伪造 which()：npm 只解析到 .cmd 时，用 node 跑 npm-cli.js（不依赖真实安装）。"""
    prefix = tmp_path / "nodejs"
    bindir = prefix / "node_modules" / "npm" / "bin"
    bindir.mkdir(parents=True)
    cli = bindir / "npm-cli.js"
    cli.write_text("// stub", encoding="utf-8")
    npm_cmd = prefix / "npm.cmd"
    npm_cmd.write_text("@echo off", encoding="utf-8")
    node_exe = prefix / "node.exe"
    node_exe.write_text("", encoding="utf-8")

    def fake_which(name):
        return {"npm": str(npm_cmd), "node": str(node_exe)}.get(name)

    monkeypatch.setattr(verify_projects.shutil, "which", fake_which)
    argv = verify_projects.prepare("npm run build", tmp_path)
    assert argv == [str(node_exe), str(cli), "run", "build"]
    _assert_no_shell(argv)


def test_node_resolves_to_real_exe(tmp_path, monkeypatch):
    node_exe = tmp_path / "node.exe"
    node_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(verify_projects.shutil, "which",
                        lambda n: str(node_exe) if n == "node" else None)
    assert verify_projects.prepare("node -v", tmp_path) == [str(node_exe), "-v"]


def test_unresolvable_tokens_are_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_projects.shutil, "which", lambda n: None)
    assert verify_projects.prepare("npm run build", tmp_path) == ["npm", "run", "build"]
    assert verify_projects.prepare("node -v", tmp_path) == ["node", "-v"]


def test_taskkill_missing_degrades_without_raising(tmp_path, monkeypatch):
    class FakeProc:
        pid = 999
        stdout = None
        returncode = None
        def __init__(self):
            self.killed = False
            self.waited = False
        def communicate(self, timeout=None):
            raise verify_projects.subprocess.TimeoutExpired("fake", timeout)
        def kill(self):
            self.killed = True
        def wait(self, timeout=None):
            self.waited = True

    fake = FakeProc()
    monkeypatch.setattr(verify_projects.subprocess, "Popen", lambda *a, **k: fake)

    def no_taskkill(*a, **k):
        raise FileNotFoundError("taskkill not on PATH")

    monkeypatch.setattr(verify_projects.subprocess, "run", no_taskkill)
    rc, out, _ = verify_projects.run(["whatever"], tmp_path, 0.01)
    assert rc is None
    assert "taskkill" in out and "process.kill" in out
    assert fake.killed and fake.waited


# ---------------------------------------------------------------- #16 结构化 finding
def _write_broken_doc(tmp_path, mutate):
    doc = facts_parity.F.load_json(facts_parity.F.DEFAULT_DATA)
    mutate(doc)
    p = tmp_path / "broken.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.mark.parametrize("mutate, label", [
    (lambda d: d.__setitem__("doc_refs", {"oops": 1}), "refs 非 list"),
    (lambda d: d["doc_refs"][0].pop("path", None), "缺 path"),
    (lambda d: d["doc_refs"].__setitem__(0, "not-a-mapping"), "条目是字符串"),
    (lambda d: d["doc_refs"][0].__setitem__("path", 123), "path 非字符串"),
], ids=["refs-not-list", "missing-path", "entry-is-str", "path-not-str"])
def test_facts_parity_broken_doc_refs_is_blocking(tmp_path, capsys, mutate, label):
    p = _write_broken_doc(tmp_path, mutate)
    rc = facts_parity.run(p, tmp_path / "generated", facts_parity.ROOT)
    assert rc == facts_parity.EXIT_BLOCKING, label
    assert "结构损坏" in capsys.readouterr().out


def test_facts_parity_clean_semantics_unchanged(tmp_path, capsys):
    rc = facts_parity.run(facts_parity.F.DEFAULT_DATA, tmp_path / "generated",
                          facts_parity.ROOT)
    assert rc == facts_parity.EXIT_OK
    out = capsys.readouterr().out
    assert "missing=0" in out          # :71 计数口径未变
    assert "clean (exit=0)" in out


# ---------------------------------------------------------------- #13 环境性 SKIP 口径
def test_benign_skip_patterns_register_scan_hardcoded():
    src = (ROOT / "scripts" / "run_all_gates.sh").read_text(encoding="utf-8")
    assert "'scan_hardcoded:skip(no-powershell'" in src
    assert 'note_skip "scan_hardcoded:skip(no-powershell)"' in src
    assert "分类口径" in src


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash 不在 PATH，跳过 shell 语义实测")
def test_is_environmental_skip_real_bash_semantics():
    """抽取真实数组 + 函数来源执行（不跑整份门禁）：环境标签 0 / 真实 SKIP 1。"""
    snippet = r'''
src=$(mktemp)
sed -n '/^BENIGN_SKIP_PATTERNS=(/,/^)/p' "$1/scripts/run_all_gates.sh" > "$src"
sed -n '/^is_environmental_skip()/,/^}/p' "$1/scripts/run_all_gates.sh" >> "$src"
. "$src"
rm -f "$src"
is_environmental_skip "scan_hardcoded:skip(no-powershell)"; echo "env=$?"
is_environmental_skip "scan_hardcoded:skip(real-miss)"; echo "real=$?"
'''
    r = subprocess.run(["bash", "-c", snippet, "_", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=30)
    assert r.returncode == 0, r.stderr
    assert "env=0" in r.stdout
    assert "real=1" in r.stdout


# ---------------------------------------------------------------- #22 口令去硬编码
def test_smoke_password_no_literal_and_env_override():
    src = (ROOT / "scripts" / "smoke_e2e.mjs").read_text(encoding="utf-8")
    assert "Cp7Smoke2026" not in src
    assert "ALLIN_SMOKE_PASSWORD" in src
    assert "randomBytes(8)" in src
    assert "from 'node:crypto'" in src
    assert "passwordConfirm=${encodeURIComponent(password)}" in src
    # 历史审计证据不得被整改改动
    audit = (ROOT / "docs" / "记录" / "审计" /
             "深度审计报告_2026-11-10.md").read_text(encoding="utf-8")
    assert "Cp7Smoke2026" in audit
