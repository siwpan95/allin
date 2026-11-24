#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器事实聚合器 —— `facts/machine/<机>.json`（单源，一机一件）→ `facts.json` 的机器段。

## 为什么拆（2026-11-25）

全哥两轮指出同一件事：
「你不把各机事实源区分清楚，以现在这种混杂的情况，门禁其实形同虚设。」
「代码是一扇门，文档是另一扇门。文档混写才是目前最大的问题。」

`facts/facts.json` 十三个顶层键里混着三层内容：

| 层 | 键 | 归属 |
| --- | --- | --- |
| B2/B3 跨机共识 | projects / tiering / tools / licenses / ports / facts / doc_refs | 人写，跟仓走 |
| **B' 机器特化** | machines / volumes / runtimes / observation_runs | **各机自己的事，一机一件** |
| C 时点 | generated_at | 派生 |

混居的后果正是「门禁形同虚设」：machine 段是三机共一文件，没有归属隔离，
`g20-facts` 只判 markdown 分区文件、不读它；`facts_drift` 只对「md 目录数 vs machines 条数」
做计数对账——**`volumes.free_gb` 停在 56 天前也没有任何红灯**。

## 拆法（最小命中）

- **单源**：`facts/machine/<machine_id>.json`，每台机一份，各机只写自己那份（铁律 6 的数字版）；
- **派生**：`facts.json` 的 machines / volumes / runtimes / observation_runs 四段由本脚本聚合，
  文件头写 `"_machine_section_derived": true`，**手改即被下次聚合覆盖 + `--check` 报红**；
- 其余九个键（共识层）不动，仍由 `build_*.py` 各自投影。

## 用法

    python tools/facts/build_machine_index.py            # 聚合写入 facts.json
    python tools/facts/build_machine_index.py --check    # 只比对（派生是否滞后/被手改）
    python tools/facts/build_machine_index.py --split    # 从 facts.json 拆出 machine/*.json（一次性迁移）

零第三方依赖。退出码：0 一致 / 1 不一致 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from .exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK
except ImportError:
    try:
        from exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK
    except ImportError:
        EXIT_OK, EXIT_FINDING, EXIT_ENV = 0, 1, 3

#: 从 facts.json 下沉到 machine/<机>.json 的机器特化段
MACHINE_SECTIONS = ("volumes", "runtimes", "observation_runs")
DERIVED_FLAG = "_machine_section_derived"


def repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "facts").is_dir() and (parent / "tools").is_dir():
            return parent
    return None


def split_from_facts(facts: Path, out_dir: Path) -> list[str]:
    """一次性迁移：把 facts.json 的三机机器段拆成 machine/<机>.json。"""
    doc = json.loads(facts.read_text(encoding="utf-8"))
    machines = doc.get("machines") or []
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for m in machines:
        mid = m.get("machine_id")
        if not mid:
            continue
        payload = {
            "schema_version": doc.get("schema_version", "1.0"),
            "machine": m,
            "volumes": [v for v in doc.get("volumes") or [] if v.get("machine_id") == mid],
            "runtimes": [r for r in doc.get("runtimes") or [] if r.get("machine_id") == mid],
            "observation_runs": [o for o in doc.get("observation_runs") or [] if o.get("machine_id") == mid],
            "source": "由 build_machine_index.py --split 从 facts.json 拆出；此后本文件是该机的**单源**",
        }
        path = out_dir / f"{mid}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(mid)
    return written


def aggregate(machine_dir: Path) -> dict:
    """读 machine/*.json → 四段聚合结果（按 machine_id 排序，稳定可比）。"""
    machines, volumes, runtimes, runs = [], [], [], []
    if not machine_dir.is_dir():
        return {"machines": [], "volumes": [], "runtimes": [], "observation_runs": []}
    for path in sorted(machine_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        m = doc.get("machine")
        if not m:
            continue
        machines.append(m)
        volumes.extend(doc.get("volumes") or [])
        runtimes.extend(doc.get("runtimes") or [])
        runs.extend(doc.get("observation_runs") or [])
    machines.sort(key=lambda x: str(x.get("machine_id", "")))
    return {"machines": machines, "volumes": volumes, "runtimes": runtimes, "observation_runs": runs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_machine_index",
                                 description="机器事实聚合：machine/<机>.json → facts.json 机器段（派生）")
    ap.add_argument("--root", help="allin 仓根")
    ap.add_argument("--check", action="store_true", help="只比对，不写")
    ap.add_argument("--split", action="store_true", help="从 facts.json 拆出 machine/*.json（一次性迁移）")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else repo_root()
    if root is None:
        print("ENV ERROR: 找不到 allin 仓根", file=sys.stderr)
        return EXIT_ENV
    facts = root / "facts" / "facts.json"
    machine_dir = root / "facts" / "machine"
    if not facts.is_file():
        print(f"ENV ERROR: {facts} 不存在", file=sys.stderr)
        return EXIT_ENV

    if args.split:
        done = split_from_facts(facts, machine_dir)
        print(f"已拆出 {len(done)} 份 → {machine_dir}: {', '.join(done)}")
        return EXIT_OK

    agg = aggregate(machine_dir)
    if not agg["machines"]:
        print(f"ENV ERROR: {machine_dir} 下没有可聚合的机器文件（先跑 --split）", file=sys.stderr)
        return EXIT_ENV

    doc = json.loads(facts.read_text(encoding="utf-8"))
    current = {k: doc.get(k) or [] for k in ("machines", *MACHINE_SECTIONS)}
    same = all(current[k] == agg[k] for k in current)

    if args.check:
        if same:
            print(f"machines-sync: clean（{len(agg['machines'])} 台机，与 machine/ 聚合一致）")
            return EXIT_OK
        diffs = [k for k in current if current[k] != agg[k]]
        print(f"machines-sync: blocking —— facts.json 机器段与 machine/ 聚合不一致（段: {', '.join(diffs)}）")
        print("  处置：跑 build_machine_index.py 重建；若你手改了 facts.json 的机器段，改到 machine/<机>.json 去")
        return EXIT_FINDING

    doc.update(agg)
    doc[DERIVED_FLAG] = True
    facts.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE: facts.json 机器段 = {len(agg['machines'])} 台机 / {len(agg['volumes'])} 卷 / "
          f"{len(agg['runtimes'])} 运行时 / {len(agg['observation_runs'])} 观测轮次（聚合自 {machine_dir}）")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
