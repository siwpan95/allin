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
  H3 无产物目录        —— `output/ state/ cache/ dist/ build/`（任意层级）
                          ＋ `release/`（**仅仓根**：release 是极常见的源码目录名，
                          见 ARTIFACT_DIRS_ROOT_ONLY 的 2026-09-28 实证说明）
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
# 分层（2026-09-28 误报治理，DSH 12 条实证）：
#   · 任意层级都算 `ARTIFACT_DIRS`：这几个名字在源码树里几乎不会作为**源码目录**出现。
#   · **只在仓根**才算 `ARTIFACT_DIRS_ROOT_ONLY`：`release` 是极常见的**源码目录名**
#     （发布工具 / 发布脚本 / 发版说明常叫 release）。实证：DSH 的 `scripts/release/*.ts`
#     是**发布工具的源码**，被原先"任意层级裸匹配"整目录误伤 12 条。
#     而**仓根**的 `release/` 通常确实是产物输出位置，故保留根级判定。
ARTIFACT_DIRS = {"output", "state", "cache", "dist", "build"}
ARTIFACT_DIRS_ROOT_ONLY = {"release"}
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
    # 第二个前置负向断言（2026-09-28 补，DSH 实证）：键名**左边不能是字母/数字/下划线** ——
    # 否则 `const LONG_TOKEN = '...'` 会因为**名字里含 token** 而被当成凭据键命中。
    # 实证：`LONG_TOKEN`（宽表格渲染测试里的长路径串）、`BROWSER_FIXTURE_TOKEN` 都是这么中招的。
    # 这属于**子串误匹配**，与"值像不像密钥"无关，必须在模式层修掉。
    re.compile(rb"""(?<![&?/])(?<![A-Za-z0-9_])(?P<k>["']?(?:access[_-]?token|api[_-]?key|auth[_-]?token|client[_-]?secret|secret[_-]?key|password|passwd|secret|token)["']?)\s*[=:]\s*["']?(?P<v>[0-9a-zA-Z_\-+/=.]{20,})["']?""", re.I),
    re.compile(rb"https://[^/\s]+:[0-9a-fA-F]{20,}@"),
    re.compile(rb"sk-[0-9a-zA-Z]{20,}"),
    # 注意两个坑（首版各踩一次）：
    #  ① Python 3.12+ 禁止 bytes 字面量含非 ASCII 字符（rb"...私人令牌" → SyntaxError）
    #  ② bytes 模式下 re 不认 \uXXXX（只认 \xNN）——「私人令牌」的 UTF-8 字节写死如下
    re.compile(b"private[\\s_-]?token|\\xe7\\xa7\\x81\\xe4\\xba\\xba\\xe4\\xbb\\xa4\\xe7\\x89\\x8c", re.I),
    # 形态④（2026-09-28 新增，补一个**盲区**）：**本机/内网 URL 的查询参数令牌**。
    #
    # 背景：形态①带 `(?<![&?/])`，把"跟在 ?/&// 后面的键名"一律排除 —— 因为那说明它是 URL 查询参数。
    # 该排除是 2026-09-27 为 RolePlayer 加的，实证很清楚：`&token=651a3142…`
    # 出现在 8 个规则书 HTML 里、**同一个令牌**、宿主全是 `www.beian.gov.cn`（公共政务站）
    # ⇒ 是**分享链接参数，不是秘密**。
    #
    # 但 `http://127.0.0.1:3080/?token=<32 位>` 是**本地会话令牌**，那是**真凭据**
    # （实证：DSH Web 把启动 URL 连同令牌写进 dsh-web-diagnose-*.log）。
    # 两者形态完全相同，靠"值像不像密钥"分不开 —— **能分开的是宿主**：
    #   · 公共站（beian.gov.cn / gitee.com / …）⇒ 分享链接，不判
    #   · 环回/内网（127.0.0.1 / localhost / [::1] / 10. / 192.168. / 172.16-31.）⇒ 本机服务凭据，判
    # 实测依据：RolePlayer 8 处查询参数令牌里，落在环回/内网的 = **0 处** ⇒ 该判别不会把它误伤。
    #
    # 实现上不在本模式里写宿主，而是交给 CONTEXT_REQUIRED（窗口内必须出现环回/内网 URL），
    # 这样"宿主判别"是一处独立、可单独测试的规则。
    re.compile(rb"""[?&](?P<k>access[_-]?token|api[_-]?key|auth[_-]?token|client[_-]?secret|secret[_-]?key|password|passwd|secret|token)=(?P<v>[0-9a-zA-Z_\-+/=.]{20,})""", re.I),
]
#: 上面「令牌**文件名**」那条的下标（2026-09-27 误报治理）。只在附近真的出现密钥形态的值时才算命中。
#: 实证：`docs/MEMORY.md`、`docs/gitee推送流程`、`docs/深度审核报告` 等 14 处文档被这条判红，
#: 而它们说的都是「令牌放在哪 / **未打印** / 曾被内嵌」这类**关于凭据的记录**——
#: 提及令牌文件名 ≠ 持有令牌；只有同一窗口里出现 32+ hex 才升级为发现。
TOKEN_NAME_PATTERN_INDEX = 3
assert CRED_PATTERNS[TOKEN_NAME_PATTERN_INDEX].pattern.startswith(b"private"), \
    "CRED_PATTERNS 重排了：请把 TOKEN_NAME_PATTERN_INDEX 指到「令牌文件名」那条，否则豁免会静默失效"
