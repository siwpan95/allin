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
    """在短文本里按关键词找 SPDX（带回退：装了 license-expression 就再校验一次）。

    2026-11-21 修订：原实现按 ``_KEYWORD_TO_SPDX`` 的**词表顺序**取第一个命中，
    于是「整体 MIT；apps/video/src/live/（real-url）为 GPL-2.0」这种**混合许可**
    的标准写法被判成 GPL-2.0（GPL 在词表里排在 MIT 前面），与 LICENSE 文件=MIT
    构成假阳性「声明不一致」。改为按**文本中最先出现的位置**取 —— 这类写法里
    主体许可总在前面，子目录/依赖的许可在后面。

    实测影响：private-radio-stations（LICENSE=MIT / package.json=MIT / README 被判 GPL）。
    """
    low = text.lower()
    best: tuple[int, str] | None = None
    for spdx, keys in _KEYWORD_TO_SPDX:
        for key in keys:
            m = re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", low)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), spdx)
            if m:
                break  # 该 SPDX 的任一别名首次命中即可，不必再试其它别名
    if best is None:
        return None
    found = best[1]
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
    """定位本仓的主 README。

    2026-11-21 修订：``ctx.root_startswith("readme")`` 按前缀取**第一个**匹配项，
    字典序下 ``README.en.md`` 排在 ``README.md`` 之前 ⇒ 会读到**英文版**。
    实测 test 仓：``README.en.md`` 是 Gitee 建仓模板的**未填写占位**（正文全是
    ``xxxx`` / ``Readme_XXX.md``），真正的内容在 ``README.md`` ⇒ 规则 11 读着
    占位文件判「缺用法/示例、缺许可」，而补写工具写的是 ``README.md``，
    两者对不上（补了仍报红）。

    本函数改为：跳过**未填写的模板占位 README**，优先取 ``README.md``。
    只影响 README 类规则（11/12/16），不动 ``root_startswith`` 本身
    （它是通用函数，CHANGELOG/LICENSE 也在用）。
    """
    primary = ctx.root_startswith("readme")
    if primary is None:
        return None
    # 收集所有 README 候选
    candidates = [primary]
    try:
        for raw, lowered in ctx._root_lower:  # noqa: SLF001 - 同包内协作
            if lowered.startswith("readme") and raw not in candidates:
                candidates.append(raw)
    except Exception:  # noqa: BLE001 - 取不到候选就退回首个
        pass

    def _is_placeholder(rel: str) -> bool:
        text = ctx.text(rel)
        if text is None:
            return False
        low = text.lower()
        markers = ("xxxx", "readme_xxx", "your project name")
        hits = sum(1 for m in markers if m in low)
        return hits >= 2 and text.count("\n") < 40

    # 主 README（README.md）优先
    for rel in candidates:
        if rel.lower() in ("readme.md", "readme.markdown", "readme.rst", "readme.txt"):
            return rel
    # 其次取第一个非占位的
    for rel in candidates:
        if not _is_placeholder(rel):
            return rel
    return primary


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
    """从 pyproject.toml / package.json / Cargo.toml 读许可证声明。

    返回 (声明值, 清单文件名)。**清单文件名在「文件存在但没写 license 字段」时
    仍要如实返回** —— 2026-11-21 修订：原实现只在**读到值**时才返回文件名，
    值缺失一律返回 (None, "")，于是调用方无法区分两种情况：

      · 「本仓根本没有清单文件」   → 项目清单这个来源**不适用**
      · 「本仓有清单但没写 license」→ 项目清单这个来源**缺失**（真缺口）

    两种情况在原实现里被压成同一个空串，导致判据把前者也报成缺失 ——
    实测 139 仓里 57 个单文件项目被误判。现在文件名与值分开返回，
    调用方可分别处置。
    """
    # 清单文件存在但没写 license 字段时，返回该文件名 + None 值。
    if "pyproject.toml" in ctx.file_set:
        value = _pyproject_license(ctx)
        if value:
            return value, "pyproject.toml"
        return None, "pyproject.toml"
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
            return None, "package.json"
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
            return None, "Cargo.toml"
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
            # 2026-11-21 补：PEP 621 推荐写法 ``license = {file = "LICENSE"}``。
            # 实测 3dworld / an-engine / dwarf-scrolls / mcclone3d 四仓都用这种
            # 形式声明许可证，原判据不认，报「缺少声明来源：pyproject.toml」——
            # 是判据漏识别，不是仓库缺声明。
            # ``file`` 形态没有字面许可证类型，但它明确指向 LICENSE 文件，
            # 与 LICENSE 文件来源一致 ⇒ 视为已声明（取 LICENSE 文件的识别结果）。
            if raw.get("file"):
                # 直接取该仓 LICENSE 文件的识别结果，保证与其他来源同族，
                # 避免「见 LICENSE 文件」与「MIT」被误判成两族冲突。
                lic_rel = _license_rel(ctx)
                if lic_rel:
                    lic_text = ctx.text(lic_rel)
                    if lic_text:
                        found = identify_license(lic_text)
                        if found:
                            return found
                return "见 LICENSE 文件"
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
    """README 里 License 章节标题后出现的**项目自身**许可声明。

    2026-11-21 修订（原实现：标题后 500 字符内取首个 SPDX 关键词）：
      · 原实现有两个缺陷，实测在发布区 139 仓上造成 3 条**假阳性的「声明不一致」**：
        ① 窗口内抓到的是**第三方依赖的许可证**（localplayer 的 hls.js=Apache-2.0、
           novel-down 提及 AGPL-3.0-or-later、private-radio-stations 的 vendor 目录 GPL-2.0），
           而三个仓自身的 LICENSE 文件与许可章节都写着 MIT；
        ② 500 字符窗口是硬编码的物理长度，与章节实际长度无关 —— 章节稍长就把
           声明挤出窗口，判据从「不误报」退化成「漏报」。
      · 改为：只取窗口内**第一段**（遇空行/新标题即止），且该段内若含第三方/
        vendor/兼容性语汇（第三方依赖、vendor、以太坊、GPL、兼容、参照…）则**不取**，
        交由 LICENSE 文件与项目清单两侧判据裁决。
      · 这不是放宽判据而是修正判据：项目自身声明 MIT 而第三方依赖是 Apache，
        本来就**不矛盾**，原实现把两者混为一谈。
    """
    rel = _readme_rel(ctx)
    if rel is None:
        return None
    text = ctx.text(rel)
    if text is None:
        return None
    # 2026-11-01 @SIWPAN：允许编号章节标题（如「## 11. 许可」）——上游 website README 实证踩中
    # 2026-11-21 补：标题正则不能用 `\b` 收尾。
    # 实测 board-replay 的「## 许可证」匹配不上 —— 中文「可」与「证」之间
    # 没有 \b 边界（\b 只在 \w 与非 \w 之间成立，中文虽属 \w 但相邻两字不算边界）。
    # 改成 `(?:...)(?![a-z0-9])`：英文明示词后不接字母数字，中文标题则直接放行。
    match = re.search(
        r"^#{1,6}\s*(?:\d+[.、)．]*\s*)?(?:license|licence|许可|协议)(?![a-z0-9]).*$",
        text, re.I | re.M)
    if not match:
        return None
    # 只取标题后的第一段：遇空行或下一个标题即止。
    tail = text[match.end():]
    para_lines: list[str] = []
    for line in tail.splitlines():
        stripped = line.strip()
        if not stripped:
            if para_lines:
                break  # 第一段结束
            continue
        if stripped.startswith("#"):
            break  # 下一节开始
        para_lines.append(stripped)
    segment = "\n".join(para_lines)
    if not segment:
        return None
    # 先在本段**第一行**找 SPDX：典型写法「MIT（见 LICENSE）。依赖的 X 为 MIT…」
    # —— 自身声明在句首，第三方说明在句尾。原实现把整段丢给「第三方语汇」
    # 排除规则，导致 niulai 这类仓明明首句声明了 MIT 却被判缺。
    first = para_lines[0] if para_lines else ""
    own = _keyword_spdx(first)
    if own:
        return own

    # 第一段里出现第三方 / vendor / 兼容性语汇 ⇒ 这段讲的不是「本仓自身许可」，不取。
    # 2026-11-21 补：还要排除「讲**内容/他人**许可」的语汇 —— 实测 sfx-download 的
    # `## 许可` 章节说的是"所下载音频的版权归各源网站及原作者所有，请遵守对应许可
    # （CC BY 需署名、CC0 可自由使用）"，这里 CC0 是**被下载音频**的许可，
    # 与本仓 LICENSE=MIT-0 并不矛盾。原实现把它当成本仓声明 ⇒ 假阳性「声明不一致」。
    if re.search(
        r"第三方|vendor|依赖|兼容|不兼容|以 ?太 ?坊|GPL|AGPL|LGPL|referenc|upstream|上游"
        r"|版权归|原作者|所下载|被下载|源网站|下载内容|内容的许可|本程序下载",
        segment, re.I,
    ):
        return None
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


