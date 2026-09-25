#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repo_hygiene.py —— 仓库卫生门禁（把 gitee 推送流程 §1「仓库卫生六项」变成退出码）

为什么存在
----------
`docs/gitee推送流程_2026-09-25.md` §1 要求：任何仓在推送前须过「仓库卫生六项」，
且**门禁必须在匿名 clone 副本上也能跑通**（本地有 .gitignore 上下文，本地跑通不算数）。
该要求此前只以文字存在，**没有任何可执行件**（2026-09-25 实测：6 项要求 → 0 项有门禁）。
本脚本把它变成退出码。

检查项（六项 + 本工作区沉淀出的两项）
------------------------------------
  H1 LICENSE 唯一      —— 判**路径**：仓根须有 LICENSE；`_ref/ThirdParty/LICENSE` 之类
                          的 basename 同样是 LICENSE，只判文件名会漏（文档 §1 明确此坑）
  H2 无第三方源码目录  —— `_ref/ vendor/ node_modules/ third_party/`（跟踪面内）
  H3 无产物目录        —— `output/ state/ cache/ dist/ build/ release/`（跟踪面内）
  H4 无归档、无大文件  —— `*.zip *.tar.gz *.7z`；单文件 > 5 MiB
  H5 无凭据            —— ①令牌**本体子串**匹配（从凭据文件读，不回显）
                          ②通用形态匹配（键名在前，避免 sha256 误报）
                          ③URL 内嵌凭据 `https://user:hex@`
  H6 文档一致性        —— 借鉴记账须含「上游 URL + 许可证 + 不入仓声明」
  H7 仓名与目录名一致  —— 本地目录名须等于 origin 仓名（本工作区 2026-09-25 沉淀：
                          目录 platform 与远端仓 allin-platform 曾长期不一致，
                          改名后暴露出 safe.directory/符号链接/BOM 三处连带问题）
  H8 行尾一致性        —— 跟踪面内「实际行尾」与「core.autocrlf 期望行尾」是否自洽。
                          本工作区 2026-09-25 实证：机器级 `core.autocrlf=true` 与
                          LF-only 仓组合，会让 100+ 文件呈现**内容相同的假 modified**，
                          足以把「2 个真改动」淹没在「251 个假改动」里。

判定范围
--------
默认只判 **git 跟踪面**（`git ls-files`）——因为进仓的才是公开面。
`--worktree` 追加工作树扫描（抓未跟踪的产物/大文件）。

用法
----
    python repo_hygiene.py --repo G:\\repos\\cordis-table-app
    python repo_hygiene.py --all                       # G:\\repos 下全部仓
    python repo_hygiene.py --all --worktree            # 含未跟踪面
    python repo_hygiene.py --repo X --baseline B.csv   # 基线棘轮（存量不阻断）
    python repo_hygiene.py --selfcheck                 # 注入破坏用例，证明门禁是活的
    python repo_hygiene.py --all --json out.json       # 机读输出

退出码
------
    0 = 干净（或全部命中都在基线内）
    1 = 有新阻断项
    2 = 用法错误
    3 = 环境错误（git 不可用等）

基线纪律
--------
基线只在「存量确实清完」时刷新；刷新前先 `--list-all` 看过全部存量，
否则棘轮会把新增悄悄吞掉（同 scan_hardcoded.ps1 的纪律）。
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

MIB = 1024 * 1024
BIG_FILE_LIMIT = 5 * MIB

# H2 第三方源码目录（跟踪面内出现即阻断）
THIRD_PARTY_DIRS = {"_ref", "vendor", "node_modules", "third_party"}
# H3 产物目录（跟踪面内出现即阻断）
# 含 *.egg-info / *.dist-info 这类**构建元数据**：它们是 setuptools 生成物，
# 2026-09-26 实测因 `git add -A` 误入过 d20 仓（当时本表未覆盖，门禁没拦住）。
ARTIFACT_DIRS = {"output", "state", "cache", "dist", "build", "release"}
ARTIFACT_DIR_SUFFIXES = (".egg-info", ".dist-info", ".egg-link")
# H4 归档后缀
ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".7z", ".rar", ".tar.bz2")

