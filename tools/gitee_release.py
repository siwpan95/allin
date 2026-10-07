#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gitee_release.py — Gitee 建仓 / 转公开 / 发布发行版（分步、可重入、零三方依赖）
==============================================================================

把"发一个版本"从手工点网页变成可复现的命令。每个子命令都能单独跑，
重复跑是幂等的（已存在就跳过，不重复创建），所以中断了可以直接重跑。

    python tools/gitee_release.py whoami
    python tools/gitee_release.py create   --name pluginplayer
    python tools/gitee_release.py remote   --name pluginplayer
    python tools/gitee_release.py public   --name pluginplayer
    python tools/gitee_release.py release  --name pluginplayer --tag v1.0.0 \
                                           --title "PluginPlayer v1.0.0" --notes-file notes.md
    python tools/gitee_release.py attach   --name pluginplayer --tag v1.0.0 --file dist.zip
    python tools/gitee_release.py status   --name pluginplayer

令牌来源（**绝不要写进仓库**）：
    1. --token HEX
    2. 环境变量 GITEE_TOKEN
    3. --token-file 指定的文件（从中提取第一段 32/64 位 hex）

【发布流程见 DEPLOY.md「发布流程（Gitee）」；下面是踩过的平台坑，别再踩一遍】
  · Gitee 单附件上限 **100MB**（社区版），仓库总附件 ≤ 1GB。
    发布载荷解压后 127MB，但压成 zip 只有 47.9MB（2.65x）—— 所以发**一个 zip**，
    而不是 17 个散文件（散文件还会丢目录结构：附件名不允许带路径分隔符）。
  · `PATCH /repos/{owner}/{repo}` **必须带 `name` 字段**，
    否则 400 `{"messages": ["name is missing"]}`（转公开时会撞上）。
  · `GET /releases/tags/{tag}` 在 tag 不存在时返回 **200 + null**，不是 404 ——
    只判状态码会走进"已存在"分支然后对 None 取属性。
  · 建仓用 `auto_init: false`：否则会多一个无关的首次提交，且默认分支不再是你要推的那个。
  · **`--repo` 的默认值是 cwd，不是本工具所在仓根**（2026-10-06 改）：此前默认取
    工具自身仓根，导致「未带 `--repo` 跑 `remote`」会把 /allin 的 origin 改写掉。
    现在有本地副作用的子命令（remote/release/attach/upload）**必须**能解析出 git 工作树，
    否则退出码 2；`selfcheck` 子命令断言这套解析的取值与两个方向。
  · **`--repo` 的默认值是 cwd，不是本工具所在仓根**（2026-10-06 改）：此前默认取
    工具自身仓根，导致「未带 `--repo` 跑 `remote`」会把 /allin 的 origin 改写掉。
    现在有本地副作用的子命令（remote/release/attach/upload）**必须**能解析出 git 工作树，
    否则退出码 2；`selfcheck` 子命令断言这套解析的取值与两个方向。
  · 响应的 `html_url` 可能为 null；发行版网页地址按
    `https://gitee.com/{owner}/{repo}/releases/{tag}` 构造。
  · 发布页上 Gitee 自动附的源码包链接（`/archive/refs/tags/*.zip`）**不是直链**：
    匿名 HTTP 客户端拿到的是 HTML 页面。GPL 义务要求的源码指向应当写 `git clone` 地址。