def _readme_license_line(ctx: "ProjectContext") -> str | None:
    """README **行首引用块**里的许可声明（模板化 README 的常见形态）。

    2026-11-21 新增。实测：发布区大量 README 由统一模板生成，许可声明放在
    标题下的引用块里而非独立章节 ——

        > 仓库：<https://gitee.com/siwpan/darksouls> ｜ 许可：MIT-0（MIT No Attribution）（见 [LICENSE](LICENSE)）

    旧判据只认 `## 许可` 章节标题 ⇒ 这类 README 一律被判「缺 README 声明来源」，
    实测在 139 仓上造成 18 仓假阴性（声明明明在，却报缺失）。
    """
    rel = _readme_rel(ctx)
    if rel is None:
        return None
    text = ctx.text(rel)
    if text is None:
        return None
    # 只看声明行：① 引用块行（'>' 开头）；② 「仓库：<url> ｜ 许可：X」形态。
    # 实测 peasy-ai 第 25 行是**不带 '>' 的正文行**，同样由统一模板生成，
    # 旧实现只认 '>' 开头 ⇒ 漏判。
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(">"):
            if not re.match(r"^(?:仓库|repo|repository)\s*[:：]", stripped, re.I):
                continue
        if not re.search(r"许可|licen[cs]e", stripped, re.I):
            continue
        # 同样排除第三方/vendor 语境（见 _readme_license_section 的同款理由）。
        if re.search(
            r"第三方|vendor|依赖|兼容|不兼容|以 ?太 ?坊|GPL|AGPL|LGPL|upstream|上游",
            stripped, re.I,
        ):
            continue
        found = _keyword_spdx(stripped)
        if found:
            return found
    return None


