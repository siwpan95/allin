#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月账取证生成器（`machine_ledger.py`）—— 给「这笔活是哪台机器干的」出**分级证据**。

## 它不做的事（先说边界）

它**不写叙事、不下结论、不改月账**。月账是各机的运行时载体
（`docs/事实源/机器/<机>/月账/<YYYY-MM>.md`）；本工具只产出一份**可复核的证据汇总**，
落在 `tools/gate/audit/machine-ledger/`（audit 已被 gitignore）。写账的人拿它当底稿，
判断留给人。

**它不是判据，不进 `run_all_gates.sh`**：判据坏了要拦提交，取证工具坏了只该少一份底稿。
让一个"出底稿的工具"有权拦提交，是把两件事的责任混在一起。

## 为什么需要它

实测死结（2026-11）：391 笔提交里 32 笔标题带 `@机器`，57 笔触及某机分区，
**325 笔（83%）任何来源都查不出机器**；而 author/committer 恒为同一个共享身份
`siwpan <siwpan@users.noreply.gitee.com>` —— `git shortlog` / `.mailmap` 都救不了
（官方文档明说共享账号时统计无法区分实际参与者）。字段里没有，就只能**分级取证**，
并且**如实报告查不出来的那部分**。

## 三源分级（证据强度不同，绝不可混用）

| 级 | 来源 | 强度 | 能否单独作归属依据 |
| --- | --- | --- | --- |
| **A** | 交接卷 `docs/记录/交接/<YYYY-MM>.md` 里标了 `@<STEM>` 的**节**（节号 + 标题 + 日期） | 强 | **能**（该机自述） |
| **B** | 提交标题带 `@<STEM>`（含 `@KQABATS` 这类短形态） | 中 | **能**（作者当场声明） |
| **C** | 提交**触及** `<STEM>` 分区文件 | 弱 | **不能**（只作旁证） |
| **D** | 三源都没有 | —— | 如实计数并列出 |

> A 是**文档级**证据（某台机认领了哪些节），落不到具体提交上。所以 A 与 B/C/D
> 是两个轴，**不能相加**成「某机做了多少笔提交」。

## 两条硬边界（用户拍板 + ADR 明令）

### 1. `SPLIT_DATE = 2026-10-30`：此前归 `PROTOTYPE-01`（原型机）

分机事实源 2026-10-30 才建立，此前只有单一 `本机事实.md`。**allin 最初是在一台
未登记的原型机上推进的**，其外置盘（`F:` / `G:`）现已接到 `DESKTOP-8RSV60V`。
故早于 `SPLIT_DATE` 的提单一律归 **`PROTOTYPE-01`（kind: archive，无 hostname）**，
**不计入任何实机的 A/B/C 级** —— 那时「分区」这个概念还不存在，算到某机头上是造证据。
即便它的标题里写着 `@SIWPAN`，也只记进 `tag_in_subject` 备查。

### 2. 「承载 ≠ 产出」：盘在谁那儿，不等于活是谁干的

「盘符 + 顶层目录名 `repos` / `archive` / `nodejs`」这类路径痕迹指向**原型机的盘**（现在挂在
8RSV60V 上），**不是** 8RSV60V 产出的。故带这类痕迹的提交**不进 8RSV60V 的 C 级**，
只记进 `prototype_carrier`，并注明不得据此归属。

## 三种「没有归属」必须分开计数（混成一个数就是误导）

- `PROTOTYPE-01` —— 分机前的提交，**本就不该有机器归属**（不是缺陷）；
- `unattributed_after_split` —— 分机后三源皆无，**这是真缺口**；其中再分
  `gate_covered`（>= 判据生效日：今后会被 `check_machine_trailer.py` 判红）
  与 `gate_uncovered`（判据生效前：只记账不追责）；
- `out_of_window` —— 早于判据生效日的提交，**不适用**新判据（一等结论，非绿非红）。

## 与判据的关系（为什么这里不 import 判据的内部件）

口径必须一致（同 `core.quotepath=false`、同 trailer 键），但**实现各自独立**：
2026-11-26 实测踩过 —— 取证工具借用了判据的测试 helper，判据给 helper 加了个参数，
取证工具的自检就以「`git init` 失败」这种误导性方式整片变红（11 例里 8 例）。
**取证工具不能让自己的正确性挂在另一个文件的内网签名上。**

## 用法

```bash
python tools/gate/machine_ledger.py --month 2026-11            # 写 json + md 到 audit/
python tools/gate/machine_ledger.py --month 2026-11 --json     # 只打 JSON 到 stdout
python tools/gate/machine_ledger.py --month 2026-11 --machine SIWPAN
python tools/gate/machine_ledger.py --selfcheck               # 13 例负对照
```

退出码：0 有产出／1 有可疑项／2 用法错／3 环境错。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
#: 口径打架的专用退出码（ADR §P8 第 4 条）。**刻意避开 0/1**：
#: · 0 = 有产出；1 = 有可疑项（正常的"红"，会被读成"仓里查出问题"）；
#: · 口径打架不是"仓有问题"，是**工具给不出可信数字** ⇒ 与"环境错"同级，取 3。
#: 用 1 的话，下游会把"工具坏了"和"仓里有问题"一起丢进复盘，
#: 而真正的原因（口径漂了）永远不会被看见。
EXIT_CONFLICT = 3
#: 固定前缀：元判据（`check_blind_gates` 之类）可直接 grep 这一行，不必解析中文。
CALIBER_PREFIX = "CALIBER CONFLICT:"

ROOT = Path(__file__).resolve().parents[2]        # tools/gate/ → 仓根
MACHINE_DIR = "docs/事实源/机器"
#: 归档机（`kind: archive`）：不是真机，不进**实机**的 A/B/C 表。
#: 它承载分机前的历史（此时"哪台机做的"本就无从谈起），单独作为 `PROTOTYPE-01` 桶统计。
#: 改动它分区的提单一律算"未归属"—— 触到归档目录不能说明活是谁干的。
ARCHIVE_MACHINES = {"PROTOTYPE-01"}
HANDOVER_DIR = "docs/记录/交接"
AUDIT_DIR = "tools/gate/audit/machine-ledger"
TRAILER_KEY = "Machine"

#: **归属分界**：此前机器分区事实源还不存在（只有单一 `本机事实.md`）。
SPLIT_DATE = "2026-10-30"
#: 原型机（虚构归档机，kind=archive，无 hostname）。无标识历史落到它名下 ——
#: 一个**有名字**的桶才追得下去；泛泛的"未归属"桶最后谁都不管。
PROTOTYPE = "PROTOTYPE-01"
PROTOTYPE_KIND = "archive"
#: **判据分界**（与 check_machine_trailer.EFFECTIVE_FROM 必须同值）。
#: 2026-12-01（不是 11-26）：hook 目前只有 SIWPAN 装了，定得太早会让另两台一上手就"违规"。
GATE_EFFECTIVE_FROM = "2026-12-01"
#: 判月时区，显式声明（ADR-0012 §D4.2）：团队只有一个工作时区；按提交者本地时区判月，
#: 会让同一天的工作落在两个月份里。月边界的命令**必须写带偏移的完整时间戳**（§D4.2b）。
TZ_NAME = "+08:00"

