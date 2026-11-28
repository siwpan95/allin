#!/usr/bin/env python
"""消费方：调用 allin-governance 的发现目录，写入 registry/observed/（机器观测态）。

三仓分工（用户草案，2026-11-28 落地）：
  allin             = 消费方，提出需求：发布区里有哪些仓、怎么启动、远端是谁；
  allin-governance  = 解决需求：scan --catalog 产出发现目录 JSON；
  govrule           = 审批 + 交付：registry.observed 判据核对观测态的机器字段与人属边界。

消费方**不自己实现扫描**，也**永不写 registry/projects/**（人工语义）。
契约不满足（schema 不符 / 字段缺失 / discovered 与 rows 不一致）时直接失败——
不把「 provider 变了」悄悄降级成「写少几条」。

用法：
    python platform/scripts/import_catalog.py --root <发布区> --dry-run
    python platform/scripts/import_catalog.py --root <发布区>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "requirements" / "scan.fixture.json"
_contract = json.loads(FIXTURE.read_text(encoding="utf-8"))
SCHEMA = _contract["schema"]
REQUIRED_ROW_KEYS = ("id", "path", "launch", "publish")
OBSERVED_DIR = Path(__file__).resolve().parents[1] / "registry" / "observed"


def fetch(root: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "allin_governance", "scan", "--catalog", "--root", root],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"provider 失败（exit {proc.returncode}）：{proc.stderr[:500]}")
    return json.loads(proc.stdout)


def validate(cat: dict) -> None:
    """消费方侧契约校验——provider 升级不能让消费方静默少写。"""
    if cat.get("schema") != SCHEMA:
        raise ValueError(f"schema 不符：{cat.get('schema')!r} != {SCHEMA!r}")
    for key in _contract["required_top"]:
        if key not in cat:
            raise ValueError(f"契约 fixture 要求顶层字段 {key}，provider 没给")
    rows = cat.get("rows")
    if not isinstance(rows, list):
        raise ValueError("rows 缺失或不是数组")
    if int(cat.get("discovered") or -1) != len(rows):
        raise ValueError(f"discovered={cat.get('discovered')} 与 rows={len(rows)} 不一致")
    for i, row in enumerate(rows):
        missing = [k for k in _contract["required_row"] if k not in row]
        if missing:
            raise ValueError(f"rows[{i}] 缺字段：{missing}")
        pub = row.get("publish") or {}
        for key in _contract["required_publish"]:
            if key not in pub:
                raise ValueError(f"rows[{i}].publish 缺 {key}")
        # 人属字段绝不允许出现在观测目录里（判据会再守一遍）
        forbidden = [k for k in _contract["forbidden_row"] if k in row]
        if forbidden:
            raise ValueError(f"rows[{i}] 混入了人工字段：{forbidden}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    # 不写死任何机器的发布区路径：env 或由仓位置推导（<repo>/../repos）
    ap.add_argument("--root", default=None, help="发布区根（默认 ALLIN_REPOS_ROOT 或仓根父目录）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--unknown-policy", choices=["observe", "warn", "fail"], default="warn",
                    help="探针不可用（未知项目）的处置：observe=静默跳过 / warn=列出交人工（默认）/ fail=阻断")
    args = ap.parse_args(argv)
    if args.root is None:
        import os
        args.root = os.environ.get("ALLIN_REPOS_ROOT") or str(
            Path(__file__).resolve().parents[2].parent)

    try:
        cat = fetch(args.root)
        validate(cat)
    except Exception as exc:                              # noqa: BLE001
        print(f"CONTRACT FAIL: {exc}", file=sys.stderr)
        return 2

    written = skipped = 0
    for row in cat["rows"]:
        if not row.get("launch"):
            skipped += 1                                  # 未知项目：绝不伪造启动命令
            if args.unknown_policy == "fail":
                raise RuntimeError(f"未知项目 {row['id']}：探针不可用且 --unknown-policy=fail")
            if args.unknown_policy == "warn":
                print(f"  WARN 未知项目 {row['id']}：探针不可用，交人工（不写入观测态）", file=sys.stderr)
            continue
        obj = {
            "id": row["id"],
            "path": row["path"],
            "checkout": row.get("checkout", "local"),
            "launch": row["launch"],
            "publish": row["publish"],
            "_origin": "scan",
            "_scanned_at": cat["generated_at"],
            "_note": "由 allin-governance scan --catalog 产出（机器观测态）；人工语义在 registry/projects/。",
        }
        target = OBSERVED_DIR / f"{row['id']}.json"
        if not args.dry_run:
            OBSERVED_DIR.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
    verb = "将" if args.dry_run else "已"
    print(f"== {verb}写 {written} 条观测态；{skipped} 条探针不可用（交人工，不伪造）")
    print("== 人工目录 registry/projects/ 未被触碰；govrule registry.observed 判据负责审批")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