退出码: 0 成功；1 失败
"""

import argparse
import glob
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

API = "https://gitee.com/api/v5"
MAX_ATTACH_MB = 100.0        # Gitee 社区版单附件上限（见文件头）


def load_token(arg=None, token_file=None):
    if arg and arg.strip():
        return arg.strip()
    env = os.environ.get("GITEE_TOKEN", "").strip()
    if env:
        return env
    if token_file:
        try:
            txt = open(token_file, encoding="utf-8", errors="replace").read()
        except OSError as e:
            raise SystemExit("[ERR] 读不到令牌文件 %s (%s)" % (token_file, e))
        for tok in re.findall(r"[0-9a-f]{32,64}", txt):
            return tok
        raise SystemExit("[ERR] %s 里没有 32/64 位 hex 令牌" % token_file)
    raise SystemExit("[ERR] 没给令牌。用 --token / --token-file，或设环境变量 GITEE_TOKEN。")


def api(method, path, token, data=None, timeout=60, retries=2):
    """JSON 请求。返回 (status, parsed_or_text)。网络抖动重试两次。"""
    url = API + path
    if "access_token=" not in url:
        url += ("&" if "?" in url else "?") + "access_token=" + token
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json;charset=UTF-8")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                try:
                    return r.status, json.loads(raw)
                except ValueError:
                    return r.status, raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    return -1, str(last)


def upload_file(path, token, filepath, timeout=1800):
    """流式 multipart 上传（不把上百 MB 的附件读进内存）。"""
    name = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    boundary = "----pp" + uuid.uuid4().hex
    pre = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
           "Content-Type: application/octet-stream\r\n\r\n" % (boundary, name)).encode("utf-8")
    post = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    conn = http.client.HTTPSConnection("gitee.com", timeout=timeout)
    conn.putrequest("POST", path)
    conn.putheader("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    conn.putheader("Content-Length", str(len(pre) + size + len(post)))
    conn.putheader("Authorization", "token " + token)
    conn.endheaders()
    conn.send(pre)
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            conn.send(chunk)
    conn.send(post)
    resp = conn.getresponse()
    return resp.status, resp.read().decode("utf-8", "replace")


# 本工具自身所在的仓根。**曾经**它是 `--repo` 的默认值 —— 2026-10-06 的事故根因：
# 未带 `--repo` 执行 `remote` 时，它把 /allin 的 origin 改写成了目标仓。
TOOL_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 会在目标仓里跑 git 命令的子命令（有本地副作用）：必须能解析出一个**真工作树**
GIT_SIDE_EFFECT_CMDS = ("remote", "release", "attach", "upload")


def resolve_repo(args):
    """把 `--repo` 解析成实际目标仓；有副作用的子命令**必须在 git 工作树里**。

    - 不给 `--repo` -> 取 **cwd**（不再取工具自身仓根，见文件头事故记）；
    - 给了 `--repo` -> 用它，并归一化到工作树根（`git rev-parse --show-toplevel`）；
    - 有副作用的子命令解析不到工作树 -> **退出码 2 + 说明**，绝不静默猜一个目录。

    调试铁律 41：拿到坏输入必须响亮失败，不许"打印提示就返回 0"。
    """
    raw = (args.repo or "").strip()
    explicit = bool(raw)
    repo = os.path.abspath(raw) if explicit else os.getcwd()
    if args.cmd in GIT_SIDE_EFFECT_CMDS:
        if not os.path.isdir(repo):
            print("[FAIL] --repo 不是目录: %s" % repo)
            sys.exit(2)
        probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if probe.returncode != 0:
            print("[FAIL] 目标不是 git 工作树: %s" % repo)
            print("       `%s` 会在目标仓里执行 git 操作，拒绝在非仓目录上猜。" % args.cmd)
            print("       用法：cd <目标仓> 后执行，或显式 --repo <目标仓路径>")
            sys.exit(2)
        top = probe.stdout.decode("utf-8", "replace").strip()
        if not explicit:
            print("[INFO] 未给 --repo，按 cwd 解析目标仓: %s" % top)
        args.repo = top or repo
    else:
        args.repo = repo
    return args.repo


def cmd_selfcheck(args, token):
    """自检：断言"目标仓解析"的**具体取值**与**两个方向**（离线、不需要令牌）。

    调试铁律 61：自检必须断言分类/字段值，且每个方向各一条用例；只断言"有输出"抓不出判反。
    """
    import contextlib
    import io
    import shutil
    import tempfile

    class _A:
        def __init__(self, cmd, repo):
            self.cmd, self.repo = cmd, repo

    fails = []

    def check(name, cond, detail=""):
        print("  %s %s%s" % ("ok  " if cond else "FAIL", name,
                             "" if cond else "  <- " + detail))
        if not cond:
            fails.append(name)

    root = tempfile.mkdtemp(prefix="gitee_rel_selfcheck_")
    plain = os.path.join(root, "not_a_repo")
    repo_a, repo_b = os.path.join(root, "repo_a"), os.path.join(root, "repo_b")
    saved = os.getcwd()
    try:
        for d in (plain, repo_a, repo_b):
            os.makedirs(d)
        for d in (repo_a, repo_b):
            subprocess.run(["git", "init", "-q", d], check=True)

        # ① 不给 --repo -> 取 cwd（**尤其是不能取工具自身仓根** = 事故回归用例）
        os.chdir(repo_a)
        with contextlib.redirect_stdout(io.StringIO()):
            got = resolve_repo(_A("remote", ""))
        check("默认取 cwd", os.path.realpath(got) == os.path.realpath(repo_a), got)
        check("默认不再是工具自身仓根（事故回归）",
              os.path.realpath(got) != os.path.realpath(TOOL_REPO_ROOT), got)

        # ② 显式 --repo 胜出（反方向）
        with contextlib.redirect_stdout(io.StringIO()):
            got = resolve_repo(_A("remote", repo_b))
        check("显式 --repo 胜出", os.path.realpath(got) == os.path.realpath(repo_b), got)

        # ③ 有副作用的子命令在非仓目录 -> 退出码 2（响亮失败）
        os.chdir(plain)
        code = None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                resolve_repo(_A("remote", ""))
        except SystemExit as e:
            code = e.code
        check("非仓目录 + 有副作用 -> exit 2", code == 2, repr(code))

        # ④ 无副作用的子命令在非仓目录 -> 正常工作（另一方向，别把门关死）
        with contextlib.redirect_stdout(io.StringIO()):
            got = resolve_repo(_A("create", ""))
        check("纯 API 子命令不要求工作树",
              os.path.realpath(got) == os.path.realpath(plain), got)

        # ⑤ argparse 这一层：默认值必须是哨兵，**不能**是工具自身仓根
        #    （上面用的是伪 args，测不到 argparse；这一条才真正覆盖事故回归）
        parser = build_parser()
        parsed = parser.parse_args(["remote"])
        check("argparse 默认值是哨兵（不是工具自身仓根）",
              parsed.repo == "" and os.path.abspath(parsed.repo or os.getcwd())
              != os.path.realpath(TOOL_REPO_ROOT), repr(parsed.repo))
        os.chdir(repo_a)
        with contextlib.redirect_stdout(io.StringIO()):
            got = resolve_repo(parser.parse_args(["remote"]))
        check("真 parser + 无 --repo -> cwd",
              os.path.realpath(got) == os.path.realpath(repo_a), got)

        # ⑥ 子目录也要归一化到工作树根（否则 git -C 子目录会另建 tag/远端）
        sub = os.path.join(repo_a, "sub", "deep")
        os.makedirs(sub)
        os.chdir(sub)
        with contextlib.redirect_stdout(io.StringIO()):
            got = resolve_repo(_A("release", ""))
        check("子目录归一化到工作树根",
              os.path.realpath(got) == os.path.realpath(repo_a), got)
    finally:
        os.chdir(saved)
        shutil.rmtree(root, ignore_errors=True)

    total = 8
    print("SELFCHECK_%s (%d/%d)" % ("PASSED" if not fails else "FAILED",
                                    total - len(fails), total))
    return 0 if not fails else 1


# 本工具自身所在的仓根。**曾经**它是 `--repo` 的默认值 —— 2026-10-06 的事故根因：
# 未带 `--repo` 执行 `remote` 时，它把 /allin 的 origin 改写成了目标仓。
def repo_path(args):
    return "/repos/%s/%s" % (args.owner, args.name)


def get_release(args, token, tag):
    st, d = api("GET", "%s/releases/tags/%s" % (repo_path(args), tag), token)
    if st == 200 and isinstance(d, dict) and d.get("id"):
        return d
    return None


# ============================================================================
# 子命令
# ============================================================================

def cmd_whoami(args, token):
    st, d = api("GET", "/user", token)
    if st != 200:
        print("[FAIL] 令牌不可用: %s %s" % (st, str(d)[:200]))
        return 1
    print("[OK] login=%s name=%s id=%s" % (d.get("login"), d.get("name"), d.get("id")))
    return 0


def derive_desc_from_readme(repo):
    """从本地 README.md 首行标题（# ...）取仓库描述；无标题则取首行非空文本；都没有返回 ''。

    用于建仓时自动按 README 填描述，避免错贴别的仓（如早先 --desc 硬编码成
    PluginPlayer 描述，导致 d20-table-link 等被错贴）的描述。
    """
    for base in (repo, os.getcwd()):
        p = os.path.join(base, "README.md")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    if s.startswith("# "):
                        return s[2:].strip()
                    return s
        except OSError:
            continue
    return ""


def cmd_create(args, token):
    st, d = api("GET", repo_path(args), token)
    if st == 200:
        print("[SKIP] 仓库已存在: %s (private=%s default_branch=%s)"
              % (d.get("full_name"), d.get("private"), d.get("default_branch")))
        return 0
    # 描述：显式 --desc 优先；否则从本地 README.md 首行标题自动取，避免错贴别的仓描述
    desc = (args.desc or "").strip()
    if not desc:
        desc = derive_desc_from_readme(args.repo)
        if desc:
            print("[INFO] 未传 --desc，从 %s/README.md 首行标题取描述: %s"
                  % (args.repo, desc))
    payload = {
        "name": args.name,
        "private": True,          # 先私有：推完再转公开，避免半成品被看到
        "auto_init": False,       # 不自动建 README（会多一个无关提交）
        "has_issues": True,
        "has_wiki": False,
        "can_comment": True,
    }
    if desc:
        payload["description"] = desc
    st, d = api("POST", "/user/repos", token, payload)
    if st in (200, 201):
        print("[OK] 已创建私有仓库: %s (id=%s)" % (d.get("full_name"), d.get("id")))
        return 0
    print("[FAIL] 建仓失败: %s %s" % (st, str(d)[:300]))
    return 1


def cmd_remote(args, token):
    url = "https://gitee.com/%s/%s.git" % (args.owner, args.name)
    names = subprocess.run(["git", "remote"], cwd=args.repo,
                           stdout=subprocess.PIPE).stdout.decode().split()
    if "origin" in names:
        subprocess.run(["git", "remote", "set-url", "origin", url], cwd=args.repo, check=True)
        print("[OK] origin 已更新: %s" % url)
    else:
        subprocess.run(["git", "remote", "add", "origin", url], cwd=args.repo, check=True)
        print("[OK] 已添加 origin: %s" % url)
    return 0


def cmd_public(args, token):
    st, d = api("GET", repo_path(args), token)
    if st != 200:
        print("[FAIL] 读仓库失败: %s %s" % (st, str(d)[:200]))
        return 1
    if not d.get("private"):
        print("[SKIP] 已经是公开仓库")
        return 0
    # 必须带 name —— 见文件头的平台坑说明
    st, d = api("PATCH", repo_path(args), token, {"name": args.name, "private": False})
    if st == 200:
        print("[OK] 已转为公开: https://gitee.com/%s/%s" % (args.owner, args.name))
        return 0
    print("[FAIL] 转公开失败: %s %s" % (st, str(d)[:300]))
    return 1


def cmd_release(args, token):
    tag = args.tag
    have = subprocess.run(["git", "tag", "-l", tag], cwd=args.repo,
                          stdout=subprocess.PIPE).stdout.decode().strip()
    if not have:
        subprocess.run(["git", "tag", "-a", tag, "-m", args.title], cwd=args.repo, check=True)
        print("[OK] 已创建标签 %s" % tag)
    else:
        print("[SKIP] 本地已有标签 %s" % tag)
    # -f：允许把 tag 前移到"全量回归通过的那个提交"
    rc = subprocess.run(["git", "push", "-f", "origin", tag], cwd=args.repo,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        print("[FAIL] 推送标签失败（先 git remote 配好、并能免密推送）")
        return 1
    print("[OK] 标签已推送")

    if get_release(args, token, tag):
        print("[SKIP] 发行版已存在: %s" % release_url(args, tag))
        return 0
    body = open(args.notes_file, encoding="utf-8").read() if args.notes_file else ""
    data = {"tag_name": tag, "name": args.title, "body": body, "prerelease": args.pre}
    # ⚠⚠ Gitee 的 POST /releases **必须**带 `target_commitish`，否则直接
    #   400 {"messages": ["target_commitish is missing"]}（2026-09-22 实测撞到）。
    #   原实现只在显式传 --branch 时才带上它 -> **不传必失败**。
    #   改成：没传就自动探测仓库当前分支，保证默认路径也能成功。
    branch = args.branch
    if not branch:
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=(getattr(args, "repo", None) or os.getcwd()),
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True).stdout.strip()
    data["target_commitish"] = branch or "master"
    st, d = api("POST", "%s/releases" % repo_path(args), token, data, timeout=120)
    if st in (200, 201):
        print("[OK] 发行版已创建: %s (id=%s)" % (release_url(args, tag), d.get("id")))
        return 0
    print("[FAIL] 建发行版失败: %s %s" % (st, str(d)[:300]))
    return 1


def release_url(args, tag):
    return "https://gitee.com/%s/%s/releases/%s" % (args.owner, args.name, tag)


def upload_attachments(args, token, files):
    rel = get_release(args, token, args.tag)
    if not rel:
        print("[FAIL] 找不到发行版 %s（先跑 release 子命令）" % args.tag)
        return 1
    existing = {a.get("name") for a in (rel.get("assets") or [])}
    fail = []
    for i, path in enumerate(files, 1):
        if not os.path.isfile(path):
            print("[%d/%d] [FAIL] 文件不存在: %s" % (i, len(files), path))
            fail.append((os.path.basename(path), "文件不存在"))
            continue
        name = os.path.basename(path)
        mb = os.path.getsize(path) / 1048576.0
        if name in existing:
            print("[%d/%d] [SKIP] %-36s 已存在" % (i, len(files), name))
            continue
        if mb > MAX_ATTACH_MB:
            print("[%d/%d] [SKIP] %-36s %.1f MB 超过 %.0fMB 上限"
                  % (i, len(files), name, mb, MAX_ATTACH_MB))
            fail.append((name, "超过 %.0fMB" % MAX_ATTACH_MB))
            continue
        # ⚠⚠ 路径必须带 `/api/v5` 前缀：`api()` 内部会自动补，但 `upload_file` 是**直连**
        #    （HTTPSConnection("gitee.com") + 原样 path）—— 少了前缀就是 404。
        #    2026-09-22 实测踩到：4 个附件全部返回 `你所访问的页面不存在 (404)` 的 HTML 页，
        #    而同一路径手工带上 /api/v5 后立刻 201。这个坑不报错、只静默失败，非常阴。
        _api_path = API[len("https://gitee.com"):]          # "/api/v5"
        url = "%s%s/releases/%s/attach_files?access_token=%s" % (
            _api_path, repo_path(args), rel["id"], token)
        t0 = time.time()
        try:
            st, txt = upload_file(url, token, path)
        except Exception as e:                        # noqa: BLE001
            st, txt = -1, "%s: %s" % (type(e).__name__, e)
        ok = st in (200, 201)
        print("[%d/%d] [%s] %-36s %6.1f MB %6.1fs %s"
              % (i, len(files), "OK" if ok else "FAIL", name, mb, time.time() - t0,
                 "" if ok else str(txt)[:180]))
        if not ok:
            fail.append((name, str(txt)[:180]))
    if fail:
        print("\n[FAIL] %d 个附件失败: %s" % (len(fail), fail))
        return 1
    print("\n[PASS] 附件上传完成")
    return 0


def cmd_attach(args, token):
    return upload_attachments(args, token, args.file)


def cmd_upload(args, token):
    """按 build.py --release 的口径挑出发布载荷，逐个上传（小文件场景用）。

    大文件多的时候更推荐先压成一个 zip 再 attach —— 见文件头。
    载荷口径直接复用 gen_third_party_notices.dist_payload()，不在这里再写一份，
    否则"哪些文件算发布载荷"会有两个真相。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import gen_third_party_notices as notices
    except ImportError as exc:
        print("[FAIL] 无法 import gen_third_party_notices: %s" % exc)
        return 1
    d = args.dir or os.path.join(args.repo, "dist")
    payload = notices.dist_payload(dist=d)
    if payload is None:
        print("[FAIL] %s 不存在（先 build.py --release）" % d)
        return 1
    files = [os.path.join(d, r.replace("/", os.sep)) for r, _s in payload]
    print("[INFO] 待上传 %d 个文件（口径同 build.py --release）" % len(files))
    return upload_attachments(args, token, files)


