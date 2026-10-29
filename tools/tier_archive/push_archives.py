# -*- coding: utf-8 -*-
"""推送归档仓的 master + 全部 archive/* 分支，并核对远端分支数。"""
import subprocess, os, sys

TARGETS = [
    (r"G:\local\_tier3_work\game-prototypes", 34),
    (r"G:\local\_tier3_work\media-prototypes", 13),
    (r"G:\local\_tier3_work\music-prototypes", 3),
    (r"G:\local\_tier3_work\dev-toolkit", 13),
    (r"G:\repos\players-unified", 4),
    (r"G:\repos\sin-virtue-cordis-host", 1),
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
