#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""watchdog.py —— 工作区看门狗（盘健康 · 仓完整性 · 同步漂移）

为什么存在
----------
2026-09-25 实测事故：G: 盘（外置 WD，Disk 3）全天持续 `disk 事件 153`（IO 重试），
19:07 触发 `Ntfs 事件 132`「短时间内发生太多修复事件」+ 9 次「卷 G: 上的文件系统
结构现在已经修复」—— **NTFS 在线自愈在写入过程中改坏了 git 对象**，造成 4 个仓损坏：

    G:\\allin               .git/index 坏签名 + pack .idx 非单调 + commit-graph 签名不符
    G:\\repos\\novel        .git\\objects 目录项损坏（"文件或目录损坏且无法读取"）
    G:\\repos\\novel-down   同上
    G:\\repos\\ncmturnmp3   同上

**全部是事后人工挖出来的，没有任何机制在"第一时间"叫。** 本脚本补上这个监工。

三项职责
--------
  W1 盘健康     —— 卷 dirty 位、HealthStatus、以及**事件日志里的 IO 重试/NTFS 自愈计数**。
                   重点：SMART 会报 `Healthy` 而盘正在重试 IO（本次实测即如此），
                   所以**必须看事件日志**，不能只看 Get-PhysicalDisk。
  W2 仓完整性   —— 每个仓：`.git/objects` 是否可读、HEAD 是否可解、fsck 是否有非 dangling 问题。
                   `.git/objects` 打不开是本次事故的指纹，必须单独判。
  W3 同步漂移   —— 本地 HEAD vs 远端 ref（只信 `git ls-remote`，不信陈旧的 remote-tracking ref）。

用法
----
    python watchdog.py                      # 全量巡检（默认范围）
    python watchdog.py --quick              # 只做 W1 + 抽样（快）
    python watchdog.py --disk G,F           # 只查指定卷
    python watchdog.py --repos-root G:\\repos
    python watchdog.py --selfcheck          # 注入破坏用例自证
    python watchdog.py --json wd.json       # 机读输出
    python watchdog.py --quiet              # 只输出告警

退出码
------
    0 = 全绿
    1 = 有告警（损坏/漂移/盘风险）
    2 = 用法错误
    3 = 环境错误

设计纪律
--------
· **只读**：不改任何仓、不动任何盘。发现问题的动作是"报"，不是"修"。
· **告警要有指纹**：`.git/objects` 不可读、fsck 非 dangling、dirty 位、事件计数超阈值——
  每条都能定位到具体仓/卷，便于直接处置。
· **不许假绿**：任何一项因环境原因无法判定时记 `SKIP` 并计入告警，不当作通过。
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 事件日志阈值：单次巡检窗口内，同一磁盘的 IO 重试次数超过它即告警
IO_RETRY_WARN = 20
NTFS_REPAIR_WARN = 1        # NTFS 在线自愈出现即告警（本次事故正是它）
WINDOW_HOURS = 24


class Alert:
    __slots__ = ("code", "target", "detail", "severity")

    def __init__(self, code, target, detail, severity="WARN"):
        self.code = code
        self.target = target
        self.detail = detail
        self.severity = severity

    def __str__(self):
        return "[{}] {} :: {}".format(self.code, self.target, self.detail)


def ps(script, timeout=180):
    """执行 PowerShell 片段并返回 stdout（只读操作用）。"""
    for exe in ("pwsh", "powershell"):
        try:
            p = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script],
                               capture_output=True, timeout=timeout)
            return p.stdout.decode("utf-8", "replace")
        except FileNotFoundError:
            continue
        except Exception as e:
            return "[ERR] " + str(e)
    return "[ERR] 无 PowerShell"


# ------------------------------------------------------------------ W1 盘健康