FS, RS = "\x1f", "\x1e"
#: 机器标识（`@` 必须显式：裸词 `KQABATS` 在正文里常常只是叙述，算成归属声明太松）
TAG_PAT = re.compile(r"@`?(SIWPAN|DESKTOP-KQABATS|DESKTOP-8RSV60V|KQABATS|8RSV60V|跨机)`?")
#: 原型机承载痕迹：**盘符 + 顶层目录名**的形态（`repos` / `archive` / `nodejs`）。承载 ≠ 产出。
#:
#: 2026-11-26 从 `[FG]:…`（两个具体盘符）改成形态识别，两个理由：
#: ① 盘符是**接线事实**、不是归属事实：原型盘今天接在 F:/G:，明天可能换（`E:`/`H:` 同样成立）；
#:    把盘符写进判据，等于让判据随机器搬线而失效。
#: ② 原写法在源码里留下形如「盘符:\\目录」的**字面量**，被 `scan_hardcoded.ps1` 判成
#:    "硬编码绝对路径且根不存在" —— 它判得对（那确实指向不存在的根）；
#:    但判据不该靠基线压掉自己的分类模式。**改形态比加豁免干净**。
#: 额外收益：检测面变宽（不再是"只认 G 盘"）。
CARRIER_PAT = re.compile(r"\b[A-Za-z]:[\\/](?:repos|archive|nodejs)\b", re.IGNORECASE)

#: 承载痕迹的**夹具样本模板**：用占位符而非字面量路径。
#: 判据按形态识别、不绑定机器，夹具只需一条样本；写字面量会被 `scan_hardcoded` 判红
#: （那是正确的判据行为），而这里并没有真实的待访问路径。
_CARRIER_SAMPLE = "docs: 从 {drive}:\\{directory} 里翻出来的旧账"


def _carrier_text(drive: str = "Q", directory: str = "repos") -> str:
    """造一条承载痕迹样本（默认合成盘符 `Q` + `repos` —— 不对应任何真机）。"""
    return _CARRIER_SAMPLE.format(drive=drive, directory=directory)
#: 节号引用：`§231` 与 `§二百三十一` 在本仓并存，两种都要认。
CN_NUM = re.compile(r"§\s*([0-9]{1,4}|[一二三四五六七八九十百零]{1,8})")
DATE_PAT = re.compile(r"(20\d\d-\d\d-\d\d)")
SECTION_HEADING = re.compile(r"^##\s+(\S+?)、(.+)$")
NOT_A_SECTION = ("按机索引", "会话交接")
_CN = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(text: str) -> int | None:
    """`一百三十一` → 131；`231` → 231。只支持本仓实际用到的三位以内节号。"""
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = section = 0
    for ch in text:
        if ch == "百":
            total += (section or 1) * 100
            section = 0
        elif ch == "十":
            total += (section or 1) * 10
            section = 0
        elif ch in _CN:
            section = _CN[ch]
        else:
            return None
    return total + section


# ---------------------------------------------------------------- git（独立实现）
def git(repo: Path | str, *args: str, env: dict | None = None, check: bool = True) -> str:
    """调 git。**`core.quotepath=false` 是硬性要求**：不关掉它，中文路径会被转义成
    `docs/\\346\\234\\272\\345\\231\\250/…`，C 级匹配全线失效 —— 而失效的表现是
    「这笔提交没碰分区」，与「确实没碰」完全同形（已踩过一次）。
    """
    proc = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{proc.stderr.strip()[:300]}")
    return proc.stdout


def discover_machines(repo: Path) -> list[str]:
    base = Path(repo) / MACHINE_DIR
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))


def machine_aliases(machines: list[str]) -> dict[str, str]:
    """`@KQABATS` → `DESKTOP-KQABATS`。由 stem 派生，不另立表（少一处漂移源）。"""
    out = {}
    for stem in machines:
        out[stem.upper()] = stem
        if "-" in stem:
            out.setdefault(stem.split("-", 1)[1].upper(), stem)
    return out


def read_commits(repo: Path, month: str) -> list[dict]:
    """读某月提交（sha / 日期 / 标题 / 变更文件 / 正文）。

    **逐提交取文件集，且 `git log` 后面绝对不加 `-- <path>`**（ADR-0012 §P8①）：
    一旦带 pathspec，git 会启用 **history simplification**，自己决定"哪些提交值得显示"
    —— 结果是它可能少看也可能多看几条，而少看的那几条**没有任何提示**。
    实测代价：`git log -- <path>` 与逐提交扫全量的差就是 318 / 319 两个数打架的来源，
    当时谁都没看出来。所以这里只做一件事：**不带 pathspec 地读全量，逐提交拿 `--name-only`**，
    再在 Python 里自己判"有没有触及某路径"。宁可慢一点，不可少看一条。

    月份按 `YYYY-MM` 前缀在 Python 侧精确过滤，**命令里根本不给 `--since/--until`**。

    两条实测理由（都在同一个方向上错：**少算**）：
    1. `--since` 的纯日期串被当成 **UTC 零点** ⇒ 2026-11-01 08:00+0800 之前的提交
       全被挡在窗外（389 vs 391）。
    2. 更要命的是：`--since/--until` 比的是 **committer date**。而"author 在 10 月、
       committer 在 11 月"（rebase / cherry-pick 的常态）这类提交，一旦 committer 落在
       窗口外，就会被**整个丢掉** —— 而这正是本仓最需要看见的一类（口径分叉的第一现场）。
       实测：造一笔 author=10-15 / committer=11-05 的提交，带窗口取数时 10 月得 0 笔。

    ⇒ 全量读、Python 侧按 author month 切。643 条提交一次读完，代价可忽略；
    换来的是"取数这一步不再有第二个日期口径"。
    """
    # 不给 `--since/--until`：见 docstring 的两条理由（都是 committer date 惹的祸）。
    # `%aI`（author date，带时区）而不是 `%cd`：ADR-0012 §D4.1 定的是**干活时间**。
    # committer date 会被 rebase / cherry-pick / 补提交改写成"记录被写进仓的时间"。
    # 实测今天 643/643 两条日期同月（跨月分叉 0 条），所以这个改动**不改数字**，
    # 但口径必须先定死 —— 趁两个值一致时换，成本为零；等分叉了再换，就是一次翻账。
    fmt = f"%x1e%H{FS}%aI{FS}%P{FS}%s"
    raw = git(repo, "log", "--date=short", f"--format={fmt}", "--name-only", "HEAD")
    commits = []
    for chunk in raw.split(RS):
        if not chunk.strip():
            continue
        lines = chunk.split("\n")
        parts = lines[0].split(FS)
        if len(parts) < 4:
            continue
        sha, date, parents, subject = (parts[0].strip(), parts[1].strip(),
                                       parts[2].split(), parts[3].strip())
        if not date.startswith(month):
            continue
        commits.append({"sha": sha, "date": date, "parents": parents, "subject": subject,
                        "files": [ln.strip() for ln in lines[1:] if ln.strip()], "body": ""})
    # 正文单独取一次：`--name-only` 与多行 `%b` 放进同一个 format 会互相踩分隔符。
    body_raw = git(repo, "log", f"--format=%x1e%H{FS}%b", "HEAD")
    bodies = {}
    for chunk in body_raw.split(RS):
        if not chunk.strip():
            continue
        sha, _, body = chunk.partition(FS)
        bodies[sha.strip()] = body
    for commit in commits:
        commit["body"] = bodies.get(commit["sha"], "")
    return commits