# 允许出现在仓根之外的 LICENSE（第三方许可随包是合规的，H1 判"仓根唯一"）
LICENSE_ROOT_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")

# H5 通用凭据形态。判据要点（首版误报实证后收紧）：
#   · **键名须带引号或前后有词边界** —— 否则 `data-api-key="x"` 这类属性名也会被当成键
#   · **值必须自身像密钥** —— 首版只要求「键名 + 16 位以上字符」，结果把
#     `password = 'Please enter your password'`（D&D 规则书 HTML 里的说明文字）
#     判成凭据，36 条命中里绝大多数是这种误报。误报多了门禁就没人看了。
#   · 值长度门槛提到 20，并**排除含空格/常见英文词/重复字符**的形态
CRED_PATTERNS = [
    # 前置负向断言：键名不得紧跟在 `&`/`?`/`/` 后面 —— 那说明它是 **URL 查询参数**
    # （实证：RolePlayer 规则书 HTML 里的 `...&token=<uuid>` 是 gitee 公开链接参数，
    #  值确实像 UUID 密钥，纯靠"值像不像密钥"判不出来，必须看上下文）
    re.compile(rb"""(?<![&?/])(?P<k>["']?(?:access[_-]?token|api[_-]?key|auth[_-]?token|client[_-]?secret|secret[_-]?key|password|passwd|secret|token)["']?)\s*[=:]\s*["']?(?P<v>[0-9a-zA-Z_\-+/=.]{20,})["']?""", re.I),
    re.compile(rb"https://[^/\s]+:[0-9a-fA-F]{20,}@"),
    re.compile(rb"sk-[0-9a-zA-Z]{20,}"),
    # 注意两个坑（首版各踩一次）：
    #  ① Python 3.12+ 禁止 bytes 字面量含非 ASCII 字符（rb"...私人令牌" → SyntaxError）
    #  ② bytes 模式下 re 不认 \uXXXX（只认 \xNN）——「私人令牌」的 UTF-8 字节写死如下
    re.compile(b"private[\\s_-]?token|\\xe7\\xa7\\x81\\xe4\\xba\\xba\\xe4\\xbb\\xa4\\xe7\\x89\\x8c", re.I),
]
# 值里出现这些词 = 是说明文字，不是密钥
VALUE_STOPWORDS = re.compile(
    r"password|passwd|username|user_?name|your_?|example|placeholder|changeme|string|number|"
    r"function|return|object|boolean|undefined|null|true|false|description|required|optional",
    re.I)
# 允许的占位写法（脱敏约定：一律 <TOKEN> / **** / <HEX>）
CRED_PLACEHOLDER = re.compile(rb"<[A-Z_]{3,}>|\*{4,}|<HEX>|<REDACTED>|\.\.\.|^\$|\{\{|%[A-Z_]+%|xxxx", re.I)


def _value_looks_secret(v):
    """判断匹配到的『值』是否真像密钥（而非英文说明文字/标识符）。"""
    if len(v) < 20:
        return False
    if VALUE_STOPWORDS.search(v):
        return False
    # 单一字符重复（aaaa…/0000…）不是密钥
    if len(set(v)) <= 3:
        return False
    # 至少要有一定字符多样性：数字+字母混合，或长 hex
    has_digit = any(c.isdigit() for c in v)
    has_alpha = any(c.isalpha() for c in v)
    return (has_digit and has_alpha) or (len(v) >= 32 and has_alpha)

# H6 借鉴记账三要素
ATTR_URL = re.compile(r"https?://\S+")
ATTR_LICENSE = re.compile(r"(MIT|Apache[- ]?2|GPL|AGPL|BSD|CC[ -]?BY|MPL|Unlicense|许可|License)", re.I)
ATTR_NOCOMMIT = re.compile(r"(不入仓|不入库|不随仓库分发|不随仓发布|不纳入版本|gitignore)")


class Finding:
    __slots__ = ("check", "repo", "path", "detail")

    def __init__(self, check, repo, path, detail):
        self.check = check
        self.repo = repo
        self.path = path
        self.detail = detail

    def key(self):
        return "{}\t{}\t{}".format(self.check, self.repo, self.path)

    def __str__(self):
        return "[{}] {} :: {} —— {}".format(self.check, self.repo, self.path, self.detail)


