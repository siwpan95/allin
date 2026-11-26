#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器归属 trailer 判据（`Machine:`）—— registry 之外的编排层判据。

## 为什么要有这道判据（死结复述，实测数据在交接卷）

本仓 9/10/11 三个月的提交里，作者身份只有 `siwpan <siwpan@users.noreply.gitee.com>`
**一个**——`author` / `committer` 字段里没有机器信息，`git shortlog` 与 `.mailmap`
都救不了（官方文档明说：共享账号时"统计无法区分实际参与者"）。实测 2026-11：

| 月份 | 提交数 | 标题带 `@机器` | 触及某机分区 | **两源皆无** |
| --- | --- | --- | --- | --- |
| 2026-11 | 391 | 24 | 61 | **319（82%）** |

也就是说：**"这笔提交是哪台机器做的"这件事，过去从来没有被记录过。** 事后再怎么
考古，都只能在"标题里的 `@`"和"改过谁的分区"之间做推断——而推断不是证据。

## 判什么

`docs/事实源/机器/<STEM>/…` 是**机器分区**（铁律 6：只有该机可改自己的分区）。
于是有一条同义反复、却可机检的约束：

> **改了谁的分区，就必须声明自己是那台机器。**

判据：凡某提交改动了 `docs/事实源/机器/<STEM>/…`，该提交必须带 `Machine: <STEM>`
trailer；缺则判红；声明的机器与改动分区不一致（跨机越权）判红；声明了不存在的
机器名（拼错）也判红——拼错若放行，`Machine: SIWPAM` 会静默通过，
等于给拼写错误发免检证。

## 三种"没有 trailer"必须分开（不许混为一谈）

1. `merge` —— 合并提交。message 由 git 生成（`--no-ff` 时取 `-m` 或编辑器），
   **commit-msg 钩子在这种路径上的行为不可依赖**；且合并提交本身 `--name-only`
   是空集。→ 单列，不计入 blocking。
2. `squash` —— 平台（Gitee / GitHub）**Squash and merge** 会把 message 重写成
   "标题 + (#PR)"，逐条提交的 trailer **在服务端被丢弃**。网页端直接编辑/新建文件
   产生的提交同理：**它根本没经过本地钩子**。→ 单列，不计入 blocking，
   但**正签名才认**（`ticket (#12)` 形态 / `Merge pull request #12` 形态），
   不靠"看起来像"来猜。
3. `missing` —— 就是**忘了写**。→ 判红。

> 为什么宁可把"网页提交"错判成"忘了写"，也不反过来：错判成 `squash` 是**洗白**
> （真漏掉的机器归属从此拿不到证据），错判成 `missing` 只是多一次可见的修补动作
> （`git commit --amend` 或 `git rebase --exec` 补一行）。取证系统里，
> 假阳性可见、假阴性致命。

`--strict-rewritten` 可把 1/2 也判红（用于确认某窗口内**不该**有平台重写提交时）。

## 生效范围：只判 `EFFECTIVE_FROM` 之后的提交

历史 391 笔没有 trailer，追溯判红等于让判据一落地就常红——`D18`（交接卷按机标注）
与 `D19`（月账不按机归属）是同一先例：**只判生效之后，不逼迫改写历史**。
cutoff 是一个常量（`EFFECTIVE_FROM`），不是"最近 N 天"——后者会随运行时间漂移，
同一个提交今天绿明天红。

生效日之前的提交不是"绿"，也不是"红"，而是 **`out_of_window` 一等结论**：
不能用生效后的规则去判生效前的提交。它们逐日记在 `OUT-OF-WINDOW` 行里（带样本），
**归属问题另由 `tools/gate/machine_ledger.py` 取证**——判据不追责，不等于没有账。

> 两个分界别混：
> · `SPLIT_DATE = 2026-10-30`（在 machine_ledger.py 里）是**归属分界**：
>   此前机器分区事实源还不存在（只有单一 `本机事实.md`），commit 归 `PROTOTYPE-01`。
> · `EFFECTIVE_FROM = 2026-12-01` 是本文件的**判据分界**：从这天起按新规矩判。
> 判据窗口 ⊂ 归属分界之后，所以"判据只管该管的、不替历史定性"。

窗口内一个提交都没有时，本判据**不冒充通过**：打印 `[SKIP]` 与原因后退出 0。
另外挂一条**过期守卫**：cutoff 已过 `STALE_DAYS` 天而窗口内仍是 0 个提交 ⇒ exit 2
（constraint 配错或钩子被整体绕过，两种都是真问题，不能长期静默）。

## 用法

```bash
python tools/gate/check_machine_trailer.py                  # 判据（默认动作）
python tools/gate/check_machine_trailer.py --selfcheck      # 12 例负对照 + 变异探针
python tools/gate/check_machine_trailer.py --inject <msg>   # commit-msg 钩子调用（幂等）
python tools/gate/check_machine_trailer.py --since 2026-11-01 --until 2026-12-01  # 取证窗口
```

退出码：0 干净（或窗口为空并显式 SKIP）／1 有阻断／2 用法或配置错／3 环境错。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_FINDING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3

ROOT = Path(__file__).resolve().parents[2]  # tools/gate/ → 仓根
#: 机器分区根（相对仓根）。**不写绝对路径**：g01 判据禁机器绑定。
MACHINE_DIR = "docs/事实源/机器"
#: 归档机（`kind: archive`）：**不是真机** —— 无 hostname、无硬件，没人「是它」。
#: 它的分区目录确实存在（`docs/事实源/机器/PROTOTYPE-01/`，承载 2026-10-30 分机前的历史），
#: 但铁律 6 的「只有该机可改自己的分区」对一台虚构的机器不成立：谁整理那段历史，
#: 都是**跨机协作**，不是"该机在自己分区里干活"。
#: 因此**不要求 `Machine:` 声明**（要求了也没人能真声明），但改动仍可见（ledger 有记录）。
#: 这条豁免必须显式写死：靠"目录名看起来不像机器"来豁免，下一个人加机就会踩。
ARCHIVE_MACHINES = {"PROTOTYPE-01"}
TRAILER_KEY = "Machine"
#: 判据生效日：此前的提交不判（与 D18 / D19「只判生效之后」同一先例）。
#: 2026-12-01（不是落地日 11-26）：钩子目前只在 SIWPAN 上真正装好，定得太早会让
#: 另两台机的**第一次互动就是违规** —— 判据不该以「谁先撞上」的方式分配责任。
#: **改这个值等于改判据范围**；改之前先看 ADR-0012 §D2.5 ——
#: 本常量与 ADR 不一致时**以 ADR 为准**（本次就是靠这句话才没让两处各自漂）。
#: 必须同时改本文件头部说明与交接卷记账。
EFFECTIVE_FROM = "2026-12-01"
#: 过期守卫：cutoff 之后这么久还没有任何提交被窗口覆盖 ⇒ 配置错或被绕过。
STALE_DAYS = 45
#: 预告窗：生效日之前的这几天，**只 WARN 不判红**（ADR-0012 §D2.5）。
#: 作用是在强制之前先拿到"采纳率"读数 —— 否则到 2026-12-01 才第一次知道谁没装钩子，
#: 而那时第一批互动对象就是违规，判据活不过一周。
PREVIEW_FROM = "2026-11-26"
#: 复审 trailer：`Machine: <A>` 却改了 `<B>` 的分区时，`Machine-Review: <B>`
#: 表示"B 那边的改动另有 B 的人过目"（铁律 6 在提交层唯一可判的形态，ADR §D2.3/§D3.3）。
REVIEW_KEY = "Machine-Review"

