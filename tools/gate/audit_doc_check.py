#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计/报告类文档的错漏自动检查器（2026-11-10 深度审计配套件）。

背景：allin 仓的治理体系对**代码**有 20 道门禁 + 30 条 repocheck 规则，对**文档**
有 D1–D17 索引契约。但有一类文档此前**零机检覆盖**：审计报告 / 复评报告 / 走查清单
这类「结论型文档」。它们的典型失效模式是：

  E1 证据锚点失效   —— 报告写 `file.py:123`，但该行已被改动或该行内容与报告描述不符；
  E2 章节结构缺失   —— 报告缺「审计范围」「问题清单」「来源」「疑点」等必备章节；
  E3 严重度乱序     —— 问题清单未按严重程度排序，或同档内顺序混乱；
  E4 无源推测混入   —— 结论段落没有 file:line 锚点也没有来源标记（= 推测）；
  E5 来源不可核查   —— 引用了来源但没给 URL；
  E6 数量口径矛盾   —— 同一事实在文中出现互相矛盾的数字（如门禁 19 与 20 并存）；
  E7 疑点被当结论   —— 「待验证」段落里的条目被写进「已确认问题清单」。

本脚本把上述可机检的部分变成提交即红。**判定口径刻意收窄**：
只核「机器能确定」的事，不核「措辞好不好」——后者留给人工评审。

用法：
  python tools/gate/audit_doc_check.py <文档.md> [<文档2.md> ...]
  python tools/gate/audit_doc_check.py --selfcheck
  python tools/gate/audit_doc_check.py --list-all

历史基线：上线日之前已有的历史文档欠账登记在 audit_doc_baseline.json（按文档+判据
给数量配额）。基线内输出 BASE 不计门禁；超出配额或未登记文档的任何违例输出 FAIL。
退出码按**新增违例**判定：0 无新增违例；1 有新增违例；2 用法错；3 环境错。
零三方依赖（仅标准库）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # tools/gate/ → 仓根

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2
EXIT_ENV = 3

# ── 文档类型识别（决定哪些判据适用）────────────────────────────────────────
# docs/记录/审计/ 下不全是「审计报告」：还有清单、盘点、台账、取证记录、汇编。
# 对这些文档要求「审计范围 / 问题清单 / 来源 / 疑点 / 处置建议」五章是误报
# —— 清单类文档天然没有「处置建议」。
#
# 判据：**标题或正文首段同时出现「审计/深度审核/复评」类信号** 才视为审计报告，
# 只在审计报告上启用 E2/E3/E4/E6/E7；其余文档仍跑 E1（证据锚点核对）——
# 因为任何文档引用了不存在的代码行都是错。
AUDIT_REPORT_TITLE_RE = re.compile(
    r"(深度审计|审计报告|深度审核|审核报告|复评报告|整改复评|安全评估|代码审计|"
    r"审计结果|走查报告|核查报告)"
)
# 明确不是审计报告的标题信号（清单 / 台账 / 索引 / 取证流水）
NON_AUDIT_TITLE_RE = re.compile(
    r"(清单|台账|索引|目录|汇总|汇编|取证记录|流水|记账|一览|备忘|说明)"
)


def is_audit_report(doc: Path, text: str) -> bool:
    """判定该文档是否属于「审计报告」类（决定 E2–E7 是否适用）。"""
    head = "\n".join(text.splitlines()[:30])
    title_line = next((ln for ln in text.splitlines() if ln.lstrip().startswith("#")), "")
    title = title_line.lstrip("#").strip()
    if NON_AUDIT_TITLE_RE.search(title):
        return False
    if AUDIT_REPORT_TITLE_RE.search(title):
        return True
    # 标题无信号时看正文首段：同时出现「问题清单」与「处置建议」也算审计报告
    return bool(re.search(r"(问题清单|问题列表)", head) and re.search(r"(处置建议|整改建议|处置计划)", head))


