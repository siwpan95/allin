# -*- coding: utf-8 -*-
"""docs 支柱服务：统一调度 allin/docs 的构建与索引（portfolio / 文档别名 / 目录索引）。

被 cordis 内核挂载后，经 ``ctx.docs`` 访问。底层是 Python / PowerShell 工具，本服务用子进程封装。
"""
from __future__ import annotations

import os
import shutil
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
            # 2026-11-08 深度审核：缺脚本时 return None 会被 CLI 映射成 exit 0，
            # 「什么都没做」假绿。改为环境错误码。
            print('（make_doc_aliases.ps1 不存在）', file=sys.stderr)
            return 3
        # S1（2026-11-11）：优先 PowerShell 7（pwsh），回落 Windows PowerShell 5.1。
        # 用 shutil.which 探测 PATH，不硬编码解释器绝对路径（跨机可移植）。
        shell = shutil.which('pwsh') or shutil.which('powershell') or 'powershell'
        cmd = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script]
        # 只换解释器还不够：子进程直接继承 OS 控制台句柄时中文会乱码；而 pwsh 7
        # 在 Windows 管道下**同样按系统 ANSI(cp936) 输出**（实测字节 b'\xb9\xe6\xb7\xb6'
        # = 「规范」），不能按 shell 版本猜编码。这里捕获原始字节、自动探测：
        # UTF-8 严格解码成功即用，失败回落系统 ANSI；再经 CLI 已强制 UTF-8 的
        # sys.stdout 写出（与 _configure_stdio 同源），跨 pwsh/5.1/非 Windows 均成立。
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True)

        def _decode(raw: bytes) -> str:
            if not raw:
                return ''
            try:
                return raw.decode('utf-8')
            except UnicodeDecodeError:
                return raw.decode('mbcs' if os.name == 'nt' else 'utf-8', errors='replace')

        if proc.stdout:
            sys.stdout.write(_decode(proc.stdout))
        if proc.stderr:
            sys.stderr.write(_decode(proc.stderr))
        return proc

    # ---- 文档枢纽索引契约门禁（SPEC-005，D1–D8）----
    def index(self):
        tool = os.path.join(TOOLS_DIR, 'gate', 'docs_index.py')
        if not os.path.isfile(tool):
            print('（docs_index.py 不存在）', file=sys.stderr)
            return 3
        return subprocess.run([sys.executable, tool], cwd=ROOT)

    # ---- 审计/报告类文档错漏自动检查（E1–E7）----
    def audit_check(self, docs=None, as_json: bool = False, quiet: bool = False):
        """检查结论型文档（审计报告 / 复评报告）的证据锚点与结构自洽性。

        未指定文档时默认检查 ``docs/记录/审计/`` 下全部 ``*.md``。
        历史欠账基线内的违例不计门禁（输出 BASE）；新增违例才判红。
        退出码原样透传：0 无新增违例 / 1 有新增违例 / 2 用法错 / 3 环境错。
        """
        tool = os.path.join(TOOLS_DIR, 'gate', 'audit_doc_check.py')
        if not os.path.isfile(tool):
            print('（audit_doc_check.py 不存在）', file=sys.stderr)
            return 3
        flags = (['--json'] if as_json else []) + (['--quiet'] if quiet else [])
        args = [sys.executable, tool] + flags
        if docs:
            args.extend(docs)
        else:
            listing = subprocess.run([sys.executable, tool, '--list-all'], cwd=ROOT,
                                     capture_output=True, text=True,
                                     encoding='utf-8', errors='replace')
            if listing.returncode != 0:
                sys.stderr.write(listing.stderr or '')
                return listing.returncode
            targets = [line.strip() for line in listing.stdout.splitlines() if line.strip()]
            if not targets:
                print('（未找到受检文档）', file=sys.stderr)
                return 3
            args = [sys.executable, tool] + flags + targets
        return subprocess.run(args, cwd=ROOT)
