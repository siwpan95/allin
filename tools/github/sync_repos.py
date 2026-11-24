#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_repos.py — 本地发布区 ↔ GitHub ↔ gitee 三端增量巡检（从 WorkBuddy 临时工作区上提）
================================================================================

本工具是 automation「GitHub 增量巡检」的**唯一入口**，由 WorkBuddy 定时任务调用。
上提自 WorkBuddy 临时工作区的 sync_github.py（原 cwd 在临时目录，
无版本化、无治理）。上提纪律参照 venv-audit 与 foolproof-operation 两次能力上提：
只搬判据与工具，不留第二份实现。

权威关系（2026-11-24 全哥明确）：**gitee 远端 = 唯一权威源**，本地与 GitHub 都是它的下游。
  · 本地落后 → 快进对齐；本地领先/分叉 → 异常只报告，不回推
  · GitHub 差异 → 以「已与 gitee 对齐的本地」为准推送；GitHub 独有提交不删，只报告
  · 方向严格单向：gitee → 本地 → GitHub。**禁止向 gitee 推送**（pushorigin 语义废止）

职责边界（**判据单一实现**）：
  · 建仓 / 推 GitHub / 独立复核 → 委托 tools/github_release.py（create/push/verify）
    本文件**不重复实现**这些逻辑，避免两份建仓代码漂移。
  · 本文件只实现：
      list       盘点三端差集
      pull       fetch origin(gitee) 后仅快进（脏/detached/分叉/领先 → 只报告）
      drift      报告本地领先/分叉的仓（原 pushorigin 的只读替代，不回推）
      sync       串起 list→create→pull→push→drift，默认 dry-run

安全边界（写死，不提供绕过开关）：
  · 工作区脏 / detached HEAD / 与远端分叉或本地领先 → 一律只报告，不自动 rebase/merge
  · 绝不向 gitee 推送（gitee 是权威，只从它拉取）
  · --apply 才真动作；不带则纯只读（automation 默认不带）
  · sin-virtue-game 在 gitee 已 404（退役），GitHub 侧保留归档副本，不为其建 gitee 仓
  · allin 治理仓独立双推，不在发布区（repos）扫描范围

通道与凭据：
  · 推送 GitHub 走 SSH（git@github.com:siwpan95/<name>.git），443 被封不可用
  · 拉取/回推走 origin = gitee HTTPS
  · 令牌由 github_release.get_token 统一取（GITHUB_TOKEN → GCM），本文件不碰明文

退出码：0 成功/无需动作 · 1 有失败 · 2 用法或环境 · 3 网络或 API 失败
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

# github_release 的加载支持两种形态（与 _repocheck_dir() 同一纪律，不是两份副本）：
#   1. 安装态：两个模块都被 package-dir 映射进 allin_governance._toolkit，直接 import
#   2. 源码态（仓内直接跑 / 开发 / CI）：按本文件相对路径定位仓内真身
try:
    from . import github_release as gh                    # 安装态（包内）
except (ImportError, ValueError):
    try:
        import github_release as gh                        # 源码态（调用方已把 tools/github 放进 sys.path）
    except ImportError:
        import importlib.util                              # 源码态兜底：按本文件相对路径加载
        _AL = os.path.dirname(os.path.abspath(__file__))   # tools/github
        _candidate = os.path.join(_AL, "github_release.py")  # 同包目录
        _spec = importlib.util.spec_from_file_location("allin_github_release", _candidate)
        gh = importlib.util.module_from_spec(_spec)  # noqa: E402
        _spec.loader.exec_module(gh)

REPOS_ROOT_ENV = "ALLIN_REPOS_ROOT"


def log(msg: str):
    print(msg, flush=True)


def git(args, cwd=None, timeout=300):
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def local_repos(root) -> list:
    return [n for n in sorted(os.listdir(root))
            if os.path.isdir(os.path.join(root, n, ".git"))]


def cmd_list(args, token):
    return gh.cmd_list(args, token)


def cmd_pull(args):
    """对齐本地：fetch origin(gitee) 后仅 ff-only；不安全态一律只报告。"""
    root = gh.repos_root(args.repos_root)
    loc = local_repos(root)
    log("对齐目标: 本地 %d 仓，远端 origin(gitee)" % len(loc))
    ff = synced = skipped = human = 0
    human_names = []
    for i, name in enumerate(loc, 1):
        d = os.path.join(root, name)
        st = git(["status", "--porcelain", "-uno"], cwd=d)
        if st.stdout.strip():
            skipped += 1
            log("[%d/%d] %s 跳过：工作区有未提交改动" % (i, len(loc), name))
            continue
        br = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=d).stdout.strip()
        if not br or br == "HEAD":
            skipped += 1
            log("[%d/%d] %s 跳过：detached HEAD" % (i, len(loc), name))
            continue
        f = git(["fetch", "--tags", "origin"], cwd=d, timeout=300)
        if f.returncode != 0:
            skipped += 1
            log("[%d/%d] %s 跳过：fetch 失败 %s" % (i, len(loc), name, (f.stderr or "")[:100]))
            continue
        ref = "origin/%s" % br
        r = git(["rev-parse", "--verify", ref], cwd=d)
        if r.returncode != 0:
            skipped += 1
            log("[%d/%d] %s 跳过：远端无分支 %s" % (i, len(loc), name, ref))
            continue
        rsha, lsha = r.stdout.strip(), git(["rev-parse", "HEAD"], cwd=d).stdout.strip()
        if lsha == rsha:
            synced += 1
            continue
        anc = git(["merge-base", "--is-ancestor", "HEAD", ref], cwd=d)
        if anc.returncode != 0:
            human += 1
            human_names.append(name)
            log("[%d/%d] %s 需人工：与远端分叉或本地领先（不自动 rebase/merge）" % (i, len(loc), name))
            continue
        if not args.apply:
            ff += 1
            log("[%d/%d] [DRY] %s 可快进 -> %s" % (i, len(loc), name, rsha[:8]))
            continue
        m = git(["merge", "--ff-only", ref], cwd=d, timeout=300)
        if m.returncode == 0:
            ff += 1
            log("[%d/%d] %s 快进对齐 -> %s" % (i, len(loc), name, rsha[:8]))
        else:
            skipped += 1
            log("[%d/%d] %s 快进失败：%s" % (i, len(loc), name, (m.stderr or "")[:100]))
    log("对齐结束: 快进 %d | 已最新 %d | 跳过 %d | 需人工 %d" % (ff, synced, skipped, human))
    if human_names:
        log("需人工: " + " ".join(human_names))
    return 0


