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
# 历史留痕（589 行，2026-10-28 起）没有 batch 字段。按「同 commit + 相邻记录间隔
# <= 该秒数」把连续执行推断成一次跑批；一次跑批内单条门禁远快于 5 分钟，
# 而两次独立跑批之间通常远超这个间隔（实测同秒连跑也由 PID 后缀区分）。
BATCH_GAP_SECONDS = 300


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


def _aware(stamp: datetime | None) -> datetime | None:
    """统一成 tz-aware，避免 naive/aware 混比抛 TypeError（历史行可能不带 Z）。"""
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp


def in_window(run: dict, since: datetime) -> bool:
    stamp = _aware(parse_ts(str(run.get("ts", ""))))
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


# --------------------------------------------------------------- 跑批口径
def group_batches(runs: list[dict]) -> list[tuple[str, list[dict], bool]]:
    """把执行留痕按「一次跑批」分组，返回 [(key, items, inferred)]。

    优先用 `run_all_gates.sh` 写入的 `batch` 字段（精确，同一批共享一个 RUN_ID）；
    历史行（无 batch）按「同 commit + 相邻间隔 <= BATCH_GAP_SECONDS」聚类推断，
    标记 inferred=True，以便输出时如实说明这是推断而非确证。

    **为什么不能再按 ts[:19] 秒级分组**：一次跑批要跑十几条门禁、跨几十秒，
    秒级分组会把它拆成几十个「秒组」；只要某一秒恰好没有失败记录，旧口径就把
    那一秒当作「最近一次全绿」，于是一次有失败的跑批照样报 fresh —— 假绿。
    证据新鲜度必须回答「最近一次完整跑批全绿了吗」，不是「某一秒内没红吗」。
    """
    explicit: dict[str, list[dict]] = {}
    legacy: list[dict] = []
    for run in runs:
        batch = str(run.get("batch") or "").strip()
        if batch:
            explicit.setdefault(batch, []).append(run)
        else:
            legacy.append(run)
    groups: list[tuple[str, list[dict], bool]] = [
        (key, items, False) for key, items in explicit.items()
    ]
    if legacy:
        epoch = datetime.min.replace(tzinfo=timezone.utc)
        ordered = sorted(
            legacy,
            key=lambda r: (_aware(parse_ts(str(r.get("ts", "")))) or epoch,
                           str(r.get("commit", ""))),
        )
        cluster: list[dict] = []
        last_stamp: datetime | None = None
        last_commit = ""
        for run in ordered:
            stamp = _aware(parse_ts(str(run.get("ts", ""))))
            commit = str(run.get("commit", ""))
            gap = ((stamp - last_stamp).total_seconds()
                   if (stamp is not None and last_stamp is not None) else 0)
            if cluster and (gap > BATCH_GAP_SECONDS or commit != last_commit):
                groups.append((f"legacy#{len(groups)}", cluster, True))
                cluster = []
            cluster.append(run)
            last_stamp = stamp
            last_commit = commit
        if cluster:
            groups.append((f"legacy#{len(groups)}", cluster, True))
    return groups


def batch_stamp(items: list[dict]) -> datetime | None:
    stamps = [_aware(parse_ts(str(r.get("ts", "")))) for r in items]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


# --------------------------------------------------------------- SKIP 单列口径
# SKIP ≠ 通过。落盘 `skipped` 字段把「真跑」与「SKIP」分开：后者不计入
# failed / escapeRate / lastOkAt，整批全 SKIP 的跑批也不得伪装成全绿。
# 旧留痕（无 `skipped` 字段）一律按真跑兼容回放，历史全绿仍算全绿。
def is_skipped(run: dict) -> bool:
    """仅当显式 `skipped is True` 才算 SKIP；旧行无字段 ⇒ 按真跑处理（兼容回放）。"""
    return run.get("skipped") is True


def real_runs(runs: list[dict]) -> list[dict]:
    """过滤掉 SKIP 行，只留真跑记录（旧行无字段 ⇒ 按真跑处理）。"""
    return [r for r in runs if not is_skipped(r)]


def escape_rate_of(window: list[dict]) -> float:
    """逃逸率：分母只算真跑；空真跑集合返回 0.0。"""
    real = real_runs(window)
    if not real:
        return 0.0
    failed = sum(1 for r in real if int(r.get("exit", 0)) != 0)
    return failed / len(real)


