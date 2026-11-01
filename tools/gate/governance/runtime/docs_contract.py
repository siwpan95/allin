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

#: 规范编号（`SPEC-005`）本身即可定位文件 ⇒ 可作 § 的目标
SPEC_TOKEN = re.compile(r"\b(SPEC-\d+)\b")

#: 稳定的中文文档别名 → 文件（本仓只认这几个；别名硬编码是**有意的**：
#: 「索引」在本仓恒指机器分区索引（统辖入口），加新别名前须确认全仓无歧义）
DOC_ALIASES = {
    "索引": "事实源/机器分区索引.md",
}

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


def resolvable_tokens(path: str) -> set[str]:
    """（保留：字符串形态的可解析节号集合，供调试与自检比对用）"""
    toks = set(heading_tokens(path))
    lines = read_text(path).splitlines()
    has_numbered_heading = any(re.match(r"^#{2,4}\s+[0-9]+(?:\.[0-9]+)*[ .、]", ln) for ln in lines)
    if not has_numbered_heading:
        for ln in lines:
            m = re.match(r"^(\d+)\.\s+\S", ln)
            if m:
                toks.add(m.group(1))
    return toks


def tok_key(tok: str):
    """节号 → **规范化键**（中文序数与阿拉伯数等价）；不可解析返回 None。

    为什么必须规范化：同一节可能有两种写法 —— 顶级节用中文序数（`## 一百一十、`），
    而引用方常写阿拉伯（`§110`）⇒ 字符串比对会把**合法引用**判成失效（假红）。
    实测：INDEX 的 REC-HO-03 行里就写着 `§110`，而该卷的标题是 `## 一百一十、…`。
    ⚠ 用**字符串键**而非 float —— 节号可以是多层小数（`§2.1.1`），float() 解析不了。
    """
    if re.match(r"^\d+(?:\.\d+)*$", tok):
        parts = tok.split(".")
        if len(parts[0]) >= 8:                    # 20261031173800 这类时间戳不是节号
            return None
        frac = ".".join(parts[1:]).rstrip("0")
        return parts[0] + ("." + frac if frac else "")
    v = cn2int(tok)
    return str(v) if v is not None else None


def numeric_token_set(path: str, with_list_items: bool = False) -> set[str]:
    """文档的可解析节号集合（规范化键）。

    `with_list_items=True` 时额外计入编号列表项 —— 仅当该文档**全文无编号标题**时才计
    （SPEC-004 的 69 条调试铁律就是列表项；机器分区索引的列表项只是 §0 的子项、不算节号）。
    """
    out: set[str] = set()
    toks = heading_tokens(path)
    if with_list_items and not any(re.match(r"^#{2,4}\s+[0-9]+(?:\.[0-9]+)*[ .、]", ln)
                                   for ln in read_text(path).splitlines()):
        for ln in read_text(path).splitlines():
            m = re.match(r"^(\d+)\.\s+\S", ln)
            if m:
                toks.add(m.group(1))
    for t in toks:
        k = tok_key(t)
        if k is not None:
            out.add(k)
    return out


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


def collect_targets(docs: str, root: str, f: str, line: str) -> list[tuple[int, str]]:
    """本行**可定位**的目标：(位置, 绝对路径)。D9 与 D13 共用一份，避免两边判据漂移。"""
    out: list[tuple[int, str]] = []
    for m in TARGET_TOKEN.finditer(line):
        cand = m.group(1) or m.group(2)
        p = resolve_path(docs, root, f, cand)
        if p:
            out.append((m.end(), p))
    for m in SPEC_TOKEN.finditer(line):                 # 规范编号本身即可定位文件
        p = resolve_spec(docs, m.group(1))
        if p:
            out.append((m.end(), p))
    for alias, rel in DOC_ALIASES.items():              # 稳定的中文别名（如「索引 §1」）
        for m in re.finditer(re.escape(alias), line):
            p = os.path.join(docs, rel.replace("/", os.sep))
            if os.path.isfile(p):
                out.append((m.end(), p))
    out.sort()
    return out


def adjacent_target(targets: list[tuple[int, str]], line: str, ref_start: int):
    """该引用是否已有**紧邻**可定位目标（紧邻型 / 规范编号型 / 别名型）⇒ 返回该目标或 None。"""
    for pos, p in reversed(targets):
        if pos > ref_start:
            continue
        if all(ch in GAP_OK for ch in strip_refs(line[pos:ref_start])):
            return p
    return None


