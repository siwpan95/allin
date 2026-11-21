r"""publish_area_license_fields.py —— 发布区清单/README 许可证声明补齐（规则 10 收口）

为什么有这个脚本
    规则 10（``license.inconsistent``）要求 LICENSE 文件 / README / 项目清单
    三处声明不矛盾、且至少两处可交叉复核。实测发布区 139 仓剩余 error 形态：
      · 10 仓：有 pyproject.toml / package.json 但**没写 license 字段**
      · 7 仓：README 缺许可声明（无「许可」章节，也无行首引用声明）
      · 1 仓：真冲突（sfx-download 的 LICENSE=MIT / README=CC0-1.0）—— 人工裁决

口径纪律
    · 写入的许可证类型**从该仓 LICENSE 文件实读**，不臆造；
    · pyproject.toml：在 [project] 段插入 ``license = "..."``（有 [project] 才插）；
    · package.json：在根对象插入 ``"license": "..."``；
    · README：追加「## 许可」段，注明类型与 LICENSE 链接；
    · 真冲突（LICENSE 与 README 类型不同）**不自动改**，留给人工裁决并输出清单。

用法
    python tools/publish_area_license_fields.py --repos-root <发布区根> --dry-run
    python tools/publish_area_license_fields.py --repos-root <发布区根> --apply

退出码
    0 无待办
    1 有待补（预演）或已完成补写（--apply）
    2 用法或环境错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

from publish_area_readme_sections import detect_license, detect_sections


def add_pyproject_license(path: Path, lic: str) -> tuple[str, bool]:
    """在 [project] 段插入 license 字段。返回 (新文本, 是否改动)。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = tomllib.loads(text)
    except Exception:  # noqa: BLE001 - TOML 解析失败就不动
        return text, False
    if "project" not in data:
        return text, False
    if data["project"].get("license"):
        return text, False
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "[project]":
            lines.insert(i + 1, f'license = "{lic}"')
            return "\n".join(lines) + "\n", True
    return text, False


def add_package_json_license(path: Path, lic: str) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, False
    if not isinstance(data, dict) or data.get("license"):
        return text, False
    # 保留原缩进风格（检测 2 空格 / tab）
    indent = "  "
    body = text
    m = re.search(r'\{\s*\n([ \t]+)"', text)
    if m:
        indent = m.group(1)
    # 在根对象第一个键之后插入
    keys = list(data.keys())
    if not keys:
        return text, False
    first = keys[0]
    pattern = re.compile(rf'^(\s*)"{re.escape(first)}"\s*:', re.M)
    mm = pattern.search(text)
    if not mm:
        return text, False
    insert_at = text.rfind("\n", 0, mm.start()) + 1
    line = f'{indent}"license": "{lic}",\n'
    return text[:insert_at] + line + text[insert_at:], True


def find_readme(repo: Path) -> Path | None:
    for name in ("README.md", "README.MD", "README.markdown", "README.rst"):
        if (repo / name).is_file():
            return repo / name
    return None


def process_repo(repo: Path) -> dict:
    lic = detect_license(repo)
    if not lic:
        return {"repo": repo.name, "status": "no-license"}

    actions: list[dict] = []

    # pyproject.toml 缺 license
    pp = repo / "pyproject.toml"
    if pp.is_file():
        try:
            data = tomllib.loads(pp.read_text(encoding="utf-8", errors="replace"))
            if "project" in data and not data["project"].get("license"):
                new, changed = add_pyproject_license(pp, lic)
                if changed:
                    actions.append({"file": "pyproject.toml", "kind": "pyproject", "new": new})
        except Exception:  # noqa: BLE001
            pass

    # package.json 缺 license
    pj = repo / "package.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict) and not data.get("license"):
                new, changed = add_package_json_license(pj, lic)
                if changed:
                    actions.append({"file": "package.json", "kind": "package", "new": new})
        except json.JSONDecodeError:
            pass

    # README 缺许可声明
    rd = find_readme(repo)
    if rd is not None:
        text = rd.read_text(encoding="utf-8", errors="replace")
        if "许可" not in detect_sections(text):
            addition = (
                f"\n\n## 许可\n\n- {lic}，见 [LICENSE](LICENSE)。\n\n"
                f"<!-- 补写记账：{repo.name} · 本段由 allin 仓 "
                f"tools/publish_area_license_fields.py 依据本仓 LICENSE 文件实读补写 -->\n"
            )
            actions.append({"file": rd.name, "kind": "readme", "new": text + addition})

    if not actions:
        return {"repo": repo.name, "status": "ok", "license": lic}
    return {"repo": repo.name, "status": "todo", "license": lic, "actions": actions}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区许可证声明补齐")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
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

    repos = sorted(p for p in rp.iterdir() if p.is_dir() and (p / ".git").exists())
    only = {s.strip() for s in args.only.split(",") if s.strip()}
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
            files = "、".join(a["file"] for a in r["actions"])
            print(f"  {r['repo']:<26} [{r['license']}] 补 {files}")

    if not todos:
        return 0
    if not args.apply:
        print("\n预演模式：加 --apply 实际写盘")
        return 1

    n = 0
    for r in todos:
        repo = rp / r["repo"]
        for a in r["actions"]:
            target = repo / a["file"]
            target.write_text(a["new"], encoding="utf-8", newline="\n")
            n += 1
    print(f"\n已补写 {n} 处声明（{len(todos)} 个仓）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