def is_cross_repo_doc(doc: Path, text: str) -> bool:
    """判定该文档是否盘点**其他仓库**的文件。

    这类文档（如「硬编码路径盘点」）的锚点指向外部仓，本仓内必然找不到。
    判定信号：标题含「盘点 / 清单 / 修复计划」等跨仓语义。
    命中时：**仓内找不到的锚点一律跳过**（无论有无目录前缀）—— 无从判定它属于
    哪个外部仓，猜错比不猜更危险；仓内确实存在的锚点仍照常校验行号。
    这样无需逐个维护外部仓名白名单（会随仓库演进腐烂、挂一漏万）。
    """
    title_line = next((ln for ln in text.splitlines() if ln.lstrip().startswith("#")), "")
    title = title_line.lstrip("#").strip()
    return bool(re.search(r"(盘点|清单|修复计划|逐项结论)", title))


# ── 章节必备性（E2）──────────────────────────────────────────────────────────
# 报告类文档必须有的章节（按「别名」匹配，命中任一别名即算存在）
REQUIRED_SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("审计范围", ("审计范围", "范围与依据", "审计范围与依据")),
    ("问题清单", ("问题清单", "问题列表", "发现清单", "风险清单")),
    ("来源", ("来源", "联网检索", "参考来源", "检索来源", "来源清单")),
    ("疑点", ("待验证", "疑点", "未确认", "待核实")),
    ("处置建议", ("处置建议", "建议", "整改建议", "处置计划", "优先级")),
]

# ── 证据锚点（E1）────────────────────────────────────────────────────────────
# 形如 `path/to/file.ext:123` 或 `path/to/file.ext:12-34`。
# 反引号包裹是首选写法，但**裸锚点同样要核** —— 报告里写成裸 `file.py:123`
# 时若漏检，等于给「锚点可以随便写」开了口子。故此处允许有/无反引号两种形态。
ANCHOR_RE = re.compile(
    r"[`]?([A-Za-z0-9_./\\\-一-鿿]+"
    r"\.(?:py|js|mjs|ts|json|ya?ml|md|txt|sh|ps1|toml|ini|cfg|html|css|svg|bat))"
    r":(\d+)(?:-(\d+))?[`]?"
)

# 允许不校验的路径前缀（第三方 / 构建产物 / 仓外）
SKIP_PREFIXES = (
    "vendor/", "node_modules/", "build/", "dist/", ".venv/",
    "site-packages/", "http://", "https://",
)
# 兼容表：非跨仓文档里偶尔也会直接引用这些外部仓根，命中前缀时不判「文件不存在」。
# 跨仓盘点文档已按文档类型整体豁免（见 check_anchors），不依赖这张表；本表只是
# 让「普通报告里提到 3dworld/foo.py:12」不至于变成噪声。
CROSS_REPO_PREFIXES = (
    "remix/", "musickit/", "bridge/", "3dworld/", "mirsolo/", "allin_engine/",
    "alloy/", "webcopier/", "RolePlayer/", "lab/", "moba_battle_platform/",
    "private-radio-stations/", "ncmturnmp3/", "cordis-table-app/",
    "deepseek-harness/", "dict-scene-engine/", "players-unified/",
)

# ── 严重度排序（E3）──────────────────────────────────────────────────────────
SEVERITY_ORDER = [
    ("严重", "critical", "p0", "s1", "🔴"),
    ("高", "high", "p1", "s2", "🟠"),
    ("中", "medium", "p2", "s3", "🟡"),
    ("低", "low", "p3", "s4", "🔵"),
]
# 优先级标记与严重度的映射：P0 最重、P3 最轻。处置建议段常用 P0/P1 表述，
# 若不参与排序会被误判为「排序倒置」。此处把 P 序列接到严重度序列尾部。
PRIORITY_RANK = {"p0": 0, "p1": 1, "p2": 2, "p3": 3}
# 章节标题里的严重度标记
SEVERITY_HEAD_RE = re.compile(
    r"^\s*(?:#{2,4}\s*)?(?:\[[^\]]{0,20}\]|"
    r"(?:严重|高|中|低|Severity)\s*[:：]?)?\s*"
    r"(?:🔴|🟠|🟡|🔵)?\s*"
    r"((?:\[?(?:P0|P1|P2|P3|S-?\d+|H-\d+|M-\d+|L-\d+)\]?)|"
    r"(?:严重|高|中|低))\s*",
    re.MULTILINE,
)

