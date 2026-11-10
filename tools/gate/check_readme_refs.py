#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""现行文档「可机检事实」护栏门禁（2026-11-04 工程审查 Docu Top3-2 落地件；
2026-11-10 深度审计 H-5 / P1 #10 扩面：R2 从「仓根 README 集合包含」升级为
「多文档集合相等 + 门面必须含真值」）。

背景：文档索引契约（docs_index.py D1–D14）只覆盖 docs/ 内部，而**仓根 README 是
引用最密集、漂移代价最高却零门禁覆盖的文件**——2026-11-04 审查实测它同时存在
命名反向漂移（alloy/allin_engine）、已删仓残留表述、失效路径、包版本落后一代，
全部能静默存活。2026-11-10 深度审计 H-5 进一步实测：旧 R2 只读仓根 README、
只匹配 `0.0.0aN` 占位 alpha 序列，版本号一旦换格式就 `mentioned` 空集 →
整个 R2 静默失效；且 SPEC-204 / SVG / wiki 的旧版本号（0.0.0a2 / 0.0.0a1）
在判定面外长期存活。本门禁把其中可机检的两类变成提交即红：

  R1 路径存在性：仓根 README 中所有指向仓内文件的引用（markdown 链接 + 反引号路径，
     限 docs/ architecture/ preset/ scripts/ tools/ kernel/ platform/ packages/
     website/ 开头的相对路径）必须真实存在。判据沿用 2026-11-04 实测定标，未改动。
  R2 版本对账（扩面后）：
     · 判定面 = SCAN_GLOBS 显式白名单（现行事实声明类文档）。
     · 「集合相等」口径：以**每份文档为单位**，`mentioned ⊆ {pkg_version}` ——
       任何旧版本号都判红；没有任何版本号的文档视为干净（不报「缺版本号」，
       否则会大面积误伤）。
     · 仓根 README 额外保留「必须包含真值」要求（门面不得落后一代）。
     · 两条判据都写进输出（干净态摘要 + 违例明细）。

为什么排除 CHANGELOG.md / docs/记录/** 等历史留档：它们是**历史事实**，改它们
等于篡改历史（本仓铁律「只增不改史实」）。现行口径的订正只落在 SCAN_GLOBS 白名单；
历史件里的旧版本号是当时的事实，保持原样。audit-fragments/** 是整改证据输出、
packages/allin-governance/build/** 是打包产物、.venv/** 是第三方环境，同样不在判定面。

版本号正则的「避免误伤」取舍（重要）：
  只匹配 `0.0.0aN` 占位 alpha 系列与 PEP440 预发布形态
  （`x.y.z` + `a|b|rc|dev|post` + 数字，如 `0.1.0b2` / `1.0.0rc1` / `1.2.3dev1`），
  **刻意不匹配**纯三段稳定版 `1.2.3`。实测本仓 docs/规范/SPEC-*.md 里三段点分数字
  几乎全是第三方版本 / IP / 章节号 / 端口 / 日期：Python `3.14.7`、openpyxl `3.1.5`、
  tag `v1.2.0`、Dolt `2.7.2`、IP `127.0.0.1`、`§2.1.1`、DSH 分发版 `0.1.7-rc.1`、
  `versions/22.22.2-3`、`2026-11-10`。纯三段无法与 allin-governance 版本区分，
  匹配即全域误报；带 `-` 连字符的 semver 预发布亦不在判定面（避免误伤 SPEC-104 /
  SPEC-901 里的 DSH 版本号）。真值 `0.0.0a5` 及可预见的演进都是 PEP440 预发布形态，
  已被完整覆盖 —— 这正是「放宽到换格式也不会静默失效」与「零误伤」的平衡点。

用法：python tools/gate/check_readme_refs.py [--quiet] [--selfcheck]
退出码：0 干净；1 有违例（明细列出）；3 环境错。
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # tools/gate/ → 仓根
README = ROOT / "README.md"
PYPROJECT = ROOT / "packages" / "allin-governance" / "pyproject.toml"

# R2 判定面：只核「现行事实声明」类文档（显式白名单 glob，不隐式 glob 全仓）。
# 刻意排除 CHANGELOG.md、docs/记录/**、audit-fragments/**、docs/事实源/**、
# packages/allin-governance/build/**、.venv/** —— 历史留档 / 生成物 / 第三方环境，
# 里面的旧版本号是当时的事实，改它们等于篡改历史。新增现行声明类文档时在此显式登记。
SCAN_GLOBS = (
    "README.md",
    "packages/*/README.md",
    "docs/规范/SPEC-*.md",
    "wiki/*.md",
    "architecture/system-architecture.svg",
)
README_REL = "README.md"  # 仓根门面：额外要求「必须包含真值」

# 判定面：只核这些前缀的仓内相对路径（其余 http/#/绝对路径不归本门禁管）
CHECKED_PREFIXES = (
    "docs/", "architecture/", "preset/", "scripts/", "tools/",
    "kernel/", "platform/", "packages/", "website/",
)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")          # [x](path)
BACKTICK_PATH = re.compile(r"`((?:docs|architecture|preset|scripts|tools|kernel|platform|packages|website)/[^`]+?)`")

