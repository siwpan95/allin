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
  allin status [--json] [--strict]
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


def _configure_stdio() -> None:
    """强制 UTF-8 输出，与治理门禁 govlib.configure_stdio() 同一口径。

    为什么不靠系统默认：PowerShell 7.4+ 按 UTF-8 解码子进程输出，而 Python 在
    cp936 控制台下会写 GBK 字节 ⇒ `allin --help` 的中文全变乱码。门禁侧早已统一
    强制 UTF-8，CLI 作为同一仓的前门也照此办理（2026-10-26 实测）。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8', errors='replace', newline='\n')


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
        if args.action == 'audit-check':
            docs = [a for a in (getattr(args, 'docs', None) or []) if a != '--']
            return svc.audit_check(docs=docs, as_json=getattr(args, 'json', False),
                                   quiet=getattr(args, 'quiet', False))
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
            result = svc.apply(args.name, dry_run=not args.yes)
            # WJ-01：apply 返回结构化结果；真实落地未实现（dry_run=False）时
            # ok=False ⇒ 映射非零退出（2），避免「--yes 零动作」假绿；dry-run 成功 ⇒ 0。
            if isinstance(result, dict):
                return 0 if result.get('ok') else 2
            return 0
    if args.domain == 'status':
        return ctx.status.summary(as_json=args.json, strict=args.strict)
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
    ds_ac = ds.add_parser('audit-check', help='审计/报告类文档错漏自动检查（E1 证据锚点 / E2 章节 / E3 排序 / E4 无源 / E6 口径 / E7 疑点）')
    ds_ac.add_argument('docs', nargs='*', help='待检文档路径（相对仓根）；省略则检查 docs/记录/审计/ 下全部')
    ds_ac.add_argument('--json', action='store_true', help='机器可读输出')
    ds_ac.add_argument('--quiet', action='store_true', help='只输出结论，不展开基线明细')

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

    p_stat = sub.add_parser('status', help='三面贯通只读状态汇总（纯文件事实源，不依赖网络）')
    p_stat.add_argument('--json', action='store_true', help='输出机器可读 JSON（供 smoke:e2e 断言）')
    p_stat.add_argument('--strict', action='store_true',
                        help='数据源损坏时退出码升级为 2（缺省损坏=1、缺失=0 降级；fail-loud 供机器消费方）')
    return parser


def main() -> int:
    _configure_stdio()
    args = build_parser().parse_args()
    try:
        rc = dispatch(args)
    except (AttributeError, FileNotFoundError, ImportError, RuntimeError, ValueError) as exc:
        # 2026-11-08 深度审核：_boot / 服务方法的异常此前全部裸 traceback，
        # 机器消费方无法区分故障类型。统一为可读诊断 + 环境错误码。
        print(f'allin: 命令执行失败：{exc.__class__.__name__}: {exc}', file=sys.stderr)
        return 3
    return _exit_code(rc)


if __name__ == '__main__':
    sys.exit(main())
