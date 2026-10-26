# -*- coding: utf-8 -*-
"""tools 支柱服务：统一调度 allin 的命令行工具（gitee_release.py / 凭据脚本 / 吸收的技能）。

被 cordis 内核挂载后，经 ``ctx.tools`` 访问。所有子命令都走 allin 自己的原生工具，
不再由人工直接敲 git/curl——这正是「工具统一纳入 cordis 调度」的落点。
"""
from __future__ import annotations

import os
import subprocess
import sys

from cordis import Service

from kernel.paths import ROOT, TOOLS_DIR


def get_gitee_token() -> str | None:
    """取 Gitee 令牌：优先 GITEE_TOKEN 环境变量，否则从 Windows GCM 现取（绝不硬编码）。"""
    tok = os.environ.get('GITEE_TOKEN')
    if tok:
        return tok
    try:
        out = subprocess.run(
            ['git', 'credential', 'fill'],
            input='protocol=https\nhost=gitee.com\n',
            capture_output=True, text=True, timeout=30,
        )
        for line in out.stdout.splitlines():
            if line.startswith('password='):
                return line[len('password='):]
    except Exception:
        pass
    return None


def _run(cmd, cwd=ROOT, env=None):
    """运行子进程，继承终端（让工具输出直达用户）。"""
    return subprocess.run(cmd, cwd=cwd, env=env)


class ToolService(Service):
    def __init__(self, ctx, config=None):
        super().__init__(ctx, 'tools')

    def __cordis_init__(self):
        return None

    # ---- gitee_release.py：建仓 / 转公开 / 发布 / 核验 ----
    def gitee_release(self, args):
        tool = os.path.join(TOOLS_DIR, 'gitee_release.py')
        cmd = [sys.executable, tool] + list(args)
        env = dict(os.environ)
        tok = get_gitee_token()
        if tok:
            env['GITEE_TOKEN'] = tok
        return _run(cmd, cwd=ROOT, env=env)

    # ---- 凭据脚本：gitee-credential.ps1 / tavily-credential.ps1 ----
    def credential(self, name: str, action: str = 'get'):
        script = os.path.join(TOOLS_DIR, 'credentials', f'{name}-credential.ps1')
        if not os.path.isfile(script):
            raise FileNotFoundError(f'凭据脚本不存在: {script}')
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, action]
        return _run(cmd, cwd=ROOT)

    # ---- 已吸收的技能：列出可被内核调度的技能清单 ----
    def skills(self):
        skill_dir = os.path.join(ROOT, '.workbuddy', 'skills')
        if not os.path.isdir(skill_dir):
            print('（allin 项目级技能目录不存在，技能尚未吸收）')
            return None
        for name in sorted(os.listdir(skill_dir)):
            print(name)
        return None