def batch_verdict(runs: list[dict], now: datetime) -> dict:
    """证据新鲜度：按整批判定全绿（纯函数，不读磁盘，供 --selfcheck 注入验证）。

    整组全是 SKIP 的批次不算全绿（`real` 为空 ⇒ ok=False）；SKIP 单列计数
    通过 `skipped_runs` / `batches_with_skips` 一并返回。
    """
    stamps = [_aware(parse_ts(str(r.get("ts", "")))) for r in runs]
    stamps = [s for s in stamps if s is not None]
    newest = max(stamps) if stamps else None

    groups = group_batches(runs)
    skipped_runs = sum(1 for r in runs if is_skipped(r))
    batches_with_skips = sum(
        1 for _key, items, _inferred in groups if any(is_skipped(r) for r in items)
    )
    greens: list[tuple[datetime, bool, int]] = []
    last_stamp: datetime | None = None
    last_ok: bool | None = None
    for _key, items, inferred in groups:
        real = real_runs(items)
        # 整组全是 SKIP ⇒ real 为空 ⇒ ok=False，不得伪装成全绿。
        ok = bool(real) and all(int(r.get("exit", 0)) == 0 for r in real)
        stamp = batch_stamp(items)
        if ok and stamp is not None:
            greens.append((stamp, inferred, len(items)))
        if stamp is not None and (last_stamp is None or stamp > last_stamp):
            last_stamp, last_ok = stamp, ok

    newest_green = max(greens, key=lambda g: g[0]) if greens else None
    green_at = newest_green[0] if newest_green else None
    if newest is None:
        return {"state": "no-evidence", "age_hours": None, "last_run": None,
                "last_green": None, "last_green_inferred": None,
                "green_batches": 0, "batches": len(groups), "last_batch_ok": None,
                "skipped_runs": skipped_runs, "batches_with_skips": batches_with_skips}

    anchor = green_at or newest
    age = (now - anchor).total_seconds() / 3600.0
    if last_ok is False:
        state = "last-batch-red"
    elif green_at is None:
        state = "no-green-batch"
    else:
        state = "fresh" if age <= FRESH_HOURS else ("aging" if age <= AGING_DAYS * 24 else "stale")
    return {
        "state": state,
        "age_hours": round(age, 1),
        "last_run": newest.isoformat(),
        "last_green": green_at.isoformat() if green_at else None,
        "last_green_inferred": newest_green[1] if newest_green else None,
        "green_batches": len(greens),
        "batches": len(groups),
        "last_batch_ok": last_ok,
        "skipped_runs": skipped_runs,
        "batches_with_skips": batches_with_skips,
    }


def build_metrics(runs: list[dict], days: int, budget_ms: int = BUDGET_MS) -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    window = [run for run in runs if in_window(run, since)]

    window_real = real_runs(window)
    failed = [run for run in window_real if int(run.get("exit", 0)) != 0]
    # 逃逸率分母只算真跑；SKIP 单列计数，不进 failed / escapeRate。
    escape_rate = escape_rate_of(window)

    # 证据新鲜度改为按「一次跑批」判定，旧秒级分组会把红批洗成 fresh（见 group_batches）。
    freshness = batch_verdict(runs, now)

    exceptions = count_exceptions()
    total_exceptions = sum(exceptions.values())
    agent_spans = load_runs(AGENT_TRAIL)
    agent_window = [span for span in agent_spans if in_window(span, since)]
    return {
        "window_days": days,
        "runs_total": len(runs),
        "runs_in_window": len(window),
        "runs_in_window_real": len(window_real),
        "skipped_runs": len(window) - len(window_real),
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
                 f"（{metrics['failed_runs']}/{metrics['runs_in_window_real']} 真跑；"
                 f"SKIP {metrics['skipped_runs']} 单列）")
    for label in metrics["failing_labels"]:
        lines.append(f"       - 曾失败：{label}")
    fresh = metrics["evidence_freshness"]
    if fresh["state"] == "no-evidence":
        lines.append("  ② 证据新鲜度：无证据（还没跑过门禁）")
    else:
        green = fresh.get("last_green")
        batches = fresh.get("batches", 0)
        greens = fresh.get("green_batches", 0)
        if fresh.get("last_batch_ok") is False:
            lines.append(f"  ② 证据新鲜度：{fresh['state']} —— 最近一次跑批有失败，"
                         f"不算全绿证据（{greens}/{batches} 个批次全绿）")
        elif green is None:
            lines.append(f"  ② 证据新鲜度：{fresh['state']} —— 有执行留痕，"
                         f"但没有可证明的全绿批次（0/{batches}）")
        else:
            inferred = "（按时间邻近推断，历史留痕无 batch 字段）" if fresh.get("last_green_inferred") else ""
            lines.append(f"  ② 证据新鲜度：{fresh['state']}（最近一次全绿批次距今 "
                         f"{fresh['age_hours']} 小时；{greens}/{batches} 个批次全绿）")
            lines.append(f"       最近全绿：{green}{inferred}")
        lines.append(f"       最近执行：{fresh['last_run']}")
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


