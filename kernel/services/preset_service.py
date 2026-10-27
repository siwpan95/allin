# -*- coding: utf-8 -*-
"""preset 支柱服务：统一调度 allin/preset 的治理模式（组合包 / 装配清单）。

被 cordis 内核挂载后，经 ``ctx.preset`` 访问。preset 是「治理模式」资产，本服务先做
只读盘点（list / show），apply 默认只打印将要执行的动作、**不自动落地**，避免误改治理态。
"""
from __future__ import annotations

import os

from kernel.cordis import Service

from kernel.paths import PRESET_DIR


class PresetService(Service):
    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'preset')

    def __cordis_init__(self):
        return None

    # ---- 列出全部 preset 组合包 ----
    def list(self):
        if not os.path.isdir(PRESET_DIR):
            print('（preset 目录不存在）')
            return None
        for name in sorted(os.listdir(PRESET_DIR)):
            full = os.path.join(PRESET_DIR, name)
            kind = '目录' if os.path.isdir(full) else '文件'
            print(f'[{kind}] {name}')
        return None

    # ---- 查看某个 preset 的内容（只读）----
    def show(self, name: str):
        path = os.path.join(PRESET_DIR, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f'preset 不存在: {path}')
        if os.path.isdir(path):
            for f in sorted(os.listdir(path)):
                print(f'  {f}')
        else:
            with open(path, 'r', encoding='utf-8') as fh:
                print(fh.read())
        return None

    # ---- 应用 preset：默认 dry-run（只打印动作），dry_run=False 才落地 ----
    def apply(self, name: str, dry_run: bool = True):
        path = os.path.join(PRESET_DIR, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f'preset 不存在: {path}')
        verb = '【dry-run】将应用' if dry_run else '应用'
        print(f'{verb} preset: {name}  ({path})')
        # TODO: 解析 preset 组合包并落到 registry / 工具调度（按具体格式实现）
        return None
