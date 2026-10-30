# -*- coding: utf-8 -*-
"""为 Tier③ 归档仓补建 archive/<原仓> 分支（幂等，一次性脚本）。

落点环境变量化（铁律 5：不写死盘符，跨机可用）：
- TIER3_INDEX   组合分级决策索引.md 路径；缺省按本仓 docs/事实源/ 推导
- TIER3_WORK    收拢工作区（各目标归档仓克隆所在处）；必填
- TIER3_REPOS   源仓发布区根（<root>/<仓名>）；必填
- TIER3_ARCHIVE 归档区根（<root>/<仓名>-retired-<日期>）；必填
"""
import os, subprocess, re, io, sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
IDX = os.environ.get("TIER3_INDEX") or str(_REPO / "docs" / "事实源" / "组合分级决策索引.md")
W = os.environ.get("TIER3_WORK", "")
REPOS = os.environ.get("TIER3_REPOS", "")
ARCHIVE = os.environ.get("TIER3_ARCHIVE", "")
if not (W and REPOS and ARCHIVE):
    sys.exit("缺少 TIER3_WORK / TIER3_REPOS / TIER3_ARCHIVE 环境变量"
             "（落点随机器，不再写死盘符；见模块 docstring）")

rows = []
for line in io.open(IDX, encoding="utf-8"):
    m = re.match(r"\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*([①②③④][^|]*)\|\s*([^|]*)\|\s*([^|]*)\|", line)
    if m:
        rows.append({"name": m.group(2).strip(), "tier": m.group(4).strip(), "tgt": m.group(6).strip()})

groups = {}
for r in rows:
    if r["tier"].startswith("③") and r["tgt"] not in ("-",):
        groups.setdefault(r["tgt"], []).append(r["name"])


def run(a):
    return subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace")


def hasref(p, ref):
    return run(["git", "-C", p, "rev-parse", "--verify", "--quiet", ref]).returncode == 0


def srcpath(n):
    for c in (os.path.join(REPOS, n), os.path.join(ARCHIVE, f"{n}-retired-20261029")):
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    return None


def tgtpath(t):
    for c in (os.path.join(W, t), os.path.join(REPOS, t)):
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    return None


ok, fail = [], []
for tgt, names in groups.items():
    tp = tgtpath(tgt)
    if not tp:
        print("!! 目标缺:", tgt, flush=True)
        continue
    for n in names:
        if hasref(tp, f"refs/heads/archive/{n}"):
            ok.append((tgt, n, "已存在"))
            continue
        s = srcpath(n)
        if not s:
            fail.append((tgt, n, "源仓缺失"))
            print("  x", tgt, n, "源仓缺失", flush=True)
            continue
        br = "master" if hasref(s, "refs/heads/master") else ("main" if hasref(s, "refs/heads/main") else None)
        if not br:
            fail.append((tgt, n, "源仓无 master/main"))
            print("  x", tgt, n, "无主分支", flush=True)
            continue
        r = run(["git", "-C", tp, "fetch", "--no-tags", s, f"+refs/heads/{br}:refs/heads/archive/{n}"])
        if r.returncode == 0:
            ok.append((tgt, n, "ok"))
            print("  +", tgt, n, flush=True)
        else:
            fail.append((tgt, n, r.stderr.strip()[-70:]))
            print("  x", tgt, n, r.stderr.strip()[-70:], flush=True)

print(f"\n=== 结果: 建立/已存在 {len(ok)} 条 | 失败 {len(fail)} ===", flush=True)
for t, c in Counter(t for t, _, _ in ok).items():
    print(f"   {t}: {c}", flush=True)
for x in fail:
    print("   FAIL", x, flush=True)
