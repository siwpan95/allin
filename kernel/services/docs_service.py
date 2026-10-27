# -*- coding: utf-8 -*-
"""docs 支柱服务：统一调度 allin/docs 的构建与索引（portfolio / 文档别名 / 目录索引）。

被 cordis 内核挂载后，经 ``ctx.docs`` 访问。底层是 Python / PowerShell 工具，本服务用子进程封装。
"""
from __future__ import annotations

import os
import subprocess
import sys

from kernel.cordis import Service

from kernel.paths import ROOT, TOOLS_DIR


class DocsService(Service):
    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'docs')

    def __cordis_init__(self):
        return None

    # ---- 刷新 PORTFOLIO.md（--apply 才写盘，否则干跑看数字）----
    def portfolio(self, apply: bool = False):
        tool = os.path.join(TOOLS_DIR, 'build_portfolio.py')
        args = ['--apply'] if apply else []
        cmd = [sys.executable, tool] + args
        return subprocess.run(cmd, cwd=ROOT)

    # ---- 重建文档枢纽 ASCII 别名 junction ----
    def aliases(self):
        script = os.path.join(ROOT, 'tools', 'gate', 'make_doc_aliases.ps1')
        if not os.path.isfile(script):
            print('（make_doc_aliases.ps1 不存在）')
            return None
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script]
        return subprocess.run(cmd, cwd=ROOT)

    # ---- 文档枢纽索引契约门禁（SPEC-005，D1–D8）----
    def index(self):
        tool = os.path.join(TOOLS_DIR, 'gate', 'docs_index.py')
        if not os.path.isfile(tool):
            print('（docs_index.py 不存在）')
            return None
        return subprocess.run([sys.executable, tool], cwd=ROOT)
