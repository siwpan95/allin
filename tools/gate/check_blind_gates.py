#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盲门元判据（blind-gate meta criterion）—— 「跑了、绿了、什么都没量」必须判红。

## 为什么需要这道判据

判据有三种静默失效，只有第二种会被现有 20 道门禁看见：

1. **死门（dead gate）**：登记了、但从不被调用。本仓已有对策 —— 编排层把每条命令
   接进 `scripts/run_all_gates.sh`，且 `g00-meta` 逐道跑 `--selfcheck` 证明「仍会红」。
2. **环境坏门（broken gate）**：跑了，但错误被吞成 0。对策是 `g10-failloud-probe`、
   `g18-exceptions` 与 `selfcheck` 的 `misreports` 计数。
3. **盲门（blind gate）**：跑完了、退 0、**什么都没量**。没有一道门禁能判它自己 ——
   因为「门禁没扫描到对象」与「门禁扫描了对象且没问题」在退出码上完全同形。

第 3 类是本文件唯一的判据。它的立场来自两条外部证据（已进 ADR 记账）：
「a gate that only ever passes is no gate」与「a check that cannot fail tells you
nothing」—— 后者的操作化结论是：**「没跑」与「没发现问题」必须可区分**。
pytest 无用例收集时退 5、Jest 默认无测试即失败，都是同一个立场。

本仓有过正实例：上一轮 `repocheck --only-gates` 注册了 0 条规则却退 0，还打印
「82% 通过」—— 一份「什么都没量」的报告被当成结论消费了。

## 为什么它不占 g 编号

g00–g20 是**判仓库**的门禁，判据对象是被管的仓。本文件判的是**门禁自己**，属编排层
元判据，跑在 20 道门禁之外（`scripts/run_all_gates.sh` 接线）。给它一个 g 编号会把
「判据的判据」混进「判据」的清单里，让「20 道」这个被多份文档引用的计数漂移。

## 判红口径（唯一一条，宁窄不宽）

一道门禁被判 **BLIND**，当且仅当同时满足：

* 输出里能读到 `scanned 0 file(s)`（它**自己说了**一个对象都没读）；
* 退出码为 0（它**自己说了**没问题）；
* 输出里没有任何显式 SKIP 标记（`skipped N>0` / `SKIPPED (not a pass)` / `not_applicable`）。

三条缺一条都不判红，且每种情形有单独的名字，**都不叫"通过"**：

| 判定 | 含义 | 是否算通过 |
| --- | --- | --- |
| `measured` | 读到 `scanned N>0` 且退 0 | 是（唯一算通过的） |
| `skipped` | `scanned 0` + 退 0 + 显式 SKIP，**连同 SKIP 理由一起打印** | 否（not a pass） |
| `blind` | `scanned 0` + 退 0 + 无任何 SKIP 标记 | **判红** |
| `undetermined` | 输出里**没有** `scanned` 字段，无从判定 | 否（可见，不默认当绿） |
| `failed` | 退出码非 0 | 否（门禁自己已判红，不重复计数） |
| `skipped-platform` | registry 的 `platforms` 不含本机 | 否（不适用） |

`undetermined` 是刻意不给默认值的：g15-docs-contract 从不用 `govlib.Report.scanned`，
它的输出里没有任何 `scanned` 字样。把它当绿，就是让「无法判定」冒充「判定通过」——
这正是盲门的定义。本工具因此把它**逐条列出**，并以退出码 2（不是 0）表达
「本批判定不完整」。要让批量编排不被这一条长期拖红，可用 `--allow-undetermined`
（仍会打印，只是不改变退出码）；默认是严格的。

`skipped` 之所以还要求**打印理由**：显式 SKIP 是唯一合法的「我确实没量」出口，
它必须可被复核。g06-numbering 今天就是 `scanned 0 + skipped 1`，理由是
「no tracked bilingual pair in scope」—— 实测本仓 `git ls-files` 里 0 个 `*.zh.md`、
0 个 `vN.*` 序号文件，该 SKIP 为真。**理由文本与本判定同屏输出**，是为了让下一个人
能像上面那样去核，而不是把 SKIP 当成新的免检章。

退出码：0 全部有量（或有据可查的 SKIP）/ 1 存在盲门 / 2 存在不可判定（未加
`--allow-undetermined` 时）/ 3 环境错（找不到 registry、解释器不可用）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_USAGE = 2
EXIT_ENV = 3

MEASURED = "measured"
SKIPPED = "skipped"
BLIND = "blind"
UNDETERMINED = "undetermined"
FAILED = "failed"
SKIPPED_PLATFORM = "skipped-platform"
ERROR = "error"

#: 唯一算「通过」的判定之外的集合，用于汇总与退出码。
NOT_A_PASS = (SKIPPED, UNDETERMINED, FAILED, SKIPPED_PLATFORM, ERROR)

# --------------------------------------------------------------------------- #
# 匹配面：**白名单只认具名形态**，其余一律判「不可判定」
#
# 2026-11-25 现场教训（team-lead 要求写清，已进 ADR 记账）：
#   第一版为「兼容非 govlib 输出」加了宽松兜底 `\bscanned\s*[=:]\s*(\d+)`。真实仓首跑
#   把 **g15-docs-contract 判成了 measured(scanned=1)** —— 而那个 1 来自豁免统计标签
#   `D16-plan-scanned=1`，g15 根本不报 scanned。也就是说：**判据为了兼容而放宽的那
#   一处，就是它失灵的那一处。** 它当时打印的是「19 道有量」，比错误更像好结论。
#
# 处置：不是「把兜底收窄一点」（那还是在猜），而是**只认具名形态**：
#   ① govlib 渲染摘要行   `<title>: scanned N file(s); blocking B; exempted E; skipped S.`
#   ② 同一渲染片段的行内形态 `scanned N file(s)`
#   ③ 机读**字段名**形态   `"scanned": N`（字段名，不是标签）
# 三条都不命中 ⇒ **undetermined**。宁可判「不可判定」，也不猜。
# 猜错的代价是假绿（把没量当量了），判不出的代价只是多一条待办 —— 两者不对称。
#
# 另外保留一份**排除清单**作第二道闸（白名单之外不省的那一手），逐条对应
# team-lead 点名的四类行，且每一类都配一条反例钉在 --selfcheck 里：
#   1. `…-scanned=` 这类别人的统计标签（`D16-plan-scanned=1`）；
#   2. `exempted:` 豁免行；
#   3. `SKIPPED` / `not applicable` 行；
#   4. 注释行与被编号前缀标记的「别人记录自己的工作」。
# --------------------------------------------------------------------------- #

#: ① 权威形态：govlib 渲染摘要（整行锚定）。
SUMMARY_RE = re.compile(
    r"^(?P<claim>.+?):\s*scanned\s+(?P<scanned>\d+)\s+file\(s\);\s*"
    r"blocking\s+(?P<blocking>\d+);\s*exempted\s+(?P<exempted>\d+);\s*"
    r"skipped\s+(?P<skipped>\d+)\.",
    re.MULTILINE,
)
#: ② 渲染片段（允许非 govlib 输出，但仍要求完整的 `scanned N file(s)` 字样）。
#: 起点排除 `-`/标识符字符，故 `plan-scanned 3 file` 不算。
SCANNED_RENDERED_RE = re.compile(r"(?<![-\w])scanned\s+(\d+)\s+file\(s\)", re.IGNORECASE)
#: ③ 机读字段名形态（JSON）：`"scanned": 3`。
SCANNED_JSON_KEY_RE = re.compile(r'"scanned"\s*:\s*(\d+)')

#: 排除清单（四类），按顺序判，命中即该行不作数。
REJECT_LABEL_LIKE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*scanned\s*[=:]")
#: ⚠ 实测（2026-11-25 逐条关掉规则的变异测试）：白名单落地后，本规则**不承重** ——
#: `D16-plan-scanned=1` 因白名单要求 `N file(s)` 字样而本来就读不到。它只作防御，
#: 防的是「将来有人把白名单放宽」。**测出来是防御就写防御，不写成"生效"。**
REJECT_EXEMPT_LINE = re.compile(r"^\s*exempted\s*:", re.IGNORECASE)
REJECT_COMMENT_LINE = re.compile(r"^\s*(?:#|//|;|--|\*)")
REJECT_SKIP_LINE = re.compile(r"^\s*\[?SKIP(?:PED)?\b", re.IGNORECASE)
REJECT_NOT_APPLICABLE = re.compile(r"not[ _-]applicable", re.IGNORECASE)
#: 「别人记录自己的工作」：一行里既有别的门禁的 `"gate"` 键又有 `"scanned"` 键 ⇒
#: 那是别人的逐道记录，不是本次读数。这条是排除清单里唯一**承重**的一条 ——
#: 白名单第 ③ 形态（`"scanned": N`）会把它读成自己的读数，必须靠这一条挡住。
REJECT_FOREIGN_RECORD = re.compile(r'"gate"\s*:', re.IGNORECASE)