FS = "\x1f"   # 字段分隔
RS = "\x1e"   # 记录分隔

#: 平台 squash 的**正签名**（不是"看起来像"）：标题以 `(#12)` 收尾。
SQUASH_SUBJECT = re.compile(r"\(#\d+\)\s*$")
#: 平台合并的**正签名**：GitHub 默认 `Merge pull request #12 …`，git 本地 `Merge branch '…'`。
PLATFORM_MERGE = re.compile(r"^(Merge pull request #\d+|Merge branch '|Merge remote-tracking branch ')")


# ---------------------------------------------------------------- 基础设施
def git(repo: Path | str, *args: str, check: bool = True, input_text: str | None = None,
        env: dict | None = None):
    """调 git。**`core.quotepath=false` 是硬性要求**：不关掉它，中文路径会被转义成
    `docs/\\346\\234\\272\\345\\231\\250/…`，分区匹配全线失效——而失效方式是"静默没命中"，
    看起来就像"这笔提交没碰分区"。这个坑已经踩过一次（月账取证）。
    """
    cmd = ["git", "-c", "core.quotepath=false", *args]
    proc = subprocess.run(
        cmd, cwd=str(repo), capture_output=True, text=True,
        encoding="utf-8", errors="replace", input=input_text, env=env,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{proc.stderr.strip()[:400]}")
    return proc


def discover_machines(repo: Path | str) -> list[str]:
    """机器标识 = `docs/事实源/机器/` 下的子目录名（g19/g20 的 stem 口径）。"""
    base = Path(repo) / MACHINE_DIR
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))


def aliases_for(machines: list[str]) -> dict[str, str]:
    """`DESKTOP-KQABATS` → 别名 `KQABATS`（提交标题里实测就是这么写的短形态）。

    由 stem 派生而不是另立一张表：多一张表就多一处漂移源，而这里没有第二种事实。
    """
    out = {}
    for stem in machines:
        out[stem.upper()] = stem
        if "-" in stem:
            out.setdefault(stem.split("-", 1)[1].upper(), stem)
    return out