# ── 无源推测（E4 / E5）───────────────────────────────────────────────────────
# 结论性表述：若该行既无 file:line 锚点、也无来源引用，则视为无源结论
CONCLUSION_RE = re.compile(
    r"(导致|造成|构成|意味着|等同于|可以|能够|必然|一定会|证实|确认存在|存在漏洞|属于.{0,6}漏洞)"
)
SOURCE_MARK_RE = re.compile(
    r"(https?://|OWASP|CWE-\d+|CWE\s|Node\.js|Bandit|MITRE|CVE-\d+|实测|已复核|已确认)"
)
# 显式把结论降级为疑点的标记：出现即说明作者**主动**标注了不确定性，
# 属正确处理方式，不应再被 E4/E7 重复报警。
DEFERRED_MARK_RE = re.compile(
    r"(列为待验证疑点|见疑点|详见疑点|待验证疑点\s*V-\d+|疑点\s*V-\d+)"
)

# ── 疑点标记（E7）────────────────────────────────────────────────────────────
# 「已确认」区段内出现这些词 = 疑点被当成结论
DOUBT_MARK_RE = re.compile(
    r"(需人工确认|待验证|待确认|尚未验证|未验证|需确认|可能|疑似|预计|推测|无法确认)"
)

# ── 数量口径矛盾（E6）────────────────────────────────────────────────────────
# 抽取「<数字> <量词> <名词>」，检测同一名词出现互相矛盾的数字。
# 名词须有实质含义（≥2 个中文字符），且排除「entry / item / 条目」这类泛词 ——
# 泛词在不同语境下指代不同对象，比对它们只会产出假阳性。
COUNT_RE = re.compile(r"(\d+)\s*(道|条|个|份|项|次|行|字节)")
COUNT_CONTEXT_RE = re.compile(r"(\d+)\s*(道|条|个|份|项|次|行|字节)\s*([\u4e00-\u9fa5]{2,12})")
# 泛词黑名单：这些名词在不同语境下指代不同对象，比对无意义
VAGUE_NOUNS = {
    "条目", "项目文件", "文件内容", "内容片段", "条目集合",
}


class Finding:
    __slots__ = ("code", "where", "message", "detail")

    def __init__(self, code: str, where: str, message: str, detail: str = "") -> None:
        self.code = code
        self.where = where
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict:
        return {"code": self.code, "where": self.where, "message": self.message, "detail": self.detail}

    def __str__(self) -> str:
        base = f"[{self.code}] {self.where}: {self.message}"
        return f"{base}\n      {self.detail}" if self.detail else base


def u8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ── 历史欠账基线（2026-11-10 上线时建立）────────────────────────────────────
# 检查器上线时，docs/记录/审计/ 下已有 4 份历史报告不满足新判据（缺必备章节、
# 无源结论、简称歧义）。这些是**真实欠账**，不是误报，不该抹掉；但若让它们
# 直接把 `allin docs audit-check` 顶成常红，命令就失去门禁价值。
# ⇒ 按仓内既有 baseline 惯例登记配额：基线内输出 BASE 不计门禁，新增违例判红。
BASELINE_FILE = ROOT / "tools" / "gate" / "audit_doc_baseline.json"


def load_baseline() -> dict[str, dict[str, int]]:
    """读取基线配额；文件缺失/损坏按「无基线」处理（从严，不静默放行）。"""
    if not BASELINE_FILE.is_file():
        return {}
    try:
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        quota = data.get("quota", {})
        return {
            str(doc).replace("\\", "/"): {str(k): int(v) for k, v in caps.items()}
            for doc, caps in quota.items()
        }
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"警告：基线文件不可解析，本次按无基线从严判定（{exc}）", file=sys.stderr)
        return {}


