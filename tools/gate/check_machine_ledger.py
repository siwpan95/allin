#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月账一致性判据（registry 之外的判据，登记于 `tools/gate/README.md` §12）。

## 为什么需要它

`docs/事实源/机器/<机>/月账/YYYY-MM.md` 是 **各机自持**的运行时记录（`机器分区索引.md`
「月账与交接的归属」，铁律 6）。自持本身带来三种只有判据能拦的失真：

1. **引用了不存在的节**。月账写「按交接卷 §N 推进」是一种**溯源断言**；`docs_index`
   的 D9 只判 `docs/` 树内的 `§N` 锚点，D18 只判交接卷**最新一节**有没有 `@机名`，
   没有任何一道判「月账引的那一节还在不在」。节被重排/撤销后，断言会静默悬空 ——
   下游读到「按 §225 做完了」却查无此节，只会以为是自己没找到。
2. **归属不明的卷**。铁律 6 只允许两条通道：**本机自持**（该机自己写）与
   **代整理 + 待该机复核**（本机代笔、把判定权留给事实方）。卷首不写通道，
   读者无法判断这份卷是「事实方自述」还是「他人转述」—— 铁律 6 的合法通道就成了口头的。
3. **自述的数字没人核**。「本期总提交 N / 可归属 M / 未归属 K」是月账里唯一
   可被机器独立重算的断言（`git rev-list --count`），也是**最容易抄错**的一类
   （换机器、跨月边界、漏算一次 squash 就差一）。

## 三条判据

| 判据 | 判什么 | 判红条件 |
| --- | --- | --- |
| **A** | 月账里对交接卷的**节引用**必须落在真实存在的节上 | 引用的节号在该月卷的标题集合里**不存在**（且同行无撤销/订正标记） |
| **B** | 每份月账卷首必须声明**归属通道**，且声明要成对 | ①两条通道都没声明；②声明了「代整理」却缺「待…复核」（半张声明=免检章） |
| **C** | 月账「未归属提交」一节的三个数字必须与 `git rev-list --count` 实测一致 | 总提交 / 可归属 / 未归属 任一对不上，或该节存在却读不到三个数字 |

## 哪些**不可**机检（写清楚，别让它们冒充已判）

- **A 的机一致半边**：铁律 6 要求跨机引用用 `§章节` 指针，所以**引用他机的节是本仓
  规定动作**，不是缺陷。文本上没有可靠的形态区分「引用」与「据为己有」——
  `KQABATS（交接卷 §223）` 是引用，`据 §223 完成本机工作` 才是据为己有，两者字面同构。
  故本判据只判**节存在性**；「引他机节而未命名该机」记 **UNDETERMINED** 并列清单，
  不给默认值。要让它能判红，需要月账改用声明式写法（见文末「下一步」）。
- **B 的「谁真的写了」**：本仓 643 个提交的作者全是 `siwpan <siwpan@users.noreply.gitee.com>`
  （2026-11-26 实测 `git log --format='%an|%ae' | sort -u`），三台机身份同值 ⇒
  `git blame` / `git log` 无法反推执笔机。故 B 只判**声明在不在、成不成对**，
  「声明与事实是否相符」记 UNDETERMINED（`--verbose` 时逐卷打印）。
- **C 只在月账真写了那一节时生效**。当期三份月账都没有该节 ⇒ 本判据当期 SKIP
  （`skipped (not a pass)`，不是通过）。它的负对照与变异验证在 `--selfcheck` 里跑，
  证明它红得出来 —— 一个只在自检里红过的判据，仍然比 `scanned 0 + exit 0` 诚实。

## 与既有判据的分工（避免第二份真相源）

- 节号的**规范化**（中文序数 `二百三十一` ↔ 阿拉伯 `231` ↔ 多层 `231.1`）**不另写一份**：
  `docs_contract.tok_key` / `numeric_token_set` 已是全仓唯一实现（D9/D12/D13 同源）。
  本文件 `import` 它，装包时用包内那份、裸 clone 时回退仓内真身（与 `docs_index.py` 同款）。
- D18 判「交接卷最新一节有没有标 `@机名`」，本判据判「月账引的节存不存在」；两者判不同对象。
- D19 判「共有月账条目不许在时间戳里标归属机」，对象是 `docs/记录/记忆/`，与本判据不重叠。

## 范围（避免越权：铁律 6）

- **本机月账**：三条判据全判，阻断计入退出码。
- **异机月账**：只有 **B** 阻断（B 判的正是「这份卷的归属说得清吗」，缺声明即归属不明，
  这是读就能看出来的，不需要替他机下事实结论）；**A/C 对他机只报告不阻断**并记
  UNDETERMINED —— 本机不替他机判内容对错（与 `g20-facts` 只判本机分区同构）。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 无阻断，且无不可判定项 |
| 1 | 存在阻断（A/B/C 任一判红） |
| 2 | 无阻断但存在不可判定项（未加 `--allow-undetermined` 时；**不是通过**） |
| 3 | 环境错（找不到根 / 找不到月账目录 / git 不可用） |

自检：`--selfcheck` 逐条跑正例与负对照，并支持 `--mutate a|b|c` 做**变异验证**
（把某条判据的判红分支摘掉后，自检必须**红**：变异体若存活，等于该判据没在承重）。

## 下一步（要让它能判 A 的机一致半边）

月账条目改用声明式溯源块，例如：

```text
> 来源：交接卷 §231（@SIWPAN） ｜ 方式：自述
> 来源：交接卷 §225（@DESKTOP-8RSV60V） ｜ 方式：引用
```

有了「方式」字段，「据为己有」就成了可机检的字面量，A 的机一致半边才能从
UNDETERMINED 升为阻断。**在那之前不加**：靠猜写法的判据，误报的代价是团队开始
绕过它，比不判更坏。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# 共享判据（节号规范化）—— 全仓唯一实现，不复制第二份：
# 装包 → 用包内那份（公共核已提仓 allin-governance）；未装包 → 回退仓内真身。
try:
    from allin_governance._gatesuite.runtime import docs_contract  # noqa: E402
except ImportError:  # pragma: no cover - 裸 clone 且未装包时的回退
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "governance", "runtime"))
    import docs_contract  # noqa: E402

TITLE = "machine-ledger"
EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_UNDETERMINED = 2
EXIT_ENV = 3

#: 月账与交接卷的落点（相对仓根；`/` 分隔，落地时转 os.sep）。
LEDGER_GLOB = ("docs", "事实源", "机器")
LEDGER_SUBDIR = "月账"
HANDOVER_DIR = ("docs", "记录", "交接")

#: 卷首声明的两条合法归属通道（铁律 6）。第一条自带「自持」义，第二条必须成对。
CHANNEL_SELF = ("本机自持",)
CHANNEL_DELEGATED = ("代整理",)
#: 「代整理」的配对方：只写「代整理」而不写复核承诺 = 把合法通道用成免检章。
RECHECK_RE = re.compile(r"(待[^，。；\n]{0,12}复核|待该机复核|待事实方复核)")

#: 节号 token（数字或中文序数）—— 与 docs_contract 同一套字符集。
CN_CHARS = "零一二三四五六七八九十百"
NUM = r"(?:[0-9]+(?:\.[0-9]+)*|[" + CN_CHARS + r"]+)"
#: 形态① `§231` / `§225.2` / `§二百三十一`：必须带「交接卷」前缀（裸 `§N` 按 D14 指本文件）。
CITE_SECTION_RE = re.compile(
    r"交接卷\s*(?:(\d{4}-\d{2})\s*卷?\s*)?[（(]?\s*§\s*(" + NUM + r")"
)
#: 形态② `交接卷 181 节` / `交接卷第二百一十七节` / `原第二百二十五节 .6`
CITE_VOLUME_RE = re.compile(
    r"(?:交接卷|原)\s*(?:§\s*)?第?\s*(" + NUM + r")\s*节(?:\s*\.\s*([0-9]+))?"
)
#: 机名标注：`@SIWPAN` / `@\`DESKTOP-KQABATS\`` / `@跨机`（交接卷的既定写法）。
MACHINE_TAG_RE = re.compile(r"@\s*`?([A-Za-z][A-Za-z0-9_-]{2,}|跨机)`?")
CROSS_MACHINE = "跨机"