# ---------------------------------------------------------------- 读取提交
def read_commits(repo: Path | str, since: str | None = None, until: str | None = None,
                 rev: str = "HEAD") -> list[dict]:
    """按机读口径读出提交（sha / committer 日期 / 父提交 / 标题 / trailer / 变更文件）。

    trailer 走 git 内建解析器 `%(trailers:key=…)`，与 `git interpret-trailers --parse`
    **同一实现**（`trailer.c`）；`--selfcheck` 里有一条用例专门断言两种读法一致——
    「同一事实写在两处」必须由机器盯着，否则迟早分家。
    """
    fmt = (
        f"%x1e%H{FS}%cd{FS}%P{FS}%s{FS}"
        f"%(trailers:key={TRAILER_KEY},valueonly,separator=;){FS}"
        f"%(trailers:key={REVIEW_KEY},valueonly,separator=;)"
    )
    args = ["log", "--date=short", f"--format={fmt}", "--name-only"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    args.append(rev)
    out = git(repo, *args).stdout

    commits = []
    for chunk in out.split(RS):
        if not chunk.strip():
            continue
        lines = chunk.split("\n")
        parts = lines[0].split(FS)
        if len(parts) < 5:
            continue
        commits.append({
            "sha": parts[0].strip(),
            "date": parts[1].strip(),
            "parents": parts[2].split(),
            "subject": parts[3].strip(),
            "trailers": [t.strip() for t in parts[4].split(";") if t.strip()],
            "reviews": [t.strip().upper() for t in parts[5].split(";") if t.strip()]
                       if len(parts) > 5 else [],
            "files": [ln.strip() for ln in lines[1:] if ln.strip()],
        })
    return commits


def touched_machines(files: list[str], machines: list[str]) -> dict[str, list[str]]:
    """提交改动了哪些**真机**的分区（→ {stem: [文件…]}）。归档机不参与（见 ARCHIVE_MACHINES）。"""
    out: dict[str, list[str]] = {}
    for path in files:
        for stem in machines:
            if stem in ARCHIVE_MACHINES:
                continue
            if path.startswith(f"{MACHINE_DIR}/{stem}/"):
                out.setdefault(stem, []).append(path)
    return out


def touches_archive(files: list[str]) -> list[str]:
    """提交是否改动了归档机分区（只作可见性记录，不判红）。"""
    hit = []
    for path in files:
        for stem in ARCHIVE_MACHINES:
            if path.startswith(f"{MACHINE_DIR}/{stem}/"):
                hit.append(path)
    return hit


# ---------------------------------------------------------------- 判定
def classify(commit: dict) -> str:
    """`normal` / `merge` / `squash` —— 后两者是"技术上无法带 trailer"。"""
    if len(commit["parents"]) > 1:
        return "merge"
    subject = commit["subject"]
    if SQUASH_SUBJECT.search(subject) or PLATFORM_MERGE.match(subject):
        return "squash"
    return "normal"


def _mutated() -> bool:
    """变异探针：把"改分区"整段判据摘掉，用于证明 `--selfcheck` 不是装饰。

    自检的价值全在"它会红"：一个恒返回 0 的自检与没有自检在退出码上完全同形。
    所以 `--selfcheck` 会**再跑一遍本进程**（带此环境变量），断言届时自检必须变红。
    """
    return os.environ.get("ALLIN_MACHINE_TRAILER_MUTATE") == "no-block"


def judge(commits: list[dict], machines: list[str], effective_from: str,
          strict_rewritten: bool = False, exemptions: dict[str, dict] | None = None,
          preview_from: str | None = None) -> dict:
    """`exemptions`：例外台账（ADR §D2.4 通道 (b)），`{sha前缀: {id, expires, …}}`。

    两条豁免通道缺一不可：正签名（平台 squash 的 `(#N)`）覆盖"能确定形态"的那一半；
    **例外台账**覆盖 git 给不出确定形态的那一半（本地 squash、`rebase --exec`、
    历史迁移、网页直接编辑）。只有 (a) 没有 (b) 时，那一半只能靠人手工忽略 ——
    那就是白名单，而且是没人能复核的白名单。
    """
    exemptions = exemptions or {}
    out = {
        "effective_from": effective_from,
        "scanned": 0, "requiring": 0,
        "missing": [], "cross": [], "unknown": [],
        "rewritten": [], "blocking": 0,
        #: **一等结论**（不是"绿"）：生效日之前的提交不适用本判据。
        #: 单列而不是静默跳过 —— 静默跳过会让「窗口外」与「判过且干净」同形，
        #: 那正是本仓反复在治的病（没判 ≠ 没问题）。见 ADR-0011 D3-H 的 undetermined 立场。
        "out_of_window": {"count": 0, "sample": []},
        #: 动过归档机分区的提交：不算违规，但要看得到（"看不见的豁免"就是免检章）
        "archive_touched": 0,
        #: 预告窗（生效日之前几天）：只 WARN 并逐条列出，退出码不变（ADR §D2.5）。
        #: 作用是在强制之前先拿到采纳率读数，而不是到生效日才第一次知道谁没装钩子。
        "preview": [],
        #: 命中例外台账的提交（通道 b）：豁免但必须留痕
        "exempted_by_ledger": [],
        #: 台账条目**已在提交之前到期** ⇒ 不豁免，按 MISSING 判红（带台账编号）
        "expired_ledger_hits": [],
    }
    known = set(machines)
    for commit in commits:
        if commit["date"] < effective_from:
            # 预告窗：生效前 `PREVIEW_FROM` 起的提交，**逐条 WARN**（只统计采纳率，不判红）。
            in_preview = preview_from is not None and commit["date"] >= preview_from
            if in_preview:
                touched_preview = touched_machines(commit["files"], machines)
                declared_preview = [t.strip().upper() for t in commit["trailers"] if t.strip()]
                if touched_preview and not set(touched_preview) <= set(declared_preview):
                    out["preview"].append({
                        "sha": commit["sha"], "date": commit["date"],
                        "subject": commit["subject"], "touched": sorted(touched_preview),
                        "declared": declared_preview,
                    })
            out["out_of_window"]["count"] += 1
            if len(out["out_of_window"]["sample"]) < 5:
                out["out_of_window"]["sample"].append(
                    {"sha": commit["sha"], "date": commit["date"],
                     "subject": commit["subject"]})
            continue  # 历史不追溯
        out["scanned"] += 1
        if touches_archive(commit["files"]):
            out["archive_touched"] += 1
        kind = classify(commit)
        touched = {} if _mutated() else touched_machines(commit["files"], machines)
        declared = [t.strip().upper() for t in commit["trailers"] if t.strip()]

        if kind != "normal":
            # merge / squash **一律单列**，包括 `touched` 为空的情形：
            # `git log --name-only` 对合并提交不输出文件集（它没有"自己的 diff"），
            # 所以"文件集为空"不等于"没碰分区"，而是"看不见"。看不见的东西
            # 必须被列出来，不能因为它是空集就从视野里消失。
            out["rewritten"].append({
                "kind": kind, "sha": commit["sha"], "date": commit["date"],
                "subject": commit["subject"], "touched": sorted(touched),
                "why": "合并提交 message 由 git 生成、文件集不可见" if kind == "merge"
                       else "平台 squash / 网页提交会丢弃或从未产生 trailer",
            })
            if strict_rewritten:
                out["blocking"] += 1
            continue

        if not touched:
            continue
        out["requiring"] += 1
        touched_names = sorted(touched)
        bad_unknown = [d for d in declared if d not in known]
        if bad_unknown:
            out["unknown"].append({
                "sha": commit["sha"], "date": commit["date"], "declared": bad_unknown,
                "known": machines,
            })
            out["blocking"] += 1
        ledger_hit = next((key for key in exemptions if commit["sha"].startswith(key)), None)
        if ledger_hit is not None:
            rule = exemptions[ledger_hit]
            expires = str(rule.get("expires") or "")
            # 判的是「**这笔提交**发生时豁免还有效吗」，不是「今天还有效吗」。
            # 提交日期 <= 到期日 ⇒ 当时合法 ⇒ 豁免（哪怕今天已过期，也只注明，不追溯判红）；
            # 提交日期 >  到期日 ⇒ 当时就没豁免 ⇒ 按"忘了写"判红，并带出台账编号。
            if not expires or commit["date"] <= expires:
                note = ""
                if expires and expires < _dt.date.today().isoformat():
                    note = f"（台账已于 {expires} 过期，但本提交发生在有效期内）"
                out["exempted_by_ledger"].append({
                    "sha": commit["sha"], "date": commit["date"], "touched": touched_names,
                    "exception": rule, "note": note,
                })
                continue           # 通道 (b)：提交当时在豁免期内 ⇒ 不判红，但留痕
            out["expired_ledger_hits"].append({
                "sha": commit["sha"], "date": commit["date"], "touched": touched_names,
                "exception": rule, "evidence": f"台账 {rule['id']} 已于 {expires} 到期，"
                                               f"本提交 {commit['date']} 在其后",
            })
            # 落到下面按 MISSING 判红（原始缺陷还在：这笔提交确实没声明机器）
        if not declared:
            out["missing"].append({
                "sha": commit["sha"], "date": commit["date"], "touched": touched_names,
                "subject": commit["subject"],
                "files": [f for stem in touched_names for f in touched[stem]][:6],
            })
            out["blocking"] += 1
        else:
            reviews = set(commit.get("reviews") or [])
            # `Machine: A` 却改 B 的分区 ⇒ 红；**除非**同时带 `Machine-Review: B`
            # （B 那边另有人过目）。这是铁律 6 在提交层唯一可判的形态（ADR §D2.3/§D3.3）。
            lacked = [s for s in touched_names if s not in declared and s not in reviews]
            if lacked:
                out["cross"].append({
                    "sha": commit["sha"], "date": commit["date"],
                    "declared": declared, "touched": touched_names, "lacked": lacked,
                    "subject": commit["subject"],
                })
                out["blocking"] += 1
    return out


# ---------------------------------------------------------------- 例外台账（通道 b）
def load_exemptions(repo: Path | str, path: str | None = None) -> dict[str, dict]:
    """读例外台账（`exceptions.yml`），取 `gate: machine-trailer` 且**未过期**的条目。

    为什么需要这条通道（ADR §D2.4）：本地 squash、`rebase --exec`、历史迁移、
    网页直接编辑 —— git 给不出可判的确定形态（正签名抓不到）。这类提交要么靠台账，
    要么靠人手工忽略；**手工忽略就是白名单**，而白名单没人复核。
    台账每条都要求 approver / compensating / expires（g18 的老格式，直接复用）。

    过期条目**不再豁免**，并且**不由本判据判红**：过期是 g18 的判据对象
    （一处口径一处判），本判据只按"当前有效的豁免"办事，不重复罚。
    """
    candidates = [Path(path)] if path else [
        Path(repo) / "exceptions.yml",
        Path(repo) / ".venv" / "Lib" / "site-packages" / "allin_governance"
        / "_gatesuite" / "exceptions.yml",
        Path(repo) / ".venv" / "lib" / "python3.12" / "site-packages" / "allin_governance"
        / "_gatesuite" / "exceptions.yml",
    ]
    target = next((c for c in candidates if c.is_file()), None)
    if target is None:
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    # ⚠ **不在这里按 today 过滤**（ADR §D2.4 裁定）：过期与否要和**提交日期**比，
    # 而不是和"今天"比。按今天判会把"在豁免有效期内合法提交"的老提交追溯性地判红 ——
    # 判据一旦开始罚历史，人就学会绕过它。过滤挪到 judge()，逐提交比。
    out: dict[str, dict] = {}
    for entry in data.get("exceptions") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("gate", "")).strip() != "machine-trailer":
            continue
        if str(entry.get("status", "open")).strip().lower() != "open":
            continue
        expires = str(entry.get("expires", "")).strip()
        target_text = str(entry.get("target", "")).strip()
        for token in target_text.replace("，", ",").split(","):
            token = token.strip().split()[0] if token.strip() else ""
            if len(token) >= 7 and all(ch in "0123456789abcdef" for ch in token.lower()):
                out[token.lower()] = {
                    "id": entry.get("id", "?"), "expires": expires or "?",
                    "approver": entry.get("approver", "?"),
                }
    return out


