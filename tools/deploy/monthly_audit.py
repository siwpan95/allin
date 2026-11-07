#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""monthly_audit.py -- 仓内月度治理盘点（ERP 调研 P2 的备用路线，2026-11-07）。

为什么是「仓内调度」而不是 WorkBuddy 定时自动化
------------------------------------------------
WorkBuddy 的定时自动化挂在某台机器的会话工作区上：换机即失效、配方随会话走，
不能随仓库 clone 复制。本脚本把配方压进仓内 `tools/deploy/`：

* 判据**全部复用仓内既有 CLI**，不另写一套（SPEC-003 §新建三查）；
* 调度由 Windows Task Scheduler 的 `ALLIN-monthly-audit` 任务承担，
  注册动作仍由人在各机执行（ADR-0010 部署守护面同款纪律）；
* 运行产物落 `tools/gate/audit/monthly-audit-runs.jsonl`（机器本地，已被
  `.gitignore` 的 `audit/*` 覆盖），与 `gate-runs.jsonl` / `g21-runs.jsonl` 同族。

于是「换机」= clone + 跑一次 `register-tasks.ps1`，无需重建任何会话侧自动化。

盘点项（纯 Python 面，不依赖 npm / bash / WorkBuddy）
------------------------------------------------------
1. `verify_facts` -- 本机机器事实源断言（复用 g20 判据，`--json` 机读）
2. `docs_index`   -- 文档枢纽契约 D1–D17
3. `repocheck`    -- 仓内自检口径（与 `scripts/run_all_gates.sh` 同一组参数）
4. `portfolio`    -- 组合分级对账「137 = 140 − 3」的**表内自洽**判据

组合分级为什么只硬判「表内自洽」
--------------------------------
`docs/事实源/组合分级决策索引.md` 自己写明「工作区 repos 根按机器而异」：
SIWPAN 本机 `../repos` 实测 138、8RSV60V 实测 137，差值来自各机检出情况，
不是台账错误。拿某台机器的目录数硬判 137 会制造跨机假红 —— 与
`verify_facts` 默认只判本机那份文件是同一个道理（g20 2026-10-30 已修）。

故：决策表编号连续 / 分层求和 / 合计 / 对账式算术 = **硬判据**（跨机一致）；
发布区实测 git 目录数 = **观测项**，如实记偏差但不阻断，
需要时可 `--strict-publish-area` 收紧为阻断。

月度幂等守卫
------------
触发器取「每周一」（PowerShell cmdlet 直接可得，免 XML / schtasks 月度触发器）；
「每月一次」由本脚本保证：JSONL 中最后一次 `status=ok` 的 `period` 与当前
`YYYY-MM` 相同即 skip。上一次 `failed` **不**阻断重跑（修完必须能复验），
`--force` 可强制重跑。skip 不写 JSONL，避免每周往留痕里塞噪音。

退出码：0 全绿 / skip，1 有阻断项，2 用法错，3 环境错。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

EXIT_OK, EXIT_FAILED, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

AUDIT_REL = Path("tools") / "gate" / "audit" / "monthly-audit-runs.jsonl"
PORTFOLIO_REL = Path("docs") / "事实源" / "组合分级决策索引.md"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 900

_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
_TIER = re.compile(
    r"^\|\s*\*{0,2}([①②③④][^|*]*)\*{0,2}\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|", re.M)
_TOTAL = re.compile(r"\|\s*\*\*合计\*\*\s*\|\s*\*\*(\d+)\*\*")
_EQUATION = re.compile(r"(\d+)\s*=\s*(\d+)\s*[\u2212\u2013-]\s*(\d+)")


def default_root() -> Path:
    """仓根自发现：`tools/deploy/monthly_audit.py` 上溯两级。零盘符字面量（g01）。"""
    return Path(__file__).resolve().parents[2]


def _tail(text: str, width: int = 180) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return (lines[-1] if lines else "(无输出)")[:width]