def cross_check_month_count(repo: Path, month: str, author_count: int | None) -> dict:
    """**两条独立口径**算当月提交数，必须一致；不一致就报"口径打架"，不报数字。

    ADR-0012 §D4.2b（Architect 复现并升格）：
      · 纯日期串 `--since=2026-11-01` 被当成 **UTC 零点** ⇒ 11-01 00:00~08:00(+08:00)
        的提交在 UTC 里还属 10 月，被**静默**扣掉（实测 389，真值 391）。
      · 这条与 `git log -- <path>` 的 history simplification 是同一类：
        **都是"让工具替你选口径"，而且都往"数字变小"的方向错** —— 少算的账看起来更干净，
        所以没人会去查它。

    所以：一条按 author date 自己算（`_author_month_table`），一条交给 git 但**写全带偏移的
    时间戳**。两条对得上才算过；对不上说明口径某处变了，此时**任何数字都不该被引用**。

    返回 `{"author": n, "revlist_offset": m, "ok": bool, "window": "…"}`。
    """
    author = author_count
    start = f"{month}-01T00:00:00{TZ_NAME}"
    year, mon = month.split("-")
    nxt = f"{int(year) + (1 if int(mon) == 12 else 0)}-{(int(mon) % 12) + 1:02d}"
    end = f"{nxt}-01T00:00:00{TZ_NAME}"
    proc = subprocess.run(
        ["git", "rev-list", "--count", f"--since={start}", f"--until={end}", "HEAD"],
        cwd=str(repo), check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace")
    try:
        by_git = int((proc.stdout or "").strip())
    except ValueError:
        by_git = None
    ok = author is not None and by_git is not None and author == by_git
    # 变异探针：强行制造"口径打架"，用来验**拒答这条路真的会走**。
    # 不做这一步，"口径打架 ⇒ exit 3 且一个数字都不给"就只是一句注释。
    if os.environ.get("ALLIN_LEDGER_MUTATE") == "caliber-conflict":
        # 变异态要让**两个读数真的差 1**，不能只把 ok 拧成 False：
        # 若两个数仍相等却在喊 conflict，读到这条日志的人会得出"这道判据有时会胡说"——
        # 而它唯一的用途正是"不给数 ⇒ 真有问题"。**负对照的输出也是文档。**
        if by_git is not None and author is not None:
            by_git = by_git + 1
        ok = False
    return {"author": author, "revlist_offset": by_git, "ok": ok,
            "window": f"{start} .. {end}"}


def head_sha(repo: Path) -> str | None:
    proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8")
    return (proc.stdout.strip() or None) if proc.returncode == 0 else None


# ---------------------------------------------------------------- A 级：交接卷自述
def parse_handover(text: str, machines: list[str]) -> dict:
    """解析交接卷，取 A 级证据（该机**自述**的节）。

    两个来源都算 A（都是文档里写下来的归属）：
      · 卷首**按机索引**（`### \\`@SIWPAN\\`（46 节）` 下的表格）—— 2026-11-25 起有；
      · 正文节标题里的 `@STEM` 标注（D18 判据要求新节必须标）。
    更早的卷（如 2026-10）**没有索引**，只有正文 —— 所以两条都要走。
    """
    alias = machine_aliases(machines)
    alias["跨机"] = "跨机"
    per_machine: dict[str, list[dict]] = {stem: [] for stem in machines}
    per_machine["跨机"] = []
    untagged: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(owner: str | None, section: str, title: str, source: str) -> None:
        key = (owner or "", section)
        if key in seen:
            return  # 索引与正文各出现一次 —— 只记一条，别把同一节数两遍
        seen.add(key)
        match = DATE_PAT.search(title)
        entry = {"section": section.strip(), "title": title.strip(),
                 "date": match.group(1) if match else None, "source": source}
        if owner is None:
            untagged.append(entry)
        elif owner in per_machine:
            per_machine[owner].append(entry)

    lines = text.split("\n")
    current: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("###"):
            current = None      # 正文开始 ⇒ 索引块结束（否则正文里的表格会被算进索引）
            continue
        if stripped.startswith("### "):
            current = None
            # 只认**按机索引块的表头**：真实形态是 `### `@SIWPAN`（46 节）` / `### **未标机**（…）（5 节）`，
            # 特征是行尾 `节）`。不能见 `###` 就当表头 —— 正文里有大量 `### 117.4 …（@SIWPAN 复核）`
            # 这类小节标题，把它们当表头会把随后表格里的每一行都算成 A 级证据
            # （2026-11 实测：不做这个限定，A 级从 116 节虚增到 198 节）。
            if "未标机" in stripped:
                current = "__untagged__"
            elif stripped.rstrip().endswith("节）"):
                match = re.search(r"@`?([^`（）]+)`?", stripped)
                if match:
                    name = match.group(1).strip()
                    current = alias.get(name.upper()) or (name if name in per_machine else None)
            continue
        if stripped.startswith("---"):
            current = None
            continue
        if current and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 2 or cells[0] in ("节", "---") or set(cells[0]) <= {"-", " "}:
                continue
            add(None if current == "__untagged__" else current, cells[0], cells[1], "index")

    total_sections = 0
    for line in lines:
        if not line.startswith("## ") or line.startswith("###"):
            continue
        if any(key in line for key in NOT_A_SECTION):
            continue
        match = SECTION_HEADING.match(line.strip())
        if not match:
            continue
        total_sections += 1
        section, title = match.group(1), match.group(2)
        tag = TAG_PAT.search(title)
        owner = alias.get(tag.group(1).upper()) if tag else None
        add(owner, section, title, "heading")

    tagged = sum(len(v) for v in per_machine.values())
    return {
        "machines": per_machine,
        "untagged": untagged,
        "totals": {"sections": max(total_sections, tagged + len(untagged)),
                   "tagged": tagged, "untagged": len(untagged)},
    }


# ---------------------------------------------------------------- B/C/D 级：提交
def _root_level_only(files: list[str]) -> bool:
    """只触碰**机器区根级**文件（`docs/事实源/机器/*.md`），不碰任何机目录。

    这类文件是机器区的公共索引，**不属于任何单机**（ADR §D4.3 把这条钉进算法）：
    把"改了机器区索引"算到某台机头上，等于替那台机认领它没做的活。
    """
    touched = [f for f in files if f.startswith(MACHINE_DIR + "/")]
    if not touched:
        return False
    return all(len(f[len(MACHINE_DIR) + 1:].split("/")) == 1 for f in touched)


def _cites(subject: str) -> list[int]:
    out = []
    for raw in CN_NUM.findall(subject):
        value = cn2int(raw)
        if value:
            out.append(value)
    return out


def classify_commits(commits: list[dict], machines: list[str]) -> dict:
    """每笔提交**恰好**落一个桶 —— 守恒式（总数 = 各桶之和）就建在这条上。

    用"条目数"而不是"桶计数"会把改了两台机分区的一笔数两次，于是
    「未归属 = 总数 − 有归属」永远对不上，而那个式子恰恰是所有人最先看的一个。
    """
    alias = machine_aliases(machines)
    alias["跨机"] = "跨机"
    result = {
        "B": {stem: [] for stem in machines},
        "C": {stem: [] for stem in machines},
        "cross_machine_tagged": [],
        "prototype_01": [],
        "prototype_carrier": [],
        "unattributed": [],
        "multi_machine": [],
        "labels": {"prototype": 0, "B": 0, "C": 0, "cross": 0, "unattributed": 0},
        "gate_covered_missing": 0,
        "gate_uncovered_missing": 0,
        "out_of_window": 0,
        #: D 的明细（三者之和恒等于 D，**明细不搬出 D**，ADR §D4.3 / §P2）。
        #: 命名刻意与 `prototype_carrier` 区分 —— 它们是**两个不同集合**：
        #:   · `root_level`：只改机器区根级文件（`docs/事实源/机器/*.md`），不属任何单机；
        #:   · `carrier_trace_no_partition`：标题/正文有原型盘痕迹（G:/F:），
        #:     且**没有**触及任何机器分区 ⇒ 归属仍未知；
        #:   · `other`：其余三源皆无的普通提交。
        #: （`prototype_carrier` 是"有盘痕迹且触及 8RSV60V 分区 ⇒ 从 C 级剔除"的那批，
        #:  与这里互不相交；两个词共用 "carrier" 会让半年后的人把它们相加。）
        "unattributed_parts": {"root_level": 0, "carrier_trace_no_partition": 0, "other": 0},
    }
    for commit in commits:
        subject = commit["subject"]
        tags = [alias[m.group(1).upper()] for m in TAG_PAT.finditer(subject)]
        claimed = sorted({t for t in tags if t != "跨机" and t in machines})
        touched: dict[str, list[str]] = {}
        for path in commit["files"]:
            for stem in machines:
                if path.startswith(f"{MACHINE_DIR}/{stem}/"):
                    touched.setdefault(stem, []).append(path)
        carrier = bool(CARRIER_PAT.search(subject) or CARRIER_PAT.search(commit["body"]))
        entry = {"sha": commit["sha"], "date": commit["date"], "subject": subject,
                 "files": commit["files"][:8]}

        if commit["date"] < SPLIT_DATE and not claimed:
            result["prototype_01"].append({
                **entry,
                "why": f"分机事实源 {SPLIT_DATE} 才建立；本仓当时在未登记的原型机上推进",
                "tag_in_subject": tags,
            })
            result["labels"]["prototype"] += 1
            continue
        # 分机前的提交里，**标题已带机名**的记 B 而不是塞进 PROTOTYPE-01
        # （ADR §D1.5「证据优先」：证据在，就不能假装没有）。2026-10 实测 2 笔
        # （c5e0510c / b649313f，都是 2026-10-29）⇒ E 从 133 变 202 之外的正确值。

        if claimed:
            for stem in claimed:
                result["B"][stem].append({**entry, "cited_sections": _cites(subject)})
            result["labels"]["B"] += 1
        elif "跨机" in tags:
            # `@跨机` 是**显式否认机器归属**（共识/机制/发布），不能降级当 C 级旁证。
            result["cross_machine_tagged"].append(entry)
            result["labels"]["cross"] += 1
        else:
            weak = {stem: paths for stem, paths in touched.items()
                    if not (carrier and stem == "DESKTOP-8RSV60V")}
            if carrier and "DESKTOP-8RSV60V" in touched:
                result["prototype_carrier"].append({
                    **entry, "would_be": "DESKTOP-8RSV60V",
                    "why": "标题/正文含原型盘痕迹（G:/F:）—— 盘接到 8RSV60V 上"
                           "不等于活是该机干的（承载 ≠ 产出）"})
            if weak:
                for stem, paths in weak.items():
                    result["C"][stem].append({**entry, "files": paths[:8]})
                result["labels"]["C"] += 1
            else:
                result["unattributed"].append(entry)
                result["labels"]["unattributed"] += 1
                # ADR §P8②：根级机器文件（`docs/事实源/机器/*.md`，不属于任何单机）
                # 与承载痕迹必须**单列可见**，不能只留在 D 的总数里。
                # 这里作为 D 的**明细**统计，不改变 D 的头条数（否则已锁定的口径又要重锁）。
                if carrier:
                    result["unattributed_parts"]["carrier_trace_no_partition"] += 1
                elif _root_level_only(commit["files"]):
                    result["unattributed_parts"]["root_level"] += 1
                else:
                    result["unattributed_parts"]["other"] += 1
                if commit["date"] >= GATE_EFFECTIVE_FROM:
                    result["gate_covered_missing"] += 1
                else:
                    result["gate_uncovered_missing"] += 1
        if len(claimed) > 1 or len(touched) > 1:
            result["multi_machine"].append({"sha": commit["sha"], "date": commit["date"],
                                            "claimed": claimed, "touched": sorted(touched)})
        if commit["date"] < GATE_EFFECTIVE_FROM:
            result["out_of_window"] += 1
    return result


# ---------------------------------------------------------------- 汇总
def collect(repo: Path, month: str, machine: str | None = None) -> dict:
    repo = Path(repo)
    machines = [m for m in discover_machines(repo) if m not in ARCHIVE_MACHINES]
    if not machines:
        raise FileNotFoundError(f"找不到机器分区目录 {MACHINE_DIR}（跑错仓？）")

    handover_path = repo / HANDOVER_DIR / f"{month}.md"
    a_tier = {"machines": {stem: [] for stem in machines}, "untagged": [],
              "totals": {"sections": 0, "tagged": 0, "untagged": 0}}
    handover_note = None
    if handover_path.is_file():
        a_tier = parse_handover(handover_path.read_text(encoding="utf-8"), machines)
    else:
        handover_note = f"交接卷缺席：{HANDOVER_DIR}/{month}.md（A 级证据无来源）"

    commits = read_commits(repo, month)
    tiers = classify_commits(commits, machines)
    labels = tiers["labels"]
    payload = {
        "month": month,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "repo_head": head_sha(repo),
        "boundaries": {"split_date": SPLIT_DATE, "gate_effective_from": GATE_EFFECTIVE_FROM},
        "totals": {
            "commits_in_month": len(commits),
            "prototype_01": labels["prototype"],
            "attributed_B": labels["B"],
            "attributed_C_only": labels["C"],
            "attributed_commits": labels["B"] + labels["C"],
            "unattributed_after_split": labels["unattributed"],
            "gate_covered_missing": tiers["gate_covered_missing"],
            "gate_uncovered_missing": tiers["gate_uncovered_missing"],
            "cross_machine_tagged": labels["cross"],
            "prototype_carrier": len(tiers["prototype_carrier"]),
            "out_of_window": tiers["out_of_window"],
            "handover_sections": a_tier["totals"]["sections"],
            "handover_sections_tagged": a_tier["totals"]["tagged"],
            # ADR-0012 §D2.6 的记账恒等式：已标机节 + 未标机节 == 节总数。
            # 少了这一条，「A 级 124/137」这两个数就只能靠人相信工具没漏读。
            "sections_accounting_ok": (a_tier["totals"]["tagged"] + a_tier["totals"]["untagged"]
                                       == a_tier["totals"]["sections"]),
            "conservation_ok": len(commits) == sum(labels.values()),
            #: 两条独立口径（author date 自算 / 带偏移时间戳交给 git）必须一致。
            #: 不一致 = 口径打架 ⇒ main() 直接拒答（宁可不给数，不给两个数）。
            "count_cross_check": cross_check_month_count(repo, month, len(commits)),
            "unattributed_parts": dict(tiers["unattributed_parts"]),
            "parts_sum_ok": sum(tiers["unattributed_parts"].values()) == labels["unattributed"],
        },
        "A_sections": a_tier["machines"],
        "A_untagged": a_tier["untagged"],
        "B_commits": tiers["B"],
        "C_commits": tiers["C"],
        "cross_machine_tagged": tiers["cross_machine_tagged"],
        "multi_machine_commits": tiers["multi_machine"],
        "prototype_01": {
            "machine_id": PROTOTYPE, "kind": PROTOTYPE_KIND, "hostname": None,
            "count": labels["prototype"],
            "note": f"分机事实源 {SPLIT_DATE} 才建立；allin 当时在一台**未登记的原型机**上推进，"
                    "其外置盘（F:/G:）现已接到 @DESKTOP-8RSV60V —— **不代表该机执行**"
                    "（承载 ≠ 产出，ADR 已明令）。此桶内的提交不计入任何实机的 A/B/C 级。",
            "commits": tiers["prototype_01"],
        },
        "prototype_carrier": {
            "count": len(tiers["prototype_carrier"]),
            "note": "标题/正文含「盘符 + 顶层目录名 repos/archive/nodejs」类原型盘痕迹的提交："
                    "**不进 8RSV60V 的 C 级**（盘在谁那儿 ≠ 活是谁干的）",
            "commits": tiers["prototype_carrier"],
        },
        "unattributed": {
            "count": labels["unattributed"],
            "gate_covered": tiers["gate_covered_missing"],
            "gate_uncovered": tiers["gate_uncovered_missing"],
            "note": "分机后三源皆无 —— **真缺口**，不是「没有这回事」。"
                    "`gate_covered` 在判据生效日之后（今后会被 check_machine_trailer.py 判红）；"
                    "`gate_uncovered` 在生效日之前（机制当时还不存在，只记账不追责）。",
            "commits": tiers["unattributed"],
        },
        "out_of_window": {
            "count": tiers["out_of_window"],
            "note": f"早于判据生效日 {GATE_EFFECTIVE_FROM} 的提交：**不适用**新判据"
                    "（一等结论，非绿非红）。与 `unattributed.gate_uncovered` 是同一批提交的"
                    "两个视角：一个问「有没有归属」，一个问「判不判」。",
        },
        "caveats": [
            "A 级是**节级**证据（某机认领了哪些交接节），落不到具体提交上；A 与 B/C 不可相加。",
            "C 级路径旁证**不可单独作为归属依据**：跨机协作时别人也可能改你的分区文件。",
            "B 级只认标题里显式 `@<STEM>`（含 @KQABATS 等短形态）；标题写 `@跨机` 的归跨机桶。",
            "本工具不判定「该不该归某机」，只按证据强度分级；最终判断留给人 / 写账人。",
        ],
        "handover_note": handover_note,
    }
    if machine:
        payload = _filter(payload, machine)
    return payload


def _filter(payload: dict, machine: str) -> dict:
    machine = machine.upper()
    out = dict(payload)
    for key in ("A_sections", "B_commits", "C_commits"):
        out[key] = {machine: payload[key].get(machine, [])}
    out["filtered_machine"] = machine
    return out


# ---------------------------------------------------------------- 人读版
def render_markdown(payload: dict, limit: int = 40) -> str:
    t = payload["totals"]
    lines = [
        f"# 机器归属取证 · {payload['month']}（三源分级，不是叙事）",
        "",
        f"> 生成：`tools/gate/machine_ledger.py --month {payload['month']}`"
        f" · HEAD `{payload.get('repo_head') or '?'}` · {payload['generated_at']}",
        "> **这是证据汇总，不是月账正文**。月账由各机自己写；这里只回答"
        "「这笔活是哪台机器干的、证据有多硬」。",
        "> **本文件是机器归属数字的唯一口径**（2026-11-26 团队裁决）：三处数字不一致时以此为准 ——"
        "理由只有一条：它可被一条命令复现（`python tools/gate/machine_ledger.py --month <YYYY-MM> --json`），"
        "手数出来的数下一次没人能复现。",
        "",
        "## 0. 分界与口径",
        "",
        f"- **归属分界** `SPLIT_DATE = {payload['boundaries']['split_date']}`：此前机器分区"
        "事实源还不存在（只有单一 `本机事实.md`），提交归 `PROTOTYPE-01`（原型机，未登记）。",
        f"- **判据分界** `{payload['boundaries']['gate_effective_from']}`："
        "`check_machine_trailer.py` 只判这一天之后的提交。",
        "- 证据强度：**A 强**（交接卷里该机自述的节）/ **B 中**（提交标题 `@机名`）"
        " / **C 弱**（触及该机分区，**不可单独作依据**）/ **D 未归属**（三源皆无，如实计数）。",
        "",
        "## 1. 总账（先看这张表：三种「没有归属」不能混成一个数）",
        "",
        "| 项 | 数量 |",
        "| --- | --- |",
        f"| 本月提交数 | {t['commits_in_month']}"
        f"（双口径校验：author {t['count_cross_check']['author']} / "
        f"rev-list(带偏移) {t['count_cross_check']['revlist_offset']} ⇒ "
        f"{'一致' if t['count_cross_check']['ok'] else '**口径打架，本表数字不可引用**'}） |",
        f"| A · 交接卷已标注的节 | {t['handover_sections_tagged']} / {t['handover_sections']} |",
        f"| B · 标题带 `@机名` 的提交 | {t['attributed_B']} |",
        f"| C · 仅凭触及分区（弱旁证） | {t['attributed_C_only']} |",
        f"| **D · 未归属（真缺口）** | **{t['unattributed_after_split']}**"
        f"（判据生效后 {t['gate_covered_missing']} / 生效前 {t['gate_uncovered_missing']}） |",
        f"| `PROTOTYPE-01`（分机前，本就不该有归属） | {t['prototype_01']} |",
        f"| 标题写 `@跨机` | {t['cross_machine_tagged']} |",
        f"| 承载痕迹（原型盘路径，不进 8RSV60V 的 C 级） | {t['prototype_carrier']} |",
        f"| out-of-window（早于判据生效日，不适用判据） | {t['out_of_window']} |",
        "",
        "守恒校验：B + C + `PROTOTYPE-01` + `@跨机` + 未归属 = 本月提交 ⇒ "
        f"**{'通过' if t['conservation_ok'] else '不通过（有提交落不进任何桶，是 bug）'}**",
        "",
    ]
    for stem in sorted(k for k in payload["A_sections"] if k != "跨机"):
        sections = payload["A_sections"].get(stem, [])
        b_commits = payload["B_commits"].get(stem, [])
        c_commits = payload["C_commits"].get(stem, [])
        lines += [f"## 2. `{stem}`", "", f"**A 级（强，自述）· {len(sections)} 节**", ""]
        if sections:
            lines += ["| 节 | 标题 | 日期 | 来源 |", "| --- | --- | --- | --- |"]
            for item in sections[:limit]:
                lines.append(f"| {item['section']} | {item['title'][:60]} | "
                             f"{item['date'] or '—'} | {item['source']} |")
            if len(sections) > limit:
                lines.append(f"| … | 另 {len(sections) - limit} 节（见 JSON） | | |")
        else:
            lines.append("_本月交接卷里没有该机标注的节。_")
        lines += ["", f"**B 级（中，标题 `@{stem}`）· {len(b_commits)} 笔**", ""]
        if b_commits:
            lines += ["| 提交 | 日期 | 标题 |", "| --- | --- | --- |"]
            for item in b_commits[:limit]:
                lines.append(f"| `{item['sha'][:8]}` | {item['date']} | {item['subject'][:70]} |")
        else:
            lines.append("_无。_")
        lines += ["", f"**C 级（弱，触及分区，不可单独作依据）· {len(c_commits)} 笔**", ""]
        if c_commits:
            lines += ["| 提交 | 日期 | 标题 | 触及文件（示例） |", "| --- | --- | --- | --- |"]
            for item in c_commits[:limit]:
                example = item["files"][0] if item.get("files") else "—"
                lines.append(f"| `{item['sha'][:8]}` | {item['date']} | "
                             f"{item['subject'][:52]} | {example} |")
            if len(c_commits) > limit:
                lines.append(f"| … | | 另 {len(c_commits) - limit} 笔（见 JSON） | |")
        else:
            lines.append("_无。_")
        lines.append("")

    cross = payload["A_sections"].get("跨机", [])
    if cross:
        lines += [f"## 3. `@跨机`（共识 / 机制 / 发布）· {len(cross)} 节", ""]
        for item in cross[:limit]:
            lines.append(f"- {item['section']} {item['title'][:70]}（{item['date'] or '—'}）")
        lines.append("")

    proto = payload["prototype_01"]
    lines += [f"## 4. `{PROTOTYPE}`（原型机，未登记）· {proto['count']} 笔", "",
              f"> {proto['note']}", ""]
    for item in proto["commits"][:limit]:
        lines.append(f"- `{item['sha'][:8]}` {item['date']} {item['subject'][:70]}")
    if proto["count"] > limit:
        lines.append(f"- … 另 {proto['count'] - limit} 笔（见 JSON）")
    lines.append("")

    carrier = payload["prototype_carrier"]
    if carrier["count"]:
        lines += [f"## 5. 承载痕迹（不进 8RSV60V 的 C 级）· {carrier['count']} 笔", "",
                  f"> {carrier['note']}", ""]
        for item in carrier["commits"][:limit]:
            lines.append(f"- `{item['sha'][:8]}` {item['date']} {item['subject'][:70]}")
        lines.append("")

    un = payload["unattributed"]
    lines += [f"## 6. 未归属（D）· {un['count']} 笔 —— 真缺口，不是「没有这回事」", "",
              f"> {un['note']}", "",
              f"其中受判据覆盖（>= {payload['boundaries']['gate_effective_from']}）："
              f"{un['gate_covered']} 笔；生效前：{un['gate_uncovered']} 笔。", ""]
    if un["count"]:
        lines += ["| 提交 | 日期 | 标题 |", "| --- | --- | --- |"]
        for item in un["commits"][:limit]:
            lines.append(f"| `{item['sha'][:8]}` | {item['date']} | {item['subject'][:70]} |")
        if un["count"] > limit:
            lines.append(f"| … | | 另 {un['count'] - limit} 笔（见 JSON） |")
        lines.append("")

    if payload.get("A_untagged"):
        lines += ["## 7. 交接卷未标机的节（早期未规范，归属待补）", "",
                  "| 节 | 标题 | 日期 |", "| --- | --- | --- |"]
        for item in payload["A_untagged"][:limit]:
            lines.append(f"| {item['section']} | {item['title'][:60]} | {item['date'] or '—'} |")
        lines.append("")

    lines += ["## 8. 读法（必须遵守）", ""]
    lines += [f"- {caveat}" for caveat in payload["caveats"]]
    if payload.get("handover_note"):
        lines.append(f"- ⚠ {payload['handover_note']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检（独立夹具）
def _sc_commit(repo: Path, rel: str | None, content: str, message: str,
               when: str, trailer: str | None = None) -> str:
    if rel:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    body = message.rstrip("\n") + "\n"
    if trailer:
        body += f"\n{TRAILER_KEY}: {trailer}\n"
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    proc = subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=str(repo), input=body,
                          capture_output=True, text=True, encoding="utf-8", env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"commit 失败：{proc.stderr.strip()[:200]}")
    return git(repo, "rev-parse", "HEAD").strip()


def _sc_git_add(repo: Path) -> None:
    git(repo, "add", "-A")


def _sc_amend(repo: Path, message: str, when: str) -> None:
    """把改动 amend 进**同一笔**提交（造"一笔提交改了两台机分区"用）。"""
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    proc = subprocess.run(["git", "commit", "-q", "--amend", "-m", message], cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8", env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"amend 失败：{proc.stderr.strip()[:200]}")


def _sc_repo(base: Path) -> Path:
    """自检夹具：**独立**的临时仓构造，不借用判据（`check_machine_trailer.py`）的内部 helper。

    为什么必须独立：借用对方的内部 helper，等于把本工具的自检绑在对方的函数签名上 ——
    对方给 `_commit()` 加一个参数，本工具的自检就会以「`git init` 失败」这种
    **误导性方式**整片变红（2026-11-26 实测：11 例里 8 例红，第一现场看起来像 git 坏了）。
    自检的价值全在「独立地验」。
    """
    repo = base / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "LedgerSelfCheck"),
                       ("user.email", "ledger-selfcheck@example.invalid"),
                       ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
        git(repo, "config", key, value)
    for stem in ("SIWPAN", "DESKTOP-KQABATS", "DESKTOP-8RSV60V"):
        (repo / MACHINE_DIR / stem / "月账").mkdir(parents=True)
    (repo / "docs" / "其他.md").write_text("公共文档\n", encoding="utf-8")
    _sc_commit(repo, "docs/其他.md", "v0\n", "chore: 初始化", "2026-11-26T09:00:00")
    return repo


def _selfcheck_refusal() -> tuple[bool, str]:
    """验「口径打架 ⇒ 拒答」：变异态下必须 exit 3、stderr 有固定前缀、stdout 无数字。

    为什么这条路要单验：拒答是**唯一一种"没有输出也算失败"**的形态。
    退出码若取 0/1，下游会把"工具给不出数"读成"仓里没问题"或"仓里有问题"——
    两种误读都会让真正的原因（口径漂了）永远不被看见。
    """
    with tempfile.TemporaryDirectory(prefix="machine-ledger-refusal-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        for step in (["git", "init", "-q", "-b", "main"],
                     ["git", "config", "user.email", "selfcheck@example.invalid"],
                     ["git", "config", "user.name", "SelfCheck"],
                     ["git", "config", "commit.gpgsign", "false"]):
            subprocess.run(step, cwd=str(repo), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (repo / "docs").mkdir()
        (repo / "docs" / "其他.md").write_text("x\n", encoding="utf-8")
        (repo / MACHINE_DIR / "SIWPAN" / "月账").mkdir(parents=True)
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-q", "-m", "chore: init"], cwd=str(repo), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = dict(os.environ, ALLIN_LEDGER_MUTATE="caliber-conflict")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--month", "2026-11",
             "--repo", str(repo), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if proc.returncode != EXIT_CONFLICT:
            return False, f"期望 exit {EXIT_CONFLICT}，实际 {proc.returncode}"
        if CALIBER_PREFIX not in (proc.stderr or ""):
            return False, "stderr 缺固定前缀（元判据无法识别）"
        if "commits_in_month" in (proc.stdout or ""):
            return False, "口径打架时仍输出了数字（应一个数字都不给）"
        return True, f"exit {EXIT_CONFLICT} + 前缀到位 + stdout 无数字"


def _selfcheck_author_vs_committer() -> tuple[bool, str]:
    """口径回归的决定性负对照：造一笔 **author 在 10 月、committer 在 11 月** 的提交。

    ADR §D4.1 定的是 author date。若有人把 `%aI` 改回 `%cd`，这笔会被算进 11 月 ——
    而**其它断言全都照样通过**（今天的 643 条两条日期同月，改回去数字不变）。
    所以那条改动只能靠这笔"故意造出来的分叉"来抓。

    ⚠ 刻意**不**把三个月的真实读数（71/181/391）写死进自检：每来一笔新提交它就红，
    而"因为仓里有新提交而红"的用例，教出来的是"忽略它"。判据该盯**口径**，不盯**快照**。
    """
    with tempfile.TemporaryDirectory(prefix="machine-ledger-ac-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        for step in (["git", "init", "-q", "-b", "main"],
                     ["git", "config", "user.email", "selfcheck@example.invalid"],
                     ["git", "config", "user.name", "SelfCheck"],
                     ["git", "config", "commit.gpgsign", "false"]):
            subprocess.run(step, cwd=str(repo), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (repo / "f.md").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(repo), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = dict(os.environ,
                   GIT_AUTHOR_DATE="2026-10-15T10:00:00+08:00",    # 干活：10 月
                   GIT_COMMITTER_DATE="2026-11-05T10:00:00+08:00")  # 写入：11 月
        done = subprocess.run(["git", "commit", "-q", "-m", "feat: 跨月 rebase 过的一笔"],
                              cwd=str(repo), env=env, check=False,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                              encoding="utf-8", errors="replace")
        if done.returncode != 0:
            return False, f"夹具提交失败：{(done.stderr or '')[:120]}"
        in_oct = len(read_commits(repo, "2026-10"))
        in_nov = len(read_commits(repo, "2026-11"))
        note = f"author=10-15 / committer=11-05 ⇒ 2026-10 计 {in_oct} 笔，2026-11 计 {in_nov} 笔"
        if in_oct == 1 and in_nov == 0:
            return True, note
        return False, f"应按 author date 归 10 月，实际（{note}）—— 口径被改回 committer date 了？"


def selfcheck() -> int:
    """13 例。两条硬要求（用户点名）：**中文路径必须匹配**、**未归属必须计数**。"""
    cases: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="machine-ledger-") as tmp:
        # ------------------------------------------------ 11 月卷
        repo = _sc_repo(Path(tmp) / "nov")
        mdir = f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md"
        mdir_k = f"{MACHINE_DIR}/DESKTOP-KQABATS/月账/2026-11.md"
        mdir8 = f"{MACHINE_DIR}/DESKTOP-8RSV60V/月账/2026-11.md"
        post = "2026-11-28T10:00:00"   # 11 月内（仍在判据生效日之前）
        pre = "2026-11-10T10:00:00"    # 分机后、判据生效前

        _sc_commit(repo, mdir, "a\n", "docs(ho): @SIWPAN 记一笔本机账", post, "SIWPAN")
        _sc_commit(repo, mdir_k, "b\n", "docs(ho): @KQABATS 短形态别名", post, "DESKTOP-KQABATS")
        _sc_commit(repo, mdir, "c\n", "docs: 改分区但标题没写机名", post)          # C（SIWPAN）
        _sc_commit(repo, "docs/其他.md", "d\n", "docs: 三源皆无（生效日后）", post)  # D + covered
        _sc_commit(repo, "docs/其他.md", "e\n", "docs: 三源皆无（生效日前）", pre)    # D + uncovered
        # 承载痕迹：标题里带原型机外置盘的**路径形态**（盘符 + repos/archive/nodejs），
        # 且只碰 8RSV60V 分区 ⇒ 必须转 carrier，不得进 8RSV60V 的 C 级。
        # 样本用模板造（见 `_carrier_text`）：判据按形态识别，不绑定具体盘符。
        _sc_commit(repo, mdir8, "f\n", _carrier_text(), post)
        sha_cross = _sc_commit(repo, "docs/其他.md", "g\n",
                               "docs(ho): @跨机 共识类，不是某台机的活", post)

        (repo / HANDOVER_DIR).mkdir(parents=True, exist_ok=True)
        (repo / HANDOVER_DIR / "2026-11.md").write_text(
            "# 交接 · 2026-11\n\n"
            "## 按机索引（以机器标识为顶层）\n\n"
            "### `@SIWPAN`（2 节）\n\n"
            "| 节 | 标题 |\n| --- | --- |\n"
            "| 一百二十六 | SIWPAN 机自修（2026-11-03） |\n"
            "| 一百三十八 | 分区文件夹化（2026-11-07 晨） |\n\n"
            "### `@DESKTOP-KQABATS`（1 节）\n\n"
            "| 节 | 标题 |\n| --- | --- |\n"
            "| 一百一十七 | AgentOps 调研（2026-11-02） |\n\n"
            "### **未标机**（1 节）\n\n"
            "| 节 | 标题 |\n| --- | --- |\n"
            "| 一百一十四 | 官网上线（2026-11-01） |\n\n"
            "---\n\n"
            "## 一百二十六、SIWPAN 机自修（2026-11-03 @`SIWPAN`）\n\n"
            "## 一百四十九、只有正文标注的节（2026-11-09 @`SIWPAN`）\n",
            encoding="utf-8")

        payload = collect(repo, "2026-11")
        t = payload["totals"]

        # ① A 级：索引解析出节号/标题/日期（索引 2 节 + 正文新增 1 节 = 3）
        cases.append(("A 级：按机索引解析出节号/标题/日期",
                      len(payload["A_sections"]["SIWPAN"]) == 3
                      and payload["A_sections"]["SIWPAN"][0]["section"] == "一百二十六"
                      and payload["A_sections"]["SIWPAN"][0]["date"] == "2026-11-03"))
        # ② A 级：正文 `@机名` 标注（索引里没有的那节）也要认
        cases.append(("A 级：正文 `@机名` 标注也计入（索引之外）",
                      any(item["section"] == "一百四十九"
                          for item in payload["A_sections"]["SIWPAN"])))
        # ③ A 级：未标机的节单列（不硬塞给某台机）
        cases.append(("A 级：未标机的节单列，不硬塞给任何机",
                      len(payload["A_sections"]["SIWPAN"]) == 3
                      and len(payload["A_untagged"]) == 1
                      and t["handover_sections"] >= 5))
        # ④ B 级：短形态别名 `@KQABATS` → DESKTOP-KQABATS
        cases.append(("B 级：`@KQABATS` 归 DESKTOP-KQABATS（短形态别名）",
                      len(payload["B_commits"]["DESKTOP-KQABATS"]) == 1))
        # ⑤ C 级 + **中文路径必须匹配**（quotepath 负对照）
        c_list = payload["C_commits"]["SIWPAN"]
        cases.append(("C 级：中文路径被原样匹配（quotepath=false 生效）",
                      len(c_list) == 1
                      and c_list[0]["files"][0].startswith(f"{MACHINE_DIR}/SIWPAN/")))
        # ⑥ **未归属必须计数**（守恒式）
        conserved = (t["commits_in_month"] == t["prototype_01"] + t["attributed_commits"]
                     + t["cross_machine_tagged"] + t["unattributed_after_split"])
        cases.append(("未归属必须计数且守恒（总数 = 有归属 + 原型机 + 跨机 + 未归属）",
                      conserved and t["unattributed_after_split"] >= 2
                      and t["conservation_ok"]))
        # ⑦ `@跨机` 不落进任何实机的 B/C 级
        cross_shas = [c["sha"] for c in payload["cross_machine_tagged"]]
        in_b = [c["sha"] for v in payload["B_commits"].values() for c in v]
        cases.append(("`@跨机` 单列，不混进实机 B/C 级",
                      t["cross_machine_tagged"] == 1 and sha_cross in cross_shas
                      and sha_cross not in in_b))
        # ⑧ 承载 ≠ 产出
        cases.append(("承载 ≠ 产出：盘符+repos 痕迹不进 8RSV60V 的 C 级",
                      payload["prototype_carrier"]["count"] == 1
                      and len(payload["C_commits"]["DESKTOP-8RSV60V"]) == 0))
        # ⑧b **一笔同时改两台机分区** ⇒ 只能落**一个**桶（C 计数 1，条目 2）。
        #     这条反例专门守守恒式：按"条目数"而不是"桶计数"来汇总，会让同一笔提交
        #     在两个机的 C 表里各出现一次 ⇒ 有归属数虚增 ⇒ 「未归属 = 总数 − 有归属」永远对不上。
        _sc_commit(repo, f"{MACHINE_DIR}/DESKTOP-KQABATS/月账/2026-11.md", "m\n",
                   "docs: 一笔同时改两台机分区", post)
        # 同一次提交里再改 SIWPAN 分区（amend 进同一笔，而不是新开一笔）
        (repo / mdir).write_text("multi\n", encoding="utf-8")
        _sc_git_add(repo)
        _sc_amend(repo, "docs: 一笔同时改两台机分区", post)
        # ⚠ sha 必须在 amend **之后**取：amend 会重写提交号，先取后改会让断言永远不等
        #   （第一版就是这么假红的 —— 与"判据自己踩自己"是同一类错）。
        sha_multi = git(repo, "rev-parse", "HEAD").strip()
        multi_payload = collect(repo, "2026-11")
        multi_totals = multi_payload["totals"]
        per_machine_entries = (len(multi_payload["C_commits"]["SIWPAN"])
                               + len(multi_payload["C_commits"]["DESKTOP-KQABATS"]))
        cases.append(("一笔改两台机分区 ⇒ 只落一个桶（条目 3 / 计数 2，守恒不破）",
                      multi_totals["conservation_ok"]
                      and multi_totals["attributed_C_only"] == 2
                      and per_machine_entries == 3
                      and any(item["sha"] == sha_multi
                              for item in multi_payload["multi_machine_commits"])))

        # ⑧c 形态识别与盘符无关：E/Z 盘同一目录也认；不是这三个目录就不认
        cases.append(("承载痕迹按形态识别（E/Z 盘都认，非 repos/archive/nodejs 不认）",
                      all(CARRIER_PAT.search(_carrier_text(d, n))
                          for d, n in (("E", "repos"), ("Z", "archive"), ("Q", "nodejs")))
                      and not CARRIER_PAT.search(_carrier_text("Q", "projects"))))

        # ⑨ 三种「没有归属」分开计数（11 月整月在判据生效前 ⇒ 全部落在 uncovered 一侧）
        cases.append(("三种「没有归属」分开计数（真缺口再分 生效后/生效前）",
                      t["gate_covered_missing"] == 0
                      and t["gate_uncovered_missing"] == t["unattributed_after_split"]
                      and t["out_of_window"] == t["commits_in_month"]))

        # ⑨b 判据覆盖侧（12 月卷）：生效日之后的未归属必须记进 gate_covered，
        #     不能与"机制还不存在"的旧账混成一个数。
        dec = _sc_repo(Path(tmp) / "dec")
        _sc_commit(dec, "docs/其他.md", "z\n", "docs: 三源皆无（生效日后）", "2026-12-02T10:00:00")
        dec_payload = collect(dec, "2026-12")
        cases.append(("判据生效后的未归属记进 gate_covered（与旧账分开）",
                      dec_payload["totals"]["gate_covered_missing"] == 1
                      and dec_payload["totals"]["gate_uncovered_missing"] == 0))

        # ------------------------------------------------ 10 月卷（分机前）
        old = _sc_repo(Path(tmp) / "oct")
        _sc_commit(old, f"{MACHINE_DIR}/SIWPAN/月账/2026-10.md", "x\n",
                   "docs(ho): @SIWPAN 分机前的一笔", "2026-10-29T10:00:00", "SIWPAN")
        _sc_commit(old, "docs/其他.md", "y\n", "docs: 分机后的一笔", "2026-10-31T10:00:00")
        old_payload = collect(old, "2026-10")
        proto = old_payload["prototype_01"]["commits"]
        # ⑩ 分机前的**无标注**提交 → PROTOTYPE-01；**标题已带机名**的 → 记 B
        #    （ADR §D1.5「证据优先」：证据在，就不能假装没有。2026-10 实测 2 笔属于后者。）
        _sc_commit(old, f"{MACHINE_DIR}/SIWPAN/月账/2026-10.md", "z\n",
                   "docs: 分机前的另一笔（标题无机名）", "2026-10-28T10:00:00")
        old_payload = collect(old, "2026-10")
        proto = old_payload["prototype_01"]["commits"]
        cases.append(("分机前无标注 → PROTOTYPE-01；标题带机名 → 记 B（证据优先）",
                      old_payload["prototype_01"]["count"] == 1
                      and len(old_payload["B_commits"]["SIWPAN"]) == 1
                      and proto[0]["tag_in_subject"] == []))
        # ⑪ 原型机必须具名
        cases.append(("PROTOTYPE-01 是具名归档机（kind=archive、无 hostname）",
                      old_payload["prototype_01"]["machine_id"] == PROTOTYPE
                      and old_payload["prototype_01"]["kind"] == "archive"
                      and old_payload["prototype_01"]["hostname"] is None))

        md = render_markdown(payload)
        # ⑫ 人读版把三种「没有归属」分开写明 + 标明 C 级不可单用
        cases.append(("人读版分开写明三种「没有归属」且标注 C 级不可单用",
                      all(key in md for key in ("PROTOTYPE-01", "未归属", "out-of-window"))
                      and "不可单独作依据" in md))
        # ⑬ JSON 可序列化且含守恒标记
        # ⑯ 双口径一致性（ADR §D4.2b）：author 自算 == 带偏移时间戳交给 git
        cases.append(("双口径一致（author 自算 == rev-list 带偏移时间戳）",
                      t["count_cross_check"]["ok"]))
        cases.append(("JSON 可序列化且含守恒标记",
                      bool(json.dumps(payload, ensure_ascii=False))
                      and "conservation_ok" in payload["totals"]))

    # ⑰ 拒答这条路必须真的会走（口径打架 ⇒ exit 3 + 固定前缀 + 无数字）
    verdict_ok, verdict_note = _selfcheck_refusal()
    cases.append((f"口径打架 ⇒ 拒答（{verdict_note}）", verdict_ok))

    # ⑱ 口径回归的决定性负对照（author 10 月 / committer 11 月 ⇒ 必须归 10 月）
    ac_ok, ac_note = _selfcheck_author_vs_committer()
    cases.append((f"跨月提交按 author date 归月（{ac_note}）", ac_ok))

    passed = 0
    for name, ok in cases:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        passed += 1 if ok else 0
    print(json.dumps({"cases": len(cases), "passed": passed}, ensure_ascii=False))
    if passed == len(cases):
        print("SELFCHECK: PASS —— 两条硬要求（中文路径 / 未归属计数）都有反例兜底")
        return EXIT_OK
    print("SELFCHECK: FAIL —— 有判据没验过（见上）")
    return EXIT_FINDING


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="月账机器归属取证生成器（三源分级）")
    parser.add_argument("--month", default=None, help="YYYY-MM（默认本月）")
    parser.add_argument("--machine", default=None, help="只看某台机（STEM）")
    parser.add_argument("--repo", default=str(ROOT), help="仓根（默认本仓）")
    parser.add_argument("--out", default=None, help=f"输出目录（默认 {AUDIT_DIR}）")
    parser.add_argument("--json", action="store_true", dest="as_json", help="只打 JSON 到 stdout")
    parser.add_argument("--limit", type=int, default=40, help="人读版每个表最多列几行")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    month = args.month or _dt.date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        print(f"用法错：--month 需要 YYYY-MM，收到 {month!r}", file=sys.stderr)
        return EXIT_USAGE
    try:
        payload = collect(Path(args.repo), month, args.machine)
    except FileNotFoundError as error:
        print(f"ENV ERROR: {error}", file=sys.stderr)
        return EXIT_ENV
    except RuntimeError as error:
        print(f"ENV ERROR: git 调用失败：{error}", file=sys.stderr)
        return EXIT_ENV

    check = payload["totals"]["count_cross_check"]
    if not check["ok"]:
        # 口径打架时**不输出任何数字**：一个"看起来合理"的数被引用一次，
        # 后面所有人都会用它，而没人会回头查它是怎么来的。
        # 仍打印两个读数（读者要能自己看到"为什么打架"），退出码 3。
        print(f"{CALIBER_PREFIX} 两条独立口径不一致 —— author date 自算 {check['author']} 笔，"
              f"带偏移时间戳交给 git {check['revlist_offset']} 笔（窗口 {check['window']}）。"
              f"先查口径，别用这两组数字。", file=sys.stderr)
        print(f"{CALIBER_PREFIX} 退出码 {EXIT_CONFLICT}：工具给不出可信数字，"
              f"**不是**「仓里查出问题」，也不要把本条当通过", file=sys.stderr)
        return EXIT_CONFLICT

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK

    out_dir = Path(args.out) if args.out else Path(args.repo) / AUDIT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{month}.json"
    md_path = out_dir / f"{month}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload, limit=args.limit), encoding="utf-8")

    t = payload["totals"]
    print(f"machine_ledger: {month} commits={t['commits_in_month']} "
          f"A_sections={t['handover_sections_tagged']}/{t['handover_sections']} "
          f"B={t['attributed_B']} C={t['attributed_C_only']} "
          f"D_unattributed={t['unattributed_after_split']} "
          f"prototype_01={t['prototype_01']} carrier={t['prototype_carrier']} "
          f"cross={t['cross_machine_tagged']} out_of_window={t['out_of_window']}")
    print(f"  → {json_path}")
    print(f"  → {md_path}")
    print("  [note] 这是**证据汇总**，不是月账正文；归属判断留给人。C 级不可单独作依据。")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
