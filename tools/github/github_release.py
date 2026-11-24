#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github_release.py — GitHub 建仓 / 转公开 / 增量推送 / 独立复核（分步、可重入、零三方依赖）
====================================================================================

对称 tools/gitee_release.py，但**按 GitHub 平台差异实现，不照搬 Gitee 判据**：

  · Gitee 的 `public` 是整数（0/1/2）且与 `private` 互斥、空仓不能设公开、须先建私有再 PATCH；
    GitHub 是 `private` 布尔值，建仓时直接给 `private=True`，推完再 PATCH `private=False`。
  · Gitee 走 HTTPS 直推；GitHub 在本环境 443 被封，**推送只能走 SSH**
    （git@github.com:<owner>/<repo>.git），REST 建仓/改可见性仍走 api.github.com（通）。
  · GitHub 拒收 shallow push（`did not receive expected object`）——推送前必须
    `git fetch --unshallow origin`，否则报「成功」实为失败。
  · 限流：主限流 5000/h（x-ratelimit-* 头为权威）；次级内容创建 80/min、500/h
    （POST 计 5 points），超限 403/429 + Retry-After / x-ratelimit-reset。
    与 Gitee 的「新建项目配额撞限后小时间隔重试无效」不同，GitHub 按头退避即可。

令牌来源（**绝不写进仓库**，参照 gitee_release 的 GITEE_TOKEN 纪律）：
    1. 环境变量 GITHUB_TOKEN
    2. git credential fill（host=github.com）→ Windows 凭据管理器（GCM / DPAPI）
       —— 本机已验证可用（login=siwpan95，classic PAT 含 repo scope）
    3. --token-file 仅供显式指定的外部文件（不入库）

子命令：
    whoami                     验证令牌与账号
    list                       列出账号下公开仓（分页）
    create --name <repo>       建私有仓（幂等；已存在跳过）
    public --name <repo>       推完后转公开（幂等；匿名 GET 复核）
    remote --name <repo>       设置/添加 github SSH remote
    push   --name <repo>       增量推送（比对 refs，浅克隆自动补全）
    verify                     独立复核：逐仓 ls-remote vs 本地 for-each-ref
    sync   [--apply]           巡检闭环：list → create → pull(ff-only from gitee) → push(to GitHub) → drift
                               **默认 dry-run：只报告不改动远端**；--apply 才真动作
                               权威源 = gitee 远端，绝不向 gitee 推送

安全边界（写死，不提供绕过开关）：
  · 工作区脏 / detached HEAD / 与远端分叉或本地领先 → 一律只报告，不自动 rebase/merge
  · 绝不向 gitee 推送（2026-11-24 全哥明确：gitee 远端是唯一权威源，本地与 GitHub 都是下游；
    原 pushorigin「本地回推 gitee」语义已废止，改为 drift 只读报告）
  · sin-virtue-game 在 gitee 已 404（退役仓），GitHub 侧保留归档副本，不为其建 gitee 仓
  · --apply 下建仓/推送属高风险，须人在场放行；automation 里默认不带 --apply

退出码：0 成功/无需动作 · 1 有失败 · 2 用法或环境 · 3 网络或 API 失败
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
SSH_TMPL = "git@github.com:{owner}/{name}.git"
DEFAULT_OWNER = "siwpan95"
REPOS_ROOT_ENV = "ALLIN_REPOS_ROOT"       # 去符盘：发布区根由环境变量给出
RATE_BACKOFF = [1, 5, 20, 60]             # GitHub 次级限流退避（秒），按 Retry-After 优先


def _rd():
    """运行时默认值（可选）；缺失时用内置常量，避免对治理仓结构的硬依赖。"""
    try:
        from tools import runtime_defaults as rd  # type: ignore
        return rd
    except Exception:
        return None


def repos_root(arg=None) -> str:
    root = arg or os.environ.get(REPOS_ROOT_ENV, "")
    if root:
        return os.path.abspath(root)
    rd = _rd()
    if rd is not None:
        for attr in ("REPOS_ROOT", "repos_root", "PUBLISH_ROOT"):
            v = getattr(rd, attr, None)
            if isinstance(v, str) and v:
                return os.path.abspath(v)
    raise SystemExit("[ERR] 未指定发布区根：用 --repos-root 或设 %s（不写死盘符）" % REPOS_ROOT_ENV)


