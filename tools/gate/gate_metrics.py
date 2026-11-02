# -*- coding: utf-8 -*-
"""Turn the gate execution trail into the governance metrics.

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
4. **性能预算 (gate latency budget)** -- how long each check takes against a
   budget. The literature is unsubtle here: a check that takes minutes gets
   skipped, worked around, or switched off, and then it is not a control at all.
   Reported per label as p50 / p95 / max; p95 over budget is what counts, so a
   single cold-start outlier does not condemn a fast gate.
5. **agent 执行观测 (agent execution observability)** -- 第 5 类指标（2026-11-02 新增）：
   前四类全部只答「仓库体检做得怎么样」，没有一个能答 AgentOps 的核心问题 ——
   **agent 这次任务走了几步、成了没有、卡在哪一步**。数据来自
   `tools/gate/audit/agent-runs.jsonl`（MCP 每次工具调用落一个 span，
   字段向 OTel GenAI 语义约定对齐）。口径：一次 MCP 会话 = 一个 trace；
   会话内全部调用成功才算一次做完（对应 AgentOps 的 escalation rate 口径）；
   步数越多越可能绕圈 ⇒ 对应「步数预算 + 熔断器」。

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
AGENT_TRAIL = AUDIT / "agent-runs.jsonl"
SNAPSHOTS = AUDIT / "exceptions-snapshots.jsonl"
BASELINES = ROOT / "gate" / "governance" / "baseline"
EXEMPTIONS = AUDIT / "repo_hygiene_exemptions.csv"

FRESH_HOURS = 24
AGING_DAYS = 7
BUDGET_MS = 60_000          # 门禁研究共识：单次检查应 < 60s，慢过这条线的门禁会被绕过


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
    if rows and rows[0].lower().startswith(("rule", "check")):
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


def percentile(values: list[int], fraction: float) -> int:
    """Nearest-rank percentile; the sample is tiny, so no interpolation games."""
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def latency(runs: list[dict], budget_ms: int) -> dict:
    """Per-label latency against the budget; p95 over budget is the verdict."""
    by_label: dict[str, list[int]] = {}
    for run in runs:
        try:
            by_label.setdefault(str(run.get("label", "")), []).append(int(run.get("ms", 0)))
        except (TypeError, ValueError):
            continue
    per_label = []
    for label, samples in sorted(by_label.items()):
        p95 = percentile(samples, 0.95)
        per_label.append({
            "label": label, "n": len(samples),
            "p50": percentile(samples, 0.5), "p95": p95, "max": max(samples),
            "over_budget": p95 > budget_ms,
        })
    per_label.sort(key=lambda item: -item["p95"])
    return {"budget_ms": budget_ms, "per_label": per_label,
            "over_budget": [item["label"] for item in per_label if item["over_budget"]]}


# ---------------------------------------------------------------- agent ops
# 第五类指标（2026-11-02）：**agent 侧**执行观测。
#
# 为什么门禁指标还不够：①②③④ 全部只答「仓库体检做得怎么样」——
# 逃逸率、新鲜度、例外燃尽、门禁延迟。没有一个能答 AgentOps 的核心问题：
#
#     **agent 这次任务走了几步、成了没有、卡在哪一步？**
#
# AgentOps 的失败模式不是「模型说错了」，而是「做了无法解释、无法回滚的动作」。
# 要解释一个动作，先得有动作序列 —— 这就是 `agent-runs.jsonl` 的职责。
#
# 口径（刻意保守，避免指标自欺）：
#   * **一次会话 = 一个 trace**（MCP 走 stdio JSON-RPC，进程即会话）；
#   * **会话成败**：该会话内**全部**工具调用都成功 ⇒ ok；只要有一次 error ⇒ failed。
#     （AgentOps 的「escalation rate」同源：能不能一次做完，比做得多快更重要。）
#   * **步数**：span 数 —— 步数越多越可能绕圈（呼应「步数预算 + 熔断器」）。
def agent_ops(spans: list[dict]) -> dict:
    """Agent execution metrics: session success rate + step distribution.

    **口径的坑（2026-11-02 实测发现）**：工具返回 `isError` 有两种截然不同的含义 ——
      ① **业务性拒绝**：agent 主动试了危险路径，被策略挡住（如缺 `confirm=true`、未知工具名）。
         这是**治理机制正常工作**，是一次**成功**的验证，不该算「agent 任务失败」；
      ② **真正失败**：工具崩了/超时/结果不可用。
    早期版本把两者都算 error ⇒ 自检跑完「一次做完率 0%」，把**机制生效**误报成**任务失败** ——
    这类指标自欺比没指标更糟。
    ⇒ 现在按 `error_kind` 区分：`rejected`（业务拒绝，不计失败）/ `failed`（真失败）/ 未标注则按 failed（保守）。
    """
    sessions: dict[str, list[dict]] = {}
    for span in spans:
        trace_id = str(span.get("trace_id") or span.get("session_id") or "")
        if not trace_id:
            continue
        sessions.setdefault(trace_id, []).append(span)

    if not sessions:
        return {"state": "no-evidence", "sessions": 0, "spans": 0,
                "success_rate": None, "steps_p50": 0, "steps_p95": 0, "steps_max": 0,
                "by_tool": [], "failed_traces": [], "rejected_calls": 0, "failed_calls": 0}

    def kind_of(span: dict) -> str:
        kind = str(span.get("error_kind") or "")
        if kind:
            return kind
        return "failed" if not bool(span.get("ok")) else "ok"

    step_counts = [len(items) for items in sessions.values()]
    rejected_total = sum(1 for span in spans if kind_of(span) == "rejected")
    failed_total = sum(1 for span in spans if kind_of(span) == "failed")
    failed_traces = [tid for tid, items in sessions.items()
                     if any(kind_of(item) == "failed" for item in items)]

    by_tool: dict[str, dict] = {}
    for span in spans:
        name = str(span.get("tool") or span.get("gen_ai.tool.name") or "")
        if not name:
            continue
        slot = by_tool.setdefault(name, {"tool": name, "calls": 0, "errors": 0,
                                         "rejected": 0, "total_ms": 0})
        slot["calls"] += 1
        kind = kind_of(span)
        if kind == "failed":
            slot["errors"] += 1
        elif kind == "rejected":
            slot["rejected"] += 1
        try:
            slot["total_ms"] += int(span.get("ms", 0))
        except (TypeError, ValueError):
            pass
    tool_rows = sorted(by_tool.values(), key=lambda item: -item["calls"])

    # 按 tier 聚合（read / write-reversible / write-irreversible）—— 对应「工具面三级权限」的观测面。
    by_tier: dict[str, dict] = {}
    for span in spans:
        tier = str(span.get("tier") or "read")
        slot = by_tier.setdefault(tier, {"tier": tier, "calls": 0, "failed": 0, "rejected": 0})
        slot["calls"] += 1
        kind = kind_of(span)
        if kind == "failed":
            slot["failed"] += 1
        elif kind == "rejected":
            slot["rejected"] += 1

    ok_sessions = len(sessions) - len(failed_traces)
    return {
        "state": "ok",
        "sessions": len(sessions),
        "spans": len(spans),
        "success_rate": round(ok_sessions / len(sessions), 4),
        "failed_sessions": len(failed_traces),
        "rejected_calls": rejected_total,
        "failed_calls": failed_total,
        "steps_p50": percentile(step_counts, 0.5),
        "steps_p95": percentile(step_counts, 0.95),
        "steps_max": max(step_counts),
        "by_tool": tool_rows,
        "by_tier": by_tier,
        "failed_traces": failed_traces[:10],
    }


def build_metrics(runs: list[dict], days: int, budget_ms: int = BUDGET_MS) -> dict:
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
    agent_spans = load_runs(AGENT_TRAIL)
    agent_window = [span for span in agent_spans if in_window(span, since)]
    return {
        "window_days": days,
        "runs_total": len(runs),
        "runs_in_window": len(window),
        "escape_rate": round(escape_rate, 4),
        "failed_runs": len(failed),
        "failing_labels": sorted({str(run.get("label", "")) for run in failed})[:10],
        "evidence_freshness": freshness,
        "exceptions": {"total": total_exceptions, "by_source": exceptions},
        "latency": latency(window, budget_ms),
        "agent_ops": agent_ops(agent_window),
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
    perf = metrics["latency"]
    lines.append(f"  ④ 性能预算：预算 {perf['budget_ms']} ms（p95 超限即计）"
                 f"　超限 {len(perf['over_budget'])}/{len(perf['per_label'])} 项")
    for item in perf["per_label"][:6]:
        flag = "超限" if item["over_budget"] else "ok"
        lines.append(f"       - [{flag}] {item['label']}：p50 {item['p50']}ms / "
                     f"p95 {item['p95']}ms / max {item['max']}ms（n={item['n']}）")
    # ⑤ agent 侧执行观测（AgentOps）：会话成功率 + 步数分布
    agent = metrics.get("agent_ops") or {}
    if agent.get("state") != "ok":
        lines.append("  ⑤ agent 执行观测：无证据（还没有 agent 工具调用留痕）")
    else:
        rate = agent["success_rate"]
        lines.append(f"  ⑤ agent 执行观测：会话 {agent['sessions']} 次 / span {agent['spans']} 个"
                     f"　一次做完率 {rate * 100:.1f}%"
                     f"（失败会话 {agent['failed_sessions']}）")
        lines.append(f"       步数：p50 {agent['steps_p50']} / p95 {agent['steps_p95']} / max {agent['steps_max']}"
                     f"（步数越多越可能绕圈 ⇒ 对应「步数预算 + 熔断器」）")
        lines.append(f"       调用分类：策略拒绝 {agent.get('rejected_calls', 0)} 次"
                     f"（治理机制生效，不计失败）／真失败 {agent.get('failed_calls', 0)} 次")
        for item in agent["by_tool"][:6]:
            detail = ""
            if item.get("errors"):
                detail += f"，失败 {item['errors']}"
            if item.get("rejected"):
                detail += f"，拒绝 {item['rejected']}"
            lines.append(f"       - {item['tool']}：调用 {item['calls']} 次"
                         f"，累计 {item['total_ms']}ms{detail}")
        tier_order = ["read", "write-reversible", "write-irreversible"]
        tiers = agent.get("by_tier", {})
        if tiers:
            parts = []
            for t in tier_order:
                if t in tiers:
                    slot = tiers[t]
                    flag = f"失败{slot['failed']}" if slot["failed"] else "ok"
                    parts.append(f"{t} {slot['calls']} 次（{flag}）")
            lines.append(f"       工具面分级：{' ｜ '.join(parts)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="governance metrics from the gate execution trail")
    parser.add_argument("--trail", default=str(TRAIL), help=f"gate run trail (default: {TRAIL})")
    parser.add_argument("--days", type=int, default=30, help="window for the escape rate (default 30)")
    parser.add_argument("--budget", type=int, default=BUDGET_MS,
                        help=f"latency budget in ms for metric 4 (default {BUDGET_MS})")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--snapshot", action="store_true", help="append the current exception count to the trend file")
    args = parser.parse_args(argv)

    path = Path(args.trail)
    if not path.is_file():
        print(f"ENV ERROR: 没有执行留痕：{path}（先跑 bash scripts/run_all_gates.sh）")
        return 3
    runs = load_runs(path)
    metrics = build_metrics(runs, args.days, args.budget)
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
