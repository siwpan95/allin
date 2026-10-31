#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs_contract.py —— 文档枢纽契约的**共享判据**（D9 / D10 / D11）。

为什么独立成模块
----------------
同一个 D 系列判据在本仓有**两个落点**，且必须各自自包含：

- `tools/gate/docs_index.py` —— 仓内 canonical（allin 仓自己跑）
- `tools/gate/governance/gates/g15_docs_contract.py` —— **分发版**落地（DSH 等采用方跑）

历史教训（`SPEC-004` 调试铁律 64 / `check_gate_drift.py` 存在的原因）：
"两份必须一致"只写在文档里 ⇒ 必然漂移；**两份都能跑、都"看着对"**，差异只有人工 diff 才看得见。
所以新判据**只写这一份**，两个入口都 import 它 —— **结构上杜绝漂移**，而不是靠记得同步。

本模块补的三处盲区（2026-11-01 实测，此前全靠人盯）
------------------------------------------------------
1. **D9 章节锚点**：全仓 `§N` 引用**没有任何判据校验**。
   `g19-docs-refs` 只解析**文件路径**、不查**章节锚点** ⇒ 章节序一改就留静默失效指针
   （2026-10-30 重写 `DESKTOP-KQABATS` 章节序时一次留下 **6 处**，隔一天才靠专项审计抓到）。
2. **D10 卷首区间**：D7 只校验卷首**有没有**声明覆盖区间，**不核区间与正文是否相符**
   ⇒ 本仓 10 月卷长期写「~ 2026-10-16」而正文已写到 10-31，**没有任何判据能发现**。
3. **D11 同一文档两处份数自述**：INDEX 头部「**覆盖** … 记录 N = **M 份**」由 D8 核，
   但 §四 标题里还有一份「记录（`记录/`，N 份）」的**旁证计数**，两者各漂各的
   （实测出现过 头部 54 / 标题 53）。D8 只看头部 ⇒ 漏。

