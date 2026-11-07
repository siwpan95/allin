#!/usr/bin/env python3
"""check_arch_assets.py —— 架构资产对账门禁（ADR-0009）。

背景：`architecture/`（两张 SVG + adr/）在文档契约判据（docs_index D1–D17 / g19）之外，
是本仓唯一免检的架构叙事资产。2026-11-04 体检实测其内 5 处漂移静默存活近一月
（ADR 索引缺 0006–0008、SVG 缺 packages/website 子系统、图内门禁数/D 范围/仓数
三处数字落后两代）。ADR-0007 只把**叙事正文**迁进了 SPEC-204，图源与 ADR 仍在
判据外 —— 本脚本把这两类资产的「声明 ↔ 事实」对账变成退出码（门禁写了不跑 = 没有门禁）。

六项对账（全部从真身推导，不抄声明）：
  A. adr/ 索引 ↔ adr/*.md 文件集合（双向差集 + 状态闭集 + 链接文件存在）
  B. SVG 门禁数 ↔ tools/gate/governance/gates/ 实际文件（数量 / 编号范围 / 缺号）
  C. SVG docs_index D 范围 ↔ SPEC-204 声明（SPEC-204 受 g19 管辖，作传递锚）
  D. SVG + SPEC-204 仓数 ↔ PORTFOLIO.md（Gitee API 脚本生成物，仓数离线代理）
  E. 两张 SVG 标题必须带「修订」日期（起草·修订双日期，让陈旧度可见）
  F. website 默认端口 ↔ docs/事实源/ports.yaml 登记（README 声称已登记，2026-11-04 实测在案）

纯标准库；退出码：0 = 全部对账通过，1 = 存在 blocking。
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # tools/gate/ -> tools/ -> 仓根

# UTF-8 输出（与仓内其他门禁同口径；Windows 控制台缺省 cp936 会吞中文）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_STATUS_CLOSED = {"proposed", "accepted", "superseded"}  # adr/README 声明的状态闭集
_EN = "\u2013"  # 图与规范用的 en dash（g00–g20 / D1–D17 同一字符，别想当然写成 '-'）


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class Report:
    def __init__(self) -> None:
        self.blocks: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"  [ok] {msg}")

    def block(self, msg: str) -> None:
        self.blocks.append(msg)
        print(f"  [FAIL] {msg}")


def check_adr_index(rep: Report) -> None:
    """A. adr/README.md 索引表 ↔ adr/*.md 文件集合。"""
    adr_dir = os.path.join(ROOT, "architecture", "adr")
    readme = os.path.join(adr_dir, "README.md")
    actual: dict[str, str] = {}  # id -> 文件名
    for name in os.listdir(adr_dir):
        m = re.fullmatch(r"(ADR-\d{4})-.+\.md", name)
        if m:
            actual[m.group(1)] = name
    indexed: dict[str, tuple[str, str]] = {}  # id -> (链接文件名, 状态)
    for line in _read("architecture/adr/README.md").splitlines():
        m = re.match(r"\|\s*(ADR-\d{4})\s*\|\s*\[.*?\]\((ADR-[^)]+\.md)\)\s*\|\s*(\w+)\s*\|", line)
        if m:
            indexed[m.group(1)] = (m.group(2), m.group(3))
    if not indexed:
        rep.block("adr/README.md 索引表解析出 0 行 —— 表格格式变了，本门禁按旧体例匹配")
        return
    missing = sorted(set(actual) - set(indexed))
    extra = sorted(set(indexed) - set(actual))
    if missing:
        rep.block(f"adr 索引缺登（文件在、索引没有）: {', '.join(missing)}")
    if extra:
        rep.block(f"adr 索引多登（索引有、文件不在）: {', '.join(extra)}")
    bad_status = [f"{aid}={st}" for aid, (_, st) in indexed.items() if st not in _STATUS_CLOSED]
    if bad_status:
        rep.block(f"adr 状态不在闭集 proposed/accepted/superseded: {', '.join(bad_status)}")
    bad_link = [aid for aid, (fn, _) in indexed.items() if actual.get(aid) != fn]
    if bad_link:
        rep.block(f"adr 索引链接文件名与盘上不符: {', '.join(bad_link)}")
    if not (missing or extra or bad_status or bad_link):
        rep.ok(f"adr 索引 ↔ 文件集合一致（{len(actual)} 条，状态闭集 + 链接名核对通过）")


def check_svg_gates(rep: Report) -> None:
    """B. SVG 门禁数 ↔ gates/ 目录实际文件。"""
    gates_dir = os.path.join(ROOT, "tools", "gate", "governance", "gates")
    ids = sorted(
        m.group(1)
        for name in os.listdir(gates_dir)
        if (m := re.fullmatch(r"(g\d{2})_.+\.py", name))
    )
    if not ids:
        rep.block("gates/ 目录解析出 0 个门禁文件 —— 目录结构变了，本门禁需同步修订")
        return
    lo, hi, count = ids[0], ids[-1], len(ids)
    expect_missing = [f"g{n:02d}" for n in range(int(lo[1:]), int(hi[1:]) + 1) if f"g{n:02d}" not in ids]
    svg = _read("architecture/system-architecture.svg")
    checks = [
        (f"{lo}{_EN}{hi}", f"门禁编号范围 {lo}{_EN}{hi}"),
        (f"{count} 道治理门禁", f"门禁总数 {count} 道"),
    ]
    if expect_missing:
        checks.append(("缺 " + "、".join(expect_missing), "缺号声明（" + "、".join(expect_missing) + "）"))
    for needle, label in checks:
        if needle in svg:
            rep.ok(f"system-architecture.svg {label} ↔ gates/ 目录一致")
        else:
            rep.block(f"system-architecture.svg 缺声明「{needle}」({label}) —— 图落后于 gates/ 真身")


def check_svg_drange(rep: Report) -> None:
    """C. SVG docs_index D 范围 ↔ SPEC-204 声明（SPEC-204 受 g19 管辖）。"""
    spec = _read(os.path.join("docs", "规范", "SPEC-204-系统架构.md"))
    m = re.search(r"docs_index\(D(\d+)" + _EN + r"D(\d+)\)", spec)
    if not m:
        rep.block("SPEC-204 缺 docs_index(D1–D17) 形状的声明 —— 锚没了，SVG 对账失去基准")
        return
    rng = f"D{m.group(1)}{_EN}D{m.group(2)}"
    svg = _read("architecture/system-architecture.svg")
    if rng in svg:
        rep.ok(f"system-architecture.svg D 范围 ↔ SPEC-204 一致（{rng}）")
    else:
        rep.block(f"system-architecture.svg 缺 D 范围「{rng}」—— 图落后于 SPEC-204")


def check_repo_count(rep: Report) -> None:
    """D. SVG + SPEC-204 仓数 ↔ PORTFOLIO.md（Gitee API 生成物）。"""
    port = _read("PORTFOLIO.md")
    m = re.search(r"共\s*(\d+)\s*个仓库", port)
    if not m:
        rep.block("PORTFOLIO.md 缺「共 N 个仓库」声明 —— 仓数对账失去基准（生成脚本输出格式变了？）")
        return
    n = m.group(1)
    svg = _read("architecture/system-architecture.svg")
    if f"{n} 仓" in svg and f"公开 {n}" in svg:
        rep.ok(f"system-architecture.svg 仓数 ↔ PORTFOLIO.md 一致（{n}）")
    else:
        rep.block(f"system-architecture.svg 仓数声明需含「{n} 仓」与「公开 {n}」—— 图落后于 PORTFOLIO.md")
    spec = _read(os.path.join("docs", "规范", "SPEC-204-系统架构.md"))
    if f"{n} 个 Gitee 仓" in spec:
        rep.ok(f"SPEC-204 仓数 ↔ PORTFOLIO.md 一致（{n}）")
    else:
        rep.block(f"SPEC-204 仓数声明需含「{n} 个 Gitee 仓」—— 规范落后于 PORTFOLIO.md")


def check_svg_revision_date(rep: Report) -> None:
    """E. 两张 SVG 标题必须带「修订」日期（陈旧度可见）。"""
    for rel in ("architecture/system-architecture.svg", "architecture/data-flow.svg"):
        head = _read(rel)[:2000]
        if re.search(r"\d{4}-\d{2}-\d{2}\s*修订", head):
            rep.ok(f"{os.path.basename(rel)} 标题带修订日期")
        else:
            rep.block(f"{os.path.basename(rel)} 标题缺「YYYY-MM-DD 修订」—— 图改动日期必须标注，让陈旧度可见")


def check_website_port(rep: Report) -> None:
    """F. website 默认端口 ↔ docs/事实源/ports.yaml 登记。"""
    cfg = _read(os.path.join("website", "src", "config.js"))
    m = re.search(r"process\.env\.PORT\s*\|\|\s*'(\d{4,5})'", cfg)
    if not m:
        rep.block("website/src/config.js 缺 `process.env.PORT || 'NNNN'` 形状的默认端口 —— 端口对账失去基准")
        return
    port = m.group(1)
    ports = _read(os.path.join("docs", "事实源", "ports.yaml"))
    block = re.search(rf"-\s*port:\s*{port}\n(.*?)(?=\n\s*-\s*port:|\Z)", ports, re.S)
    if not block:
        rep.block(f"ports.yaml 缺 {port} 端口登记 —— README 声称「已登记事实源/ports.yaml」与盘不符")
        return
    if re.search(r"allin-website|website|官网", block.group(1)):
        rep.ok(f"website 默认端口 {port} ↔ ports.yaml 登记一致（allin-website）")
    else:
        rep.block(f"ports.yaml 的 {port} 条目未见 allin-website/官网归属 —— 登记与用途对不上")


def main() -> int:
    print("== 架构资产对账（ADR-0009）==")
    rep = Report()
    check_adr_index(rep)
    check_svg_gates(rep)
    check_svg_drange(rep)
    check_repo_count(rep)
    check_svg_revision_date(rep)
    check_website_port(rep)
    if rep.blocks:
        print(f"RESULT: {len(rep.blocks)} 项对账失败")
        return 1
    print("RESULT: 架构资产对账全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