def cmd_drift(args):
    """只读报告本地相对权威源(gitee)的偏离。绝不推送——gitee 是权威，只能从它拉取。"""
    root = gh.repos_root(args.repos_root)
    loc = local_repos(root)
    log("偏离检查: 本地 %d 仓相对 origin(gitee)（只读，不推送）" % len(loc))
    ok = skipped = human = 0
    names = []
    for i, name in enumerate(loc, 1):
        d = os.path.join(root, name)
        if name == "sin-virtue-game":
            skipped += 1
            continue
        br = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=d).stdout.strip()
        if not br or br == "HEAD":
            skipped += 1
            continue
        if git(["status", "--porcelain", "-uno"], cwd=d).stdout.strip():
            skipped += 1
            continue
        r = git(["rev-parse", "--verify", "origin/%s" % br], cwd=d)
        if r.returncode != 0:
            skipped += 1
            continue
        lsha = git(["rev-parse", "HEAD"], cwd=d).stdout.strip()
        if lsha == r.stdout.strip():
            continue
        a = git(["rev-list", "--count", "origin/%s..HEAD" % br], cwd=d).stdout.strip()
        b = git(["rev-list", "--count", "HEAD..origin/%s" % br], cwd=d).stdout.strip()
        ahead = int(a) if a.isdigit() else -1
        behind = int(b) if b.isdigit() else -1
        if behind > 0:
            human += 1
            names.append(name)
            log("[%d/%d] %s 需人工：远端有新提交（本地独有 %s / 远端独有 %s）" % (i, len(loc), name, ahead, behind))
            continue
        ok += 1
        log("[%d/%d] 偏离：%s 本地领先 %d 提交（只报告；如需提升为权威须人工推送到 gitee）"
            % (i, len(loc), name, ahead))
    log("偏离检查结束: 领先 %d | 需人工 %d | 跳过 %d（零推送）" % (ok, human, skipped))
    if names:
        log("需人工: " + " ".join(names))
    return 0


def cmd_sync(args, token):
    """巡检闭环：list → create(github_release) → pull → push(github_release) → drift（只读）。"""
    root = gh.repos_root(args.repos_root)
    loc = local_repos(root)
    ghnames = gh.gh_repos(token)
    missing = [n for n in loc if n.lower() not in {g.lower() for g in ghnames}]
    log("[sync] 本地 %d | GitHub %d | 待建 %d | mode=%s"
        % (len(loc), len(ghnames), len(missing), "APPLY" if args.apply else "DRY-RUN"))
    created = pushed = back = 0
    for name in missing:
        if not args.apply:
            log("  [DRY] 待建: %s" % name)
            continue
        if gh.cmd_create(argparse.Namespace(owner=args.owner, name=name, desc=""), token) == 0:
            created += 1
    for i, name in enumerate(loc, 1):
        d = os.path.join(root, name)
        state = gh._safe_state(d)
        if state:
            log("  [MANUAL] [%d/%d] %s: %s" % (i, len(loc), name, state))
            continue
        if gh.cmd_push(argparse.Namespace(owner=args.owner, name=name,
                                          repos_root=root, apply=args.apply)) == 0 and args.apply:
            pushed += 1
    log("[sync] 建仓 %d | 推 GitHub %d | mode=%s" % (created, pushed, "APPLY" if args.apply else "DRY-RUN"))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="三端增量巡检（建仓/推 GitHub/复核委托 github_release.py）")
    ap.add_argument("--owner", default=gh.DEFAULT_OWNER)
    ap.add_argument("--repos-root", default="", help="发布区根；不传走 %s" % REPOS_ROOT_ENV)
    ap.add_argument("--token", default="")
    ap.add_argument("--token-file", default="")
    ap.add_argument("--apply", action="store_true", help="真动作；不带只报告")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("pull")
    sub.add_parser("drift")
    sub.add_parser("sync")
    return ap


def main(argv=None):
    # argv 可选：独立运行时走 sys.argv（argparse 约定），从包内 `allin-governance github`
    # 调用时由包装层把剩余参数传进来。2026-11-24 事故：原签名不接受参数，而 CLI 包装层
    # 传了一个 list ⇒ 每次 `github <子命令>` 都 TypeError（1.0.1 已发布版本实测）。
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    if args.cmd in ("pull", "drift"):
        return cmd_pull(args) if args.cmd == "pull" else cmd_drift(args)
    token = gh.get_token(args.token, args.token_file)
    if args.cmd == "list":
        return cmd_list(args, token)
    if args.cmd == "sync":
        return cmd_sync(args, token)
    return 2


if __name__ == "__main__":
    sys.exit(main())
