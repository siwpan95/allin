# -*- coding: utf-8 -*-
"""配置树引导 —— allin 的统一挂载入口（docs/platform/preset/tools 经 cordis 编排）。

直接复用 3dworld 已转正、headless 验证通过的范式（host/tree.py）：
  - load_tree：ctx.plugin(Loader) → drain 几轮（等 isolate 子插件就绪）→ 配置树声明即挂载
  - _resolve_service_names + _validate_entry_names：服务短名白名单（安全边界）
  - await_ready / mount_tree：一行式引导 + 就绪等待

单一事实来源：本次挂哪些服务、各带什么 config，只由 configs/*.yml 声明一次。
"""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---- cordis 定位（vendor/cordis/src 经 .pth 暴露；换环境可设 CORDIS_SRC） ----
import kernel._cordis_locate as _cordis_locate  # noqa: E402

_cordis_locate.ensure()

import yaml  # noqa: E402
from cordis import Context, Loader  # noqa: E402

from kernel import registry  # noqa: E402
from kernel.registry import SYNTH_PREFIX  # noqa: E402

# 配置树目录（仓库资产，不随 wheel 分发；可用 ALLIN_CONFIGS 指向别处）
CONFIG_DIR = os.environ.get('ALLIN_CONFIGS') or os.path.join(ROOT, 'kernel', 'configs')

# 全部四大支柱就绪所需的最低服务集（CLI 引导与 headless 验证共用）
WANT_ALL = ('docs', 'platform', 'preset', 'tools')
ALLIN_CONFIG = 'cordis.allin.yml'


def config_path(name: str) -> str:
    return os.path.join(CONFIG_DIR, name)


# ---- 配置树 entry 白名单（安全：配置即代码）----------------------------------
# cordis 的 Loader 会把每条 entry 的 name 直接 import（见 vendor/cordis/src/cordis/loader.py）。
# 因此 entry name 等同于可执行代码，必须钉死在白名单内。
ALLOWED_NAME_PREFIXES = (
    f'{SYNTH_PREFIX}.',      # 服务短名（registry.SERVICES 封闭表）
    'allin.kernel.services.',  # 手写模块路径（仅限本仓库 services 包）
)
ALLOWED_NAME_EXACT = ('@cordisjs/plugin-group',)


def _resolve_service_names(data, path: str) -> int:
    """把 entry 里的服务短名解析成 cordis 能加载的模块路径，返回替换条数。"""
    if not isinstance(data, list):
        return 0
    n = 0
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        if registry.is_service(name):
            entry['name'] = registry.bind(name)
            n += 1
    return n


def _validate_entry_names(data, path: str) -> None:
    """拒绝白名单之外的 entry name（会被 cordis 当模块名导入）。"""
    if not isinstance(data, list):
        return
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        if not isinstance(name, str):
            continue
        if name in ALLOWED_NAME_EXACT or name.startswith(ALLOWED_NAME_PREFIXES):
            continue
        raise ValueError(
            f'配置树 {path} 第 {i} 条 entry 的 name={name!r} 不在白名单内 —— '
            f'entry name 会被 cordis 直接 import，等同于执行代码。'
            f'允许前缀：{ALLOWED_NAME_PREFIXES}；或使用 registry.py 里的服务短名'
            f'（{len(registry.SERVICES)} 个）。'
        )


async def load_tree(ctx, path: str):
    """用 Cordis 原生 Loader 把配置树挂载为服务图。

    ctx.plugin(Loader) 是异步的；Loader 会注册 isolate 等子插件，必须先 drain 几轮再
    root.update，否则首条 entry 会因 _isolate 未就绪而抛 KeyError。
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f'配置树不存在: {path}')
    await ctx.plugin(Loader)
    loader = ctx.loader
    for _ in range(16):
        await asyncio.sleep(0)
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    _resolve_service_names(data, path)
    _validate_entry_names(data, path)
    await loader.root.update(data)
    return loader


async def await_ready(ctx, loader, want=(), timeout: float = 8.0) -> bool:
    """等待配置树加载完成：want 中服务全部可达。"""
    want = tuple(want)
    dt = 1.0 / 60.0
    elapsed = 0.0
    while elapsed < timeout:
        await loader.await_()
        await asyncio.sleep(0)
        if all(getattr(ctx, n, None) is not None for n in want):
            return True
        elapsed += dt
    missing = [n for n in want if getattr(ctx, n, None) is None]
    raise RuntimeError(
        f"配置树未在 {timeout}s 内就绪；缺失服务: {missing}\n"
        '  提示：cordis 的 Loader 会**吞掉插件构造期异常** —— 某 entry 的模块 import 成功、'
        '但 Service.__init__ / __cordis_init__ 抛错时，这里只看到"服务不就绪"。\n'
        '  定位办法：手工 `import <entry name>` 一次看真实异常。'
    )


async def mount_tree(path: str, want=(), timeout: float = 8.0):
    """一行式引导：新建 Context、按配置树挂载、等到就绪，返回 ctx。"""
    ctx = Context()
    loader = await load_tree(ctx, path)
    if want:
        await await_ready(ctx, loader, want, timeout)
    return ctx


__all__ = [
    'CONFIG_DIR', 'WANT_ALL', 'ALLIN_CONFIG', 'config_path',
    'load_tree', 'await_ready', 'mount_tree',
]