#: 「撤销/订正」标记：引用一个**已被撤掉的节**是在描述历史，不是溯源断言。
#: 有它 ⇒ 记 UNDETERMINED（人去看），无它 ⇒ 判红（断言悬空）。
TOMBSTONE_RE = re.compile(r"(撤销|已删|撤回|已撤|作废|删除|订正|取代)")

#: 判据 C 的节标题特征与三个数字键。
UNATTRIBUTED_HEAD = "未归属"
#: 机读声明行（首选；自由文本里猜数字是假红的来源，能声明就别猜）。
COUNTS_MARKER = re.compile(r"ledger-counts:\s*([^\n]*?)(?:-->|$)", re.IGNORECASE)
#: 兼容既有散文/表格写法（只认**键紧邻数字**的形态，不做跨句邻近匹配）：
#: 实测反例——`可归属率仍停在 18%` 会被 `可归属\D{0,6}(\d+)` 读成「可归属=18」。
PROSE_TOTAL = re.compile(r"(?:总提交|本月)\s*[:：]?\s*(\d+)\s*条")
TABLE_ROW = re.compile(r"^\|\s*(总提交|可归属|未归属|有线索)\s*\|\s*\**\s*(\d+)\s*\**\s*\|", re.MULTILINE)
HEAD_COUNT = re.compile(r"(\d+)\s*条")

#: 「月账/交接的归属」规矩 2026-11-25 才立（`机器分区索引.md`）⇒ **B 的通道声明与
#: A2 的机名标注只判此月及以后的卷**。对存量卷（含 2026-11-25 按 git 记录重建的
#: `PROTOTYPE-01/月账/2026-09.md`）不逼迫改写 —— 与 D18/D19 的「生效月」限定同款：
#: 判据一旦追溯到规范诞生之前，第一次跑批就会红一片，团队的下一个动作是加豁免，
#: 而不是修数据。**A1（节存在性）不受此限**：悬空引用在哪个月都是悬空。
EFFECTIVE_FROM = "2026-11"

#: 判月时区，显式声明（ADR-0012 §D4.2）：团队只有一个工作时区，按提交者本地时区判月
#: 会让同一天的工作落在两个月份里。实测 643/643 条提交都是 +08:00。
TZ = _dt.timezone(_dt.timedelta(hours=8))
TZ_NAME = "+08:00"


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #


@dataclass
class Section:
    """交接卷里的一个节（`##`/`###`/`####` 标题）。"""

    key: str
    line: int
    heading: str
    machine: str | None = None


@dataclass
class Cite:
    """月账里的一个节引用（原样保留，便于判红文案直接引用原文）。

    `volume` 是**引用里点名的那一卷**（`交接卷 2026-09 §五十九` → `2026-09`）。
    点名与不点名要分开处理：点名了还查不到 = 断言悬空（红）；没点名但在别卷存在
    = 歧义（WARN）。把两者判成同一个红，等于罚了内容正确的引用。
    """

    key: str
    line: int
    text: str
    volume: str | None = None


@dataclass
class Ledger:
    """一份月账。"""

    machine: str
    month: str
    path: Path
    rel: str
    text: str


@dataclass
class Finding:
    criterion: str
    path: str
    line: int
    message: str
    blocking: bool = True

    def render(self) -> str:
        mark = "BLOCK" if self.blocking else "REPORT"
        return f"[{mark}] {self.criterion} {self.path}:{self.line} {self.message}"


@dataclass
class Undetermined:
    criterion: str
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"[UNDET] {self.criterion} {self.path}:{self.line} {self.message}"


@dataclass
class Warning_:
    """**提示项**：可疑但不足以判红（不参与退出码）。

    为什么要这个类别：把「歧义」和「造假」判成同一个红，团队的下一个动作是加豁免，
    而不是修数据 —— 那是判据自己把可信度耗掉的方式。跨卷引用不点名卷是**歧义**，
    任何卷都查不到才是**悬空**。
    """

    criterion: str
    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"[WARN] {self.criterion} {self.path}:{self.line} {self.message}"


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    undetermined: list[Undetermined] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)
    scanned: int = 0
    skipped: int = 0
    exempted: int = 0
    #: 口径行（ADR-0012 §D4.5）：不带口径的数，半年后无法与别的数比较，等于没有数。
    caliber: str = ""

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]


# --------------------------------------------------------------------------- #
# 解析：交接卷的节表
# --------------------------------------------------------------------------- #


def parse_sections(text: str) -> list[Section]:
    """把交接卷解析成节表；机名标注**沿标题层级继承**。

    继承是必需的：`### 231.1 …` 自己不写 `@机名`，它归 `## 二百三十一、@SIWPAN …`
    那一节。若不继承，所有子节都会变成「机名未知」而把 UNDETERMINED 淹掉。
    """
    sections: list[Section] = []
    stack: list[tuple[int, str | None]] = []      # (层级, 机名)
    for number, raw in enumerate(text.splitlines(), start=1):
        matched = re.match(r"^(#{2,4})\s+(.*)$", raw)
        if not matched:
            continue
        level = len(matched.group(1))
        heading = matched.group(2).strip()
        token = docs_contract.SECTION_TOKEN.match(heading)
        if token is None:
            continue
        key = docs_contract.tok_key(token.group(1))
        if key is None:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        tag = MACHINE_TAG_RE.search(heading)
        machine = tag.group(1) if tag else (stack[-1][1] if stack else None)
        stack.append((level, machine))
        sections.append(Section(key=key, line=number, heading=heading, machine=machine))
    return sections


def resolve_section(sections: list[Section], key: str) -> tuple[Section | None, bool]:
    """返回 (命中节, 是否精确命中)。

    多层节号（`231.1`）若本卷没有该子标题，退到父节（`231`）—— 交接卷有
    `### 230.3` 这种写法，也有把子节写成粗体行的；退到父节能把「节存在但子号缺」
    与「整节不存在」区分开，前者不冤判。
    """
    exact = next((s for s in reversed(sections) if s.key == key), None)
    if exact is not None:
        return exact, True
    if "." in key:
        parent = key.rsplit(".", 1)[0]
        found = next((s for s in reversed(sections) if s.key == parent), None)
        if found is not None:
            return found, False
    return None, False


def collect_cites(text: str) -> list[Cite]:
    """抽出月账里对交接卷的全部节引用（两种形态，去重保序）。"""
    cites: list[Cite] = []
    seen: set[tuple[str, int]] = set()
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        found: list[tuple[int, str]] = []
        volumes: dict[str, str] = {}
        for matched in CITE_SECTION_RE.finditer(line):
            key = docs_contract.tok_key(matched.group(2))
            if key:
                found.append((matched.start(), key))
                if matched.group(1):
                    volumes[key] = matched.group(1)     # 引用里点名了卷
        for matched in CITE_VOLUME_RE.finditer(line):
            base = docs_contract.tok_key(matched.group(1))
            if not base:
                continue
            key = base + ("." + matched.group(2) if matched.group(2) else "")
            found.append((matched.start(), key))
        for position, key in sorted(found):
            if (key, number) in seen:
                continue
            seen.add((key, number))
            start = max(0, position - 20)
            cites.append(Cite(key=key, line=number, text=line[start:position + 40].strip(),
                              volume=volumes.get(key)))
    return cites


def ledger_channel(text: str) -> tuple[str | None, bool]:
    """读出卷首声明的归属通道 → (通道名|None, 是否带复核承诺)。

    只看前 20 行：声明是**卷首契约**，正文里顺手提一句不算声明。
    """
    head = "\n".join(text.splitlines()[:20])
    delegated = any(word in head for word in CHANNEL_DELEGATED)
    own = any(word in head for word in CHANNEL_SELF)
    if delegated and own:
        # 两条都写了 ⇒ 取更严的那条（代整理），并要求配对复核承诺。
        return "代整理", bool(RECHECK_RE.search(head))
    if delegated:
        return "代整理", bool(RECHECK_RE.search(head))
    if own:
        return "本机自持", True
    return None, False


# --------------------------------------------------------------------------- #
# 解析：月账发现
# --------------------------------------------------------------------------- #