# ---------------------------------------------------------------- 注入
def machine_stem() -> str:
    """本机标识：hostname 按 stem 口径**大写**（`siwpan` → `SIWPAN`）。

    与 g19/g20 的 stem 一致（`facts/machine/*.json.machine_id` 就是大写 hostname）。
    容器/CI 里 hostname 是随机串，可用 `ALLIN_MACHINE_STEM` 显式覆盖。
    """
    override = os.environ.get("ALLIN_MACHINE_STEM", "").strip()
    if override:
        return override.upper()
    try:
        return socket.gethostname().strip().upper()
    except OSError:
        return ""


def parse_trailers(repo: Path | str, message_file: str) -> list[str]:
    proc = git(repo, "interpret-trailers", "--parse", message_file, check=False)
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def inject(repo: Path | str, message_file: str, quiet: bool = False, stem: str | None = None) -> int:
    """在 commit-msg 阶段追加 `Machine: <STEM>`。**幂等**：已有该 trailer 就什么都不做。

    幂等不是洁癖：`core.hooksPath` 与 pre-commit 两条路径可能同时生效，
    非幂等的注入会把 trailer 叠成两行（`Machine: SIWPAN` ×2），那本身就是脏数据。

    **注入失败不阻断提交**：钩子的第一职责是别把人的提交搞丢。失败只警告——
    漏了 trailer 由判据在下次跑批里抓（那时是红的、可见的），
    比"提交被一个写消息的钩子挡死"要好。
    """
    try:
        text = Path(message_file).read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        if not quiet:
            print(f"[commit-msg] 读不到提交信息（{message_file}）：{error}", file=sys.stderr)
        return EXIT_OK
    # 纯注释 / 空消息：git 随后会以 "empty commit message" 自行中止，无需注入。
    if not [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]:
        return EXIT_OK
    try:
        existing = parse_trailers(repo, message_file)
    except RuntimeError as error:
        existing = []
        if not quiet:
            print(f"[commit-msg] trailer 解析失败：{error}", file=sys.stderr)
    if any(ln.split(":", 1)[0].strip().lower() == TRAILER_KEY.lower() for ln in existing):
        if not quiet:
            print(f"[commit-msg] 已有 {TRAILER_KEY}: trailer，跳过注入（幂等）")
        return EXIT_OK
    stem = (stem or machine_stem()).upper()
    if not stem:
        if not quiet:
            print("[commit-msg] 取不到 hostname，无法注入 Machine: trailer（用 "
                  "ALLIN_MACHINE_STEM 显式指定）", file=sys.stderr)
        return EXIT_OK
    proc = git(repo, "interpret-trailers", "--in-place",
               f"--trailer={TRAILER_KEY}: {stem}", message_file, check=False)
    if proc.returncode != 0:
        if not quiet:
            print(f"[commit-msg] 注入失败（不阻断提交）：{proc.stderr.strip()[:200]}", file=sys.stderr)
        return EXIT_OK
    if not quiet:
        print(f"[commit-msg] 已追加 {TRAILER_KEY}: {stem}")
    return EXIT_OK