# ---------------------------------------------------------------- 组合分级判据
def parse_portfolio(text: str, publish_dirs: int | None = None,
                    strict_publish_area: bool = False) -> dict:
    """解析 FACT-08，判「表内自洽」；发布区目录数只作观测（可 strict 收紧）。

    抽成纯函数是为了 `--selfcheck` 能用临时夹具逐维注入破坏，不碰真实事实源。
    """
    issues: list[str] = []
    lines = text.splitlines()

    start = next((i for i, l in enumerate(lines)
                  if l.startswith("## ") and "全量决策表" in l), None)
    numbers: list[int] = []
    if start is None:
        issues.append("缺「## 全量决策表」节")
    else:
        for line in lines[start + 1:]:
            if line.startswith("## "):
                break
            m = _ROW.match(line)
            if m:
                numbers.append(int(m.group(1)))
    rows = len(numbers)
    contiguous = bool(numbers) and numbers == list(range(1, rows + 1))
    if not contiguous:
        issues.append("决策表编号不连续：%d 行（首 %s / 末 %s）"
                      % (rows, numbers[:1], numbers[-1:]))

    m_total = _TOTAL.search(text)
    declared_total = int(m_total.group(1)) if m_total else None
    if declared_total is None:
        issues.append("分级统计表缺「**合计**」行")

    tiers = [int(n) for _, n in _TIER.findall(text)]
    tier_sum = sum(tiers) if tiers else None
    if tier_sum is None:
        issues.append("分级统计表未解析到任何分层计数")

    m_eq = _EQUATION.search(text)
    left = mid = archived = None
    if m_eq:
        left, mid, archived = (int(x) for x in m_eq.groups())
    else:
        issues.append("头部时点块缺对账式「N = M − K」")

    if rows and declared_total is not None and rows != declared_total:
        issues.append("决策表行数 %d ≠ 统计表合计 %d" % (rows, declared_total))
    if tier_sum is not None and declared_total is not None and tier_sum != declared_total:
        issues.append("分层求和 %d ≠ 统计表合计 %d" % (tier_sum, declared_total))
    if mid is not None and declared_total is not None and mid != declared_total:
        issues.append("对账式右端 %d ≠ 统计表合计 %d" % (mid, declared_total))
    if None not in (left, mid, archived) and mid - archived != left:
        issues.append("对账式算术不自洽：%d − %d ≠ %d" % (mid, archived, left))

    expected = left
    deviations: list[dict] = []
    if publish_dirs is not None and expected is not None and publish_dirs != expected:
        deviations.append({
            "kind": "publish-area-count",
            "observed": publish_dirs,
            "expected": expected,
            "delta": publish_dirs - expected,
            "note": "各机检出情况不同，观测项默认不阻断",
        })
        if strict_publish_area:
            issues.append("发布区实测 %d 目录 ≠ 台账期望 %d（--strict-publish-area 已开启）"
                          % (publish_dirs, expected))

    return {
        "ok": not issues,
        "issues": issues,
        "hard": {
            "decisionRows": rows,
            "contiguous": contiguous,
            "tierSum": tier_sum,
            "declaredTotal": declared_total,
            "equation": "%s = %s − %s" % (left, mid, archived),
        },
        "observed": {"publishAreaGitDirs": publish_dirs, "expected": expected},
        "deviations": deviations,
    }


