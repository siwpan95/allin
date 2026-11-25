#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g21 · agent-parity —— routes.yaml ⇄ SKILL.md 锚点 ⇄ GOVERNANCE 段锚点 三方对账门禁，
外加第四方「真身」对账（目录 ⇄ 台账 ⇄ 散文声明数，ADR-0011 §D2）。

设计依据（冻结基线 v3）：team 交付物 P2-智能体编排工程化.md §1/§2/§5；
第四方依据 architecture/adr/ADR-0011-计数与基线从手写改为可判.md §D2。
对账对象：
  1. tools/orchestration/routes.yaml                          —— 17 专项 skill 路由台账（机器可读唯一事实源）
  2. .workbuddy/skills/allin-governance-agent/SKILL.md        —— workbuddy 形态（锚点 `<!-- route:<id> -->`）
  3. preset/allin/allin.patch.yml 的 GOVERNANCE:BEGIN/END 段   —— dsh 形态（同款锚点）
  4. .workbuddy/skills/*/                                    —— 「真身」：目录集，缺席者只在这里可见

判据：
  * 台账每条：entry 文件存在且非空；forms 声明的每个形态里锚点恰好 1 次（缺=红，重复=红）；
  * 反向对账：正文里存在而台账没有的孤儿锚 = 红（台账腐化或锚点笔误都拦）；
  * **真身对账（v2，2026-11-25 起）**：三方对账是「内部一致性」判据 —— 三面同时少一条它照样绿。
    所以再加三条，缺一条都留缺口：
      A 声明 ⇄ 台账：三处人写载体里的「N 个专项 skill」必须等于 len(routes)（扣掉 `router`
        指向的那条）；声明 = 人写的**结论**，台账 = 机器可读的**账**，两者不等即红（E106）。
      B 台账 ⇄ 真身：`.workbuddy/skills/` 目录集 ⟺ 台账 skill 集，**双向差集非空即红**：
        目录有台账无 ⇒ E107（缺席者，漏登记）；台账有目录无 ⇒ E108（死链）。
      C router 自洽：`router` 字段指向的目录必须存在（E109）。**排除项不写在代码里** ——
        谁是路由者是台账的一等字段，不是门禁里的第二份手写事实（改名不必改门禁）。
    A 单用会被「两个错互相抵消」骗过（15 == 16−1 曾在漏登 2 条时恰好成立，见 ADR-0011 §P2）：
    B 是 A 的分母校验，两者必须成对。
  * lastVerified 超 90 天 = WARN（只计数不判红，棘轮收紧留待后续裁决）；
  * 某载体里找不到计数声明 = W302 WARN（撤掉声明不算错，但「这里没有可判的数字」要报出来，
    否则删掉一句话就能让判据名存实亡）；
  * 结构性错误（受控子集外写法 / 标记不成对 / 载体缺失 / version 不认 / router 缺失）= fail-loud 红。

产物（v3 终裁）：tools/gate/audit/g21-runs.jsonl —— JSONL 逐行，每行 = 一次运行的完整
快照（**行内必含 routes 数组**：portal /api/orchestration 免 YAML 解析直接消费最后一行；
绝不按 route 拆行）；5MB 轮转（超限改名 .1，沿 tasks.log 口径）；目录已被 .gitignore
的 `/tools/gate/audit/*` 覆盖，无需登记。行 schema：

  {"type":"g21-run","checkedAt","commit","routesFile","routesReadable",
   "routes":[{id,skill,entry,forms,trigger}],
   "results":[{code,routeId,side,severity:"error"|"warn",ok,reason}],
   "summary":{total,ok,drift,warn},
   "reconciliation":{router,routerInLedger,effective,routesTotal,skillDirs,
                     declarations[],silentCarriers[],unregistered[],dangling[]},
   "error"?{code,msg<=500}}

`reconciliation` 是**附加**字段（老消费方只读 routes/summary，多一个键不破坏契约）：
它回答「这次到底量了什么」，避免「量到 0」与「量到 17 全对」在日志里长得一样
（ADR-0011 §D3 同一动机；summary 的键位不动，portal / allin status 无需改）。
summary.ok = 无 findings 的路由条数（不再用 total−drift，否则伪 routeId 会让它变负）。

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
SKILLS_DIR = ROOT / ".workbuddy" / "skills"
PATCH_FILE = ROOT / "preset" / "allin" / "allin.patch.yml"
AUDIT_DIR = ROOT / "tools" / "gate" / "audit"
RUNS_FILE = AUDIT_DIR / "g21-runs.jsonl"
REL_ROUTES = "tools/orchestration/routes.yaml"
REL_SKILLS = ".workbuddy/skills/"
MAX_BYTES = 5 * 1024 * 1024  # 5MB 轮转，对齐 launch.js tasks.log 口径

#: 计数声明所在的三处人写载体：`(仓根相对路径, 短名（进 findings 的 routeId）, 人话身份)`。
#: 这是一份**载体清单**，不是第二份数字事实 —— 数字只有一个来源（台账），这里只说
#: 「去哪几个地方核对人写的那句结论」。短名进 `route=<短名>:<行号>`，便于一眼定位。
DECLARED_SITES = (
    ("preset/allin/allin.patch.yml", "allin.patch.yml", "DSH 治理段正文（唯一手改源）"),
    (".workbuddy/skills/allin-governance-agent/SKILL.md", "SKILL.md", "WorkBuddy 治理载体"),
    ("docs/规范/SPEC-204-系统架构.md", "SPEC-204", "架构规范"),
)
#: 「N 个专项 skill」。量词允许 个/条（SPEC-204 §6 写的是「15 条专项 skill 路由」），
#: 定语允许 专项/既有项目级 —— **只放宽措辞，不放宽数值**：命中几个就核几个，
#: 少核一处等于给「换个说法就逃出判据」留门。
DECLARED_RE = re.compile(r"(\d+)\s*[个条]\s*(?:既有项目级|专项)\s*skill")


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


def parse_routes(text: str) -> tuple[list[dict], str]:
    """受控子集 → (routes, router)。

    `router` 是 2026-11-25 起的一等顶层字段：路由者自身的 skill 名。它**不进 routes
    列表**（给自己立一条「路由到我自己」是环，且会让台账语义变味），所以计数与目录
    差集都要扣掉它 —— 而扣谁必须**从台账读**，不能写死在门禁里：写死等于把「谁是
    路由者」变成第二份手写事实，下次改名没人知道要改这里。
    """
    routes: list[dict] = []
    version: int | None = None
    router: str | None = None
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
            m = re.fullmatch(r"router:\s*(\S+)", line)
            if m:
                if version is None:
                    raise Structural("E201", f"L{lineno}: router 出现在 version 之前（受控子集要求 version 在首）")
                if router is not None:
                    raise Structural("E201", f"L{lineno}: router 重复声明（只能有一个路由者）")
                rid = m.group(1).strip('"')
                if not ID_RE.match(rid):
                    raise Structural("E201", f"L{lineno}: router「{rid}」不匹配 ^[a-z0-9][a-z0-9-]*$")
                router = rid
                continue
            if line == "routes:":
                if version is None:
                    raise Structural("E201", f"L{lineno}: routes 出现在 version 之前（受控子集要求 version 在首）")
                in_routes = True
                continue
            raise Structural(
                "E201",
                f"L{lineno}: 无法识别的顶层行「{line[:40]}」（受控子集只认 `version: <int>`、"
                f"`router: <route-id>` 与 `routes:`）")
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
    if router is None:
        raise Structural(
            "E203",
            "缺少顶层 router 声明（路由者自身的 skill 名）。没有它，「专项 skill 数」就得分不清"
            "「路由者」与「被路由者」—— 排除项只能靠写死名单，而写死名单会在改名时悄悄失效")
    if router in ids:
        # ADR-0011 §D2.2-C 的另一种形态（router 也在台账里）。允许，但 entry 必须指向它自己，
        # 否则「router 字段写了某条路由」就成了张冠李戴。
        own = next(r for r in routes if r["id"] == router)
        if own["entry"] != f"{REL_SKILLS}{router}/SKILL.md":
            raise Structural(
                "E203",
                f"router={router} 同时出现在 routes 里，但其 entry「{own['entry']}」"
                f"不是 {REL_SKILLS}{router}/SKILL.md（router 字段与那条路由不自洽）")
    return routes, router


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

def finding(code: str, severity: str, route_id: str, side: str, ok: bool,
            reason: str) -> dict:
    """一条 findings 行的唯一构造点。

    `code` 落进产物（E101…/W301…）：此前只在 reason 文本里出现，消费方无法按码过滤，
    而本门禁已有 9 个码——「同一句人话里读码」是给下一个排障的人添堵。
    追加键不改语义：portal / status_service 只读 severity / routeId / reason。
    """
    return {"code": code, "routeId": route_id, "side": side, "severity": severity,
            "ok": ok, "reason": reason[:REASON_MAX]}


def findings(routes: list[dict], wb: Counter, dsh: Counter, today: date):
    """返回 (errors, warns)。error/warn 行的 reason ≤500 字符且带指名文件的修复指引。"""
    errors: list[dict] = []
    warns: list[dict] = []
    known = {r["id"] for r in routes}

    def err(code: str, route_id: str, side: str, msg: str, fix: str) -> None:
        errors.append(finding(code, "error", route_id, side, False, f"{msg}。修复: {fix}"))

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
            warns.append(finding("W301", "warn", rid, "routes", True,
                                 f"W301: lastVerified 已 {age} 天（>{WARN_DAYS}），"
                                 f"建议实测复核后在 routes.yaml 刷新该条目日期"))

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
# 第四方：真身对账（目录 ⇄ 台账 ⇄ 散文声明数）—— ADR-0011 §D2
# --------------------------------------------------------------------------- #

def skill_dirs() -> set[str]:
    """`.workbuddy/skills/` 下的真实目录名 = 「真身」。

    缺席者只在这里可见：少登一条，routes.yaml / SKILL.md / GOVERNANCE 段三面同时少，
    三方对账照样一致（本轮 15/16/18 就是这么躺了一个月的）。
    目录缺失或空 ⇒ 结构错，不判绿：量不到东西不能等于没问题（ADR-0011 §D3 同源）。
    """
    if not SKILLS_DIR.is_dir():
        raise Structural("E204", f"skills 目录缺失：{REL_SKILLS}（真身对账没有分母）")
    dirs = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
    if not dirs:
        raise Structural("E204", f"{REL_SKILLS} 下没有任何 skill 目录（不可判定 ≠ 全绿）")
    return dirs


def declared_counts() -> tuple[list[dict], list[dict]]:
    """三处人写载体里的「N 个专项 skill」声明 → (命中清单, 一处都没有的载体清单)。

    只放宽措辞（个/条、专项/既有项目级），不放过数值：同一个载体里命中几处就核几处，
    任何一处与台账不等即红 —— 「换一种说法」不该是逃出判据的办法。
    """
    hits: list[dict] = []
    silent: list[dict] = []
    for rel, short, label in DECLARED_SITES:
        text = read_text(ROOT / rel)
        found = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in DECLARED_RE.finditer(line):
                found += 1
                hits.append({"where": rel, "short": short, "label": label,
                             "line": lineno, "value": int(match.group(1)),
                             "text": match.group(0)})
        if not found:
            silent.append({"where": rel, "short": short, "label": label})
    return hits, silent


def reconcile(routes: list[dict], router: str, dirs: set[str],
              declared: list[dict], silent: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """A 声明⇄台账 / B 台账⇄真身 / C router 自洽。返回 (errors, warns, reconciliation)。"""
    errors: list[dict] = []
    warns: list[dict] = []
    route_ids = {r["id"] for r in routes}
    registered = {r["skill"] for r in routes}
    # 路由者自身不是「被路由的专项 skill」：它要么在 routes 里（ADR-0011 D2.2-C 形态，
    # 此时扣 1），要么完全不在（本仓现行形态，此时不扣）。两种形态都从台账读，不写死。
    effective = len(routes) - (1 if router in route_ids else 0)

    def err(code: str, route_id: str, side: str, msg: str, fix: str) -> None:
        errors.append(finding(code, "error", route_id, side, False, f"{msg}。修复: {fix}"))

    # A 声明 ⇄ 台账
    for decl in declared:
        if decl["value"] == effective:
            continue
        err("E106", f"{decl['short']}:{decl['line']}", "declared",
            f"{decl['label']} 写的是「{decl['text']}」，台账派生值为 {effective}"
            f"（routes {len(routes)} 条 − router {router} 的 "
            f"{1 if router in route_ids else 0} 条）",
            f"改 {decl['where']}:{decl['line']} 的数字为 {effective}；"
            f"新增/退役 skill 后必须同时回填这三处，否则跑 python tools/gate/agent_parity.py 会红")

    # B 台账 ⇄ 真身（双向差集；单方向只能抓一半）
    unregistered = sorted(dirs - registered - {router})
    dangling = sorted(registered - dirs)
    for name in unregistered:
        err("E107", name, "skills-dir",
            f"{REL_SKILLS}{name}/ 存在，但 routes.yaml 没有登记它（缺席者：任何"
            f"「内部一致性」判据都看不见目录里多出来的人）",
            f"在 {REL_ROUTES} 补一条路由条目 + 双形态锚点"
            f"（.workbuddy/skills/allin-governance-agent/SKILL.md §4 与 "
            f"preset/allin/allin.patch.yml GOVERNANCE 段各一个 <!-- route:{name} -->），"
            f"若是废弃 skill 则删目录；复跑本门禁")
    for route in routes:
        if route["skill"] in dirs:
            continue
        err("E108", route["id"], "routes",
            f"台账 skill「{route['skill']}」在 {REL_SKILLS} 下没有同名目录（死链：台账指着不存在的地方）",
            f"补齐 {REL_SKILLS}{route['skill']}/SKILL.md，或从 {REL_ROUTES} 删除该条"
            f"并同时删掉双形态锚点（否则会变成 E103 孤儿锚）")

    # C router 自洽
    if router not in dirs:
        err("E109", router, "router",
            f"routes.yaml 的 router={router} 在 {REL_SKILLS} 下没有同名目录（路由者指向空气）",
            f"改正 {REL_ROUTES} 的 router 字段，或补齐 {REL_SKILLS}{router}/SKILL.md")

    # 载体里连声明都没有：不算错（撤掉数字是合法修法），但不能静默 —— 否则删掉一句话
    # 就能让这条判据名存实亡，而跑批仍然全绿。
    for site in silent:
        warns.append(finding("W302", "warn", f"{site['short']}:0", "declared", True,
                             f"W302: {site['label']}（{site['where']}）里找不到"
                             f"「N 个专项 skill」声明，该载体本次不参与计数判据"
                             f"（正则 {DECLARED_RE.pattern}）"))

    reconciliation = {
        "router": router,
        "routerInLedger": router in route_ids,
        "effective": effective,
        "routesTotal": len(routes),
        "skillDirs": len(dirs),
        "declarations": [{"where": d["where"], "line": d["line"], "value": d["value"]}
                         for d in declared],
        "silentCarriers": [s["where"] for s in silent],
        "unregistered": unregistered,
        "dangling": dangling,
    }
    return errors, warns, reconciliation


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


def build_row(routes, results, summary, readable, error=None, recon=None) -> dict:
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
    if recon is not None:
        row["reconciliation"] = recon
    if error is not None:
        row["error"] = {"code": error[0], "msg": str(error[1])[:REASON_MAX]}
    return row


# --------------------------------------------------------------------------- #
# 输出与主流程
# --------------------------------------------------------------------------- #

def print_finding(item: dict) -> None:
    print(f"[g21][{item['code']}] route={item['routeId']} side={item['side']} "
          f"severity={item['severity']} | {item['reason']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="g21 agent-parity：routes.yaml ⇄ SKILL.md 锚点 ⇄ GOVERNANCE 段锚点 ⇄ "
                    "skills 目录真身/声明数 四方对账")
    parser.parse_args(argv)

    print("==> g21 agent-parity（编排路由台账三方对账 + 真身对账）")
    routes: list[dict] = []
    readable = False
    try:
        routes, router = parse_routes(read_text(ROUTES_FILE))
        readable = True
        wb_text = read_text(SKILL_FILE)
        gov = gov_block(read_text(PATCH_FILE))
        dirs = skill_dirs()
        declared, silent = declared_counts()
    except Structural as exc:
        row = build_row(routes, [], {"total": 0, "ok": 0, "drift": 0, "warn": 0},
                        readable, error=(exc.code, exc.msg))
        print(f"[g21][{exc.code}] 结构错 | {exc.msg} | 已落 error 行（不可判定 ≠ 全绿）")
        append_row(row)
        print(f"g21 agent-parity: 红（结构错 {exc.code}）")
        return 2

    errors, warns = findings(routes, count_anchors(wb_text), count_anchors(gov), date.today())
    recon_errors, recon_warns, recon = reconcile(routes, router, dirs, declared, silent)
    errors += recon_errors
    warns += recon_warns
    # ok 只数「无 findings 的路由条数」：伪 routeId（声明载体 / 目录名）会让 total−drift 变负，
    # 而 portal 与 allin status 都把这个数当「台账里有多少条是真的」读。
    drift_ids = {e["routeId"] for e in errors}
    route_ids = {r["id"] for r in routes}
    summary = {"total": len(routes), "ok": len(route_ids - drift_ids),
               "drift": len(drift_ids), "warn": len(warns)}
    results = errors + warns
    row = build_row(routes, results, summary, readable, recon=recon)
    append_row(row)

    for e in errors:
        print_finding(e)
    for w in warns:
        print_finding(w)
    print(f"    summary: total={summary['total']} ok={summary['ok']} "
          f"drift={summary['drift']} warn={summary['warn']}")
    print(f"    真身: router={recon['router']} 目录={recon['skillDirs']} "
          f"台账派生值={recon['effective']} 声明={[d['value'] for d in recon['declarations']]}")
    print(f"    产物: {RUNS_FILE.relative_to(ROOT).as_posix()}")
    if errors:
        print("g21 agent-parity: 红（漂移，见上行修复指引）")
        return 1
    print("g21 agent-parity: 绿（台账 ⇄ 双形态锚点 ⇄ 真身目录 ⇄ 声明数 全对账一致）")
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