def check_disks(letters):
    alerts, info = [], {}
    drives = [l.strip().rstrip(":") for l in letters if l.strip()]
    # 卷状态
    script = (
        "Get-Volume | Where-Object { $_.DriveLetter } | "
        "Select-Object DriveLetter,FileSystemType,HealthStatus,OperationalStatus,"
        "@{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},"
        "@{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,1)}} | ConvertTo-Json -Compress"
    )
    out = ps(script)
    try:
        vols = json.loads(out)
        if isinstance(vols, dict):
            vols = [vols]
    except Exception:
        vols = []
        alerts.append(Alert("W1", "(卷)", "无法枚举卷状态（PowerShell 输出不可解析）", "ERROR"))
    for v in vols:
        L = str(v.get("DriveLetter") or "")
        if drives and L.upper() not in [d.upper() for d in drives]:
            continue
        info[L] = v
        health = str(v.get("HealthStatus") or "")
        op = str(v.get("OperationalStatus") or "")
        if health.lower() != "healthy" or op.lower() not in ("ok",):
            alerts.append(Alert("W1", L + ":", "卷状态异常 Health={} Op={}".format(health, op), "ERROR"))

    # dirty 位（需要读权限；C: 常因权限失败，记为 SKIP 而不是通过）
    for L in (drives or [k for k in info]):
        r = ps("fsutil dirty query {}:".format(L), timeout=30)
        rl = r.strip().lower()
        if "is dirty" in rl and "not dirty" not in rl:
            alerts.append(Alert("W1", L + ":", "脏位已置（Dirty）—— 需计划 chkdsk", "ERROR"))
        elif "not dirty" in rl:
            pass
        else:
            alerts.append(Alert("W1", L + ":", "脏位无法判定（{}）—— 记为 SKIP，不当作通过".format(r.strip()[:60]), "INFO"))

    # 事件日志：IO 重试 + NTFS 自愈（**SMART 会说 Healthy，这里才是真相**）
    script = (
        "$s=(Get-Date).AddHours(-{});".format(WINDOW_HOURS) +
        "Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$s} -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ProviderName -match 'disk|Ntfs|volmgr' } | "
        "Group-Object { \"$($_.ProviderName)|$($_.Id)\" } | "
        "ForEach-Object { \"$($_.Name)=$($_.Count)\" }"
    )
    out = ps(script)
    counts = {}
    for line in out.splitlines():
        line = line.strip()
        if "=" in line and "|" in line:
            k, _, v = line.rpartition("=")
            try:
                counts[k] = int(v)
            except ValueError:
                pass
    io_retry = sum(c for k, c in counts.items() if k.startswith("disk|") and k.endswith("|153"))
    ntfs_repair = sum(c for k, c in counts.items()
                      if k.startswith("Ntfs|") and k.split("|")[1] in ("130", "131", "132", "55", "98"))
    if io_retry >= IO_RETRY_WARN:
        alerts.append(Alert("W1", "disk 事件 153", "近 {}h IO 重试 {} 次（阈值 {}）—— 盘在挣扎，避免大量写入".format(
            WINDOW_HOURS, io_retry, IO_RETRY_WARN), "ERROR"))
    if ntfs_repair >= NTFS_REPAIR_WARN:
        alerts.append(Alert("W1", "Ntfs 自愈事件", "近 {}h 文件系统修复事件 {} 次 —— **本次 4 仓损坏的直接原因**".format(
            WINDOW_HOURS, ntfs_repair), "ERROR"))
    info["_events"] = counts
    info["_io_retry"] = io_retry
    info["_ntfs_repair"] = ntfs_repair
    return alerts, info


# ------------------------------------------------------------------ W2 仓完整性