#: govlib 把 SKIP 理由印在这一行；抓住它是为了让 SKIP 可复核而不是免检。
SKIP_REASON_RE = re.compile(r"SKIPPED\s*\(not a pass\)\s*:\s*(.+)", re.IGNORECASE)
#: 行首的 SKIP / SKIPPED 标记（`skipped 0` 这种「零跳过」不算标记）。
SKIP_LINE_RE = re.compile(r"^[ \t]*\[?SKIP(?:PED)?\]?(?![A-Za-z])(?!\s*[:=]?\s*0\b)", re.MULTILINE)
NOT_APPLICABLE_RE = re.compile(r"not[ _-]applicable", re.IGNORECASE)


def reject_reason(line: str) -> str:
    """这一行为什么不能当 scanned 读数用；返回空串表示「可用」。

    独立成函数是为了让排除清单本身可测（它也是一种判据，也要有反例）。
    实测承重情况（逐条关掉规则看判定是否翻转）：
      · 别人的逐道记录 → 承重（关掉后变 measured）
      · 注释行         → 承重（关掉后变 measured）
      · SKIP 标记行    → 承重（关掉后变 skipped）
      · 豁免行 / 统计标签 → 不承重（白名单已挡住），仅作防御
    """
    if REJECT_EXEMPT_LINE.match(line):
        return "豁免行（exempted:）"
    if REJECT_FOREIGN_RECORD.search(line) and re.search(r"scanned", line, re.IGNORECASE):
        return "别人的逐道记录（同一行有 \"gate\" 与 scanned）"
    if REJECT_LABEL_LIKE.search(line):
        return "别人的统计标签（…-scanned=）"
    if REJECT_SKIP_LINE.match(line):
        return "SKIP 标记行"
    if REJECT_NOT_APPLICABLE.search(line):
        return "not applicable 行"
    if REJECT_COMMENT_LINE.match(line):
        return "注释行"
    return ""