def get_token(arg=None, token_file=None) -> str:
    """GITHUB_TOKEN → GCM(git credential fill) → 显式 token-file；令牌绝不入库、不回显。"""
    if arg and arg.strip():
        return arg.strip()
    env = os.environ.get("GITHUB_TOKEN", "").strip()
    if env:
        return env
    try:
        r = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith("password="):
                    tok = line[len("password="):].strip()
                    if tok:
                        return tok
    except Exception:
        pass
    if token_file:
        try:
            with open(token_file, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except OSError as e:
            raise SystemExit("[ERR] 读不到令牌文件 %s (%s)" % (token_file, e))
        # GitHub classic(ghp_)/fine-grained(github_pat_)/oauth(gho_) 三种前缀
        m = re.search(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,})\b", txt)
        if m:
            return m.group(0)
        raise SystemExit("[ERR] %s 里没有 GitHub 令牌形态的字符串" % token_file)
    raise SystemExit("[ERR] 没给令牌。设 GITHUB_TOKEN，或确保 GCM 有 github.com 条目，或用 --token-file。")


def api(method: str, path: str, token: str, data=None, timeout: int = 60):
    """JSON 请求。返回 (status, parsed_or_text, headers)。令牌仅在 Authorization 头。"""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(API + path, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "allin-github-release")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                try:
                    return r.status, json.loads(raw), dict(r.headers)
                except ValueError:
                    return r.status, raw, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            hdr = dict(e.headers)
            try:
                return e.code, json.loads(raw), hdr
            except ValueError:
                return e.code, raw, hdr
        except urllib.error.URLError as e:
            if attempt == 3:
                return -1, "网络错误: %s" % e, {}
            time.sleep(1.5 * (attempt + 1))
    return -1, "未知错误", {}


def _retry_after(hdr: dict, fallback_idx: int) -> int:
    """优先按 Retry-After / x-ratelimit-reset，否则用本地退避序列。"""
    try:
        if hdr.get("Retry-After"):
            return max(1, int(hdr["Retry-After"]))
    except (TypeError, ValueError):
        pass
    try:
        if hdr.get("X-RateLimit-Remaining") in (0, "0"):
            reset = int(hdr.get("X-RateLimit-Reset", 0))
            if reset:
                return max(1, reset - int(time.time()) + 2)
    except (TypeError, ValueError):
        pass
    return RATE_BACKOFF[min(fallback_idx, len(RATE_BACKOFF) - 1)]


def git(args, cwd=None, timeout=300, check=False):
    """跑一条 git 命令。

    `check` 只为接口一致性而存在：调用方写 `check=False` 表达「失败也继续」的意图
    （如 remote set-url 前先 add）。**不接受它会让整条子命令 TypeError** ——
    2026-11-24 实战（paixu 建仓推送）实测：`github remote` 就是这么崩的，
    而当时只有 `--version` 和 import 被验证过。签名与调用点必须一起看。
    """
    return subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          check=check)


def local_repos(root) -> list:
    out = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(os.path.join(d, ".git")):
            out.append(name)
    return out


def gh_repos(token) -> set:
    names, page = set(), 1
    while True:
        st, d, _ = api("GET", "/user/repos?per_page=100&page=%d&affiliation=owner" % page, token)
        if st != 200 or not isinstance(d, list):
            break
        names |= {x["name"] for x in d if isinstance(x, dict) and x.get("name")}
        if len(d) < 100:
            break
        page += 1
    return names


def cmd_whoami(token):
    st, d, h = api("GET", "/user", token)
    if st != 200:
        print("[FAIL] whoami: HTTP %s %s" % (st, str(d)[:200]))
        return 3
    scopes = h.get("X-OAuth-Scopes") or h.get("x-oauth-scopes") or "(fine-grained/无 scope 头)"
    print("[OK] login=%s type=%s" % (d.get("login"), d.get("type")))
    print("[INFO] scopes=%s" % scopes)
    st2, _, h2 = api("GET", "/rate_limit", token)
    if st2 == 200:
        print("[INFO] rate_limit core.remaining=%s" % h2.get("X-RateLimit-Remaining", "?"))
    return 0


def cmd_list(args, token):
    root = repos_root(args.repos_root)
    loc = local_repos(root)
    gh = gh_repos(token)
    missing = [n for n in loc if n.lower() not in {g.lower() for g in gh}]
    extra = sorted(g for g in gh if g.lower() not in {n.lower() for n in loc})
    print("本地仓 %d | GitHub 仓 %d | 待建 %d | GitHub 独有 %d" % (len(loc), len(gh), len(missing), len(extra)))
    if missing:
        print("待建: " + " ".join(missing))
    if extra:
        print("GitHub 独有(不在本地发布区): " + " ".join(extra))
    if args.json:
        print(json.dumps({"local": loc, "github": sorted(gh), "missing": missing, "extra": extra}, ensure_ascii=False))
    return 0


