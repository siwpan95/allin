#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓根 README「可机检事实」护栏门禁（2026-11-04 工程审查 Docu Top3-2 的落地件）。

背景：文档索引契约（docs_index.py D1–D14）只覆盖 docs/ 内部，而**仓根 README 是
引用最密集、漂移代价最高却零门禁覆盖的文件**——2026-11-04 审查实测它同时存在
命名反向漂移（alloy/allin_engine）、已删仓残留表述、失效路径、包版本落后一代，
全部能静默存活。本门禁把其中可机检的两类变成提交即红：

  R1 路径存在性：README 中所有指向仓内文件的引用（markdown 链接 + 反引号路径，
     限 docs/ architecture/ preset/ scripts/ tools/ kernel/ platform/ packages/
     website/ 开头的相对路径）必须真实存在。历史性陈述（~~删除线~~、行内代码里的
     旧路径带「已删除/历史」标注的段落）不在判定面 —— 判定面 = 链接目标。
  R2 版本对账：README 提到的 allin-governance 版本号集合必须**包含**
     packages/allin-governance/pyproject.toml 的实际 version（防"门面落后一代"）。

用法：python tools/gate/check_readme_refs.py [--readme README.md] [--quiet]
退出码：0 干净；1 有违例（明细列出）；2 用法错；3 环境错。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # tools/gate/ → 仓根
README = ROOT / "README.md"
PYPROJECT = ROOT / "packages" / "allin-governance" / "pyproject.toml"

# 判定面：只核这些前缀的仓内相对路径（其余 http/#/绝对路径不归本门禁管）
CHECKED_PREFIXES = (
    "docs/", "architecture/", "preset/", "scripts/", "tools/",
    "kernel/", "platform/", "packages/", "website/",
)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")          # [x](path)
BACKTICK_PATH = re.compile(r"`((?:docs|architecture|preset|scripts|tools|kernel|platform|packages|website)/[^`]+?)`")
VERSION = re.compile(r"\b0\.0\.0a\d+\b")


def u8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def collect_paths(text: str) -> list:
    """收集 README 里指向仓内文件的引用。

    判定面刻意收窄（2026-11-04 实测定标）：
    - markdown 链接目标：最强信号，全部核；
    - 反引号路径：仅核「末段带扩展名」的文件形引用 —— 排除 `docs/platform/preset/tools`
      这类支柱简写、`kernel/services/*.py` 这类 glob、以及历史叙述里的旧目录（如
      三仓整合记账里的 `platform/docs/`，目录已按设计拆除）。
    """
    refs = []
    for m in MD_LINK.finditer(text):
        refs.append(m.group(1))
    for m in BACKTICK_PATH.finditer(text):
        cand = m.group(1)
        last = cand.rstrip("/").rsplit("/", 1)[-1]
        if "*" in cand or "." not in last:
            continue
        refs.append(cand)
    out = []
    for ref in refs:
        path = ref.split("#", 1)[0].strip()  # 去锚点
        if not path or path.startswith(("http://", "https://", "mailto:", "/")):
            continue
        if not path.startswith(CHECKED_PREFIXES):
            continue
        out.append(path)
    return out


def main() -> int:
    u8()
    problems = []
    text = README.read_text(encoding="utf-8")

    # --- R1 路径存在性 ---
    seen = set()
    for ref in collect_paths(text):
        if ref in seen:
            continue
        seen.add(ref)
        if not (ROOT / ref).exists():
            problems.append(f"R1 失效路径：{ref}")

    # --- R2 版本对账 ---
    m = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.M)
    if not m:
        print(f"ENV-ERROR: 无法从 {PYPROJECT} 解析 version")
        return 3
    pkg_version = m.group(1)
    mentioned = set(VERSION.findall(text))
    if mentioned and pkg_version not in mentioned:
        problems.append(
            f"R2 版本漂移：README 提到 {sorted(mentioned)}，"
            f"但 pyproject 实际 version = {pkg_version}（门面落后于事实源）"
        )

    if problems:
        print(f"check_readme_refs：{len(problems)} 处违例")
        for p in problems:
            print(f"  - {p}")
        print("（仓根 README 不在 docs_index 判据内，本门禁是其唯一机检护栏；"
              "历史性陈述请用删除线/「历史」标注并改写，不要保留现行口气的失效引用）")
        return 1
    print(f"check_readme_refs：README 可机检事实干净（{len(seen)} 个仓内路径引用 + 版本 {pkg_version} 对账一致）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