def _utf8_stdio() -> None:
    """Windows 控制台默认 cp936；打印中文/生僻字会 UnicodeEncodeError 并吞掉整份报告。

    「记账失败」被伪装成「没有失败」是本仓吃过多次的亏（见 run_all_gates.sh 的
    log_run 注释）。输出被管道接走时又一切正常 —— 这类缺陷只在人工跑时出现，
    所以必须显式钉死，不能指望默认值。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 老 Python / 被替换的 stream 都可能不支持
            pass


def host_platform() -> str:
    """registry 的 `platforms` 词汇（`nt` / `posix`），与 run.ts 保持同一口径。"""
    return "nt" if os.name == "nt" else "posix"


@dataclass
class GateResult:
    """一道门禁的判定结果 —— 字段本身就是证据，不另存一份解释。"""

    gate_id: str
    title: str
    verdict: str
    exit_code: int | None = None
    scanned: int | None = None
    skipped_count: int | None = None
    blocked: int | None = None
    claim: str = ""
    skip_reason: str = ""
    detail: str = ""
    #: 被排除清单挡下的可疑行（「我为什么没读它」与读数同等重要）。
    rejected: list[str] = field(default_factory=list)
    ms: int = 0
    output: str = field(default="", repr=False)

    def as_dict(self) -> dict:
        return {
            "gate": self.gate_id,
            "verdict": self.verdict,
            "exit": self.exit_code,
            "scanned": self.scanned,
            "skipped": self.skipped_count,
            "blocking": self.blocked,
            "claim": self.claim,
            "skip_reason": self.skip_reason,
            "detail": self.detail,
            "rejected": self.rejected,
            "ms": self.ms,
        }


# --------------------------------------------------------------------------- #
# registry / gate script discovery
# --------------------------------------------------------------------------- #


def locate_registry(explicit: str | None, gatesuite: str | None, python: str) -> Path:
    """找到 registry.json；找不到就**响亮地**停下，绝不退 0。

    两种形态与 `run.ts` 同源：仓内 `tools/gate/governance/registry.json`，
    包内 `<site-packages>/allin_governance/_gatesuite/registry.json`。默认向解释器
    问包的位置（包是本仓唯一的套件来源），也接受显式 `--registry` / `--gatesuite`。
    """
    if explicit:
        return Path(explicit).resolve()
    if gatesuite:
        return (Path(gatesuite) / "registry.json").resolve()
    probe = (
        "import allin_governance,os,sys;"
        "sys.stdout.write(os.path.join(os.path.dirname(allin_governance.__file__),"
        "'_gatesuite','registry.json'))"
    )
    done = subprocess.run(
        [python, "-c", probe],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    candidate = (done.stdout or "").strip()
    if done.returncode == 0 and candidate and Path(candidate).is_file():
        return Path(candidate)
    raise SystemExit(
        "BLIND_GATES ENV ERROR: 找不到门禁套件的 registry.json\n"
        f"  解释器：{python}\n"
        f"  探针输出：{candidate or (done.stderr or '').strip()}\n"
        "  先 `pip install allin-governance`，或用 --registry / --gatesuite 显式指定。"
    )


def resolve_script(script_rel: str, gatesuite: Path) -> Path:
    """`governance/gates/x.py` 在包内形态下少一层前缀（与 run.ts 的 gateScript 同口径）。"""
    rel = script_rel
    if gatesuite.name.endswith("_gatesuite") and rel.startswith("governance/"):
        rel = rel[len("governance/"):]
    return (gatesuite / rel).resolve()


def load_registry(path: Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"BLIND_GATES ENV ERROR: registry 不可读（{path}）：{error}") from error
    gates = raw.get("gates") if isinstance(raw, dict) else None
    if not isinstance(gates, list) or not gates:
        raise SystemExit(f"BLIND_GATES ENV ERROR: {path} 没有声明任何门禁（0 道 = 无从判定）")
    return gates


# --------------------------------------------------------------------------- #
# 判定
# --------------------------------------------------------------------------- #


def classify(output: str, code: int) -> tuple[str, dict]:
    """把「一段门禁输出 + 退出码」判成一个 verdict，附带证据字段。

    纯函数（不碰进程、不碰文件），所以本工具自己的 `--selfcheck` 能直接喂假输出
    验它 —— 一段判据如果连「假的红」都测不出来，它自己就是盲门。
    """
    summary = SUMMARY_RE.search(output)
    scanned: int | None
    skipped_count: int | None = None
    blocked: int | None = None
    claim = ""
    rejected: list[str] = []
    if summary is not None:
        scanned = int(summary.group("scanned"))
        blocked = int(summary.group("blocking"))
        skipped_count = int(summary.group("skipped"))
        claim = summary.group("claim").strip()
    else:
        # 白名单第 ②③ 形态：逐行判，先过排除清单（豁免行 / 统计标签 / SKIP 行 / 注释），
        # 被排除的行**记下原因**当证据 —— 「我为什么没读它」必须和读数一样可见，
        # 否则下一个人只看到 undetermined，不知道该去核哪一行。
        scanned = None
        for line in output.splitlines():
            reason = reject_reason(line)
            if reason:
                if len(rejected) < 3 and re.search(r"scanned", line, re.IGNORECASE):
                    rejected.append(f"{reason}：{line.strip()[:100]}")
                continue
            match = SCANNED_RENDERED_RE.search(line) or SCANNED_JSON_KEY_RE.search(line)
            if match is not None:
                scanned = int(match.group(1))
                break
        # 非 govlib 输出没有「标题: scanned …」这种形态，只能拿首行当「它声称在做什么」。
        # 首行过长时（例如 g15 那种几十项豁免统计）不当作 claim —— 那种行不是声明，
        # 硬拿它当声明会让判红文案指向噪声。
        first = output.strip().splitlines()[0].strip() if output.strip() else ""
        claim = first if len(first) <= 120 else ""

    reason_match = SKIP_REASON_RE.search(output)
    skip_reason = reason_match.group(1).strip() if reason_match is not None else ""
    # 显式 SKIP 的判据按强度分三档，任一成立即算「它自己说了没量」：
    #   ① 摘要行里的 skipped 计数 > 0（govlib 口径，最可靠）；
    #   ② 正文里有 `SKIPPED (not a pass)` 理由行；
    #   ③ 行首有 SKIP/SKIPPED 标记，或正文出现 not_applicable。
    explicit_skip = (
        (skipped_count is not None and skipped_count > 0)
        or bool(skip_reason)
        or SKIP_LINE_RE.search(output) is not None
        or NOT_APPLICABLE_RE.search(output) is not None
    )

    evidence = {
        "scanned": scanned,
        "skipped_count": skipped_count,
        "blocked": blocked,
        "claim": claim,
        "skip_reason": skip_reason,
        "rejected": rejected,
    }

    if code != 0:
        # 门禁自己已经判红了 —— 这不是盲门，是响亮的红。不重复计数，
        # 但也不许它悄悄混进「通过」。
        evidence["detail"] = f"exit {code}（门禁自己报错/阻断，非盲门）"
        return FAILED, evidence
    if scanned is None:
        evidence["detail"] = "输出里没有具名的 scanned 读数（摘要行 / `scanned N file(s)` / `\"scanned\": N`）"
        return UNDETERMINED, evidence
    if scanned > 0:
        evidence["detail"] = f"scanned {scanned} 个对象，blocking {blocked if blocked is not None else '-'}"
        return MEASURED, evidence
    if explicit_skip:
        evidence["detail"] = (
            f"scanned 0 但显式 SKIP（{skip_reason or '标记无理由文本'}）—— not a pass，非盲门"
        )
        return SKIPPED, evidence
    evidence["detail"] = "scanned 0 + exit 0 + 无任何 SKIP 标记"
    return BLIND, evidence


def run_gate(python: str, script: Path, root: Path, extra: list[str], timeout: int) -> tuple[int | None, str, int, str]:
    """跑一道门禁，返回 (退出码|None, 合并输出, 耗时ms, 错误说明)。"""
    started = time.time()
    try:
        done = subprocess.run(
            [python, str(script), "--root", str(root), *extra],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", int((time.time() - started) * 1000), f"超时（>{timeout}s）：门禁没跑完，无从判定"
    except OSError as error:
        return None, "", int((time.time() - started) * 1000), f"无法调起门禁：{error}"
    return done.returncode, done.stdout or "", int((time.time() - started) * 1000), ""


def judge_all(
    gates: list[dict],
    gatesuite: Path,
    root: Path,
    python: str,
    timeout: int,
    only: list[str] | None = None,
) -> list[GateResult]:
    """逐道判定；**逐道**而不是读聚合退出码，否则一道盲门会被其余 19 道盖住。"""
    results: list[GateResult] = []
    platform = host_platform()
    for gate in gates:
        gate_id = str(gate.get("id") or "<unnamed>")
        title = str(gate.get("title") or "")
        if only is not None and gate_id not in only:
            continue
        platforms = gate.get("platforms") or []
        if isinstance(platforms, list) and platforms and platform not in platforms:
            results.append(
                GateResult(
                    gate_id=gate_id,
                    title=title,
                    verdict=SKIPPED_PLATFORM,
                    detail=f"registry 声明 platforms={platforms}，本机是 {platform}：不适用，未判",
                )
            )
            continue
        script_rel = str(gate.get("script") or "")
        script = resolve_script(script_rel, gatesuite)
        if not script_rel or not script.is_file():
            results.append(
                GateResult(
                    gate_id=gate_id,
                    title=title,
                    verdict=ERROR,
                    detail=f"registry 声明的脚本不存在：{script}",
                )
            )
            continue
        extra = ["--no-profile"] if gate.get("profileProbe") is True else []
        code, output, ms, error = run_gate(python, script, root, extra, timeout)
        if code is None:
            results.append(
                GateResult(gate_id=gate_id, title=title, verdict=ERROR, detail=error, ms=ms, output=output)
            )
            continue
        verdict, evidence = classify(output, code)
        results.append(
            GateResult(
                gate_id=gate_id,
                title=evidence["claim"] or title,
                verdict=verdict,
                exit_code=code,
                scanned=evidence["scanned"],
                skipped_count=evidence["skipped_count"],
                blocked=evidence["blocked"],
                claim=evidence["claim"] or title,
                skip_reason=evidence["skip_reason"],
                detail=evidence["detail"],
                rejected=evidence["rejected"],
                ms=ms,
                output=output,
            )
        )
    return results


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #


def print_table(results: list[GateResult]) -> None:
    width = max((len(item.gate_id) for item in results), default=8)
    print()
    print(f"{'GATE'.ljust(width)}  {'SCANNED':>7}  {'EXIT':>4}  {'VERDICT':<17} EVIDENCE")
    print("-" * (width + 46))
    for item in results:
        scanned = "-" if item.scanned is None else str(item.scanned)
        code = "-" if item.exit_code is None else str(item.exit_code)
        verdict = item.verdict if item.verdict != BLIND else "BLIND (!)"
        print(f"{item.gate_id.ljust(width)}  {scanned:>7}  {code:>4}  {verdict:<17} {item.detail}")


def print_findings(results: list[GateResult]) -> None:
    """判红文案要能独立成证据：哪一道、它声称扫了什么、为什么这算「没量」。"""
    blind = [item for item in results if item.verdict == BLIND]
    for item in blind:
        print()
        print(f"BLIND {item.gate_id}：「{item.claim}」")
        print(f"  它声称在判：{item.title}")
        print(f"  它实际报的：scanned 0 file(s)，exit 0，没有任何 SKIP/SKIPPED/not_applicable 标记")
        print("  为什么这算「没量」：一个对象都没读，却退出 0 —— 「没跑」与「跑过且没问题」")
        print("  在退出码上完全同形。下游拿到 0 只会以为「查过了，干净」。")
        tail = [line for line in item.output.strip().splitlines() if line.strip()][-4:]
        for line in tail:
            print(f"    | {line}")
    undetermined = [item for item in results if item.verdict == UNDETERMINED]
    # 一等结论（ADR-0011 D3-H）：undetermined 与 measured / blind **并列计数**，
    # 禁止在统计时折叠 —— 折进「未量」会与 SKIP 混账，折进「有量」就是这次事故本身。
    # 因此这一行**每次都打**（含 undetermined=0），且带名字；不打就等于让它消失。
    print()
    print(f"UNDETERMINED: {len(undetermined)} ({', '.join(item.gate_id for item in undetermined) or '无'})")
    if undetermined:
        print("不可判定（UNDETERMINED，不是通过 —— 无从证明它量了东西）：")
        for item in undetermined:
            print(f"  - {item.gate_id}：「{item.title}」{item.detail}")
            for rejected in item.rejected:
                print(f"      排除的可疑行 → {rejected}")
        print("  修法（属各门禁 owner 的活，本工具不改门禁本体）：让该道门禁像其余门禁一样")
        print("  用 govlib.Report.scanned 计数并渲染出 `scanned N file(s)`。")


def summarize(results: list[GateResult]) -> dict:
    counts = {
        "total": len(results),
        "measured": 0,
        "skipped": 0,
        "blind": 0,
        "undetermined": 0,
        "failed": 0,
        "skipped_platform": 0,
        "error": 0,
    }
    for item in results:
        key = item.verdict.replace("-", "_")
        counts[key] = counts.get(key, 0) + 1
    return counts


def record(results: list[GateResult], counts: dict, path: Path, root: Path) -> None:
    """落一行机读留痕（audit/ 已被 .gitignore 覆盖，属运行时产物）。

    留痕失败不改变判定（本仓既有口径）：宁可少一条记录，也不能因为记账把结论污染。

    2026-11-25 复盘补三个字段（`commit` / `dirty` / `untracked`）：没有 commit，
    这份历史就只能回答「上次跑了多少」，回答不了「**跨提交**它有没有多看见东西」。
    而「scanned 跨提交不变」正是覆盖未跟进的那个唯一信号（见 §覆盖未跟进）。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record_obj = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "root": str(root),
            "commit": head_commit(root) or "",
            "dirty": len(dirty_paths(root)),
            "untracked": untracked_files(root),
            "summary": counts,
            "gates": [item.as_dict() for item in results],
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record_obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 元判据之四：registry 之外的判据（例外必须显式、可读、单点维护）
#
# registry.json 描述的是**「判仓库」的 20 道套件契约**（g00–g20，缺 g02）。有些判据不在这份
# 契约里，但确实在跑、确实会红。它们最危险的处置方式是「代码里没写 ⇒ 当成不存在」——
# 那就是死门的生成方式，而且它不留任何证据。
#
# 口径（team-lead 裁决，2026-11-25）：**g21 不登记进 registry**（登记会把「20 道」改成 21，
# 牵连 SPEC-204 架构图、SVG 对账、g00 契约与多处文档数字 —— 为一个归属问题制造涟漪），
# 但**必须显式列出**：清单落在 `tools/gate/README.md §12` 的机器可读块里，
# 本工具**从那里读**，不硬编码任何一条 —— 以后新增 registry 外判据，只有那一处要改。
#
# 三条核验（都是可证伪的，不是"我看了下没问题"）：
#   ① 清单块存在且可解析（块没了 = 例外重新变成不可见 ⇒ 判红）；
#   ② 每条声明的入口文件真的存在（声明了但文件不在 = 清单在骗人 ⇒ 判红）；
#   ③ 每条声明的入口文件真的出现在 `scripts/run_all_gates.sh` 里（声明"已接线"必须可验
#      ⇒ 没接线就是死门候补，判红）；并且它**不该**已经出现在 registry 里
#      （已经在契约里了却还挂在例外清单 = 清单陈旧 ⇒ 判红）。
#
# 不做反向完备性核验（"tools/gate/ 下所有 .py 都得登记"）：那里还有十来个一次性脚本与
# 辅助模块，逼它们全登记只会训出一个没人看的清单 —— 一个靠噪音维持的清单等于没有清单。
# --------------------------------------------------------------------------- #

