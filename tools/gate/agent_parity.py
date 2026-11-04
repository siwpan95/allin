#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g21 · agent-parity —— routes.yaml ⇄ SKILL.md 锚点 ⇄ GOVERNANCE 段锚点 三方对账门禁。

设计依据（冻结基线 v3）：team 交付物 P2-智能体编排工程化.md §1/§2/§5。
对账对象：
  1. tools/orchestration/routes.yaml                          —— 15 专项 skill 路由台账（机器可读唯一事实源）
  2. .workbuddy/skills/allin-governance-agent/SKILL.md        —— workbuddy 形态（锚点 `<!-- route:<id> -->`）
  3. preset/allin/allin.patch.yml 的 GOVERNANCE:BEGIN/END 段   —— dsh 形态（同款锚点）

判据：
  * 台账每条：entry 文件存在且非空；forms 声明的每个形态里锚点恰好 1 次（缺=红，重复=红）；
  * 反向对账：正文里存在而台账没有的孤儿锚 = 红（台账腐化或锚点笔误都拦）；
  * lastVerified 超 90 天 = WARN（只计数不判红，棘轮收紧留待后续裁决）；
  * 结构性错误（受控子集外写法 / 标记不成对 / 载体缺失 / version 不认）= fail-loud 红。

产物（v3 终裁）：tools/gate/audit/g21-runs.jsonl —— JSONL 逐行，每行 = 一次运行的完整
快照（**行内必含 routes 数组**：portal /api/orchestration 免 YAML 解析直接消费最后一行；
绝不按 route 拆行）；5MB 轮转（超限改名 .1，沿 tasks.log 口径）；目录已被 .gitignore
的 `/tools/gate/audit/*` 覆盖，无需登记。行 schema：

  {"type":"g21-run","checkedAt","commit","routesFile","routesReadable",
   "routes":[{id,skill,entry,forms,trigger}],
   "results":[{routeId,side,severity:"error"|"warn",ok,reason}],
   "summary":{total,ok,drift,warn},
   "error"?{code,msg<=500}}

判红三条件（portal / allin status 同款，先判 error/routesReadable 再读 summary）：
  routesReadable==false 或行含 error 字段 或 summary.drift>0  ⇒ 红。
崩溃/结构错也必须落一行（带 error 字段）再退出——「不可判定 ≠ 全绿」，禁假绿。
正常行不得出现 error 字段；正常结果行不落 severity（只落 findings 行：
error 行 ok:false，warn 行 ok:true 附 ok=true 的超龄/降级提示）。

退出码：0 绿 / 1 漂移（E1xx findings）/ 2 结构错（E2xx）/ 3 门禁自身异常（E999）。
错误信息格式：[g21][<code>] route=<id> side=<form> | <事实> | 修复: <指名文件的一句话指令>。

零第三方依赖（仅标准库）——立论：便携 Python 无 PyYAML 曾致 g18 假红，本门禁的
routes.yaml 是受控子集（version + 单行 flow 条目），行式解析即可，不引入 PyYAML 依赖。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - GBK 控制台兜底，失败不致命
    pass

ROOT = Path(__file__).resolve().parents[2]
ROUTES_FILE = ROOT / "tools" / "orchestration" / "routes.yaml"
SKILL_FILE = ROOT / ".workbuddy" / "skills" / "allin-governance-agent" / "SKILL.md"
PATCH_FILE = ROOT / "preset" / "allin" / "allin.patch.yml"
AUDIT_DIR = ROOT / "tools" / "gate" / "audit"
RUNS_FILE = AUDIT_DIR / "g21-runs.jsonl"
REL_ROUTES = "tools/orchestration/routes.yaml"
MAX_BYTES = 5 * 1024 * 1024  # 5MB 轮转，对齐 launch.js tasks.log 口径

MARKER_BEGIN = "<!-- GOVERNANCE:BEGIN"
MARKER_END = "<!-- GOVERNANCE:END"
ANCHOR_RE = re.compile(r"<!--\s*route:([a-z0-9][a-z0-9-]*)\s*-->")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")  # 铁律 5：禁盘符（g01 判据同源）
FIELDS = {"id", "skill", "entry", "forms", "trigger", "lastVerified"}
FORMS = {"workbuddy", "dsh"}
WARN_DAYS = 90
SCHEMA_VERSION = 1
REASON_MAX = 500


