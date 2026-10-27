# -*- coding: utf-8 -*-
"""Turn the gate execution trail into the three governance metrics.

`scripts/run_all_gates.sh` appends one JSON line per executed check to
`tools/gate/audit/gate-runs.jsonl`. Without that trail a repository can only
say "the gates are green right now"; with it, governance can answer the three
questions that actually matter (and that an auditor asks first):

1. **门禁逃逸率 (gate escape rate)** -- how often a gate *failed* when it ran.
   A gate that is red half the time and silenced by a re-run is not a control,
   it is a speed bump.
2. **证据新鲜度 (evidence freshness)** -- how old the newest passing run is.
   Proof that is 40 days old is not proof of the current tree.
3. **例外燃尽 (exception burn-down)** -- how many frozen exceptions exist and
   whether the pile is shrinking. Every frozen baseline key and every hygiene
   exemption row is accepted risk; accepted risk has to be counted, and a count
   that never moves is a count nobody is working on.

The tool is a reporter, never a gate: it always exits 0 unless asked for an
unusable input (missing trail), where it exits 3 like the gates do.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # tools/
AUDIT = ROOT / "gate" / "audit"
TRAIL = AUDIT / "gate-runs.jsonl"
SNAPSHOTS = AUDIT / "exceptions-snapshots.jsonl"
BASELINES = ROOT / "gate" / "governance" / "baseline"
EXEMPTIONS = AUDIT / "repo_hygiene_exemptions.csv"

FRESH_HOURS = 24
AGING_DAYS = 7


def read_lines(path: Path) -> list[str]:
    """Read UTF-8 lines, or an empty list when the file is absent."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def load_runs(path: Path) -> list[dict]:
    runs: list[dict] = []
    for line in read_lines(path):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "ts" in record:
            runs.append(record)
    return runs


def parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def in_window(run: dict, since: datetime) -> bool:
    stamp = parse_ts(str(run.get("ts", "")))
    return stamp is not None and stamp >= since


def count_exceptions() -> dict[str, int]:
    """Frozen baseline keys per gate + hygiene exemption rows."""
    per_source: dict[str, int] = {}
    for path in sorted(BASELINES.glob("*.txt")) if BASELINES.is_dir() else []:
        keys = [ln.strip() for ln in read_lines(path)
                if ln.strip() and not ln.strip().startswith("#")]
        per_source[path.stem] = len(keys)
    rows = [ln.strip() for ln in read_lines(EXEMPTIONS)
            if ln.strip() and not ln.strip().startswith("#")]
    if rows and rows[0].lower().startswith("rule"):
        rows = rows[1:]
    per_source["repo_hygiene_exemptions.csv"] = len(rows)
    return per_source


def append_snapshot(total: int) -> None:
    """Append the current exception count so a trend can exist later."""
    try:
        AUDIT.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOTS, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                     "exceptions": total}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def previous_snapshot() -> int | None:
    lines = [ln for ln in read_lines(SNAPSHOTS) if ln.strip()]
    if len(lines) < 2:
        return None
    try:
        return int(json.loads(lines[-2]).get("exceptions", 0))
    except (json.JSONDecodeError, ValueError):
        return None


def build_metrics(runs: list[dict], days: int) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    window = [run for run in runs if in_window(run, since)]

    failed = [run for run in window if int(run.get("exit", 0)) != 0]
    escape_rate = (len(failed) / len(window)) if window else 0.0

    stamps = [parse_ts(str(run.get("ts", ""))) for run in runs]
    stamps = [stamp for stamp in stamps if stamp is not None]
    newest = max(stamps) if stamps else None
    # A "green batch" = the newest timestamp whose whole second-level group has no failure.
    green_at = None
    if stamps:
        by_ts: dict[str, list[dict]] = {}
        for run in runs:
            by_ts.setdefault(str(run.get("ts", ""))[:19], []).append(run)
        green_candidates = [key for key, items in by_ts.items()
                            if all(int(item.get("exit", 0)) == 0 for item in items)]
        if green_candidates:
            green_at = parse_ts(max(green_candidates) + "Z" if not max(green_candidates).endswith("Z")
                                else max(green_candidates))

    if newest is None:
        freshness = {"state": "no-evidence", "age_hours": None, "last_run": None, "last_green": None}
    else:
        age = (now - (green_at or newest)).total_seconds() / 3600.0
        state = "fresh" if age <= FRESH_HOURS else ("aging" if age <= AGING_DAYS * 24 else "stale")
        freshness = {"state": state, "age_hours": round(age, 1),
                     "last_run": newest.isoformat(),
                     "last_green": green_at.isoformat() if green_at else None}

    exceptions = count_exceptions()
    total_exceptions = sum(exceptions.values())
    return {
        "window_days": days,
        "runs_total": len(runs),
        "runs_in_window": len(window),
        "escape_rate": round(escape_rate, 4),
        "failed_runs": len(failed),
        "failing_labels": sorted({str(run.get("label", "")) for run in failed})[:10],
        "evidence_freshness": freshness,
        "exceptions": {"total": total_exceptions, "by_source": exceptions},
    }


def render(metrics: dict, previous: int | None) -> str:
    lines = [f"治理指标 @ {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
             f"  样本：{metrics['runs_total']} 次执行（近 {metrics['window_days']} 天 {metrics['runs_in_window']} 次）"]
    lines.append(f"  ① 门禁逃逸率：{metrics['escape_rate'] * 100:.1f}%"
                 f"（{metrics['failed_runs']}/{metrics['runs_in_window']}）")
    for label in metrics["failing_labels"]:
        lines.append(f"       - 曾失败：{label}")
    fresh = metrics["evidence_freshness"]
    if fresh["state"] == "no-evidence":
        lines.append("  ② 证据新鲜度：无证据（还没跑过门禁）")
    else:
        lines.append(f"  ② 证据新鲜度：{fresh['state']}（最近一次全绿距今 {fresh['age_hours']} 小时）")
        lines.append(f"       最近全绿：{fresh['last_green'] or '（无）'}")
    exc = metrics["exceptions"]
    delta = ""
    if previous is not None:
        change = exc["total"] - previous
        delta = f"，较上次 {change:+d}"
    lines.append(f"  ③ 例外燃尽：冻结/豁免共 {exc['total']} 条{delta}")
    for source, count in sorted(exc["by_source"].items(), key=lambda kv: -kv[1]):
        if count:
            lines.append(f"       - {source}: {count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="governance metrics from the gate execution trail")
    parser.add_argument("--trail", default=str(TRAIL), help=f"gate run trail (default: {TRAIL})")
    parser.add_argument("--days", type=int, default=30, help="window for the escape rate (default 30)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--snapshot", action="store_true", help="append the current exception count to the trend file")
    args = parser.parse_args(argv)

    path = Path(args.trail)
    if not path.is_file():
        print(f"ENV ERROR: 没有执行留痕：{path}（先跑 bash scripts/run_all_gates.sh）")
        return 3
    runs = load_runs(path)
    metrics = build_metrics(runs, args.days)
    previous = previous_snapshot()
    if args.snapshot:
        append_snapshot(metrics["exceptions"]["total"])
    if args.json:
        print(json.dumps({**metrics, "exceptions_previous": previous}, ensure_ascii=False, indent=2))
    else:
        print(render(metrics, previous))
    return 0


if __name__ == "__main__":
    sys.exit(main())