REGISTRY_EXTERNAL_BEGIN = "<!-- registry-external-gates:begin -->"
REGISTRY_EXTERNAL_END = "<!-- registry-external-gates:end -->"


def judge_registry_external(
    text: str, registry_ids: set[str], wiring_text: str | None, exists
) -> tuple[list[dict], list[str]]:
    """解析并核验「registry 之外的判据」清单。纯函数（`exists` 可注入）以便自检。

    返回 (entries, findings)。findings 非空即判红 —— 例外的可见性本身是一条判据。
    """
    findings: list[str] = []
    entries: list[dict] = []
    begin = text.find(REGISTRY_EXTERNAL_BEGIN)
    end = text.find(REGISTRY_EXTERNAL_END)
    if begin < 0 or end < 0 or end < begin:
        findings.append(
            "清单块不存在（`tools/gate/README.md §12` 的 registry-external-gates begin/end 标记）："
            "registry 之外的判据重新变成不可见 —— 那正是死门的生成方式"
        )
        return entries, findings
    body = text[begin + len(REGISTRY_EXTERNAL_BEGIN):end]
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            findings.append(f"清单行格式不合法（应为 `id | 入口文件 | 为什么不在 registry`）：{line[:80]}")
            continue
        entry = {"id": parts[0], "entry": parts[1], "why": parts[2] if len(parts) > 2 else ""}
        entries.append(entry)
        if not exists(entry["entry"]):
            findings.append(f"{entry['id']}：清单声明的入口不存在（{entry['entry']}）")
        if entry["id"] in registry_ids:
            findings.append(f"{entry['id']}：已在 registry 契约里，应从本清单删除（清单陈旧）")
        if wiring_text is None:
            continue  # 接线文件不在（判的是别的仓）⇒ 跳过该项，不制造假红
        if entry["entry"] not in wiring_text:
            findings.append(
                f"{entry['id']}：清单声明它已接线，但 `scripts/run_all_gates.sh` 里找不到 {entry['entry']}"
                "（声明与事实不一致 = 死门候补）"
            )
    if not entries and not findings:
        findings.append("清单块存在但没有任何条目：要么补条目，要么删块（空清单等于没清单）")
    return entries, findings




def check_registry_external_files(
    readme_dir: Path, registry_ids: list[str], root: Path
) -> tuple[list[dict], list[str]]:
    """把 README 与接线脚本读进来，交给纯函数判定（读不到 = finding，不是"没有例外"）。"""
    readme = readme_dir / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
    except OSError as error:
        return [], [f"清单文件读不到（{readme}）：{error} —— 例外因此不可见"]
    wiring_path = root / "scripts" / "run_all_gates.sh"
    try:
        wiring_text: str | None = wiring_path.read_text(encoding="utf-8")
    except OSError:
        # 判的是别的仓（没有本仓的接线脚本）⇒ 跳过接线核验，但要说出来，别假装核过。
        wiring_text = None
    return judge_registry_external(text, set(registry_ids), wiring_text, lambda rel: (readme_dir / rel).is_file())


# --------------------------------------------------------------------------- #
# 元判据之三：覆盖未跟进（scanned 数没变 / 新文件不在扫描面）
#
# 为什么「scanned 没变」本身是信号：
#
# 2026-11-25 ADR-0011 验收现场（Archi 复核、team-lead 转述）：
#   新建 ADR-0011 后跑 `g19 --only g19-docs-refs` 得 `scanned 88 / blocking 0`，
#   看起来是绿的 —— 但 scanned 仍是 88，与建文件**之前**一模一样。原因不是巧合：
#   门禁的语料来自 `git ls-files`，**未入索引的新文件根本不在任何门禁的扫描面里**。
#   所以那条绿不是「新文件没问题」，而是「新文件没被看见」。
#
# 结构上的根因（比案例更狠）：govlib.Report.exit_code() **从不读 scanned** ——
#   它只看 findings 与（严格模式下的）skipped。也就是说一道门禁可以合法地
#   「一个对象都没读、退 0」，而共享出口不会有任何意见；g00-meta 核的也是
#   caught/clean/misreports，同样不看 scanned。整条链上没有任何一处对
#   「你读到了东西吗」有判据 —— 这就是本文件存在的理由。
#
# 因此这里判两件事，硬度不同，绝不含糊其辞：
#   ① **硬信号（可证伪）**：工作树里存在未入索引的文件 ⇒ 本批所有 scanned 与
#      blocking 都只对**索引内的文件**成立。理由不是推断，是语料来源的事实。
#      它不可判红（谁都有正在写的新文件），但必须可见 —— 否则「20/20 clean」
#      会被当成对新文件的结论。
#   ② **软信号（提示）**：与上一个**不同提交**的留痕相比，本区间新增了已跟踪文件，
#      而某道门禁的 scanned 一个没多 ⇒ 「覆盖未跟进」。之所以只作提示不作判红：
#      scanned 不变也可能只是新文件不在该道语境内（加一个 .md 不该改变 g09 对
#      .py 的计数）。要把它变成硬判据，registry 得先声明每道门的**扫描域**
#      （scope glob）；registry 现在没有这个字段，硬判必然大量误报。
#      —— 缺的那个事实我如实说出来，而不是用一条会叫的假判据顶上去。
# --------------------------------------------------------------------------- #

COVERAGE_FOLLOWED = "followed"
COVERAGE_LAG = "coverage-not-followed"
COVERAGE_INCONCLUSIVE = "inconclusive"


def git(root: Path, *args: str) -> tuple[int, str]:
    """跑一条 git 命令；失败一律降级为「拿不到」，绝不当成「没有」。"""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return done.returncode, done.stdout or ""


def head_commit(root: Path) -> str | None:
    code, out = git(root, "rev-parse", "HEAD")
    return out.strip() if code == 0 and out.strip() else None


def untracked_files(root: Path) -> list[str]:
    """未入索引且未被 .gitignore 排除的文件 —— 它们是所有门禁的共同盲区。"""
    code, out = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if code != 0:
        return []
    return [entry for entry in out.split("\0") if entry]