# ---------------------------------------------------------------- 门禁主流程
def run_gate(repo: Path, since: str | None, until: str | None, effective_from: str,
             strict_rewritten: bool, as_json: bool,
             exceptions_path: str | None = None) -> int:
    machines = discover_machines(repo)
    if not machines:
        print(f"ENV ERROR: {Path(repo) / MACHINE_DIR} 不存在或没有子目录 —— "
              "没有机器分区，本判据无可判对象（这可能是跑错了仓）。", file=sys.stderr)
        return EXIT_ENV

    commits = read_commits(repo, since=since, until=until)
    exemptions = load_exemptions(repo, exceptions_path)
    report = judge(commits, machines, effective_from, strict_rewritten,
                   exemptions=exemptions, preview_from=PREVIEW_FROM)
    report["machines"] = machines
    report["strict_rewritten"] = strict_rewritten

    # 单独判一句"判据有没有真的判过东西"：scanned 0 + exit 0 + 无声，与"判了没问题"
    # 完全同形，那正是本仓 `check_blind_gates.py` 要抓的盲门。
    if report["scanned"] == 0:
        if as_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        # 空窗口是 **not a pass**：`scanned 0` 且计入 skipped（既不是绿、也不是 exempted）。
        print(f"machine_trailer: scanned 0 commit(s) since {effective_from}; blocking 0; "
              f"skipped 1; out-of-window {report['out_of_window']['count']}")
        stale = _stale_check(effective_from)
        if stale:
            # ADR §D2.5：过期守卫**判红**（exit 1），不是 exit 2。
            # 理由：生效 45 天后窗口仍 0 条提交，只有两种可能 —— 常量配错，或提交整体
            # 绕过了钩子；两种都意味着**判据根本没在看东西**，而"没在看"必须与
            # "看了没问题"分开。
            print(f"BLOCK STALE-WINDOW {stale}", file=sys.stderr)
            return EXIT_FINDING
        print(f"[SKIP] machine_trailer:skip(no-commits-since-cutoff:{effective_from}) "
              "—— 判据已接线，但窗口内没有任何提交可判（not a pass）")
        return EXIT_OK

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return EXIT_FINDING if report["blocking"] else EXIT_OK


def _stale_check(effective_from: str) -> str | None:
    try:
        cutoff = _dt.date.fromisoformat(effective_from)
    except ValueError:
        return None
    overdue = (_dt.date.today() - cutoff).days
    if overdue > STALE_DAYS:
        return (f"判据生效日 {effective_from} 已过 {overdue} 天（阈值 {STALE_DAYS}），"
                "窗口内仍无任何提交可判 —— 要么 cutoff 配错，要么提交整体绕过了钩子。"
                "长期静默的判据不是判据。")
    return None


def _print_human(report: dict) -> None:
    print(f"machine_trailer: scanned {report['scanned']} commit(s) since "
          f"{report['effective_from']}; requiring {report['requiring']}; "
          f"blocking {report['blocking']}; rewritten {len(report['rewritten'])}; "
          f"out-of-window {report['out_of_window']['count']}; "
          f"preview {len(report['preview'])}; "
          f"exempt-by-ledger {len(report['exempted_by_ledger'])}")
    for item in report["preview"]:
        print(f"  WARN PREVIEW {item['sha'][:8]} {item['date']} 触及 "
              f"{','.join(item['touched'])} 却未声明 —— 预告窗（{PREVIEW_FROM} 起）只提示"
              f"不判红：到生效日 {report['effective_from']} 这就是红")
        print(f"        {item['subject'][:70]}")
    for item in report["exempted_by_ledger"]:
        rule = item["exception"]
        print(f"  EXEMPT-BY-LEDGER {item['sha'][:8]} {item['date']} 台账 {rule['id']}"
              f"（到期 {rule['expires']} / 批准 {rule['approver']}）触及 "
              f"{','.join(item['touched'])} —— 通道 (b)：git 给不出确定形态时的人工登记"
              f"{item.get('note', '')}")
    if report["archive_touched"]:
        print(f"  ARCHIVE-EXEMPT {report['archive_touched']} 笔提交动过归档机分区"
              f"（{'/'.join(sorted(ARCHIVE_MACHINES))}）—— 归档机不是真机，不要求 Machine: 声明")
    if report["out_of_window"]["count"]:
        print(f"  OUT-OF-WINDOW {report['out_of_window']['count']} 笔提交早于生效日 "
              f"{report['effective_from']} —— **不适用**本判据（不是绿、不是红）。"
              "它们的归属由 tools/gate/machine_ledger.py 取证，不由本判据追责")
    for item in report["missing"]:
        print(f"  BLOCK MISSING {item['sha'][:8]} {item['date']} 触及 {','.join(item['touched'])} 分区"
              f"但无 {TRAILER_KEY}: trailer —— 该提交改了谁的分区，就必须声明自己是那台机器"
              f"（铁律 6）。修复：git commit --amend 补 `{TRAILER_KEY}: {item['touched'][0]}`")
        print(f"        {item['subject'][:70]}")
        for f in item["files"]:
            print(f"        · {f}")
    for item in report["cross"]:
        print(f"  BLOCK CROSS-MACHINE {item['sha'][:8]} {item['date']} 声明 "
              f"{','.join(item['declared'])} 却改了 {','.join(item['lacked'])} 的分区"
              "（跨机越权：只有该机可改自己的分区）")
        print(f"        {item['subject'][:70]}")
    for item in report["unknown"]:
        print(f"  BLOCK UNKNOWN-MACHINE {item['sha'][:8]} {item['date']} 声明了不存在的机器 "
              f"{','.join(item['declared'])}（拼错会被静默放行，故判红）"
              f"；已知：{','.join(item['known'])}")
    for item in report["rewritten"]:
        scope = ",".join(item["touched"]) if item["touched"] else "文件集不可见"
        print(f"  REWRITTEN {item['kind']} {item['sha'][:8]} {item['date']} "
              f"[{scope}] —— {item['why']}；单列不计入 blocking")
        print(f"        {item['subject'][:70]}")
    if report["rewritten"] and not report["strict_rewritten"]:
        print(f"  [note] {len(report['rewritten'])} 笔属「技术上无法带 trailer」（merge / 平台 squash），"
              "已与「忘了写」分开单列；`--strict-rewritten` 可把它们也判红")


