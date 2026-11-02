#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent 行为回归 eval harness —— 改配置/提示词/工具面前后的「同一组输入」对照。

为什么要有它：门禁判的是**仓库**（路径、编码、文档契约），判不了**agent 的行为**
（它能不能定位到仓根、工具面还在不在、人格里写的门禁数与 registry 是否一致）。
这类漂移不会让任何一道门禁变红，却会让 agent 在真实任务里答错。

所以这里放一组**固定样例（黄金集）**：几个典型输入 → 期望结论，跑一遍几十毫秒。
大改动前先跑它，改完再跑一次，两次都绿才算没有行为漂移。

2026-11-02 升级为 eval harness（见 docs/记录/交接/2026-11.md §117.3 P1-①）：
  - **黄金集版本化**：case 列表不再内嵌代码，改到 `audit/agent_regression_golden.json`
    （与 runner 解耦 ⇒ 改 case 集是显式的数据变更、可追溯，不会在改代码时默默变动）。
  - **提交式基线 + 版本间 diff**：`audit/agent_regression_baseline.json` 是已知良好的
    通过状态（随仓提交）。每次运行与基线对比，若有 case 从 pass 翻成 FAIL ⇒ **判定为回归**，
    直接 exit 1 并打印「翻了哪几项」——「改 prompt 修好 1 个、悄悄弄坏 5 个」由此可被捕获。
  - 仅在显式 `--commit-baseline` 时才写回基线（人类在刻意改黄金集/修 case 之后用）；
    默认（含 run_all_gates.sh 调用）只对比不写回，保证 CI 不会被某次运行悄悄改基线。

判据来源：`docs/规范/SPEC-001-铁律.md`（铁律 2 复盘）与
`.workbuddy/skills/allin-governance-agent/SKILL.md`（本样例集即其 §2.1 的回归项）。

用法：
    python tools/gate/agent_regression.py                 # 对比基线（CI 默认）
    python tools/gate/agent_regression.py --verbose       # 附每条的实际输出尾部
    python tools/gate/agent_regression.py --commit-baseline   # 写回当前状态为新基线

退出码：0 全绿（含相对基线无回归）/ 1 有样例失败或相对基线回归 / 3 环境错误（解释器/黄金集不可用等）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "gate" / "audit"
GOLDEN = AUDIT / "agent_regression_golden.json"
BASELINE = AUDIT / "agent_regression_baseline.json"
PRESET = ROOT / "preset" / "allin" / "allin.patch.yml"
REGISTRY = ROOT / "tools" / "gate" / "governance" / "registry.json"
MCP = ROOT / "platform" / "apps" / "mcp" / "src" / "index.js"
NODE = "node"