def _check_license_consistency(ctx: "ProjectContext") -> str | CheckResult:
    """规则 10：LICENSE 文件 / README 声明 / 项目清单声明是否一致。

    2026-11-21 修订判据形态（原实现要求「三处齐全，缺一即 error」）：

      原形态在发布区 139 仓上产出 **128 条 error**，逐条核实后分两类：
        · 96 仓根本没有任何项目清单（单文件 Python 项目，无 pyproject/package.json）
          —— 要求「清单必须声明许可证」对这类项目**不成立**，是判据越界；
        · 20 仓清单存在但未写 license 字段 —— 这是**真缺口**，可批量补；
        · 12 仓 README 已有声明但判据没认出来（模板化行首声明 / 章节措辞不同）
          —— 判据过严。

      新形态：**至少两处声明一致即通过**（LICENSE 文件 + README/清单任一）。
      理由：本仓铁律是「仓库有 LICENSE 文件即受控」，README 与清单是**冗余复核**，
      不是必备双签。要求三处齐全会把「没写清单」与「许可证真冲突」混为一谈 ——
      后者必须拦（仓库许可可能与声明不符），前者只是缺冗余。
      真冲突（两处及以上声明互相矛盾）仍判 error，不放宽。
    """
    license_rel = _license_rel(ctx)
    if license_rel is None:
        return CheckResult.skip("no-license-file")

    text = ctx.text(license_rel)
    from_file = identify_license(text) if text else None
    from_readme = _readme_license_section(ctx) or _readme_license_line(ctx)
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

    # 只有 LICENSE 文件一处声明 ⇒ 无法交叉复核，但许可证本身已受控。
    # 2026-11-21：此处**不判 error**（原判据要求三处齐全，对 96 个无清单的
    # 单文件项目不成立）。冗余缺失降级为 warn，真正的冲突仍在上方判 error。
    if len(present) == 1:
        return CheckResult.bad(
            f"仅 {next(iter(present))} 一处声明许可证，缺冗余复核（README 或项目清单）",
            Severity.WARN)

    # 2026-11-21 再修订：**清单文件本身不存在**时，「项目清单」这个来源是
    # 「不适用」而非「缺失」。实测 139 仓里 57 仓是单文件/无清单项目
    # （无 pyproject.toml / package.json / Cargo.toml）—— 对它们要求
    # 「清单必须声明许可证」不成立，判据越界。
    # manifest_rel 为空串或 None 都表示「本仓没有清单文件」。
    missing = []
    for k, v in sources.items():
        if v:
            continue
        if k == "项目清单" and not manifest_rel:
            continue  # 本仓无清单文件 ⇒ 该来源不适用，不算缺失
        missing.append(k)
    if missing:
        return CheckResult.bad("缺少声明来源：" + "、".join(missing))
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 11-12：README
# ---------------------------------------------------------------------------

#: README 应覆盖的三类语义（中英文关键词任一命中即可）。
#:
#: 2026-11-21 扩充等价措辞：实测发布区大量 README 由统一模板生成，三类信息
#: **都在**，但标题措辞与原关键词表不同：
#:   · 「## 运行方式与依赖」= 安装 + 用法（原表只认「安装/快速开始/usage」，
#:     漏判 ⇒ 27 仓被误报「缺用法/示例」）；
#:   · 「## 测试状态」「## 目录要点」等模板段不影响本判据。
#: 扩充的是**同义措辞**（语义等价），不是放宽 —— 真正缺内容的仓仍会报。
_README_SECTIONS: tuple[tuple[str, str], ...] = (
    ("安装/快速开始",
     r"install|installation|安装|快速开始|getting started|quick ?start|"
     r"运行方式|运行方法|运行|启动|运行要求|依赖与运行"),
    ("用法/示例",
     r"usage|example|用法|使用|示例|运行方式|运行方法|运行|操作说明|"
     r"功能说明|使用说明|玩法|使用方式|快速上手|秒上手|常用命令|"
     r"快速开始|上手|启动|命令|cli|api| tutorial"),
    ("许可",
     r"licen[cs]e|许可|协议|授权"),
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