# ---------------------------------------------------------------- D9
def check_d9(docs: str, root: str, files: list[str], rep) -> None:
    """`§N` 章节锚点必须指向真实存在的章节（g19 只解析文件路径、不查锚点）。"""
    heads: dict[str, set[str]] = {}
    for f in files:
        # 目标解析用「标题编号 +（全文无编号标题时的）编号列表项编号」，且**数值化**
        # （中文序数与阿拉伯数等价：§110 == ## 一百一十、）
        heads[f] = numeric_token_set(os.path.join(docs, f.replace("/", os.sep)), with_list_items=True)

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
            # 本行的**指向性目标**：(位置, 绝对路径) —— D9/D13 共用一份收集逻辑
            targets = collect_targets(docs, root, f, line)
            self_marks = [(m.end(), True) for m in SELF_MARK.finditer(line)]

            for rm in refs:
                tgt = adjacent_target(targets, line, rm.start())
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
                rv = tok_key(rm.group(1))
                if rv is None:
                    rep.exempt("D9-ref-not-numeric")
                    continue
                if rv not in toks:
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


# ---------------------------------------------------------------- D12
CN_DIGIT = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn2int(s: str):
    """中文序数 → 整数（九十四→94、一百一十一→111）。不是中文序数则返回 None。"""
    total, num = 0, 0
    for ch in s:
        if ch in CN_DIGIT:
            num = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            unit = CN_UNIT[ch]
            if unit == 10 and num == 0:
                num = 1                      # 「十二」= 12
            total += num * unit
            num = 0
        else:
            return None
    return total + num


def token2int(tok: str):
    """章节号 → 整数（阿拉伯或中文序数）；时间戳形态与小节号返回 None。"""
    if tok.isdigit():
        if len(tok) >= 8:                    # 20261031173800 这类时间戳不是节号
            return None
        return int(tok)
    return cn2int(tok)


def top_section_span(path: str):
    """卷的**顶级节**（`##` 级）节号区间（min, max）；忽略时间戳形态与小节。

    ⚠ 只取 `##` 级：小节（`### 107.5`）与时间戳小节（`### 20261031173800`）不算顶级节。
    ⚠ `min` 不可靠：有的卷在 `## 九十四` 之后又用了 `## 一、`~`## 五、` 作子节（如 2026-10 卷）
      ⇒ **不判「起节 ≤ 实际首节」**，只判**末节**（那才是真实漏网的形态）。
    """
    lo = hi = None
    for line in read_text(path).splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if not m:
            continue
        t = SECTION_TOKEN.match(m.group(1).strip())
        if not t:
            continue
        v = token2int(t.group(1))
        if v is None:
            continue
        if lo is None or v < lo:
            lo = v
        if hi is None or v > hi:
            hi = v
    return lo, hi


