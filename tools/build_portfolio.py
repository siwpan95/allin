#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_portfolio.py —— 重建仓根 PORTFOLIO.md（Gitee 全量仓索引）。

为什么有这个脚本：PORTFOLIO.md 里写着「本文件由脚本从 Gitee API 自动生成 …… 需刷新时重跑生成脚本」，
但**生成脚本此前从未入库**（2026-09-28 实测：仓内与历史里都找不到）。本脚本补上这个落点。

用法：
    python build_portfolio.py                         # 干跑，打印统计与前三行
    python build_portfolio.py --apply                 # 写 <仓根>/PORTFOLIO.md
    python build_portfolio.py --owner <Gitee 账号>    # 换发行仓所有者
    PLATFORM_GITEE_OWNER=<账号> python build_portfolio.py

口径：
  · owner 默认 `siwpan`；与 `platform/scripts/check_repos.mjs` / `discover_repos.mjs`
    共用 `PLATFORM_GITEE_OWNER`（2026-11-13：换机 / 换发行仓时不再各写一份账号）
  · 只读公开 API（匿名即可，**不需要令牌**；也因此不要在脚本里放任何凭据）
  · 简介列按铁律 5 机械去符盘（`X:\\` → `/`），远端原文可能仍含盘符
  · 分页取全量（单页上限 100）
"""
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://gitee.com/api/v5"
DEFAULT_OWNER = "siwpan"
CTX = ssl.create_default_context()
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(REPO_ROOT, "PORTFOLIO.md")

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import runtime_defaults as _rd  # noqa: E402


def resolve_owner(argv):
    """与 platform/scripts/check_repos.mjs 同源：CLI > env > 默认。"""
    for i, a in enumerate(argv):
        if a == "--owner" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--owner="):
            return a.split("=", 1)[1]
    return os.environ.get("PLATFORM_GITEE_OWNER") or DEFAULT_OWNER


def fetch_all(owner):
    out, page = [], 1
    while page <= 5:
        url = "%s/users/%s/repos?type=all&sort=full_name&per_page=100&page=%d" % (API, owner, page)
        req = urllib.request.Request(url, headers={"User-Agent": "allin-portfolio-builder"})
        with urllib.request.urlopen(req, timeout=_rd.timeout("url_open"), context=CTX) as r:
            batch = json.loads(r.read().decode("utf-8"))
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        page += 1
    return out


def de_drive(s):
    """去符盘：X:\\foo / X:/foo -> /foo（铁律 5）。"""
    if not s:
        return s
    return re.sub(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]", "/", s).replace("\\\\", "/")


def main():
    apply_ = "--apply" in sys.argv
    owner = resolve_owner(sys.argv)
    try:
        repos = fetch_all(owner)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("ENV ERROR: 取远端仓清单失败：%s" % e)
        print("  （Gitee 匿名 API 有限流；隔一段时间重试，或不要在限流窗口内跑）")
        return 3

    repos.sort(key=lambda r: r["path"].lower())
    pub = sum(1 for r in repos if not r.get("private"))
    priv = len(repos) - pub
    today = __import__("datetime").date.today().isoformat()

    L = []
    L.append("# Gitee 项目组合索引（%s）" % owner)
    L.append("")
    L.append("> 本文件由 [`tools/build_portfolio.py`](tools/build_portfolio.py) 从 Gitee API 自动生成"
             "（生成于 %s），是**索引**而非源码镜像。" % today)
    L.append("> **治理原则：源码按需懒拉取**——只有开始具体开发某项目时，才 `git clone` 到本地 `/repos/<仓名>`；")
    L.append("> 不预先克隆全量仓库。本索引随远端变化而过期，需刷新时重跑：`python tools/build_portfolio.py --apply`。")
    L.append("> 简介列里的多段盘符路径已按铁律 5 机械去符盘（远端原文可能仍含盘符）。")
    L.append("")
    L.append("**共 %d 个仓库**（公开 %d · 私有 %d）。" % (len(repos), pub, priv))
    L.append("")
    L.append("## 全量清单（按仓库名排序）")
    L.append("")
    L.append("| 仓库 | 语言 | Star | 可见性 | 简介 |")
    L.append("|---|---|---|---|---|")
    for r in repos:
        name = r["path"]
        lang = r.get("language") or "—"
        star = r.get("stargazers_count", 0)
        vis = "私有" if r.get("private") else "公开"
        desc = (r.get("description") or "").replace("|", "\\|").strip()
        desc = de_drive(desc)
        L.append("| [%s/%s](https://gitee.com/%s/%s.git) | %s | %s | %s | %s |"
                 % (owner, name, owner, name, lang, star, vis, desc))
    L.append("")
    text = "\n".join(L) + "\n"

    if apply_:
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("已写入 %s（%d 仓 / 公开 %d / 私有 %d）" % (OUT, len(repos), pub, priv))
    else:
        print("干跑：owner=%s 共 %d 仓（公开 %d / 私有 %d）" % (owner, len(repos), pub, priv))
        for line in L[:12]:
            print("  " + line)
        print("  （干跑；加 --apply 落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
