# -*- coding: utf-8 -*-
"""推送归档仓的 master + 全部 archive/* 分支，并核对远端分支数（一次性脚本）。

落点环境变量化（铁律 5）：TIER3_WORK / TIER3_REPOS 随机器传入，不写死盘符。
"""
import subprocess, os, sys
from pathlib import Path

_WORK = os.environ.get("TIER3_WORK", "")
_REPOS = os.environ.get("TIER3_REPOS", "")
if not (_WORK and _REPOS):
    sys.exit("缺少 TIER3_WORK / TIER3_REPOS 环境变量（落点随机器，不再写死盘符）")

TARGETS = [
    (os.path.join(_WORK, "game-prototypes"), 34),
    (os.path.join(_WORK, "media-prototypes"), 13),
    (os.path.join(_WORK, "music-prototypes"), 3),
    (os.path.join(_WORK, "dev-toolkit"), 13),
    (os.path.join(_REPOS, "players-unified"), 4),
    (os.path.join(_REPOS, "sin-virtue-cordis-host"), 1),
]


def run(a, cwd=None, timeout=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


for path, expect in TARGETS:
    name = os.path.basename(path)
    print(f"\n=== {name} ===", flush=True)
    r = run(["git", "-C", path, "push", "origin", "master",
             "refs/heads/archive/*:refs/heads/archive/*"], timeout=3600)
    tail = (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout) else ""
    print(f"  push rc={r.returncode} {tail[:110]}", flush=True)
    r2 = run(["git", "-C", path, "ls-remote", "--heads", "origin"], timeout=300)
    branches = [l.split("refs/heads/")[1] for l in r2.stdout.splitlines() if "refs/heads/" in l]
    arch = [b for b in branches if b.startswith("archive/")]
    print(f"  远端分支 {len(branches)} 个，其中 archive/* {len(arch)} 个（预期 {expect}）"
          f"{' ✅' if len(arch) == expect else ' ❌'}", flush=True)
