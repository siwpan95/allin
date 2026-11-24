#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""随包工具对账 —— `allin-toolkit` 实际打包的工具 ↔ allin 台账登记，双向相等。

## 为什么要有这个

2026-11-24 用户定调：「只有打包发版 PyPI 的才是工具，剩下的都和工具无关」+
「我想要的其实是做进 allin 中，接入流程，将随包工具变成名副其实」。

当时的实测缺口（首次对账结果）：

| 工具 | 打包 | tools.yaml | registry |
| --- | --- | --- | --- |
| auto_clicker / print / renamer / subtitle / yasuo | ✓ | ✓ | — |
| **calculator** | ✓ | **无** | — |
| **captcha-demo** | ✓ | **无** | — |
| **fonts** | — | ✓（过期：纯资源库，不是工具） | — |

即：包里有而台账没有（漏登记）、台账有而包里没有（过期登记），两边都没人管 ⇒
「随包工具」只是个文件名，不是体系里的一员。

## 判据（双向相等，仅对「工具」）

- **工具** = `allin-toolkit` 的 `pyproject.toml` 里 `packages` 声明过的子包
  （`allin_toolkit.tools.<name>`）。目录里躺着但没打包的，**不算工具** ——
  用户口径：`fonts` / `haha` / `pomodmer` / `santi-teleprompter` 这些都不是。
- **台账** = `docs/事实源/tools.yaml` 里带 `pypi: allin-toolkit` 的条目，
  **减去** `status` 明确写「非工具」的。
- 差集任一方向非空 ⇒ finding（名字归一化：`_` 与 `-` 视为同一个）。

## 三态（与仓内其他门禁同款口径）

- `clean`   —— 双向相等，exit 0
- `finding` —— 有差集，exit 1，逐条给出「加进哪边 / 从哪边删」
- `skip`    —— 找不到 `dev-toolkit` 仓（干净检出 / CI），exit 0 并**明确标注 skip**。
  ⚠ **SKIP 不是通过**：末行汇总里会带上 `skipped=1`，别把绿当成验过。

零第三方依赖（标准库；TOML 用 `tomllib`，Python ≥ 3.11）。退出码：0/1/2/3。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:  # 包内形态
    from .exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK, EXIT_USAGE
except ImportError:  # 仓内直跑
    try:
        from exit_codes import EXIT_ENV, EXIT_FINDING, EXIT_OK, EXIT_USAGE
    except ImportError:
        EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

REPO_MARKERS = ("docs", "preset", "tools")
PKG_MARKER = "allin-toolkit"          # tools.yaml 里标记「随包分发」的字段值
NOT_A_TOOL = "非工具"                  # status 里出现这个词 ⇒ 不算工具


def norm(name: str) -> str:
    """`auto_clicker` / `auto-clicker` 视为同一个（包内用下划线，台账惯用连字符）。"""
    return name.replace("_", "-").lower()


def find_repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if all((parent / m).is_dir() for m in REPO_MARKERS):
            return parent
    return None


def find_toolkit_root(explicit: str | None) -> Path | None:
    """`dev-toolkit` 仓根：显式参数 → 环境变量 → 兄弟目录。"""
    import os

    for cand in (explicit, os.environ.get("TOOLKIT_ROOT")):
        if cand:
            p = Path(cand).expanduser()
            if (p / "pyproject.toml").is_file():
                return p.resolve()
    root = find_repo_root()
    if root:
        for cand in (root.parent / "dev-toolkit", root.parent.parent / "dev-toolkit"):
            if (cand / "pyproject.toml").is_file():
                return cand.resolve()
    return None


def packaged_tools(toolkit_root: Path) -> list[str]:
    """`allin-toolkit` 实际打包的工具名（pyproject packages 的 `tools.<x>` 层）。"""
    try:
        import tomllib  # Python ≥ 3.11
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"ENV ERROR: 需要 Python 3.11+ 的 tomllib（{exc}）") from exc
    doc = tomllib.loads((toolkit_root / "pyproject.toml").read_text(encoding="utf-8"))
    packages = doc.get("tool", {}).get("setuptools", {}).get("packages") or []
    names = set()
    for entry in packages:
        parts = entry.split(".")
        if len(parts) >= 3 and parts[0] == "allin_toolkit" and parts[1] == "tools":
            names.add(norm(parts[2]))
    return sorted(names)


def packaged_tools_from_wheel(wheel: Path) -> list[str]:
    """从**实际 wheel** 里取工具目录 —— 产物判据，不是声明判据。

    为什么必须提供这条路（2026-11-24 的真实事故）：0.3.0 的 pyproject 顶层删了四个非工具项，
    但**漏删子包**（`tools.calculator.calculator` / `tools.captcha_demo.model` 等 5 条），
    setuptools 照打不误 ⇒ 声明看着干净，wheel 里仍有 9 个目录。
    只读 pyproject 的对账会给出「通过」，而产物是脏的 —— 判据必须能读产物。
    """
    import zipfile

    prefix = "allin_toolkit/tools/"
    with zipfile.ZipFile(wheel) as zf:
        names = [n for n in zf.namelist() if n.startswith(prefix)]
    tops = {n[len(prefix):].split("/")[0] for n in names}
    return sorted(norm(top) for top in tops if top and top != "__init__.py")


