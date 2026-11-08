# -*- coding: utf-8 -*-
"""B1 覆盖率补充：kernel.tree 的纯函数（与 test_kernel_want_all.py 互补）。

test_kernel_want_all.py 已覆盖 _want_all_from_config 的导入期推导 + 白名单越界 fail-loud。
本文件补它没走的：

1. _resolve_service_names：服务短名解析成合成模块路径，返回替换条数；
2. _validate_entry_names：白名单内放行、白名单外抛 ValueError（配置即代码安全边界）；
3. _want_all_from_config 的两个边界分支：
   - 配置文件缺失 → 返回出厂四元组（不抛）；
   - 配置无任何带 id 的 entry → RuntimeError。

跑法：python -m pytest kernel/tests/test_tree_coverage.py -q
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

from kernel import tree
from kernel.tree import (
    _resolve_service_names,
    _validate_entry_names,
    _want_all_from_config,
)


def test_resolve_service_names_rewrites_short_names_and_counts():
    """短名命中 registry.SERVICES 才解析；非服务名原样保留；返回替换条数。"""
    data = [
        {'name': 'docs'},
        {'name': 'allin.kernel.services.something'},  # 合法手写路径，不解析
        {'name': 'platform'},
        {'name': 'not-a-service'},  # 不在白名单，不解析
    ]
    n = _resolve_service_names(data, '<test>')
    assert n == 2
    assert data[0]['name'] == '_allinsrv.docs'
    assert data[2]['name'] == '_allinsrv.platform'
    # 非服务名保持原值
    assert data[1]['name'] == 'allin.kernel.services.something'
    assert data[3]['name'] == 'not-a-service'


def test_resolve_service_names_non_list_returns_zero():
    assert _resolve_service_names({'name': 'docs'}, '<test>') == 0
    assert _resolve_service_names(None, '<test>') == 0


def test_validate_entry_names_allows_synth_and_handwritten_and_exact():
    """白名单内的三类 name 都不应抛。"""
    data = [
        {'name': '_allinsrv.docs'},
        {'name': 'allin.kernel.services.status_service'},
        {'name': '@cordisjs/plugin-group'},
    ]
    _validate_entry_names(data, '<test>')  # 不抛即通过


def test_validate_entry_names_rejects_out_of_whitelist():
    """白名单外的 name 会被 cordis 当模块 import —— 等同执行代码，必须拒绝。"""
    data = [{'name': 'evil.os.system'}]
    with pytest.raises(ValueError):
        _validate_entry_names(data, '<test>')


def test_validate_entry_names_non_list_is_noop():
    _validate_entry_names({'name': 'evil'}, '<test>')  # 不抛


def test_want_all_falls_back_to_default_when_config_missing():
    """配置树缺席（新装 / ALLIN_CONFIGS 指向空目录）：返回出厂四元组，而非抛。"""
    with tempfile.TemporaryDirectory() as tmp:
        missing = os.path.join(tmp, 'does-not-exist.yml')
        orig = tree.config_path
        tree.config_path = lambda name: missing
        try:
            result = _want_all_from_config()
        finally:
            tree.config_path = orig
    assert result == ('docs', 'platform', 'preset', 'tools')


def test_want_all_raises_when_no_id_entries():
    """配置存在但没有任何带 id 的 entry：必须 RuntimeError（而不是返回空清单）。"""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'cordis.allin.yml')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('- name: docs\n')  # 有 name 但无 id 字段
        orig = tree.config_path
        tree.config_path = lambda name: p
        try:
            with pytest.raises(RuntimeError):
                _want_all_from_config()
        finally:
            tree.config_path = orig
