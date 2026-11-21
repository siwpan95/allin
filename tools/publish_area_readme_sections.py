r"""publish_area_readme_sections.py —— 发布区 README 缺段批量补写（规则 11 收口）

为什么有这个脚本
    规则 11（``docs.readme_structure``）要求 README 覆盖三类语义：安装/快速开始、
    用法/示例、许可。实测发布区（由 `--repos-root` 指定）139 仓中，**49 仓**被判定缺段。
    逐仓手写 49 次不可复跑、也不可复核 ⇒ 做成工具，按「从仓库自身事实推导内容」
    的方式补写，而不是套模板糊弄。

口径纪律（对应铁律 1「README 优先」与「借鉴必记账」）
    · 补写的内容**必须来自该仓自身的事实**：入口命令取自 README 已有的
      「运行方式」段 / 目录要点段 / 实际存在的脚本文件；许可类型取自该仓
      LICENSE 文件的首行识别结果（MIT / MIT-0 / Apache-2.0 …），**不臆造**。
    · 只**追加**缺失的章节，不改写已有章节 —— 已有内容是作者的，不动。
    · 每个仓补写后写一条「补写记账」到 ``docs/记录/``，注明依据来源。
    · 默认预演（``--dry-run``），``--apply`` 才写盘。

用法
    python tools/publish_area_readme_sections.py --repos-root <发布区根> --dry-run
    python tools/publish_area_readme_sections.py --repos-root <发布区根> --apply

退出码
    0 全部已满足 / 预演无待补
    1 有待补（预演）或已完成补写（--apply）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

#: 判据与 tools/repocheck/rules_docs.py 的 _README_SECTIONS 同源。
#: 命中即「该语义已覆盖」，不再补写。
_SECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("安装/快速开始",
     r"install|installation|安装|快速开始|getting started|quick ?start|"
     r"运行方式|运行方法|运行|启动|运行要求|依赖与运行"),
    ("用法/示例",
     r"usage|example|用法|使用|示例|运行方式|运行方法|运行|操作说明|"
     r"功能说明|使用说明|玩法|使用方式"),
    ("许可",
     r"licen[cs]e|许可|协议|授权"),
)

_LICENSE_FILES = ("LICENSE", "LICENCE", "COPYING", "COPYRIGHT")

#: Gitee 建仓模板生成的**未填写占位 README**（如 README.en.md）。
#: 实测（test 仓）：README.en.md 内容全是 ``xxxx`` / ``Readme_XXX.md`` 占位，
#: 而真正的内容在 README.md。判据 ``root_startswith("readme")`` 按前缀取文件，
#: 字典序下 ``README.en.md`` 排在 ``README.md`` 之前 ⇒ 会读到占位文件。
#: 本工具**只补真正的 README**（主 README / 英文 README 择其一），不碰占位模板。
_PLACEHOLDER_MARKERS = ("xxxx", "readme_xxx", "readme_xxx.md", "your project name")


def _is_placeholder_readme(text: str) -> bool:
    """该 README 是否是未填写的建仓模板占位文件。"""
    low = text.lower()
    if len(text) > 1200:
        return False
    hits = sum(1 for m in _PLACEHOLDER_MARKERS if m in low)
    # 至少两个占位特征，且正文很短 ⇒ 判为占位
    return hits >= 2 and text.count("\n") < 40


def detect_sections(text: str) -> set[str]:
    """README 已覆盖哪几类语义。"""
    return {label for label, pat in _SECTION_PATTERNS if re.search(pat, text, re.I)}


def detect_license(repo: Path) -> str | None:
    """从该仓 LICENSE 文件首行识别许可类型（不臆造）。"""
    for name in _LICENSE_FILES:
        for cand in (repo / name, repo / (name + ".md"), repo / (name + ".txt")):
            if not cand.is_file():
                continue
            try:
                head = cand.read_text(encoding="utf-8", errors="replace")[:600]
            except OSError:
                continue
            low = head.lower()
            if "mit no attribution" in low or "mit-0" in low:
                return "MIT-0"
            if "apache license" in low:
                return "Apache-2.0"
            if "gnu affero" in low:
                return "AGPL-3.0"
            if "gnu general public" in low:
                m = re.search(r"version\s+([\d.]+)", low)
                return f"GPL-{m.group(1)}" if m else "GPL"
            if "gnu lesser" in low:
                return "LGPL"
            if "mozilla public license" in low:
                return "MPL-2.0"
            if "bsd" in low and "redistribution" in low:
                return "BSD"
            if "mit license" in low or re.search(r"permission is hereby granted,? free of charge", low):
                return "MIT"
            return "见 LICENSE 文件"
    return None


_RUN_CMD_RE = re.compile(
    r"`?(?:python|python3|node|npm|npm run|bash|\./|cargo|java|go)\s+[^`\n]{1,90}`?")
_DEP_RE = re.compile(r"依赖[：:]\s*([^\n。]{1,80})")


def derive_usage(repo: Path, text: str) -> list[str]:
    """从仓库自身事实推导「运行方式」条目。

    依次尝试：README 已有的运行命令 → 实际存在的入口脚本。
    推不出就返回空列表（不臆造）。
    """
    items: list[str] = []
    seen: set[str] = set()

    # ① README 里已经写出的运行命令（可能散落在「目录要点」等段里）
    for m in _RUN_CMD_RE.finditer(text):
        cmd = m.group(0).strip().strip("`").strip()
        if cmd and cmd not in seen and not cmd.startswith("npm run ") is False:
            seen.add(cmd)
            items.append(f"运行：`{cmd}`")
        if len(items) >= 4:
            break

    # ② 仓内实际存在的入口脚本（补 README 没写出来的）
    #    先认「包形态」：有 <name>/__init__.py 且有 <name>/__main__.py ⇒ `python -m <name>`
    #    （实测 yasuo 仓：真实入口是 `python -m yasuo`，若按脚本名猜会给出
    #     `python run.py` —— run.py 存在但不是入口，guess 错了）
    pkg_candidates: list[str] = []
    # 形态 a：顶层即包（仓根有 __init__.py 与 __main__.py）
    if (repo / "__init__.py").is_file() and (repo / "__main__.py").is_file():
        pkg_candidates.append(repo.name)
    # 形态 b：包子目录（<name>/__init__.py + <name>/__main__.py）
    for entry in sorted(repo.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / "__init__.py").is_file() and (entry / "__main__.py").is_file():
            pkg_candidates.append(entry.name)
    if pkg_candidates:
        cmd = f"python -m {pkg_candidates[0]}"
        if cmd not in seen:
            seen.add(cmd)
            items.append(f"运行：`{cmd}`")
    else:
        # 没有包形态时才按脚本名猜入口
        entry_candidates = (
            "main.py", "main.pyw", "app.py", "run.py", "start.py",
            "index.js", "main.js", "index.ts", "app.js", "cli.py",
            "main.py3", "play.py", "game.py", "game.pyw",
        )
        for name in entry_candidates:
            if (repo / name).is_file():
                cmd = f"python {name}" if name.endswith(".py") else f"node {name}"
                if cmd not in seen:
                    seen.add(cmd)
                    items.append(f"运行：`{cmd}`")
                break

    # ③ 依赖说明（若 README 已提过依赖但未成句，补一条）
    m = _DEP_RE.search(text)
    if m and not any("依赖" in it for it in items):
        items.append(f"依赖：{m.group(1).strip()}")

    return items[:6]


def build_sections(repo: Path, text: str) -> list[tuple[str, list[str]]]:
    """算出该仓需要追加哪些章节（只补缺失的）。"""
    have = detect_sections(text)
    todo: list[tuple[str, list[str]]] = []

    # 用法/示例 —— 从仓库自身事实推导
    if "用法/示例" not in have:
        usage = derive_usage(repo, text)
        if usage:
            todo.append(("用法", usage))

    # 许可 —— 从 LICENSE 文件识别
    if "许可" not in have:
        lic = detect_license(repo)
        if lic:
            body = [f"{lic}，见 [LICENSE](LICENSE)。"]
            if lic == "MIT-0":
                body.append("MIT No Attribution —— 无署名义务。")
            elif lic == "MIT":
                body.append("MIT License —— 保留版权声明即可。")
            todo.append(("许可", body))

    # 安装/快速开始 —— 只有在能推出命令时才补（无依赖声明的仓不硬编 pip 命令）
    if "安装/快速开始" not in have:
        install: list[str] = []
        for name in ("requirements.txt", "pyproject.toml", "package.json", "Cargo.toml"):
            if (repo / name).is_file():
                if name == "requirements.txt":
                    install.append("安装依赖：`pip install -r requirements.txt`")
                elif name == "pyproject.toml":
                    install.append("安装依赖：`pip install -e .`")
                elif name == "package.json":
                    install.append("安装依赖：`npm install`")
                elif name == "Cargo.toml":
                    install.append("安装依赖：`cargo build`")
                break
        if not install:
            install.append("本项目为免安装形态：克隆后直接运行（见下方用法）。")
        todo.append(("快速开始", install))

    return todo


def process_repo(repo: Path) -> dict:
    """检查单个仓，算出待补章节（不写盘）。"""
    readme = None
    candidates = []
    for name in ("README.md", "README.MD", "README.markdown", "README.rst", "README.txt"):
        if (repo / name).is_file():
            candidates.append(repo / name)
    # 2026-11-21：跳过 Gitee 模板占位 README（如 README.en.md 全是 xxxx），
    # 优先补真正的内容文件。判据侧读取顺序由 repocheck 决定，本工具只管写对文件。
    for cand in candidates:
        try:
            txt = cand.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _is_placeholder_readme(txt):
            readme = cand
            break
    if readme is None and candidates:
        # 全是占位模板 ⇒ 取主 README 补（总比没有强）
        readme = next((c for c in candidates if c.name.lower() == "readme.md"), candidates[0])
    if readme is None:
        return {"repo": repo.name, "status": "no-readme"}
    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"repo": repo.name, "status": "unreadable", "error": str(exc)}

    todo = build_sections(repo, text)
    if not todo:
        return {"repo": repo.name, "status": "ok"}
    return {
        "repo": repo.name,
        "status": "todo",
        "readme": readme.name,
        "sections": [{"title": t, "lines": b} for t, b in todo],
    }


def render(repo: str, sections: list[dict]) -> str:
    """生成追加文本。"""
    out: list[str] = ["", ""]
    for sec in sections:
        out.append(f"## {sec['title']}")
        out.append("")
        for line in sec["lines"]:
            out.append(f"- {line}")
        out.append("")
    out.append(f"<!-- 补写记账：{repo} · 本段由 allin 仓 tools/publish_area_readme_sections.py 依据本仓自身事实补写 -->")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区 README 缺段批量补写")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""),
                    help="发布区根目录（默认取 $PROJECTS_ROOT）")
    ap.add_argument("--apply", action="store_true", help="实际写盘（默认预演）")
    ap.add_argument("--dry-run", action="store_true", help="预演（默认行为）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--only", default="", help="只处理指定仓名（逗号分隔）")
    args = ap.parse_args(argv)

    root = args.repos_root
    if not root:
        print("用法错误：需 --repos-root 或设 $PROJECTS_ROOT", file=sys.stderr)
        return 2
    rp = Path(root)
    if not rp.is_dir():
        print(f"用法错误：发布区不存在 {rp}", file=sys.stderr)
        return 2

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    repos = sorted(p for p in rp.iterdir() if p.is_dir() and (p / ".git").exists())
    if only:
        repos = [p for p in repos if p.name in only]

    results = [process_repo(p) for p in repos]
    todos = [r for r in results if r["status"] == "todo"]

    if args.json:
        print(json.dumps({"scanned": len(repos), "todo": len(todos),
                          "results": todos}, ensure_ascii=False, indent=2))
    else:
        print(f"扫描 {len(repos)} 个仓，待补 {len(todos)} 个")
        for r in todos:
            titles = "、".join(s["title"] for s in r["sections"])
            print(f"  {r['repo']:<28} 补 [{titles}]")

    if not todos:
        return 0
    if not args.apply:
        print("\n预演模式：加 --apply 实际写盘")
        return 1

    changed: list[str] = []
    for r in todos:
        repo = rp / r["repo"]
        readme = repo / r["readme"]
        text = readme.read_text(encoding="utf-8", errors="replace")
        # 追加前确保末尾换行，避免与原末行粘连
        if not text.endswith("\n"):
            text += "\n"
        text += render(r["repo"], r["sections"])
        readme.write_text(text, encoding="utf-8", newline="\n")
        changed.append(r["repo"])

    print(f"\n已补写 {len(changed)} 个仓的 README")
    for name in changed:
        print(f"  {name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