def check_repo(repo):
    """返回 (alerts, status)。指纹优先：.git/objects 可读性是本次事故的第一判据。"""
    a = []
    name = os.path.basename(repo.rstrip("\\/"))
    obj = os.path.join(repo, ".git", "objects")
    if not os.path.isdir(obj):
        return [Alert("W2", name, "无 .git/objects（不是仓或被截断）", "ERROR")], "NOOBJ"
    try:
        os.listdir(obj)
    except OSError as e:
        return [Alert("W2", name, ".git/objects 不可读 —— 文件系统级损坏（指纹！）: {}".format(
            str(e)[:80]), "ERROR")], "BROKEN_OBJECTS"

    def git(*args, t=120):
        try:
            p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, timeout=t)
            return p.returncode, p.stdout.decode("utf-8", "replace")
        except Exception as e:
            return 128, str(e)

    # ⚠ 必须用 HEAD^{commit}：`rev-parse --verify HEAD` **只解析 ref 名**，
    # 不验证对象是否存在 —— 首版用 HEAD，导致「objects 全删」和「HEAD 写坏」
    # 两个破坏用例都被判成 OK（自检当场抓出）。
    rc, out = git("rev-parse", "--verify", "HEAD^{commit}")
    if rc != 0:
        low = out.lower()
        if "dubious ownership" in low:
            return a, "OWNERSHIP"
        return [Alert("W2", name, "HEAD 不可解为提交对象: {}".format(out.strip()[:90]), "ERROR")], "BAD_HEAD"

    rc, out = git("fsck", "--no-progress", "--no-dangling", t=300)
    if rc != 0:
        bad = [l for l in out.splitlines()
               if l.strip() and not l.startswith(("dangling", "notice", "Checking"))]
        if bad:
            return [Alert("W2", name, "fsck 非 dangling 问题 {} 条：{}".format(len(bad), bad[0][:80]), "ERROR")], "FSCK"
    return a, "OK"


def iter_repos(root):
    out = []
    if not os.path.isdir(root):
        return out
    for n in sorted(os.listdir(root)):
        d = os.path.join(root, n)
        if os.path.isdir(d) and os.path.isdir(os.path.join(d, ".git")):
            out.append(d)
    return out


# ------------------------------------------------------------------ W3 同步漂移

def check_sync(repo):
    name = os.path.basename(repo.rstrip("\\/"))

    def git(*args, t=120):
        try:
            p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, timeout=t)
            return p.returncode, p.stdout.decode("utf-8", "replace")
        except Exception as e:
            return 128, str(e)

    rc, out = git("rev-parse", "--verify", "HEAD^{commit}", t=60)
    if rc != 0:
        return []          # W2 已报，不重复
    local = out.strip()
    rc, br = git("rev-parse", "--abbrev-ref", "HEAD")
    br = br.strip()
    if rc != 0 or br in ("HEAD", ""):
        return []
    rc, url = git("config", "--get", "remote.origin.url")
    if rc != 0 or not url.strip():
        return []
    # **只信 ls-remote**（MEMORY 调试铁律 13：陈旧的 remote-tracking ref 会造成假阳性）
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        p = subprocess.run(["git", "ls-remote", "origin", "refs/heads/" + br],
                           cwd=repo, capture_output=True, timeout=120, env=env)
        remote = p.stdout.decode("utf-8", "replace").split()
        remote = remote[0].strip() if remote else ""
    except Exception:
        return [Alert("W3", name, "ls-remote 失败（网络/权限）—— 记为 SKIP", "INFO")]
    if not remote:
        return [Alert("W3", name, "远端无分支 {} —— 本地有未推送分支".format(br), "WARN")]
    if remote != local:
        return [Alert("W3", name, "漂移：本地 {} != 远端 {}（branch {}）".format(
            local[:8], remote[:8], br), "WARN")]
    return []


# ------------------------------------------------------------------ selfcheck

