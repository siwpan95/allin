# -*- coding: utf-8 -*-
"""allin 全流程自动推进 —— 定时任务友好的单一入口。

## 这个脚本解决什么

allin 的治理流程散落在四个独立入口里，定时任务要「一条命令跑完全流程」时
必须自己拼装：

    同步核对  bash scripts/sync-before-push.sh          （只读：fetch + ahead/behind）
    门禁全跑  bash scripts/run_all_gates.sh             （20 道门禁 + 测试 + 自检）
    发版预检  python scripts/release_preflight.py       （静态：版本/产物对账）
    状态汇总  python allin_cli.py status --json --strict（三面只读）

本脚本把四步串成一个**可重入、退出码语义清晰、结果可机读**的单一命令，
供 `allin tools auto-flow` 与 WorkBuddy automation 调用。

## 纪律（来自 SPEC-001 铁律 3 / SPEC-002 §零 自主模式）

- **绝不 push、绝不建仓、绝不自提交、绝不改工作区源码**。
  本脚本只做检查与本地留痕 —— 推送/发版属高风险动作，必须人在场逐项放行。
- fetch 只更新远端跟踪引用（SPEC-002 §七：非实质改动），工作树脏时同步步骤
  只报告不处置；发现 DIVERGED 记为 finding（exit 1），不自动 rebase/merge。
- SKIP ≠ pass：门禁原样透传其退出码（0 clean / 1 failed / 2 incomplete）。
- 每一步均有结构化留痕（tools/gate/audit/auto-flow-runs.jsonl，已被 .gitignore
  覆盖）， machine-readable 汇总行 `ALLIN_AUTO_FLOW_SUMMARY` 供自动化判定。

## 用法

    python tools/auto_flow.py                 # 全流程（同步 + 门禁 + 预检 + 状态）
    python tools/auto_flow.py --quick         # 快跑：同步 + 状态（离线/高频巡检）
    python tools/auto_flow.py --with-platform # 追加 platform check/test/harness
    python tools/auto_flow.py --no-fetch      # 跳过 fetch（离线环境）
    python tools/auto_flow.py --json          # 机读输出
    python tools/auto_flow.py --selfcheck     # 判据自身回归（不跑外部命令）

退出码与治理门禁同一词汇：0 干净 / 1 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "tools" / "gate" / "audit" / "auto-flow-runs.jsonl"
BASH = "bash"  # 走 PATH，不写死机器路径（g01）


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _append_run(record: dict) -> None:
    """留痕失败不得拖垮主流程 —— 与 run_all_gates.sh 的 log_run 同口径。"""
    try:
        RUNS.parent.mkdir(parents=True, exist_ok=True)
        if RUNS.exists() and RUNS.stat().st_size > 5 * 1024 * 1024:
            RUNS.replace(RUNS.with_suffix(".jsonl.1"))
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _run(label: str, argv: list[str], *, env: dict[str, str] | None = None,
         release_preflight: bool = False) -> dict:
    """同步跑一步，捕获输出并返回结构化结果。输出同时回显，便于定时任务日志阅读。

    `release_preflight=True` 时把 preflight 的 INCOMPLETE 归为 not_applicable：
      静态预检的 5 项（版本单一来源 / dist 干净 / 产物齐备 / sdist 自包含 /
      package-dir 已物化）是真跑真判；仅 twine check 与 --install 安装实测在
      无人值守场景不适用（后者要建 venv 装包，属发版动作）。
      这与 run_all_gates.sh 的 not_applicable 同口径：单列、不冒充通过、不判红。
      真失败（exit 1）与环境错（无 INCOMPLETE 标记的 exit 3）仍判 finding。
    """
    print(f"==> [{label}] {' '.join(argv)}", flush=True)
    t0 = time.monotonic()
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=merged,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        rc = proc.returncode
    except FileNotFoundError as exc:
        out = f"ENV ERROR: {exc}"
        rc = EXIT_ENV
    ms = int((time.monotonic() - t0) * 1000)
    # 完整输出回显（定时任务日志是唯一排障现场），但机读 JSON 只留尾部摘要。
    if out.strip():
        print(out.rstrip(), flush=True)
    tail = out.strip().splitlines()[-8:]
    if rc == EXIT_OK:
        status = "ok"
    elif (release_preflight and rc == EXIT_ENV
          and "RESULT: INCOMPLETE" in out and "[FAIL]" not in out):
        status = "not_applicable"
    else:
        status = "finding"
    extra = ""
    if rc == EXIT_USAGE:
        extra = "（exit 2：可能是门禁的 incomplete/SKIP，SKIP ≠ pass）"
    print(f"    [{status}] {label} exit={rc} {ms}ms{extra}", flush=True)
    return {
        "label": label, "argv": argv, "exit": rc, "ms": ms,
        "status": status, "tail": tail,
    }


def _sync_step(no_fetch: bool) -> dict | None:
    """同步核对。--no-fetch 时整步跳过并显式标注（skip ≠ pass）。"""
    script = ROOT / "scripts" / "sync-before-push.sh"
    if not script.is_file():
        return {
            "label": "sync", "argv": [], "exit": EXIT_ENV, "ms": 0,
            "status": "error", "tail": [f"ENV ERROR: 缺少 {script}"],
        }
    if no_fetch:
        print("    [SKIP] sync（--no-fetch）：未核对远端，不声称已同步", flush=True)
        return None
    return _run(
        "sync",
        [BASH, "scripts/sync-before-push.sh"],
        env={"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"},
    )


def _gate_step(with_platform: bool) -> dict:
    script = ROOT / "scripts" / "run_all_gates.sh"
    if not script.is_file():
        return {
            "label": "gates", "argv": [], "exit": EXIT_ENV, "ms": 0,
            "status": "error", "tail": [f"ENV ERROR: 缺少 {script}"],
        }
    argv = [BASH, "scripts/run_all_gates.sh"]
    if with_platform:
        argv.append("--with-platform")
    return _run("gates", argv)


def _selfcheck() -> int:
    """判据自身回归：验证汇总口径不会把 finding/SKIP 洗成 ok。"""
    cases = [
        ("全绿", [], EXIT_OK),
        ("单步 finding", [{"label": "x", "exit": 1, "status": "finding"}], EXIT_BLOCKING),
        ("门禁 incomplete", [{"label": "gates", "exit": 2, "status": "finding"}], EXIT_BLOCKING),
        ("环境错", [{"label": "x", "exit": 3, "status": "error"}], EXIT_BLOCKING),
        ("skip 不算绿", [{"label": "x", "exit": 0, "status": "error"}], EXIT_BLOCKING),
        ("场景不适用不判红", [{"label": "preflight", "exit": 3, "status": "not_applicable"}], EXIT_OK),
        ("多步一红", [
            {"label": "a", "exit": 0, "status": "ok"},
            {"label": "b", "exit": 1, "status": "finding"},
        ], EXIT_BLOCKING),
    ]
    failed = 0
    for name, steps, want in cases:
        got = _verdict(steps)
        ok = got == want
        print(f"[{'ok' if ok else 'FAIL'}] {name}: verdict={got} want={want}")
        failed += 0 if ok else 1
    print(f"SELFCHECK ok={len(cases) - failed} fail={failed}")
    return EXIT_OK if failed == 0 else EXIT_BLOCKING


def _verdict(steps: list[dict]) -> int:
    """汇总口径：finding/error 判红；not_applicable 单列不冒充通过、也不判红。

    与 run_all_gates.sh 的三态一致（clean / incomplete / not_applicable）：
    环境或场景不适用 ≠ 已验证通过，但也不该把无人值守可以合法跳过的项
    （发版专属的 twine/--install）当成故障让定时任务常红。
    """
    blocking = ("finding", "error")
    if any(s.get("status") in blocking or
           (s.get("status") == "ok" and s.get("exit") != EXIT_OK)
           for s in steps):
        return EXIT_BLOCKING
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="auto-flow", description="allin 全流程自动推进（定时任务友好，绝不 push）"
    )
    parser.add_argument("--quick", action="store_true", help="快跑：只做同步核对 + 状态汇总")
    parser.add_argument("--with-platform", action="store_true", help="门禁额外跑 platform check/test/harness")
    parser.add_argument("--no-fetch", action="store_true", help="跳过 git fetch（离线）")
    parser.add_argument("--json", action="store_true", help="机读输出")
    parser.add_argument("--selfcheck", action="store_true", help="判据自身回归")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return _selfcheck()

    steps: list[dict] = []
    print(f"allin 全流程自动推进 @ {ROOT}", flush=True)
    print("----------------------------------------", flush=True)

    sync = _sync_step(args.no_fetch)
    if sync is not None:
        steps.append(sync)

    if not args.quick:
        steps.append(_gate_step(args.with_platform))
        preflight = ROOT / "scripts" / "release_preflight.py"
        if preflight.is_file():
            steps.append(_run(
                "preflight", [sys.executable, "scripts/release_preflight.py"],
                release_preflight=True,
            ))
        else:
            steps.append({
                "label": "preflight", "argv": [], "exit": EXIT_ENV, "ms": 0,
                "status": "error", "tail": [f"ENV ERROR: 缺少 {preflight}"],
            })

    status_cli = ROOT / "allin_cli.py"
    if status_cli.is_file():
        steps.append(_run(
            "status",
            [sys.executable, "allin_cli.py", "status", "--json", "--strict"],
        ))
    else:
        steps.append({
            "label": "status", "argv": [], "exit": EXIT_ENV, "ms": 0,
            "status": "error", "tail": [f"ENV ERROR: 缺少 {status_cli}"],
        })

    verdict = _verdict(steps)
    head = _head()
    print("----------------------------------------", flush=True)
    if args.json:
        print(json.dumps({
            "head": head, "verdict": "finding" if verdict else "clean",
            "not_applicable": na_n,
            "steps": [{k: v for k, v in s.items() if k != "argv"} for s in steps],
        }, ensure_ascii=False), flush=True)
    na_n = sum(1 for s in steps if s["status"] == "not_applicable")
    print(
        f"ALLIN_AUTO_FLOW_SUMMARY status={'finding' if verdict else 'clean'} "
        f"steps={len(steps)} fail={sum(1 for s in steps if s['status'] == 'finding')} "
        f"not_applicable={na_n} head={head}", flush=True,
    )
    if na_n:
        print(f"场景不适用 {na_n} 项（非已验证通过）：", flush=True)
        for s in steps:
            if s["status"] == "not_applicable":
                print(f"  - {s['label']}（发版专属检查，定时任务不执行）", flush=True)
    _append_run({
        "ts": _ts(), "head": head, "quick": args.quick,
        "verdict": "finding" if verdict else "clean",
        "not_applicable": na_n,
        "steps": [{k: v for k, v in s.items() if k != "argv"} for s in steps],
    })
    if verdict:
        print("全流程存在 finding：逐条见上；推送/发版仍需人在场放行。", flush=True)
    return verdict


if __name__ == "__main__":
    sys.exit(main())
