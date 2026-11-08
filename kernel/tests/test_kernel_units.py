# -*- coding: utf-8 -*-
"""B1 覆盖率补充：registry / _cordis_locate / platform_service 的纯逻辑单测。

此前这三个模块在覆盖率报告里缺口最大（registry 36% / _cordis_locate 67% /
platform_service 52%），且多为无副作用的纯函数或只读目录的小方法，是低风险高收益目标。
跑法：pytest kernel/tests/test_kernel_units.py
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

from kernel import _cordis_locate
from kernel import registry


# ---------------------------------------------------------------- registry

def test_registry_is_service_true_and_false():
    assert registry.is_service('docs') is True
    assert registry.is_service('platform') is True
    assert registry.is_service('status') is True
    assert registry.is_service('unknown') is False
    assert registry.is_service(123) is False  # 非 str 必须 False


def test_registry_service_names_sorted_tuple_and_complete():
    names = registry.service_names()
    assert isinstance(names, tuple)
    assert names == tuple(sorted(names))
    assert {'docs', 'platform', 'preset', 'tools', 'status'}.issubset(set(names))


def test_registry_bind_known_returns_synth_module_and_idempotent():
    full = registry.bind('docs')
    assert full == '_allinsrv.docs'
    assert full in sys.modules
    # 幂等：再次 bind 返回同一模块路径，不重复建
    assert registry.bind('docs') == full


def test_registry_bind_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        registry.bind('does-not-exist')


# ---------------------------------------------------------------- _cordis_locate

def test_repo_root_and_vendor_dir_derived_from_file():
    root = _cordis_locate.repo_root()
    assert os.path.isabs(root)
    assert os.path.isdir(root)
    v = _cordis_locate.vendor_dir()
    assert v.endswith(os.path.join('vendor', 'cordis', 'src'))


def test_locate_prefers_valid_cordis_src_env(monkeypatch):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'cordis'))
    monkeypatch.setenv('CORDIS_SRC', d)
    # 2026-11-08 P0-1：仓外 cordis 源需要显式 opt-in（受评审的部署决策）。
    monkeypatch.setenv('ALLIN_ALLOW_EXTERNAL_CORDIS', '1')
    assert _cordis_locate.locate() == d


def test_locate_rejects_external_cordis_src_without_optin(monkeypatch):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'cordis'))
    monkeypatch.setenv('CORDIS_SRC', d)
    monkeypatch.delenv('ALLIN_ALLOW_EXTERNAL_CORDIS', raising=False)
    with pytest.raises(RuntimeError):
        _cordis_locate.locate()


def test_locate_invalid_cordis_src_falls_back(monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv('CORDIS_SRC', os.path.join(d, 'nope'))
    res = _cordis_locate.locate()
    assert res is None or os.path.isdir(res)  # 不抛，回退 vendor 或 None


def test_locate_no_env_does_not_raise(monkeypatch):
    monkeypatch.delenv('CORDIS_SRC', raising=False)
    res = _cordis_locate.locate()
    assert res is None or os.path.isdir(res)


def test_ensure_non_strict_returns_bool_without_raising(monkeypatch):
    # CORDIS_SRC 清空；即便 vendor 存在导致真实 import，ensure(False) 也只返 bool 不抛
    monkeypatch.delenv('CORDIS_SRC', raising=False)
    res = _cordis_locate.ensure(strict=False)
    assert isinstance(res, bool)


# ---------------------------------------------------------------- platform_service

class _FakeReflect:
    def provide(self, name, instance, check):
        return None


class _FakeCtx:
    reflect = _FakeReflect()


def test_platform_service_instantiates():
    from kernel.services import platform_service
    svc = platform_service.PlatformService(ctx=_FakeCtx(), config=None)
    assert svc is not None
    assert svc.name == 'platform'


def test_platform_registry_count_reads_real_registry_dir(capsys):
    from kernel.services import platform_service
    svc = platform_service.PlatformService(ctx=_FakeCtx(), config=None)
    rc = svc.registry_count()
    # registry_count 约定：数量是「输出」不是退出码，必须返回 0（否则会被当 exit code 误用）
    assert rc == 0
    out = capsys.readouterr().out
    assert 'registry 项目条目' in out