判据形态说明（避免误报的设计取舍）
-----------------------------------
- **D9 的源范围＝规范/ + 事实源/ + 枢纽根件**，**不含 记录/**。
  记录是「只增不改、不作为约束」的历史证据，它引用的旧锚点**当时是对的**
  （实测：2026-09 卷引 `机器分区索引.md §7.1`，该节 10-30 改版后已移走 ⇒ 改历史才是错的，只能不判）。
  记录作为**目标**仍可被引用。
- **D9 只判「目标可定位」的引用**：形如 `[`X.md`](path) §N` / 裸 `X.md §N` / `SPEC-104 §N`。
  裸 `§N`（无目标，如 SPEC-001 里的「现有 §三十五~四十」）**无法判定目标 ⇒ 跳过并计数**，
  不猜、不拦 —— 猜错就是假红，而假红会让门禁被人关掉。
- 同一句里 `§4.2.6、§五、§六` 这类**连写**，后续 `§` 继承前一个目标（分隔符只允许连接符类）。
- 目标文件若**没有任何编号标题**（如 `## 铁律 5：…` 这种文字标题），**无法判定 ⇒ 跳过并计数**。
- 头部契约的**「引用格式」字段是格式声明**（例 `SPEC-102 §一`），不是活指针 ⇒ 跳过并计数。
- 章节号既认 `## 7.` / `### 112.1` 标题，也认交接卷常见的**粗体小节行** `**80.4 …**`
  （不认这一形态会把 80.4 判成失效 ⇒ 假红）。
- **D10 只核上界**：卷正文常引用更早的历史日期（下界必然被违反），故只校验
  「正文最新日期 ≤ 卷首声明的止」—— 这正是"区间没随正文续写"这个真实漏网的形态。
"""
from __future__ import annotations

import io
import os
import re

# ---------------------------------------------------------------- 基础设施
CN_CHARS = "零一二三四五六七八九十百"

#: 章节号：阿拉伯（可含小数）或中文序数
SECTION_TOKEN = re.compile(r"^([0-9]+(?:\.[0-9]+)*|[%s]+)" % CN_CHARS)
SECTION_REF = re.compile(r"§\s*([0-9]+(?:\.[0-9]+)*|[%s]+)" % CN_CHARS)

#: 指向性目标：**markdown 链接里的 .md**，或**反引号包裹的 .md 路径**。
#: ⚠ **刻意不含裸文件名** —— 裸文件名在「讨论某文档」的句子里出现得极多
#:   （`MEMORY.md` 661 行混装… / 一致性由门禁保证见 `INDEX.md`），
#:   实测会把这些"**被讨论对象**"误当成 § 的目标 ⇒ 假红（一次误判就足以让人把门禁关掉）。
TARGET_TOKEN = re.compile(r"(?:\]\(([^)\s]+\.md)(?:#[^)]*)?\)|`([^`\s]+\.md)`)")

#: 自引用标记：明确指向「本文件」——文件级；「本节」是节级，**不算**（它指当前小节）
SELF_MARK = re.compile(r"(本文件|本文|本卷)")

#: 目标与引用之间允许出现的「连接符类」字符（其余一律视为换目标 ⇒ 不继承）
#: 含 `|` / `｜` 与数字 —— INDEX 的表格行里，「覆盖区间」列的 `§N` 与「文件」列的链接之间
#:   隔着表格竖线**和日期**（`… | 2026-08-27 ~ 08-30（§一~§五十八） | …`），
#:   它们指的正是**同一份文件**（实测：INDEX 的 FACT-09~11、REC-HO-01~04 各行都属此类）。
#:   这类陈述真实漏网过：INDEX 的 REC-HO-03 行曾写「~ 10-08（§九十四~§一百零七）」，
#:   而该卷实际已含 §108/§109/§110 ⇒ 「覆盖区间自述」必须能机检。
GAP_OK = set(" \t~、，,；;。·（）()「」『』【】[]`*：:－-—|｜0123456789")

#: 粗体小节行：`**80.4 P2 归档完整性核对 …**`（交接卷的小节常用此形态而非标题）
BOLD_SECTION = re.compile(r"^\*\*([0-9]+(?:\.[0-9]+)*|[%s]+)(?=\s|[、，,．.])" % CN_CHARS)

#: D9 的**源**范围：规范（约束性，活）+ 事实源（活台账）+ 枢纽根件（INDEX/README）
#: **不含 记录/** —— 记录是「只增不改、不作为约束」的历史证据，它引用的是**当时正确**的旧锚点
#: （实测：2026-09 卷引 `机器分区索引.md §7.1`，而该节在 10-30 改版后已移到别处 ⇒
#:  改历史是错的，只能不判）。记录作为**目标**仍可被引用。
D9_SRC_PREFIXES = ("规范/", "事实源/")
D9_SRC_ROOT_FILES = ("INDEX.md", "README.md")

#: 头部契约里的「引用格式」字段是**引用格式声明**，不是活指针（例 `SPEC-102 §一`）⇒ 跳过
REF_FORMAT_FIELD = re.compile(r"\*\*引用格式\*\*")

DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")

#: INDEX 各节标题里的份数自述（分类目录名 → 标题里的目录写法）
COUNT_SECTIONS = (("规范", "规范"), ("事实源", "事实源"), ("记录", "记录"))


def read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def heading_tokens(path: str) -> set[str]:
    """文档的章节号集合。

    取两类行**开头**的编号或中文序数：
    1. `##`/`###`/`####` 标题 —— `## 7. 推送与远端镜像`、`### 112.1 …`、`## 一百一十二、…`
    2. **粗体小节行** —— 交接卷里小节常写成 `**80.4 P2 归档完整性核对 …**` 而非标题
       （实测：不认这一形态会把 80.4 判成失效指针 —— 假红）

    只认开头 —— `## 铁律 5：去符盘` 的编号在标题中间且带前缀文字，
    判据无法把它映射成一个章节号（这类目标一律跳过，见模块说明）。
    粗体行要求编号后紧跟分隔符（空白/标点），否则 `**137**` 这类数字会被误当节号。
    """
    out: set[str] = set()
    for line in read_text(path).splitlines():
        m = re.match(r"^#{2,4}\s+(.*)$", line)
        if m:
            t = SECTION_TOKEN.match(m.group(1).strip())
            if t:
                out.add(t.group(1))
            continue
        b = BOLD_SECTION.match(line)
        if b:
            out.add(b.group(1))
    return out


def resolve_path(docs: str, root: str, src_rel: str, cand: str) -> str | None:
    """把候选路径解析成真实文件：依次试「源文件所在目录 / docs 根 / 仓根」。"""
    cand = cand.split("#")[0].strip()
    if not cand or cand.startswith(("http://", "https://", "mailto:")):
        return None
    src_dir = os.path.dirname(os.path.join(docs, src_rel.replace("/", os.sep)))
    for base in (src_dir, docs, root):
        p = os.path.normpath(os.path.join(base, cand.replace("/", os.sep)))
        if os.path.isfile(p) and p.lower().endswith(".md"):
            return p
    return None


def resolve_spec(docs: str, spec_id: str) -> str | None:
    """`SPEC-104` → `规范/SPEC-104-<中文短名>.md`。"""
    spec_dir = os.path.join(docs, "规范")
    if not os.path.isdir(spec_dir):
        return None
    for fn in sorted(os.listdir(spec_dir)):
        if fn.startswith(spec_id + "-") and fn.endswith(".md"):
            return os.path.join(spec_dir, fn)
    return None


#: 连写引用（`§一~§五十八`）里，第二个引用与目标之间夹着第一个引用本身 ⇒ 比较前先剥掉
REF_TOKEN = re.compile(r"§\s*[0-9]+(?:\.[0-9]+)*|§\s*[%s]+" % CN_CHARS)


def strip_refs(text: str) -> str:
    """去掉文本里已经出现过的 `§N` 引用（连写情形用）。"""
    return REF_TOKEN.sub("", text)


# ---------------------------------------------------------------- D9
def check_d9(docs: str, root: str, files: list[str], rep) -> None:
    """`§N` 章节锚点必须指向真实存在的章节（g19 只解析文件路径、不查锚点）。"""
    heads: dict[str, set[str]] = {}
    for f in files:
        heads[f] = heading_tokens(os.path.join(docs, f.replace("/", os.sep)))

    for f in files:
        if not (f.startswith(D9_SRC_PREFIXES) or f in D9_SRC_ROOT_FILES):
            rep.exempt("D9-historical-src")
            continue
        full = os.path.join(docs, f.replace("/", os.sep))
        for ln, line in enumerate(read_text(full).splitlines(), 1):
            if REF_FORMAT_FIELD.search(line):
                rep.exempt("D9-ref-format-field")
                continue
            refs = list(SECTION_REF.finditer(line))
            if not refs:
                continue
            # 本行的**指向性目标**：(位置, 绝对路径) —— 只认链接与反引号包裹（见 TARGET_TOKEN 注释）
            targets: list[tuple[int, str]] = []
            for m in TARGET_TOKEN.finditer(line):
                cand = m.group(1) or m.group(2)
                p = resolve_path(docs, root, f, cand)
                if p:
                    targets.append((m.end(), p))
            targets.sort()

            self_marks = [(m.end(), True) for m in SELF_MARK.finditer(line)]

            for rm in refs:
                tgt = None
                # ① 紧邻型：目标与 § 之间只隔着分隔符
                for pos, p in reversed(targets):
                    if pos > rm.start():
                        continue
                    if all(ch in GAP_OK for ch in strip_refs(line[pos:rm.start()])):
                        tgt = p
                        break
                # ② 自引用标记型：「本文件 §N」
                if tgt is None:
                    for pos, _ in reversed(self_marks):
                        if pos > rm.start():
                            continue
                        if all(ch in GAP_OK for ch in line[pos:rm.start()]):
                            tgt = os.path.join(docs, f.replace("/", os.sep))
                            break
                if tgt is None:
                    rep.exempt("D9-no-target")
                    continue
                rel = os.path.relpath(tgt, docs).replace("\\", "/")
                toks = heads.get(rel)
                if toks is None:
                    rep.exempt("D9-target-outside")
                    continue
                if not toks:
                    rep.exempt("D9-target-no-sections")
                    continue
                if rm.group(1) not in toks:
                    rep.block("D9", "%s:%d 的 §%s 在 %s 里没有对应章节" % (f, ln, rm.group(1), rel))
                else:
                    rep.exempt("D9-anchor-ok")


# ---------------------------------------------------------------- D10
def check_d10(docs: str, rep) -> None:
    """交接卷卷首声明的覆盖区间，必须覆盖正文里出现的**最新日期**。"""
    d = os.path.join(docs, "记录", "交接")
    if not os.path.isdir(d):
        rep.skip("D10 交接卷区间（记录/交接/ 不存在）")
        return
    for fn in sorted(os.listdir(d)):
        if not re.match(r"^\d{4}-\d{2}\.md$", fn):
            continue
        lines = read_text(os.path.join(d, fn)).splitlines()
        head = "\n".join(lines[:6])
        m = re.search(r"（\s*(20\d{2}-\d{2}-\d{2})\s*~\s*(20\d{2}-\d{2}-\d{2})\s*）", head)
        if not m:
            continue                      # D7 已报「缺区间」，此处不重复
        _lo, hi = m.groups()
        body = "\n".join(lines[6:])
        dates = sorted({x.group(1) for x in DATE_RE.finditer(body)})
        if not dates:
            rep.exempt("D10-no-dates")
            continue
        if dates[-1] > hi:
            rep.block("D10", "交接卷 %s 卷首覆盖区间止于 %s，但正文出现 %s —— 区间未随正文续写"
                      % (fn, hi, dates[-1]))
        else:
            rep.exempt("D10-range-covers")


# ---------------------------------------------------------------- D11
def check_d11(docs: str, rep) -> None:
    """INDEX 内部**两处**份数自述（头部覆盖行 vs 各节标题）必须一致。

    D8 只核头部那一行；§二/§三/§四 标题里各带一份「N 份」，两边各漂各的。
    """
    idx = os.path.join(docs, "INDEX.md")
    if not os.path.isfile(idx):
        return                            # D8 已报
    text = read_text(idx)
    head = "\n".join(text.splitlines()[:20])
    cm = re.search(r"覆盖\*\*[^\n]*?根\s*(\d+)[^\d\n]+规范\s*(\d+)[^\d\n]+事实源\s*(\d+)[^\d\n]+记录\s*(\d+)",
                   head)
    if not cm:
        return                            # D8 已报
    said = {"规范": int(cm.group(2)), "事实源": int(cm.group(3)), "记录": int(cm.group(4))}
    for cat, dirname in COUNT_SECTIONS:
        sm = re.search(r"^##[^\n]*`%s/`[^\n]*?(\d+)\s*份" % re.escape(dirname), text, re.M)
        if not sm:
            rep.exempt("D11-no-selfcount")
            continue
        if int(sm.group(1)) != said[cat]:
            rep.block("D11", "INDEX §%s 标题自述 %s 份，与头部覆盖行的 %d 份不一致"
                      % (cat, sm.group(1), said[cat]))
        else:
            rep.exempt("D11-count-agree")


# ---------------------------------------------------------------- 自检
def _fixture(kind: str, base: str) -> str:
    """造一个迷你枢纽（只含三项新判据所需的结构）。"""
    docs = os.path.join(base, "docs")
    os.makedirs(os.path.join(docs, "事实源", "机器"), exist_ok=True)
    os.makedirs(os.path.join(docs, "记录", "交接"), exist_ok=True)

    sec = "1" if kind == "clean" else "99"
    with io.open(os.path.join(docs, "事实源", "机器", "机器分区索引.md"), "w", encoding="utf-8") as f:
        f.write("# 机器分区索引\n\n## 1. 标识\n\n## 2. 盘位\n\n"
                "见 `机器分区索引.md` §%s\n" % sec)

    hi = "2026-10-31" if kind == "clean" else "2026-10-16"
    with io.open(os.path.join(docs, "记录", "交接", "2026-10.md"), "w", encoding="utf-8") as f:
        f.write("# 会话交接 · 2026-10 卷（2026-10-04 ~ %s）\n\n正文（2026-10-31 记）。\n" % hi)

    rec_n = 1 if kind == "count-line-drift" else 1
    head_rec = 1
    with io.open(os.path.join(docs, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# INDEX\n\n> **时点** 2026-10-31 ｜ **覆盖** 根 0 + 规范 0 + 事实源 1 + 记录 %d = **%d 份**\n\n"
                "## 四、记录（`记录/`，%d 份，**只增不改**）\n" % (head_rec, head_rec + 1, rec_n))
    return docs


def selfcheck_extra() -> dict[str, int]:
    """对三处新判据各造一个真实破坏用例 + 一个干净用例。

    自检用例放在**共享模块**里 ⇒ 两个落点（仓内 docs_index.py / 分发版 g15）共用同一套，
    不会各写一套而漂移（与 D 系列判据同一条纪律）。
    """
    import shutil
    import tempfile

    caught = clean = misreports = 0
    for kind in ("anchor-dangling", "range-too-narrow", "count-line-drift"):
        tmp = tempfile.mkdtemp(prefix="docscontract_")
        try:
            docs = _fixture(kind, tmp)
            rep = _MiniReport()
            check_d9(docs, os.path.dirname(docs), _mini_files(docs), rep)
            check_d10(docs, rep)
            check_d11(docs, rep)
            if rep.blocking:
                caught += 1
            else:
                print("MISSED case not caught: %s" % kind)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    tmp = tempfile.mkdtemp(prefix="docscontract_")
    try:
        docs = _fixture("clean", tmp)
        rep = _MiniReport()
        check_d9(docs, os.path.dirname(docs), _mini_files(docs), rep)
        check_d10(docs, rep)
        check_d11(docs, rep)
        if rep.blocking:
            misreports += 1
            print("MISREPORT clean-case failed: %s -- %s" % (kind, [m for _, m in rep.blocking][:3]))
        else:
            clean += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {"caught": caught, "clean": clean, "misreports": misreports}


class _MiniReport:
    """最小 Report 替身（两个落点的 Report 类字段一致，duck typing 即可）。"""

    def __init__(self) -> None:
        self.blocking: list[tuple[str, str]] = []
        self.reported: list[tuple[str, str]] = []
        self.exempted: dict[str, int] = {}
        self.skipped: list[str] = []

    def block(self, code: str, msg: str) -> None:
        self.blocking.append((code, msg))

    def note(self, code: str, msg: str) -> None:
        self.reported.append((code, msg))

    def exempt(self, kind: str, n: int = 1) -> None:
        self.exempted[kind] = self.exempted.get(kind, 0) + n

    def skip(self, what: str) -> None:
        self.skipped.append(what)


def _mini_files(docs: str) -> list[str]:
    out = []
    for dp, dn, fns in os.walk(docs):
        dn[:] = [x for x in dn if x not in ("md", "spec", "facts", "records", "历史")]
        for fn in fns:
            if fn.endswith(".md"):
                full = os.path.join(dp, fn)
                out.append(os.path.relpath(full, docs).replace("\\", "/"))
    return sorted(out)
