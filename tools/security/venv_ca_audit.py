#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""venv CA 证书安全巡检与加固（eMudhra/emSign CA 事件，GHSA-6q48-6c7w-9gw2）。

背景
----
2026-10-20 披露的 **CRITICAL** 事件（CVSS 9.1，CWE-295，无 CVE）：

  · certifi ``>= 2019.03.09, < 2026.10.19`` 的 CA 捆绑包内含 **emSign ECC Root CA - G3** 根证书。
  · eMudhra 签发并链到该根的 **8 张中间 CA 证书私钥已泄露**并被吊销。
  · 持泄露私钥者可签发「对任意主机名都像真的」证书；再叠加 on-path 即可 MITM。
  · 受影响面：``requests`` / ``urllib3`` / ``pip`` 等一切依赖 certifi 信任链的组件。

  修复线：certifi **2026.10.18** 移除全部 emSign 根；**2026.10.19** 只恢复「未受影响」的 emSign 根。
  ⇒ 安全版本 = ``certifi >= 2026.10.19``，且包内**不得再出现 emSign ECC Root CA - G3**。

判定为什么必须精确到 G3
-----------------------
certifi 2026.10.19 的捆绑包里 **仍然有 9 处 "emSign"**（未受影响的那些根，按公告被有意恢复）。
所以「有没有 emSign」是**错的判据**（会误报）；**唯一正确判据**是精确匹配 ``emSign ECC Root CA - G3``。

三个必查面（本工具全查，旧版本漏了第 2 面）
------------------------------------------
1. **独立 certifi 包**：``site-packages/certifi/cacert.pem`` —— 版本 + G3 计数
2. **pip 的 vendored certifi**（公告点名的受影响组件）：``site-packages/pip/_vendor/certifi/cacert.pem``
   —— 旧版本只查第 1 面，而多数 venv 根本没装独立 certifi（``import certifi`` 直接失败），
   于是这一面**从未被真正检查过**（结论侥幸正确，但依据是 pip 版本下限，不是声明的检查项）。
3. **uv**：``uv < 0.13.4`` 的 vendored webpki-root-certs 同含 G3（修复：uv 0.13.4 / webpki-roots 1.0.10）

安全基线
--------
  certifi >= 2026.10.19 ；pip >= 26.2.2 ；uv >= 0.13.4（已安装才检查）

用法
----
  python venv_ca_audit.py scan   [root] [jobs]   # 只读扫描
  python venv_ca_audit.py apply  [root] [jobs]   # 加固（幂等）
  python venv_ca_audit.py verify [root] [jobs]   # 功能级审计（实跑解释器）

home 映射（本机可用基准解释器，按 venv 的 major.minor 匹配）::

  3.14.x -> G:\\Python314
  3.13.x -> C:\\Users\\psw\\.workbuddy\\binaries\\python\\versions\\3.13.12
  3.12.x -> C:\\Users\\psw\\AppData\\Roaming\\uv\\python\\cpython-3.12.14-windows-x86_64-none

纪律：纯标准库；只读 site-packages 元数据（不启动解释器）用于 scan；
verify 才会实跑解释器做功能级确认；**不删除任何文件**（损坏的 pip 仅改名加 .bak 备份）。
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

DEFAULT_ROOT = r"G:\repos"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "htmlcov", "build", "dist", ".idea", ".vscode"}
FLOORS = {"certifi": (2026, 10, 19), "pip": (26, 2, 2), "uv": (0, 13, 4)}
G3 = "emSign ECC Root CA - G3"
BASE_MAP = {
    (3, 14): r"G:\Python314",
    (3, 13): r"C:\Users\psw\.workbuddy\binaries\python\versions\3.13.12",
    (3, 12): r"C:\Users\psw\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none",
}


# ----------------------------------------------------------------- 基础工具

def ver_tuple(v):
    nums = re.findall(r"\d+", v or "")
    if not nums:
        return None
    try:
        return tuple(int(x) for x in nums[:3])
    except ValueError:
        return None