def split_by_baseline(
    doc_rel: str, findings: list[Finding], quota: dict[str, dict[str, int]]
) -> tuple[list[Finding], list[Finding]]:
    """把某文档的违例分成 (基线内, 新增)。

    按「判据 + 数量」配额而非文本指纹：行号漂移、措辞微调都不会让基线失效，
    同时任何**多出来**的同类违例或新判据违例都会落到「新增」侧判红。
    """
    caps = quota.get(doc_rel, {})
    if not caps or not findings:
        return [], list(findings)
    used: dict[str, int] = {}
    base: list[Finding] = []
    new: list[Finding] = []
    for f in findings:
        n = used.get(f.code, 0)
        if n < caps.get(f.code, 0):
            used[f.code] = n + 1
            base.append(f)
        else:
            new.append(f)
    return base, new


# ── E1：证据锚点核对 ─────────────────────────────────────────────────────────
def _build_name_index() -> dict[str, list[str]]:
    """建立「文件名 → 仓内相对路径列表」索引，用于解析报告里的简称锚点。

    报告常写 `registry.js:62` 而非全路径 `platform/packages/core/src/registry.js:62`。
    若不做这一步，简称锚点会被误判成「文件不存在」——那是假阳性，会让检查器失去
    信用。规则：**同名候选唯一 ⇒ 采用；同名候选多个 ⇒ 不猜（留给 E1 报「歧义」）**。
    """
    index: dict[str, list[str]] = {}
    skip_dirs = {".git", "node_modules", ".venv", "__pycache__", "build", "dist", ".pytest_cache"}
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(ROOT).parts
        if any(part in skip_dirs for part in rel_parts):
            continue
        index.setdefault(p.name, []).append(p.relative_to(ROOT).as_posix())
    return index


_NAME_INDEX: dict[str, list[str]] | None = None


def _dedup_same_file(cands: list[str]) -> list[str]:
    """按真实路径去重，消除符号链接别名造成的「假歧义」。

    仓内 `docs/records` / `docs/facts` / `docs/spec` 是指向中文目录的 symlink，
    `rglob` 会把同一份文件收两次；不去重时 `交接/2026-11.md` 明明唯一却会
    被判成「同名文件有 4 个」，属工具假阳性。
    """
    seen: dict[str, str] = {}
    for c in cands:
        key = os.path.realpath(str(ROOT / c))
        seen.setdefault(key, c)
    return list(seen.values())


def _resolve_short_name(rel: str) -> tuple[str | None, str]:
    """把简称锚点解析成仓内相对路径。

    返回 (解析结果 | None, 说明)。解析结果为 None 表示**无法唯一确定**。
    """
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = _build_name_index()
    name = rel.rsplit("/", 1)[-1]
    cands = _dedup_same_file(_NAME_INDEX.get(name, []))
    if not cands:
        return None, f"仓内无同名文件（{name}）"
    if len(cands) == 1:
        return cands[0], f"简称 {name} → {cands[0]}"
    # 多候选：优先取与锚点目录前缀相符的
    if "/" in rel:
        prefix = rel.rsplit("/", 1)[0]
        exact = [c for c in cands if c.endswith("/" + rel)]
        if len(exact) == 1:
            return exact[0], f"简称 {rel} → {exact[0]}"
        suffix = [c for c in cands if c.startswith(prefix + "/")]
        if len(suffix) == 1:
            return suffix[0], f"简称 {rel} → {suffix[0]}"
    return None, f"同名文件有 {len(cands)} 个，无法唯一确定：{name}"