# ---------------------------------------------------------------- 自检
def _fixture_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "SelfCheck"), ("user.email", "selfcheck@example.invalid"),
                       ("commit.gpgsign", "false"), ("core.hooksPath", os.devnull)):
        git(repo, "config", key, value)
    # 只建**空目录**（git 不跟踪空目录）：分区文件由各用例自己造，
    # 否则初始提交会顺手带走两机分区 ⇒ 每个用例都被同一笔"既成事实"拖红，
    # 用例之间就不再独立（每个用例只该破坏自己那一维）。
    for stem in ("SIWPAN", "DESKTOP-KQABATS"):
        (repo / MACHINE_DIR / stem / "月账").mkdir(parents=True)
    (repo / "docs" / "其他.md").write_text("公共文档\n", encoding="utf-8")
    _commit(repo, "docs/其他.md", "公共文档 v0\n", "chore: 初始化")
    return repo


def _commit(repo: Path, rel: str, content: str, message: str, trailer: str | None = None,
            when: str | None = None) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    msg = message.rstrip("\n") + "\n"
    if trailer:
        msg += f"\n{TRAILER_KEY}: {trailer}\n"
    env = dict(os.environ)
    if when:  # 造"生效日之前"的提交：判据的边界只能靠改变提交日期来验
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    git(repo, "commit", "-q", "-F", "-", input_text=msg, env=env)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def _msg_file(base: Path, text: str) -> str:
    path = base / "COMMIT_EDITMSG"
    path.write_text(text, encoding="utf-8")
    return str(path)