def run_git(repo, *args, binary=False):
    """执行 git 命令；返回 (rc, stdout)。失败不抛异常，由调用方判定。"""
    cmd = ["git", "-C", repo] + list(args)
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=180)
    except Exception as e:
        return 128, (b"" if binary else str(e))
    return p.returncode, (p.stdout if binary else p.stdout.decode("utf-8", "replace"))


def is_git_repo(path):
    return os.path.isdir(os.path.join(path, ".git"))


def tracked_files(repo):
    """git 跟踪面（含中文名安全：不用 core.quotepath 转义）。"""
    rc, out = run_git(repo, "-c", "core.quotepath=false", "ls-files", "-z")
    if rc != 0:
        return None
    return [f for f in out.split("\0") if f]


def blob_sizes(repo):
    """一次取回跟踪面全部文件的入库体量。

    性能纪律：首版对**每个文件**调一次 `git cat-file -s`，几万个文件 = 几万次进程创建，
    单仓扫描直接跑到分钟级（实测 109 仓 10 分钟未完成）。改用 `git ls-tree -r -l`
    一次拿全，单仓一次子进程。

    用 blob 口径（不是 os.path.getsize），避开 .gitattributes 的 CRLF/LF 坑。
    """
    rc, out = run_git(repo, "-c", "core.quotepath=false", "ls-tree", "-r", "-l", "HEAD")
    if rc != 0:
        return {}
    sizes = {}
    for line in out.splitlines():
        # 形如: 100644 blob <sha> <size>\t<path>
        try:
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) >= 4 and parts[1] == "blob":
                sizes[path] = int(parts[3])
        except (ValueError, IndexError):
            continue
    return sizes


def blob_size(repo, path, cache=None):
    """单文件体量（保留给零散调用；批量场景请用 blob_sizes）。"""
    if cache is not None and path in cache:
        return cache[path]
    rc, out = run_git(repo, "cat-file", "-s", "HEAD:" + path)
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def origin_repo_name(repo):
    rc, out = run_git(repo, "config", "--get", "remote.origin.url")
    if rc != 0 or not out.strip():
        return None
    url = out.strip()
    m = re.search(r"[:/]([^/:]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


# ---------------------------------------------------------------- 各检查项

def check_h1_license(repo, tracked, ctx):
    f = []
    root = [t for t in tracked if "/" not in t and os.path.basename(t) in LICENSE_ROOT_NAMES]
    if not root:
        f.append(Finding("H1", repo, "(仓根)", "仓根无 LICENSE —— 铁律 4 建仓三件套之一"))
    # 判路径：报告仓根之外的 LICENSE（不一定违规，但必须可见，便于人工判断
    # 是否属于「随包第三方许可」这种合规例外）
    others = [t for t in tracked
              if "/" in t and os.path.basename(t) in LICENSE_ROOT_NAMES
              and not t.startswith("docs/")]
    if others and ctx.get("verbose"):
        for o in others[:10]:
            f.append(Finding("H1i", repo, o, "仓根之外的 LICENSE（确认是随包第三方许可）"))
    return f


def check_h2_thirdparty(repo, tracked, ctx):
    f = []
    for t in tracked:
        parts = t.split("/")
        for p in parts[:-1]:
            if p in THIRD_PARTY_DIRS:
                f.append(Finding("H2", repo, t, "跟踪面含第三方源码目录 '{}'（应 gitignore，不入仓）".format(p)))
                break
    return f


def check_h3_artifacts(repo, tracked, ctx):
    f = []
    for t in tracked:
        parts = t.split("/")
        hit = None
        for p in parts[:-1]:
            if p in ARTIFACT_DIRS:
                hit = "产物目录 '{}'".format(p)
                break
            if p.endswith(ARTIFACT_DIR_SUFFIXES):
                hit = "构建元数据目录 '{}'（setuptools 生成物，勿入库）".format(p)
                break
        if hit:
            f.append(Finding("H3", repo, t, "跟踪面含" + hit + "（应 gitignore）"))
    return f


def check_h4_archives(repo, tracked, ctx):
    f = []
    sizes = ctx.get("_blob_sizes") or {}
    for t in tracked:
        low = t.lower()
        if low.endswith(ARCHIVE_SUFFIXES):
            f.append(Finding("H4", repo, t, "跟踪面含归档文件（应走 release 附件或 LFS）"))
            continue
        sz = sizes.get(t)
        if sz is not None and sz > BIG_FILE_LIMIT:
            f.append(Finding("H4", repo, t, "入库体量 {:.2f} MiB > 5 MiB".format(sz / MIB)))
    # --worktree：抓未跟踪的大文件/归档
    if ctx.get("worktree"):
        for dirpath, dirnames, filenames in os.walk(repo):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__", ".venv")]
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, repo).replace("\\", "/")
                try:
                    if not os.path.isfile(p):
                        continue
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if fn.lower().endswith(ARCHIVE_SUFFIXES):
                    f.append(Finding("H4w", repo, rel, "工作树含归档文件（未跟踪；勿提交）"))
                elif sz > BIG_FILE_LIMIT:
                    f.append(Finding("H4w", repo, rel, "工作树文件 {:.2f} MiB > 5 MiB".format(sz / MIB)))
    return f