def selfcheck() -> int:
    """注入式自证：秒级假绿必须被挡住，真全绿必须被认出（不读磁盘留痕）。

    五个方向：
      ① legacy 跨秒批次含一条失败、且最晚那一秒单独成功 ⇒ 不得判全绿
         （这正是旧 ts[:19] 口径的假绿复现：那一秒会被当成「最近一次全绿」）；
      ② 显式 batch 的一批含失败 ⇒ 不得判全绿，last_batch_ok=False；
      ③ 显式 batch 的一批全成功 ⇒ 能算出 last_green；
      ④ 先绿后红两批 ⇒ 最近批次红，但仍有更早的全绿批次可报；
      ⑤ SKIP 单列口径（可证伪 + legacy 兼容回放）：整批只有 SKIP 绿不得算全绿、
         真跑红 + SKIP 绿不判全绿、无 skipped 字段的 legacy 全绿仍算全绿、
         3 行含 1 SKIP + 1 真跑红 ⇒ 分母 2 / failed 1 / escape_rate 0.5。
         把 is_skipped 改成恒 False 时本方向必红（SELFCHECK_FAILED / exit 3）。
    """
    print("== 治理度量 自测（跑批口径反假绿） ==")
    now = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
    ok = True

    legacy_red = [
        {"ts": "2026-11-04T11:59:58Z", "commit": "c1", "label": "a", "exit": 0, "ms": 10},
        {"ts": "2026-11-04T11:59:59Z", "commit": "c1", "label": "b", "exit": 1, "ms": 10},
        {"ts": "2026-11-04T12:00:00Z", "commit": "c1", "label": "c", "exit": 0, "ms": 10},
    ]
    v1 = batch_verdict(legacy_red, now)
    print("  ① 跨秒批次含失败不判全绿:      %s  [last_green=%s, last_batch_ok=%s]"
          % ("✔" if v1["last_green"] is None and v1["last_batch_ok"] is False else "✘",
             v1["last_green"], v1["last_batch_ok"]))
    ok &= v1["last_green"] is None and v1["last_batch_ok"] is False

    explicit_red = [
        {"ts": "2026-11-04T11:59:58Z", "batch": "run-1", "commit": "c1", "label": "a", "exit": 0, "ms": 10},
        {"ts": "2026-11-04T11:59:59Z", "batch": "run-1", "commit": "c1", "label": "b", "exit": 1, "ms": 10},
        {"ts": "2026-11-04T12:00:00Z", "batch": "run-1", "commit": "c1", "label": "c", "exit": 0, "ms": 10},
    ]
    v2 = batch_verdict(explicit_red, now)
    print("  ② 显式 batch 含失败不判全绿:   %s"
          % ("✔" if v2["last_green"] is None and v2["last_batch_ok"] is False else "✘"))
    ok &= v2["last_green"] is None and v2["last_batch_ok"] is False

    explicit_green = [dict(r, exit=0, batch="run-2") for r in explicit_red]
    v3 = batch_verdict(explicit_green, now)
    print("  ③ 显式 batch 全绿能算出全绿:   %s  [%s]"
          % ("✔" if v3["last_green"] and v3["last_batch_ok"] is True else "✘", v3["last_green"]))
    ok &= bool(v3["last_green"]) and v3["last_batch_ok"] is True

    mixed = explicit_red + [
        {"ts": "2026-11-04T11:59:00Z", "batch": "run-0", "commit": "c1", "label": "z", "exit": 0, "ms": 10},
    ]
    v4 = batch_verdict(mixed, now)
    print("  ④ 先绿后红：最近批次红仍保留更早全绿: %s"
          % ("✔" if v4["last_batch_ok"] is False and bool(v4["last_green"]) else "✘"))
    ok &= v4["last_batch_ok"] is False and bool(v4["last_green"])

    # ⑤ SKIP 单列口径：整批 SKIP 不得伪装全绿（核心可证伪点）、真跑红 + SKIP 绿不判全绿、
    #    legacy 无 skipped 字段仍判全绿（兼容回放）、真跑分母/逃逸率断言。
    all_skip = [
        {"ts": "2026-11-04T11:59:58Z", "batch": "run-s", "commit": "c1",
         "label": "a", "exit": 0, "ms": 0, "skipped": True},
        {"ts": "2026-11-04T11:59:59Z", "batch": "run-s", "commit": "c1",
         "label": "b", "exit": 0, "ms": 0, "skipped": True},
    ]
    v5a = batch_verdict(all_skip, now)
    a5 = v5a["last_green"] is None and v5a["last_batch_ok"] is False

    red_plus_skip = [
        {"ts": "2026-11-04T11:59:58Z", "batch": "run-m", "commit": "c1",
         "label": "real-red", "exit": 1, "ms": 10},
        {"ts": "2026-11-04T11:59:59Z", "batch": "run-m", "commit": "c1",
         "label": "skip-a", "exit": 0, "ms": 0, "skipped": True},
        {"ts": "2026-11-04T12:00:00Z", "batch": "run-m", "commit": "c1",
         "label": "skip-b", "exit": 0, "ms": 0, "skipped": True},
    ]
    v5b = batch_verdict(red_plus_skip, now)
    b5 = v5b["last_green"] is None and v5b["last_batch_ok"] is False

    legacy_green = [
        {"ts": "2026-11-04T11:59:58Z", "batch": "run-l", "commit": "c1",
         "label": "a", "exit": 0, "ms": 10},
        {"ts": "2026-11-04T11:59:59Z", "batch": "run-l", "commit": "c1",
         "label": "b", "exit": 0, "ms": 10},
    ]
    v5c = batch_verdict(legacy_green, now)
    c5 = bool(v5c["last_green"]) and v5c["last_batch_ok"] is True

    mixed3 = [
        {"ts": "2026-11-04T11:59:58Z", "label": "skip", "exit": 0, "ms": 0, "skipped": True},
        {"ts": "2026-11-04T11:59:59Z", "label": "real-red", "exit": 1, "ms": 10},
        {"ts": "2026-11-04T12:00:00Z", "label": "real-ok", "exit": 0, "ms": 10},
    ]
    real3 = real_runs(mixed3)
    failed3 = [r for r in real3 if int(r.get("exit", 0)) != 0]
    d5 = (len(real3) == 2 and len(failed3) == 1
          and abs(escape_rate_of(mixed3) - 0.5) < 1e-9)

    v5 = a5 and b5 and c5 and d5
    print("  ⑤ SKIP 单列 + legacy 兼容回放:    %s  [整批SKIP不绿=%s, 真跑红+SKIP不绿=%s, "
          "legacy全绿=%s, 分母=%s/failed=%s/rate=%s]"
          % ("✔" if v5 else "✘", a5, b5, c5, len(real3), len(failed3),
             escape_rate_of(mixed3)))
    ok &= v5

    print("SELFCHECK_%s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="governance metrics from the gate execution trail")
    parser.add_argument("--trail", default=str(TRAIL), help=f"gate run trail (default: {TRAIL})")
    parser.add_argument("--days", type=int, default=30, help="window for the escape rate (default 30)")
    parser.add_argument("--budget", type=int, default=BUDGET_MS,
                        help=f"latency budget in ms for metric 4 (default {BUDGET_MS})")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--snapshot", action="store_true", help="append the current exception count to the trend file")
    parser.add_argument("--selfcheck", action="store_true", help="inject-and-prove the batch verdict (no trail needed)")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

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