def dirty_paths(root: Path) -> list[str]:
    code, out = git(root, "status", "--porcelain")
    if code != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def added_between(root: Path, previous: str, current: str) -> list[str]:
    """两个提交之间**新增**的已跟踪文件（`--diff-filter=A`）。"""
    if not previous or not current or previous == current:
        return []
    code, out = git(root, "diff", "--name-only", "--diff-filter=A", f"{previous}..{current}", "-z")
    if code != 0:
        return []
    return [entry for entry in out.split("\0") if entry]


def judge_coverage_delta(previous: int | None, current: int | None, added: list[str]) -> tuple[str, str]:
    """纯函数：**scanned 数没变**算不算信号。

    被抽成纯函数，是为了让 `--selfcheck` 能对四种答案（跟进/未跟进/无新增/无历史）
    逐条断言 —— 一个只在真仓里跑过一次的判据，不知道自己会不会在别的形态上沉默。
    """
    if not added:
        return COVERAGE_INCONCLUSIVE, "本区间没有新增的已跟踪文件，无信号"
    if previous is None or current is None:
        return COVERAGE_INCONCLUSIVE, "缺 scanned 读数（无历史留痕或该道未报 scanned）"
    if current == previous:
        return COVERAGE_LAG, f"scanned {previous} -> {current} 不增，而本区间新增了 {len(added)} 个文件"
    return COVERAGE_FOLLOWED, f"scanned {previous} -> {current}（新增 {len(added)} 个文件）"


