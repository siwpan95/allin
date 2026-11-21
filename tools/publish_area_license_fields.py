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

#: 与门禁**同源**：直接复用 repocheck 的 SPDX 关键词表与归一化函数，
#: 而不是在本工具里另造一套。判据一旦分叉就会互相打架 —— 2026-11-21 实测：
#: 门禁的 ``_KEYWORD_TO_SPDX`` 不含 ``MIT-0``，``mit`` 会把 MIT-0 归一成 MIT 族，
#: 因此 README 写「MIT」而 LICENSE 是 MIT-0 时门禁判**同族、不报错**；
#: 本工具若按字面比较，就会把这 9 个已合规的仓误判成待补并再写一遍声明。
sys.path.insert(0, str(Path(__file__).resolve().parent / "repocheck"))
try:  # pragma: no cover - 依赖仓内目录结构，缺失时退回宽松判据
    from rules_docs import _keyword_spdx, normalize_spdx
except Exception:  # noqa: BLE001
    _keyword_spdx = None  # type: ignore[assignment]
    normalize_spdx = None  # type: ignore[assignment]

#: 许可章节标题 —— 与门禁 ``tools/repocheck/rules_docs.py::_readme_license_section``
#: 同源（含编号章节「## 10. 许可证」的写法）。工具与门禁判据必须一致，否则会出现
#: 「工具认为已声明、门禁认为缺声明」的僵局：实测 2026-11-21，dict-scene-engine 的
#: 「## 插件与事件协议」被本工具旧的宽判据当成许可章节（正则含「协议」），
#: loly / stay / zhuangtaiji 的章节里只有「演示用途」「以既有约定为准」和一个 badge
#: 而无任何许可类型，工具三次都跳过，门禁三次都判红。
_LICENSE_HEAD = re.compile(
    r"^#{1,6}\s*(?:\d+[.、)．]*\s*)?(?:license|licence|许可|协议)(?![a-z0-9]).*$",
    re.I | re.M)

#: SPDX 标识 → README 里可能出现的写法（归一化后比较）。
_LICENSE_TOKENS = {
    "MIT-0": (r"\bmit[-\s_]?0\b", r"\bmit\s+no\s+attribution\b"),
    "MIT": (r"\bmit\b(?!\s*[-\s]?\s*0\b)", r"\bmit\s+license\b"),
    "Apache-2.0": (r"\bapache[-\s]?2\.0\b", r"\bapache\s+license\b"),
    "GPL-3.0": (r"\bgpl[-\s]?3(\.0)?\b", r"\bgnu\s+general\s+public\s+license\b"),
    "BSD-3-Clause": (r"\bbsd[-\s]?3[-\s]?clause\b",),
    "CC0-1.0": (r"\bcc0\b",),
}


def _mentions_license(text: str, lic: str) -> bool:
    """文本里是否出现**明确**的许可类型（与门禁同族口径）。

    优先走门禁的 ``_keyword_spdx`` + ``normalize_spdx``：MIT 与 MIT-0 在门禁里
    属同一族，这里也必须如此，否则同一个仓会出现「工具补、门禁仍判不一致」或
    「门禁已认可、工具又补一遍」的来回拉锯。
    """
    if _keyword_spdx is not None and normalize_spdx is not None:
        found = _keyword_spdx(text)
        if not found:
            return False
        a, b = normalize_spdx(found), normalize_spdx(lic)
        # 前缀包容：本工具的 detect_license 会把 LICENSE 识别成 ``GPL-3``，
        # 而门禁关键词表里是 ``GPL-3.0`` —— 同一许可的两种写法，不能判成两族。
        return a == b or a.startswith(b) or b.startswith(a)
    low = text.lower()  # 兜底：门禁模块不可用时按关键词表近似
    for pat in _LICENSE_TOKENS.get(lic, ()):
        if re.search(pat, low):
            return True
    if lic not in _LICENSE_TOKENS:
        norm = re.sub(r"[^a-z0-9.]", "", lic.lower())
        if norm and norm in re.sub(r"[^a-z0-9.]", "", low):
            return True
    return False