def cmd_create(args, token):
    """建私有仓（先私后公，与 gitee_release 同一纪律）；推完由 public 子命令转公开。"""
    st, d, _ = api("GET", "/repos/%s/%s" % (args.owner, args.name), token)
    if st == 200:
        print("[SKIP] 仓库已存在: %s (private=%s default_branch=%s)"
              % (d.get("full_name"), d.get("private"), d.get("default_branch")))
        return 0
    if st not in (404,):
        print("[FAIL] 探测仓库失败: HTTP %s %s" % (st, str(d)[:200]))
        return 3
    payload = {"name": args.name, "private": True, "auto_init": False}
    if args.desc:
        payload["description"] = args.desc
    for attempt in range(1, len(RATE_BACKOFF) + 1):
        st, d, hdr = api("POST", "/user/repos", token, payload)
        if st in (200, 201):
            print("[OK] 已创建私有仓: %s (id=%s) —— 推送后执行 public 转公开"
                  % (d.get("full_name"), d.get("id")))
            return 0
        if st == 422:
            print("[SKIP] 已存在(422): %s" % args.name)
            return 0
        blob = json.dumps(d, ensure_ascii=False) if not isinstance(d, str) else d
        if st in (403, 429):
            wait = _retry_after(hdr, attempt - 1)
            print("[WARN] 建仓遇限流 HTTP %s，退避 %ds（第 %d 次）" % (st, wait, attempt))
            if attempt < len(RATE_BACKOFF):
                time.sleep(wait)
                continue
            print("[FAIL] 限流持续，本轮收工（下一轮再试）: %s" % blob[:200])
            return 3
        print("[FAIL] 建仓失败: HTTP %s %s" % (st, blob[:300]))
        return 1
    return 1


def cmd_public(args, token):
    """推完转公开。幂等；转完用**匿名 GET**复核（不信认证态响应）。"""
    st, d, _ = api("GET", "/repos/%s/%s" % (args.owner, args.name), token)
    if st != 200:
        print("[FAIL] 仓库不存在: HTTP %s" % st)
        return 3
    if not d.get("private"):
        print("[SKIP] 已公开: %s" % d.get("full_name"))
    else:
        st2, d2, hdr = api("PATCH", "/repos/%s/%s" % (args.owner, args.name), token, {"private": False})
        if st2 != 200:
            blob = json.dumps(d2, ensure_ascii=False) if not isinstance(d2, str) else d2
            if st2 in (403, 429):
                print("[WARN] 限流，退避 %ds 后重试一次" % _retry_after(hdr, 0))
                time.sleep(_retry_after(hdr, 0))
                st2, d2, _ = api("PATCH", "/repos/%s/%s" % (args.owner, args.name), token, {"private": False})
            if st2 != 200:
                print("[FAIL] 转公开失败: HTTP %s %s" % (st2, str(d2)[:200]))
                return 1
        print("[OK] 已转公开: %s" % d2.get("full_name"))
    # 匿名复核（镜像 gitee_release 的匿名 GET 纪律）
    req = urllib.request.Request("https://api.github.com/repos/%s/%s" % (args.owner, args.name),
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "allin-gh-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            anon = json.loads(r.read().decode("utf-8", "replace"))
            print("[ANON] 匿名复核 private=%s default_branch=%s" % (anon.get("private"), anon.get("default_branch")))
            return 0 if not anon.get("private") else 1
    except Exception as e:
        print("[WARN] 匿名复核失败（不冒充成功）: %s" % e)
        return 3


def cmd_remote(args):
    root = repos_root(args.repos_root)
    d = os.path.join(root, args.name)
    if not os.path.isdir(os.path.join(d, ".git")):
        print("[FAIL] 本地无此仓: %s" % d)
        return 2
    url = SSH_TMPL.format(owner=args.owner, name=args.name)
    names = git(["remote"], cwd=d).stdout.split()
    if "github" in names:
        git(["remote", "set-url", "github", url], cwd=d, check=False)
        print("[OK] github remote 已更新: %s" % url)
    else:
        git(["remote", "add", "github", url], cwd=d, check=False)
        print("[OK] 已添加 github remote: %s" % url)
    return 0


def _refs(d) -> set:
    r = git(["for-each-ref", "--format=%(refname)", "refs/heads", "refs/tags"], cwd=d)
    return set(x.strip() for x in r.stdout.splitlines() if x.strip())


def _remote_refs(url) -> set:
    """远端 ref 全集，格式必须与 _refs() 一致（完整 refs/... 路径）。

    2026-11-24 首跑全红假象的根因：本函数曾把 refs/heads/ → heads/ 归一化，
    而 _refs() 返回完整路径，导致每个本地 ref 都被判「远端缺失」。
    另 git ls-remote 会输出 annotated tag 的 `^{}` 解引用行，本地 for-each-ref 没有，
    必须排除，否则那一行会被当成远端独有（本工具只做 local - remote 差集，影响小，但仍不严谨）。
    """
    r = git(["ls-remote", "--heads", "--tags", url], timeout=120)
    out = set()
    for line in r.stdout.splitlines():
        p = line.split("\t")
        if len(p) != 2:
            continue
        ref = p[1]
        if ref.endswith("^{}"):       # annotated tag 解引用，不是独立 ref
            continue
        if ref.startswith("refs/heads/") or ref.startswith("refs/tags/"):
            out.add(ref)              # 与 _refs() 同格式：完整 refs/... 路径
    return out


def _safe_state(d) -> str | None:
    """返回 None 表示安全；否则返回跳过原因（脏/detached/分叉/领先）。"""
    st = git(["status", "--porcelain", "-uno"], cwd=d)
    if st.stdout.strip():
        return "工作区有未提交改动"
    br = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=d)
    if br.stdout.strip() == "HEAD":
        return "detached HEAD"
    origin = git(["remote", "get-url", "origin"], cwd=d)
    if origin.returncode != 0:
        return "无 origin"
    fr = git(["fetch", "origin", "--prune"], cwd=d, timeout=300)
    if fr.returncode != 0:
        return "fetch 失败"
    ahead = git(["rev-list", "--count", "HEAD..@{u}"], cwd=d).stdout.strip()   # 落后
    behind = git(["rev-list", "--count", "@{u}..HEAD"], cwd=d).stdout.strip()  # 领先
    if behind not in ("0", ""):
        return "本地领先 %s 提交" % behind
    if ahead not in ("0", ""):
        return "落后远端 %s 提交（需先快进）" % ahead
    return None