#: 「URL 查询参数令牌」那条的下标（形态④）。只有**窗口内出现环回/内网 URL**时才算命中。
URL_QUERY_TOKEN_INDEX = 4
assert CRED_PATTERNS[URL_QUERY_TOKEN_INDEX].pattern.startswith(b"[?&]"), \
    "CRED_PATTERNS 重排了：请把 URL_QUERY_TOKEN_INDEX 指到「URL 查询参数」那条，否则宿主判别会静默失效"

#: 环回 / 私网地址（RFC 1122/1918 + IPv6 环回）。用于形态④的宿主判别：
#: 令牌挂在**本机或内网**服务上 ⇒ 是本机会话凭据，判；挂在公共站上 ⇒ 多为分享链接，不判。
LOOPBACK_OR_PRIVATE = re.compile(
    rb"https?://(?:localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|0\.0\.0\.0|\[::1\]|"
    rb"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
    rb"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?::\d+)?",
    re.I)
CONTEXT_REQUIRED = {
    TOKEN_NAME_PATTERN_INDEX: re.compile(rb"[0-9a-fA-F]{32,}"),
    URL_QUERY_TOKEN_INDEX: LOOPBACK_OR_PRIVATE,
}
# 值里出现这些词 = 是说明文字，不是密钥
# 2026-09-28 追加（DSH 10 条实证）：**自证是夹具**的词。真实凭据不会自称
# "NOT_A_REAL_CREDENTIAL" / "DO-NOT-LOG" / "fixture"——出现这些词即夹具，属结构判定。
VALUE_STOPWORDS = re.compile(
    r"password|passwd|username|user_?name|your_?|example|placeholder|changeme|string|number|"
    r"function|return|object|boolean|undefined|null|true|false|description|required|optional|"
    r"fixture|dummy|sample|fake|synthetic|not[_-]?a[_-]?real|do[_-]?not[_-]?log|redact",
    re.I)
# 允许的占位写法（脱敏约定：一律 <TOKEN> / **** / <HEX>）
CRED_PLACEHOLDER = re.compile(rb"<[A-Z_]{3,}>|\*{4,}|<HEX>|<REDACTED>|\.\.\.|^\$|\{\{|%[A-Z_]+%|xxxx", re.I)

#: 「顺序串」合成标记（2026-10-06 补，用户拍板「改门禁自身正则」）。
#: 实证：`docs/记录/交接/2026-09.md:1440` 的 `sk-abcdefghijklmnop1234567890abcd` 被判红 ——
#: 它是**文档里的合成示例**，但不含 fixture/example 这类自称词，故 VALUE_STOPWORDS 认不出。
#: **阈值怎么定的（第一版过宽，被自检当场拦下）**：首版连 `1234567890` 一起拒，
#: 结果把门禁**自己的正例夹具**（`a1b2c3d4e5f67890abcdef1234567890`）也拒了 —— 一次挂掉 5 条自检用例
#: （真键名仍判 / 真 sk- 仍判 / 未跟踪面 / 环回 URL / localhost）。
#: 收紧为「**≥8 位连续升序字母**」：真 hex 令牌里最多出现 `abcdef`（6 位），8 位升序字母出现概率可忽略；
#: 而 `abcdefghijklmnop`（16 位）这种只有手敲示例才有。**自检既是保险，也是判据的标尺。**
VALUE_SYNTHETIC = re.compile(rb"abcdefgh|ABCDEFGH")

#: 「模式定义文本」守卫（2026-10-06 补，同一轮）。
#: 门禁**必然**包含它要找的模式（正则字面串），而它们的**字符集**与凭据不同：
#: 真实凭据是 [0-9a-zA-Z_-+/=.] 这一族，不含方括号/圆括号/花括号/问号/星号/竖线/脱字符/美元/反斜杠/尖括号。
#: 实证：`tools/repo_hygiene.py:139` 的 URL 查询参数正则字面串本身就是候选命中；本轮它恰好
#: 被「夹具缺标记」那条挡下，但**这一类此前没有判据兜底**（改一行源码就可能自命中）。
#: 调试铁律 53：发现一处漏检要反推**整类**影响面，不能只修当前这一例。
CRED_PATTERN_TEXT = re.compile(rb"[\[\](){}?*+|^$\\<>]")


def _value_looks_secret(v):
    """判断匹配到的『值』是否真像密钥（而非英文说明文字/标识符）。"""
    if len(v) < 20:
        return False
    if VALUE_STOPWORDS.search(v):
        return False
    # 顺序串（abcdefgh…/1234567890…）是手敲的合成示例，不是随机令牌（2026-10-06 补）
    if VALUE_SYNTHETIC.search(v.encode("ascii", "replace")):
        return False
    # 值是**成员/环境引用**（纯点分标识符路径）⇒ 它不是字面量。
    # 结构判定（2026-09-28，DSH 实证）：`environment.DOWNLOAD_TEST_COS_SECRET_KEY`、
    # `process.env.DSH_WORKSPACE_UPDATE_TOKEN`、`RELEASE_ENVIRONMENT.APPLE_API_KEY` 都是**引用**——
    # 引用指向别处，真正的值若存在会在其**定义处**被本门禁另行检出，所以跳过引用不降低检出能力。
    if re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+", v):
        return False
    # 单一字符重复（aaaa…/0000…）不是密钥
    if len(set(v)) <= 3:
        return False
    # 长**描述性 slug** 不是密钥（2026-09-28，DSH 实证：`github-webhook-real-e2e-secret`）。
    # 结构判据：全长小写、只由 `[a-z0-9-_]` 组成、且**含 a-f 之外的字母**。
    #   · 全小写 + 含 g-z ⇒ 是英文词组，不是随机串；
    #   · 而**全字母的长 hex**（只用 a-f，如 abcdefabcdef…）仍判为密钥 —— 这条不能误伤。
    # 注意：**不可**直接把 `e2e` 之类加进停用词 —— 十六进制令牌里 `e2e` 是常见子串，那样会真漏。
    if len(v) >= 32 and re.fullmatch(r"[a-z0-9\-_]+", v) and re.search(r"[g-z]", v):
        return False
    # 至少要有一定字符多样性：数字+字母混合，或长 hex
    has_digit = any(c.isdigit() for c in v)
    has_alpha = any(c.isalpha() for c in v)
    return (has_digit and has_alpha) or (len(v) >= 32 and has_alpha)