def discover_ledgers(root: Path) -> list[Ledger]:
    """找出全部月账：`docs/事实源/机器/<机>/月账/YYYY-MM.md`。"""
    base = root.joinpath(*LEDGER_GLOB)
    if not base.is_dir():
        raise SystemExit(
            f"{TITLE} ENV ERROR: 找不到机器分区目录 {base}\n"
            "  月账判据以 `docs/事实源/机器/<机>/月账/` 为唯一落点"
            "（`机器分区索引.md`「月账与交接的归属」2026-11-25 起）。"
        )
    ledgers: list[Ledger] = []
    for machine_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        month_dir = machine_dir / LEDGER_SUBDIR
        if not month_dir.is_dir():
            continue
        for path in sorted(month_dir.glob("*.md")):
            if not re.fullmatch(r"\d{4}-\d{2}\.md", path.name):
                continue   # 专题/方案文件不是月账（与 D18 同款限定）
            month = path.name[:7]
            rel = path.relative_to(root).as_posix()
            ledgers.append(
                Ledger(
                    machine=machine_dir.name,
                    month=month,
                    path=path,
                    rel=rel,
                    text=docs_contract.read_text(str(path)),
                )
            )
    if not ledgers:
        raise SystemExit(
            f"{TITLE} ENV ERROR: {base} 下没有任何 `月账/YYYY-MM.md`\n"
            "  0 份月账 = 无从判定，不是通过（`scanned 0 + exit 0` 正是盲门的定义）。"
        )
    return ledgers


def handover_sections(root: Path, month: str) -> list[Section] | None:
    """读该月交接卷的节表；该月无卷 → None（记为 SKIP，不当通过）。"""
    path = root.joinpath(*HANDOVER_DIR) / f"{month}.md"
    if not path.is_file():
        return None
    return parse_sections(docs_contract.read_text(str(path)))


def handover_volumes(root: Path) -> dict[str, list[Section]]:
    """读**全部**交接卷 → `{YYYY-MM: 节表}`。

    为什么需要全卷：月账会引用**别的卷**的节。实测 2026-11 卷的 SIWPAN 月账引
    `§五十九 ~ §六十一`，而那是 **2026-09 卷**的节 —— 只看本卷就判它"悬空"，
    等于罚了一条**内容正确**的溯源断言。跨卷引用本身合法（历史就是这样传递的），
    判据要判的是「读者能不能顺着这句话找到那一节」。

    只看月卷（`YYYY-MM.md`）：专题/方案文件不是卷（与 D18 同款限定）。
    """
    volumes: dict[str, list[Section]] = {}
    base = root.joinpath(*HANDOVER_DIR)
    if not base.is_dir():
        return volumes
    for path in sorted(base.glob("*.md")):
        if not re.fullmatch(r"\d{4}-\d{2}\.md", path.name):
            continue
        try:
            volumes[path.name[:7]] = parse_sections(docs_contract.read_text(str(path)))
        except OSError:
            continue
    return volumes


def _names_volume(text: str, month: str) -> bool:
    """引用文本里有没有**点名卷**（`交接卷 2026-09 §五十九` / `2026-09 卷` 都算）。

    为什么要求点名：跨卷引用不写卷号，读者在一堆月账里无法判断「§59」是哪一卷的 ——
    那是**歧义**（WARN），不是**造假**（BLOCK）。判据必须能区分这两者。
    """
    return month in text


# --------------------------------------------------------------------------- #
# 判据 C 的 git 实测
# --------------------------------------------------------------------------- #


def _author_month_table(root: Path) -> dict[str, dict] | None:
    """一次读出全部提交 → `{sha: {"month", "subject", "files", "author"}}`，月份按 **author date** 判。

    ## 为什么不用 `git rev-list --count --since/--until`

    `--since/--until` 按 **committer date** 过滤，而 ADR-0012 §D4.1 定的口径是
    **author date**：问「这台机在 2026-10 做了什么」，问的是**干活的时间**；
    committer date 是「记录被写进仓的时间」，会被 rebase / cherry-pick / 补提交改写成
    今天。两者一旦分家，同一笔活会在「谁做的」和「什么时候做的」上给出两套账。

    **实测差异（2026-11 现场，这条判据自己撞出来的）**：
    `git rev-list --count --since=2026-11-01 --until=2026-12-01` = **389**，
    而按 author date 落在 2026-11 的 = **391** —— 月账写的 391 是**对的**，
    判据却拿 389 去判它造假。差的那 2 笔的 committer 时间戳落在窗口边缘，
    被 `--since` 的边界比较挡在门外；`--since` 这种「把日期交给 git 自己解释」的写法，
    解释权不在我们手里（ADR 原文：「用 `git log --since/--until` 而不声明它按哪个日期，
    等于让工具替你选」）。

    所以这里改成：**取全量 → 显式换算到 +08:00 → 按 `YYYY-MM` 判月**。
    643 条提交一次读完，代价可忽略；换来的是「哪一个数、按哪个日期、在哪个时区」全部写在代码里。
    """
    command = ["git", "-c", "core.quotepath=false", "log", "--date=iso-strict",
               "--pretty=format:%x1e%H%x1f%aI%x1f%s", "--name-only", "HEAD"]
    try:
        done = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, encoding="utf-8",
                              errors="replace", check=False)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    table: dict[str, dict] = {}
    for chunk in (done.stdout or "").split("\x1e"):
        if not chunk.strip():
            continue
        lines = chunk.split("\n")
        parts = lines[0].split("\x1f")
        if len(parts) < 3:
            continue
        sha, author, subject = parts[0].strip(), parts[1].strip(), parts[2].strip()
        try:
            stamp = _dt.datetime.fromisoformat(author)
        except ValueError:
            continue
        if stamp.tzinfo is None:                     # 理论上 --date=iso-strict 一定带时区
            stamp = stamp.replace(tzinfo=TZ)
        table[sha] = {
            "month": stamp.astimezone(TZ).strftime("%Y-%m"),   # §D4.2：一律换到 +08:00 再判月
            "subject": subject,
            "files": [ln.strip() for ln in lines[1:] if ln.strip()],
            "author": author,
        }
    return table or None


def _rev_count(root: Path, month: str, pathspec: list[str]) -> int | None:
    """当月提交数（**author date** 口径）。`pathspec` 非空时只数触及这些路径前缀的提交。

    返回 None ⇒ 实测不可用（非工作树 / git 缺失）—— 调用方据此记 SKIP，**不猜**。
    """
    table = _author_month_table(root)
    if table is None:
        return None
    count = 0
    for entry in table.values():
        if entry["month"] != month:
            continue
        if pathspec and not any(
            path == prefix or path.startswith(prefix.rstrip("/") + "/")
            for path in entry["files"] for prefix in pathspec
        ):
            continue
        count += 1
    return count


def default_git_counts(root: Path, month: str, machine: str) -> tuple[int | None, int | None]:
    """(当期总提交数, 可归属本机的提交数)。

    **可归属的口径写死在这里，且只写一次**：当月内触及该机**机器作用域路径**的提交。
    作用域 = `docs/事实源/机器/<机>/**` 与 `facts/machine/<机>(.json|/**)` ——
    这两处是「一机一写」的边界，涉及其它路径的提交无法归到某一台机。
    口径不写在月账里（那会变成第二份真相源），月账只声明**数字**。
    """
    total = _rev_count(root, month, [])
    scoped = _rev_count(root, month, [
        f"docs/事实源/机器/{machine}",
        f"facts/machine/{machine}.json",
        f"facts/machine/{machine}",
    ])
    return total, scoped


def _mentions_machine(text: str, machine: str) -> bool:
    """卷内是否提过这台机。`DESKTOP-KQABATS` 的短式 `KQABATS`（"拉取 KQABATS 的节"）也算提到。"""
    lowered = text.lower()
    name = machine.lower()
    if name in lowered:
        return True
    short = name.split("-", 1)[-1] if name.startswith("desktop-") else name
    return len(short) >= 4 and short in lowered


