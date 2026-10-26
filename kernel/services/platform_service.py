# -*- coding: utf-8 -*-
"""platform 支柱服务：统一调度 allin/platform 的治理与门禁（registry 校验 / check:repos）。

被 cordis 内核挂载后，经 ``ctx.platform`` 访问。底层工具是 Node（registry.js / check_repos.mjs），
本服务用 node 子进程封装，统一入口。
"""
from __future__ import annotations

import os
import subprocess

from cordis import Service

from kernel.paths import PLATFORM_DIR, ROOT


def _node(script: str, *args, cwd=PLATFORM_DIR):
    cmd = ['node', script] + list(args)
    return subprocess.run(cmd, cwd=cwd)


class PlatformService(Service):
    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'platform')

    def __cordis_init__(self):
        return None

    # ---- npm run check:repos：本地路径 ⇄ 远端存活 ⇄ 目录/仓名错位 三向核对 ----
    def check_repos(self):
        return subprocess.run(['npm', 'run', 'check:repos'], cwd=PLATFORM_DIR, shell=True)

    # ---- 直接跑某个 mjs 脚本 ----
    def run_mjs(self, script: str, *args):
        return _node(script, *args)

    # ---- 列出 registry 项目数 ----
    def registry_count(self):
        reg_dir = os.path.join(PLATFORM_DIR, 'registry', 'projects')
        n = len([f for f in os.listdir(reg_dir) if f.endswith('.yaml')])
        print(f'registry 项目条目：{n}')
        return n