def load_previous(path: Path, current_commit: str | None) -> dict | None:
    """取上一个**不同提交**的留痕行；同一提交的多批没有信息量（scanned 必然相同）。

    读不到 / 解析不了都返回 None —— 判据在缺数据时应当说「不可判定」，
    而不是把「没有历史」当成「没问题」。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    previous: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        commit = str(entry.get("commit") or "")
        if not commit or commit == current_commit:
            continue
        if isinstance(entry.get("gates"), list):
            previous = entry
    return previous


def coverage_report(
    results: list[GateResult], root: Path, record_path: Path | None
) -> tuple[dict, int]:
    """打印覆盖未跟进的两个信号；返回 (汇总, 是否发现覆盖未跟进)。"""
    untracked = untracked_files(root)
    print()
    if untracked:
        print("COVERAGE_INDEX_ONLY：本批的 scanned / blocking 只对**索引内**的文件成立")
        print("  门禁语料 = `git ls-files`，下列未入索引的新文件不在任何门禁的扫描面里：")
        for path in untracked:
            print(f"    - {path}")
        print("  ⇒ 它们上面的「绿」不含任何证据。要覆盖：git add 后复跑，或用该道门禁的")
        print("    scan_*() 直扫该文件（g19 用 scan_doc()，g13 用 scan() 等）。")
    else:
        print("COVERAGE_INDEX_ONLY：无 —— 工作树没有未入索引的新文件，本批覆盖全部已跟踪文件")

    current_commit = head_commit(root)
    previous = load_previous(record_path, current_commit) if record_path else None
    added = added_between(root, str(previous.get("commit")), current_commit) if previous else []
    lag_count = 0
    followed = 0
    inconclusive = 0
    print()
    if previous is None:
        print("COVERAGE_DELTA：不可判定 —— 没有**另一个提交**的留痕可比（首次运行或始终同一提交）")
        print("  这不是「覆盖跟上了」，是「无从判断」。跨提交留痕会由 --record 自动累积。")
        inconclusive = len(results)
    else:
        print(f"COVERAGE_DELTA prior={previous.get('commit')} head={current_commit or '(未知)'} "
              f"added={len(added)}")
        prior_scanned = {
            str(entry.get("gate")): entry.get("scanned")
            for entry in previous.get("gates", [])
            if isinstance(entry, dict)
        }
        for item in results:
            old = prior_scanned.get(item.gate_id)
            old = old if isinstance(old, int) else None
            verdict, detail = judge_coverage_delta(old, item.scanned, added)
            if verdict == COVERAGE_LAG:
                lag_count += 1
                print(f"  {item.gate_id:<26} {verdict}：{detail}  ← 它没多看见东西")
            elif verdict == COVERAGE_FOLLOWED:
                followed += 1
            else:
                inconclusive += 1
        if lag_count == 0 and added:
            print(f"  本次新增 {len(added)} 个已跟踪文件，全部有 scanned 变化的道已跟进")
    summary = {
        "untracked": len(untracked),
        "index_only": 1 if untracked else 0,
        "added": len(added),
        "lag": lag_count,
        "followed": followed,
        "inconclusive": inconclusive,
    }
    print(
        "COVERAGE_SUMMARY "
        f"untracked={len(untracked)} index_only={summary['index_only']} added={len(added)} "
        f"lag={lag_count} followed={followed} inconclusive={inconclusive}"
    )
    return summary, lag_count


# --------------------------------------------------------------------------- #
# 元判据之二：两半自检（caught / clean 各至少一个样本）
# --------------------------------------------------------------------------- #

#: 自证有效性的严格契约（RULES.md §自证有效）：恰好三键、紧凑分隔符、整行。
#: 用严格形态而不是 `caught.*?(\d+)` 之类的宽松匹配，理由同上：宽松兜底会把
#: 「输出里恰好提到这个词」当成「它确实这么做了」。
SELFCHECK_RE = re.compile(r'^SELFCHECK \{"caught":(\d+),"clean":(\d+),"misreports":(\d+)\}$', re.MULTILINE)

BOTH_HALVES = "both"
NO_CATCH = "no-catch"
NO_CLEAN = "no-clean"
MISREPORTS = "misreports"
NO_LINE = "no-selfcheck-line"
SELFCHECK_RED = "selfcheck-exit"


def judge_selfcheck_line(output: str, code: int) -> tuple[str, dict]:
    """判定一道门禁的 `--selfcheck` 是否**两半都验**了。

    为什么单独判这件事：只验红（caught>0, clean==0）的门禁无法证明自己不误报，
    只验静（clean>0, caught==0）的门禁无法证明自己会红 —— 后者正是「一条检查若
    不能失败，就什么都没告诉你」。govlib.SelfCheck.finish() 已把 caught==0 或
    clean==0 判红，但门禁可以绕过它手搓 SELFCHECK 行（g15 就是这么干的，g00 也
    允许），所以这条判据不能只依赖 govlib 的行为。
    """
    match = SELFCHECK_RE.search(output)
    evidence: dict = {"caught": None, "clean": None, "misreports": None, "note": ""}
    if match is None:
        evidence["note"] = "输出里没有严格形态的 SELFCHECK 行 —— 结构缺失，无从判定两半"
        return NO_LINE, evidence
    caught, clean, misreports = (int(value) for value in match.groups())
    evidence.update({"caught": caught, "clean": clean, "misreports": misreports})
    # 顺序是有意的：先判「哪一半缺」，再判退出码。若反过来，只验一半的门禁会先被
    # 归成「自检自身红」—— 那是它退 1 的**后果**，不是**原因**；owner 要的是原因。
    if misreports:
        evidence["note"] = f"干净样本被误报 {misreports} 次（假阳性）"
        return MISREPORTS, evidence
    if caught < 1:
        evidence["note"] = "只验静、不验红：注入的缺陷一个都没抓到"
        return NO_CATCH, evidence
    if clean < 1:
        evidence["note"] = "只验红、不验静：没有一个干净样本被证明不误报"
        return NO_CLEAN, evidence
    if code != 0:
        evidence["note"] = f"两半数据齐全，但自检自身退出 {code}（它自己已经判红了）"
        return SELFCHECK_RED, evidence
    if clean == 1:
        evidence["note"] = "两半齐全但薄：clean 只有 1 个样本（建议补第二条干净样本，不阻断）"
    return BOTH_HALVES, evidence


def two_halves(gates: list[dict], gatesuite: Path, root: Path, python: str, timeout: int) -> int:
    """逐道跑 `--selfcheck`，把「两半自检」变成一张可机检的表 + 一个退出码。"""
    rows: list[tuple[str, tuple[str, dict]]] = []
    platform = host_platform()
    width = max((len(str(gate.get("id"))) for gate in gates), default=8)
    print(f"{'GATE'.ljust(width)}  {'CAUGHT':>6}  {'CLEAN':>5}  {'MISREP':>6}  结论")
    print("-" * (width + 44))
    counts = {BOTH_HALVES: 0, NO_CATCH: 0, NO_CLEAN: 0, MISREPORTS: 0, NO_LINE: 0, SELFCHECK_RED: 0,
              SKIPPED_PLATFORM: 0}
    for gate in gates:
        gate_id = str(gate.get("id") or "<unnamed>")
        platforms = gate.get("platforms") or []
        if isinstance(platforms, list) and platforms and platform not in platforms:
            counts[SKIPPED_PLATFORM] += 1
            print(f"{gate_id.ljust(width)}  {'-':>6}  {'-':>5}  {'-':>6}  {SKIPPED_PLATFORM}（platforms={platforms}）")
            continue
        script_rel = str(gate.get("script") or "")
        script = resolve_script(script_rel, gatesuite)
        if not script_rel or not script.is_file():
            counts[NO_LINE] += 1
            print(f"{gate_id.ljust(width)}  {'-':>6}  {'-':>5}  {'-':>6}  {NO_LINE}（脚本不存在：{script}）")
            continue
        code, output, _ms, error = run_gate(python, script, root, ["--selfcheck"], timeout)
        if code is None:
            counts[NO_LINE] += 1
            print(f"{gate_id.ljust(width)}  {'-':>6}  {'-':>5}  {'-':>6}  {NO_LINE}（{error}）")
            continue
        verdict, evidence = judge_selfcheck_line(output, code)
        counts[verdict] += 1
        rows.append((gate_id, (verdict, evidence)))
        caught = "-" if evidence["caught"] is None else str(evidence["caught"])
        clean = "-" if evidence["clean"] is None else str(evidence["clean"])
        misreports = "-" if evidence["misreports"] is None else str(evidence["misreports"])
        print(f"{gate_id.ljust(width)}  {caught:>6}  {clean:>5}  {misreports:>6}  {verdict}"
              + (f"｜{evidence['note']}" if evidence["note"] else ""))

    total = len(gates)
    print()
    print(
        "TWO_HALVES_SUMMARY "
        f"total={total} both={counts[BOTH_HALVES]} no_catch={counts[NO_CATCH]} "
        f"no_clean={counts[NO_CLEAN]} misreports={counts[MISREPORTS]} "
        f"no_selfcheck_line={counts[NO_LINE]} selfcheck_exit={counts[SELFCHECK_RED]} "
        f"skipped_platform={counts[SKIPPED_PLATFORM]}"
    )
    thin = [gate_id for gate_id, (verdict, evidence) in rows if verdict == BOTH_HALVES and evidence["clean"] == 1]
    if thin:
        print(f"  薄（clean 仅 1 样本，不阻断、建议各 owner 补）：{', '.join(thin)}")
    bad = [
        gate_id for gate_id, (verdict, _evidence) in rows
        if verdict not in (BOTH_HALVES,)
    ]
    if bad:
        print(f"  待补（只覆盖一半 / 结构缺失 / 自检红）：{', '.join(bad)}")
    return EXIT_BLOCKING if bad else EXIT_OK


# --------------------------------------------------------------------------- #
# 自检：证明这道判据自己会红
# --------------------------------------------------------------------------- #


#: 假门禁矩阵。每一行是一个「必须在真机上也成立」的判定分支：
#: 本工具若对任何一行判错，它就没有资格去判那 20 道真门禁。
FAKE_CASES: tuple[tuple[str, str, int, str], ...] = (
    # (gate_id, 输出, 退出码, 期望 verdict)
    (
        "fake-blind",
        "fake blind gate: scanned 0 file(s); blocking 0; exempted 0; skipped 0.\n",
        0,
        BLIND,
    ),
    (
        "fake-measured",
        "fake clean gate: scanned 3 file(s); blocking 0; exempted 0; skipped 0.\n",
        0,
        MEASURED,
    ),
    (
        "fake-skip",
        "fake skip gate: scanned 0 file(s); blocking 0; exempted 0; skipped 1.\n"
        "  SKIPPED (not a pass): nothing in scope=1\n",
        0,
        SKIPPED,
    ),
    (
        "fake-nofield",
        "blocking=0 baseline=0 new=0 reported=0 skipped=0\n",
        0,
        UNDETERMINED,
    ),
    (
        # 成对反例（2026-11-25 实测踩到）：豁免标签 `D16-plan-scanned=1` 里的
        # `scanned=` 不是 scanned 计数。兜底正则若把它算进去，本工具就会替一道
        # 不报 scanned 的门禁编出一个数字，把「不可判定」洗成「有量」。
        "fake-lookalike",
        "blocking=0 baseline=0 new=0 reported=0 skipped=0\n"
        "  exempted: D16-plan-scanned=1, D15-file-clean=141\n",
        0,
        UNDETERMINED,
    ),
    # 排除清单四类，一类一条反例（缺一类就有一种行能冒充读数）。
    (
        "fake-lookalike-label",  # ① 别人的统计标签（不在 exempted: 行内，靠标签模式挡）
        "note: D16-plan-scanned=1 (stats)\nblocking=0 baseline=0\n",
        0,
        UNDETERMINED,
    ),
    (
        # ①**承重**反例：同一行里有别的门禁的 `"gate"` 键 + `scanned` 键。
        # 白名单第 ③ 形态会把它读成自己的读数（scanned=1）；只有「别人的逐道记录」
        # 这条排除规则能挡住。去掉那条规则，本用例立刻变成 measured(1) 而失败。
        "fake-lookalike-foreign-record",
        '{"gate": "D16-plan", "scanned": 1, "blocking": 0}\n',
        0,
        UNDETERMINED,
    ),
    (
        "fake-lookalike-skip",  # ② SKIP 标记行里提到的数字不算本次读数
        "SKIPPED (not a pass): scanned 0 file(s) 的比照=1\n",
        0,
        UNDETERMINED,
    ),
    (
        "fake-lookalike-comment",  # ③④ 注释行 / 被引用的历史数字
        "# 上次跑是 scanned 3 file(s)，本次没报\nblocking=0\n",
        0,
        UNDETERMINED,
    ),
    (
        "fake-red",
        "fake red gate: scanned 0 file(s); blocking 2; exempted 0; skipped 0.\n",
        1,
        FAILED,
    ),
    (
        "fake-nonzero-measured",
        "fake loud gate: scanned 7 file(s); blocking 1; exempted 0; skipped 0.\n",
        1,
        FAILED,
    ),
)

#: 两半判据的成对反例：正例（两半齐全）与三种残缺形态都必须在矩阵里，
#: 否则「只覆盖一半」这一类会静默通过 —— 那正是本判据要防的病。
FAKE_SELFCHECK_CASES: tuple[tuple[str, str, int, str], ...] = (
    ("sc-both", 'SELFCHECK {"caught":3,"clean":2,"misreports":0}\n', 0, BOTH_HALVES),
    ("sc-one-clean", 'SELFCHECK {"caught":0,"clean":4,"misreports":0}\n', 1, NO_CATCH),
    ("sc-one-caught", 'SELFCHECK {"caught":5,"clean":0,"misreports":0}\n', 1, NO_CLEAN),
    ("sc-misreport", 'SELFCHECK {"caught":3,"clean":2,"misreports":1}\n', 1, MISREPORTS),
    # 宽松匹配会把这个 note 行也当成 SELFCHECK —— 严格形态要求整行匹配，故记结构缺失。
    ("sc-note-only", 'SELFCHECK note: 别名不可遍历\ncaught=9 clean=9\n', 0, NO_LINE),
    ("sc-red", 'SELFCHECK {"caught":3,"clean":2,"misreports":0}\n', 2, SELFCHECK_RED),
)

#: 覆盖未跟进的四种答案 —— 缺任何一种，这条判据就有沉默的分支。
FAKE_COVERAGE_CASES: tuple[tuple[str, int | None, int | None, list[str], str], ...] = (
    ("cv-lag", 88, 88, ["architecture/adr/ADR-0011-x.md"], COVERAGE_LAG),
    ("cv-followed", 88, 91, ["architecture/adr/ADR-0011-x.md"], COVERAGE_FOLLOWED),
    ("cv-no-new-files", 88, 88, [], COVERAGE_INCONCLUSIVE),
    ("cv-no-history", None, 88, ["x.md"], COVERAGE_INCONCLUSIVE),
    ("cv-gate-silent", 88, None, ["x.md"], COVERAGE_INCONCLUSIVE),
)


def selfcheck() -> int:
    """用假门禁跑**同一条代码路径**（classify + judge_all + 退出码 + git 覆盖），证明它会红。

    这是「一条检查若不能失败，就什么都没告诉你」的具体落法：只断言「正常输入退 0」
    的检查，永远不知道自己会不会在真问题上退 0。
    """
    failures: list[str] = []
    checked = 0

    def expect(ok: bool, label: str) -> None:
        """记一次断言 —— 分子分母同源，避免「用例数」靠手写的常量漂移。"""
        nonlocal checked
        checked += 1
        if not ok:
            failures.append(label)

    for gate_id, output, code, expected in FAKE_CASES:
        verdict, evidence = classify(output, code)
        expect(verdict == expected, f"{gate_id}: 期望 {expected}，实得 {verdict}（{evidence['detail']}）")

    # 两半自检的解析器同样要成对验：能认「两半齐全」，也能认出「只验一半」。
    for gate_id, output, code, expected in FAKE_SELFCHECK_CASES:
        verdict, evidence = judge_selfcheck_line(output, code)
        expect(verdict == expected,
               f"{gate_id}: 两半判定期望 {expected}，实得 {verdict}（{evidence['note']}）")

    # 覆盖未跟进：scanned 不增 + 有新增文件 ⇒ 必须报 lag；scanned 有增 ⇒ 必须报 followed。
    for case_id, previous, current, added, expected in FAKE_COVERAGE_CASES:
        verdict, detail = judge_coverage_delta(previous, current, added)
        expect(verdict == expected, f"{case_id}: 覆盖判定期望 {expected}，实得 {verdict}（{detail}）")

    # 端到端：造一个假套件目录 + 假门禁脚本，走完整 judge_all（真起子进程）。
    import tempfile

    with tempfile.TemporaryDirectory(prefix="blind-gates-selfcheck-") as tmp:
        tmp_path = Path(tmp)
        suite = tmp_path / "suite"
        suite.mkdir()
        gates: list[dict] = []
        for gate_id, output, code, _expected in FAKE_CASES:
            body = (
                "import sys\n"
                f"sys.stdout.write({output!r})\n"
                f"raise SystemExit({code})\n"
            )
            script = suite / f"{gate_id}.py"
            script.write_text(body, encoding="utf-8", newline="\n")
            gates.append(
                {
                    "id": gate_id,
                    "title": f"fixture {gate_id}",
                    "script": script.name,
                    "platforms": ["nt", "posix"],
                }
            )
        # 平台不匹配的假门禁：在两种宿主上都断言它被记为 not applicable，而不是被判红。
        other = "posix" if host_platform() == "nt" else "nt"
        offline = suite / "fake-otherplatform.py"
        offline.write_text("raise SystemExit(0)\n", encoding="utf-8", newline="\n")
        gates.append(
            {
                "id": "fake-otherplatform",
                "title": "fixture other platform",
                "script": offline.name,
                "platforms": [other],
            }
        )
        registry = suite / "registry.json"
        registry.write_text(json.dumps({"gates": gates}, ensure_ascii=False), encoding="utf-8", newline="\n")

        results = judge_all(load_registry(registry), suite, tmp_path, sys.executable, timeout=120)
        got = {item.gate_id: item.verdict for item in results}
        for gate_id, _output, _code, expected in FAKE_CASES:
            expect(got.get(gate_id) == expected, f"端到端 {gate_id}: 期望 {expected}，实得 {got.get(gate_id)}")
        expect(got.get("fake-otherplatform") == SKIPPED_PLATFORM,
               f"端到端 fake-otherplatform: 期望 {SKIPPED_PLATFORM}，实得 {got.get('fake-otherplatform')}")
        counts = summarize(results)
        expect(counts["blind"] == 1, f"汇总盲门数：期望 1，实得 {counts['blind']}")
        # 退出码本身也是判据的一部分：有盲门必须非 0，否则编排层读不到。
        expect(exit_code_for(counts, allow_undetermined=False) == EXIT_BLOCKING, "退出码：含盲门时必须是 1")
        # 只有「有量 + 有据 SKIP」的批必须放行 —— 否则这条判据会变成常红噪音。
        clean_counts = {"total": 2, "measured": 1, "skipped": 1, "blind": 0, "undetermined": 0,
                        "failed": 0, "skipped_platform": 0, "error": 0}
        expect(exit_code_for(clean_counts, allow_undetermined=False) == EXIT_OK,
               "退出码：有量 + 有据 SKIP 的批必须为 0")
        und_counts = {"total": 2, "measured": 1, "skipped": 0, "blind": 0, "undetermined": 1,
                      "failed": 0, "skipped_platform": 0, "error": 0}
        expect(exit_code_for(und_counts, allow_undetermined=False) == EXIT_USAGE,
               "退出码：存在不可判定且未放宽时必须非 0（不可判定 ≠ 通过）")
        expect(exit_code_for(und_counts, allow_undetermined=True) == EXIT_OK,
               "退出码：--allow-undetermined 时必须放行")

    # 端到端覆盖未跟进：真起一个 git 仓，两次提交之间新增文件，scanned 不变 ⇒ 必须报 lag。
    # 这一段走的是 `--coverage-delta` 真正用到的 git 管道（head_commit / added_between /
    # load_previous / untracked_files），不是纯函数替身 —— 否则「git 那半边」从没被测过。
    with tempfile.TemporaryDirectory(prefix="blind-gates-coverage-") as tmp:
        # 留痕文件放在仓**外**（真实用法也是 tools/gate/audit/ 被 .gitignore 覆盖），
        # 否则它自己会被算成「本区间新增的已跟踪文件」—— 第一次写这段时就踩到了，
        # 断言当场报出 added=['b.md','history.jsonl']。
        cover = Path(tmp) / "repo"
        cover.mkdir()
        git(cover, "init", "-q")
        (cover / "a.md").write_text("first\n", encoding="utf-8", newline="\n")
        git(cover, "add", "-A")
        git(cover, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "A")
        first = head_commit(cover)
        history = Path(tmp) / "history.jsonl"
        prior_line = {"commit": first, "gates": [{"gate": "fake", "scanned": 88}]}
        history.write_text(json.dumps(prior_line, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        (cover / "b.md").write_text("second\n", encoding="utf-8", newline="\n")
        git(cover, "add", "-A")
        git(cover, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "B")
        head = head_commit(cover)
        prior = load_previous(history, head)
        expect(prior is not None and prior.get("commit") == first,
               f"load_previous: 应取到上一个不同提交，实得 {prior}")
        added = added_between(cover, first or "", head or "")
        expect(added == ["b.md"], f"added_between: 期望 ['b.md']，实得 {added}")
        verdict, detail = judge_coverage_delta(88, 88, added)
        expect(verdict == COVERAGE_LAG, f"端到端覆盖：scanned 不变 + 有新增文件必须报 lag，实得 {verdict}（{detail}）")
        # 未入索引的新文件：这条硬信号也要端到端验（它就是 ADR-0011 那一现场）。
        (cover / "c-untracked.md").write_text("draft\n", encoding="utf-8", newline="\n")
        found = untracked_files(cover)
        expect(found == ["c-untracked.md"], f"untracked_files: 期望 ['c-untracked.md']，实得 {found}")

    # registry 之外的判据清单：解析器本身也是判据，也要有反例（块缺失 / 入口不存在 /
    # 已进 registry / 声明已接线但脚本里没有）。
    good_block = (
        REGISTRY_EXTERNAL_BEGIN + "\n"
        "# 注释行\n"
        "g21-agent-parity | agent_parity.py | 编排层判据\n"
        "check_blind_gates | check_blind_gates.py | 元判据\n"
        + REGISTRY_EXTERNAL_END + "\n"
    )
    fake_exists = lambda rel: rel in {"agent_parity.py", "check_blind_gates.py"}  # noqa: E731
    wiring = "run tools/gate/agent_parity.py\nrun tools/gate/check_blind_gates.py --root .\n"
    found_entries, found_findings = judge_registry_external(good_block, {"g19-docs-refs"}, wiring, fake_exists)
    expect(len(found_entries) == 2, f"清单解析：期望 2 条，实得 {len(found_entries)}")
    expect(not found_findings, f"清单解析：合法块不该有 finding，实得 {found_findings}")
    for case_id, text, ids, wired, wanted in (
        ("xr-no-block", "no markers here\n", set(), wiring, "清单块不存在"),
        ("xr-missing-file", good_block, set(), wiring, "入口不存在"),
        ("xr-stale", good_block, {"g21-agent-parity"}, wiring, "已在 registry 契约里"),
        ("xr-not-wired", good_block.replace("", "", 0), set(), "run nothing\n", "找不到 agent_parity.py"),
    ):
        _entries, findings = judge_registry_external(
            text, ids, wired,
            (lambda rel: False) if case_id == "xr-missing-file" else fake_exists,
        )
        expect(any(wanted in item for item in findings), f"{case_id}: 期望 finding 含「{wanted}」，实得 {findings}")

    payload = json.dumps(
        {"cases": checked, "pass": checked - len(failures), "fail": len(failures)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    for failure in failures:
        print(f"  FAIL {failure}")
    print(f"BLIND_GATES_SELFCHECK {payload}")
    if failures:
        print("selfcheck failed: 本工具对至少一条已知答案判错了 —— 它没有资格去判真门禁")
        return EXIT_BLOCKING
    print("selfcheck ok: 假盲门被抓、假正常被放、假 SKIP 不算红、无 scanned 字段记为不可判定")
    print("              scanned 不变 + 有新增文件报覆盖未跟进；未入索引文件被单列；两半残缺全被判红")
    return EXIT_OK


def exit_code_for(counts: dict, allow_undetermined: bool) -> int:
    """汇总 → 退出码。抽成函数，是为了让 selfcheck 能直接验它（否则退出码本身无判据）。"""
    if counts.get("blind", 0) > 0:
        return EXIT_BLOCKING
    if counts.get("undetermined", 0) > 0 and not allow_undetermined:
        return EXIT_USAGE
    return EXIT_OK


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    parser = argparse.ArgumentParser(
        description="盲门元判据：scanned 0 + exit 0 + 无 SKIP ⇒ 判红（不占 g 编号，属编排层）"
    )
    parser.add_argument("--root", default=None, help="被判的仓根（默认由本文件位置上溯两级）")
    parser.add_argument("--registry", default=None, help="registry.json 路径（默认向解释器问包的位置）")
    parser.add_argument("--gatesuite", default=None, help="门禁套件目录（含 registry.json 与 gates/）")
    parser.add_argument("--python", default=None, help="跑门禁用的解释器（默认本进程解释器）")
    parser.add_argument("--only", default=None, help="只判这几道（逗号分隔的 gate id）")
    parser.add_argument("--timeout", type=int, default=600, help="单道门禁超时秒数（默认 600）")
    parser.add_argument("--json", action="store_true", help="输出机读 JSON（stdout 最后一行）")
    parser.add_argument("--quiet", action="store_true", help="只打汇总行与判红文案")
    parser.add_argument(
        "--allow-undetermined",
        action="store_true",
        help="存在不可判定项时仍退 0（默认退 2）；判定结果照旧逐条打印，不会变成「通过」",
    )
    parser.add_argument("--record", default=None, help="把本次判定追加为 JSONL（默认不落盘）")
    parser.add_argument("--selfcheck", "--selftest", dest="selfcheck", action="store_true",
                        help="用假门禁证明本判据会红（负对照）")
    parser.add_argument("--two-halves", action="store_true",
                        help="元判据之二：逐道跑 --selfcheck，核 caught/clean 两半是否都验（表格 + 退出码）")
    parser.add_argument("--coverage-delta", action="store_true",
                        help="元判据之三：单列未入索引的新文件（它们不在任何扫描面内），"
                             "并与上一个不同提交的留痕比 scanned 是否跟进（提示，不判红）")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    python = args.python or os.environ.get("DSH_GOVERNANCE_PYTHON") or sys.executable
    registry = locate_registry(args.registry, args.gatesuite, python)
    gates = load_registry(registry)
    if args.two_halves:
        if args.only:
            wanted = {part.strip() for part in args.only.split(",") if part.strip()}
            gates = [gate for gate in gates if str(gate.get("id")) in wanted]
            if not gates:
                print("BLIND_GATES USAGE ERROR: --only 过滤后一道门禁都不剩", file=sys.stderr)
                return EXIT_USAGE
        return two_halves(gates, registry.parent, root, python, args.timeout)
    only = [part.strip() for part in args.only.split(",") if part.strip()] if args.only else None
    if only is not None:
        known = {str(gate.get("id")) for gate in gates}
        unknown = [item for item in only if item not in known]
        if unknown:
            print(f"BLIND_GATES USAGE ERROR: registry 里没有这些门禁：{', '.join(unknown)}", file=sys.stderr)
            return EXIT_USAGE
    results = judge_all(gates, registry.parent, root, python, args.timeout, only=only)
    if not results:
        print("BLIND_GATES USAGE ERROR: 一道门禁都没判（--only 过滤后为空）", file=sys.stderr)
        return EXIT_USAGE

    counts = summarize(results)
    if not args.quiet:
        print(f"[blind-gates] 判据：scanned 0 + exit 0 + 无 SKIP 标记 ⇒ 判红（{len(results)} 道）")
        print(f"[blind-gates] registry {registry}")
        print(f"[blind-gates] root {root}；解释器 {python}")
        print_table(results)
    print_findings(results)

    record_path = Path(args.record) if args.record else None
    coverage: dict = {}
    if args.coverage_delta:
        # 顺序不可换：先把上一个提交的留痕读出来，再写本次 —— 否则本次会盖在历史之上，
        # 下一次跑批就把「上一个提交」比成「自己」了（同一提交无信息量，永远不可判定）。
        coverage, lag = coverage_report(results, root, record_path)
        if lag:
            print(f"  覆盖未跟进 {lag} 道：scanned 没变而本区间新增了文件 —— 是「没看」，不是「没问题」")
    if record_path is not None:
        record(results, counts, record_path, root)

    # registry 之外的判据：清单从 tools/gate/README.md §12 读（单点维护），不硬编码。
    external_entries, external_findings = check_registry_external_files(
        Path(__file__).resolve().parent, [str(gate.get("id")) for gate in gates], root
    )
    print()
    print(
        f"REGISTRY_EXTERNAL: {len(external_entries)} "
        f"({', '.join(entry['id'] for entry in external_entries) or '无'})"
        " — 清单见 tools/gate/README.md §12"
    )
    for finding in external_findings:
        print(f"  REGISTRY_EXTERNAL_FINDING: {finding}")

    print()
    print(
        "BLIND_GATES_SUMMARY "
        f"total={counts['total']} measured={counts['measured']} skipped={counts['skipped']} "
        f"blind={counts['blind']} undetermined={counts['undetermined']} failed={counts['failed']} "
        f"skipped_platform={counts['skipped_platform']} error={counts['error']}"
    )
    if counts["measured"]:
        print(f"  有量：{counts['measured']} 道读到 scanned > 0 —— 这些道真的扫了东西")
    if counts["skipped"]:
        print(f"  not a pass：{counts['skipped']} 道 scanned 0 但显式 SKIP（理由已在上表，可复核）")
    if counts["blind"]:
        print(f"  判红：{counts['blind']} 道扫了 0 个对象却报绿（见上方 BLIND 段）")
    if counts["undetermined"]:
        print(f"  不可判定：{counts['undetermined']} 道输出里没有 scanned 字段（见上方清单，不得当绿）")

    if args.json:
        payload: dict = {
            "summary": counts,
            # 一等结论，单列不折叠：消费方读这个键就不会把「不可判定」当成 0 道。
            "undetermined_gates": [item.as_dict() for item in results if item.verdict == UNDETERMINED],
            "registry_external": {
                "entries": external_entries,
                "findings": external_findings,
            },
            "gates": [item.as_dict() for item in results],
        }
        if coverage:
            payload["coverage"] = coverage
        print(json.dumps(payload, ensure_ascii=False))

    strict = exit_code_for(counts, args.allow_undetermined)
    # 清单核验不通过同样判红：例外的可见性是一条判据，不是一段文档。
    if external_findings and strict == EXIT_OK:
        return EXIT_BLOCKING
    return strict


if __name__ == "__main__":
    raise SystemExit(main())