def check_anchors(doc: Path, text: str, findings: list[Finding]) -> None:
    """核对报告里每个 `file:line` 锚点：文件存在？行号在范围内？

    代码块（```）内的行**不参与判定** —— 那里的 `// index.js:1068` 是代码摘录的
    出处标注，不是报告自身的证据引用；对它判「文件不存在」是假阳性。
    跨仓盘点文档（is_cross_repo_doc）里仓内不存在的锚点按外部仓引用跳过，
    但仓内存在的锚点仍逐条核行号，不放过真错漏。
    """
    cross_repo = is_cross_repo_doc(doc, text)
    seen: set[tuple[str, int]] = set()
    in_code = False
    for raw_line in text.splitlines():
        if raw_line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = ANCHOR_RE.search(raw_line)
        if not m:
            continue
        rel = m.group(1).replace("\\", "/")
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        if rel.lower().startswith(SKIP_PREFIXES) or rel.startswith("/"):
            continue
        if rel.startswith(CROSS_REPO_PREFIXES):
            continue  # 跨仓盘点文档：指向外部仓的文件
        if cross_repo and "/" not in rel:
            continue  # 跨仓盘点文档的裸文件名锚点：无从判定归属，跳过
        if (rel, start) in seen:
            continue
        seen.add((rel, start))
        target = ROOT / rel
        if not target.is_file():
            # 简称解析：文件名唯一时可定位到真实路径
            resolved, note = _resolve_short_name(rel)
            if resolved is None:
                if cross_repo:
                    # 跨仓盘点文档（如「硬编码路径盘点 / 修复计划」）盘点的就是
                    # 其他仓库的文件，带目录前缀的锚点天然不在本仓；逐个维护
                    # 外部仓名白名单既挂一漏万又会随仓库演进腐烂，这里按文档
                    # 类型整体豁免「仓内找不到」这一类，仍保留对**仓内存在**的
                    # 锚点做行号校验（下方逻辑不变）。
                    continue
                findings.append(Finding(
                    "E1", f"{doc.name}",
                    f"证据锚点无法定位：{rel}:{start}（{note}）",
                    "报告引用了不存在的文件 —— 可能是路径写错、文件已删或已移动。",
                ))
                continue
            rel = resolved
            target = ROOT / rel
        try:
            lines = read_text(target).splitlines()
        except OSError as exc:
            findings.append(Finding(
                "E1", f"{doc.name}",
                f"证据锚点文件不可读：{rel}（{exc.__class__.__name__}）",
                "",
            ))
            continue
        if start > len(lines):
            findings.append(Finding(
                "E1", f"{doc.name}",
                f"证据锚点行号越界：{rel}:{start}（文件只有 {len(lines)} 行）",
                "行号与当前代码不符 —— 代码改动后报告未同步。",
            ))
            continue
        if end > len(lines):
            findings.append(Finding(
                "E1", f"{doc.name}",
                f"证据锚点行号区间越界：{rel}:{start}-{end}（文件只有 {len(lines)} 行）",
                "",
            ))
    return


# ── E2：必备章节 ────────────────────────────────────────────────────────────
def check_sections(doc: Path, text: str, findings: list[Finding]) -> None:
    heads = [ln.strip() for ln in text.splitlines() if ln.lstrip().startswith("#")]
    joined = "\n".join(heads)
    for label, aliases in REQUIRED_SECTIONS:
        if not any(a in joined for a in aliases):
            findings.append(Finding(
                "E2", f"{doc.name}",
                f"缺必备章节：{label}",
                "报告类文档须覆盖：审计范围 / 问题清单 / 来源 / 疑点 / 处置建议。",
            ))


# ── E3：严重度排序 ──────────────────────────────────────────────────────────
def check_severity_order(doc: Path, text: str, findings: list[Finding]) -> None:
    """问题清单段内，严重度标记必须按 严重→高→中→低 升序。

    判定只在**同一章节内**进行：跨章节（如「问题清单」末尾的 P0 处置建议）
    不构成排序倒置 —— 不同章节可以有各自的编号体系。
    """
    lines = text.splitlines()
    cur_section = ""
    seq: list[tuple[int, str, int]] = []  # (rank, 标记, 行号)
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            cur_section = s.lstrip("#").strip()
            seq = []  # 换章节即重置
            continue
        if not s or s.startswith("|") or s.startswith(">"):
            continue
        m = SEVERITY_HEAD_RE.match(s)
        if not m:
            continue
        token = m.group(1).strip().strip("[]").lower()
        rank = -1
        for idx2, (zh, en, p, s_alias, emoji) in enumerate(SEVERITY_ORDER):
            if token in (zh, en, p, s_alias, emoji):
                rank = idx2
                break
        if rank < 0 and token in PRIORITY_RANK:
            rank = PRIORITY_RANK[token]
        if rank >= 0:
            seq.append((rank, m.group(0).strip(), idx))
    for i in range(1, len(seq)):
        if seq[i][0] < seq[i - 1][0]:
            findings.append(Finding(
                "E3", f"{doc.name}:{seq[i][2]}",
                f"「{cur_section}」段内问题清单未按严重程度排序（升序应为 严重→高→中→低）",
                f"第 {seq[i - 1][2]} 行的「{seq[i - 1][1]}」之后出现更低的「{seq[i][1]}」。",
            ))
            break  # 只报首个，避免刷屏