def cmd_push(args):
    root = repos_root(args.repos_root)
    d = os.path.join(root, args.name)
    if not os.path.isdir(os.path.join(d, ".git")):
        print("[FAIL] 本地无此仓: %s" % d)
        return 2
    url = SSH_TMPL.format(owner=args.owner, name=args.name)
    names = git(["remote"], cwd=d).stdout.split()
    if "github" not in names:
        git(["remote", "add", "github", url], cwd=d)
    else:
        git(["remote", "set-url", "github", url], cwd=d)
    # 浅克隆补全（GitHub 拒收 shallow push）
    if os.path.exists(os.path.join(d, ".git", "shallow")):
        if not args.apply:
            print("[DRY] %s 浅克隆，需 fetch --unshallow" % args.name)
        else:
            print("[INFO] %s 浅克隆，补全历史…" % args.name)
            u = git(["fetch", "--unshallow", "origin"], cwd=d, timeout=1200)
            if u.returncode != 0:
                print("[FAIL] unshallow 失败: %s" % (u.stderr or "")[:160])
                return 1
    local = _refs(d)
    remote = _remote_refs(url)
    diff = sorted(local - remote)
    if not diff:
        print("[SKIP] %s 无差异，无需推送" % args.name)
        return 0
    print("[%s] %s 需推 refs %d 个: %s" % ("DRY" if not args.apply else "PUSH", args.name, len(diff), diff[:6]))
    if not args.apply:
        return 0
    p1 = git(["push", "github", "--all"], cwd=d, timeout=600)
    p2 = git(["push", "github", "--tags"], cwd=d, timeout=600)
    if p1.returncode == 0 and p2.returncode == 0:
        print("[OK] 已推送: %s" % args.name)
        return 0
    print("[FAIL] 推送失败: %s" % ((p1.stderr or "") + (p2.stderr or ""))[:300])
    return 1