# 凭据只可能出现在文本里；这些后缀直接跳过（性能：H5 曾是主要瓶颈，见下）
BINARY_EXT = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin", ".o", ".a", ".lib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svgz",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".avi", ".mkv", ".webm",
    ".zip", ".gz", ".tgz", ".7z", ".rar", ".xz", ".bz2", ".jar", ".whl",
    ".ttf", ".otf", ".woff", ".woff2", ".eot", ".pdf", ".psd",
    ".db", ".sqlite", ".sqlite3", ".mdb", ".pak", ".unity3d", ".asset",
}
CRED_READ_LIMIT = 2 * MIB


def check_h5_credentials(repo, tracked, ctx):
    """凭据扫描。

    性能纪律（实测）：首版对每个跟踪文件无条件 `open().read()` 全量读入，在
    15 仓 / 19,182 文件的采样里独占 11.1s（总 13.8s）——109 仓推算约 5 分钟，
    叠加 H8 后整轮超 600s。优化：跳过二进制后缀、只读前 CRED_READ_LIMIT 字节。
    凭据不会藏在 PNG/EXE 里，跳过是**判据上正确**的省略，不是偷工。
    """
    f = []
    body = ctx.get("token_body")
    for t in tracked:
        ext = os.path.splitext(t)[1].lower()
        if ext in BINARY_EXT:
            continue
        p = os.path.join(repo, t.replace("/", os.sep))
        try:
            with open(p, "rb") as fh:
                data = fh.read(CRED_READ_LIMIT)
        except OSError:
            continue
        if body and body in data:
            f.append(Finding("H5", repo, t, "含令牌本体（从凭据文件子串匹配命中）—— 必须吊销重发"))
            continue
        for pat in CRED_PATTERNS:
            m = pat.search(data)
            if not m:
                continue
            text = m.group(0)
            if CRED_PLACEHOLDER.search(text):
                continue
            # 形态①（键值对）需额外判定「值是否真像密钥」，避免把英文说明当凭据
            if "k" in pat.groupindex:
                try:
                    val = m.group("v").decode("ascii", "replace")
                except Exception:
                    val = ""
                if not _value_looks_secret(val):
                    continue
            f.append(Finding("H5", repo, t, "疑似凭据形态：{}".format(pat.pattern[:40])))
            break
    # ③ .git/config 的 URL 内嵌凭据（不进跟踪面，但属仓库卫生）
    cfg = os.path.join(repo, ".git", "config")
    if os.path.isfile(cfg):
        try:
            d = open(cfg, "rb").read()
            if CRED_PATTERNS[1].search(d):
                f.append(Finding("H5", repo, ".git/config", "remote URL 内嵌明文凭据"))
        except OSError:
            pass
    return f