def check_d12(docs: str, rep) -> None:
    """INDEX 交接表的「覆盖区间」列自述，必须与**该卷自身**相符。

    为什么必须按卷判：交接卷的顶级节用中文序数，而**节号在不同卷间会重复**
    （`§一` 在 2026-08 卷是「总体状态」、在 2026-10 卷是「用户拍板」）⇒
    `§N` 必须带卷才无歧义，全局判必然误报。

    三条判据：
      (a) 列内每个 `§X` 都存在于该卷的标题集合
      (b) 列内声明的**末节 ≥ 该卷实际末节**（真实漏网形态：写「§一百零七」而卷里已到 §一百一十一）
      (c) 列内声明的**日期区间 == 该卷卷首声明的日期区间**（D10 保证卷首区间随正文续写，
          D12 再保证 INDEX 的登记与卷首同步 ⇒ 三段链条闭合）
    """
    idx = os.path.join(docs, "INDEX.md")
    if not os.path.isfile(idx):
        return
    for ln, line in enumerate(read_text(idx).splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        target_rel, link_idx = None, None
        for i, c in enumerate(cells):
            for m in re.finditer(r"\]\((记录/交接/[^)\s]+\.md)\)", c):
                target_rel, link_idx = m.group(1), i
        if target_rel is None or link_idx is None or link_idx + 1 >= len(cells):
            continue
        cell = cells[link_idx + 1]
        vol_path = os.path.join(docs, target_rel.replace("/", os.sep))
        if not os.path.isfile(vol_path):
            continue

        # (c) 日期区间：INDEX 登记 vs 卷首声明
        dm = re.search(r"(20\d{2}-\d{2}-\d{2})\s*~\s*(?:(20\d{2})-)?(\d{2}-\d{2})", cell)
        hm = re.search(r"（\s*(20\d{2}-\d{2}-\d{2})\s*~\s*(20\d{2}-\d{2}-\d{2})\s*）",
                       "\n".join(read_text(vol_path).splitlines()[:6]))
        if dm and hm:
            idx_hi = "%s-%s" % (dm.group(2) or dm.group(1)[:4], dm.group(3))
            if (dm.group(1), idx_hi) != hm.groups():
                rep.block("D12", "INDEX 第 %d 行的覆盖区间日期 %s ~ %s 与该卷卷首声明的 %s ~ %s 不一致"
                          % (ln, dm.group(1), idx_hi, hm.group(1), hm.group(2)))

        # (a) 列内每个 §X 都该卷存在（**数值化**比较：中文序数与阿拉伯数等价）
        toks = numeric_token_set(vol_path)
        for m in SECTION_REF.finditer(cell):
            rv = tok_key(m.group(1))
            if rv is None:
                continue
            if rv not in toks:
                rep.block("D12", "INDEX 第 %d 行的 §%s 在 %s 里没有对应章节"
                          % (ln, m.group(1), target_rel))

        # (b) 声明的末节 ≥ 该卷实际末节
        rm = re.search(r"§([0-9]+(?:\.[0-9]+)*|[%s]+)\s*~\s*§([0-9]+(?:\.[0-9]+)*|[%s]+)"
                       % (CN_CHARS, CN_CHARS), cell)
        if rm:
            declared_end = token2int(rm.group(2))
            _lo, actual_end = top_section_span(vol_path)
            if declared_end is not None and actual_end is not None and declared_end < actual_end:
                rep.block("D12", "INDEX 第 %d 行声明的节区间止于 §%s，但该卷实际已到第 %d 节"
                          % (ln, rm.group(2), actual_end))
        else:
            rep.exempt("D12-open-range")

# ---------------------------------------------------------------- D13
#: 文档限定词：出现在 `§` 之前，说明这个 § 指向**别的**文档（不归本行链接）
DOC_QUALIFIERS = ("交接档", "交接", "索引", "本卷", "本文件", "本文", "本节",
                   "规范", "记忆", "计划", "审计", "快照", "专题", "事故", "决策", "外部")

#: INDEX 的登记行里，「文件/卷」列的链接（整段含标签，用于排除标签里的 §）
INDEX_ROW_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+\.md)\)")


def _index_row_ids(docs: str) -> dict[str, str]:
    """INDEX 的**行号 → 该行链接的文档**映射（`FACT-01` → `事实源/机器分区索引.md`）。

    行号是 INDEX 里**稳定的标识符**（登记项的主键），所以 `FACT-01 §5.1` 这类引用
    可以唯一定位目标 —— 与「规范编号型」「中文别名型」同属**无歧义指向形态**。
    """
    idx = os.path.join(docs, "INDEX.md")
    out: dict[str, str] = {}
    if not os.path.isfile(idx):
        return out
    for line in read_text(idx).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not re.match(r"^[A-Z]+-[A-Z0-9]+$", cells[0]):
            continue
        targets = set()
        for m in INDEX_ROW_LINK.finditer(line):
            p = resolve_path(docs, os.path.dirname(docs), "INDEX.md", m.group(2))
            if p:
                targets.add(p)
        if len(targets) == 1:
            out[cells[0]] = next(iter(targets))
    return out