class Structural(Exception):
    """结构错（E2xx）：判不了 ≠ 通过，落 error 行后 exit 2。"""

    def __init__(self, code: str, msg: str):
        super().__init__(msg)
        self.code = code
        self.msg = msg


# --------------------------------------------------------------------------- #
# 受控 YAML 子集解析器（立论见模块 docstring；超子集一律 fail-loud）
# --------------------------------------------------------------------------- #

def split_top(body: str, lineno: int) -> list[str]:
    """按顶层逗号切分 flow map 内容（双引号内 / [ ] 序列内的逗号不切）。"""
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    depth = 0
    for ch in body:
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
        elif not in_quote and ch == "[":
            depth += 1
            buf.append(ch)
        elif not in_quote and ch == "]":
            depth -= 1
            if depth < 0:
                raise Structural("E201", f"L{lineno}: flow 条目内方括号不配对")
            buf.append(ch)
        elif ch == "," and not in_quote and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if in_quote or depth != 0:
        raise Structural("E201", f"L{lineno}: 引号或方括号未闭合（flow 条目禁止跨行）")
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_entry(body: str, lineno: int) -> dict:
    item: dict[str, str] = {}
    for part in split_top(body, lineno):
        key, sep, value = part.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or not value or key not in FIELDS:
            allowed = ", ".join(sorted(FIELDS))
            raise Structural(
                "E201",
                f"L{lineno}: 未知/空/缺失字段「{key or part[:30]}」（允许字段：{allowed}）")
        item[key] = value
    missing = sorted(FIELDS - set(item))
    if missing:
        raise Structural("E201", f"L{lineno}: 缺字段 {missing}")

    rid = item["id"].strip('"')
    if not ID_RE.match(rid):
        raise Structural("E201", f"L{lineno}: id「{rid}」不匹配 ^[a-z0-9][a-z0-9-]*$")

    skill = item["skill"].strip('"')
    if not skill:
        raise Structural("E201", f"L{lineno}: skill 不得为空")

    entry = item["entry"].strip('"')
    if DRIVE_RE.search(entry) or entry.startswith(("/", "\\")) or "\\" in entry:
        raise Structural(
            "E201",
            f"L{lineno}: entry「{entry}」必须是仓根相对 POSIX 路径（禁盘符/绝对路径/反斜杠——g01 判据）")

    forms_raw = item["forms"]
    if not (forms_raw.startswith("[") and forms_raw.endswith("]")):
        raise Structural("E201", f"L{lineno}: forms 必须是 flow 序列，如 [workbuddy, dsh]")
    forms = [f.strip().strip('"') for f in forms_raw[1:-1].split(",") if f.strip()]
    if not forms or not set(forms) <= FORMS:
        raise Structural(
            "E201", f"L{lineno}: forms {forms} 必须是 {{workbuddy, dsh}} 的非空子集")

    trigger = item["trigger"].strip('"')
    if not (1 <= len(trigger) <= 120):
        raise Structural("E201", f"L{lineno}: trigger 须为 1..120 字（实测 {len(trigger)}）")

    lv_raw = item["lastVerified"].strip('"')
    try:
        lv = date.fromisoformat(lv_raw)
    except ValueError as exc:
        raise Structural("E201", f"L{lineno}: lastVerified「{lv_raw}」不是 YYYY-MM-DD（{exc}）")

    return {"id": rid, "skill": skill, "entry": entry, "forms": forms,
            "trigger": trigger, "lastVerified": lv.isoformat()}


def parse_routes(text: str) -> list[dict]:
    routes: list[dict] = []
    version: int | None = None
    in_routes = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not in_routes:
            m = re.fullmatch(r"version:\s*(\d+)", line)
            if m:
                version = int(m.group(1))
                continue
            if line == "routes:":
                if version is None:
                    raise Structural("E201", f"L{lineno}: routes 出现在 version 之前（受控子集要求 version 在首）")
                in_routes = True
                continue
            raise Structural(
                "E201",
                f"L{lineno}: 无法识别的顶层行「{line[:40]}」（受控子集只认 `version: <int>` 与 `routes:`）")
        if not line.startswith("- {") or not line.endswith("}"):
            raise Structural(
                "E201",
                f"L{lineno}: 路由条目必须是单行 flow 写法 `- {{ ... }}`（多行/嵌套超出受控子集）")
        routes.append(parse_entry(line[3:-1], lineno))

    if version is None:
        raise Structural("E201", "缺少顶层 version 声明")
    if version != SCHEMA_VERSION:
        raise Structural("E203", f"routes.yaml version={version}，本门禁只认 version={SCHEMA_VERSION}")
    if not routes:
        raise Structural("E203", "routes 为空（至少 1 条路由条目）")
    ids = [r["id"] for r in routes]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise Structural("E201", f"路由 id 重复：{dup}")
    return routes