def fmt_ver(t):
    return ".".join(str(x) for x in t) if t else "?"


def find_venvs(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "pyvenv.cfg" in filenames:
            found.append(dirpath)
    return sorted(found)


def read_pkgs(venv):
    """读 certifi/pip/uv 版本：先 *.dist-info，再 virtualenv 的 *.virtualenv 标记（不启动解释器）。"""
    sp = os.path.join(venv, "Lib", "site-packages")
    pkgs = {}
    if not os.path.isdir(sp):
        return pkgs
    entries = os.listdir(sp)
    for suffix in (".dist-info", ".virtualenv"):
        for entry in entries:
            if not entry.endswith(suffix):
                continue
            stem = entry[: -len(suffix)]
            for pkg in FLOORS:
                if stem.lower().startswith(pkg + "-"):
                    pkgs.setdefault(pkg, stem[len(pkg) + 1:])
                    break
    return pkgs


def pyver(venv):
    try:
        with open(os.path.join(venv, "pyvenv.cfg"), encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("version"):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "?"


def orphan_entries(venv):
    """列出 site-packages 下以 ``~`` 开头的一级孤儿项。

    来源：Windows 上 pip 自升级时会把自身包目录改名成 ``~ip``（运行中删不掉），
    升级成功后应自行清理；进程被杀/清理失败就留下孤儿。
    实测：``~ip`` 内 vendored certifi 停在 2026.06.17（**含 3 份 G3 根**，在受影响区间内），
    而活跃的 ``pip/_vendor/certifi`` 已是 2026.10.19（干净）。
    ⇒ 孤儿**不在 import 路径上**（``import pip`` 走 ``pip/``，``importlib.metadata`` 也不被遮蔽），
    但它让「扫 cacert.pem」的审计工具反复误报，且磁盘上留着一份过期易受攻击的 CA 捆绑包。
    ⇒ 处置：移出 site-packages（改名隔离，不删除）。
    """
    sp = os.path.join(venv, "Lib", "site-packages")
    if not os.path.isdir(sp):
        return []
    return sorted(e for e in os.listdir(sp) if e.startswith("~"))


def scan_bundles(venv):
    """扫出该 venv 内**所有** CA 捆绑包，逐个统计 G3 命中数。

    返回 [(相对路径, G3 命中数, emSign 总命中数, 归属), ...]
    归属 = 'active'（在正常包目录下，**真在 import 路径上**）| 'orphan'（在 ~ 孤儿目录下，惰性残留）
    —— emSign 总命中数只作参考（2026.10.19 起合法保留未受影响的 emSign 根），
    真正的判据是 G3 命中数必须为 0。
    """
    sp = os.path.join(venv, "Lib", "site-packages")
    out = []
    if not os.path.isdir(sp):
        return out
    for dp, dn, fn in os.walk(sp):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f != "cacert.pem":
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            rel = os.path.relpath(p, sp).replace("\\", "/")
            top = rel.split("/")[0]
            out.append((rel, text.count(G3), text.count("emSign"),
                        "orphan" if top.startswith("~") else "active"))
    return sorted(out)


def standalone_uv_version():
    """查 PATH 上的 uv 版本（uv 自带 vendored webpki-roots，非 venv 内）。"""
    exe = shutil.which("uv")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    m = re.search(r"(\d+\.\d+\.\d+)", (r.stdout or "") + (r.stderr or ""))
    return m.group(1) if m else None


# ----------------------------------------------------------------- 判定

def detect(venv, pkgs=None, bundles=None, orphans=None):
    """返回问题清单（空列表 = 达标）。三面全查：独立 certifi / pip vendored / uv。"""
    if pkgs is None:
        pkgs = read_pkgs(venv)
    if bundles is None:
        bundles = scan_bundles(venv)
    if orphans is None:
        orphans = orphan_entries(venv)
    issues = []

    # 面 1：独立 certifi 包
    cur = ver_tuple(pkgs.get("certifi"))
    if cur is not None and cur < FLOORS["certifi"]:
        issues.append("certifi %s < %s" % (pkgs.get("certifi"), fmt_ver(FLOORS["certifi"])))

    # 面 1b：pip 版本（pip 自带 vendored certifi，公告点名的受影响组件）
    cur = ver_tuple(pkgs.get("pip"))
    if cur is not None and cur < FLOORS["pip"]:
        issues.append("pip %s < %s" % (pkgs.get("pip"), fmt_ver(FLOORS["pip"])))

    # 面 2：**活跃** CA 捆绑包里不得再有 G3（真正在 import 路径上，命中即实锤）
    for rel, g3, emsign, kind in bundles:
        if g3 and kind == "active":
            issues.append("活跃 CA bundle 含 G3 x%d: %s" % (g3, rel))

    # 面 2b：孤儿残留（~ip 等）——惰性，但磁盘上留着过期易受攻击的 CA 捆绑包，需隔离
    if orphans:
        issues.append("孤儿残留(pip 自升级遗留): " + ",".join(orphans))

    # 面 3：uv（独立安装才查）
    uvv = standalone_uv_version()
    if uvv:
        t = ver_tuple(uvv)
        if t is not None and t < FLOORS["uv"]:
            issues.append("uv %s < %s" % (uvv, fmt_ver(FLOORS["uv"])))
    return issues


# ----------------------------------------------------------------- 执行器

def probe(py):
    try:
        r = subprocess.run([py, "--version"], capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def pip_works(py):
    try:
        r = subprocess.run([py, "-m", "pip", "--version"], capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def repair_home(venv):
    """pyvenv.cfg 的 home 指向失效基准解释器时，按版本映射改写为本地可用路径。

    只改 home 一行；version/executable/command 等历史行原样保留。
    """
    cfg = os.path.join(venv, "pyvenv.cfg")
    try:
        with open(cfg, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None, None
    ver = ""
    for line in lines:
        if line.strip().startswith("version"):
            ver = line.split("=", 1)[1].strip() if "=" in line else ""
    m = re.match(r"(\d+)\.(\d+)", ver)
    if not m:
        return None, None
    base = BASE_MAP.get((int(m.group(1)), int(m.group(2))))
    if not base or not os.path.isdir(base):
        return None, None
    old = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("home"):
            old = line.split("=", 1)[1].strip() if "=" in line else ""
            lines[i] = "home = " + base
            break
    else:
        return None, None
    with open(cfg, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return base, old


def quarantine_broken_pip(venv):
    """ensurepip 误判 'Requirement already satisfied' 空转时：把损坏的 pip 目录与
    pip-*.dist-info **改名加 .bak 备份**（不删除），让 ensurepip 能重新引导。"""
    sp = os.path.join(venv, "Lib", "site-packages")
    if not os.path.isdir(sp):
        return []
    stamp = time.strftime("%Y%m%d%H%M%S")
    moved = []
    for entry in os.listdir(sp):
        if entry == "pip" or entry.startswith("pip-") and entry.endswith(".dist-info"):
            src = os.path.join(sp, entry)
            dst = src + ".bak." + stamp
            try:
                os.rename(src, dst)
                moved.append(entry)
            except OSError:
                pass
    return moved


def quarantine_orphans(venv):
    """把 ``~`` 孤儿项移出 site-packages（改名隔离，**不删除**），移入 ``<venv>/.orphan/``。

    特殊情形：若活跃 ``pip`` 目录缺失而 ``~ip`` 存在，说明这个 venv 的 pip 实际被孤儿顶掉了
    ⇒ 此时**还原**（``~ip`` → ``pip``）以修复损坏的 venv，而不是隔离它。

    返回 (隔离清单, 还原清单)。
    """
    sp = os.path.join(venv, "Lib", "site-packages")
    if not os.path.isdir(sp):
        return [], []
    entries = [e for e in os.listdir(sp) if e.startswith("~")]
    if not entries:
        return [], []

    stamp = time.strftime("%Y%m%d%H%M%S")
    quarantine_dir = os.path.join(venv, ".orphan")
    moved, restored = [], []

    # 孤儿顶掉了唯一的 pip ⇒ 先还原
    if not os.path.isdir(os.path.join(sp, "pip")) and "~ip" in entries:
        try:
            os.rename(os.path.join(sp, "~ip"), os.path.join(sp, "pip"))
            restored.append("~ip -> pip")
            entries.remove("~ip")
        except OSError:
            pass

    if entries:
        try:
            os.makedirs(quarantine_dir, exist_ok=True)
        except OSError:
            return [], restored
    for e in entries:
        src = os.path.join(sp, e)
        dst = os.path.join(quarantine_dir, e + "." + stamp)
        try:
            os.rename(src, dst)
            moved.append(e)
        except OSError:
            pass
    return moved, restored


def _work(item):
    venv, py, issues, pkgs = item
    try:
        if py is None:
            return (venv, "anomaly", "no Scripts/python.exe", None, False)
        repaired_from = None
        if not probe(py):
            base, old = repair_home(venv)
            if base is None:
                return (venv, "failed", "interpreter broken, no local base for repair", None, False)
            if not probe(py):
                return (venv, "failed", "home repaired to %s but interpreter still fails" % base,
                        None, False)
            repaired_from = old

        notes = []
        bootstrapped = False

        # ① pip 缺失/残缺 -> ensurepip 引导（带改名备份的空转兜底）
        if not pip_works(py):
            r = subprocess.run([py, "-m", "ensurepip", "--upgrade"],
                               capture_output=True, text=True, timeout=300)
            if not pip_works(py):
                moved = quarantine_broken_pip(venv)
                r = subprocess.run([py, "-m", "ensurepip", "--upgrade"],
                                   capture_output=True, text=True, timeout=300)
                if moved:
                    notes.append("quarantined: " + ",".join(moved))
            if not pip_works(py):
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
                return (venv, "failed", "ensurepip bootstrap failed: " + " | ".join(tail),
                        repaired_from, False)
            bootstrapped = True
            notes.append("pip bootstrapped via ensurepip")

        # ② 需要升级的包：pip（刷新其 vendored certifi）+ 已装但低于基线的 certifi
        targets = []
        cur_pip = ver_tuple(read_pkgs(venv).get("pip"))
        if cur_pip is None or cur_pip < FLOORS["pip"]:
            targets.append("pip")
        cur_cf = ver_tuple(read_pkgs(venv).get("certifi"))
        if cur_cf is not None and cur_cf < FLOORS["certifi"]:
            targets.append("certifi")

        before = {p: read_pkgs(venv).get(p) for p in targets}
        if targets:
            r = subprocess.run([py, "-m", "pip", "install", "--upgrade"] + targets,
                               capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
                return (venv, "failed", " | ".join(tail), repaired_from, bootstrapped)

        # ③ 升级后若**活跃** CA 捆绑包仍有 G3 -> 强制重装 pip（刷新 vendored certifi）
        leftovers = [b for b in scan_bundles(venv) if b[1] > 0 and b[3] == "active"]
        if leftovers:
            r = subprocess.run([py, "-m", "pip", "install", "--upgrade", "--force-reinstall", "pip"],
                               capture_output=True, text=True, timeout=900)
            leftovers = [b for b in scan_bundles(venv) if b[1] > 0 and b[3] == "active"]
            if leftovers:
                return (venv, "failed", "活跃 G3 残留未清除: " + ", ".join(b[0] for b in leftovers),
                        repaired_from, bootstrapped)
            notes.append("force-reinstalled pip to purge G3")

        # ④ 孤儿残留（~ip 等）隔离出 site-packages（不删除）
        moved, restored = quarantine_orphans(venv)
        if moved:
            notes.append("quarantined: " + ",".join(moved))
        if restored:
            notes.append("restored: " + ",".join(restored))

        after = read_pkgs(venv)
        still = detect(venv, pkgs=after)
        if still:
            return (venv, "failed", "; ".join(still), repaired_from, bootstrapped)

        info = ", ".join("%s %s->%s" % (p, before[p], after.get(p)) for p in targets) or "no-op"
        if repaired_from:
            info += " [home: %s -> repaired]" % repaired_from
        if notes:
            info += " [" + "; ".join(notes) + "]"
        return (venv, "upgraded", info, repaired_from, bootstrapped)
    except Exception as e:  # noqa: BLE001
        return (venv, "failed", "worker error: %r" % e, None, False)


# ----------------------------------------------------------------- 子命令

def cmd_scan(root):
    if not os.path.isdir(root):
        print("ROOT_MISSING " + root)
        return 1
    venvs = find_venvs(root)
    uvv = standalone_uv_version()
    n_vuln = 0
    n_orphan = 0
    print("ROOT %s" % root)
    print("UV_STANDALONE %s" % (uvv or "not-found"))
    for v in venvs:
        pkgs = read_pkgs(v)
        bundles = scan_bundles(v)
        orphans = orphan_entries(v)
        issues = detect(v, pkgs=pkgs, bundles=bundles, orphans=orphans)
        if issues:
            n_vuln += 1
        if orphans:
            n_orphan += 1
        print(json.dumps({
            "venv": v,
            "py": pyver(v),
            "pkgs": pkgs,
            "bundles": [{"path": b[0], "g3": b[1], "emsign": b[2], "kind": b[3]} for b in bundles],
            "orphans": orphans,
            "issues": issues,
            "interp": os.path.isfile(os.path.join(v, "Scripts", "python.exe")),
        }, ensure_ascii=False))
    print("VULNERABLE_TOTAL %d" % n_vuln)
    print("OK_TOTAL %d" % (len(venvs) - n_vuln))
    print("ORPHAN_VENV_TOTAL %d" % n_orphan)
    print("SCAN_SUMMARY root=%s total=%d vulnerable=%d clean=%d orphan_venvs=%d uv=%s"
          % (root, len(venvs), n_vuln, len(venvs) - n_vuln, n_orphan, uvv or "not-found"))
    return 0


def cmd_apply(root, jobs):
    venvs = find_venvs(root)
    items = []
    for v in venvs:
        pkgs = read_pkgs(v)
        issues = detect(v, pkgs=pkgs)
        py = os.path.join(v, "Scripts", "python.exe")
        has_interp = os.path.isfile(py)
        # pip 完全缺失（曾被外部进程删/同步不完整）也要修
        if not issues and not (has_interp and "pip" not in pkgs):
            continue
        items.append((v, py if has_interp else None, issues, pkgs))

    results = [None] * len(items)
    lock = threading.Lock()
    done = [0]

    def run(i):
        res = _work(items[i])
        results[i] = res
        with lock:
            done[0] += 1
            print("progress %d/%d" % (done[0], len(items)), flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(run, range(len(items))))

    upgraded = bootstrapped_n = 0
    failed, anomalies = [], []
    old_homes = {}
    for res in results:
        if res is None:
            continue
        venv, status, info, repaired_from, bootstrapped = res
        if status == "upgraded":
            print("[UPGRADED] %s  %s" % (venv, info))
            upgraded += 1
            if bootstrapped:
                bootstrapped_n += 1
            if repaired_from:
                old_homes[repaired_from] = old_homes.get(repaired_from, 0) + 1
        elif status == "anomaly":
            print("[ANOMALY] %s  %s" % (venv, info))
            anomalies.append((venv, info))
        else:
            print("[FAIL] %s  %s" % (venv, info))
            failed.append((venv, info[:300]))
    print("APPLY_SUMMARY root=%s upgraded=%d already_ok=%d failed=%d anomaly=%d bootstrapped=%d"
          % (root, upgraded, len(venvs) - len(items), len(failed), len(anomalies), bootstrapped_n))
    if old_homes:
        print("REPAIRED_HOME_SOURCES " + json.dumps(old_homes, ensure_ascii=False))
    for v, why in anomalies:
        print("  anomaly: %s (%s)" % (v, why))
    for v, why in failed:
        print("  failed: %s (%s)" % (v, why))
    return 0 if not failed and not anomalies else 2


def _verify(item):
    """功能审计：实际运行解释器与 pip，并核对磁盘上的 CA 捆绑包 G3 计数。"""
    venv, py = item
    issues = []
    if not probe(py):
        return (venv, ["interpreter broken"])
    r = subprocess.run([py, "-m", "pip", "--version"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        issues.append("pip broken/missing")
    else:
        m = re.search(r"pip (\d+\.\d+\.\d+)", r.stdout)
        if m and ver_tuple(m.group(1)) < FLOORS["pip"]:
            issues.append("pip %s < %s" % (m.group(1), fmt_ver(FLOORS["pip"])))
    # 独立 certifi（有装才查）
    code = ("import certifi,pathlib;"
            "p=pathlib.Path(certifi.where());"
            "t=p.read_text(errors='replace');"
            "print(certifi.__version__, t.count('emSign ECC Root CA - G3'))")
    r2 = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=120)
    if r2.returncode == 0 and r2.stdout.strip():
        parts = r2.stdout.split()
        if ver_tuple(parts[0]) < FLOORS["certifi"]:
            issues.append("certifi %s < %s" % (parts[0], fmt_ver(FLOORS["certifi"])))
        if len(parts) > 1 and parts[1] != "0":
            issues.append("certifi bundle emSign-G3 x%s" % parts[1])
    # pip vendored certifi（旧版本漏检的这一面，必须在磁盘上直接核对）
    for rel, g3, _emsign, kind in scan_bundles(venv):
        if g3 and kind == "active":
            issues.append("活跃 CA bundle 含 G3 x%d: %s" % (g3, rel))
    # 孤儿残留（惰性，但含过期易受攻击的 CA 捆绑包，须已隔离）
    orphans = orphan_entries(venv)
    if orphans:
        issues.append("孤儿残留未隔离: " + ",".join(orphans))
    return (venv, issues)


def cmd_verify(root, jobs):
    venvs = find_venvs(root)
    uvv = standalone_uv_version()
    uv_issue = None
    if uvv:
        t = ver_tuple(uvv)
        if t is not None and t < FLOORS["uv"]:
            uv_issue = "uv %s < %s" % (uvv, fmt_ver(FLOORS["uv"]))

    items = [(v, os.path.join(v, "Scripts", "python.exe")) for v in venvs]
    results = [None] * len(items)
    lock = threading.Lock()
    done = [0]

    def run(i):
        res = _verify(items[i])
        results[i] = res
        with lock:
            done[0] += 1
            print("progress %d/%d" % (done[0], len(items)), flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(run, range(len(items))))

    bad = 0
    for venv, issues in results:
        if issues:
            bad += 1
            print("[ISSUE] %s  %s" % (venv, "; ".join(issues)))
    if uv_issue:
        bad += 1
        print("[ISSUE] <standalone uv>  %s" % uv_issue)
    print("VERIFY_SUMMARY total=%d clean=%d issue=%d uv=%s"
          % (len(venvs), len(venvs) - bad, bad, uvv or "not-found"))
    return 0 if bad == 0 else 2


def main(argv):
    mode = argv[1] if len(argv) > 1 else "scan"
    if mode == "scan":
        root = argv[2] if len(argv) > 2 else DEFAULT_ROOT
        return cmd_scan(root)
    if mode == "verify":
        root = argv[2] if len(argv) > 2 else DEFAULT_ROOT
        jobs = int(argv[3]) if len(argv) > 3 else 8
        return cmd_verify(root, jobs)
    if mode == "apply":
        root = argv[2] if len(argv) > 2 else DEFAULT_ROOT
        jobs = int(argv[3]) if len(argv) > 3 else 8
        return cmd_apply(root, jobs)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