def cmd_status(args, token):
    st, d = api("GET", repo_path(args), token)
    if st != 200:
        print("[FAIL] 读仓库失败: %s %s" % (st, str(d)[:200]))
        return 1
    print("仓库: %s  private=%s  default_branch=%s"
          % (d.get("full_name"), d.get("private"), d.get("default_branch")))
    print("      https://gitee.com/%s/%s" % (args.owner, args.name))
    st, rels = api("GET", "%s/releases" % repo_path(args), token)
    if st == 200 and isinstance(rels, list):
        print("发行版 %d 个:" % len(rels))
        for r in rels[:10]:
            assets = r.get("assets") or []
            print("   %-10s %-38s 附件 %d 个  %s"
                  % (r.get("tag_name"), (r.get("name") or "")[:38], len(assets),
                     release_url(args, r.get("tag_name"))))
    return 0


def build_parser():
    """构造参数解析器（抽成函数：自检必须能拿到**真 parser**）。

    2026-10-06 自证教训：自检原先构造伪 args 直接调 `resolve_repo()`，**绕过了 argparse 默认值**，
    于是"把 `--repo` 默认值改回工具自身仓根"这个**正是事故本身的回归**竟然测不出来。
    调试铁律 61：自检要断言真实取值；61/65 合起来的结论是——**测不到默认值就等于没测**。
    """
    ap = argparse.ArgumentParser(description="Gitee 建仓 / 转公开 / 发布发行版")
    ap.add_argument("--owner", default="siwpan")
    ap.add_argument("--name", default="pluginplayer")
    # default 必须是空串哨兵：要能区分"没给"（-> cwd）与"显式给了"（-> 归一化并提示）
    ap.add_argument("--repo", default="",
                    help="目标仓路径；留空 = 当前工作目录（cwd）")
    ap.add_argument("--desc", default="",
                    help="仓库描述；留空则自动从 --repo（或 cwd）下 README.md 首行标题取")
    ap.add_argument("--token", default="")
    ap.add_argument("--token-file", default="")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("whoami", "create", "remote", "public", "status", "selfcheck"):
        sub.add_parser(n)
    s = sub.add_parser("release")
    s.add_argument("--tag", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--notes-file", default="")
    s.add_argument("--branch", default="", help="留空则由 Gitee 从 tag 推断")
    s.add_argument("--pre", action="store_true", help="标为预览版")
    s = sub.add_parser("attach")
    s.add_argument("--tag", required=True)
    s.add_argument("--file", action="append", default=[])
    s = sub.add_parser("upload")
    s.add_argument("--tag", required=True)
    s.add_argument("--dir", default="")
    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()

    if args.cmd == "selfcheck":                  # 自检是离线的，先于取令牌
        return cmd_selfcheck(args, "")
    token = load_token(args.token, args.token_file)
    resolve_repo(args)                           # 解析并（有副作用时）校验目标仓
    fn = {"whoami": cmd_whoami, "create": cmd_create, "remote": cmd_remote,
          "public": cmd_public, "release": cmd_release, "attach": cmd_attach,
          "upload": cmd_upload, "status": cmd_status}[args.cmd]
    return fn(args, token)


if __name__ == "__main__":
    sys.exit(main())
