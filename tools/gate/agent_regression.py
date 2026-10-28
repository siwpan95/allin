#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent 行为回归样例集 —— 改配置/提示词/工具面前后的「同一组输入」对照。

为什么要有它：门禁判的是**仓库**（路径、编码、文档契约），判不了**agent 的行为**
（它能不能定位到仓根、工具面还在不在、人格里写的门禁数与 registry 是否一致）。
这类漂移不会让任何一道门禁变红，却会让 agent 在真实任务里答错。

所以这里放一组**固定样例**：几个典型输入 → 期望结论，跑一遍几十毫秒。
大改动前先跑它，改完再跑一次，两次都绿才算没有行为漂移。

判据来源：`docs/规范/SPEC-001-铁律.md`（铁律 2 复盘）与
`.workbuddy/skills/allin-governance-agent/SKILL.md`（本样例集即其 §2.1 的回归项）。

用法：
    python tools/gate/agent_regression.py            # 跑全部样例
    python tools/gate/agent_regression.py --verbose  # 附每条的实际输出尾部

退出码：0 全绿 / 1 有样例失败 / 3 环境错误（解释器不可用等）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESET = ROOT / "preset" / "allin" / "allin.patch.yml"
REGISTRY = ROOT / "tools" / "gate" / "governance" / "registry.json"
MCP = ROOT / "platform" / "apps" / "mcp" / "src" / "index.js"
NODE = "node"


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
# 样例：每条返回 (是否通过, 说明)
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
    """样例 5 · 双载体一致：preset 治理段与 SKILL.md 说的是同一套事实。"""
    gate = ROOT / "tools" / "gate" / "governance" / "gates" / "g16_skill_preset_parity.py"
    if not gate.is_file():
        return False, f"g16 门禁脚本不存在：{gate}"
    code, _ = run([sys.executable, str(gate), "--quiet"])
    return code == 0, f"g16 退出码 {code}"


def case_docs_hub():
    """样例 6 · 文档枢纽：登记与份数自述仍然对齐。"""
    code, _ = run([sys.executable, str(ROOT / "tools" / "gate" / "docs_index.py")])
    return code == 0, f"docs_index 退出码 {code}"


CASES = [
    ("定位仓根", case_repo_root),
    ("门禁数自述一致", case_gate_count_says_same),
    ("MCP 工具面", case_mcp_tool_surface),
    ("MCP 自检", case_mcp_selftest),
    ("双载体一致", case_carrier_parity),
    ("文档枢纽", case_docs_hub),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="agent 行为回归样例集")
    parser.add_argument("--verbose", action="store_true", help="附每条的实际输出尾部")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    failed = 0
    for label, fn in CASES:
        try:
            ok, detail = fn()
        except Exception as exc:  # 样例自身炸了也要报红，不能静默跳过
            ok, detail = False, f"样例异常：{exc}"
        if ok:
            print(f"ok   {label} —— {detail}")
        else:
            failed += 1
            print(f"FAIL {label} —— {detail}")
    print("----------------------------------------")
    print(f"agent 行为回归：{len(CASES) - failed}/{len(CASES)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