def commit_of():
    """尽量拿到当前 HEAD 短哈希，写进基线便于追溯（拿不到就空串）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace", timeout=20,
        )
        return out.stdout.strip()[:8]
    except Exception:
        return ""


def run(cmd, cwd=None, timeout=180):
    """跑一条命令；返回 (退出码, 合并输出)。IO 一律显式编码，避免 GBK 吞字符。"""
    try:
        res = subprocess.run(
            cmd, cwd=str(cwd or ROOT), timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace",
        )
        return res.returncode, res.stdout or ""
    except FileNotFoundError:
        return 127, f"命令不存在：{cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"超时（{timeout}s）：{' '.join(cmd)}"


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# 测试逻辑：每个 case 返回 (是否通过, 说明)。下方 CASE_FUNCS 由黄金集按名索引。
# --------------------------------------------------------------------------- #

def case_repo_root():
    """样例 1 · 定位仓根：仓根必须自证（索引 + 定位脚本都在）。"""
    ok = (ROOT / "docs" / "INDEX.md").is_file() and (ROOT / "preset" / "allin" / "locate-root.ps1").is_file()
    return ok, "仓根自证：docs/INDEX.md + preset/allin/locate-root.ps1"


def case_gate_count_says_same():
    """样例 2 · 人格说的门禁数 == registry 实际门禁数（历史上漂移过：人格写 15、实际 19）。"""
    if not REGISTRY.is_file():
        return False, f"registry 不存在：{REGISTRY}"
    payload = json.loads(read_text(REGISTRY))
    actual = len(payload.get("gates", []))
    text = read_text(PRESET)
    m = re.search(r"共\s*(\d+)\s*道", text)
    if not m:
        return False, "preset 治理段里找不到「共 N 道」的自述"
    said = int(m.group(1))
    return said == actual, f"人格自述 {said} 道 vs registry 实际 {actual} 道"


def case_mcp_tool_surface():
    """样例 3 · 工具面：数量与关键工具名都在（删工具/改工具名会被这里抓住）。"""
    code, out = run([NODE, str(MCP), "--list-tools"])
    if code != 0:
        return False, f"--list-tools 退出码 {code}"
    try:
        tools = json.loads(out)
    except json.JSONDecodeError as exc:
        return False, f"--list-tools 返回的不是 JSON：{exc}"
    names = {t.get("name") for t in tools}
    need = {"memory.read", "memory.append", "memory.promotable", "gate.run", "gate.history"}
    missing = sorted(need - names)
    return not missing, f"工具 {len(tools)} 个；缺失关键工具：{missing or '无'}"


def case_mcp_selftest():
    """样例 4 · MCP 自检：协议、写工具未确认即拒绝、未知工具报错。"""
    code, out = run([NODE, str(MCP), "--selftest"], timeout=300)
    return code == 0 and "SELFTEST OK" in out, f"--selftest 退出码 {code}"


def case_carrier_parity():
    """样例 5 · 多载体一致：preset 治理段、SKILL.md 与 agent.cordis.yml 说的是同一套事实。"""
    gate = ROOT / "tools" / "gate" / "governance" / "gates" / "g16_skill_preset_parity.py"
    if not gate.is_file():
        return False, f"g16 门禁脚本不存在：{gate}"
    code, _ = run([sys.executable, str(gate), "--quiet"])
    return code == 0, f"g16 退出码 {code}"


def case_docs_hub():
    """样例 6 · 文档枢纽：登记与份数自述仍然对齐。"""
    code, _ = run([sys.executable, str(ROOT / "tools" / "gate" / "docs_index.py")])
    return code == 0, f"docs_index 退出码 {code}"


CASE_FUNCS = {
    "定位仓根": case_repo_root,
    "门禁数自述一致": case_gate_count_says_same,
    "MCP 工具面": case_mcp_tool_surface,
    "MCP 自检": case_mcp_selftest,
    "多载体一致": case_carrier_parity,
    "文档枢纽": case_docs_hub,
}


def load_golden():
    if not GOLDEN.is_file():
        # 黄金集是 harness 的契约，缺失即环境错误（不允许静默回退到内嵌列表）。
        raise SystemExit("3|黄金集缺失：%s" % GOLDEN)
    data = json.loads(read_text(GOLDEN))
    cases = data.get("cases", [])
    unknown = [c for c in cases if c not in CASE_FUNCS]
    if unknown:
        raise SystemExit("3|黄金集引用了未实现的 case：%s" % unknown)
    return data.get("version", 0), cases


def load_baseline():
    if not BASELINE.is_file():
        return None
    try:
        return json.loads(read_text(BASELINE))
    except json.JSONDecodeError:
        return None


def save_baseline(state: dict):
    BASELINE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="agent 行为回归 eval harness")
    parser.add_argument("--verbose", action="store_true", help="附每条的实际输出尾部")
    parser.add_argument("--commit-baseline", action="store_true",
                        help="把当前运行状态写回 baseline（刻意改黄金集/修 case 后用；CI 不传此参）")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        golden_version, case_names = load_golden()
    except SystemExit as exc:
        code, _, msg = str(exc).partition("|")
        print(msg or str(exc))
        return int(code or 3)

    baseline = load_baseline()
    current = {}
    failed = 0
    for label in case_names:
        try:
            ok, detail = CASE_FUNCS[label]()
        except Exception as exc:  # 样例自身炸了也要报红，不能静默跳过
            ok, detail = False, f"样例异常：{exc}"
        current[label] = ok
        if ok:
            print(f"ok   {label} —— {detail}")
        else:
            failed += 1
            print(f"FAIL {label} —— {detail}")
    print("----------------------------------------")
    print(f"agent 行为回归：{len(case_names) - failed}/{len(case_names)} 通过（黄金集 v{golden_version}）")

    # ── 基线对比 / 写回 ──
    if args.commit_baseline:
        state = {
            "version": golden_version,
            "commit": commit_of(),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(case_names),
            "passed": len(case_names) - failed,
            "pass_rate": round((len(case_names) - failed) / len(case_names), 4),
            "cases": current,
        }
        save_baseline(state)
        print(f"基线已写回：{state['passed']}/{state['total']} 通过（commit {state['commit'] or '?'}）")
        # 写回模式不做回归拦截（这是「建立基线」的动作本身）
        return 1 if failed else 0

    if baseline is None:
        print("⚠ 无基线文件，跳过回归对比（首次运行请加 --commit-baseline 建立基线）")
        return 1 if failed else 0

    # 版本间 diff：找出从 pass 翻成 FAIL 的 case（回归），以及 FAIL→pass 的改善项
    regressed, improved = [], []
    for label, ok in current.items():
        prev = baseline.get("cases", {}).get(label)
        if prev is True and ok is False:
            regressed.append(label)
        elif prev is False and ok is True:
            improved.append(label)

    base_rate = baseline.get("pass_rate")
    cur_rate = round((len(case_names) - failed) / len(case_names), 4)
    print(f"对比基线（commit {baseline.get('commit') or '?'} 通过率 {base_rate}）："
          f"当前 {cur_rate}")
    if improved:
        print("  改善项（FAIL→pass）：" + "、".join(improved))
    if regressed:
        print("⚠ 回归项（pass→FAIL）：" + "、".join(regressed))
        # 回归 = 相对已知良好状态退步，无论当前是否还有别的通过项，都判失败
        return 1
    if failed:
        # 当前有失败、但基线里这些 case 本就是 FAIL（已知降级态），不算回归，只提示
        print("  （当前失败项在基线中亦为 FAIL，非本次回归）")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