def parse_declared_counts(section_text: str, heading_text: str) -> dict[str, int]:
    """从「未归属提交」节读出数字。**能声明的就声明，不猜散文。**

    优先级：① 机读行 `<!-- ledger-counts: total=.. attributable=.. unattributed=.. -->`；
    ② 键紧邻数字的表格行 `| 总提交 | 391 |`；③ 标题括号里的 `（2026-11，319 条）`；
    ④ 正文 `本月 391 条提交`。

    ⚠ 不做跨句邻近匹配：实测反例 `可归属率仍停在 18%` 会被读成「可归属=18」——
    假读比读不到更坏（读不到走 UNDETERMINED，假读会判一条真红给一个无辜的数字）。
    """
    out: dict[str, int] = {}
    marker = COUNTS_MARKER.search(section_text) or COUNTS_MARKER.search(heading_text)
    if marker is not None:
        for key, value in re.findall(r"([A-Za-z]+)\s*=\s*(\d+)", marker.group(1)):
            alias = {"total": "总提交", "attributable": "可归属", "unattributed": "未归属"}.get(key.lower())
            if alias:
                out[alias] = int(value)
        if out:
            return out
    for key, value in TABLE_ROW.findall(section_text):
        name = "可归属" if key == "有线索" else key
        out.setdefault(name, int(value))
    if "未归属" not in out:
        matched = HEAD_COUNT.search(heading_text)
        if matched:
            out["未归属"] = int(matched.group(1))
    if "总提交" not in out:
        matched = PROSE_TOTAL.search(section_text)
        if matched:
            out["总提交"] = int(matched.group(1))
    if "可归属" not in out:
        # `391 − 319 = 72` 这类自述也算：只认 `总提交 − 未归属 = N` 的显式算式。
        matched = re.search(r"(\d+)\s*条\s*[（(]\s*\d+\s*[−-]\s*\d+\s*[)）]", section_text)
        if matched:
            out["可归属"] = int(matched.group(1))
    return out


def _section_body(text: str, heading_line: int) -> str:
    """取某标题行到下一个同级或更高级标题之间的正文。"""
    lines = text.splitlines()
    start = heading_line - 1
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        matched = re.match(r"^(#{1,6})\s+", lines[index])
        if matched and len(matched.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start + 1:end])


# --------------------------------------------------------------------------- #
# 判定（纯逻辑；`git_counts` 可注入，自检因此不需要真 git）
# --------------------------------------------------------------------------- #


def judge(
    root: Path,
    ledgers: list[Ledger],
    sections_for,                      # month -> list[Section] | None
    local_machine: str,
    git_counts,
    mutate: set[str] | None = None,
    volumes_for=None,                  # () -> {month: list[Section]}（跨卷引用解析用；可缺省）
) -> Result:
    """跑三条判据。`mutate` 里列出的判据会**摘掉判红分支**（变异验证用）。

    变异不是玩具：它证明「把判红那几行删掉，自检会红」。一个摘不掉红的判据，
    在真实仓里红不红只是运气。
    """
    mutate = mutate or set()
    result = Result()
    local = local_machine.upper()
    all_volumes: dict[str, list[Section]] = {}
    if volumes_for is not None:
        try:
            all_volumes = volumes_for() or {}
        except OSError:
            all_volumes = {}

    for ledger in ledgers:
        is_local = ledger.machine.upper() == local
        enforce_channel = ledger.month >= EFFECTIVE_FROM
        result.scanned += 1
        sections = sections_for(ledger.month)

        # ---- 判据 A：节引用必须落在真实节上 --------------------------------
        if sections is None:
            result.skipped += 1
            result.undetermined.append(Undetermined(
                "A", ledger.rel, 0,
                f"该月无交接卷（`docs/记录/交接/{ledger.month}.md` 不存在）：节引用无从核对",
            ))
            cites: list[Cite] = []
        else:
            cites = collect_cites(ledger.text)
            lines = ledger.text.splitlines()
            cross_machines: dict[str, int] = {}     # 他机名 -> 首次出现的行号
            untagged: dict[str, int] = {}           # 节号 -> 行号
            for cite in cites:
                found, exact = resolve_section(sections, cite.key)
                if found is None and cite.volume and cite.volume != ledger.month:
                    # **点名了卷**：就在被点名的那一卷里找。点名是本卷之外的唯一正当写法，
                    # 所以这里要真去找 —— 点名了却查无此节，那是**断言悬空**（比不点名更硬：
                    # 它给出了可复核的坐标，而那个坐标是空的）。
                    target = all_volumes.get(cite.volume)
                    hit, hit_exact = (resolve_section(target, cite.key) if target else (None, False))
                    if hit is not None:
                        found, exact = hit, hit_exact
                        result.exempted += 1
                    elif "a" not in mutate:
                        result.findings.append(Finding(
                            "A", ledger.rel, cite.line,
                            f"指名引用 `交接卷 {cite.volume} §{cite.key}`，但那一卷里没有这个节号 —— "
                            f"溯源断言悬空（点名了卷，坐标却是空的；原文：{cite.text}）",
                            blocking=is_local,
                        ))
                        continue
                if found is None:
                    line_text = lines[cite.line - 1] if cite.line <= len(lines) else ""
                    # 本卷没有、也没点名 ⇒ 到**全部**卷里找。跨卷引用是历史传递的常态，
                    # 只看本卷会把内容正确的引用判成悬空（2026-11 实测：
                    # SIWPAN 月账引 2026-09 卷的 §五十九~六十一）。
                    hit_months = sorted(
                        month for month, secs in all_volumes.items()
                        if month != ledger.month and resolve_section(secs, cite.key)[0] is not None
                    )
                    if hit_months:
                        named = [m for m in hit_months if _names_volume(line_text, m)]
                        if named:
                            result.exempted += 1          # 行内点名了卷且命中 ⇒ 可追溯，绿
                        elif "a" not in mutate:
                            # 命中但没点名卷 ⇒ **歧义**，单列 WARN，不判红。
                            result.warnings.append(Warning_(
                                "A", ledger.rel, cite.line,
                                f"引用了 §{cite.key}：本卷没有该节，它在 "
                                f"{'/'.join(hit_months)} 卷里 ⇒ 跨卷引用，但**没点名卷**，"
                                f"读者无法从这句话找到它。补成 `交接卷 {hit_months[0]} §{cite.key}` "
                                f"即可（原文：{cite.text}）",
                            ))
                        continue
                    if TOMBSTONE_RE.search(line_text):
                        # 2026-11-26 团队裁决：改为 **WARN**。引用一个已被撤销的节，
                        # 常常是**故意留痕**（记「这条已撤」），不是错引。
                        result.warnings.append(Warning_(
                            "A", ledger.rel, cite.line,
                            f"引用的 §{cite.key} 在交接卷里不存在，同行有撤销/订正标记 ⇒ "
                            f"疑似「引用已被撤掉的节」：若确是按撤销记录留痕，可忽略；"
                            f"若是笔误请改（原文：{cite.text}）",
                        ))
                    elif "a" not in mutate:
                        result.findings.append(Finding(
                            "A", ledger.rel, cite.line,
                            f"引用了交接卷 §{cite.key}，但 `docs/记录/交接/{ledger.month}.md` 里"
                            f"没有这个节号 —— 溯源断言悬空（原文：{cite.text}）",
                            blocking=is_local,
                        ))
                    continue
                if not exact:
                    # 2026-11-26 第二次裁决：**保持 UNDET，不降级**。
                    # 第一次我按"父节存在即引用成立"改成了 OK —— 那是**改判据迁就错数据**。
                    # 核原文后事实相反：`§225` 只有 225.1/.2/.3，月账引的 `.6/.7/.8` 不存在；
                    # `§4.1` 在 2026-10 卷里只被引用、从未定义；`§224` 两卷都没有。
                    # ⇒ "节存在但子号不可核"是**准确**的判定：子号写错，下一个人按它去查必然查不到。
                    # 等 Docu 按真身改对引用，这几条自己就消失（判据不需要动）。
                    result.undetermined.append(Undetermined(
                        "A", ledger.rel, cite.line,
                        f"§{cite.key} 无同名子节，退到父节 §{found.key}"
                        f"（「{found.heading[:28]}」）判定：**节存在但子号不可核** —— "
                        f"子号多半写错了，请按交接卷真身改引用（父节下实际有哪些子号，见该节正文）",
                    ))
                    continue
                if found.machine is None:
                    untagged.setdefault(cite.key, cite.line)
                elif found.machine.upper() == CROSS_MACHINE:
                    result.exempted += 1
                elif found.machine.upper() != ledger.machine.upper():
                    cross_machines.setdefault(found.machine.upper(), cite.line)
                else:
                    result.exempted += 1

            # A2（卷级判定）：引他机节本身是**铁律 6 的规定动作**，不判红；判的是
            # 「整卷从头到尾都没出现过该机名」—— 那才是把别人的自述当成本卷内容
            # （读者无法从卷内任何地方知道这节的归属）。按机去重，避免一次判出十几条噪声。
            for machine, line in sorted(cross_machines.items()):
                if _mentions_machine(ledger.text, machine) or not enforce_channel:
                    result.exempted += 1
                    continue
                if "a2" not in mutate:
                    result.findings.append(Finding(
                        "A2", ledger.rel, line,
                        f"引用了 @{machine} 的节，但整卷从未出现该机名：读者无从判断这节不是本卷内容"
                        f"（铁律 6 允许跨机引用，前提是写明是谁的）",
                        blocking=is_local,
                    ))
            for key, line in sorted(untagged.items(), key=lambda item: item[1]):
                if not enforce_channel:
                    result.exempted += 1
                    continue
                # 2026-11-26 团队裁决：改为 **WARN**。理由：那些节在 D18 豁免区内
                # （历史节、新规则不追溯），**引用它们是正当的**；判据只能提示
                # 「该节没有机器标注」，不能判「不可判定」—— 后者等于拿新规矩
                # 追溯旧数据，而 D18 明确不追溯。
                result.warnings.append(Warning_(
                    "A2", ledger.rel, line,
                    f"引用的 §{key} 标题没有 `@机名` 标注（D18 豁免区：历史节不追溯）——"
                    f"引用本身正当，只是读者无法从该节判断归属",
                ))

        # ---- 判据 B：归属通道声明必须存在且成对 ----------------------------
        has_entries = bool(re.search(r"^##\s+20\d\d-\d\d-\d\d", ledger.text, re.MULTILINE))
        channel, paired = ledger_channel(ledger.text)
        if not has_entries or not enforce_channel:
            result.exempted += 1
        elif channel is None:
            if "b" not in mutate:
                result.findings.append(Finding(
                    "B", ledger.rel, 1,
                    "卷首未声明归属通道：铁律 6 只认两条 ——「本机自持」或「代整理 + 待该机复核」。"
                    "不写通道，读者无法判断这份卷是事实方自述还是他人转述",
                    blocking=not is_local,   # 他机卷：B 是本判据唯一对他机阻断的一条
                ))
        elif channel == "代整理" and not paired:
            if "b" not in mutate:
                result.findings.append(Finding(
                    "B", ledger.rel, 1,
                    "声明了「代整理」却没有配对「待…复核」：半张声明 = 把铁律 6 的合法通道"
                    "用成免检章（代笔方擅自替事实方定论）",
                    blocking=not is_local,
                ))
        else:
            result.exempted += 1

        # ---- 判据 C：未归属提交的数字必须与 git 实测一致 --------------------
        result_c = _judge_counts(root, ledger, is_local, git_counts, mutate)
        result.findings.extend(result_c.findings)
        result.undetermined.extend(result_c.undetermined)
        result.skipped += result_c.skipped
        result.exempted += result_c.exempted

    return result