# H6 借鉴记账三要素
# 词形放宽（2026-09-27 误报治理，均由实证驱动）：
#   · URL：台账里普遍写成裸主机路径（github.com/owner/repo），不带 https://；并接受
#     「无公开链接/来源未留存/来源未注明/无上游」这类**显式的来源缺失声明**——记账的目的是
#     「来源被记录过」，记成"查不到"也算记录。
#   · 不入仓声明：等价说法很多（不公开发布/仅本地保留/禁止进入任何公开仓），原先只认一种写法。
ATTR_URL = re.compile(
    r"https?://\S+|(?:github|gitee|gitlab|bitbucket|sourceforge)\.(?:com|net|io)/\S+|"
    r"无公开链接|来源未留存|来源未注明|无上游")
ATTR_LICENSE = re.compile(r"(MIT|Apache[- ]?2|GPL|AGPL|BSD|CC[ -]?BY|MPL|Unlicense|许可|License)", re.I)
ATTR_NOCOMMIT = re.compile(
    r"(不入仓|不入库|不随仓库分发|不随仓发布|不纳入版本|gitignore|不公开发布|不对外发布|"
    r"仅本地保留|仅本地参考|禁止进入任何公开仓|不进公开仓|不进入公开仓)")


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


def untracked_unignored(repo):
    """**未跟踪且未被忽略**的文件（`--exclude-standard` 已排除 .gitignore 命中的）。

    为什么要单独要这一面（2026-09-28 实证）：`dsh web` 把会话令牌写进
    **未跟踪**的 `dsh-web-diagnose-<ts>.log` 落在仓根。未跟踪文件在 H5 的视野之外
    （H5 只拿 `tracked`），而**未跟踪且未被忽略**恰是最危险的窗口 ——
    它还没被 .gitignore 挡住，**一次 `git add -A` 就会把令牌提交进索引**。
    （同类前科：`*.egg-info` 经 `git add -A` 误入过 d20 仓，见 H3 注释。）
    """
    rc, out = run_git(repo, "-c", "core.quotepath=false",
                      "ls-files", "--others", "--exclude-standard", "-z")
    if rc != 0:
        return []
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
    """从 `remote.origin.url` 解析**仓名**。

    支持四类形态（2026-10-06 扩容；旧实现只认前两类的一半）：
      · `https://host/owner/repo.git`
      · `git@host:owner/repo.git`（SSH 简写，用 `:` 分隔 owner/repo）
      · `file:///path/to/repo.git`
      · **本地/相对路径**（`<盘>:\\path\\to\\repo`、`/path/to/repo`）—— `git clone <本地路径>` 后就是这种

    ⚠ 旧实现 `re.search(r"[:/]([^/:]+?)(?:\\.git)?$", url)` 对 `G:\\allin` 会取到 **`\\allin`**（含反斜杠：
    因为 `[^/:]` 不排除 `\\`），于是 H7 在"克隆自本地路径"时**误报**
    `目录名 'allin' != origin 仓名 '\\allin'`。实证与判据验证见 `记录/交接/2026-10.md` §104.6：
    把副本 origin 改回真实 URL 后同一副本 `RESULT: 通过` ⇒ 确认是解析缺陷，不是仓名真不一致。
    """
    rc, out = run_git(repo, "config", "--get", "remote.origin.url")
    if rc != 0 or not out.strip():
        return None
    url = out.strip().replace("\\", "/").rstrip("/")     # 反斜杠统一（Windows 本地路径）
    if url.endswith(".git"):
        url = url[:-4]
    name = url.rsplit("/", 1)[-1]                        # 取最后一段
    if ":" in name:                                      # `host:repo`（SSH 无 owner）兜底
        name = name.rsplit(":", 1)[-1]
    name = name.strip()
    return name or None


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
        for i, p in enumerate(parts[:-1]):
            # 任意层级：无歧义的产物目录名
            if p in ARTIFACT_DIRS:
                hit = "产物目录 '{}'".format(p)
                break
            # 仅仓根（i == 0）：`release` 作为源码目录名极为常见，非根级不判
            # （2026-09-28：DSH 的 scripts/release/ 是发布工具源码，12 条误报由此而来）
            if i == 0 and p in ARTIFACT_DIRS_ROOT_ONLY:
                hit = "仓根产物目录 '{}'".format(p)
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
            # 同行注明「这是夹具」即豁免（2026-09-27）：门禁**必然**包含它要找的模式，
            # 自检夹具更是刻意写出真实形态；但豁免只作用于**那一行**，真实值照旧检出。
            # 2026-09-28 补：同时认**兄弟门禁自己的标记** `gov-credentials: allow`。
            #   实证：DSH 的 governance/gates/g03_credentials.py、g04_push_evidence.py 里
            #   刻意写出真实密钥形态做自检，并且**已经**用 `# gov-credentials: allow` 标注，
            #   但本工具原先只认 `repo-hygiene: allow` ⇒ 两套标记不互通 ⇒ 那 5 条被反复判红。
            #   标记名不同不代表豁免意图不同，**认它**；但同样只作用于那一行。
            line_start = data.rfind(b"\n", 0, m.start()) + 1
            line_end = data.find(b"\n", m.end())
            line = data[line_start: line_end if line_end != -1 else len(data)]
            if b"repo-hygiene: allow" in line or b"gov-credentials: allow" in line:
                continue
            index = CRED_PATTERNS.index(pat)
            # 形态②（URL 内嵌凭据）：**主机名**若是 RFC 2606/6761 保留域，则必然不是真实服务。
            # 结构判定（2026-09-28，DSH 实证）：g04_push_evidence.py 的自检夹具写的是
            # `https://svc:8f14e45f…@host.invalid/x.git` —— `.invalid` 是保留的无效 TLD，
            # 且 `8f14e45fceea167a5a36dedd4bea2543` 是 "1234567" 的 MD5（经典占位哈希）。
            # 用户名:口令 的形态在这里无法靠"值像不像"判，但**主机名能**。
            if index == 1:
                tail = data[m.end(): m.end() + 96]
                hm = re.match(rb"[^/\s\"'`]+", tail)
                if hm and re.search(rb"\.(?:invalid|test|example|localhost)(?=[/:]|$)", hm.group(0), re.I):
                    continue
            if index in CONTEXT_REQUIRED:
                window = data[max(0, m.start() - 200):m.end() + 200]
                if not CONTEXT_REQUIRED[index].search(window):
                    continue
            # 形态①（键值对）需额外判定「值是否真像密钥」，避免把英文说明当凭据
            if "k" in pat.groupindex:
                try:
                    val = m.group("v").decode("ascii", "replace")
                except Exception:
                    val = ""
                if not _value_looks_secret(val):
                    continue
            else:
                # 形态②③（URL 内嵌凭据 / sk- 密钥）**没有 k 组**，原先完全绕过值判定。
                # 2026-09-28 补（DSH 实证）：命中文本本身若含"自证是夹具"的词，即为夹具 ——
                #   实证 `sk-e2efixture1234567890`（`const FIXTURE_SECRET = 'sk-e2efixture…'`）、
                #   `'prove telemetry with key sk-e2efixture1234567890'`。
                #   真实凭据不会自称 fixture。只对**命中文本本身**判，不扩大窗口。
                mt = m.group(0)
                if VALUE_STOPWORDS.search(mt.decode("ascii", "replace")):
                    continue
                # 2026-10-06 补两条（同族：命中文本**自称 / 看着**就是合成物，不是凭据）
                if VALUE_SYNTHETIC.search(mt):
                    continue
                if CRED_PATTERN_TEXT.search(mt):
                    continue
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
    # 触发词收窄（2026-09-27 误报治理）：原先含裸「上游 / upstream / reference」，
    # 而这三个是**通用技术词**——本仓几乎每篇文档都写「上游仓 / 上游快照 / 上游版本」，
    # 于是把路线图、评估、历史流水统统拉进来判（21 条里 19 条是这么来的）。
    # 现在只认**明确的借鉴声明**：借鉴 / 源码来源 / 第三方源码（或 code/asset/notice）/ borrowed。
    trigger = re.compile(r"借鉴|源码来源|第三方(源码|代码|资产|组件)|"
                         r"third[- ]party\s+(source|code|asset|notice)|borrowed", re.I)
    # 判据范围收窄（同日第二次，按本函数自己的说明对齐）：**记账的载体是专档**——
    # 只有「台账型」文档才要求三要素齐全，其余文档出现「借鉴」二字（规则原文、定位陈述）
    # 不构成借鉴声明。原先扫全部 docs/，与上面的说明自相矛盾。
    ledger = re.compile(r"来源|许可|reference|notice|attribution|资产", re.I)
    for t in tracked:
        low = t.lower()
        if not low.endswith((".md", ".txt")):
            continue
        # 只判 docs/ 下的专档（README 是门面，不是记账载体）
        if not low.startswith("docs/"):
            continue
        # 历史树只增不改（docs/md/ = 当时的判断依据），不做回溯改写，也就不判它
        if low.startswith("docs/md/"):
            continue
        # 只判台账型文档（文件名即其职责）
        if not ledger.search(os.path.basename(low)):
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
        # 有 origin 却解析不出仓名 ⇒ **不许静默通过**（`g10-failloud-probe`：拿不到输入要响亮说明）。
        # 完全**没有** origin 的仓不属本项（H7 判的是"目录名 vs 仓名"的一致性）。
        rc, out = run_git(repo, "config", "--get", "remote.origin.url")
        if rc == 0 and out.strip():
            return [Finding("H7", repo, "(仓名)",
                            "SKIPPED (not a pass)：origin 存在但解析不出仓名（{}）".format(out.strip()))]
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