def check_h6_attribution(repo, tracked, ctx):
    """借鉴记账：`docs/` 下声明「借鉴/参考/上游」的文档须含上游URL+许可证+不入仓声明。

    判据收窄（首版误报实证）：
      · **只判 `docs/` 下的文档** —— README 里的「## 源码来源」（说明依赖来自哪个包管理器）
        不是借鉴记账，不该被本项约束。记账的载体是 docs/REFERENCE.md 一类专档。
      · 英文关键词加**词边界** —— 首版用 `参考`，匹到了英文单词 "Reference"（reference 含 reference），
        属于把通用词当关键词。改用 `\\breference\\b` 并去掉裸「参考」。
    """
    f = []
    trigger = re.compile(r"借鉴|源码来源|上游|third[- ]party|\breference\b|\bupstream\b", re.I)
    for t in tracked:
        low = t.lower()
        if not low.endswith((".md", ".txt")):
            continue
        # 只判 docs/ 下的专档（README 是门面，不是记账载体）
        if not low.startswith("docs/"):
            continue
        p = os.path.join(repo, t.replace("/", os.sep))
        try:
            if os.path.getsize(p) > 2 * MIB:
                continue
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if not trigger.search(txt):
            continue
        has_url = bool(ATTR_URL.search(txt))
        has_lic = bool(ATTR_LICENSE.search(txt))
        has_nc = bool(ATTR_NOCOMMIT.search(txt))
        if not (has_url and has_lic and has_nc):
            missing = []
            if not has_url:
                missing.append("上游URL")
            if not has_lic:
                missing.append("许可证")
            if not has_nc:
                missing.append("不入仓声明")
            f.append(Finding("H6", repo, t, "借鉴记账缺：" + "、".join(missing)))
    return f


def check_h7_naming(repo, tracked, ctx):
    name = origin_repo_name(repo)
    if not name:
        return []
    dirname = os.path.basename(os.path.abspath(repo))
    if dirname != name:
        return [Finding("H7", repo, "(仓名)", "目录名 '{}' != origin 仓名 '{}'".format(dirname, name))]
    return []


def check_h8_eol(repo, tracked, ctx):
    """跟踪面内「实际行尾」与「core.autocrlf 期望行尾」是否自洽。

    判据：对每个文本文件，若核心配置 core.autocrlf=true，则 git 期望工作树为 CRLF、
    库内为 LF。此时若工作树文件是 LF 而库内也是 LF，内容其实一致，**不应**表现为
    modified —— 但实测（2026-09-25）git 仍会把它列进 status，制造假改动。
    本检查统计「内容与库内逐字节相同、却被 git 标为 modified」的文件数。

    性能纪律：首版对每个 modified 文件 spawn 一次 `git cat-file`。仓一多就慢，
    故先用 `git diff --numstat` 排除真实改动（增删行数非 0 的必然有内容差异），
    只对「形似假 modified」的少量文件做逐字节复核。
    """
    rc, _ = run_git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if rc != 0:
        return []
    rc, out = run_git(repo, "-c", "core.quotepath=false", "status", "--porcelain", "-uno")
    if rc != 0:
        return []
    modified = []
    for line in out.splitlines():
        if len(line) > 3 and line[:2].strip() in ("M", "MM", " M"):
            p = line[3:].strip().strip('"')
            modified.append(p)
    if not modified:
        return []
    # 用 numstat 先筛：有增删行的就是真改动，不必逐字节比
    rc, num = run_git(repo, "-c", "core.quotepath=false", "-c", "core.autocrlf=false",
                      "diff", "--numstat", "--", ".")
    suspect = []
    changed = set()
    if rc == 0:
        for line in num.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                add, dele, path = parts[0], parts[1], parts[2]
                if add != "0" or dele != "0":
                    changed.add(path)
    for p in modified:
        if p not in changed:
            suspect.append(p)
    if not suspect:
        return []
    fake = []
    for p in suspect:
        real = os.path.join(repo, p.replace("/", os.sep))
        if not os.path.isfile(real):
            continue
        try:
            blob = subprocess.run(["git", "-C", repo, "cat-file", "blob", "HEAD:" + p],
                                  capture_output=True, timeout=60).stdout
            wt = open(real, "rb").read()
        except Exception:
            continue
        if blob == wt:
            fake.append(p)
    if fake:
        return [Finding("H8", repo, "(行尾)", "{} 个文件内容与库内逐字节相同却被标 modified（core.autocrlf 与仓行尾约定冲突）：例 {}".format(
            len(fake), ", ".join(fake[:3])))]
    return []