def _judge_counts(root: Path, ledger: Ledger, is_local: bool, git_counts, mutate: set[str]) -> Result:
    """判据 C：三件事，各自独立成条，避免「一条不符就整节不可判」。"""
    out = Result()
    lines = ledger.text.splitlines()
    line_no = next((index for index, line in enumerate(lines, start=1)
                    if line.startswith("#") and UNATTRIBUTED_HEAD in line), 0)
    if not line_no:
        out.skipped += 1
        out.undetermined.append(Undetermined(
            "C", ledger.rel, 0,
            f"没有「{UNATTRIBUTED_HEAD}」节：本判据当期无对象（skipped 不是通过）",
        ))
        return out

    heading = lines[line_no - 1]
    declared = parse_declared_counts(_section_body(ledger.text, line_no), heading)
    total_measured, attributable_measured = git_counts(root, ledger.month, ledger.machine)
    window = _window_text(ledger.month)

    if total_measured is None:
        out.skipped += 1
        out.undetermined.append(Undetermined(
            "C", ledger.rel, line_no, "git 实测不可用（非工作树 / git 缺失）：数字无从核对",
        ))
        return out

    # C1 总提交：与 git 当月实测比。窗口口径写进报错文案 —— 数字对不上时，
    # 第一件事是让对方能一行命令复现，而不是争论「谁算错了」。
    if "总提交" not in declared:
        out.undetermined.append(Undetermined(
            "C", ledger.rel, line_no,
            f"该节没声明「总提交」数（机读行 `<!-- ledger-counts: total=… -->` 或表格行均可）："
            f"git 实测 {window} = {total_measured} 条",
        ))
    elif declared["总提交"] != total_measured:
        out.findings.append(Finding(
            "C", ledger.rel, line_no,
            f"「总提交」自述 {declared['总提交']}，git 实测 {total_measured}"
            f"（口径：**author date** / tz={TZ_NAME} / 窗口 {window}）"
            f"—— 复现：`git log --pretty=%aI | grep -c '^{ledger.month}'`"
            f"（**不要**用 `git rev-list --count --since/--until`：那按 committer date，"
            f"会把它判成另一个数）",
            blocking=is_local and "c" not in mutate,
        ))
    else:
        out.exempted += 1

    # C2 算术自洽：未归属 == 总提交 − 可归属。这一条不依赖 git，只查自述内部是否自相矛盾。
    if {"总提交", "可归属", "未归属"} <= declared.keys():
        if "c" not in mutate and declared["未归属"] != declared["总提交"] - declared["可归属"]:
            out.findings.append(Finding(
                "C", ledger.rel, line_no,
                f"「未归属」自述 {declared['未归属']}，但自述的 总提交 {declared['总提交']} − "
                f"可归属 {declared['可归属']} = {declared['总提交'] - declared['可归属']}：节内自相矛盾",
                blocking=is_local,
            ))
        else:
            out.exempted += 1
            # 声明了「可归属」也要把**实测候选**摆出来：C1/C2 只核了两个能独立重算的数
            # （总提交、节内算术），「可归属」本身取决于"什么算线索"的定义 ——
            # 声明值与三种实测口径**全都对不上**时，读者有权知道（WARN，不阻断）。
            # 实测：2026-11 月账声明「有线索 72」，而三种口径给出 31 / 66 / 80。
            clues = _measured_clues(root, ledger.month)
            candidates = {clues["标题带机"], clues["触及分区"], clues["并集"]}
            if declared["可归属"] not in candidates and "c" not in mutate:
                out.warnings.append(Warning_(
                    "C", ledger.rel, line_no,
                    f"「可归属」声明 {declared['可归属']}，与三种实测口径都不等"
                    f"（标题带 @机 {clues['标题带机']} / 触及分区 {clues['触及分区']} / "
                    f"并集 {clues['并集']}，均按 author date）—— 数字本身可能没错，"
                    f"但**口径没写**，别人无法复现 ⇒ 请在卷内写明用的是哪一种",
                ))
    elif "未归属" in declared:
        # 声明了未归属却没声明可归属口径 ⇒ 不可核，但**把实测候选一并打出来**，
        # 让下一个人不用自己重算三种口径（引用体量与实测口径不一致是常态）。
        clues = _measured_clues(root, ledger.month)
        out.undetermined.append(Undetermined(
            "C", ledger.rel, line_no,
            f"该节声明未归属 {declared['未归属']}，但没声明「可归属/有线索」数 ⇒ 算术不可核。"
            f"实测候选（{window}）：标题带 @机 {clues['标题带机']} 条、"
            f"触及机器分区路径 {clues['触及分区']} 条、并集 {clues['并集']} 条、"
            f"总提交 {total_measured} 条；本机路径口径 {attributable_measured} 条",
        ))
    return out


def _window_text(month: str) -> str:
    year, mon = month.split("-")
    nxt = f"{int(year) + (1 if int(mon) == 12 else 0)}-{(int(mon) % 12) + 1:02d}"
    return f"{year}-{mon}-01..{nxt}-01"


def _measured_clues(root: Path, month: str) -> dict[str, int]:
    """三种口径的「可归属」实测值，供自述与实测对账用（只报告，不判）。

    为什么给三种而不给一种：`未归属` 的分母取决于「什么算线索」——本仓月账用的是
    「标题带 @机 ∪ 触及机器分区」的并集；而「只数本机路径」给出的是另一组数。
    三个都摆出来，读者才能判断自述用的是哪一种 —— 只给一个数就是替对方选口径。

    ⚠ 全部按 **author date** 口径（与 C1 同一个真相源，见 `_author_month_table`）：
    口径不一致的两个数放在一起比，本身就是一种假证据。
    """
    table = _author_month_table(root) or {}
    tagged = touched = union = 0
    tag_re = re.compile(r"@`?(SIWPAN|DESKTOP-KQABATS|DESKTOP-8RSV60V|KQABATS|8RSV60V)")
    scopes = ("docs/事实源/机器", "facts/machine")
    for entry in table.values():
        if entry["month"] != month:
            continue
        has_tag = bool(tag_re.search(entry["subject"]))
        has_path = any(path.startswith(scope) for path in entry["files"] for scope in scopes)
        tagged += 1 if has_tag else 0
        touched += 1 if has_path else 0
        union += 1 if (has_tag or has_path) else 0
    return {"标题带机": tagged, "触及分区": touched, "并集": union}