def declared_tools(tools_yaml: Path) -> tuple[list[str], list[str]]:
    """tools.yaml 里带 `pypi: allin-toolkit` 的条目；返回 (工具, 被排除的非工具)。"""
    tools: list[str] = []
    excluded: list[str] = []
    if not tools_yaml.is_file():
        return tools, excluded
    text = tools_yaml.read_text(encoding="utf-8", errors="replace")
    for block in re.split(r"^- tool:", text, flags=re.M)[1:]:
        lines = block.splitlines()
        name = lines[0].strip()
        body = "\n".join(lines[1:])
        if PKG_MARKER not in body:
            continue
        # 判定口径（全哥 2026-11-24 两次纠正后固化）：工具 = 一类通用问题
        # + 稳定 I/O 契约 + **跑完产出产物**；只序列化人的动作的是脚本，不算工具。
        # 落地成 kind 字段（tool / script），不靠人读 purpose 猜。
        kind = re.search(r"^\s+kind:\s*(\S+)", body, re.M)
        status = re.search(r"^\s+status:\s*(.+)$", body, re.M)
        if (kind and kind.group(1) != "tool") or (status and NOT_A_TOOL in status.group(1)):
            excluded.append(norm(name))
            continue
        if not kind:
            # 有 pypi 标记却没 kind ⇒ 口径没落实，别默默算成工具
            excluded.append(f"{norm(name)}(缺kind)")
            continue
        tools.append(norm(name))
    return sorted(set(tools)), sorted(set(excluded))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="toolkit_audit",
        description="随包工具对账：allin-toolkit 实际打包的工具 ↔ tools.yaml 登记（双向相等）",
    )
    ap.add_argument("--root", help="allin 仓根（默认按脚本位置探测）")
    ap.add_argument("--toolkit-root", help="dev-toolkit 仓根（默认兄弟目录 / TOOLKIT_ROOT）")
    ap.add_argument("--wheel", help="allin-toolkit 的 wheel 路径（给了就读**产物**，否则读声明）")
    ap.add_argument("--json", action="store_true", help="机读输出")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve() if args.root else find_repo_root()
    if root is None or not (root / "docs").is_dir():
        print("ENV ERROR: 找不到 allin 仓根（需含 docs/）", file=sys.stderr)
        return EXIT_ENV

    if args.wheel:
        wheel = Path(args.wheel).expanduser().resolve()
        if not wheel.is_file():
            print(f"ENV ERROR: wheel 不存在: {wheel}", file=sys.stderr)
            return EXIT_ENV
        packaged = packaged_tools_from_wheel(wheel)
        source = f"wheel:{wheel.name}"
        toolkit = wheel.parent  # 仅为后续输出不炸
    else:
        toolkit = find_toolkit_root(args.toolkit_root)
    if not args.wheel and toolkit is None:
        msg = ("skip: 找不到 dev-toolkit 仓（含 pyproject.toml）——本判据不适用；"
               "用 --toolkit-root 或 TOOLKIT_ROOT 指定。SKIP 不是通过。")
        if args.json:
            print(json.dumps({"status": "skip", "reason": msg}, ensure_ascii=False))
        else:
            print(msg)
        return EXIT_OK

    if not args.wheel:
        packaged = packaged_tools(toolkit)
        source = f"pyproject 声明（{toolkit.name}）—— ⚠ 非产物；要判产物用 --wheel"
    declared, excluded = declared_tools(root / "docs" / "事实源" / "tools.yaml")

    only_packaged = sorted(set(packaged) - set(declared))
    only_declared = sorted(set(declared) - set(packaged))

    if args.json:
        print(json.dumps({
            "status": "clean" if not (only_packaged or only_declared) else "finding",
            "judged_from": source,
            "packaged": packaged,
            "declared": declared,
            "excluded_non_tool": excluded,
            "missing_in_tools_yaml": only_packaged,
            "stale_in_tools_yaml": only_declared,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"== 随包工具对账（{PKG_MARKER}）==")
        print(f"   判据源: {source}")
        print(f"   打包 {len(packaged)} 个: {', '.join(packaged)}")
        print(f"   台账 {len(declared)} 个: {', '.join(declared)}")
        if excluded:
            print(f"   已排除（status 标「非工具」）: {', '.join(excluded)}")
        if only_packaged:
            print(f"\n[FINDING] 包里有、台账没登记（{len(only_packaged)}）—— 补进 docs/事实源/tools.yaml，"
                  f"并加 `pypi: {PKG_MARKER}`：")
            for name in only_packaged:
                print(f"   + {name}")
        if only_declared:
            print(f"\n[FINDING] 台账有、包里没有（{len(only_declared)}）—— 标 status 非工具或删条目：")
            for name in only_declared:
                print(f"   - {name}")
        if not (only_packaged or only_declared):
            print("\nRESULT: 通过 —— 包里的就是台账里的，台账里的就是包里的。")

    return EXIT_OK if not (only_packaged or only_declared) else EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main())