CHECKS = [
    ("H1", check_h1_license, "LICENSE 唯一（判路径）"),
    ("H2", check_h2_thirdparty, "无第三方源码目录"),
    ("H3", check_h3_artifacts, "无产物目录"),
    ("H4", check_h4_archives, "无归档 / 无 >5MiB 大文件"),
    ("H5", check_h5_credentials, "无凭据"),
    ("H6", check_h6_attribution, "文档一致性（借鉴记账）"),
    ("H7", check_h7_naming, "仓名与目录名一致"),
    ("H8", check_h8_eol, "行尾一致性（假 modified 检测）"),
]


def scan_repo(repo, ctx):
    if not is_git_repo(repo):
        return [Finding("ENV", repo, "-", "不是 git 仓（无 .git）")]
    tracked = tracked_files(repo)
    if tracked is None:
        return [Finding("ENV", repo, "-", "git ls-files 失败（仓可能损坏）")]
    # 体量一次取全，供 H4 用（避免逐文件 spawn：见 blob_sizes 的性能纪律）
    ctx = dict(ctx)
    ctx["_blob_sizes"] = blob_sizes(repo)
    out = []
    for _cid, fn, _desc in CHECKS:
        try:
            out.extend(fn(repo, tracked, ctx))
        except Exception as e:
            out.append(Finding("ENV", repo, "-", "检查 {} 异常: {}".format(_cid, e)))
    return out


def load_baseline(path):
    keys = set()
    if path and os.path.isfile(path):
        try:
            with io.open(path, encoding="utf-8-sig", newline="") as fh:
                for row in csv.reader(fh):
                    if len(row) >= 3 and row[0] != "check":
                        keys.add("{}\t{}\t{}".format(row[0], row[1], row[2]))
        except Exception:
            pass
    return keys


def save_baseline(path, findings):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["check", "repo", "path", "detail"])
        for f in sorted(findings, key=lambda x: x.key()):
            w.writerow([f.check, f.repo, f.path, f.detail])


# ---------------------------------------------------------------- selfcheck

