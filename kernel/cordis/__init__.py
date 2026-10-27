# -*- coding: utf-8 -*-
"""kernel 对 vendored Cordis 的稳定重导出入口。

真实 Cordis 源码在仓库内 ``vendor/cordis/src``（见 ``kernel/_cordis_locate``）。
本包仅作静态可解析的重导出层：让 ``cordis`` 成为 kernel 项目内的模块
（满足 repocheck rule 6 的「内部模块」判定），并把服务所需的符号统一从这里暴露，
避免各 service 直接 ``from cordis import Service`` 触发的 import 断裂误报。

运行时仍由 ``_cordis_locate.ensure()`` 把 vendored 源码目录加入 sys.path，
因此本层导出的 ``Service`` 与 vendored ``cordis.Service`` 是同一个类。
"""
from __future__ import annotations

from kernel._cordis_locate import ensure

# 确保 vendored cordis 已可被 import（必要时把 vendor/cordis/src 加入 sys.path）
ensure(strict=False)

import importlib

_cordis = importlib.import_module("cordis")

Service = _cordis.Service

__all__ = ["Service"]
