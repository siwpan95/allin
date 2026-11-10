# -*- coding: utf-8 -*-
"""P2 #21：docs_contract.py 纯函数单测（零 pytest 覆盖补齐）。

只测**不碰文件系统 / 不碰缓存**的纯函数：
``tok_key`` / ``strip_refs`` / ``cn2int`` / ``token2int`` / ``_in_code`` /
``_code_spans`` / ``_has_record_ref``。

隔离策略：docs_contract.py 用唯一模块名 + 显式路径加载（不占用任何裸名
``sys.modules`` 条目，不与同名第三方或仓内模块冲突）。这些目标函数都是纯字符串
比较，不触及 ``_numeric_tokens_from_text`` 的 lru_cache，故用例间无需清缓存。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "tools" / "gate" / "governance" / "runtime" / "docs_contract.py"


def _load_docs_contract():
    uid = "_p2b_tests_docs_contract"
    if uid in sys.modules:
        return sys.modules[uid]
    spec = importlib.util.spec_from_file_location(uid, DOC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uid] = mod
    spec.loader.exec_module(mod)
    return mod


dc = _load_docs_contract()


# ------------------------------------------------------------------ tok_key
@pytest.mark.parametrize("tok,expected", [
    ("一百一十", "110"),      # 中文序数 == 阿拉伯（INDEX REC-HO-03 的 §110）
    ("110", "110"),
    ("2.1.1", "2.1.1"),       # 多层小数是字符串键，不能 float
    ("2.0", "2"),             # 尾零归一
    ("2.10", "2.1"),
    ("3.50", "3.5"),
    ("9", "9"),
])
def test_tok_key_normalizes(tok, expected):
    assert dc.tok_key(tok) == expected


@pytest.mark.parametrize("tok", [
    "20261031",              # 时间戳形态不是节号（8 位整数段）
    "20261031173800",        # 14 位时间戳
    "abc",                   # 非数字、非中文序数
    "2.x",
])
def test_tok_key_rejects_non_section(tok):
    assert dc.tok_key(tok) is None


def test_tok_key_empty_string_boundary():
    # cn2int("") 返回 0（total+num），故 tok_key("") 归一为 "0"；固化此边界，
    # 调用方（D14）依赖「不可解析返回 None」时应对空串另行过滤，不在此纯函数内兜底。
    assert dc.tok_key("") == "0"


# ------------------------------------------------------------------ cn2int
@pytest.mark.parametrize("s,expected", [
    ("九十四", 94),
    ("一百一十一", 111),
    ("一百一十", 110),
    ("十二", 12),            # 十位前无数 ⇒ 视作 1
    ("一千", 1000),
    ("五", 5),
])
def test_cn2int(s, expected):
    assert dc.cn2int(s) == expected


@pytest.mark.parametrize("s", ["abc", "2.1.1", "20261031", "一百二〇", "-", ""])
def test_cn2int_rejects_non_ordinal(s):
    # 注意 cn2int("") 返回 0（total+num），不是 None —— 只断言真正含非法字符的输入。
    if s == "":
        assert dc.cn2int(s) == 0
    else:
        assert dc.cn2int(s) is None


# ---------------------------------------------------------------- token2int
@pytest.mark.parametrize("tok,expected", [
    ("94", 94),
    ("一百一十一", 111),
    ("十二", 12),
])
def test_token2int(tok, expected):
    assert dc.token2int(tok) == expected


@pytest.mark.parametrize("tok", [
    "20261031",              # 时间戳拒绝（与 tok_key 同一口径）
    "20261031173800",
    "2.1.1",                 # 小节号返回 None
    "abc",
])
def test_token2int_rejects(tok):
    assert dc.token2int(tok) is None


# ---------------------------------------------------------------- strip_refs
def test_strip_refs_removes_arabic_references():
    assert dc.strip_refs("x §2 y") == "x  y"


def test_strip_refs_removes_chinese_references():
    # 连写引用 §一~§五十八：两个引用都被剥离，只留连接符
    assert dc.strip_refs("§一~§五十八") == "~"


def test_strip_refs_keeps_plain_text():
    assert dc.strip_refs("没有引用的正文") == "没有引用的正文"


# ------------------------------------------------------------------ _in_code
def test_in_code_inline_span():
    text = "见 `§2` 此处"
    pos = text.index("§2")
    assert dc._in_code(text, pos) is True
    # 同一段文字里裸 §3（不在反引号内）不判定为代码
    text2 = "见 §3 此处"
    assert dc._in_code(text2, text2.index("§3")) is False


def test_in_code_fence_block():
    text = "开头\n```md\n§2 在栅栏里\n```\n结尾 §2"
    inside = text.index("§2")
    outside = text.rindex("§2")
    assert dc._in_code(text, inside) is True
    assert dc._in_code(text, outside) is False


# --------------------------------------------------------------- _code_spans
def test_code_spans_pairs():
    assert list(dc._code_spans("a `x` b `y` c")) == ["x", "y"]


def test_code_spans_none():
    assert list(dc._code_spans("no code here")) == []


# ------------------------------------------------------------ _has_record_ref
def test_has_record_ref_via_link():
    assert dc._has_record_ref("证据见 [记录](记录/2026-11.md)") is True


def test_has_record_ref_via_backtick_path():
    assert dc._has_record_ref("证据见 `记录/2026-09.md`") is True


@pytest.mark.parametrize("text", [
    "普通正文 §2",
    "见 docs/记录 但没写成指针",   # 无链接、无反引号跨度
    "",
])
def test_has_record_ref_negative(text):
    assert dc._has_record_ref(text) is False