def cmd_verify(args, token):
    """独立复核：逐仓 ls-remote 比本地 for-each-ref（不信脚本自称成功）。"""
    root = repos_root(args.repos_root)
    loc = local_repos(root)
    gh = {g.lower() for g in gh_repos(token)}
    ok = bad = skip = 0
    for i, name in enumerate(loc, 1):
        d = os.path.join(root, name)
        if name.lower() not in gh:
            print("  [%d/%d] %s 跳过：GitHub 无此仓" % (i, len(loc), name))
            skip += 1
            continue
        url = SSH_TMPL.format(owner=args.owner, name=name)
        local = _refs(d)
        remote = _remote_refs(url)
        if not remote:
            print("  [%d/%d] %s 跳过：ls-remote 无输出（网络/权限？）" % (i, len(loc), name))
            skip += 1
            continue
        miss = sorted(local - remote)
        if miss:
            print("  [%d/%d] ✗ %s 缺 %d 个 ref: %s" % (i, len(loc), name, len(miss), miss[:4]))
            bad += 1
        else:
            ok += 1
    print("VERIFY_SUMMARY total=%d ok=%d bad=%d skip=%d" % (len(loc), ok, bad, skip))
    return 0 if bad == 0 else 1


def cmd_sync(args, token):
    """巡检闭环：list → create → pull(ff-only) → push。默认 dry-run。"""
    root = repos_root(args.repos_root)
    loc = local_repos(root)
    gh = gh_repos(token)
    missing = [n for n in loc if n.lower() not in {g.lower() for g in gh}]
    print("[sync] 本地 %d | GitHub %d | 待建 %d | mode=%s"
          % (len(loc), len(gh), len(missing), "APPLY" if args.apply else "DRY-RUN"))
    created = pulled = pushed = 0
    manual = []
    for name in missing:
        if not args.apply:
            print("  [DRY] 待建: %s" % name)
            continue
        rc = cmd_create(argparse.Namespace(owner=args.owner, name=name, desc=""), token)
        if rc == 0:
            created += 1
    for i, name in enumerate(loc, 1):
        d = os.path.join(root, name)
        reason = _safe_state(d)
        if reason:
            manual.append((name, reason))
            print("  [MANUAL] [%d/%d] %s: %s" % (i, len(loc), name, reason))
            continue
        # 安全态 = 与 origin 一致；此时推 github 不会覆盖任何远端独有提交
        rc = cmd_push(argparse.Namespace(owner=args.owner, name=name,
                                        repos_root=root, apply=args.apply))
        if rc == 0 and args.apply:
            pushed += 1
    print("[sync] 建仓 %d | 快进 %d | 推送 %d | 需人工 %d" % (created, pulled, pushed, len(manual)))
    for n, r in manual:
        print("  需人工: %s — %s" % (n, r))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(description="GitHub 建仓/转公开/增量推送/独立复核（令牌不入库）")
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--repos-root", default="", help="发布区根；不传走 %s" % REPOS_ROOT_ENV)
    ap.add_argument("--token", default="", help="不推荐；优先 GITHUB_TOKEN / GCM")
    ap.add_argument("--token-file", default="", help="显式外部令牌文件（绝不入库）")
    ap.add_argument("--apply", action="store_true", help="真动作；不带则只报告（dry-run）")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("whoami")
    sub.add_parser("list")
    c = sub.add_parser("create"); c.add_argument("--name", required=True); c.add_argument("--desc", default="")
    c = sub.add_parser("public"); c.add_argument("--name", required=True)
    c = sub.add_parser("remote"); c.add_argument("--name", required=True)
    c = sub.add_parser("push"); c.add_argument("--name", required=True)
    sub.add_parser("verify")
    sub.add_parser("sync")
    return ap


def main(argv=None):
    # argv 可选：独立运行时走 sys.argv（argparse 约定），从包内 `allin-governance github`
    # 调用时由包装层把剩余参数传进来。2026-11-24 事故：原签名不接受参数，而 CLI 包装层
    # 传了一个 list ⇒ 每次 `github <子命令>` 都 TypeError（1.0.1 已发布版本实测）。
    ap = build_parser()
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    if args.cmd == "remote":
        return cmd_remote(args)
    token = get_token(args.token, args.token_file)
    if args.cmd == "whoami":
        return cmd_whoami(token)
    if args.cmd == "list":
        return cmd_list(args, token)
    if args.cmd == "create":
        return cmd_create(args, token)
    if args.cmd == "public":
        return cmd_public(args, token)
    if args.cmd == "push":
        return cmd_push(args)
    if args.cmd == "verify":
        return cmd_verify(args, token)
    if args.cmd == "sync":
        return cmd_sync(args, token)
    return 2


if __name__ == "__main__":
    sys.exit(main())
