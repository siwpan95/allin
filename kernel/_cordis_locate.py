# -*- coding: utf-8 -*-
"""vendored cordis 的统一定位入口（allin 适配版）。

背景与完整说明见 vendor/cordis/VENDOR.md 与 3dworld 的同源实现。
把「定位 cordis」收口到一处：① 已安装 / 已被 .pth 暴露；
② 环境变量 CORDIS_SRC（需通过 isdir 校验，防目录注入）；③ 仓库内 vendor/cordis/src。

安全：仓库内 vendor 目录由 __file__ 绝对推导，不接受外部输入。
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys

__all__ = ['ensure', 'locate', 'repo_root', 'vendor_dir']

_VENDOR_PARTS = ('vendor', 'cordis', 'src')


def repo_root() -> str:
    """allin 仓库根（本文件在 allin/kernel/ 下，上溯两层）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vendor_dir() -> str:
    """仓库内 vendored cordis 的源码目录（vendor/cordis/src）。"""
    return os.path.join(repo_root(), *_VENDOR_PARTS)


def _find_spec():
    try:
        return importlib.util.find_spec('cordis')
    except (ImportError, ValueError, AttributeError):
        return None


def locate() -> str | None:
    """返回可用的 cordis 源码目录；都不存在时返回 None。"""
    env = os.environ.get('CORDIS_SRC')
    if env and os.path.isdir(env) and os.path.isdir(os.path.join(env, 'cordis')):
        return env
    v = vendor_dir()
    if os.path.isdir(v) and os.path.isdir(os.path.join(v, 'cordis')):
        return v
    return None


def _import_or_raise(where: str, strict: bool) -> bool:
    try:
        importlib.import_module('cordis')
        return True
    except (ImportError, TypeError) as exc:
        if not strict:
            return False
        raise ImportError(
            f'[cordis] cordis 已定位到 {where}，但导入失败 —— 几乎总是它自身的依赖缺失'
            f'（PyYAML / watchdog）：{exc.__class__.__name__}: {exc}。'
            f'请在 allin 的 venv 执行 pip install pyyaml watchdog。'
            f'提示：缺 watchdog 的典型症状是 "TypeError: NoneType takes no arguments"。'
        ) from exc


def ensure(strict: bool = True) -> bool:
    """确保 cordis 可被 import；必要时把 vendored 源码目录加入 sys.path。"""
    if _find_spec() is not None:
        return _import_or_raise('已安装 / 已被 .pth 暴露', strict)
    d = locate()
    if d is not None:
        if d not in sys.path:
            sys.path.insert(0, d)
        if _find_spec() is not None:
            return _import_or_raise(d, strict)
    if not strict:
        return False
    raise ImportError(
        f'[cordis] 未找到 cordis 包。已尝试 CORDIS_SRC={os.environ.get("CORDIS_SRC")!r} '
        f'与仓库内 {vendor_dir()}。安装方式见 vendor/cordis/VENDOR.md。'
    )
