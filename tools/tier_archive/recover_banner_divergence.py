# -*- coding: utf-8 -*-
"""回退横幅脚本造成的分叉：本地多余提交若与远端横幅重复，则丢弃并强制对齐 github 镜像（一次性脚本）。

落点环境变量化（铁律 5）：TIER3_REPOS 指向发布区根，随机器传入，不写死盘符。
"""
import os
import subprocess
import sys

REPOS = """haha test auto_clicker captcha-demo fonts pdf pomodmer print renamer santi-teleprompter
subtitle yasuo daily_player localplayer music-player player Idle adventurelog ashen-beacon bee
darksouls""".split()

_REPOS_ROOT = os.environ.get("TIER3_REPOS", "")
if not _REPOS_ROOT:
    sys.exit("缺少 TIER3_REPOS 环境变量（发布区根随机器，不再写死盘符）")


def run(a, cwd):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


for n in REPOS:
    p = os.path.join(_REPOS_ROOT, n)
    run(["git", "fetch", "origin", "-q"], p)
    ahead = run(["git", "rev-list", "--count", "origin/master..HEAD"], p).stdout.strip()
    subj = run(["git", "log", "-1", "--format=%s"], p).stdout.strip()
    remote_readme = run(["git", "show", "origin/master:README.md"], p).stdout
    remote_has = ("已归档" in remote_readme or "已不再维护" in remote_readme)
    mine = subj.startswith("docs: 标注 Tier")
    if ahead == "1" and mine and remote_has:
        run(["git", "reset", "--hard", "origin/master", "-q"], p)
        r = run(["git", "push", "github", "HEAD:master", "--force-with-lease"], p)
        g = run(["git", "ls-remote", "github", "refs/heads/master"], p).stdout.split()[0][:8]
        l = run(["git", "rev-parse", "--short=8", "HEAD"], p).stdout.strip()
        print(f"  {n:22s} 回退→{l}  github对齐={'ok' if r.returncode == 0 else 'FAIL'} ({g})", flush=True)
    else:
        print(f"  {n:22s} 跳过 ahead={ahead} mine={mine} remote_banner={remote_has} | {subj[:40]}", flush=True)
