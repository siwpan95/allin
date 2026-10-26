# -*- coding: utf-8 -*-
"""allin 服务注册表：服务短名 → 实现类（封闭白名单）。

仿 3dworld 的 host/registry.py：yml 里写服务短名（docs / platform / preset / tools），
由 tree.load_tree 在挂载前解析成实现模块。短名必须命中本表才能挂载，杜绝「配置即代码」
任意 import 的评审绕过风险（cordis 的 Loader 会把 entry 的 name 直接 import）。

新增一个被内核调度的支柱/工具，只改这张表 + 对应 services/*.py，不再加样板文件。
"""
from __future__ import annotations

import importlib
import sys
import types

__all__ = ['SERVICES', 'SYNTH_PREFIX', 'bind', 'is_service', 'service_names']

#: 合成宿主模块的顶层包名（挂进 sys.modules，只含 default）
SYNTH_PREFIX = '_allinsrv'

#: 短名 → '真实模块路径:实现类名'
SERVICES = {
    # ---- allin 四大支柱（docs / platform / preset / tools）----
    'docs': 'kernel.services.docs_service:DocsService',
    'platform': 'kernel.services.platform_service:PlatformService',
    'preset': 'kernel.services.preset_service:PresetService',
    'tools': 'kernel.services.tools_service:ToolService',
}


def is_service(name) -> bool:
    return isinstance(name, str) and name in SERVICES


def service_names():
    return tuple(sorted(SERVICES))


def bind(name: str) -> str:
    """把服务短名绑定成 cordis 能加载的模块路径，返回该路径。

    为每个短名创建一个只含 default 的宿主模块（_allinsrv.<短名>）并登记进 sys.modules，
    使「短名 → 实现类」这一映射可被子 cordis Loader 当作普通模块导入。幂等。
    """
    if name not in SERVICES:
        raise KeyError(f'未知服务短名：{name!r}（见 kernel/registry.py 的 SERVICES）')
    full = f'{SYNTH_PREFIX}.{name}'
    if full in sys.modules:
        return full
    module_path, attr = SERVICES[name].split(':', 1)
    impl = getattr(importlib.import_module(module_path), attr)
    mod = types.ModuleType(full)
    mod.default = impl
    mod.__doc__ = f'服务 {name!r} 的宿主模块（allin 生成；实现：{module_path}:{attr}）'
    sys.modules[full] = mod
    return full