def check_d13(docs: str, root: str, rep) -> None:
    """INDEX 登记表的**列语义契约**（SPEC-005 §3.6）：行内**未加限定词**的 `§N` 归本行链接的文档。

    为什么是「契约」而不是启发式：INDEX 的登记表行有固定列语义 ——
    「文件/卷」列指向一份文档，该行其余列里**不带文档限定词**的 `§N` 指的就是**这份文档**的节。
    写了契约，判据就按契约读，不靠猜；反之若带限定词，它指向**另一份**文档：
      · 文档限定词（「交接 §107.10」「索引 §1」）⇒ 跳过（属限定词解析，另一套规则）；
      · **INDEX 行号**（`FACT-01 §5.1`）⇒ 归**该行号所登记的文档**（行号是稳定主键）。

    排除项：
      - 行内有**多个**不同链接 ⇒ 目标不唯一 ⇒ 整行跳过；
      - `§` 落在**链接标签内**（如 `[§107.4 六条清理计划](…)`）⇒ 它指别处 ⇒ 跳过；
      - 该引用**已有紧邻可定位目标**（D9 已判过）⇒ 不重复判。
    """
    idx = os.path.join(docs, "INDEX.md")
    if not os.path.isfile(idx):
        return
    row_ids = _index_row_ids(docs)
    for ln, line in enumerate(read_text(idx).splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        links = list(INDEX_ROW_LINK.finditer(line))
        if not links:
            continue
        targets = {}
        for m in links:
            p = resolve_path(docs, root, "INDEX.md", m.group(2))
            if p:
                targets[m.span()] = p
        distinct = set(targets.values())
        if len(distinct) != 1:
            rep.exempt("D13-ambiguous-row")
            continue
        row_target = next(iter(distinct))
        row_rel = os.path.relpath(row_target, docs).replace("\\", "/")
        toks = numeric_token_set(row_target)
        line_targets = collect_targets(docs, root, "INDEX.md", line)
        for rm in SECTION_REF.finditer(line):
            if any(s <= rm.start() < e for s, e in targets):
                rep.exempt("D13-in-link-label")
                continue
            if adjacent_target(line_targets, line, rm.start()):
                rep.exempt("D13-already-by-D9")
                continue
            before = line[max(0, rm.start() - 12):rm.start()]
            # ① INDEX 行号限定词 → 该行号登记的文档（**紧邻型**：行号与 § 之间只隔分隔符）
            hit_id = None
            for m in reversed(list(re.finditer(r"[A-Z]+-[A-Z0-9]+", line[:rm.start()]))):
                rid = m.group(0)
                if rid not in row_ids:
                    continue
                if all(ch in GAP_OK for ch in strip_refs(line[m.end():rm.start()])):
                    hit_id = (rid, row_ids[rid])
                    break
            if hit_id:
                rid, p = hit_id
                rtoks = numeric_token_set(p)
                key = tok_key(rm.group(1))
                if key is not None and rtoks and key not in rtoks:
                    rep.block("D13", "INDEX 第 %d 行的 %s §%s 在其登记的 %s 里没有对应章节"
                              % (ln, rid, rm.group(1),
                                 os.path.relpath(p, docs).replace("\\", "/")))
                else:
                    rep.exempt("D13-row-id-ok")
                continue
            # ② 文档限定词 → 指别的文档，跳过
            if any(q in before for q in DOC_QUALIFIERS):
                rep.exempt("D13-qualified")
                continue
            # ③ 列语义契约：归本行链接的文档
            key = tok_key(rm.group(1))
            if key is None or not toks:
                rep.exempt("D13-not-numeric")
                continue
            if key not in toks:
                rep.block("D13", "INDEX 第 %d 行的 §%s 在本行链接的 %s 里没有对应章节"
                          % (ln, rm.group(1), row_rel))
            else:
                rep.exempt("D13-anchor-ok")


# ---------------------------------------------------------------- 自检
def _fixture(kind: str, base: str) -> str:
    """造一个迷你枢纽（只含新判据所需的结构）。

    ⚠ **每个破坏用例只破坏自己那一维** —— 否则会出现"自欺欺人"：
    早期版本让三个用例同时带上 §99，结果 D10/D11 的用例其实是被 D9 拦下的，
    `caught=3` 是假象，那两条判据**从未真正被执行过**。故此处逐维开关。
    """
    docs = os.path.join(base, "docs")
    os.makedirs(os.path.join(docs, "事实源", "机器"), exist_ok=True)
    os.makedirs(os.path.join(docs, "记录", "交接"), exist_ok=True)

    broken_anchor = (kind == "anchor-dangling")
    broken_spec = (kind == "spec-anchor-dangling")
    broken_alias = (kind == "alias-anchor-dangling")
    broken_range = (kind == "range-too-narrow")
    broken_count = (kind == "count-line-drift")
    broken_index_range = (kind == "index-range-drift")
    broken_row_contract = (kind == "row-contract-dangling")
    broken_row_id = (kind == "row-id-dangling")

    # 被引的索引（中文别名「索引」指向它；**布局照真实仓**：索引在 事实源/ 下、机器文件在其 机器/ 子目录）
    with io.open(os.path.join(docs, "事实源", "机器分区索引.md"), "w", encoding="utf-8") as f:
        f.write("# 机器分区索引\n\n## 1. 机器分区清单\n\n## 2. 归属规则\n")
    # 被引的规范（SPEC 编号本身即可定位它）
    os.makedirs(os.path.join(docs, "规范"), exist_ok=True)
    with io.open(os.path.join(docs, "规范", "SPEC-005-测试.md"), "w", encoding="utf-8") as f:
        f.write("# SPEC-005 · 测试\n\n> **编号** SPEC-005 ｜ **效力** 铁律级 ｜ **状态** 生效\n"
                "> **生效** 2026-09-28 ｜ **最后修订** 2026-09-28 ｜ **适用面** 全域\n"
                "> **承载体** 测试 ｜ **引用格式** SPEC-005 §5\n\n## 5. 头部契约\n\n正文。\n")
    # 引用方：三种目标形态各一处（逐维破坏）
    if broken_spec:
        refs = "见 `SPEC-005` §99；见 `机器分区索引.md` §1；见 索引 §2"
    elif broken_alias:
        refs = "见 `SPEC-005` §5；见 `机器分区索引.md` §1；见 索引 §99"
    elif broken_anchor:
        refs = "见 `SPEC-005` §5；见 `机器分区索引.md` §99；见 索引 §2"
    else:
        refs = "见 `SPEC-005` §5；见 `机器分区索引.md` §1；见 索引 §2"
    with io.open(os.path.join(docs, "事实源", "观测.md"), "w", encoding="utf-8") as f:
        f.write("# 观测\n\n## 1. 记录\n\n%s\n" % refs)

    hi = "2026-10-16" if broken_range else "2026-10-31"
    with io.open(os.path.join(docs, "记录", "交接", "2026-10.md"), "w", encoding="utf-8") as f:
        f.write("# 会话交接 · 2026-10 卷（2026-10-04 ~ %s）\n\n"
                "## 一、总体状态\n\n## 五十八、收尾\n\n正文（2026-10-31 记）。\n" % hi)

    # INDEX：登记行 + 两处份数自述 + 供 D13 用的行号（FACT-01）与登记表行
    rec_n = 5 if broken_count else 1
    head_rec = 1
    sec_hi = "§一~§一" if broken_index_range else "§一~§五十八"
    main_line = "主线（§九十九）" if broken_row_contract else "主线"
    row_id_line = "| FACT-01 | [机器分区索引](事实源/机器分区索引.md) | 2026-10-30 | 机器事实统辖入口 |"
    extra_row = ""
    if broken_row_id:
        # 该行的链接必须**真实存在**，否则整行因「目标不唯一/解析不到」被跳过 ⇒ 用例测不到
        os.makedirs(os.path.join(docs, "记录", "审计"), exist_ok=True)
        with io.open(os.path.join(docs, "记录", "审计", "某审计_2026-10-31.md"), "w", encoding="utf-8") as f:
            f.write("# 某审计\n\n## 1. 结论\n\n正文。\n")
        extra_row = "| REC-AU-99 | [某审计](记录/审计/某审计_2026-10-31.md) | 2026-10-31 | 见 FACT-01 §九十九 |"
    with io.open(os.path.join(docs, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# INDEX\n\n> **时点** 2026-10-31 ｜ **覆盖** 根 0 + 规范 0 + 事实源 1 + 记录 %d = **%d 份**\n\n"
                "## 四、记录（`记录/`，%d 份，**只增不改**）\n\n"
                "| 编号 | 卷 | 覆盖区间 | 主线 |\n| --- | --- | --- | --- |\n"
                "| REC-HO-01 | [2026-10.md](记录/交接/2026-10.md) | 2026-10-04 ~ 10-31（%s） | %s |\n"
                % (head_rec, head_rec + 1, rec_n, sec_hi, main_line))
        f.write("\n## 三、事实源（`事实源/`，1 份）\n\n| 编号 | 文件 | 时点 | 一句话 |\n| --- | --- | --- | --- |\n%s\n"
                % row_id_line)
        if extra_row:
            f.write("\n%s\n" % extra_row)
    return docs


def selfcheck_extra() -> dict[str, int]:
    """对三处新判据各造一个真实破坏用例 + 一个干净用例。

    自检用例放在**共享模块**里 ⇒ 两个落点（仓内 docs_index.py / 分发版 g15）共用同一套，
    不会各写一套而漂移（与 D 系列判据同一条纪律）。
    """
    import shutil
    import tempfile

    caught = clean = misreports = 0
    for kind in ("anchor-dangling", "spec-anchor-dangling", "alias-anchor-dangling",
                 "range-too-narrow", "count-line-drift", "index-range-drift",
                 "row-contract-dangling", "row-id-dangling"):
        tmp = tempfile.mkdtemp(prefix="docscontract_")
        try:
            docs = _fixture(kind, tmp)
            rep = _MiniReport()
            check_d9(docs, os.path.dirname(docs), _mini_files(docs), rep)
            check_d10(docs, rep)
            check_d11(docs, rep)
            check_d12(docs, rep)
            check_d13(docs, os.path.dirname(docs), rep)
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
        check_d12(docs, rep)
        check_d13(docs, os.path.dirname(docs), rep)
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
