# -*- coding: utf-8 -*-
"""allin 统一命令行接口 —— cordis 内核 boot 后按子命令调度四大支柱服务。

用法（经 venv 的 python 运行，见 allin.bat）：
  allin tools gitee-release -- status --name hushi_twrj
  allin tools credential gitee get
  allin tools skills
  allin docs portfolio [--apply]
  allin platform check-repos
  allin preset list
  allin preset show <name>
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kernel.tree import mount_tree, WANT_ALL, config_path, ALLIN_CONFIG  # noqa: E402


async def _boot():
    return await mount_tree(config_path(ALLIN_CONFIG), want=WANT_ALL)


def _exit_code(rc):
    if isinstance(rc, int):
        return rc
    if hasattr(rc, 'returncode'):
        return rc.returncode
    return 0


def dispatch(args) -> object:
    ctx = asyncio.run(_boot())
    if args.domain == 'tools':
        svc = ctx.tools
        parts = [a for a in args.args if a != '--']
        if not parts:
            print('用法: allin tools <gitee-release|credential|venv-audit|skills> ...')
            return 1
        tool = parts[0]
        rest = parts[1:]
        if tool == 'gitee-release':
            return svc.gitee_release(rest)
        if tool == 'credential':
            name = rest[0] if rest else 'gitee'
            action = rest[1] if len(rest) > 1 else 'get'
            return svc.credential(name, action)
        if tool == 'venv-audit':
            return svc.venv_audit(rest)
        if tool == 'skills':
            return svc.skills()
        print(f'未知工具: {tool}')
        return 2
    if args.domain == 'docs':
        svc = ctx.docs
        if args.action == 'portfolio':
            return svc.portfolio(apply=args.apply)
        if args.action == 'aliases':
            return svc.aliases()
        if args.action == 'index':
            return svc.index()
    if args.domain == 'platform':
        svc = ctx.platform
        if args.action == 'check-repos':
            return svc.check_repos()
        if args.action == 'registry-count':
            return svc.registry_count()
    if args.domain == 'preset':
        svc = ctx.preset
        if args.action == 'list':
            return svc.list()
        if args.action == 'show':
            return svc.show(args.name)
        if args.action == 'apply':
            return svc.apply(args.name, dry_run=not args.yes)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='allin', description='allin 统一调度 CLI（cordis 内核）')
    sub = parser.add_subparsers(dest='domain', required=True)

    p_tools = sub.add_parser('tools', help='工具调度（gitee_release.py / 凭据脚本 / venv 安全巡检 / 技能）')
    p_tools.add_argument('args', nargs=argparse.REMAINDER,
                         help='工具名 + 透传参数，如 gitee-release --name X status / credential gitee get '
                              '/ venv-audit scan <目录> / skills')

    p_docs = sub.add_parser('docs', help='文档构建/索引')
    ds = p_docs.add_subparsers(dest='action', required=True)
    ds_pf = ds.add_parser('portfolio')
    ds_pf.add_argument('--apply', action='store_true')
    ds.add_parser('aliases')
    ds.add_parser('index')

    p_plat = sub.add_parser('platform', help='platform 治理/门禁')
    pl = p_plat.add_subparsers(dest='action', required=True)
    pl.add_parser('check-repos')
    pl.add_parser('registry-count')

    p_pre = sub.add_parser('preset', help='治理模式组合包')
    pr = p_pre.add_subparsers(dest='action', required=True)
    pr_l = pr.add_parser('list')
    pr_s = pr.add_parser('show')
    pr_s.add_argument('name')
    pr_a = pr.add_parser('apply')
    pr_a.add_argument('name')
    pr_a.add_argument('--yes', action='store_true')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rc = dispatch(args)
    return _exit_code(rc)


if __name__ == '__main__':
    sys.exit(main())
