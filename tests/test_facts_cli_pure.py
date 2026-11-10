# -*- coding: utf-8 -*-
"""P2 #21：tools/facts/cli.py 纯函数单测（零 pytest 覆盖补齐）。

只测不触文件 / 不触 DB 的纯函数：
``_is_type`` / ``validate_node`` / ``_flatten`` / ``expected_hash``。

隔离策略（**关键，照抄 test_p2_convergence.py**）
--------------------------------------------------
仓内有裸名 ``import cli`` 的两个模块（tools/facts/cli.py 与 tools/repocheck/cli.py），
pytest.ini 的 testpaths 同进程收集 kernel/tests、packages/allin-governance/tests、
tools/repocheck、tests。若在主 pytest 进程顶层 ``import cli`` 或顶层
``sys.path.insert(0, tools/facts)``，会让 governance 的 ``import cli`` 拿到错的 facts cli
（``main()`` 也返回 0 并打印 SCHEMA OK ⇒ 静默假绿），且 tools/repocheck/test_scanner.py
因缺 ``PROFILES`` 崩溃。

因此这里采用隔离方式 (a) **子进程**：每一项断言都放进 ``sys.executable -c`` 的全新解释器，
只有该子进程把 ``tools/facts`` 置于 sys.path 首位再 ``import cli``；主进程断言其
returncode / stdout。主进程**从不** import cli，也不改全局 sys.path。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS = ROOT / "tools" / "facts"

# 只有子进程才注入 tools/facts —— 主进程 sys.path 保持原样
_FACTS_HEADER = "import sys\nsys.path.insert(0, %r)\n" % FACTS.as_posix()


def _py(script: str, timeout: int = 90):
    return subprocess.run(
        [sys.executable, "-c", _FACTS_HEADER + script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), timeout=timeout,
    )


# ------------------------------------------------------------------ _is_type
_S_IS_TYPE = """
import cli
# bool 是 int 子类，但语义上既不是 integer 也不是 number
assert cli._is_type(1, "integer") is True
assert cli._is_type(True, "integer") is False
assert cli._is_type(False, "integer") is False
assert cli._is_type(3.5, "number") is True
assert cli._is_type(7, "number") is True
assert cli._is_type(True, "number") is False
assert cli._is_type(True, "boolean") is True
assert cli._is_type(1, "boolean") is False
assert cli._is_type({}, "object") is True
assert cli._is_type([], "array") is True
assert cli._is_type("x", "string") is True
assert cli._is_type(None, "null") is True
assert cli._is_type(0, "string") is False
# 未知 type 默认放行（schema 未声明类型时不应误拦）
assert cli._is_type(123, "weird_type") is True
print("IS_TYPE_OK")
"""


def test_is_type_bool_is_not_integer_or_number():
    r = _py(_S_IS_TYPE)
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])
    assert "IS_TYPE_OK" in r.stdout


# -------------------------------------------------------------- validate_node
_S_VALIDATE = """
import cli
S, v = cli.SchemaError, cli.validate_node
base = {"type": "object", "required": ["id"],
        "properties": {"id": {"type": "integer"}}, "additionalProperties": False}
# 合法节点通过
v({"id": 1}, base, base)
# 聚合断言：非法输入必须抛 SchemaError 且带可读诊断
def must_fail(label, node, schema, root=None):
    try:
        v(node, schema, root if root is not None else schema)
    except S as e:
        assert str(e), label + " 缺诊断信息"
    else:
        raise AssertionError(label + " 未抛 SchemaError（判绿风险）")
must_fail("缺必填", {}, base)
enum = {"type": "object", "properties": {"s": {"enum": ["a", "b"]}}}
must_fail("枚举违约", {"s": "c"}, enum)
must_fail("未声明字段", {"id": 1, "extra": 2}, base)
must_fail("类型错", {"id": "x"}, base)
pattern = {"type": "string", "pattern": "^v[0-9]+$"}
must_fail("正则不符", "abc", pattern)
minitems = {"type": "array", "minItems": 2}
must_fail("少于 minItems", [1], minitems)
# $ref 解析：有效引用解析后，节点违反目标 schema ⇒ SchemaError
root = {"defs": {"pos": {"type": "integer", "minimum": 0}}}
must_fail("引用目标约束违约", -1, {"$ref": "#/defs/pos"}, root)
# 合法引用解析后通过
v(5, {"$ref": "#/defs/pos"}, root)
print("VALIDATE_OK")
"""


def test_validate_node_accepts_valid_and_rejects_invalid():
    r = _py(_S_VALIDATE)
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])
    assert "VALIDATE_OK" in r.stdout


# ------------------------------------------------------------------- _flatten
_S_FLATTEN = """
import cli
# sort_keys=True ⇒ 与入参键顺序无关，输出稳定
assert cli._flatten({"b": 2, "a": 1}) == cli._flatten({"a": 1, "b": 2})
assert cli._flatten({"b": 2, "a": 1}) == '{"a": 1, "b": 2}'
# ensure_ascii=False ⇒ 中文原样保留（若 True 会变成 \\uXXXX）
assert cli._flatten({"名": "值"}) == '{"名": "值"}'
print("FLATTEN_OK")
"""


def test_flatten_is_stable_and_keeps_unicode():
    r = _py(_S_FLATTEN)
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])
    assert "FLATTEN_OK" in r.stdout


# --------------------------------------------------------------- expected_hash
_S_HASH = """
import re
import cli
m = {"machine_id": "m1", "hostname": "h", "status": "current",
     "observed_at": "2026-01-01", "evidence_ref": "e"}
def doc(value):
    return {
        "machines": [m],
        "facts": [{"fact_id": "f1", "subject": "s", "attribute": "a", "value": value,
                   "scope": "machine", "status": "current", "valid_from": "2026-01-01",
                   "valid_to": None, "observed_at": "2026-01-01", "evidence_ref": "e",
                   "machine_id": "m1"}],
    }
h1 = cli.expected_hash(doc("old"), "m1")
assert re.fullmatch(r"[0-9a-f]{16}", h1), h1
assert h1 == cli.expected_hash(doc("old"), "m1"), "同输入必须确定性一致"
assert h1 != cli.expected_hash(doc("new"), "m1"), "事实值变化必须改变哈希"
print("HASH_OK")
"""


def test_expected_hash_is_16_hex_deterministic_and_sensitive():
    r = _py(_S_HASH)
    assert r.returncode == 0, (r.stdout[-600:], r.stderr[-600:])
    assert "HASH_OK" in r.stdout