# --------------------------------------------------------------------------- #
# 载体读取与锚点计数
# --------------------------------------------------------------------------- #

def read_text(path: Path) -> str:
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:  # pragma: no cover - 常量都在 ROOT 下，防御
        rel = str(path)
    if not path.is_file():
        raise Structural("E204", f"载体文件缺失：{rel}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise Structural("E204", f"载体不是合法 UTF-8：{rel}（{exc}）")


def gov_block(text: str) -> str:
    """GOVERNANCE:BEGIN/END 段文本；标记定位复用 refresh-gov-block 的「整行」规则
    （正文注释里出现标记字样不会拉错块起点——2026-10-29 实测坑）。"""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip().startswith(MARKER_BEGIN)]
    stops = [i for i, ln in enumerate(lines) if ln.strip().startswith(MARKER_END)]
    if len(starts) != 1 or len(stops) != 1 or stops[0] < starts[0]:
        raise Structural(
            "E202",
            f"{PATCH_FILE.relative_to(ROOT).as_posix()} 的 {MARKER_BEGIN}/{MARKER_END} "
            "不是成对标记（须各恰好一行且 END 在后）")
    return "\n".join(lines[starts[0]:stops[0] + 1])


def count_anchors(text: str) -> Counter:
    return Counter(ANCHOR_RE.findall(text))


# --------------------------------------------------------------------------- #
# 三方对账
# --------------------------------------------------------------------------- #

def findings(routes: list[dict], wb: Counter, dsh: Counter, today: date):
    """返回 (errors, warns)。error/warn 行的 reason ≤500 字符且带指名文件的修复指引。"""
    errors: list[dict] = []
    warns: list[dict] = []
    known = {r["id"] for r in routes}

    def err(code: str, route_id: str, side: str, msg: str, fix: str) -> None:
        reason = f"{msg}。修复: {fix}"
        errors.append({"routeId": route_id, "side": side, "severity": "error",
                       "ok": False, "reason": reason[:REASON_MAX]})

    for r in routes:
        rid = r["id"]
        entry_path = ROOT / r["entry"]
        if not entry_path.is_file() or entry_path.stat().st_size == 0:
            err("E105", rid, "routes",
                f"入口文件缺失或为空：{r['entry']}",
                "补齐该入口文件（含非空 SKILL.md），或改 routes.yaml 该条目的 entry 指向")
        if "workbuddy" in r["forms"]:
            n = wb.get(rid, 0)
            if n == 0:
                err("E101", rid, "workbuddy",
                    f"SKILL.md 缺锚点 <!-- route:{rid} -->（0 次，期望恰好 1 次）",
                    "在 .workbuddy/skills/allin-governance-agent/SKILL.md §4 路由表对应行尾追加该锚点，复跑本门禁")
            elif n > 1:
                err("E104", rid, "workbuddy",
                    f"SKILL.md 锚点 <!-- route:{rid} --> 出现 {n} 次（期望恰好 1 次）",
                    "删除多余锚点（每条路由每形态只允许一个锚点），复跑本门禁")
        if "dsh" in r["forms"]:
            n = dsh.get(rid, 0)
            if n == 0:
                err("E102", rid, "dsh",
                    f"GOVERNANCE 段缺锚点 <!-- route:{rid} -->（0 次，期望恰好 1 次）",
                    "在 preset/allin/allin.patch.yml GOVERNANCE 段路由清单补该行+锚点，"
                    "然后 python preset/allin/refresh-gov-block.py --write && --check，复跑本门禁")
            elif n > 1:
                err("E104", rid, "dsh",
                    f"GOVERNANCE 段锚点 <!-- route:{rid} --> 出现 {n} 次（期望恰好 1 次）",
                    "删除多余锚点（含注释里的示例锚），复跑本门禁")
        age = (today - date.fromisoformat(r["lastVerified"])).days
        if age > WARN_DAYS:
            warns.append({"routeId": rid, "side": "routes", "severity": "warn", "ok": True,
                          "reason": f"W301: lastVerified 已 {age} 天（>{WARN_DAYS}），"
                                    f"建议实测复核后在 routes.yaml 刷新该条目日期"[:REASON_MAX]})

    for side, counts, where in (
            ("workbuddy", wb, "SKILL.md"),
            ("dsh", dsh, "GOVERNANCE 段")):
        for aid in sorted(counts):
            if aid not in known:
                err("E103", aid, side,
                    f"{where} 存在台账外孤儿锚点 <!-- route:{aid} -->（{counts[aid]} 次）",
                    "删除该孤儿锚点，或在 tools/orchestration/routes.yaml 补对应条目（二选一，不许静默）")
    return errors, warns


