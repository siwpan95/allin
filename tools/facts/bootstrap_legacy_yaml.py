#!/usr/bin/env python3
"""一次性桥接：把三张遗留 MD 表转成 docs/事实源/{tiering,tools,licenses}.yaml 结构化权威源。

输入（人类可读孪生，原「唯一事实源」）：
  - docs/事实源/组合分级决策索引.md   （140 仓分级）
  - docs/事实源/工具分类索引.md       （34 工具）
  - docs/事实源/来源与许可表.md       （43 外部项目来源/许可）

输出（机器可读权威源，唯一被手改）：
  - docs/事实源/tiering.yaml
  - docs/事实源/tools.yaml
  - docs/事实源/licenses.yaml

纪律（与离线北极星 / 单源铁律一致）：
  * 本脚本是**一次性**桥接——转完后日常编辑只改 YAML；MD 降级为人类可读孪生（头部已标注）。
  * facts.json.{tiering,tools,licenses} 是 YAML 的派生索引投影（由 tools/facts/build_*.py 生成），
    删了重建即得，不破门禁。YAML 是唯一被手改的机器可读源；MD 与 YAML 同源维护（人手同步，约定如 ports）。
  * 不做 MD↔YAML 漂移门禁（与 ports 一致：靠约定同步）；g26 只校验 facts.json ⇄ YAML。

零第三方依赖（仅标准库；有 yaml 时顺带 dump，否则用内置稳定序列化）。
用法：python tools/facts/bootstrap_legacy_yaml.py [--out DIR] [--check]
  --check 不写文件，仅打印三表解析计数供人工核对。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "事实源"
EXIT_OK, EXIT_ENV = 0, 3


# ---------------------------------------------------------------- 通用表解析
def _cells(line: str) -> list[str]:
    """把 `| a | b | c |` 拆成 ['a','b','c']（去首尾空）。"""
    s = line.strip()
    if not s.startswith("|"):
        return []
    # 去掉首尾的 |
    if s.endswith("|"):
        s = s[1:-1]
    else:
        s = s[1:]
    return [c.strip() for c in s.split("|")]


def _strip_bq(v: str) -> str:
    """去反引号。"""
    return v.replace("`", "").strip()


def _dash(v: str) -> str | None:
    """`—` / `-` / 空 → None。"""
    v = v.strip()
    if v in ("", "-", "—", "–"):
        return None
    return v


# ---------------------------------------------------------------- tiering
TIERING_HEADER = "| # | 仓库 | 领域 | 决策层 | 动作 | 归档目标 | 备注 |"


def parse_tiering(text: str) -> list[dict]:
    rows: list[dict] = []
    lines = text.splitlines()
    in_table = False
    for ln in lines:
        if ln.strip().startswith("| #") and "仓库" in ln and "决策层" in ln:
            in_table = True
            continue
        if in_table:
            if not ln.strip().startswith("|"):
                break
            cells = _cells(ln)
            if len(cells) != 7:
                continue
            if cells[0].startswith("#") or not cells[0].isdigit():
                continue  # 表头/分隔行
            seq = int(cells[0])
            repo = _strip_bq(cells[1])
            domain = cells[2]
            tier = cells[3]
            action = cells[4]
            archive_target = _dash(cells[5]) or ""
            note = cells[6]
            rows.append({
                "repo": repo,
                "seq": seq,
                "domain": domain,
                "tier": tier,
                "action": action,
                "archive_target": archive_target,
                "note": note,
            })
    return rows


# ---------------------------------------------------------------- tools
SECTION_RE = re.compile(r"^##\s+[^（]*类（`([^`]+)`）")
TOOLS_HEADER_HINT = "| 工具 | 用途 | 登记 id | 远端仓 | 状态 |"
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def parse_tools(text: str) -> list[dict]:
    rows: list[dict] = []
    lines = text.splitlines()
    category = None
    in_table = False
    for ln in lines:
        m = SECTION_RE.match(ln.strip())
        if m:
            category = m.group(1)
            in_table = False
            continue
        if ln.strip().startswith("| 工具") and "登记 id" in ln:
            in_table = True
            continue
        if in_table:
            if not ln.strip().startswith("|"):
                in_table = False
                continue
            cells = _cells(ln)
            if len(cells) != 5:
                continue
            if cells[0] == "工具" or set(cells[0]) <= set("-"):
                continue  # 表头/分隔
            tool = _strip_bq(cells[0])
            purpose = cells[1]
            registry_id = _dash(_strip_bq(cells[2]))
            remote_cell = cells[3]
            status = _dash(cells[4])
            remote_url = None
            if remote_cell and "[" in remote_cell:
                lm = LINK_RE.search(remote_cell)
                if lm:
                    remote_url = lm.group(2)
            rows.append({
                "tool": tool,
                "category": category,
                "purpose": purpose,
                "registry_id": registry_id,
                "remote_url": remote_url,
                "status": status,
            })
    return rows


# ---------------------------------------------------------------- licenses
LICENSE_HINT = "| # | 目录 | 来源 | 许可证 | 状态 |"
SPDX_TOKENS = ["AGPL-3.0-or-later", "AGPL-3.0", "GPL-2.0", "GPL-3.0",
               "Apache-2.0", "AFL-3.0", "MIT"]


def _license_short(cell: str) -> str:
    c = cell
    if "混合" in c:
        # 形如「混合：...MIT 式；...GPL-3.0」
        spdx = [t for t in SPDX_TOKENS if t in c]
        return "混合(" + "+".join(spdx) + ")" if spdx else "混合"
    if "自定义" in c:
        return "自定义"
    if c.strip() in ("无", "无（"):
        return "无"
    if "缺 LICENSE" in c:
        # 声明了某许可但缺文件，仍以声明为准
        pass
    for t in SPDX_TOKENS:
        if t in c:
            return t
    if "无" in c:
        return "无"
    return c.strip(" *").strip()


def _has_license_file(cell: str) -> bool:
    if "非项目自身许可" in cell:
        return False
    if "缺 LICENSE" in cell:
        return False
    if "有 LICENSE" in cell:
        return True
    if "LICENSE" in cell:
        return True
    return False


def parse_licenses(text: str) -> list[dict]:
    rows: list[dict] = []
    lines = text.splitlines()
    in_table = False
    for ln in lines:
        if ln.strip().startswith("| #") and "目录" in ln and "许可证" in ln:
            in_table = True
            continue
        if in_table:
            if not ln.strip().startswith("|"):
                break
            cells = _cells(ln)
            if len(cells) != 5:
                continue
            if cells[0].startswith("#") or not cells[0].isdigit():
                continue
            seq = int(cells[0])
            raw_dir = cells[1]
            archived = raw_dir.startswith("~~")
            d = _strip_bq(raw_dir).strip("~").strip()
            source = cells[2]
            lic_cell = cells[3]
            status_cell = cells[4]
            lic = _license_short(lic_cell)
            has_l = _has_license_file(lic_cell)
            # 状态：去 ⚠️ / ** / 括号细则；归档行直接标已归档
            st = status_cell.replace("⚠️", "").replace("**", "").strip()
            st = re.sub(r"[（(].*?[）)]", "", st).strip()
            if archived:
                st = "已归档"
            rows.append({
                "dir": d,
                "seq": seq,
                "source": source,
                "license": lic,
                "license_detail": lic_cell.replace("**", "").strip(),
                "has_license_file": has_l,
                "status": st,
                "status_detail": status_cell.replace("**", "").strip(),
                "archived": archived,
            })
    return rows


# ---------------------------------------------------------------- 序列化
def dump_yaml(data: dict, path: Path) -> None:
    try:
        import yaml
        text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                              default_flow_style=False)
    except ImportError:
        # 无 yaml 时的稳定回退（不依赖第三方）
        text = _simple_dump(data)
    path.write_text(text, encoding="utf-8")


def _simple_dump(data: dict) -> str:
    out = []
    for key, rows in data.items():
        out.append(f"{key}:")
        for r in rows:
            out.append("  - " + "\n      ".join(
                f"{k}: {_q(v)}" for k, v in r.items()))
    return "\n".join(out) + "\n"


def _q(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if any(ch in s for ch in [":", "#", "[", "]", "{", "}", "'", '"']) or not s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MD 表 -> 结构化 YAML 权威源（一次性）")
    ap.add_argument("--out", type=Path, default=SRC)
    ap.add_argument("--check", action="store_true", help="仅核对计数，不写文件")
    a = ap.parse_args(argv)

    tiering_text = (SRC / "组合分级决策索引.md").read_text(encoding="utf-8")
    tools_text = (SRC / "工具分类索引.md").read_text(encoding="utf-8")
    lic_text = (SRC / "来源与许可表.md").read_text(encoding="utf-8")

    tiering = parse_tiering(tiering_text)
    tools = parse_tools(tools_text)
    licenses = parse_licenses(lic_text)

    print(f"解析计数：tiering={len(tiering)} tools={len(tools)} licenses={len(licenses)}")
    print(f"  tiering seq 范围：{tiering[0]['seq']}..{tiering[-1]['seq']}")
    print(f"  tools 类别：{sorted({t['category'] for t in tools})}")

    if a.check:
        return EXIT_OK

    a.out.mkdir(parents=True, exist_ok=True)
    dump_yaml({"tiering": tiering}, a.out / "tiering.yaml")
    dump_yaml({"tools": tools}, a.out / "tools.yaml")
    dump_yaml({"licenses": licenses}, a.out / "licenses.yaml")
    print(f"已写出：{a.out / 'tiering.yaml'} / tools.yaml / licenses.yaml")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