def _first_paragraph_after_head(text: str) -> tuple[int, int, str] | None:
    """许可章节标题后的第一段：返回 (段起始偏移, 段结束偏移, 段文本)。

    两个偏移都要：门禁 ``_readme_license_section`` **只读第一段**，所以类型声明
    必须落到第一段的位置上 —— 补在段尾会被空行隔成第二段，门禁照样判缺
    （实测 loly / stay 补完仍红）。故按 ``start`` 插到段前。
    """
    m = _LICENSE_HEAD.search(text)
    if not m:
        return None
    pos = m.end()
    start: int | None = None
    end = pos
    lines: list[str] = []
    for raw in text[m.end():].splitlines(keepends=True):
        stripped = raw.strip()
        if stripped.startswith("#"):
            break
        if not stripped:
            if lines:
                break
            pos = end = pos + len(raw)
            continue
        if start is None:
            start = pos
        lines.append(stripped)
        pos = end = pos + len(raw)
    if start is None:
        return None
    return (start, end, "\n".join(lines))


def _readme_declares(rd: Path, lic: str) -> bool:
    """README 是否已用**明确类型**声明了该许可（与门禁同一口径）。

    门禁 ``tools/repocheck/rules_docs.py`` 认三种形态，本函数必须同样认全，否则
    会出现「工具一直补、门禁一直绿不了」或者反过来的僵局：

    1. ``## 许可`` 章节 + 章节第一段写明类型；
    2. 行首引用块 ``> 仓库：… ｜ 许可：MIT-0（见 LICENSE）``（模板化 README 常见）；
    3. 不带 ``>`` 的同款正文行 ``仓库：<url> ｜ 许可：X``。
    """
    text = rd.read_text(encoding="utf-8", errors="replace")
    para = _first_paragraph_after_head(text)
    if para and _mentions_license(para[2], lic):
        return True
    # 形态 2/3：模板行。第三方语境要排除（同 _readme_license_section 的理由）。
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith(">") or re.match(r"^(?:仓库|repo|repository)\s*[:：]", s, re.I)):
            continue
        if not re.search(r"许可|licen[cs]e", s, re.I):
            continue
        if re.search(r"第三方|vendor|依赖|兼容|不兼容|GPL|AGPL|LGPL|upstream|上游", s, re.I):
            continue
        if _mentions_license(s, lic):
            return True
    return False


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
        if not _readme_declares(rd, lic):
            para = _first_paragraph_after_head(text)
            if para is None:
                # 没有许可章节 ⇒ 整段追加
                addition = (
                    f"\n\n## 许可\n\n- {lic}，见 [LICENSE](LICENSE)。\n\n"
                    f"<!-- 补写记账：{repo.name} · 本段由 allin 仓 "
                    f"tools/publish_area_license_fields.py 依据本仓 LICENSE 文件实读补写 -->\n"
                )
                actions.append({"file": rd.name, "kind": "readme", "new": text + addition})
            else:
                # 章节在、但通篇没写具体类型（如「本项目为演示/教学用途」）⇒
                # 把类型声明插到**第一段之前**，而不是段尾追加：门禁只读标题后的
                # 第一段，补在段尾会被空行隔成第二段，等于白补（实测 loly / stay）。
                start, _end, _body = para
                line = (
                    f"- 许可类型：{lic}，见 [LICENSE](LICENSE)。\n"
                    f"<!-- 补写记账：{repo.name} · 许可类型由 allin 仓 "
                    f"tools/publish_area_license_fields.py 补写（原章节未声明具体类型） -->\n\n"
                )
                actions.append({
                    "file": rd.name, "kind": "readme",
                    "new": text[:start] + line + text[start:],
                })

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