def _make_fixture(root, name, build):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    subprocess.run(["git", "init", "-q", d], capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.email", "t@t"], capture_output=True)
    subprocess.run(["git", "-C", d, "config", "user.name", "t"], capture_output=True)
    build(d)
    subprocess.run(["git", "-C", d, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", "x"], capture_output=True)
    return d


def selfcheck():
    """注入破坏用例：每条检查都必须报红；干净仓必须零命中。证明门禁不是死的。"""
    print("== 仓库卫生门禁 自测 ==")
    tmp = tempfile.mkdtemp(prefix="hyg_selfcheck_")
    ok = True
    try:
        def wr(d, rel, content, mode="w"):
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(rel) else None
            with open(p, mode, encoding=None if "b" in mode else "utf-8") as fh:
                fh.write(content)

        # 干净仓：LICENSE + 无产物 + 无凭据
        clean = _make_fixture(tmp, "clean", lambda d: (
            wr(d, "LICENSE", "MIT\n"),
            wr(d, "README.md", "# hi\n"),
            wr(d, "src/a.py", "print(1)\n"),
        ))
        res = scan_repo(clean, {})
        bad = [x for x in res if x.check != "H7"]  # 目录名 clean != origin 名，H7 预期命中
        print("  干净仓零误报: {}  {}".format("✔" if not bad else "✘", "" if not bad else str(bad[0])))
        ok &= not bad

        # H1：无 LICENSE
        r = _make_fixture(tmp, "no_license", lambda d: wr(d, "a.txt", "x\n"))
        hit = [x for x in scan_repo(r, {}) if x.check == "H1"]
        print("  H1 缺 LICENSE 被检出: {}  [{}]".format("✔" if hit else "✘", len(hit)))
        ok &= bool(hit)

        # H1 路径口径：仓根之外的 LICENSE 必须可见（不能只判 basename 就算过）
        def _lic_deep(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "_ref/ThirdParty/LICENSE", "GPL\n")
        r = _make_fixture(tmp, "lic_deep", _lic_deep)
        hit = [x for x in scan_repo(r, {"verbose": True}) if x.check == "H1i"]
        print("  H1 判路径（深层 LICENSE 可见）: {}  [{}]".format("✔" if hit else "✘", len(hit)))
        ok &= bool(hit)

        # H2/H3：第三方源码目录 + 产物目录
        def _tp(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "vendor/lib.c", "x\n")
            wr(d, "output/r.xlsx", "x\n")
        r = _make_fixture(tmp, "tp", _tp)
        res = scan_repo(r, {})
        h2 = [x for x in res if x.check == "H2"]
        h3 = [x for x in res if x.check == "H3"]
        print("  H2 第三方目录被检出: {}  [{}]".format("✔" if h2 else "✘", len(h2)))
        print("  H3 产物目录被检出:   {}  [{}]".format("✔" if h3 else "✘", len(h3)))
        ok &= bool(h2) and bool(h3)

        # H4：归档 + 大文件
        def _arch(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "pkg.zip", b"PK\x03\x04", mode="wb")
            wr(d, "big.bin", b"0" * (6 * MIB), mode="wb")
        r = _make_fixture(tmp, "arch", _arch)
        h4 = [x for x in scan_repo(r, {}) if x.check == "H4"]
        print("  H4 归档+大文件被检出: {}  [{}]".format("✔" if len(h4) >= 2 else "✘", len(h4)))
        ok &= len(h4) >= 2

        # H5：令牌本体子串 + 通用形态
        # 注意：测试值必须**自身像密钥**（含数字+字母、字符多样），否则会被
        # _value_looks_secret 正确拒绝——首版用 "0"*32 属单一字符重复，正是被拒的形态。
        secret = "a1b2c3d4e5f67890abcdef1234567890"
        def _cred(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "cfg.py", 'api_key = "{}"\n'.format(secret))
        r = _make_fixture(tmp, "cred", _cred)
        h5 = [x for x in scan_repo(r, {"token_body": secret.encode()}) if x.check == "H5"]
        print("  H5 令牌本体被检出:   {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # H5 反例一：占位写法不得误报
        def _cred_ok(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "cfg.py", 'api_key = "<TOKEN>"\nsecret = "****"\n')
        r = _make_fixture(tmp, "cred_ok", _cred_ok)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 占位写法零误报:   {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        # H5 反例二：**键名+长值但值是英文说明**（首版真实误报形态，RolePlayer 规则书 HTML）
        def _cred_prose(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "rules.html", 'var password = "Please enter your password here";\n'
                                'var secret = "This description explains the secret";\n')
        r = _make_fixture(tmp, "cred_prose", _cred_prose)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 说明文字零误报:   {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        # H6：借鉴记账缺要素
        def _attr(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/REFERENCE.md", "本项目借鉴了某上游实现。\n")
        r = _make_fixture(tmp, "attr", _attr)
        h6 = [x for x in scan_repo(r, {}) if x.check == "H6"]
        print("  H6 借鉴记账缺项被检出: {}  [{}]".format("✔" if h6 else "✘", len(h6)))
        ok &= bool(h6)

        # H7：目录名 != origin 仓名（用本地 bare 仓做 origin）
        bare = os.path.join(tmp, "renamed-origin.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], capture_output=True)
        d = os.path.join(tmp, "wrongdir")
        os.makedirs(d, exist_ok=True)
        subprocess.run(["git", "init", "-q", d], capture_output=True)
        subprocess.run(["git", "-C", d, "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", d, "config", "user.name", "t"], capture_output=True)
        subprocess.run(["git", "-C", d, "remote", "add", "origin", bare], capture_output=True)
        open(os.path.join(d, "LICENSE"), "w").write("MIT\n")
        subprocess.run(["git", "-C", d, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", d, "commit", "-qm", "x"], capture_output=True)
        h7 = [x for x in scan_repo(d, {}) if x.check == "H7"]
        print("  H7 目录名≠仓名被检出: {}  [{}]".format("✔" if h7 else "✘", len(h7)))
        ok &= bool(h7)

        # 法务：证明基线棘轮有效
        bl = os.path.join(tmp, "bl.csv")
        res = scan_repo(clean, {})
        save_baseline(bl, res)
        keys = load_baseline(bl)
        remaining = [x for x in res if x.key() not in keys]
        print("  基线棘轮生效（写入后新增=0）: {}  [{}]".format("✔" if not remaining else "✘", len(remaining)))
        ok &= not remaining

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("  自测{}".format("通过" if ok else "失败"))
    return 0 if ok else 1


# ---------------------------------------------------------------- main

def collect_repos(args):
    if args.repo:
        return [os.path.abspath(args.repo)]
    root = os.path.abspath(args.repos_root)
    if not os.path.isdir(root):
        print("[ERR] 仓根不存在: " + root, file=sys.stderr)
        return None
    out = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d) and is_git_repo(d):
            if args.filter and args.filter.lower() not in name.lower():
                continue
            out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser(description="仓库卫生门禁（六项 + 仓名/行尾）")
    ap.add_argument("--repo", help="单个仓路径")
    ap.add_argument("--all", action="store_true", help="扫描 --repos-root 下全部仓")
    ap.add_argument("--repos-root", default=r"G:\repos", help="仓根（默认 G:\\repos）")
    ap.add_argument("--filter", help="只扫名字含该子串的仓")
    ap.add_argument("--worktree", action="store_true", help="追加未跟踪面扫描")
    ap.add_argument("--baseline", default=r"G:\tools\gate\audit\hygiene_baseline.csv")
    ap.add_argument("--write-baseline", action="store_true", help="把当前命中断言为基线")
    ap.add_argument("--no-baseline", action="store_true", help="忽略基线，看全部存量")
    ap.add_argument("--list-all", action="store_true", help="打印全部命中明细")
    ap.add_argument("--token-file", help="凭据文件（读令牌本体做子串匹配；不回显）")
    ap.add_argument("--json", help="把结果写入该 JSON 文件")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selfcheck", action="store_true", help="注入破坏用例自测")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    if not args.repo and not args.all:
        ap.print_help()
        return 2

    ctx = {"worktree": args.worktree, "verbose": args.verbose}
    if args.token_file and os.path.isfile(args.token_file):
        try:
            txt = open(args.token_file, encoding="utf-8", errors="replace").read()
            m = re.search(r"\b([0-9a-fA-F]{32}|[0-9a-fA-F]{64})\b", txt)
            if m:
                ctx["token_body"] = m.group(1).encode()
        except OSError:
            pass

    repos = collect_repos(args)
    if repos is None:
        return 3
    if not repos:
        print("[WARN] 没有找到任何 git 仓", file=sys.stderr)
        return 0

    if not args.quiet:
        print("== 仓库卫生门禁 ==")
        print("  范围: {} 个仓 | 跟踪面{}".format(len(repos), " + 工作树" if args.worktree else ""))

    findings = []
    for r in repos:
        findings.extend(scan_repo(r, ctx))

    baseline = set() if args.no_baseline else load_baseline(args.baseline)
    if args.write_baseline:
        save_baseline(args.baseline, findings)
        if not args.quiet:
            print("  已写入基线: {} （{} 条）".format(args.baseline, len(findings)))
        return 0

    blocked = [f for f in findings if f.key() not in baseline]
    by_check = {}
    for f in findings:
        by_check[f.check] = by_check.get(f.check, 0) + 1

    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "repos": len(repos), "total": len(findings),
                "blocked": len(blocked), "by_check": by_check,
                "findings": [{"check": f.check, "repo": f.repo, "path": f.path, "detail": f.detail} for f in findings],
            }, fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        if by_check:
            print("  命中分布: " + "  ".join("{}={}".format(k, by_check[k]) for k in sorted(by_check)))
        else:
            print("  命中分布: 无")

    show = findings if args.list_all else blocked
    for f in show:
        print("  " + str(f))
    if not args.list_all and blocked and not args.quiet:
        print("  （以上为基线外新增；看全部存量用 --no-baseline --list-all）")

    if blocked:
        if not args.quiet:
            print("  RESULT: 阻断 —— 基线外新增 {} 条".format(len(blocked)))
        return 1
    if not args.quiet:
        print("  RESULT: 通过（存量 {} 条在基线内）".format(len(findings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