# --------------------------------------------------------------------------- #
# 产物落盘（JSONL · 一次运行一行 · 5MB 轮转）
# --------------------------------------------------------------------------- #

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_short() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace", timeout=20)
        return out.stdout.strip()[:8] or "unknown"
    except Exception:
        return "unknown"


def rotate_if_large() -> None:
    if RUNS_FILE.is_file() and RUNS_FILE.stat().st_size > MAX_BYTES:
        RUNS_FILE.replace(RUNS_FILE.with_name(RUNS_FILE.name + ".1"))


def append_row(row: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    rotate_if_large()
    with RUNS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def entry_brief(route: dict) -> dict:
    """行内 routes 数组元素：portal 免 YAML 解析（全案契约，勿减字段）。"""
    return {k: route[k] for k in ("id", "skill", "entry", "forms", "trigger")}


def build_row(routes, results, summary, readable, error=None) -> dict:
    row = {
        "type": "g21-run",
        "checkedAt": utc_now(),
        "commit": git_short(),
        "routesFile": REL_ROUTES,
        "routesReadable": readable,
        "routes": [entry_brief(r) for r in routes],
        "results": results,
        "summary": summary,
    }
    if error is not None:
        row["error"] = {"code": error[0], "msg": str(error[1])[:REASON_MAX]}
    return row


# --------------------------------------------------------------------------- #
# 输出与主流程
# --------------------------------------------------------------------------- #

def print_finding(severity: str, code: str, item: dict) -> None:
    print(f"[g21][{code}] route={item['routeId']} side={item['side']} "
          f"severity={severity} | {item['reason']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="g21 agent-parity：routes.yaml ⇄ SKILL.md 锚点 ⇄ GOVERNANCE 段锚点 三方对账")
    parser.parse_args(argv)

    print("==> g21 agent-parity（编排路由台账三方对账）")
    routes: list[dict] = []
    readable = False
    try:
        routes = parse_routes(read_text(ROUTES_FILE))
        readable = True
        wb_text = read_text(SKILL_FILE)
        gov = gov_block(read_text(PATCH_FILE))
    except Structural as exc:
        row = build_row(routes, [], {"total": 0, "ok": 0, "drift": 0, "warn": 0},
                        readable, error=(exc.code, exc.msg))
        print(f"[g21][{exc.code}] 结构错 | {exc.msg} | 已落 error 行（不可判定 ≠ 全绿）")
        append_row(row)
        print(f"g21 agent-parity: 红（结构错 {exc.code}）")
        return 2

    errors, warns = findings(routes, count_anchors(wb_text), count_anchors(gov), date.today())
    drift_ids = {e["routeId"] for e in errors}
    summary = {"total": len(routes), "ok": len(routes) - len(drift_ids),
               "drift": len(drift_ids), "warn": len(warns)}
    results = errors + warns
    row = build_row(routes, results, summary, readable)
    append_row(row)

    for e in errors:
        print_finding("error", "E1xx", e)
    for w in warns:
        print_finding("warn", "W301", w)
    print(f"    summary: total={summary['total']} ok={summary['ok']} "
          f"drift={summary['drift']} warn={summary['warn']}")
    print(f"    产物: {RUNS_FILE.relative_to(ROOT).as_posix()}")
    if errors:
        print("g21 agent-parity: 红（漂移，见上行修复指引）")
        return 1
    print("g21 agent-parity: 绿（台账与双形态锚点对账一致）")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # 崩溃也必须落一行 fail-loud（E999），禁假绿
        try:
            append_row(build_row([], [], {"total": 0, "ok": 0, "drift": 0, "warn": 0},
                                 False, error=("E999", f"门禁自身异常：{exc!r}")))
        except Exception:
            pass
        print(f"[g21][E999] 门禁自身异常：{exc!r}", file=sys.stderr)
        raise SystemExit(3)
