"""文档类规则 9-16：许可证、README、SECURITY、CONTRIBUTING、CHANGELOG。

判定口径参照 OpenSSF Scorecard（License / Security-Policy）、
repolinter default 规则集、standard-readme 与 Keep a Changelog。
所有判定只读本地文件，不联网、不执行项目代码。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from _optional import HAS_LICENSE_EXPRESSION, HAS_MARKDOWN_IT
from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext

try:  # Python 3.11+ 内置
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

#: 报告里单项 detail 最多列几条。
MAX_DETAIL_ITEMS = 5


# ---------------------------------------------------------------------------
# 许可证识别
# ---------------------------------------------------------------------------

#: (SPDX, 必须全部命中的特征片段)。按「越具体越靠前」排序。
_LICENSE_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Apache-2.0", ("apache license", "version 2.0")),
    ("MPL-2.0", ("mozilla public license", "version 2.0")),
    ("AGPL-3.0", ("gnu affero general public license", "version 3")),
    ("LGPL-3.0", ("gnu lesser general public license", "version 3")),
    ("LGPL-2.1", ("gnu lesser general public license", "version 2.1")),
    ("GPL-3.0", ("gnu general public license", "version 3")),
    ("GPL-2.0", ("gnu general public license", "version 2")),
    ("BSD-3-Clause", ("redistribution and use in source and binary forms",
                      "neither the name")),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",
                      "this list of conditions and the following disclaimer")),
    ("MIT", ("permission is hereby granted, free of charge",)),
    ("ISC", ("permission to use, copy, modify, and/or distribute this software",)),
    ("Unlicense", ("this is free and unencumbered software released into the public domain",)),
    ("CC0-1.0", ("creative commons legal code", "cc0")),
    ("WTFPL", ("do what the fuck you want to public license",)),
)

#: 关键词 → SPDX（用于 README 章节与清单字段这类短文本）。
#: 顺序敏感：泛化词（mit / isc）必须排在最后，且用词边界避免误配。
_KEYWORD_TO_SPDX: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Apache-2.0", ("apache-2.0", "apache 2.0", "apache license")),
    ("MPL-2.0", ("mpl-2.0", "mozilla public license")),
    ("AGPL-3.0", ("agpl-3.0", "agplv3", "agpl v3")),
    ("LGPL-3.0", ("lgpl-3.0", "lgplv3", "lgpl v3")),
    ("LGPL-2.1", ("lgpl-2.1", "lgplv2.1")),
    ("GPL-3.0", ("gpl-3.0", "gplv3", "gpl v3", "gnu general public license v3")),
    ("GPL-2.0", ("gpl-2.0", "gplv2", "gpl v2")),
    ("BSD-3-Clause", ("bsd-3-clause", "3-clause bsd", "new bsd")),
    ("BSD-2-Clause", ("bsd-2-clause", "2-clause bsd", "simplified bsd")),
    ("CC0-1.0", ("cc0-1.0", "cc0")),
    ("Unlicense", ("unlicense", "public domain")),
    ("WTFPL", ("wtfpl",)),
    ("MIT", ("mit license", "mit")),
    ("ISC", ("isc license", "isc")),
)

_LICENSE_PREFIXES = ("license", "licence", "copying", "copyright")


def normalize_spdx(value: str) -> str:
    """把 ``GPL-3.0`` / ``GPL-3.0-only`` / ``gpl3`` 归一成同一族名。"""
    low = value.strip().lower()
    low = low.replace("-only", "").replace("-or-later", "").replace("+", "")
    for spdx, keys in _KEYWORD_TO_SPDX:
        for key in keys:
            if key in low:
                return spdx
    return value.strip()


def identify_license(text: str) -> str | None:
    """从 LICENSE 全文识别 SPDX 标识；识别不出返回 ``None``。"""
    normalized = " ".join(text.split()).lower()
    for spdx, required in _LICENSE_SIGNATURES:
        if all(fragment in normalized for fragment in required):
            return spdx
    return None


def _keyword_spdx(text: str) -> str | None:
    """在短文本里按关键词找 SPDX（带回退：装了 license-expression 就再校验一次）。"""
    low = text.lower()
    found: str | None = None
    for spdx, keys in _KEYWORD_TO_SPDX:
        for key in keys:
            if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", low):
                found = spdx
                break
        if found:
            break
    if found is None:
        return None
    if HAS_LICENSE_EXPRESSION:  # 可选依赖：只做规范化校验，失败也不改变结论
        try:
            from license_expression import Licensing  # type: ignore[import-not-found]

            parsed = Licensing().parse(found)
            if parsed is not None:
                return str(parsed)
        except Exception:  # noqa: BLE001 - 可选依赖永不影响主流程
            pass
    return found


# ---------------------------------------------------------------------------
# 文件定位辅助
# ---------------------------------------------------------------------------

def _readme_rel(ctx: "ProjectContext") -> str | None:
    return ctx.root_startswith("readme")


def _license_rel(ctx: "ProjectContext") -> str | None:
    return ctx.root_startswith(*_LICENSE_PREFIXES)


def _changelog_rel(ctx: "ProjectContext") -> str | None:
    return ctx.root_startswith("changelog")


def _find_in_dirs(ctx: "ProjectContext", prefixes: tuple[str, ...],
                  dirs: tuple[str, ...] = ("", ".github", "docs")) -> str | None:
    """在若干候选目录里按前缀（不区分大小写）找文件。"""
    for rel_dir in dirs:
        for name in ctx.children(rel_dir):
            if name.lower().startswith(prefixes):
                return f"{rel_dir}/{name}" if rel_dir else name
    return None


def _manifest_license(ctx: "ProjectContext") -> tuple[str | None, str]:
    """从 pyproject.toml / package.json / Cargo.toml 读许可证声明。"""
    if "pyproject.toml" in ctx.file_set:
        value = _pyproject_license(ctx)
        if value:
            return value, "pyproject.toml"
    if "package.json" in ctx.file_set:
        text = ctx.text("package.json")
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            raw = data.get("license") if isinstance(data, dict) else None
            if isinstance(raw, dict):
                raw = raw.get("type")
            if isinstance(raw, str) and raw.strip():
                return _keyword_spdx(raw) or raw.strip(), "package.json"
    if "Cargo.toml" in ctx.file_set:
        text = ctx.text("Cargo.toml")
        if text and tomllib is not None:
            try:
                data = tomllib.loads(text)
                raw = (data.get("package") or {}).get("license")
                if isinstance(raw, str) and raw.strip():
                    return _keyword_spdx(raw) or raw.strip(), "Cargo.toml"
            except Exception:  # noqa: BLE001 - TOML 解析失败不影响其他来源
                pass
    return None, ""


def _pyproject_license(ctx: "ProjectContext") -> str | None:
    text = ctx.text("pyproject.toml")
    if text is None:
        return None
    data: dict = {}
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception:  # noqa: BLE001
            data = {}
    if data:
        project = data.get("project") or {}
        raw = project.get("license")
        if isinstance(raw, str):
            return _keyword_spdx(raw) or raw.strip() or None
        if isinstance(raw, dict):
            inner = raw.get("text")
            if isinstance(inner, str) and inner.strip():
                return _keyword_spdx(inner) or inner.strip()
        poetry = (data.get("tool") or {}).get("poetry") or {}
        raw = poetry.get("license")
        if isinstance(raw, str) and raw.strip():
            return _keyword_spdx(raw) or raw.strip()
    # 回退：行级扫描（TOML 解析失败时）
    match = re.search(r"^\s*license\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
    if match:
        return _keyword_spdx(match.group(1)) or match.group(1).strip()
    return None


def _readme_license_section(ctx: "ProjectContext") -> str | None:
    """README 里 License 章节标题后 500 字符内出现的 SPDX。"""
    rel = _readme_rel(ctx)
    if rel is None:
        return None
    text = ctx.text(rel)
    if text is None:
        return None
    match = re.search(r"^#{1,6}\s*(?:license|licence|许可|协议)\b.*$", text, re.I | re.M)
    if not match:
        return None
    segment = text[match.end(): match.end() + 500]
    return _keyword_spdx(segment)


# ---------------------------------------------------------------------------
# 规则 9-10：许可证
# ---------------------------------------------------------------------------

def _check_license_identifiable(ctx: "ProjectContext") -> CheckResult:
    """规则 9：LICENSE 文件能否识别为常见开源许可证。"""
    rel = _license_rel(ctx)
    if rel is None:
        return CheckResult.skip("no-license-file")  # 规则 5 已报，避免重复噪音
    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")
    spdx = identify_license(text)
    if spdx:
        return CheckResult.ok()
    return CheckResult.bad(f"{rel} 无法识别为常见开源许可证")


def _check_license_consistency(ctx: "ProjectContext") -> CheckResult:
    """规则 10：LICENSE 文件 / README 章节 / 项目清单三处声明是否一致。"""
    license_rel = _license_rel(ctx)
    if license_rel is None:
        return CheckResult.skip("no-license-file")

    text = ctx.text(license_rel)
    from_file = identify_license(text) if text else None
    from_readme = _readme_license_section(ctx)
    from_manifest, manifest_rel = _manifest_license(ctx)

    sources = {
        "LICENSE 文件": from_file,
        "README": from_readme,
        (manifest_rel or "项目清单"): from_manifest,
    }
    present = {k: v for k, v in sources.items() if v}
    if not present:
        return CheckResult.bad("三处均未声明许可证")

    families = {normalize_spdx(v) for v in present.values()}
    if len(families) > 1:
        detail = " / ".join(f"{k}={v}" for k, v in present.items())
        return CheckResult.bad("声明不一致：" + detail)

    missing = [k for k, v in sources.items() if not v]
    if missing:
        return CheckResult.bad("缺少声明来源：" + "、".join(missing))
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 11-12：README
# ---------------------------------------------------------------------------

#: README 应覆盖的三类语义（中英文关键词任一命中即可）。
_README_SECTIONS: tuple[tuple[str, str], ...] = (
    ("安装/快速开始", r"install|installation|安装|快速开始|getting started|quick ?start"),
    ("用法/示例", r"usage|example|用法|使用|示例"),
    ("许可", r"licen[cs]e|许可|协议"),
)

_MD_H2_RE = re.compile(r"^#{2}\s+\S", re.M)
_MD_H2_ANY_RE = re.compile(r"^#{2,6}\s+\S", re.M)

#: Markdown 内联链接与图片（离线只校验相对路径）。
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_MD_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


def _count_headings(text: str) -> int:
    """统计二级标题数；装了 markdown-it-py 就顺便验证一次结构。"""
    count = len(_MD_H2_RE.findall(text))
    if HAS_MARKDOWN_IT:
        try:
            from markdown_it import MarkdownIt  # type: ignore[import-not-found]

            tokens = MarkdownIt().parse(text)
            alt = sum(1 for t in tokens if t.type == "heading_open" and t.tag == "h2")
            if alt:
                return alt
        except Exception:  # noqa: BLE001 - 可选依赖永不影响主流程
            pass
    return count


def _check_readme_structure(ctx: "ProjectContext") -> CheckResult:
    """规则 11：README 是否有足够的一级结构并覆盖安装/用法/许可。"""
    rel = _readme_rel(ctx)
    if rel is None:
        return CheckResult.skip("no-readme")  # 规则 2 已报
    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")

    problems: list[str] = []
    lines = text.count("\n") + 1
    headings = _count_headings(text)
    if lines >= 100 and headings < 5:
        problems.append(f"二级标题仅 {headings} 个（建议 ≥5）")

    missing = [label for label, pattern in _README_SECTIONS
               if not re.search(pattern, text, re.I)]
    if missing:
        problems.append("缺少 " + "、".join(missing) + " 相关内容")

    if problems:
        return CheckResult.bad("；".join(problems))
    return CheckResult.ok()


def _iter_local_links(text: str) -> list[str]:
    """抽出需要本地校验的相对链接（丢弃外链、锚点与协议链接）。"""
    targets = [m.group(1).strip("<>") for m in _MD_LINK_RE.finditer(text)]
    targets += _MD_IMG_RE.findall(text)
    result: list[str] = []
    for target in targets:
        if not target or target.startswith("#"):
            continue
        if _SCHEME_RE.match(target) or target.startswith("//"):
            continue
        clean = target.split("#", 1)[0].split("?", 1)[0]
        if clean:
            result.append(clean)
    return result


def _check_readme_links(ctx: "ProjectContext") -> CheckResult:
    """规则 12：README 中的相对链接是否指向真实存在的文件。"""
    rel = _readme_rel(ctx)
    if rel is None:
        return CheckResult.skip("no-readme")
    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")

    base = Path(rel).parent
    broken: list[str] = []
    seen: set[str] = set()
    for target in _iter_local_links(text):
        if target in seen:
            continue
        seen.add(target)
        try:
            if not (ctx.root / base / target).exists():
                broken.append(target)
        except OSError:
            broken.append(target)
        if len(broken) >= MAX_DETAIL_ITEMS:
            break

    if broken:
        return CheckResult.bad(f"{len(broken)} 个相对链接指向不存在的文件：" + ", ".join(broken))
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 13-14：SECURITY.md
# ---------------------------------------------------------------------------

_SECURITY_REASON = "no-security-file"


def _security_rel(ctx: "ProjectContext") -> str | None:
    return _find_in_dirs(ctx, ("security",))


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL_RE = re.compile(r"https?://\S+")
_DAYS_RE = re.compile(r"\b\d{1,3}\s*(?:day|days|天)\b", re.I)


def _check_security_present(ctx: "ProjectContext") -> CheckResult:
    """规则 13：是否存在 SECURITY.md（根 / .github / docs，不区分大小写）。"""
    if _security_rel(ctx):
        return CheckResult.ok()
    return CheckResult.bad("根 / .github / docs 均无 SECURITY.md")


def _check_security_content(ctx: "ProjectContext") -> CheckResult:
    """规则 14：SECURITY.md 内容是否有可用的漏洞上报通道（Scorecard 6/3/1 口径）。"""
    rel = _security_rel(ctx)
    if rel is None:
        return CheckResult.skip(_SECURITY_REASON)
    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")

    points = 0
    if _EMAIL_RE.search(text) or _URL_RE.search(text):
        points += 6
    stripped = _URL_RE.sub(" ", _EMAIL_RE.sub(" ", text))
    if len(stripped.strip()) >= 50:
        points += 3
    low = text.lower()
    if "vuln" in low and "disclos" in low and _DAYS_RE.search(text):
        points += 1

    if points < 4:
        return CheckResult.bad(f"内容评分 {points}/10（缺联系方式或处置说明）")
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 15-16：CONTRIBUTING / CHANGELOG
# ---------------------------------------------------------------------------

def _check_contributing(ctx: "ProjectContext") -> CheckResult:
    """规则 15：是否有 CONTRIBUTING 并说明贡献流程。"""
    rel = _find_in_dirs(ctx, ("contrib",))
    if rel is None:
        return CheckResult.bad("根 / .github / docs 均无 CONTRIBUTING*")
    text = ctx.text(rel)
    if text is not None and not re.search(r"pull request|\bPR\b|issue|提交|贡献", text, re.I):
        return CheckResult.bad(f"{rel} 未说明贡献流程")
    return CheckResult.ok()


_CHANGELOG_UNRELEASED_RE = re.compile(r"^##\s*\[?Unreleased\]?", re.M)
_CHANGELOG_ENTRY_RE = re.compile(
    r"^##\s*\[?\d+\.\d+\.\d+\]?\s+-\s+\d{4}-\d{2}-\d{2}", re.M)


def _check_changelog_format(ctx: "ProjectContext") -> CheckResult:
    """规则 16：CHANGELOG 是否采用 Keep a Changelog 结构。"""
    rel = _changelog_rel(ctx)
    if rel is None:
        return CheckResult.bad("根目录无 CHANGELOG*")
    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")
    if _CHANGELOG_UNRELEASED_RE.search(text) or _CHANGELOG_ENTRY_RE.search(text):
        return CheckResult.ok()
    return CheckResult.bad(
        f"{rel} 未采用 Keep a Changelog 结构（缺 Unreleased 段或“## [x.y.z] - YYYY-MM-DD”条目）")


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------

RULES_DOCS: tuple[Rule, ...] = (
    Rule(9, "license.unrecognized", "许可证不可识别",
         "LICENSE 文件内容匹配不上常见开源许可证特征句（MIT/Apache-2.0/BSD/GPL/MPL/ISC 等）",
         Severity.WARN, _check_license_identifiable, requires=("license_expression",)),
    Rule(10, "license.inconsistent", "许可证三处声明不一致",
         "LICENSE 文件、README License 章节、项目清单 license 字段三者缺一或互相矛盾",
         Severity.ERROR, _check_license_consistency, requires=("license_expression",)),
    Rule(11, "docs.readme_structure", "README 结构不完整",
         "README 二级标题 <5（≥100 行时）或缺安装/用法/许可三类内容",
         Severity.ERROR, _check_readme_structure, requires=("markdown_it",)),
    Rule(12, "docs.readme_dead_link", "README 相对链接死链",
         "README 中指向本地相对路径的链接/图片在项目内不存在",
         Severity.WARN, _check_readme_links),
    Rule(13, "security.missing", "无 SECURITY.md",
         "根 / .github / docs 下均无 SECURITY.md（不区分大小写）",
         Severity.WARN, _check_security_present),
    Rule(14, "security.thin", "SECURITY.md 内容不足",
         "SECURITY.md 缺有效联系方式/自由文本说明/漏洞披露与响应期限（Scorecard 6+3+1 口径 <4）",
         Severity.WARN, _check_security_content),
    Rule(15, "docs.contributing_missing", "无 CONTRIBUTING",
         "根 / .github / docs 下无 CONTRIBUTING*，或文件内未说明贡献流程",
         Severity.WARN, _check_contributing),
    Rule(16, "docs.changelog_format", "CHANGELOG 结构不合格",
         "无 CHANGELOG*，或不含 Unreleased 段与“## [x.y.z] - YYYY-MM-DD”格式条目",
         Severity.WARN, _check_changelog_format),
)