def count_publish_dirs(root: Path) -> int | None:
    """发布区一级子目录里含 `.git` 的数量；发布区缺席返回 None（不是 0）。

    候选次序与 `scripts/run_all_gates.sh` 的 `_run_repo_hygiene` 同款：
    `PROJECTS_ROOT` → 仓内 `repos/` → 仓根同级 `repos/`。
    """
    candidates: list[Path] = []
    env = os.environ.get("PROJECTS_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.extend([root / "repos", root.parent / "repos"])
    for cand in candidates:
        try:
            if cand.is_dir():
                return sum(1 for p in cand.iterdir()
                           if p.is_dir() and (p / ".git").exists())
        except OSError:
            continue
    return None


# ---------------------------------------------------------------- 幂等守卫 / 留痕
def last_ok_period(path: Path) -> str | None:
    """最后一次 `status=ok` 的 period；失败记录不参与守卫（修完要能复验）。"""
    if not path.is_file():
        return None
    found = None
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # 轮转残留 / 半行：跳过而不是让整份留痕失效
            if rec.get("status") == "ok" and isinstance(rec.get("period"), str):
                found = rec["period"]
    except OSError:
        return None
    return found


def write_record(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size > MAX_BYTES:
        os.replace(str(path), str(path) + ".1")  # 5MB 轮转，对齐 gate-runs.jsonl
    with open(str(path), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 子进程判据
def run_tool(name: str, argv: list[str], root: Path, summarize) -> dict:
    t0 = time.monotonic()
    stdout = combined = ""
    try:
        proc = subprocess.run(argv, cwd=str(root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        rc = proc.returncode
        stdout = proc.stdout or ""
        combined = stdout + (("\n[stderr] " + proc.stderr) if proc.stderr else "")
    except subprocess.TimeoutExpired:
        rc, combined = 3, "%s 超时（>%ds）" % (name, TIMEOUT_S)
    except OSError as exc:
        rc, combined = 3, "%s 启动失败：%s" % (name, exc)
    ms = int((time.monotonic() - t0) * 1000)
    ok, summary = summarize(rc, stdout, combined)
    return {"name": name, "exit": rc, "ok": ok, "ms": ms,
            "summary": summary, "cmd": " ".join(str(a) for a in argv[1:])}


def sum_verify(rc: int, out: str, combined: str) -> tuple[bool, str]:
    try:
        data = json.loads(out)
        n = len(data.get("findings", []))
        return rc == 0 and n == 0, (
            "findings=%d；freshness=%d 份；skipped=%d 份"
            % (n, len(data.get("freshness", {})), len(data.get("skipped", []))))
    except (json.JSONDecodeError, AttributeError):
        return False, "JSON 解析失败：" + _tail(combined)


def sum_generic(rc: int, out: str, combined: str) -> tuple[bool, str]:
    return rc == 0, ("exit=%d；%s" % (rc, _tail(combined or out)))


def head_sha(root: Path) -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(root),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
        return (proc.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- 主流程
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="monthly_audit", description="allin 月度治理盘点")
    ap.add_argument("--repo-root", help="仓根（默认按脚本位置上溯两级自发现）")
    ap.add_argument("--force", action="store_true", help="忽略月度幂等守卫，强制重跑")
    ap.add_argument("--selfcheck", action="store_true", help="夹具自测（不写真留痕、不跑真实判据）")
    ap.add_argument("--strict-publish-area", action="store_true",
                    help="把发布区目录数偏差升级为阻断（默认仅观测）")
    ap.add_argument("--json", action="store_true", help="把整份报告打到 stdout")
    args = ap.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    root = Path(args.repo_root).resolve() if args.repo_root else default_root()
    required = ("tools/facts/verify_facts.py", "tools/gate/docs_index.py",
                "tools/repocheck/main.py", str(PORTFOLIO_REL))
    missing = [rel for rel in required if not (root / rel).is_file()]
    if missing:
        print("ENV ERROR: 仓根缺判据文件 %s（--repo-root 是否指到仓库根？）" % ", ".join(missing),
              file=sys.stderr)
        return EXIT_ENV

    audit = root / AUDIT_REL
    period = datetime.now().strftime("%Y-%m")
    if not args.force and last_ok_period(audit) == period:
        print("SKIP：%s 已有一次 status=ok 的月度盘点（--force 可强制重跑；"
              "上次 failed 不阻断复验）" % period)
        return EXIT_OK

    py = sys.executable
    checks = [
        run_tool("verify_facts",
                 [py, "tools/facts/verify_facts.py", "--json"], root, sum_verify),
        run_tool("docs_index", [py, "tools/gate/docs_index.py"], root, sum_generic),
        run_tool("repocheck",
                 [py, "tools/repocheck/main.py", ".", "--exclude",
                  "tools,vendor,preset,packages,scripts,website",
                  "--skip-rules", "1,7", "--fail-on", "error", "--no-color"],
                 root, sum_generic),
    ]

    pf = parse_portfolio((root / PORTFOLIO_REL).read_text(encoding="utf-8"),
                         count_publish_dirs(root), args.strict_publish_area)
    checks.append({
        "name": "portfolio", "exit": 0 if pf["ok"] else 1, "ok": pf["ok"], "ms": 0,
        "cmd": "internal:" + str(PORTFOLIO_REL),
        "summary": ("表内自洽：%d 行 / 分层和 %s / 合计 %s / %s%s"
                    % (pf["hard"]["decisionRows"], pf["hard"]["tierSum"],
                       pf["hard"]["declaredTotal"], pf["hard"]["equation"],
                       ("；偏差：" + "；".join(pf["issues"])) if pf["issues"] else "")),
    })

    status = "ok" if all(c["ok"] for c in checks) else "failed"
    rec = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": period,
        "host": platform.node(),
        "repo": root.name,
        "commit": head_sha(root),
        "status": status,
        "forced": bool(args.force),
        "checks": checks,
        "portfolio": {"hard": pf["hard"], "observed": pf["observed"],
                      "deviations": pf["deviations"]},
    }
    write_record(audit, rec)

    print("== allin 月度治理盘点 %s @ %s (commit %s) ==" % (period, rec["host"], rec["commit"]))
    for c in checks:
        print("  [%s] %-13s %s (%dms)" % ("ok" if c["ok"] else "FAIL", c["name"],
                                          c["summary"], c["ms"]))
    obs = pf["observed"]
    if obs["publishAreaGitDirs"] is None:
        print("  发布区观测：缺席（无 PROJECTS_ROOT / 同级 repos/）—— 只判表内自洽")
    else:
        print("  发布区观测：%s 个 git 目录 / 台账期望 %s / 偏差 %+d（跨机观测项%s）"
              % (obs["publishAreaGitDirs"], obs["expected"],
                 obs["publishAreaGitDirs"] - (obs["expected"] or 0),
                 "，已按 --strict-publish-area 收紧" if args.strict_publish_area else "，不阻断"))
    print("  结果：%s ｜ 留痕：%s" % (status, AUDIT_REL.as_posix()))
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    return EXIT_OK if status == "ok" else EXIT_FAILED


# ---------------------------------------------------------------- 自检夹具
_FIXTURE = """# 夹具：组合分级决策索引（5 仓）

> **时点** 2026-11-01 复核（对账式 **4 = 5 − 1** 不变）

## 分级统计

| 决策层 | 仓数 |
|---|---|
| ① 核心推进 | 2 |
| ② 精选 | 1 |
| ③ 收敛 | 1 |
| ④ 止损 | 0 |
| **③b 容器** | **1** |
| **合计** | **5** |

## 全量决策表（5 仓）

| # | 仓库 | 决策层 |
|---|---|---|
| 1 | a | ①核心推进 |
| 2 | b | ①核心推进 |
| 3 | c | ②精选 |
| 4 | d | ③收敛 |
| 5 | e | ③b 容器 |
"""


def selfcheck() -> int:
    """逐维注入破坏：判据真被执行过，而不是被别的用例顺带拦下。"""
    print("== monthly_audit 自测（夹具，不写真实留痕）==")
    cases: list[tuple[str, bool]] = []

    def expect(label: str, got: bool) -> None:
        cases.append((label, got))
        print("  [%s] %s" % ("PASS" if got else "FAIL", label))

    base = parse_portfolio(_FIXTURE)
    expect("干净夹具判 ok", base["ok"] is True and base["hard"]["decisionRows"] == 5)
    expect("分层求和 / 合计 / 对账式解析正确",
           base["hard"]["tierSum"] == 5 and base["hard"]["declaredTotal"] == 5
           and base["hard"]["equation"] == "4 = 5 − 1")

    broken_row = parse_portfolio(_FIXTURE.replace("| 3 | c | ②精选 |\n", ""))
    expect("决策表断号被拦", broken_row["ok"] is False
           and any("编号不连续" in x for x in broken_row["issues"]))

    broken_total = parse_portfolio(_FIXTURE.replace("| **合计** | **5** |",
                                                    "| **合计** | **6** |"))
    expect("合计与决策表行数不符被拦", broken_total["ok"] is False
           and any("决策表行数" in x for x in broken_total["issues"]))

    broken_eq = parse_portfolio(_FIXTURE.replace("**4 = 5 − 1**", "**4 = 5 − 2**"))
    expect("对账式算术不自洽被拦", broken_eq["ok"] is False
           and any("算术不自洽" in x for x in broken_eq["issues"]))

    soft = parse_portfolio(_FIXTURE, publish_dirs=7)
    expect("发布区偏差默认只观测、不阻断",
           soft["ok"] is True and len(soft["deviations"]) == 1
           and soft["deviations"][0]["delta"] == 3)
    hard = parse_portfolio(_FIXTURE, publish_dirs=7, strict_publish_area=True)
    expect("--strict-publish-area 能把偏差升级为阻断", hard["ok"] is False)

    now = datetime.now().strftime("%Y-%m")
    with tempfile.TemporaryDirectory(prefix="monthly_audit_selfcheck_") as tmp:
        p = Path(tmp) / "runs.jsonl"
        expect("空留痕不触发 skip", last_ok_period(p) is None)
        p.write_text(json.dumps({"period": now, "status": "ok"}) + "\n", encoding="utf-8")
        expect("同月 ok 触发 skip", last_ok_period(p) == now)
        p.write_text(json.dumps({"period": now, "status": "failed"}) + "\n", encoding="utf-8")
        expect("同月 failed 不阻断复验", last_ok_period(p) is None)
        p.write_text(json.dumps({"period": "2000-01", "status": "ok"}) + "\n",
                     encoding="utf-8")
        expect("上月 ok 不误 skip 本月", last_ok_period(p) != now)
        p.write_text("{坏行\n" + json.dumps({"period": now, "status": "ok"}) + "\n",
                     encoding="utf-8")
        expect("坏行不污染整份留痕", last_ok_period(p) == now)

    passed = sum(1 for _, ok in cases if ok)
    print("  RESULT: %d/%d 通过" % (passed, len(cases)))
    return EXIT_OK if passed == len(cases) else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