# ── E4/E5：无源结论 ─────────────────────────────────────────────────────────
def check_unsourced_claims(doc: Path, text: str, findings: list[Finding]) -> None:
    """结论性表述必须带 file:line 锚点或来源标记，否则判为无源推测。"""
    in_code = False
    hits = 0
    for idx, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            continue
        if s.startswith("|") or s.startswith(">"):
            continue  # 表格与引用块按人读，不逐行判
        if not CONCLUSION_RE.search(s):
            continue
        if ANCHOR_RE.search(s) or SOURCE_MARK_RE.search(s):
            continue
        if DEFERRED_MARK_RE.search(s):
            continue  # 已显式降级为疑点，不算无源结论
        hits += 1
        if hits <= 3:
            findings.append(Finding(
                "E4", f"{doc.name}:{idx}",
                "结论性表述缺证据锚点与来源标记（疑似无源推测）",
                s[:160],
            ))
    if hits > 3:
        findings.append(Finding(
            "E4", f"{doc.name}",
            f"共 {hits} 行结论性表述缺证据锚点与来源标记（此处只列前 3 行）",
            "",
        ))


# ── E6：数量口径矛盾 ────────────────────────────────────────────────────────
def check_count_consistency(doc: Path, text: str, findings: list[Finding]) -> None:
    """同一量词+名词组合出现不同数值 → 口径矛盾。"""
    buckets: dict[tuple[str, str], set[int]] = {}
    for m in COUNT_CONTEXT_RE.finditer(text):
        num = int(m.group(1))
        unit = m.group(2)
        noun = m.group(3).strip()
        if not noun or noun in VAGUE_NOUNS:
            continue
        key = (unit, noun)
        buckets.setdefault(key, set()).add(num)
    for (unit, noun), nums in buckets.items():
        if len(nums) > 1:
            findings.append(Finding(
                "E6", f"{doc.name}",
                f"同一事实「{noun}」出现矛盾数值：{sorted(nums)}（单位：{unit}）",
                "同一事实在文中有多个取值 —— 至少有一个是陈旧口径。",
            ))


# ── E7：疑点被当结论 ────────────────────────────────────────────────────────
def check_doubt_in_conclusions(doc: Path, text: str, findings: list[Finding]) -> None:
    """「已确认问题清单」段内不得含疑点措辞。"""
    lines = text.splitlines()
    in_confirmed = False
    for idx, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            low = s.lower()
            if "疑点" in s or "待验证" in s or "待确认" in s or "未确认" in s:
                in_confirmed = False
            elif ("问题清单" in s or "已确认" in s or "问题" in s and "确认" in s):
                in_confirmed = True
            continue
        if not in_confirmed:
            continue
        if s.startswith("|") or not s:
            continue
        if DEFERRED_MARK_RE.search(s):
            continue  # 已显式标注为疑点并指向疑点条目 —— 属正确处理
        if DOUBT_MARK_RE.search(s):
            findings.append(Finding(
                "E7", f"{doc.name}:{idx}",
                "「已确认」区段内出现疑点措辞 —— 疑点被当成了结论",
                s[:160],
            ))


# ── 汇总执行 ────────────────────────────────────────────────────────────────
# E1 对所有文档生效（任何文档引用了不存在的代码行都是错）；
# E2–E7 只对「审计报告」类文档生效（清单/台账类文档天然没有这些章节）。
ALWAYS_CHECKS = ("E1",)
AUDIT_ONLY_CHECKS = ("E2", "E3", "E4", "E6", "E7")

CHECKS = {
    "E1": check_anchors,
    "E2": check_sections,
    "E3": check_severity_order,
    "E4": check_unsourced_claims,
    "E6": check_count_consistency,
    "E7": check_doubt_in_conclusions,
}


