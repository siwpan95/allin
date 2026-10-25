"""报告渲染：文本 / CSV / HTML / JSON 四通道，以及汇总统计。

所有渲染函数都接受 ``check_project()`` 返回的结果字典列表，
``min_severity`` 只影响输出内容，不影响健康分。
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from rulebase import RANK, WEIGHTS

# ---------------------------------------------------------------------------
# 颜色
# ---------------------------------------------------------------------------

_COLOR = {
    "error": "\033[31m",
    "warn": "\033[33m",
    "info": "\033[90m",
    "ok": "\033[32m",
    "dim": "\033[90m",
    "reset": "\033[0m",
}


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_COLOR.get(color, '')}{text}{_COLOR['reset']}"


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def summarize(results: list[dict]) -> dict:
    """对整个扫描结果做汇总统计。"""
    counts = {"error": 0, "warn": 0, "info": 0}
    scores: list[float] = []
    degraded: set[int] = set()
    skipped = 0
    rule_errors: list[dict] = []
    total_w = passed_w = 0

    for result in results:
        scores.append(float(result.get("score", 0.0)))
        for finding in result.get("findings", []):
            weight = WEIGHTS.get(finding["severity"], 1)
            total_w += weight
            if finding["passed"]:
                passed_w += weight
            else:
                counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
            if finding.get("degraded"):
                degraded.add(finding["id"])
        skipped += len(result.get("skipped", []))
        rule_errors.extend(result.get("rule_errors", []))

    return {
        "projects": len(results),
        "errors": counts["error"],
        "warns": counts["warn"],
        "infos": counts["info"],
        "score_mean": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "score_min": round(min(scores), 1) if scores else 0.0,
        "pass_rate": round(passed_w / total_w, 3) if total_w else 0.0,
        "skipped_count": skipped,
        "degraded_rules": sorted(degraded),
        "rule_errors": rule_errors,
    }


# ---------------------------------------------------------------------------
# 文本
# ---------------------------------------------------------------------------

def render_text(results: list[dict], *, root: str = "", min_severity: str = "info",
                color: bool = False, summary: dict | None = None) -> str:
    """人读文本报告。"""
    summary = summary or summarize(results)
    floor = RANK.get(min_severity, 0)
    lines: list[str] = []

    if root:
        lines.append(f"根目录：{root}")
    lines.append(f"发现项目数：{summary['projects']}")
    if summary["projects"]:
        lines.append(
            f"健康分：均值 {summary['score_mean']} / 最低 {summary['score_min']}"
            f"　通过率 {summary['pass_rate']:.0%}"
        )
    lines.append("")

    for result in results:
        score = float(result.get("score", 0.0))
        tone = "ok" if score >= 8 else ("warn" if score >= 6 else "error")
        head = f"== {result['name']}  ({result['path']})"
        lines.append(f"{head}  {_paint(f'健康分 {score}', tone, color)}")

        shown = [
            f for f in result.get("findings", [])
            if not f["passed"] and RANK.get(f["severity"], 0) >= floor
        ]
        if shown:
            for finding in sorted(shown, key=lambda f: -RANK.get(f["severity"], 0)):
                detail = f"：{finding['detail']}" if finding["detail"] else ""
                tag = _paint(f"[{finding['severity']}]", finding["severity"], color)
                lines.append(f"   {tag} {finding['label']}{detail}")
        else:
            lines.append(f"   {_paint('✓ 无达到阈值的问题', 'ok', color)}")

        skipped = result.get("skipped", [])
        if skipped:
            reasons = sorted({s["reason"] for s in skipped})
            lines.append(_paint(
                f"   (跳过 {len(skipped)} 项：{', '.join(reasons)})", "dim", color))
        for err in result.get("rule_errors", []):
            lines.append(_paint(f"   [内部错误] 规则 {err['id']}：{err['error']}", "error", color))
        lines.append("")

    degraded = summary.get("degraded_rules") or []
    if degraded:
        ids = ", ".join(str(i) for i in degraded)
        lines.append(f"提示：规则 {ids} 使用内置降级实现（未安装对应可选依赖，结论口径不变）")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

CSV_HEADER = ["项目路径", "健康分", "error", "warn", "info", "问题数", "问题标签"]


def render_csv(results: list[dict], *, min_severity: str = "info") -> str:
    """CSV 文本（调用方负责加 BOM 写入时用 utf-8-sig）。"""
    floor = RANK.get(min_severity, 0)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for result in results:
        counts = result.get("severity_counts") or {}
        labels = [
            f["label"] + (f"：{f['detail']}" if f["detail"] else "")
            for f in result.get("findings", [])
            if not f["passed"] and RANK.get(f["severity"], 0) >= floor
        ]
        writer.writerow([
            result["path"],
            result.get("score", 0.0),
            counts.get("error", 0),
            counts.get("warn", 0),
            counts.get("info", 0),
            # 与「问题标签」列同源，避免「问题数 10 但列了 12 条」的自相矛盾
            len(labels),
            "；".join(labels),
        ])
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML 转义，避免报告注入/错位。"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _score_color(score: float) -> str:
    if score >= 8:
        return "#137333"
    if score >= 6:
        return "#e37400"
    return "#d93025"


_SEV_CLASS = {"error": "sev-error", "warn": "sev-warn", "info": "sev-info"}

_HTML_STYLE = """
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:24px;color:#202124;background:#fff}
h1{font-size:20px;margin:0 0 4px}
.meta{color:#5f6368;font-size:13px;margin-bottom:16px}
.cards{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.card{border:1px solid #dadce0;border-radius:8px;padding:10px 16px;min-width:110px}
.card .k{font-size:12px;color:#5f6368}
.card .v{font-size:20px;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border:1px solid #dadce0;padding:6px 10px;text-align:left;vertical-align:top}
th{background:#f1f3f4;font-weight:600;position:sticky;top:0}
tr:nth-child(even) td{background:#fafafa}
.score{font-weight:600;text-align:center;white-space:nowrap}
.sev-error{color:#d93025;font-weight:600}
.sev-warn{color:#e37400}
.sev-info{color:#5f6368}
.pill{display:inline-block;border-radius:10px;padding:0 8px;font-size:12px;margin-right:4px}
.pill.error{background:#fce8e6;color:#c5221f}
.pill.warn{background:#fef7e0;color:#b06000}
.pill.info{background:#f1f3f4;color:#5f6368}
.note{color:#5f6368;font-size:12px;margin-top:16px;line-height:1.7}
code{background:#f1f3f4;border-radius:3px;padding:1px 4px}
"""


def render_html(results: list[dict], *, root: str = "", min_severity: str = "info",
                summary: dict | None = None, version: str = "") -> str:
    """自包含单页 HTML 报告（无外部资源，可直接发出去）。"""
    summary = summary or summarize(results)
    floor = RANK.get(min_severity, 0)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    rows: list[str] = []
    for result in results:
        counts = result.get("severity_counts") or {}
        score = float(result.get("score", 0.0))
        items = [
            f'<div class="sev-{f["severity"]}">[{f["severity"]}] {_esc(f["label"])}'
            + (f'：{_esc(f["detail"])}' if f["detail"] else "")
            + "</div>"
            for f in sorted(result.get("findings", []),
                            key=lambda f: -RANK.get(f["severity"], 0))
            if not f["passed"] and RANK.get(f["severity"], 0) >= floor
        ]
        skipped = result.get("skipped", [])
        if skipped:
            items.append(f'<div class="sev-info">（跳过 {len(skipped)} 项：'
                         f'{_esc(", ".join(sorted({s["reason"] for s in skipped})))}）</div>')
        if not items:
            items.append('<div class="sev-info">✓ 无达到阈值的问题</div>')

        rows.append(
            "<tr>"
            f"<td><code>{_esc(result['path'])}</code></td>"
            f'<td class="score" style="color:{_score_color(score)}">{score}</td>'
            f'<td><span class="pill error">E {counts.get("error", 0)}</span>'
            f'<span class="pill warn">W {counts.get("warn", 0)}</span>'
            f'<span class="pill info">I {counts.get("info", 0)}</span></td>'
            f"<td>{''.join(items)}</td>"
            "</tr>"
        )

    notes: list[str] = []
    if summary.get("degraded_rules"):
        ids = ", ".join(str(i) for i in summary["degraded_rules"])
        notes.append(f"规则 {ids} 使用内置降级实现（未安装对应可选依赖，结论口径不变）。")
    if summary.get("rule_errors"):
        notes.append(f"{len(summary['rule_errors'])} 条规则内部异常，已从评分分母剔除。")
    notes.append(
        "健康分 = 10 × log1p(通过项权重) / log1p(总权重)，权重 error=3 / warn=2 / info=1；"
        "公式压缩较强，请同时参考通过率。"
    )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>repocheck 仓库体检报告</title>
<style>{_HTML_STYLE}</style></head><body>
<h1>repocheck 仓库体检报告</h1>
<div class="meta">根目录 <code>{_esc(root)}</code>　生成于 {stamp}　repocheck {_esc(version)}</div>
<div class="cards">
  <div class="card"><div class="k">项目数</div><div class="v">{summary['projects']}</div></div>
  <div class="card"><div class="k">平均分</div><div class="v" style="color:{_score_color(summary['score_mean'])}">{summary['score_mean']}</div></div>
  <div class="card"><div class="k">最低分</div><div class="v" style="color:{_score_color(summary['score_min'])}">{summary['score_min']}</div></div>
  <div class="card"><div class="k">通过率</div><div class="v">{summary['pass_rate']:.0%}</div></div>
  <div class="card"><div class="k">error</div><div class="v sev-error">{summary['errors']}</div></div>
  <div class="card"><div class="k">warn</div><div class="v sev-warn">{summary['warns']}</div></div>
  <div class="card"><div class="k">info</div><div class="v sev-info">{summary['infos']}</div></div>
</div>
<table>
<thead><tr><th>项目路径</th><th>健康分</th><th>严重度</th><th>问题</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<div class="note">{'<br>'.join(_esc(n) for n in notes)}</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_payload(results: list[dict], *, root: str = "", version: str = "",
               schema: int = 2, optional: dict | None = None) -> dict:
    """组装 ``--format json`` 的完整载荷。"""
    summary = summarize(results)
    return {
        "tool": "repocheck",
        "schema": schema,
        "version": version,
        "root": root,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "summary": {
            "projects": summary["projects"],
            "errors": summary["errors"],
            "warns": summary["warns"],
            "infos": summary["infos"],
            "score_mean": summary["score_mean"],
            "score_min": summary["score_min"],
            "pass_rate": summary["pass_rate"],
            "skipped_count": summary["skipped_count"],
        },
        "engine": {
            "optional": optional or {},
            "degraded_rules": summary["degraded_rules"],
            "rule_errors": summary["rule_errors"],
        },
        "projects": [
            {
                "name": r["name"],
                "path": r["path"],
                "score": r.get("score", 0.0),
                "pass_rate": r.get("pass_rate", 0.0),
                "severity_counts": r.get("severity_counts", {}),
                "issues": r.get("issues", []),
                "findings": r.get("findings", []),
                "skipped": r.get("skipped", []),
                "rule_errors": r.get("rule_errors", []),
                "metrics": r.get("metrics", {}),
            }
            for r in results
        ],
    }


def dumps(payload: dict) -> str:
    """稳定的 JSON 文本（中文不转义，便于人读）。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)