# 2026-11-26：`_rev_count_predicate` / `_rev_count_union` / `_rev_list` **已删**。
# 它们全都建立在 `git log --since/--until` 上（committer date 口径），正是 C 条
# 把 391 判成 389 的根源。删而不是留着「以后可能用」：同一份文件里并存两种时间口径，
# 下一个改判据的人一定会选错那一个 —— 删掉错误口径比注释警告有效。


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #


def render(result: Result, strict: bool, verbose: bool) -> int:
    for finding in result.findings:
        print(finding.render())
    for item in result.warnings:
        # WARN 单列在 BLOCK 之后、UNDET 之前：它比 UNDET 更具指向性（已定位到具体卷），
        # 但**不参与退出码** —— 歧义该提示，不该阻断。
        print(item.render())
    for item in result.undetermined:
        if verbose or True:            # UNDETERMINED 是一等结论，永远逐条打印
            print(item.render())
    blocking = result.blocking
    print()
    # 与 govlib 同款的摘要行：让 `check_blind_gates.py` 把本判据判成 measured
    # 而不是 undetermined（本判据确实报了读数，不该被当成「没量」）。
    print(f"{TITLE}: scanned {result.scanned} file(s); blocking {len(blocking)}; "
          f"exempted {result.exempted}; skipped {result.skipped}; warns {len(result.warnings)}.")
    if result.caliber:
        # ADR-0012 §D4.5：口径行必须进产物。没有它，391 与 389 谁对无法判、半年后也无法比。
        print(f"CALIBER {result.caliber}")
    print(f"UNDETERMINED: {len(result.undetermined)}"
          f"（{'不计入通过' if result.undetermined else '无'}）")
    if blocking:
        print(f"=> 判红 {len(blocking)} 条")
        return EXIT_BLOCKING
    if result.undetermined and strict:
        print("=> 无阻断但存在不可判定项：判定不完整（不是通过）。"
              "加 `--allow-undetermined` 可只报告不改退出码。")
        return EXIT_UNDETERMINED
    return EXIT_OK


# --------------------------------------------------------------------------- #
# 自检：正例 + 三条负对照 + 变异验证
# --------------------------------------------------------------------------- #

_VOLUME = """# 会话交接 · 2026-11 卷

### `@SIWPAN`（2 节）

## 二百三十一、@SIWPAN 收掉三条待办（2026-11-25）

### 231.1 处置
### 231.2 验证

## 二百三十二、@`DESKTOP-KQABATS` 拉取 30 笔
"""

_LEDGER_OK = """# SIWPAN 月账 · 2026-11

> **本机月度工作记录**。归属本机事实源、本机自持（铁律 6）。

## 2026-11-25 · 收掉三条待办

按交接卷 §231 推进；子节见交接卷 §231.2。另 §232 是他机节，本机只是引用。
"""

_LEDGER_BAD_CITE = _LEDGER_OK.replace("交接卷 §231 推进", "交接卷 §999 推进").replace(
    "；子节见交接卷 §231.2。另 §232 是他机节，本机只是引用。", "。")

_LEDGER_TOMBSTONE = """# SIWPAN 月账 · 2026-11

> **本机月度工作记录**。归属本机事实源、本机自持（铁律 6）。

## 2026-11-25 · 归属订正

上一轮把流水写进了交接卷 §224，该错误提交已撤销并恢复原状。
"""

_LEDGER_NO_CHANNEL = """# DESKTOP-KQABATS 月账 · 2026-11

> 条目只增不改。

## 2026-11-25 · 做了点事

按交接卷 §231 推进。
"""

_LEDGER_HALF_CHANNEL = """# DESKTOP-KQABATS 月账 · 2026-11

> **代整理**：本卷由 @SIWPAN 于 2026-11-25 从交接卷 §231 代为归档。

## 2026-11-25 · 做了点事

按交接卷 §231 推进。
"""

_LEDGER_COUNTS_OK = """# SIWPAN 月账 · 2026-11

> **本机月度工作记录**。归属本机事实源、本机自持（铁律 6）。

## 2026-11-25 · 未归属提交

| 项 | 数 |
| --- | --- |
| 总提交 | 391 |
| 可归属 | 33 |
| 未归属 | 358 |
"""

_LEDGER_COUNTS_BAD = _LEDGER_COUNTS_OK.replace("| 未归属 | 358 |", "| 未归属 | 357 |")

#: 子号负对照：`§231.9` 不存在（`_VOLUME` 里只有 231.1 / 231.2）。
#: 这一条守的是"父节存在 ≠ 引用成立"：把子号错判成 OK，月账就会永远带着错的子号，
#: 而下一个人按 §231.9 去查必然查不到（2026-11 现场就是 §225.6/.7/.8 与 §4.1）。
_LEDGER_BAD_SUB = _LEDGER_OK.replace("§231.2", "§231.9")

#: A2 负对照：引他机节，整卷从不提这台机。
_LEDGER_HIDDEN_CROSS = """# SIWPAN 月账 · 2026-11

> **本机月度工作记录**。归属本机事实源、本机自持（铁律 6）。

## 2026-11-25 · 借用了一节的做法

按交接卷 §232 的做法把拉取流程收敛成一条命令，本机照做后全绿。
"""

#: A2 正例：同一节，但卷内写明了它属于谁。
_LEDGER_NAMED_CROSS = _LEDGER_HIDDEN_CROSS.replace(
    "按交接卷 §232 的做法", "按 KQABATS 的交接卷 §232 的做法")

#: 跨卷引用的三种形态（2026-11-26 现场：SIWPAN 月账引 2026-09 卷的 §五十九~六十一）。
_VOLUME_2026_09 = """# 会话交接 · 2026-09 卷

## 五十九、九月的一条（2026-09-25）

## 六十、九月又一条（2026-09-26）
"""
_VOLUME_2026_10 = """# 会话交接 · 2026-10 卷

## 一百一十、十月的一条（2026-10-20）
"""
_CROSS_HEAD = """# SIWPAN 月账 · 2026-11

> **本机月度工作记录**。归属本机事实源、本机自持（铁律 6）。

## 2026-11-25 · 接着九月的活干
"""
#: ① 跨卷引用**没点名卷** ⇒ 歧义（WARN，不阻断）
_LEDGER_CROSS_UNNAMED = _CROSS_HEAD + "\n按交接卷 §五十九 的做法把流程收敛成一条命令。\n"
#: ② 跨卷引用**点名了卷**且该卷有该节 ⇒ 可追溯（绿）
_LEDGER_CROSS_NAMED = _CROSS_HEAD + "\n按交接卷 2026-09 §五十九 的做法把流程收敛成一条命令。\n"
#: ③ 点名了卷，但**那一卷没有**该节 ⇒ 坐标是空的，比不点名更硬（红）
_LEDGER_CROSS_WRONG_VOLUME = _CROSS_HEAD + "\n按交接卷 2026-10 §五十九 的做法推进。\n"


def _sandbox(files: dict[str, str]) -> tempfile.TemporaryDirectory:
    """把夹具写进临时仓（月账落点与真仓同构）→ 判据读到的路径逻辑与真跑一致。"""
    tmp = tempfile.TemporaryDirectory(prefix="machine-ledger-selfcheck-")
    root = Path(tmp.name)
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp


def _ledgers_in(root: Path) -> list[Ledger]:
    return discover_ledgers(root)


def _judge_fixture(files: dict[str, str], local: str = "SIWPAN",
                   mutate: set[str] | None = None,
                   git_counts=None) -> Result:
    tmp = _sandbox(files)
    try:
        root = Path(tmp.name)
        ledgers = _ledgers_in(root)
        cache: dict[str, list[Section] | None] = {}

        def sections_for(month: str):
            if month not in cache:
                cache[month] = handover_sections(root, month)
            return cache[month]

        return judge(
            root, ledgers, sections_for, local,
            git_counts or (lambda _root, _month, _machine: (391, 33)),
            mutate=mutate,
            # 全卷都在沙箱里 ⇒ 跨卷解析走真实路径（夹具写哪几卷，就能解析哪几卷）
            volumes_for=lambda: handover_volumes(root),
        )
    finally:
        tmp.cleanup()


