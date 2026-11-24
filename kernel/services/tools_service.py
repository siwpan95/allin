# -*- coding: utf-8 -*-
"""tools 支柱服务：统一调度 allin 的命令行工具（gitee_release.py / 凭据脚本 / 吸收的技能）。

被 cordis 内核挂载后，经 ``ctx.tools`` 访问。所有子命令都走 allin 自己的原生工具，
不再由人工直接敲 git/curl——这正是「工具统一纳入 cordis 调度」的落点。
"""
from __future__ import annotations

import os
import subprocess
import sys

from kernel.cordis import Service

from kernel.paths import ROOT, TOOLS_DIR


def _gcm_token(host: str) -> str | None:
    """从 Windows GCM 现取指定 host 的令牌（绝不硬编码、不回显）。"""
    try:
        out = subprocess.run(
            ['git', 'credential', 'fill'],
            input=f'protocol=https\nhost={host}\n',
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        )
        if out.returncode != 0:
            # 2026-11-08 深度审核：此前不检查 returncode，git 失败时静默返回 None。
            return None
        for line in out.stdout.splitlines():
            if line.startswith('password='):
                return line[len('password='):]
    except Exception:
        pass
    return None


def get_gitee_token() -> str | None:
    """取 Gitee 令牌：优先 GITEE_TOKEN 环境变量，否则从 Windows GCM 现取（绝不硬编码）。"""
    return os.environ.get('GITEE_TOKEN') or _gcm_token('gitee.com')


def get_github_token() -> str | None:
    """取 GitHub 令牌：优先 GITHUB_TOKEN 环境变量，否则从 Windows GCM 现取。

    2026-11-24 上提增量巡检时新增：github_release.py 自身也会取令牌，
    这里注入环境变量是为了让被调度的工具与 gitee-release 保持同一取令牌纪律。
    GCM 中 github.com 条目已实测可用（classic PAT 含 repo scope）。
    """
    return os.environ.get('GITHUB_TOKEN') or _gcm_token('github.com')


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
        # 2026-11-08 深度审核：name 原样拼进文件名后经
        # powershell -ExecutionPolicy Bypass -File 执行；`..\\` 或绝对路径可指向
        # 任意 .ps1。凭据名是标识符，不是路径。
        if (not isinstance(name, str) or not name
                or not all(c.isalnum() or c in '_-' for c in name)):
            raise ValueError(f'非法凭据名：{name!r}（只允许字母/数字/下划线/连字符）')
        script = os.path.join(TOOLS_DIR, 'credentials', f'{name}-credential.ps1')
        if not os.path.isfile(script):
            raise FileNotFoundError(f'凭据脚本不存在: {script}')
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, action]
        return _run(cmd, cwd=ROOT)

    # ---- venv 安全巡检与加固（通用检查框架）----
    def venv_audit(self, args):
        """调度 tools/security/venv_security.py（通用 venv 安全巡检与加固）。

        用法：allin tools venv-audit <scan|apply|verify> [root] [jobs] [--check ID]
              allin tools venv-audit --list
        检查项：pip 引导 / home 修复 / pip-certifi-uv 基线 / emSign G3 /
        离线漏洞基线 / venv 完整性 / ~ip 孤儿隔离。
        """
        tool = os.path.join(TOOLS_DIR, 'security', 'venv_security.py')
        if not os.path.isfile(tool):
            raise FileNotFoundError(f'巡检工具不存在: {tool}')
        cmd = [sys.executable, tool] + list(args)
        return _run(cmd, cwd=ROOT)

    # ---- GitHub 建仓 / 转公开 / 增量推送 / 独立复核 ----
    def github_release(self, args):
        """调度 tools/github/github_release.py（对称 gitee-release，按 GitHub 平台差异实现）。

        用法：allin tools github-release whoami|list|create|public|remote|push|verify|sync
        GitHub 令牌注入 GITHUB_TOKEN；工具本身也有 GCM 兜底。
        """
        tool = os.path.join(TOOLS_DIR, 'github', 'github_release.py')
        if not os.path.isfile(tool):
            raise FileNotFoundError(f'工具不存在: {tool}')
        cmd = [sys.executable, tool] + list(args)
        env = dict(os.environ)
        tok = get_github_token()
        if tok:
            env['GITHUB_TOKEN'] = tok
        return _run(cmd, cwd=ROOT, env=env)

    # ---- 三端增量巡检（委托 github_release 做建仓/推 GitHub/复核）----
    def github_sync(self, args):
        """调度 tools/github/sync_repos.py：list|pull|pushorigin|sync。

        默认 dry-run（只报告不改动远端）；--apply 才真动作，属高风险须人在场放行。
        发布区根可由 ALLIN_REPOS_ROOT 环境变量给出（去符盘）。
        """
        tool = os.path.join(TOOLS_DIR, 'github', 'sync_repos.py')
        if not os.path.isfile(tool):
            raise FileNotFoundError(f'工具不存在: {tool}')
        cmd = [sys.executable, tool] + list(args)
        env = dict(os.environ)
        tok = get_github_token()
        if tok:
            env['GITHUB_TOKEN'] = tok
        return _run(cmd, cwd=ROOT, env=env)

    # ---- 已吸收的技能：列出可被内核调度的技能清单 ----
    def skills(self):
        skill_dir = os.path.join(ROOT, '.workbuddy', 'skills')
        if not os.path.isdir(skill_dir):
            # 2026-11-10 深度审计 H-4：与 preset_service.list / docs_service 统一，
            # 「目录不存在」不得静默映射成 exit 0（什么都没做 ≠ 成功）。
            print(f'（allin 项目级技能目录不存在，技能尚未吸收：{skill_dir}）', file=sys.stderr)
            return 3
        for name in sorted(os.listdir(skill_dir)):
            print(name)
        return None