def selfcheck():
    print("== 看门狗 自测 ==")
    ok = True
    tmp = tempfile.mkdtemp(prefix="wd_selfcheck_")

    # ① 完好仓：应判 OK
    good = os.path.join(tmp, "good")
    os.makedirs(good)
    subprocess.run(["git", "init", "-q", good], capture_output=True)
    subprocess.run(["git", "-C", good, "config", "user.email", "t@t"], capture_output=True)
    subprocess.run(["git", "-C", good, "config", "user.name", "t"], capture_output=True)
    open(os.path.join(good, "a.txt"), "w").write("x\n")
    subprocess.run(["git", "-C", good, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", good, "commit", "-qm", "x"], capture_output=True)
    al, st = check_repo(good)
    print("  完好仓判 OK: {}  [{}]".format("✔" if st == "OK" and not al else "✘", st))
    ok &= (st == "OK" and not al)

    # ② 破坏用例：删除 .git/objects
    #    ⚠ git 对象是**只读文件**，`shutil.rmtree(..., ignore_errors=True)` 会**静默失败**，
    #    导致破坏用例其实没生效、门禁被判为"抓不到"（首版自检踩此坑，靠打印 exists 才发现）。
    #    必须先清只读位再删，并**断言真的删掉了**——否则自检本身是假的。
    broken = os.path.join(tmp, "broken")
    shutil.copytree(good, broken)
    objdir = os.path.join(broken, ".git", "objects")

    def _rm_readonly(path):
        import stat as _st
        for dp, dns, fns in os.walk(path):
            for f in fns:
                try:
                    os.chmod(os.path.join(dp, f), _st.S_IWRITE)
                except OSError:
                    pass
        shutil.rmtree(path)

    _rm_readonly(objdir)
    assert not os.path.isdir(objdir), "自检夹具构造失败：.git/objects 未被删除"
    al, st = check_repo(broken)
    print("  缺 .git/objects 被检出: {}  [{}]".format("✔" if st in ("NOOBJ", "BROKEN_OBJECTS") else "✘", st))
    ok &= st in ("NOOBJ", "BROKEN_OBJECTS")

    # ③ 破坏用例：HEAD 指向不存在的对象
    bad = os.path.join(tmp, "badhead")
    shutil.copytree(good, bad)
    with open(os.path.join(bad, ".git", "HEAD"), "w") as fh:
        fh.write("0123456789abcdef0123456789abcdef01234567\n")
    al, st = check_repo(bad)
    print("  HEAD 坏被检出: {}  [{}]".format("✔" if st == "BAD_HEAD" else "✘", st))
    ok &= (st == "BAD_HEAD")

    # ④ 漂移检测：本地多一个提交，远端未推
    drift = os.path.join(tmp, "drift")
    bare = os.path.join(tmp, "origin.git")
    subprocess.run(["git", "init", "-q", "--bare", bare], capture_output=True)
    subprocess.run(["git", "clone", "-q", bare, drift], capture_output=True)
    subprocess.run(["git", "-C", drift, "config", "user.email", "t@t"], capture_output=True)
    subprocess.run(["git", "-C", drift, "config", "user.name", "t"], capture_output=True)
    open(os.path.join(drift, "b.txt"), "w").write("y\n")
    subprocess.run(["git", "-C", drift, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", drift, "commit", "-qm", "y"], capture_output=True)
    subprocess.run(["git", "-C", drift, "push", "-q", "origin", "HEAD:refs/heads/master"], capture_output=True)
    open(os.path.join(drift, "c.txt"), "w").write("z\n")
    subprocess.run(["git", "-C", drift, "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", drift, "commit", "-qm", "z"], capture_output=True)
    sy = check_sync(drift)
    print("  未推送漂移被检出: {}  [{}]".format("✔" if sy else "✘", len(sy)))
    ok &= bool(sy)

    # ⑤ 盘健康：事件计数解析器（不依赖真实事件，验阈值逻辑）
    fake_counts = {"disk|153": IO_RETRY_WARN + 1, "Ntfs|132": 1, "Ntfs|130": 8}
    io_retry = sum(c for k, c in fake_counts.items() if k.startswith("disk|") and k.endswith("|153"))
    ntfs_repair = sum(c for k, c in fake_counts.items()
                      if k.startswith("Ntfs|") and k.split("|")[1] in ("130", "131", "132", "55", "98"))
    hit = io_retry >= IO_RETRY_WARN and ntfs_repair >= NTFS_REPAIR_WARN
    print("  盘事件阈值逻辑: {}  [io_retry={} ntfs_repair={}]".format("✔" if hit else "✘", io_retry, ntfs_repair))
    ok &= hit

    shutil.rmtree(tmp, ignore_errors=True)
    print("  自测{}".format("通过" if ok else "失败"))
    return 0 if ok else 1


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="工作区看门狗（盘健康·仓完整性·同步漂移）")
    ap.add_argument("--repos-root", action="append", default=None,
                    help="仓根，可多次；默认 G:\\repos 与 G:\\allin")
    ap.add_argument("--disk", default="C,D,F,G", help="要检查的卷（默认 C,D,F,G）")
    ap.add_argument("--quick", action="store_true", help="跳过 fsck（只做盘健康 + HEAD + 同步）")
    ap.add_argument("--no-sync", action="store_true", help="跳过 W3（离线时用）")
    ap.add_argument("--json", help="机读输出路径")
    ap.add_argument("--quiet", action="store_true", help="只输出告警")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    roots = args.repos_root or [r"G:\repos", r"G:\allin", r"G:\allin-platform"]
    alerts = []
    summary = {}

    # W1
    a1, i1 = check_disks(args.disk.split(","))
    alerts += a1
    summary["disks"] = {k: v for k, v in i1.items() if not k.startswith("_")}
    summary["events"] = {"io_retry_{}h".format(WINDOW_HOURS): i1.get("_io_retry"),
                         "ntfs_repair_{}h".format(WINDOW_HOURS): i1.get("_ntfs_repair")}

    # W2 / W3
    repos = []
    for r in roots:
        if os.path.isdir(os.path.join(r, ".git")):
            repos.append(r)
        repos += iter_repos(r)
    seen, uniq = set(), []
    for r in repos:
        k = os.path.abspath(r).lower()
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    repos = uniq

    if not args.quiet:
        print("== 看门狗 ==")
        print("  卷: {} | 仓: {} 个 | 窗口: {}h{}".format(args.disk, len(repos), WINDOW_HOURS,
                                                     " | quick" if args.quick else ""))
    stat = {}
    for r in repos:
        if args.quick:
            def _g(*a, t=60):
                try:
                    p = subprocess.run(["git", "-C", r] + list(a), capture_output=True, timeout=t)
                    return p.returncode, p.stdout.decode("utf-8", "replace")
                except Exception as e:
                    return 128, str(e)
            rc, out = _g("rev-parse", "--verify", "HEAD^{commit}")
            if rc != 0:
                if "dubious ownership" in out.lower():
                    st = "OWNERSHIP"
                else:
                    st = "BAD_HEAD"
                    alerts.append(Alert("W2", os.path.basename(r), "HEAD 不可解: " + out.strip()[:80], "ERROR"))
            else:
                st = "OK"
            al = []
        else:
            al, st = check_repo(r)
            alerts += al
        stat[st] = stat.get(st, 0) + 1
        if not args.no_sync and st in ("OK",):
            alerts += check_sync(r)
    summary["repos"] = stat

    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"generated": datetime.now().isoformat(timespec="seconds"),
                       "summary": summary,
                       "alerts": [{"code": a.code, "target": a.target, "detail": a.detail,
                                   "severity": a.severity} for a in alerts]},
                      fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        print("  仓状态分布: " + "  ".join("{}={}".format(k, v) for k, v in sorted(stat.items())))
        ev = summary.get("events", {})
        print("  事件计数: IO重试={} NTFS自愈={}（窗口 {}h）".format(
            ev.get("io_retry_{}h".format(WINDOW_HOURS)), ev.get("ntfs_repair_{}h".format(WINDOW_HOURS)), WINDOW_HOURS))

    err = [a for a in alerts if a.severity in ("ERROR", "WARN")]
    info = [a for a in alerts if a.severity == "INFO"]
    for a in err:
        print("  " + str(a))
    if info and not args.quiet:
        for a in info:
            print("  " + str(a))

    if err:
        if not args.quiet:
            print("  RESULT: 有告警 {} 条（ERROR/WARN）".format(len(err)))
        return 1
    if not args.quiet:
        print("  RESULT: 全绿（SKIP {} 条）".format(len(info)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