def selfcheck() -> int:
    """12 例负对照 + 一条变异探针。**每个用例只破坏自己那一维**，否则"红了"可能
    是被别的判据拦下的（本仓 D1–D17 的自检就踩过这个坑：三个用例同时带着 §99，
    `caught=3` 是假象）。
    """
    cases: list[tuple[str, str, bool]] = []   # (名字, 期望 "block"/"clean", 实际是否命中)
    caught = clean = misreports = 0
    mutated_run = os.environ.get("ALLIN_MACHINE_TRAILER_MUTATE") == "no-block"
    with tempfile.TemporaryDirectory(prefix="machine-trailer-") as tmp:
        tmp_path = Path(tmp)
        n = 0

        def new_repo(tag: str) -> Path:
            nonlocal n
            n += 1
            return _fixture_repo(tmp_path / f"{n:02d}-{tag}")

        def check(name: str, repo: Path, expect_block: bool, strict: bool = False) -> dict:
            nonlocal caught, clean, misreports
            report = judge(read_commits(repo), discover_machines(repo), "1970-01-01", strict)
            blocked = bool(report["blocking"])
            if expect_block:
                got = blocked
                if mutated_run:
                    got = False  # 变异态：判红逻辑被摘掉，这个用例必然不再命中 —— 见下方断言
                caught += 1 if got else 0
            else:
                got = blocked
                clean += 1 if not got else 0
                if got:
                    misreports += 1
            cases.append((name, "block" if expect_block else "clean", got))
            return report

        # ① 干净态：改分区 + 声明自己 → 不判红
        repo = new_repo("clean")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "本机记录\n",
                "docs(SIWPAN): 记一笔", trailer="SIWPAN")
        check("改分区且声明正确 → 干净", repo, False)

        # ② 缺 trailer → 判红（负对照之一：必须红得出来）
        repo = new_repo("missing")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "偷偷改了\n", "docs: 更新月账")
        report = check("改分区但无 trailer → 红", repo, True)
        if not report["missing"]:
            cases.append(("缺 trailer 应归入 MISSING 而非别的类", "MISSING", False))
            misreports += 1

        # ③ 补上 trailer → 变绿（证明红是"缺这一行"造成的，不是别的）
        #    注意这里是 **amend 同一笔提交**，不是再补一笔：再补一笔的话，
        #    上一笔的缺失仍在窗口里，用例验到的是"历史没被洗掉"而不是"补了就绿"。
        git(repo, "commit", "-q", "--amend", "-F", "-",
            input_text="docs(SIWPAN): 更新月账\n\nMachine: SIWPAN\n")
        report = check("补上 trailer → 绿", repo, False)

        # ④ 跨机越权：改 SIWPAN 分区却声明 KQABATS → 判红
        repo = new_repo("cross")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "越权\n",
                "docs(KQABATS): 代改他机", trailer="DESKTOP-KQABATS")
        check("改他机分区但声明自己 → 红（跨机越权）", repo, True)

        # ⑤ 拼错机器名 → 判红（拼错放行 = 给拼写错误发免检证）
        repo = new_repo("unknown")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "拼错\n",
                "docs: 拼错机名", trailer="SIWPAM")
        check("声明不存在的机器名 → 红", repo, True)

        # ⑥ 无关提交不带 trailer → 不判红（判据只管分区，不搞全员登记）
        repo = new_repo("unrelated")
        _commit(repo, "docs/其他.md", "无关改动\n", "docs: 改公共文档")
        check("未触及分区且无 trailer → 干净（不误伤）", repo, False)

        # ⑦ 多机声明：同时改两机分区且都声明 → 干净
        repo = new_repo("multi")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "a\n", "docs: 双机", trailer="SIWPAN")
        git(repo, "commit", "-q", "--amend", "-F", "-",
            input_text="docs: 双机\n\nMachine: SIWPAN\nMachine: DESKTOP-KQABATS\n")
        (repo / MACHINE_DIR / "DESKTOP-KQABATS" / "月账" / "2026-11.md").write_text("b\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-F", "-",
            input_text="docs: 双机改动\n\nMachine: SIWPAN\nMachine: DESKTOP-KQABATS\n")
        check("多机分区都被声明 → 干净", repo, False)

        # ⑧ merge 提交：单列 REWRITTEN，不重复计入 blocking
        repo = new_repo("merge")
        git(repo, "checkout", "-q", "-b", "feat")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "分支上改\n", "docs: 分支改月账")
        git(repo, "checkout", "-q", "main")
        _commit(repo, "docs/其他.md", "主干改动\n", "chore: 主干推进")
        git(repo, "merge", "--no-ff", "-q", "feat", "-m", "merge: 并入 feat")
        report = judge(read_commits(repo), discover_machines(repo), "1970-01-01")
        kinds = {item["kind"] for item in report["rewritten"]}
        found_merge = "merge" in kinds
        # 分支上那笔（普通提交、无 trailer）仍应判红 —— merge 单列不等于"整条分支免检"
        cases.append(("merge 提交归入 REWRITTEN（不计 blocking）", "merge", found_merge))
        if found_merge:
            caught += 1
        else:
            misreports += 1
        cases.append(("merge 不豁免分支上的普通提交", "block", bool(report["blocking"])))
        if report["blocking"]:
            caught += 1
        else:
            misreports += 1

        # ⑨ 平台 squash：正签名 `(#12)` → 单列 REWRITTEN；--strict 时判红
        repo = new_repo("squash")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "网页改\n", "docs: 网页端改月账 (#12)")
        loose = judge(read_commits(repo), discover_machines(repo), "1970-01-01", False)
        strict = judge(read_commits(repo), discover_machines(repo), "1970-01-01", True)
        ok = (bool(loose["rewritten"]) and not loose["blocking"]) and bool(strict["blocking"])
        cases.append(("squash 正签名 → 单列且非阻断；--strict 判红", "rewritten", ok))
        caught += 1 if ok else 0
        misreports += 0 if ok else 1

        # ⑩ 中文路径必须命中（quotepath=false 的负对照）：
        #    不关 quotepath，路径会变成 `docs/\346\234\272…`，分区匹配**静默**失效 ——
        #    表现是"这笔提交没碰分区"，与"确实没碰"完全同形。
        repo = new_repo("quotepath")
        sha = _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "中文\n", "docs: 中文路径")
        raw = read_commits(repo)
        hit = [c for c in raw if c["sha"] == sha]
        paths = hit[0]["files"] if hit else []
        ok = any(p.startswith(f"{MACHINE_DIR}/SIWPAN/") for p in paths) and not any("\\3" in p for p in paths)
        cases.append(("中文路径以 UTF-8 原样读出并命中分区", "block" if ok else "PATH", ok))
        caught += 1 if ok else 0
        misreports += 0 if ok else 1

        # ⑪ 两种读法一致（`--parse` vs log 内建 trailer 解析器）
        repo = new_repo("readers")
        sha = _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "比对\n",
                      "docs: 比对读法", trailer="SIWPAN")
        parsed = parse_trailers(repo, _msg_file(tmp_path, git(repo, "log", "-1", "--format=%B").stdout))
        from_log = [c for c in read_commits(repo) if c["sha"] == sha]
        from_log_trailers = from_log[0]["trailers"] if from_log else []
        ok = parsed == [f"{TRAILER_KEY}: SIWPAN"] and from_log_trailers == ["SIWPAN"]
        cases.append(("`interpret-trailers --parse` 与 log 内建解析一致", "block" if ok else "READER", ok))
        caught += 1 if ok else 0
        misreports += 0 if ok else 1

        # ⑫ 注入幂等：连注两次仍只有一行 `Machine:`
        repo = new_repo("inject")
        msg = _msg_file(tmp_path, "feat: 某改动\n")
        inject(repo, msg, quiet=True, stem="SIWPAN")
        inject(repo, msg, quiet=True, stem="SIWPAN")
        body = Path(msg).read_text(encoding="utf-8")
        ok = body.count(f"{TRAILER_KEY}:") == 1 and "Machine: SIWPAN" in body
        cases.append(("注入幂等（两次仍一行）", "block" if ok else "INJECT", ok))
        caught += 1 if ok else 0
        misreports += 0 if ok else 1

        # ⑬ 生效日之前的提交 → **out-of-window 一等结论**（不适用，既不是绿也不是红）
        #    理由（§233.1 的同一精神）：不能用生效后的规则去判生效前的提交。
        #    造法：改 8RSV60V 分区 + trailer 写 8RSV60V（本该绿）+ 提交日期 2026-10-29
        #    （分机事实源 2026-10-30 才建立，此时连"该机分区"这个概念都还没有）。
        repo = new_repo("out-of-window")
        old_sha = _commit(repo, f"{MACHINE_DIR}/DESKTOP-8RSV60V/月账/2026-10.md", "旧账\n",
                          "docs(8RSV60V): 分机前的一笔", trailer="DESKTOP-8RSV60V",
                          when="2026-10-29T10:00:00")
        report = judge(read_commits(repo), discover_machines(repo), EFFECTIVE_FROM)
        ok = (report["blocking"] == 0
              and report["out_of_window"]["count"] >= 1
              and any(item["sha"] == old_sha for item in report["out_of_window"]["sample"]))
        cases.append(("生效日之前的提交 → out-of-window（不适用，非绿非红）",
                      "block" if ok else "OUT_OF_WINDOW", ok))
        caught += 1 if ok else 0
        misreports += 0 if ok else 1

        # ⑬b 归档机（`kind: archive`）不要求声明：无人「是它」，但改动要看得见。
        repo = new_repo("archive")
        (repo / MACHINE_DIR / "PROTOTYPE-01" / "月账").mkdir(parents=True, exist_ok=True)
        _commit(repo, f"{MACHINE_DIR}/PROTOTYPE-01/月账/2026-09.md", "归档\n",
                "docs: 整理原型机时期的历史")
        report = judge(read_commits(repo), discover_machines(repo), "1970-01-01")
        archive_ok = report["blocking"] == 0 and report["archive_touched"] >= 1
        cases.append(("归档机分区不要求 Machine: 声明，但改动被记录（ARCHIVE-EXEMPT）",
                      "block" if archive_ok else "ARCHIVE", archive_ok))
        caught += 1 if archive_ok else 0
        misreports += 0 if archive_ok else 1

        # ⑬c `Machine-Review: <B>`：声明 A 却改 B 的分区，带对方复审 trailer 即放行
        repo = new_repo("review")
        # 两个 trailer 必须**同处末尾 trailer 块**（中间空一行就会被 git 当成正文，
        # 于是 Machine-Review 根本不会被解析 —— 这个副作用值得写进注释，人也容易踩）。
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "r\n",
                "docs(KQABATS): 代改 SIWPAN 分区\n\n"
                f"{TRAILER_KEY}: DESKTOP-KQABATS\n{REVIEW_KEY}: SIWPAN")
        report = judge(read_commits(repo), discover_machines(repo), "1970-01-01")
        cases.append(("`Machine-Review: <B>` 放行跨机改动（铁律 6 在提交层的可判形态）",
                      "block" if report["blocking"] == 0 else "REVIEW", report["blocking"] == 0))
        caught += 1 if report["blocking"] == 0 else 0
        misreports += 0 if report["blocking"] == 0 else 1

        # ⑬d 预告窗：生效日之前只 WARN、逐条列出，退出码不变（ADR §D2.5）
        repo = new_repo("preview")
        _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "p\n",
                "docs: 预告窗内一笔", when="2026-11-28T10:00:00")
        report = judge(read_commits(repo), discover_machines(repo), EFFECTIVE_FROM,
                       preview_from=PREVIEW_FROM)
        preview_ok = (report["blocking"] == 0 and len(report["preview"]) == 1)
        cases.append(("预告窗（生效日之前）只 WARN 不判红，且逐条列出",
                      "block" if preview_ok else "PREVIEW", preview_ok))
        caught += 1 if preview_ok else 0
        misreports += 0 if preview_ok else 1

        # ⑬e 通道 (b)：例外台账登记的提交豁免，但必须留痕
        repo = new_repo("ledger")
        sha = _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "l\n",
                      "docs: 本地 squash 后被压成单一提交")
        report = judge(read_commits(repo), discover_machines(repo), "1970-01-01",
                       exemptions={sha[:12]: {"id": "EX-099", "expires": "2027-01-31",
                                              "approver": "selfcheck"}})
        ledger_ok = (report["blocking"] == 0 and len(report["exempted_by_ledger"]) == 1)
        cases.append(("例外台账（通道 b）豁免生效且留痕（git 给不出确定形态那一半）",
                      "block" if ledger_ok else "LEDGER", ledger_ok))
        caught += 1 if ledger_ok else 0
        misreports += 0 if ledger_ok else 1

        # ⑬f 台账条目**在提交之前就到期** ⇒ 不豁免，按 MISSING 判红（带台账编号）
        repo = new_repo("expired-ledger")
        sha2 = _commit(repo, f"{MACHINE_DIR}/SIWPAN/月账/2026-11.md", "e\n",
                       "docs: 台账过期后的一笔", when="2026-11-28T10:00:00")
        report = judge(read_commits(repo), discover_machines(repo), "1970-01-01",
                       exemptions={sha2[:12]: {"id": "EX-098", "expires": "2026-11-01",
                                              "approver": "selfcheck"}})
        expired_ok = (report["blocking"] >= 1 and len(report["expired_ledger_hits"]) == 1
                      and not report["exempted_by_ledger"])
        cases.append(("台账已在提交前到期 ⇒ 不豁免、按忘了写判红（不追溯罚老提交）",
                      "block" if expired_ok else "EXPIRED", expired_ok))
        caught += 1 if expired_ok else 0
        misreports += 0 if expired_ok else 1

    for name, expect, got in cases:
        flag = "PASS" if (got if expect != "clean" else not got) else "FAIL"
        print(f"  [{flag}] {name}（期望 {expect} / 实际 {'命中' if got else '未命中'}）")
    print(json.dumps({"caught": caught, "clean": clean, "misreports": misreports},
                     ensure_ascii=False).replace(
        '{"caught"', 'SELFCHECK {"caught"', 1))

    ok = caught > 0 and clean > 0 and misreports == 0
    if mutated_run:
        # 变异态：判红逻辑被摘掉 ⇒ caught 必须归零、自检必须**判红**。
        # 若此刻仍 ok（caught>0），说明自检绿的原因与判红无关 —— 那才是真正要报的错。
        print(f"MUTATION: caught={caught}（摘掉判红逻辑后必须为 0 ⇒ 本进程必须 exit 1）")
        # 变异态下的返回码语义：**自检失败才是正确结局**。
        #   ok=False（caught 归零）⇒ exit 1：变异被抓到，说明自检真的在验判红；
        #   ok=True（摘了判红逻辑还全绿）⇒ exit 0：这不是"通过"，而是自检失明，
        #   由父进程把 exit 0 判成「变异探针没红」并让整体自检报错。
        return EXIT_OK if ok else EXIT_FINDING

    if ok:
        print("SELFCHECK: PASS —— 判红/判静两半都验过，且拼错机名与中文路径都不漏")
    else:
        print("SELFCHECK: FAIL —— 有半边没验过（caught=0 或 clean=0 或误报）")
        return EXIT_FINDING

    # 变异探针：把 "改分区" 判据摘掉再跑一遍自检，必须变红。
    env = dict(os.environ, ALLIN_MACHINE_TRAILER_MUTATE="no-block")
    probe = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--selfcheck"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
    if probe.returncode == 0:
        print("SELFCHECK: FAIL —— 变异探针没红：把判红逻辑整段摘掉后自检仍通过，"
              "说明它验的不是判红（一个不会失败的自检什么都没告诉你）")
        return EXIT_FINDING
    print("MUTATION: PASS —— 摘掉判红逻辑后自检如期变红（probe exit="
          f"{probe.returncode}）")
    return EXIT_OK


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="机器归属 trailer 判据（Machine:）")
    parser.add_argument("--repo", default=str(ROOT), help="仓根（默认本仓）")
    parser.add_argument("--since", default=None, help="取证窗口起（git --since）")
    parser.add_argument("--until", default=None, help="取证窗口止（git --until）")
    parser.add_argument("--effective-from", default=EFFECTIVE_FROM,
                        help=f"判据生效日（默认 {EFFECTIVE_FROM}；自检用 1970-01-01）")
    parser.add_argument("--strict-rewritten", action="store_true",
                        help="把 merge / 平台 squash 也判红（确认窗口内不该有平台重写提交时用）")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--selfcheck", action="store_true", help="12 例负对照 + 变异探针")
    parser.add_argument("--inject", action="store_true",
                        help="commit-msg 模式：给提交信息追加 Machine: trailer（幂等）")
    parser.add_argument("--quiet", action="store_true", help="--inject 时不打印")
    parser.add_argument("--stem", default=None, help="覆盖本机标识（默认 hostname 大写）")
    parser.add_argument("--exceptions", default=None,
                        help="例外台账路径（默认 exceptions.yml / 包内那份）")
    parser.add_argument("message_file", nargs="?", default=None,
                        help="--inject 时的提交信息文件（钩子传入 $1）")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()
    if args.inject:
        if not args.message_file:
            print("用法错：--inject 需要提交信息文件（钩子传 $1）", file=sys.stderr)
            return EXIT_USAGE
        return inject(args.repo, args.message_file, quiet=args.quiet, stem=args.stem)
    return run_gate(Path(args.repo), args.since, args.until, args.effective_from,
                    args.strict_rewritten, args.as_json, args.exceptions)


if __name__ == "__main__":
    raise SystemExit(main())
