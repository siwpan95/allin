# -*- coding: utf-8 -*-
"""深度审计 P3 (#25/#26) 回归：摘要收敛 / 读文本单一实现 / open-with / 常量反查 / registry 分义。

零新增第三方依赖。被测模块多不在包 import 路径上，一律 importlib 按文件加载或用
子进程隔离，避免污染 sys.modules["cli"] 与同名的第三方包（沿用 P2 测试纪律）。

覆盖：
* L-4  sha256 三族单一实现 + 重构前后摘要逐字节不变（防止「统一」改值破坏 P2 一致性）；
* L-5  docs_index / g15 的 read_text 委托给 docs_contract 唯一实现；
* L-1  报告列举的生产路径裸 open() 已全部改为 with（源码形态断言，不依赖运行值）；
* L-8  CRED_PATTERNS 反查用命名常量 + enumerate，不再出现 .index(pat) / [1] 魔数；
* L-6  五处 registry 均带分义注释（源码形态断言）。
"""
from __future__ import annotations

import importlib.util
import json
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


def _src(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# L-4：sha256util 三族单一实现
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sha256util():
    return _load("allin_p3_sha256util", "tools/sha256util.py")


def test_l4_selftest_passes():
    # 子进程输出含 UTF-8 非 ASCII（✔ 等），不指定 encoding 时父进程按本机代码页
    # （GBK/936）解码，reader 线程抛 UnicodeDecodeError 且 stdout 为 None（本机实测）。
    r = subprocess.run([sys.executable, str(ROOT / "tools/sha256util.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "9 passed, 0 failed" in r.stdout


def test_l4_digest_obj_matches_legacy(sha256util):
    """结构化摘要与重构前算法逐字节一致。"""
    import hashlib

    for obj in ({}, {"b": 2, "a": 1}, {"k": "中文", "n": None}, {"lst": [3, 1, 2]}):
        legacy = hashlib.sha256(
            json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        assert sha256util.digest_obj(obj) == legacy


def test_l4_digest_text_matches_legacy(sha256util):
    import hashlib

    for text in ("", "SELECT 1;", "SELECT 1;\n-- 中文\nSELECT 2;"):
        legacy = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        assert sha256util.digest_text(text) == legacy


def test_l4_facts_expected_hash_unchanged(sha256util):
    """真实 facts.json 的 machine 指纹重构前后一致（P2 逐字节保证）。"""
    doc = json.loads((ROOT / "facts/facts.json").read_text(encoding="utf-8"))
    mid = doc["machines"][0]["machine_id"]
    subset = {
        "machine": next((m for m in doc["machines"] if m["machine_id"] == mid), None),
        "facts": [f for f in doc["facts"]
                  if f.get("machine_id") == mid
                  or (f["scope"] == "global" and mid == doc["machines"][0]["machine_id"])],
    }
    import hashlib
    legacy = hashlib.sha256(
        json.dumps(subset, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    assert sha256util.digest_obj(subset) == legacy


def test_l4_three_families_distinct(sha256util):
    """三族不可互串：文本摘要 ≠ 对象摘要；文件摘要是完整 64 位。"""
    assert sha256util.digest_text('{"a":1}') != sha256util.digest_obj({"a": 1})
    assert len(sha256util.digest_obj({"a": 1})) == 16
    assert len(sha256util.digest_text("x")) == 16


def test_l4_file_sha256_lf_normalized_full_width(sha256util, tmp_path):
    a, b, c = tmp_path / "a.py", tmp_path / "b.py", tmp_path / "c.py"
    a.write_bytes(b"line1\r\nline2\r\n")
    b.write_bytes(b"line1\nline2\n")
    c.write_bytes(b"line1\nline2!\n")
    assert sha256util.file_sha256(a) == sha256util.file_sha256(b)
    assert len(sha256util.file_sha256(a)) == 64
    assert sha256util.file_sha256(a) != sha256util.file_sha256(c)


def test_l4_consumers_delegate():
    """四个消费点都改为委托，本地不再内联 hashlib.sha256(...).hexdigest()。"""
    for rel in ("tools/facts/cli.py", "deploy/netbox/sync_from_git.py",
                "deploy/dolt/import_from_git.py", "tools/check_pkg_parity.py"):
        src = _src(rel)
        assert "hashlib.sha256(" not in src, f"{rel} 仍内联 sha256"
    assert "from sha256util import digest_obj" in _src("tools/facts/cli.py")
    assert "from sha256util import digest_obj as _digest_obj" in _src("deploy/netbox/sync_from_git.py")
    assert "from sha256util import digest_text as _digest_text" in _src("deploy/dolt/import_from_git.py")
    assert "from sha256util import file_sha256" in _src("tools/check_pkg_parity.py")


def test_l4_dolt_sql_sha256_via_helper():
    """dolt 导入器经委托后的 _digest_text 输出 16 位且与独立旧式算法逐字节一致。"""
    import hashlib

    mod = _load("allin_p3_dolt", "deploy/dolt/import_from_git.py")
    sql = "-- x\nSELECT 1;\n-- 中文\n"
    legacy = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
    assert mod._digest_text(sql) == legacy
    assert len(mod._digest_text(sql)) == 16


# ---------------------------------------------------------------------------
# L-5：read_text 单一实现（薄委托）
# ---------------------------------------------------------------------------
def test_l5_read_text_delegates():
    for rel in ("tools/gate/docs_index.py", "tools/gate/governance/gates/g15_docs_contract.py"):
        src = _src(rel)
        # 本地包装已彻底删除（真正的「合并重复」），调用点直连唯一实现
        assert "def read_text" not in src, f"{rel} 仍保留本地 read_text 包装"
        assert "docs_contract.read_text(" in src
        # 本文件不再自带「io.open(...encoding...errors=replace...)」形态的读文本包装
        import re as _re
        assert _re.search(r'io\.open\([^\n]*encoding=[^\n]*errors="replace"', src) is None


def test_l5_docs_contract_owns_impl():
    block = _src("tools/gate/governance/runtime/docs_contract.py").split(
        "def read_text(path: str) -> str:", 1)[1].split("\n\n", 1)[0]
    assert 'errors="replace"' in block and 'newline=""' in block


def test_l5_delegation_runtime(tmp_path):
    """委托后读入行为不变（UTF-8 + replace + 保留换行）。"""
    contract = _load("allin_p3_dc", "tools/gate/governance/runtime/docs_contract.py")
    p = tmp_path / "x.md"
    p.write_bytes("标题\r\n正文\r\n".encode("utf-16"))  # 故意坏编码，验证 errors=replace 不抛
    out = contract.read_text(str(p))  # gov-python: allow — 动态加载的 docs_contract.read_text 已内建 encoding
    assert isinstance(out, str) and len(out) > 0


# ---------------------------------------------------------------------------
# L-1：生产路径裸 open() 已 with 化
# ---------------------------------------------------------------------------
def test_l1_no_bare_read_open():
    # 报告 §三 L-1 列举的生产路径：不得再有 `open(...).read()` 链式裸调用
    # （断言完整链式形态，避免误伤注释里提到的文件名或 with open(...) 新写法）
    checks = {
        "tools/gate/check_ps1_bom.py": ['open(path, "rb").read()'],
        "tools/gitee_release.py": [
            'open(token_file, encoding="utf-8", errors="replace").read()',
            'open(args.notes_file, encoding="utf-8").read()',
        ],
        "tools/repo_hygiene.py": [
            'open(cfg, "rb").read()', 'open(real, "rb").read()',
            'open(p, encoding="utf-8", errors="replace").read()',
        ],
    }
    for rel, needles in checks.items():
        src = _src(rel)
        for needle in needles:
            assert needle not in src, f"{rel} 仍存在裸 open: {needle}"
    # with 形态确实在位
    assert 'with open(path, "rb") as fh' in _src("tools/gate/check_ps1_bom.py")
    assert 'with open(cfg, "rb") as fh' in _src("tools/repo_hygiene.py")
    assert 'with open(real, "rb") as fh' in _src("tools/repo_hygiene.py")


# ---------------------------------------------------------------------------
# L-8：CRED_PATTERNS 命名常量 + enumerate
# ---------------------------------------------------------------------------
def test_l8_no_index_magic_number():
    src = _src("tools/repo_hygiene.py")
    assert "CRED_PATTERNS.index(pat)" not in src
    # 剥离注释行后再查魔数（注释里为解释而引用的旧写法不算残留）
    code_lines = [ln.split("#", 1)[0] for ln in src.splitlines()]
    code = "\n".join(code_lines)
    assert "CRED_PATTERNS[1]" not in code
    assert "if index == 1:" not in code
    assert "for index, pat in enumerate(CRED_PATTERNS):" in src
    assert "URL_CREDENTIAL_PATTERN_INDEX = 1" in src
    assert "if index == URL_CREDENTIAL_PATTERN_INDEX:" in src
    assert "CRED_PATTERNS[URL_CREDENTIAL_PATTERN_INDEX].search(d)" in src


def test_l8_constant_asserts_guard_reorder():
    """三个命名常量都有 assert 护栏，模式重排会立刻炸而非静默改判。"""
    src = _src("tools/repo_hygiene.py")
    for const in ("TOKEN_NAME_PATTERN_INDEX", "URL_QUERY_TOKEN_INDEX", "URL_CREDENTIAL_PATTERN_INDEX"):
        assert f"assert CRED_PATTERNS[{const}]" in src, f"{const} 缺 assert 护栏"


def test_l8_selfcheck_still_detects(tmp_path):
    """改动后仓库卫生 selfcheck 仍全绿（判据未失效）。"""
    r = subprocess.run([sys.executable, str(ROOT / "tools/repo_hygiene.py"), "--selfcheck"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-600:]


# ---------------------------------------------------------------------------
# L-6：五处 registry 分义注释
# ---------------------------------------------------------------------------
def test_l6_registry_disambiguation():
    cases = {
        "platform/packages/core/src/registry.js": "分义",
        "platform/harness/registry.mjs": "分义",
        "tools/gate/governance/registry.json": "Scope note (audit L-6)",
        "packages/allin-governance/src/allin_governance/init.py": "分义（审计 L-6）",
        "kernel/registry.py": "分义（审计 L-6）",
    }
    for rel, marker in cases.items():
        assert marker in _src(rel), f"{rel} 缺分义注释"