def _selfcheck_author_boundary() -> tuple[bool, str]:
    """钉住**时区边界**：2026-11-01 上午(+08:00) 的提交必须计入 2026-11。

    为什么必须钉这条：`git rev-list --count --since=2026-11-01` 在这个环境里把
    「2026-11-01 08:00 +0800 之前」的提交全部漏掉（`--since` 的日期串被当成 UTC 零点
    ⇒ 08:00 +0800 = 00:00 UTC 之后才算进窗口）。实测被吃掉的是这两笔：

        68b19f7c  2026-11-01T07:48:04+08:00
        ea6ef1da  2026-11-01T07:29:25+08:00

    ⇒ 389 = 391 − 2。**月账自述 391 是对的。**

    （口径修正：早前转述的「00:57 / 01:22 两笔」不是被吃掉的那两笔，是 11-02 的提交；
      真实样本是上面的 07:29 / 07:48。四种时刻一并钉进来，任何一处回退都会红。）

    不钉住它的后果：下次有人"顺手优化"成 `--since` 就会**静默**退回 389，
    而 389 看起来同样合理 —— 判据的输入边界错了，结论照样自洽。
    """
    stamps = ["2026-11-01T00:57:00+08:00", "2026-11-01T01:22:00+08:00",
              "2026-11-01T07:29:25+08:00", "2026-11-01T07:48:04+08:00"]
    with tempfile.TemporaryDirectory(prefix="machine-ledger-boundary-") as tmp:
        repo = Path(tmp)
        for step in (["git", "init", "-q", "-b", "main"],
                     ["git", "config", "user.email", "selfcheck@example.invalid"],
                     ["git", "config", "user.name", "SelfCheck"],
                     ["git", "config", "commit.gpgsign", "false"]):
            subprocess.run(step, cwd=str(repo), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for index, stamp in enumerate(stamps):
            (repo / f"f{index}.md").write_text(f"{index}\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=str(repo), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            env = dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
            done = subprocess.run(["git", "commit", "-q", "-m", f"chore: 边界样本 {stamp}"],
                                  cwd=str(repo), env=env, check=False,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                  encoding="utf-8", errors="replace")
            if done.returncode != 0:
                return False, f"夹具提交失败：{(done.stderr or '')[:120]}"

        counted = _rev_count(repo, "2026-11", [])
        old = subprocess.run(
            ["git", "rev-list", "--count", "--since=2026-11-01", "--until=2026-12-01", "HEAD"],
            cwd=str(repo), check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace").stdout.strip()
        note = f"边界样本 4 笔：本判据计 {counted} 笔；旧口径(--since) 计 {old} 笔"
        if counted != len(stamps):
            return False, f"应全部计入 2026-11（{len(stamps)} 笔），实际 {counted}（{note}）"
        if old == str(len(stamps)):
            return False, f"旧口径也数全了 ⇒ 这条负对照空转，钉不住回退（{note}）"
        return True, note


def _selfcheck_author_window() -> tuple[bool, str]:
    """C 条口径的**真 git 负对照**：造一笔「author date 在 11 月、committer date 在 10 月」的提交。

    为什么必须真造：`git rev-list --count --since/--until` 与 author-date 判月在
    **大多数提交上给出同一个数**（实测 643 条里只差 2 条），所以"只比总数"验不出区别。
    只有把两个时间戳**故意拉开到跨月**，才能证明这条判据用的是 author date ——
    否则它就是空转（换回旧实现也照样绿）。

    真实来源：rebase / cherry-pick / 补提交会把 committer date 改写成今天，
    而 author date 保留原干活时刻（ADR-0012 §D4.1 的理由）。
    """
    with tempfile.TemporaryDirectory(prefix="machine-ledger-window-") as tmp:
        repo = Path(tmp)
        steps = [
            ["git", "init", "-q", "-b", "main"],
            ["git", "config", "user.email", "selfcheck@example.invalid"],
            ["git", "config", "user.name", "SelfCheck"],
            ["git", "config", "commit.gpgsign", "false"],
        ]
        for step in steps:
            subprocess.run(step, cwd=str(repo), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (repo / "f.md").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = dict(os.environ,
                   GIT_AUTHOR_DATE="2026-11-01T00:30:00+08:00",     # 干活时间：11 月
                   GIT_COMMITTER_DATE="2026-10-31T23:00:00+08:00")   # 写入时间：10 月
        done = subprocess.run(["git", "commit", "-q", "-m", "feat: 跨月边界的提交"],
                              cwd=str(repo), env=env, check=False,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              encoding="utf-8", errors="replace")
        if done.returncode != 0:
            return False, f"夹具提交失败：{(done.stderr or '')[:120]}"

        by_author = _rev_count(repo, "2026-11", [])
        by_committer = subprocess.run(
            ["git", "rev-list", "--count", "--since=2026-11-01", "--until=2026-12-01", "HEAD"],
            cwd=str(repo), check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", errors="replace").stdout.strip()
        got = f"作者日 11 月 = {by_author}；旧口径(rev-list --since) = {by_committer}"
        if by_author != 1:
            return False, f"应按 author date 计入 2026-11，实际 {by_author}（{got}）"
        if by_committer in ("", "1"):
            return False, (f"旧口径也给了同样的数，无法区分两种口径 ⇒ 这条自检是空转（{got}）")
        return True, got


def selfcheck(mutate: set[str]) -> int:
    """正例必须静得下来，负对照必须红得出来；变异体存活必须让自检本身红。"""
    volume_rel = "docs/记录/交接/2026-11.md"
    ok_rel = "docs/事实源/机器/SIWPAN/月账/2026-11.md"
    other_rel = "docs/事实源/机器/DESKTOP-KQABATS/月账/2026-11.md"

    caught: list[str] = []
    clean: list[str] = []
    misreports: list[str] = []

    def expect_block(label: str, files: dict[str, str], criterion: str, local: str = "SIWPAN") -> None:
        # 注意：这里**不因 --mutate 而改变期望**。变异验证的语义是「摘掉判红分支后，
        # 这条负对照必须不再被抓」⇔「自检必须变红（misreports>0）」。若这里跟着变异
        # 放宽期望，变异验证就退化成恒真断言（`调试铁律 65`：恒返回同一值的判据不构成证据）。
        got = _judge_fixture(files, local=local, mutate=mutate)
        if any(f.criterion == criterion for f in got.blocking):
            caught.append(label)
        else:
            misreports.append(
                f"{label}：期望 {criterion} 判红，实际 "
                f"blocking={len(got.blocking)} undetermined={len(got.undetermined)}"
                + ("（变异体存活 —— 这一例没有真正依赖该判红分支）" if mutate else "")
            )

    def expect_warn(label: str, files: dict[str, str], criterion: str = "A",
                    local: str = "SIWPAN") -> None:
        """期望：**不阻断、但有 WARN 单列**。

        这条口径是本次新增的第三档：把「歧义」和「造假」判成同一个红，
        团队的下一个动作是加豁免而不是修数据。
        """
        got = _judge_fixture(files, local=local, mutate=mutate)
        if got.blocking:
            misreports.append(f"{label}：期望只 WARN，实际判红 {len(got.blocking)} 条")
        elif not any(w.criterion == criterion for w in got.warnings):
            misreports.append(f"{label}：期望有 {criterion} WARN，实际 warnings={len(got.warnings)}"
                              "（跨卷引用既不红也不提示 ⇒ 歧义被静默吞掉）")
        else:
            clean.append(label)

    def expect_undetermined(label: str, files: dict[str, str], criterion: str = "A",
                            local: str = "SIWPAN") -> None:
        """期望：**不阻断但记 UNDET** —— 子号错这类"判得了、但不能替人改"的结论。"""
        got = _judge_fixture(files, local=local, mutate=mutate)
        if got.blocking:
            misreports.append(f"{label}：期望只 UNDET，实际判红 {len(got.blocking)} 条")
        elif not any(u.criterion == criterion for u in got.undetermined):
            misreports.append(f"{label}：期望 {criterion} UNDET，实际 undetermined="
                              f"{len(got.undetermined)}（被当成绿了 —— 错子号会静默存活）")
        else:
            clean.append(label)

    def expect_quiet(label: str, files: dict[str, str], local: str = "SIWPAN") -> None:
        got = _judge_fixture(files, local=local, mutate=mutate)
        if got.blocking:
            misreports.append(f"{label}：期望静默，实际判红 {len(got.blocking)} 条："
                              + "；".join(f.message[:60] for f in got.blocking))
        else:
            clean.append(label)

    base = {volume_rel: _VOLUME, ok_rel: _LEDGER_OK}

    # ---- 正例：三个通道都合法 ⇒ 必须静得下来（只验红不验静，等于允许误报）
    expect_quiet("A/B 正例：引真实节 + 卷首自持", base)
    expect_quiet("A 正例：撤销标记的悬空引用记 UNDETERMINED 不判红",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_TOMBSTONE})
    expect_quiet("C 正例：三个数字与 git 实测一致",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_COUNTS_OK})
    expect_quiet("C 正例：无该节 ⇒ skipped 不判红", base)

    # ---- 负对照一：造假节号（A）
    expect_block("A 负对照：引用不存在的 §999",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_BAD_CITE}, "A")

    # ---- 负对照二：缺来源标注（B）—— 异机卷没声明通道
    expect_block("B 负对照：异机卷未声明归属通道",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_OK, other_rel: _LEDGER_NO_CHANNEL},
                 "B", local="SIWPAN")
    expect_block("B 负对照：「代整理」缺「待…复核」",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_OK, other_rel: _LEDGER_HALF_CHANNEL},
                 "B", local="SIWPAN")

    # ---- 负对照二·A2：引他机节却整卷不提该机（把别人的自述当本卷内容）
    expect_block("A2 负对照：引他机节且卷内从不提该机",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_HIDDEN_CROSS}, "A2")
    expect_quiet("A2 正例：同一节但卷内写明该机",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_NAMED_CROSS})

    # ---- 负对照三：未归属数字不符（C）
    expect_block("C 负对照：未归属 357 ≠ 391-33",
                 {volume_rel: _VOLUME, ok_rel: _LEDGER_COUNTS_BAD}, "C")

    # ---- 跨卷引用（2026-11-26 新增）：点名 / 不点名 / 点错卷，三档必须分开
    cross_base = {volume_rel: _VOLUME, "docs/记录/交接/2026-09.md": _VOLUME_2026_09,
                  "docs/记录/交接/2026-10.md": _VOLUME_2026_10}
    expect_warn("A 跨卷负对照：引别卷的节但没点名卷 ⇒ WARN 单列（不判红）",
                {**cross_base, ok_rel: _LEDGER_CROSS_UNNAMED})
    expect_quiet("A 跨卷正例：点名 `2026-09` 且该卷有该节 ⇒ 绿",
                 {**cross_base, ok_rel: _LEDGER_CROSS_NAMED})
    expect_block("A 跨卷负对照：点名 2026-10，但那一卷没有 §五十九 ⇒ 红",
                 {**cross_base, ok_rel: _LEDGER_CROSS_WRONG_VOLUME}, "A")

    # ---- 子号错不许降级（2026-11-26 裁决）：父节存在 ≠ 引用成立
    expect_undetermined("A 负对照：子号写错（§231.9 不存在）⇒ 保持 UNDET，不得当成绿",
                        {volume_rel: _VOLUME, ok_rel: _LEDGER_BAD_SUB})

    # ---- C 条口径（2026-11-26 新增）：窗口按 **author date**，不是 committer date
    window_ok, window_note = _selfcheck_author_window()
    if window_ok:
        clean.append(f"C 口径：author date 判月（{window_note}）")
    else:
        misreports.append(f"C 口径：author date 判月 —— {window_note}")

    # ---- 时区边界钉死（2026-11-26 新增）：11-01 上午的提交必须算进 11 月
    boundary_ok, boundary_note = _selfcheck_author_boundary()
    if boundary_ok:
        clean.append(f"C 口径：时区边界（{boundary_note}）")
    else:
        misreports.append(f"C 口径：时区边界 —— {boundary_note}")

    # ---- 报错也要报：假绿一例（若判据永远绿，上面全是自欺）
    print(f'SELFCHECK {{"caught": {len(caught)}, "clean": {len(clean)}, '
          f'"misreports": {len(misreports)}}}')
    for label in caught:
        print(f"  caught  ✓ {label}")
    for label in clean:
        print(f"  clean   ✓ {label}")
    for label in misreports:
        print(f"  MISREPORT ✗ {label}")
    if mutate:
        verdict = ("变异被抓住 ✓（摘掉判红分支后自检失败 ⇒ 该分支承重）"
                   if misreports else "变异**未被抓住** ✗（判红分支摘掉后自检仍全绿 ⇒ 该判据没在承重）")
        print(f"  （变异模式 --mutate {','.join(sorted(mutate))}：{verdict}）")
    return 0 if (not misreports and caught) else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def configure_stdio() -> None:
    """Windows 控制台默认 cp936，打印中文诊断会 UnicodeEncodeError 并吞掉整份报告。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 老 Python / 被替换的 stream 都可能不支持
            pass


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        prog="check_machine_ledger.py",
        description="月账一致性判据（A 节引用 / B 归属通道 / C 未归属数字）",
    )
    parser.add_argument("--root", help="仓根（缺省：当前 git 工作树根）")
    parser.add_argument("--selfcheck", action="store_true", help="跑自检（含三条负对照）")
    parser.add_argument("--mutate", default="",
                        help="变异验证：逗号分隔的 a/b/c，摘掉对应判据的判红分支（仅与 --selfcheck 合用）")
    parser.add_argument("--allow-undetermined", action="store_true",
                        help="存在不可判定项时不改退出码（仍打印）")
    parser.add_argument("--verbose", action="store_true", help="打印全部豁免与不可判定明细")
    parser.add_argument("--local-machine", default=os.environ.get("ALLIN_MACHINE") or None,
                        help="本机标识（缺省：hostname 大写；用于区分本机卷与他机卷）")
    args = parser.parse_args(argv)

    mutate = {token.strip().lower() for token in args.mutate.split(",") if token.strip()}
    unknown = mutate - {"a", "b", "c"}
    if unknown:
        print(f"{TITLE} USAGE ERROR: --mutate 只认 a/b/c，收到 {','.join(sorted(unknown))}", file=sys.stderr)
        return EXIT_ENV
    if mutate and not args.selfcheck:
        print(f"{TITLE} USAGE ERROR: --mutate 只与 --selfcheck 合用（变异验证的对象是自检）", file=sys.stderr)
        return EXIT_ENV

    if args.selfcheck:
        return selfcheck(mutate)

    root = Path(args.root).resolve() if args.root else _git_toplevel()
    if root is None or not root.is_dir():
        print(f"{TITLE} ENV ERROR: 定位不到仓根（用 --root 显式指定）", file=sys.stderr)
        return EXIT_ENV
    local = (args.local_machine or _hostname()).upper()

    try:
        ledgers = discover_ledgers(root)
    except SystemExit as error:
        print(str(error), file=sys.stderr)
        return EXIT_ENV

    cache: dict[str, list[Section] | None] = {}

    def sections_for(month: str):
        if month not in cache:
            cache[month] = handover_sections(root, month)
        return cache[month]

    result = judge(root, ledgers, sections_for, local, default_git_counts, mutate=set(),
                   volumes_for=lambda: handover_volumes(root))
    result.caliber = (f"since/until 语义 = author date（不用 committer date）/ "
                      f"tz = {TZ_NAME} / 提交域 = HEAD@{_head_sha(root) or '?'} / "
                      f"判据 = A 节引用(A/B/C) · B 归属通道 · C 三个数字")
    print(f"# 本机标识 {local}；判 {len(ledgers)} 份月账："
          + "、".join(f"{item.machine}/{item.month}" for item in ledgers))
    return render(result, strict=not args.allow_undetermined, verbose=args.verbose)


def _head_sha(root: Path) -> str | None:
    """口径行要写清「依据哪个提交」（ADR-0012 §D4.5）。取不到就写 `?`，不猜。"""
    try:
        done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(root),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              encoding="utf-8", errors="replace", check=False)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return (done.stdout or "").strip() or None


def _hostname() -> str:
    import platform

    return platform.node()


def _git_toplevel() -> Path | None:
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              encoding="utf-8", errors="replace", check=False)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return Path((done.stdout or "").strip())


if __name__ == "__main__":
    sys.exit(main())