def check_document(doc: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = read_text(doc)
    except OSError as exc:
        return [Finding("ENV", str(doc), f"文档不可读：{exc.__class__.__name__}: {exc}")]
    audit = is_audit_report(doc, text)
    for code in ALWAYS_CHECKS + AUDIT_ONLY_CHECKS:
        if code in AUDIT_ONLY_CHECKS and not audit:
            continue
        CHECKS[code](doc, text, findings)
    return findings


# ── 自检：造一份「有病」的样例，验证每条判据真的会红 ──────────────────────
def selfcheck() -> int:
    import tempfile

    cases: list[tuple[str, str, str]] = [
        ("E1-锚点文件不存在", "E1", "`tools/gate/__no_such_file__.py:10`\n"),
        ("E1-行号越界", "E1", "`allin_cli.py:999999`\n"),
        ("E2-缺必备章节", "E2", "# 深度审计报告（自检样例）\n## 无关键章节\n"),
        ("E4-无源结论", "E4", "这会导致严重的权限提升问题。\n"),
        ("E7-疑点混入结论", "E7", "## 已确认问题清单\n该项疑似存在漏洞，需人工确认。\n"),
    ]
    ok = True
    for name, expect_code, snippet in cases:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.md"
            body = snippet
            if expect_code != "E2":
                # 补齐其余必备章节，避免 E2 干扰本条判定。
                # 标题须带审计报告信号，否则会被分类器判为「非审计报告」而跳过 E2–E7。
                body = (
                    "# 深度审计报告（自检样例）\n"
                    "## 审计范围\n## 问题清单\n## 来源\n## 疑点\n## 处置建议\n" + snippet
                )
            p.write_text(body, encoding="utf-8")
            found = check_document(p)
            codes = {f.code for f in found}
            hit = expect_code in codes
            print(f"  {'OK  ' if hit else 'FAIL'} {name}: 期望 {expect_code}，实得 {sorted(codes)}")
            if not hit:
                ok = False
    # 反向：干净文档不应报 E1/E2/E7
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "clean.md"
        clean_body = (
            "# 深度审计报告（自检样例）\n"
            "## 审计范围\n覆盖 tools/gate。\n## 问题清单\n"
            "### [高] 示例\n- 位置: allin_cli.py:1\n- 依据: OWASP 实测确认\n"
            "## 来源\nhttps://owasp.org/\n## 疑点\n无。\n## 处置建议\n修复。\n"
        )
        p.write_text(clean_body, encoding="utf-8")
        found = check_document(p)
        bad = [f for f in found if f.code in ("E1", "E2", "E7")]
        print(f"  {'OK  ' if not bad else 'FAIL'} 干净文档无误报: 实得 {[f.code for f in bad]}")
        if bad:
            ok = False
    # 反向：清单/台账类文档**不是**审计报告，不得被 E2–E7 误报
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "list.md"
        list_body = (
            "# 项目清单核实与分类\n"
            "本卷记录各仓归属。\n\n"
            "- 仓 A：1 个\n- 仓 B：2 个\n"
        )
        p.write_text(list_body, encoding="utf-8")
        found = check_document(p)
        bad = [f for f in found if f.code in ("E2", "E3", "E4", "E6", "E7")]
        print(f"  {'OK  ' if not bad else 'FAIL'} 清单类文档不误报: 实得 {[f.code for f in bad]}")
        if bad:
            ok = False
    # 基线分流（2026-11-10）：配额内不计门禁，超额 / 未登记文档必须判红
    fake = [
        Finding("E2", "t.md", "缺必备章节：审计范围"),
        Finding("E2", "t.md", "缺必备章节：来源"),
    ]
    q = {"docs/记录/审计/x.md": {"E2": 2}}
    base, new = split_by_baseline("docs/记录/审计/x.md", fake, q)
    hit = len(base) == 2 and not new
    print(f"  {'OK  ' if hit else 'FAIL'} 基线配额内不判红: base={len(base)} new={len(new)}")
    if not hit:
        ok = False
    base, new = split_by_baseline("docs/记录/审计/x.md", fake, {"docs/记录/审计/x.md": {"E2": 1}})
    hit = len(base) == 1 and len(new) == 1
    print(f"  {'OK  ' if hit else 'FAIL'} 基线超额部分判红: base={len(base)} new={len(new)}")
    if not hit:
        ok = False
    base, new = split_by_baseline("docs/记录/审计/y.md", fake, q)
    hit = not base and len(new) == 2
    print(f"  {'OK  ' if hit else 'FAIL'} 未登记文档全部判红: base={len(base)} new={len(new)}")
    if not hit:
        ok = False
    hit = len(_dedup_same_file(["allin_cli.py", "allin_cli.py"])) == 1
    print(f"  {'OK  ' if hit else 'FAIL'} 符号链接别名按真实路径去重")
    if not hit:
        ok = False
    return 0 if ok else 1


def list_all() -> int:
    """列出仓内所有受本检查器管辖的文档（docs/记录/审计/ 下的 md）。"""
    base = ROOT / "docs" / "记录" / "审计"
    if not base.is_dir():
        print(f"未找到目录：{base}", file=sys.stderr)
        return EXIT_ENV
    for p in sorted(base.glob("*.md")):
        print(p.relative_to(ROOT).as_posix())
    return EXIT_OK


def main(argv: list[str]) -> int:
    u8()
    ap = argparse.ArgumentParser(
        prog="audit_doc_check",
        description="审计/报告类文档的错漏自动检查器（E1 锚点 / E2 章节 / E3 排序 / E4 无源 / E6 口径 / E7 疑点；历史欠账走 baseline 不计门禁）",
    )
    ap.add_argument("docs", nargs="*", help="要检查的文档路径（相对仓根或绝对路径）")
    ap.add_argument("--selfcheck", action="store_true", help="跑内置自检，验证每条判据真的会红")
    ap.add_argument("--list-all", action="store_true", help="列出受管辖的全部文档")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args(argv)

    if args.selfcheck:
        print("audit_doc_check 自检：")
        rc = selfcheck()
        print("自检结果：", "PASS" if rc == 0 else "FAIL")
        return rc if rc == 0 else EXIT_VIOLATION

    if args.list_all:
        return list_all()

    if not args.docs:
        ap.print_usage(sys.stderr)
        print("需至少一个文档路径，或用 --selfcheck / --list-all", file=sys.stderr)
        return EXIT_USAGE

    all_findings: list[tuple[Path, list[Finding]]] = []
    for raw in args.docs:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / raw
        if not p.is_file():
            print(f"文档不存在：{p}", file=sys.stderr)
            return EXIT_USAGE
        all_findings.append((p, check_document(p)))

    quota = load_baseline()
    split: list[tuple[str, list[Finding], list[Finding]]] = []
    for p, fs in all_findings:
        rel = p.relative_to(ROOT).as_posix() if str(p).startswith(str(ROOT)) else p.as_posix()
        base, new = split_by_baseline(rel, fs, quota)
        split.append((rel, base, new))
    new_total = sum(len(new) for _, _, new in split)
    base_total = sum(len(base) for _, base, _ in split)

    if args.json:
        payload = {
            "checked": [rel for rel, _, _ in split],
            "violations": new_total,
            "baseline": base_total,
            "findings": (
                [dict(f.as_dict(), document=rel, status="baseline") for rel, base, _ in split for f in base]
                + [dict(f.as_dict(), document=rel, status="new") for rel, _, new in split for f in new]
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_VIOLATION if new_total else EXIT_OK

    for rel, base, new in split:
        if not base and not new:
            if not args.quiet:
                print(f"OK   {rel}：无违例")
            continue
        if base:
            print(f"BASE {rel}：{len(base)} 条历史基线欠账（不计门禁）")
            if not args.quiet:
                for f in base:
                    print("  " + str(f))
        if new:
            print(f"FAIL {rel}：{len(new)} 条新增违例")
            for f in new:
                print("  " + str(f))

    print(f"\n合计：新增违例 {new_total} 条，历史基线 {base_total} 条。")
    if new_total:
        return EXIT_VIOLATION
    if not args.quiet:
        print("新增违例为 0，门禁通过。")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(EXIT_ENV)
