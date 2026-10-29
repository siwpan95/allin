# -*- coding: utf-8 -*-
"""为 Tier③ / Tier④ 源仓 README 顶部加状态横幅，提交并推送（幂等）。

用法: python _banners.py [--apply]
  不带 --apply 只打印计划。
"""
import io, json, os, re, subprocess, sys
from pathlib import Path

PLAN = r"G:\allin\docs\事实源\_banner_plan.json"
APPLY = "--apply" in sys.argv

B3 = (
    "> 📦 **已归档（Tier ③ 收敛合并）** — 本仓已迁入归档仓 `{tgt}`，"
    "完整 git 历史保留在 `archive/{name}` 分支。\n"
    "> **原仓冻结、不再开发**；活跃维护请前往归档仓，本仓仅作历史参考。\n"
    "\n"
)
B4 = (
    "> ⏸ **已不再维护（Tier ④ 止损）** — 本仓停止投入，保留原样供查阅。\n"
    "> 不再接受功能更新或缺陷修复；如需沿用，请自行评估依赖与许可。\n"
    "\n"
)


def run(a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def has_remote(repo, name):
    return name in run(["git", "-C", repo, "remote"]).stdout.split()


def main():
    plan = json.load(io.open(PLAN, encoding="utf-8"))
    items = [(x, "3") for x in plan["t3"]] + [(x, "4") for x in plan["t4"]]
    print(f"计划 {len(items)} 仓（③ {len(plan['t3'])} / ④ {len(plan['t4'])}）apply={APPLY}", flush=True)
    ok, skip, fail = [], [], []
    for x, tier in items:
        repo = os.path.dirname(x["readme"]).replace("/", "\\")
        p = x["readme"]
        raw = Path(p).read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig", errors="replace")
        if re.search(r"Tier ③|Tier ④|已归档（|已不再维护（", text[:400]):
            skip.append(x["name"])
            print("  = 已有横幅:", x["name"], flush=True)
            continue
        banner = (B3 if tier == "3" else B4).format(tgt=x.get("tgt", "game-prototypes"),
                                                    name=x["name"])
        new = banner + text.lstrip("\ufeff")
        if not APPLY:
            print("  ~", x["name"], "->", banner.splitlines()[0][:60], flush=True)
            continue
        with io.open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n") as fh:
            fh.write(new)
        msg = ("docs: 标注 Tier③ 已归档（迁入 %s）" % x.get("tgt", "game-prototypes")
               if tier == "3" else "docs: 标注 Tier④ 已停止维护")
        r1 = run(["git", "-C", repo, "add", os.path.basename(p)])
        r2 = run(["git", "-C", repo, "commit", "-q", "-m", msg])
        if r2.returncode != 0:
            fail.append((x["name"], "commit: " + r2.stderr.strip()[-80:]))
            print("  x", x["name"], "commit 失败", flush=True)
            continue
        pushed = []
        for rem in ("origin", "github"):
            if not has_remote(repo, rem):
                continue
            r3 = run(["git", "-C", repo, "push", rem, "HEAD"])
            pushed.append(f"{rem}={'ok' if r3.returncode == 0 else 'FAIL'}")
            if r3.returncode != 0:
                fail.append((x["name"], f"push {rem}: " + r3.stderr.strip()[-80:]))
        ok.append((x["name"], ",".join(pushed)))
        print("  +", x["name"], ",".join(pushed), flush=True)
    print(f"\n=== 提交推送 {len(ok)} | 跳过 {len(skip)} | 失败 {len(fail)} ===", flush=True)
    for n, w in fail:
        print("   FAIL", n, w, flush=True)


if __name__ == "__main__":
    main()
