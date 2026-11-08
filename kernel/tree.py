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

# 配置树目录（仓库资产，不随 wheel 分发）。
# 安全：ALLIN_CONFIGS 只能指向仓内目录 —— 配置树等同可执行代码（见下方白名单说明），
# 允许它指向任意外部路径就等于把「换掉整棵服务图」的能力交给环境变量。
def _safe_config_dir() -> str:
    default = os.path.join(ROOT, 'kernel', 'configs')
    raw = os.environ.get('ALLIN_CONFIGS')
    if not raw:
        return default
    candidate = os.path.realpath(raw)
    root = os.path.realpath(ROOT)
    try:
        inside = os.path.commonpath((candidate, root)) == root
    except ValueError:             # 不同盘符：commonpath 直接抛
        inside = False
    if not inside or not os.path.isdir(candidate):
        raise RuntimeError(
            f'ALLIN_CONFIGS 必须指向仓内已存在的目录（当前={raw!r}，仓根={root!r}）——'
            '配置树会被 cordis 直接 import，拒绝外部路径以防服务图劫持。'
        )
    return candidate


CONFIG_DIR = _safe_config_dir()

ALLIN_CONFIG = 'cordis.allin.yml'


def config_path(name: str) -> str:
    return os.path.join(CONFIG_DIR, name)


def _want_all_from_config() -> tuple:
    """支柱清单唯一数据源（ADR-0006，2026-11-04 工程审查 A1 的收口实现）。

    此前"四大支柱"这一份事实在 kernel/registry.py:SERVICES、本文件的 WANT_ALL、
    configs/cordis.allin.yml 三处手抄 —— 新增支柱要改 3 个文件，且漂移无报警。
    现在：WANT_ALL 从 yml 的 entry id **推导**，并 fail-loud 校验 ids ⊆ registry.SERVICES
    （yml 里写了白名单外的短名 = import 即红，而不是挂载时才炸）。
    新增第五支柱的路径收敛为：① registry.py 加短名 → ② services/ 加实现 → ③ yml 加 entry。
    """
    try:
        with open(config_path(ALLIN_CONFIG), encoding='utf-8') as fh:
            data = yaml.safe_load(fh) or []
    except FileNotFoundError:
        # 配置缺席（新装环境 / ALLIN_CONFIGS 指向空目录）时的出厂口径
        return ('docs', 'platform', 'preset', 'tools')
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        # 2026-11-08 深度审核：YAML 语法错、BOM/GBK 解码错、权限错此前让
        # `import kernel.tree` 崩在导入期，连 `allin --help` 都不可用。
        raise RuntimeError(
            f'{ALLIN_CONFIG} 读取或解析失败（{exc.__class__.__name__}: {exc}）——'
            '请检查 YAML 语法与文件编码（应为 UTF-8 无 BOM）。'
        ) from exc
    ids = tuple(e['id'] for e in data if isinstance(e, dict) and e.get('id'))
    unknown = [i for i in ids if i not in registry.SERVICES]
    if unknown:
        raise RuntimeError(
            f'{ALLIN_CONFIG} 含 registry.SERVICES 白名单之外的 entry id：{unknown}'
            f'（允许：{sorted(registry.SERVICES)}）——'
            '新增支柱须先改 kernel/registry.py（封闭表）+ kernel/services/ 实现，再回 yml 登记'
        )
    if not ids:
        raise RuntimeError(f'{ALLIN_CONFIG} 没有任何带 id 的 entry，无法推导支柱清单')
    return ids


WANT_ALL = _want_all_from_config()


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


def _reject_js_expr(value, path: str, where: str) -> None:
    """拒绝配置表达式：cordis 的 interpolate() 会对 __jsExpr 执行裸 eval()。"""
    if isinstance(value, dict):
        if '__jsExpr' in value:
            raise ValueError(
                f'配置树 {path} 的 {where} 含 __jsExpr —— cordis 的 evaluate() 会对其执行 '
                'eval(expr, {"ctx": ctx})，配置不得携带可执行表达式。'
            )
        for key, item in value.items():
            _reject_js_expr(item, path, f'{where}.{key}')
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _reject_js_expr(item, path, f'{where}[{i}]')


def _validate_entries(data, path: str, where: str) -> None:
    """递归校验所有层级的 entry name。

    Group 的 config 是嵌套 entry 列表，cordis 经
    EntryGroup.update → Entry._init → importlib.import_module 递归加载；
    只校验顶层等于把白名单整体绕过（2026-11-08 深度审核 P0-1）。
    """
    if not isinstance(data, (list, tuple)):
        return
    for i, entry in enumerate(data):
        loc = f'{where}[{i}]'
        if not isinstance(entry, dict):
            continue
        name = entry.get('name')
        if isinstance(name, str) and not (
            name in ALLOWED_NAME_EXACT or name.startswith(ALLOWED_NAME_PREFIXES)
        ):
            raise ValueError(
                f'配置树 {path} 的 {loc} name={name!r} 不在白名单内 —— '
                f'entry name 会被 cordis 直接 import，等同于执行代码。'
                f'允许前缀：{ALLOWED_NAME_PREFIXES}；精确放行：{ALLOWED_NAME_EXACT}；'
                f'或使用 registry.py 里的服务短名（{len(registry.SERVICES)} 个）。'
            )
        _reject_js_expr(entry, path, loc)
        config = entry.get('config')
        if isinstance(config, (list, tuple)):
            _validate_entries(config, path, f'{loc}.config')


def _validate_entry_names(data, path: str) -> None:
    """拒绝白名单之外的 entry name（会被 cordis 当模块名导入）。"""
    _validate_entries(data, path, 'root')


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
    import time
    want = tuple(want)
    # 2026-11-08 深度审核：原实现用 elapsed += 1/60 配 sleep(0)，480 次循环
    # 瞬间跑完，声称的 8s 超时根本不成立。改用单调时钟的实际墙钟。
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await loader.await_()
        await asyncio.sleep(0.01)
        if all(getattr(ctx, n, None) is not None for n in want):
            return True
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
