# -*- coding: utf-8 -*-
"""preset 支柱服务：统一调度 allin/preset 的治理模式（组合包 / 装配清单）。

被 cordis 内核挂载后，经 ``ctx.preset`` 访问。preset 是「治理模式」资产，本服务先做
只读盘点（list / show），apply 默认只打印将要执行的动作、**不自动落地**，避免误改治理态。
"""
from __future__ import annotations

import os
import sys

from kernel.cordis import Service

from kernel.paths import PRESET_DIR


def _resolve_preset(name: str) -> str:
    """把 name 钉死在 PRESET_DIR 内的一级条目，拒绝 ../ 与绝对路径。

    2026-11-08 深度审核：`show(name)` 原样 join 后 open().read()，`preset show
    ..\\..\\.env` 可读仓内任意文件（含凭据）。preset 名是标识符，不是路径。
    """
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or os.path.isabs(name) or '/' in name or '\\' in name
            or '\x00' in name):
        raise ValueError(f'非法 preset 名：{name!r}（只允许 PRESET_DIR 下的一级名称）')
    base = os.path.realpath(PRESET_DIR)
    path = os.path.realpath(os.path.join(base, name))
    try:
        inside = os.path.commonpath((path, base)) == base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f'preset 名越出 PRESET_DIR：{name!r}')
    return path


class PresetService(Service):
    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'preset')

    def __cordis_init__(self):
        return None

    # ---- 列出全部 preset 组合包 ----
    def list(self):
        if not os.path.isdir(PRESET_DIR):
            # 2026-11-10 深度审计 H-4：目录不存在是「环境不具备」，不是「成功列出 0 个」。
            # 此前 return None 被 CLI 映射成 exit 0（preset list 目录缺失仍判绿）。
            # 与 docs_service.aliases()/index() 的既有修法统一，返回环境错误码 3。
            print(f'（preset 目录不存在：{PRESET_DIR}）', file=sys.stderr)
            return 3
        for name in sorted(os.listdir(PRESET_DIR)):
            full = os.path.join(PRESET_DIR, name)
            kind = '目录' if os.path.isdir(full) else '文件'
            print(f'[{kind}] {name}')
        return None

    # ---- 查看某个 preset 的内容（只读）----
    def show(self, name: str):
        path = _resolve_preset(name)
        if not os.path.exists(path):
            raise FileNotFoundError(f'preset 不存在: {path}')
        if os.path.isdir(path):
            for f in sorted(os.listdir(path)):
                print(f'  {f}')
        else:
            with open(path, 'r', encoding='utf-8') as fh:
                print(fh.read())
        return None

    # ---- 应用 preset：dry-run（默认，只读打印动作）vs 真实落地 ----
    # 设计纪律（见模块 docstring）：apply 默认不自动落地，避免误改治理态。
    # 真实落地（dry_run=False，即 CLI --yes）的解析/落盘逻辑尚未实现；按仓内
    # fail-loud 纪律，绝不静默假装成功——返回 ok:False + 明确原因，交由 CLI 映射
    # 非零退出码。WJ-01 整改：消除「--yes 零动作」的假绿（此前 dry_run=False
    # 与 dry_run=True 行为完全一致、退出码恒 0）。
    def apply(self, name: str, dry_run: bool = True) -> dict:
        path = _resolve_preset(name)
        if not os.path.exists(path):
            raise FileNotFoundError(f'preset 不存在: {path}')
        verb = '【dry-run】将应用' if dry_run else '应用'
        print(f'{verb} preset: {name}  ({path})')
        if dry_run:
            # 只读盘点将要执行的动作，不落盘（设计如此）。
            return {
                'ok': True,
                'applied': False,
                'dry_run': True,
                'name': name,
                'path': path,
                'reason': 'dry-run 仅打印动作，不落盘（避免误改治理态）',
            }
        # dry_run=False（CLI --yes）：真实落地逻辑尚未实现，按 fail-loud 返回明确未实现，
        # 交由 CLI 映射为非零退出码，绝不静默返回 None 假装成功（WJ-01）。
        return {
            'ok': False,
            'applied': False,
            'dry_run': False,
            'name': name,
            'path': path,
            'reason': 'preset 真实落地逻辑尚未实现（WJ-01）：--yes 不会静默改治理态，'
                      '请先实现解析/落盘后再启用',
        }