def _default_audit_file(name):
    """审计文件的默认位置：**兼容两份落点**（2026-09-28 修）。

    · 分发副本：`<仓根>/tools/repo_hygiene.py` → `<仓根>/tools/gate/audit/<name>`
    · 工作副本：`/tools/gate/repo_hygiene.py`   → `/tools/gate/audit/<name>`

    原先写死第一种，于是工作副本会去找 `/tools/gate/gate/audit/…`（不存在）⇒
    **基线/豁免表静默落空**（与 `--repos-root` 的默认值同一类缺陷）。
    取**第一个已存在**的；都不存在时返回分发形态的路径（保持原行为，且能给出可读的路径）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(here, "gate", "audit", name), os.path.join(here, "audit", name)]
    for c in cands:
        if os.path.isfile(c):
            return c
    return cands[0]


def scan_repo(repo, ctx):
    if not is_git_repo(repo):
        return [Finding("ENV", repo, "-", "不是 git 仓（无 .git）")]
    tracked = tracked_files(repo)
    if tracked is None:
        return [Finding("ENV", repo, "-", "git ls-files 失败（仓可能损坏）")]
    # 体量一次取全，供 H4 用（避免逐文件 spawn：见 blob_sizes 的性能纪律）
    ctx = dict(ctx)
    ctx["_blob_sizes"] = blob_sizes(repo)
    # --worktree：把「未跟踪且未被忽略」的文件**额外**交给 H5（凭据）扫。
    # 依据见 untracked_unignored() 的说明：那个窗口一次 `git add -A` 就会把令牌入库。
    # 只扩 H5，不扩其它检查 —— 未跟踪的产物目录/大文件是 H4 的既有职责（见 --worktree 分支），
    # 把 H2/H3/H6 也铺到未跟踪面会让结果语义变浑（"跟踪面含…"的措辞就不成立了）。
    h5_extra = untracked_unignored(repo) if ctx.get("worktree") else []
    out = []
    for _cid, fn, _desc in CHECKS:
        try:
            arg = tracked + h5_extra if _cid == "H5" else tracked
            out.extend(fn(repo, arg, ctx))
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


def load_exemptions(path):
    """读仓级豁免表：`check,repo,path,reason,recorded_at`。

    **`reason` 为空的行一律不生效**，并原样返回给调用方报出来 —— 例外也要记账。
    `path` 支持两种写法：精确匹配；或以 `*` 结尾表示**前缀匹配**（如 `vendor/*`）。
    返回 (生效项, 缺理由项)。
    """
    active, invalid = [], []
    if not path or not os.path.isfile(path):
        return active, invalid
    try:
        with io.open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                chk = (row.get("check") or "").strip()
                repo = (row.get("repo") or "").strip()
                pth = (row.get("path") or "").strip()
                reason = (row.get("reason") or "").strip()
                if not (chk and repo and pth):
                    continue
                if not reason:
                    invalid.append("{} {} {}".format(chk, os.path.basename(repo.rstrip("/\\")), pth))
                    continue
                active.append((chk, os.path.normcase(repo.rstrip("/\\")), pth))
    except Exception as e:  # noqa: BLE001
        print("  ⚠ 豁免表读取失败（{}）：{}".format(path, e))
    return active, invalid


def is_exempted(finding, active):
    """命中是否落在豁免表内（仓路径与检查项都要对上，path 支持 `*` 前缀）。"""
    repo = os.path.normcase(finding.repo.rstrip("/\\"))
    for chk, ex_repo, pth in active:
        if finding.check != chk or repo != ex_repo:
            continue
        if pth.endswith("*"):
            if finding.path.startswith(pth[:-1]):
                return True
        elif finding.path == pth:
            return True
    return False


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

        # H3 反例（2026-09-28 新增，DSH 12 条误报实证）：
        #   `release` 只认**仓根**。`scripts/release/*.ts` 是发布工具源码，不得判；
        #   而仓根的 `release/` 仍须判（否则把这条规则改废了）。
        def _h3rel(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "scripts/release/bump.ts", "export const x = 1\n")
            wr(d, "tools/release/notes.py", "print(1)\n")
        r = _make_fixture(tmp, "h3rel", _h3rel)
        h3 = [x for x in scan_repo(r, {}) if x.check == "H3"]
        print("  H3 非根级 release 不判: {}  [{}]".format("✔" if not h3 else "✘", len(h3)))
        ok &= not h3

        def _h3relroot(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "release/app.bin", "x\n")
        r = _make_fixture(tmp, "h3relroot", _h3relroot)
        h3 = [x for x in scan_repo(r, {}) if x.check == "H3"]
        print("  H3 仓根 release 仍判:   {}  [{}]".format("✔" if h3 else "✘", len(h3)))
        ok &= bool(h3)

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
        secret = "a1b2c3d4e5f67890abcdef1234567890"  # repo-hygiene: allow
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

        # H5 反例三：**提及令牌文件名**但附近没有密钥值（2026-09-27 误报治理，14 处实证形态）
        def _cred_mention(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/令牌说明.md", "令牌取自 `私人令牌.txt`，**未打印**；该文件不入库。\n"
                                       "曾发现 remote URL 内嵌 `siwpan:<token>@gitee.com`，已清理。\n")
        r = _make_fixture(tmp, "cred_mention", _cred_mention)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 提及令牌文件名零误报: {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        # H5 正例二：提及令牌文件名的**同一窗口里有 32+ hex** → 仍须检出（豁免不能吃掉真问题）
        def _cred_mention_value(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/令牌说明.md", "私人令牌.txt 里第一行是 8f14e45fceea167a5a36dedd4bea2543（示例）。\n")  # repo-hygiene: allow
        r = _make_fixture(tmp, "cred_mention_value", _cred_mention_value)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 文件名声明旁的密钥值被检出: {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # H6 反例一：只提到「上游」这类通用技术词，不构成借鉴声明（19 处实证形态）
        def _upstream_only(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/升级说明.md", "上游快照换了；上游仓只作参考，本仓不追上游版本。\n")
        r = _make_fixture(tmp, "upstream_only", _upstream_only)
        h6 = [x for x in scan_repo(r, {}) if x.check == "H6"]
        print("  H6 仅提上游零误报:   {}  [{}]".format("✔" if not h6 else "✘", len(h6)))
        ok &= not h6

        # H6 反例二：历史树 docs/md/ 只增不改，不做回溯改写也就判它
        def _history(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/md/old/2026-07-05.md", "借鉴了某上游实现。\n")
        r = _make_fixture(tmp, "attr_history", _history)
        h6 = [x for x in scan_repo(r, {}) if x.check == "H6"]
        print("  H6 历史树不判:       {}  [{}]".format("✔" if not h6 else "✘", len(h6)))
        ok &= not h6

        # H6 反例三：三要素用等价写法（裸主机路径 + 仅本地保留）→ 不得误报
        def _attr_equivalent(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/REFERENCE.md", "借鉴：来源 github.com/owner/repo，许可 MIT，仅本地保留。\n")
        r = _make_fixture(tmp, "attr_equivalent", _attr_equivalent)
        h6 = [x for x in scan_repo(r, {}) if x.check == "H6"]
        print("  H6 等价写法零误报:   {}  [{}]".format("✔" if not h6 else "✘", len(h6)))
        ok &= not h6

        # H6 反例四：非台账文档出现「借鉴」二字（规则原文/定位陈述）→ 不是借鉴声明
        def _attr_nonledger(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "docs/参赛梳理.md", "治理准则：创新 = 借鉴 + 调整 + 同步 + 记账。\n")
        r = _make_fixture(tmp, "attr_nonledger", _attr_nonledger)
        h6 = [x for x in scan_repo(r, {}) if x.check == "H6"]
        print("  H6 非台账不判:       {}  [{}]".format("✔" if not h6 else "✘", len(h6)))
        ok &= not h6

        # H5 反例四：门禁自身必然包含它要找的模式 —— 同行注明「夹具」即豁免，但真实值仍须检出
        def _cred_self_reference(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "tools/checker.py", 'secret = "a1b2c3d4e5f67890abcdef1234567890"  # repo-hygiene: allow\n')
        r = _make_fixture(tmp, "cred_self", _cred_self_reference)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 同行注明夹具即豁免: {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        # H5 反例五（2026-09-28，DSH 实证）：**兄弟门禁自己的标记**也要认。
        # DSH 的 g03_credentials.py / g04_push_evidence.py 刻意写出真实密钥形态做自检，
        # 且已用 `# gov-credentials: allow` 标注；本工具原先只认 repo-hygiene: allow ⇒ 反复误报。
        def _cred_sibling_marker(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "governance/gates/g03.py",
               'sandbox.write("k.ts", "const apiKey = \'a8f3d9e2b7c4a1f6d0e5b8c3a9f2d7e4\'\\n")  # gov-credentials: allow\n')
        r = _make_fixture(tmp, "cred_sib", _cred_sibling_marker)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 兄弟门禁标记也认: {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        # H5 反例六（2026-09-28，DSH 实证）：键名**左边**是字母/数字/下划线 ⇒ 是子串，不是凭据键。
        # `const LONG_TOKEN = '<32 字符>'` 曾因名字含 token 被命中（LONG_TOKEN 是宽表格测试的长路径串）。
        # 同时**必须**证明真键名仍被检出，否则等于把规则改废。
        def _cred_substring_key(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "apps/web/tests/wide.e2e.ts",
               "const LONG_TOKEN = 'workspace/packages/client/ui/render.tsx/'.repeat(2)\n")
        r = _make_fixture(tmp, "cred_sub", _cred_substring_key)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 键名子串不判:     {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        def _cred_real_key(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "src/a.ts", "const accessToken = 'a1b2c3d4e5f67890abcdef1234567890'\n")
        r = _make_fixture(tmp, "cred_real", _cred_real_key)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 真键名仍判:       {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # H5 反例七（2026-09-28，DSH 实证）：**长描述性 slug** 不是密钥，
        # 但**全字母的长 hex**（只用 a-f）必须仍然算 —— 这条不能误伤。
        def _cred_slug(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/a.ts", "const SECRET = 'github-webhook-real-e2e-secret-longer'\n")
        r = _make_fixture(tmp, "cred_slug", _cred_slug)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 描述性 slug 不判: {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        def _cred_hexalpha(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/b.ts", "const accessToken = 'abcdefabcdefabcdefabcdefabcdefab'\n")
        r = _make_fixture(tmp, "cred_hexa", _cred_hexalpha)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 全字母长hex仍判:  {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # H5 反例八：形态③（sk-）没有 k 组，原先**完全绕过值判定** ⇒ 夹具被反复判红。
        # 命中文本自带 fixture 字样即夹具；但真实的 sk- 形态仍须检出。
        def _cred_skfix(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/c.ts", "const FIXTURE_SECRET = 'sk-e2efixture1234567890'\n")
        r = _make_fixture(tmp, "cred_skfix", _cred_skfix)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 sk-夹具字样不判:  {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        def _cred_skreal(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/d.ts", "const k = 'sk-a1b2c3d4e5f67890abcdef1234567890'\n")
        r = _make_fixture(tmp, "cred_skreal", _cred_skreal)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 真 sk- 仍判:      {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # H5 反例九：URL 内嵌凭据若主机是 RFC 2606 保留域（.invalid/.test/.example/.localhost），
        # 必然不是真实服务；但真实主机仍须检出。
        def _cred_reserved(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/e.py", 'u = "https://svc:8f14e45fceea167a5a36dedd4bea2543@host.invalid/x.git"\n')
        r = _make_fixture(tmp, "cred_res", _cred_reserved)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 保留域主机不判:   {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

        def _cred_realhost(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/f.py", 'u = "https://svc:8f14e45fceea167a5a36dedd4bea2543@gitee.com/o/n.git"\n')
        r = _make_fixture(tmp, "cred_realh", _cred_realhost)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 真实主机仍判:     {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        # 仓级豁免（2026-09-28）：**有理由才生效，缺理由不生效**。
        # 这条是「例外也要记账」的机械保障 —— 否则豁免表会退化成第二份基线。
        def _ex_fixture(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "vendor/lib.c", "x\n")
            wr(d, "output/r.xlsx", "x\n")
        r = _make_fixture(tmp, "exempt", _ex_fixture)
        res = [x for x in scan_repo(r, {}) if x.check == "H2"]
        exf = os.path.join(tmp, "ex.csv")
        with io.open(exf, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["check", "repo", "path", "reason", "recorded_at"])
            w.writerow(["H2", r, "vendor/*", "有意 vendor，见 vendor/README.md 的 manifest", "2026-09-28"])
        act, inv = load_exemptions(exf)
        left = [x for x in res if not is_exempted(x, act)]
        print("  豁免表有理由即生效:   {}  [{}]".format("✔" if len(act) == 1 and not left and not inv else "✘",
                                                    "%d生效/%d剩余/%d无效" % (len(act), len(left), len(inv))))
        ok &= len(act) == 1 and not left and not inv

        exf2 = os.path.join(tmp, "ex_noreason.csv")
        with io.open(exf2, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["check", "repo", "path", "reason", "recorded_at"])
            w.writerow(["H2", r, "vendor/*", "", "2026-09-28"])
        act2, inv2 = load_exemptions(exf2)
        left2 = [x for x in res if not is_exempted(x, act2)]
        print("  豁免表缺理由不生效:   {}  [{}]".format("✔" if not act2 and inv2 and left2 else "✘",
                                                    "%d生效/%d剩余/%d无效" % (len(act2), len(left2), len(inv2))))
        ok &= not act2 and bool(inv2) and bool(left2)

        # H5 反例十（2026-09-28，DSH 实证）：**未跟踪且未被忽略**的文件里若有令牌，
        # `--worktree` 必须抓到它 —— 那是最危险的窗口（一次 git add -A 就入库）。
        # 同时验证 **--worktree 关闭时不抓**（否则等于把未跟踪面静默并入常规扫描）。
        #
        # ⚠ 注意探针要选 H5 **真能抓**的形态：形态①有前置否定 `(?<![&?/])`，
        #   所以 URL 查询参数形态 `?token=<值>` 是**刻意排除**的（RolePlayer 的 gitee 公开链接实证）。
        #   ⇒ DSH 那个 `?token=…` 的诊断日志，**即使进了未跟踪面 H5 也抓不到** ——
        #   这也正是当时改用 .gitignore 规则兜住它的原因，两者是互补而非重复。
        def _cred_untracked(d):
            wr(d, "LICENSE", "MIT\n")
        r = _make_fixture(tmp, "cred_untracked", _cred_untracked)
        wr(r, "diagnose-run.log", "const accessToken = 'a1b2c3d4e5f67890abcdef1234567890'\n")
        h5_off = [x for x in scan_repo(r, {}) if x.check == "H5"]
        h5_on = [x for x in scan_repo(r, {"worktree": True}) if x.check == "H5"]
        print("  H5 未跟踪面(关)不抓: {}  [{}]".format("✔" if not h5_off else "✘", len(h5_off)))
        print("  H5 未跟踪面(开)抓:   {}  [{}]".format("✔" if h5_on else "✘", len(h5_on)))
        ok &= not h5_off and bool(h5_on)

        # H5 反例十一（2026-09-28）：**URL 查询参数令牌按宿主分流**。
        # 环回/内网 ⇒ 本机服务凭据，判；公共站 ⇒ 分享链接，不判（RolePlayer 8 处实证）。
        # 两个方向都要测：只测一边等于把规则改废或把盲区留着。
        def _cred_loopback(d):
            wr(d, "LICENSE", "MIT\n")
            # 夹具必须**自带 allow 标记，且标记要在同一源码行**：本门禁的扫描面包含它自己的源码，
            # 不带标记就会被自己判红（2026-10-06 实测：H5 两条存量红之一即此）。
            # ⚠ 标记只能放在**源码行尾注释**里、不能写进字符串内容 —— 写进内容就进了夹具文件，
            #   该夹具是"必须被判红"的正例（H5 环回URL令牌判），那样会把正例测废。
            wr(d, "t/g.log", "dsh web: http://127.0.0.1:3080/?token=a1b2c3d4e5f67890abcdef1234567890\n")  # repo-hygiene: allow
        r = _make_fixture(tmp, "cred_lo", _cred_loopback)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 环回URL令牌判:    {}  [{}]".format("✔" if h5 else "✘", len(h5)))
        ok &= bool(h5)

        def _cred_localhost_lan(d):
            # 注意：H5 每文件**最多产出一条** finding（`pat.search` 命中即 break），
            # 所以两种宿主形态要分放两个文件，否则只验得到一条。
            wr(d, "LICENSE", "MIT\n")
            wr(d, "t/h.log", "u=http://localhost:8000/&api_key=a1b2c3d4e5f67890abcdef1234567890\n")
            wr(d, "t/i.log", "v=http://192.168.1.7:9000/?token=b2c3d4e5f67890abcdef1234567890ab\n")
        r = _make_fixture(tmp, "cred_lan", _cred_localhost_lan)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 localhost/内网判: {}  [{}]".format("✔" if len(h5) >= 2 else "✘", len(h5)))
        ok &= len(h5) >= 2

        def _cred_public_link(d):
            wr(d, "LICENSE", "MIT\n")
            wr(d, "rules.html",
               'x <a href="https://www.beian.gov.cn/portal/x?&token=651a3142deadbeefdeadbeefdeadbeef1234">y</a>\n')
        r = _make_fixture(tmp, "cred_pub", _cred_public_link)
        h5 = [x for x in scan_repo(r, {}) if x.check == "H5"]
        print("  H5 公共站分享链接不判: {}  [{}]".format("✔" if not h5 else "✘", len(h5)))
        ok &= not h5

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

        # H7 反例一（2026-10-06 修）：**本地路径 remote**（`git clone <本地路径>` 后的形态）不得误报。
        # 旧实现的正则对 `G:\allin` 取到 `\allin`（含反斜杠），于是"克隆到本地路径"必然误报。
        local = os.path.join(tmp, "localclone", "allin")
        os.makedirs(local, exist_ok=True)
        subprocess.run(["git", "init", "-q", local], capture_output=True)
        subprocess.run(["git", "-C", local, "remote", "add", "origin",
                        os.path.join(tmp, "src", "allin")], capture_output=True)
        h7 = [x for x in scan_repo(local, {}) if x.check == "H7"]
        print("  H7 本地路径 remote 不误报: {}  [{}]".format("✔" if not h7 else "✘", len(h7)))
        ok &= not h7

        # H7 反例二（同轮）：origin **存在但解析不出仓名** ⇒ 报 SKIPPED，不许静默通过
        # （`g10-failloud-probe`：拿不到输入要响亮说明；"完全没 origin"仍不属本项）
        weird = os.path.join(tmp, "weirdorigin")
        os.makedirs(weird, exist_ok=True)
        subprocess.run(["git", "init", "-q", weird], capture_output=True)
        subprocess.run(["git", "-C", weird, "remote", "add", "origin", "https://"],
                       capture_output=True)
        h7 = [x for x in scan_repo(weird, {}) if x.check == "H7"]
        good = bool(h7) and "SKIPPED" in h7[0].detail
        print("  H7 解析不出仓名 ⇒ SKIPPED: {}  [{}]".format("✔" if good else "✘", len(h7)))
        ok &= good

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

def _default_repos_root():
    """仓根的默认落点：**装着各仓的那个目录**。

    本脚本有两份落点：`<仓根>/tools/`（分发副本）与工作区的 `/tools/`（工作副本）。
    两者都满足「上溯两级（或一级）= 工作区根，其下的 `repos` 就是仓根」，故用**同级 repos**
    而不是脚本自身仓根 —— 后者会让 `--all` 恒得 0 个仓（2026-09-28 实测踩到）。
    全程不出现盘符（铁律 5），换机/换盘自适应。
    """
    here = os.path.dirname(os.path.abspath(__file__))          # .../tools
    for cand_root in (os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        sib = os.path.join(cand_root, "repos")
        if os.path.isdir(sib):
            return sib
    return os.path.dirname(here)                               # 兜底：脚本自身仓根


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
    ap.add_argument("--repos-root",
                    default=os.environ.get("PROJECTS_ROOT")
                            or _default_repos_root(),
                    help="仓根 = **装着各仓的那个目录**（默认 = 环境变量 PROJECTS_ROOT，"
                         "否则脚本所在仓的**同级 `repos` 目录**，再否则脚本所在仓根）")
    ap.add_argument("--filter", help="只扫名字含该子串的仓")
    ap.add_argument("--worktree", action="store_true", help="追加未跟踪面扫描")
    ap.add_argument("--baseline",
                    default=_default_audit_file("hygiene_baseline.csv"))
    ap.add_argument("--write-baseline", action="store_true", help="把当前命中断言为基线")
    ap.add_argument("--no-baseline", action="store_true", help="忽略基线，看全部存量")
    ap.add_argument("--exemptions",
                    default=_default_audit_file("repo_hygiene_exemptions.csv"),
                    help="仓级豁免表（check,repo,path,reason,recorded_at）；**reason 为空的行不生效**")
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
        # 门禁契约（OPS-E1/E2）：拿到不可用的输入必须**响亮报错**，不能静默返回 0。
        # 原实现打印一行 WARN 就 exit 0 —— 实测后果：`--all` 因 --repos-root 默认落成
        # 脚本自身仓根（其子目录都不是 git 仓）而恒得 0 个仓，被误读成"扫描通过"。
        print("[ERR] --repos-root={} 下没有找到任何 git 仓；"
              "请用 --repos-root 指定仓根（或设 PROJECTS_ROOT）".format(args.repos_root),
              file=sys.stderr)
        return 3

    if not args.quiet:
        print("== 仓库卫生门禁 ==")
        print("  范围: {} 个仓 | 跟踪面{}".format(len(repos), " + 工作树" if args.worktree else ""))

    findings = []
    for r in repos:
        findings.extend(scan_repo(r, ctx))

    # ---------- 仓级豁免（2026-09-28 新增）----------
    # 与「基线」的本质区别（这正是要单做一套的原因）：
    #   · **基线** = 「这些命中我已知、暂不处理」的**时间棘轮** —— 不解释理由，且随新增而漂移；
    #   · **豁免** = 「这一条**不是问题**，因为……（理由）」的**显式判定** —— **理由必填**，缺理由不生效。
    # 规划里明写「把误报入基线等于把噪声合法化」，所以需要这条**要写理由**的通道。
    # 典型用途：DSH 的 `vendor/` 是**有意 vendor**（带 manifest、上游 commit、MIT LICENSE），
    # 不是"把第三方源码倒进仓"——这类"规则本身没错、但对本仓是有意例外"的情形走豁免。
    active_ex, invalid_ex = load_exemptions(args.exemptions)
    if invalid_ex and not args.quiet:
        print("  ⚠ 豁免表有 {} 行**缺理由**，已忽略（例外也要记账）：{}".format(
            len(invalid_ex), "；".join(invalid_ex[:3])))
    if active_ex:
        before_n = len(findings)
        findings = [f for f in findings if not is_exempted(f, active_ex)]
        if not args.quiet:
            print("  已应用仓级豁免：豁免掉 {} 条（表内 {} 行生效）".format(before_n - len(findings), len(active_ex)))

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