# 版本号形态：三段点分 + **必需的**预发布/开发段（PEP440 紧凑格式）。
# · 覆盖 0.0.0aN（本仓真值形态）、0.1.0b2、1.0.0rc1、1.2.3dev1。
# · 不覆盖纯 1.2.3 / 3.14.7 / v1.2.0 / 127.0.0.1 / 0.1.7-rc.1 —— 见模块 docstring
#   「避免误伤」段：这些在本仓文档里是第三方版本 / IP / 章节号 / 端口 / 日期，
#   不是 allin-governance 版本号。
# · 左边界 (?<![A-Za-z0-9_.]) 挡住 IP 后段与 `v1.2.0` 的 v；
#   右边界 (?![A-Za-z0-9_]) 允许后面跟句点 / 标点 / 中文。
VERSION = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"\d+\.\d+\.\d+"
    r"(?:a|b|rc|dev|post)\d+"
    r"(?![A-Za-z0-9_])"
)


def u8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def collect_paths(text: str) -> list:
    """收集 README 里指向仓内文件的引用（R1，判据未改动）。

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


def extract_versions(text: str) -> set[str]:
    """抽取一段文本里出现的 allin-governance 版本号集合（去重）。"""
    return {m.group(0) for m in VERSION.finditer(text)}


def read_pkg_version(pyproject_text: str) -> str | None:
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.M)
    return m.group(1) if m else None


def load_docs(root: Path) -> dict[str, str]:
    """按 SCAN_GLOBS 展开并读取判定面文档，返回 rel(相对仓根，posix) → 文本。"""
    docs: dict[str, str] = {}
    for pattern in SCAN_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            docs[rel] = path.read_text(encoding="utf-8")
    return docs


def version_problems(docs: dict[str, str], pkg_version: str) -> list[str]:
    """R2 纯判定：给定「文档 → 文本」与真值，返回违例明细（不碰文件系统）。

    两条判据都在这里，输出里也会分别体现：
      (1) 集合相等：每份文档 mentioned ⊆ {pkg_version}（任何旧版本号判红；
          空集视为干净，不报「缺版本号」）。
      (2) 门面必须含真值：README_REL 的 mentioned 必须包含 pkg_version。
    """
    problems: list[str] = []
    truth_set = {pkg_version}
    for rel, text in sorted(docs.items()):
        mentioned = extract_versions(text)
        stale = sorted(mentioned - truth_set)
        if stale:
            problems.append(
                f"R2 版本漂移：{rel} 提到旧版本 {stale}，"
                f"但 pyproject 实际 version = {pkg_version}"
                f"（判定口径 mentioned ⊆ {{{pkg_version}}}）"
            )
    # 门面不得落后一代：仓根 README 必须显式写出真值（判据 (2)）。
    readme_text = docs.get(README_REL)
    if readme_text is None:
        problems.append(f"R2 门面缺席：判定面内找不到 {README_REL}（无法执行「必须包含真值」判据）")
    elif pkg_version not in extract_versions(readme_text):
        mentioned = sorted(extract_versions(readme_text))
        problems.append(
            f"R2 门面落后：{README_REL} 未包含真值 {pkg_version}"
            f"（实际提到 {mentioned or '[]'}）"
        )
    return problems


def run_on(root: Path, quiet: bool = False) -> int:
    """对指定仓根执行 R1 + R2，返回退出码（0 干净 / 1 违例 / 3 环境错）。

    quiet 只抑制「干净态摘要」，违例明细始终打印（便于注入探针留证据）。
    """
    pyproject = root / "packages" / "allin-governance" / "pyproject.toml"
    readme = root / "README.md"
    # 环境校验：真值来源与门面必须可读，否则整条门禁不可信 → exit 3。
    if not pyproject.is_file():
        print(f"ENV-ERROR: 真值来源不存在 {pyproject}")
        return 3
    pkg_version = read_pkg_version(pyproject.read_text(encoding="utf-8"))
    if not pkg_version:
        print(f"ENV-ERROR: 无法从 {pyproject} 解析 version")
        return 3
    if not readme.is_file():
        print(f"ENV-ERROR: 仓根门面不存在 {readme}")
        return 3

    readme_text = readme.read_text(encoding="utf-8")
    problems: list[str] = []

    # --- R1 路径存在性（判据不变，只读仓根 README） ---
    seen: set[str] = set()
    for ref in collect_paths(readme_text):
        if ref in seen:
            continue
        seen.add(ref)
        if not (root / ref).exists():
            problems.append(f"R1 失效路径：{ref}")

    # --- R2 版本对账（扩面） ---
    docs = load_docs(root)
    if README_REL not in docs:
        print(f"ENV-ERROR: 白名单 SCAN_GLOBS 未命中 {README_REL}")
        return 3
    problems.extend(version_problems(docs, pkg_version))

    if problems:
        print(f"check_readme_refs：{len(problems)} 处违例")
        for p in problems:
            print(f"  - {p}")
        print("（判定面 = SCAN_GLOBS 白名单的现行声明类文档；"
              "CHANGELOG.md / docs/记录/** 等历史留档不在判定面，改它们等于篡改历史。"
              "历史性陈述请用删除线/「历史」标注，不要保留现行口气的失效引用）")
        return 1

    if not quiet:
        # 干净态摘要把两条判据的结论都写出来。
        per_doc = sum(1 for t in docs.values() if extract_versions(t) - {pkg_version})
        print(
            f"check_readme_refs：干净（R1 {len(seen)} 个仓内路径引用全部存在；"
            f"R2 判定面 {len(docs)} 份文档，集合相等口径 mentioned ⊆ {{{pkg_version}}} "
            f"违例文档 {per_doc} 份；门面 {README_REL} 必须包含真值 = "
            f"{pkg_version in extract_versions(readme_text)}）。"
        )
    return 0


def selfcheck() -> int:
    """注入探针回归（全程只在临时副本上操作，不碰真实文件、也不触发 R1 路径判据）。

    验证退出码契约：干净态 exit 0 → 塞入旧版本 0.0.0a2 必须 exit 1 →
    恢复真值后必须全绿 exit 0；并额外断言「噪声免疫」（IP / 日期 / 章节号 /
    端口 / 第三方版本 / DSH 分发版版本都不被当成 allin-governance 版本号）。
    """
    truth = "0.0.0a5"
    with tempfile.TemporaryDirectory(prefix="check_readme_refs_selfcheck_") as td:
        root = Path(td)
        (root / "packages" / "allin-governance").mkdir(parents=True)
        (root / "docs" / "规范").mkdir(parents=True)
        (root / "wiki").mkdir(parents=True)
        (root / "architecture").mkdir(parents=True)
        (root / "packages" / "allin-governance" / "pyproject.toml").write_text(
            f'[project]\nname = "allin-governance"\nversion = "{truth}"\n',
            encoding="utf-8",
        )
        (root / "packages" / "allin-governance" / "README.md").write_text(
            f"# allin-governance\n当前版本 `{truth}`。\n", encoding="utf-8"
        )
        (root / README_REL).write_text(
            f"# allin\n当前版本 `{truth}`。\n", encoding="utf-8"
        )
        (root / "wiki" / "Home.md").write_text(
            f"当前版本 `{truth}`。\n", encoding="utf-8"
        )
        (root / "docs" / "规范" / "SPEC-204-系统架构.md").write_text(
            f"现版本 {truth}。\n", encoding="utf-8"
        )
        svg = root / "architecture" / "system-architecture.svg"
        svg.write_text(
            f"<text>packages/allin-governance（PyPI，{truth}）</text>\n",
            encoding="utf-8",
        )

        print("== check_readme_refs --selfcheck（临时副本注入探针）==")
        clean_code = run_on(root, quiet=True)
        print(f"  [干净态]        exit {clean_code} | 期望 0 | "
              f"{'PASS' if clean_code == 0 else 'FAIL'}")

        # 注入旧版本 0.0.0a2（只改临时副本）
        svg.write_text(
            "<text>packages/allin-governance（PyPI，0.0.0a2）</text>\n",
            encoding="utf-8",
        )
        injected_code = run_on(root, quiet=True)
        print(f"  [注入 0.0.0a2]  exit {injected_code} | 期望 1 | "
              f"{'PASS' if injected_code == 1 else 'FAIL'}")

        # 恢复真值 → 必须全绿
        svg.write_text(
            f"<text>packages/allin-governance（PyPI，{truth}）</text>\n",
            encoding="utf-8",
        )
        restored_code = run_on(root, quiet=True)
        print(f"  [恢复干净态]     exit {restored_code} | 期望 0 | "
              f"{'PASS' if restored_code == 0 else 'FAIL'}")

    # 噪声免疫：文档里大量出现的三段点分数字都不该被抓成版本号。
    noise = (
        "Python 3.14.7、openpyxl 3.1.5、tag v1.2.0、Dolt 2.7.2、"
        "IP 127.0.0.1、日期 2026-11-10、章节 §2.1.1、端口 9000 / 9042、"
        "DSH 0.1.7-rc.1、versions/22.22.2-3、g00–g20、D1–D17"
    )
    noise_hits = extract_versions(noise)
    noise_clean = not noise_hits
    print(f"  [噪声免疫]       命中 {sorted(noise_hits) or '[]'} | 期望 [] | "
          f"{'PASS' if noise_clean else 'FAIL'}")

    ok = (clean_code == 0 and injected_code == 1
          and restored_code == 0 and noise_clean)
    if ok:
        print("SELFCHECK: PASS（干净 0 / 注入 1 / 恢复 0，且噪声零误伤）")
        return 0
    print("SELFCHECK: FAIL（护栏失效：注入未判红 / 干净态误伤 / 噪声误抓）")
    return 1


def main(argv: list[str] | None = None) -> int:
    u8()
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv
    if "--selfcheck" in argv:
        return selfcheck()
    return run_on(ROOT, quiet=quiet)


if __name__ == "__main__":
    sys.exit(main())
