#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""venv 安全巡检与加固（通用检查框架）。

定位
----
这是「venv 安全巡检与加固」的**通用执行器**，不是只针对某一条公告的一次性脚本。
检查项以注册表（``CHECKS``）组织，每条检查各自负责 ``scan`` / ``verify``，
可自动修复的检查额外提供 ``apply``。新增一类风险 = 往 ``CHECKS`` 加一个类，
不必改动主流程。

内置检查（7 项）
----------------
  · pip-bootstrap         pip 缺失/损坏 → ensurepip 引导（损坏则先改名备份）
  · broken-home-repair    pyvenv.cfg 的 home 指向失效基准解释器 → 按版本映射修复
  · pip-certifi-uv-baseline  pip / certifi / uv 版本基线
  · ca-emsign-g3          emSign ECC Root CA - G3（GHSA-6q48）活跃 CA 捆绑包残留
  · dep-vuln-baseline     离线已知漏洞基线（内置 ADVISORIES 表，可按公告扩充）
  · venv-integrity        venv 结构完整性（解释器/元数据/重复 dist-info）
  · orphan-quarantine     site-packages 下 ``~`` 孤儿残留（pip 自升级遗留）隔离

为什么 CA 判据必须精确到 G3
---------------------------
certifi 2026.10.19 的捆绑包里仍保留 9~15 处未受影响的 ``emSign`` 根（公告有意恢复）。
所以「有没有 emSign」是**错的**判据（会误报）；**唯一正确判据**是精确匹配
``emSign ECC Root CA - G3``，且只在活跃包目录内计数。

三个必查面（CA 检查）
--------------------
1. 独立 certifi 包：``site-packages/certifi/cacert.pem``
2. **pip 的 vendored certifi**：``site-packages/pip/_vendor/certifi/cacert.pem``
   （公告点名的受影响组件；多数 venv 根本没装独立 certifi，靠 ``import certifi`` 会静默跳过）
3. uv：``uv < 0.13.4`` 的 vendored webpki-roots 同含 G3（修复：uv 0.13.4 / webpki-roots 1.0.10）

安全基线
--------
  certifi >= 2026.10.19 ；pip >= 26.2.2 ；uv >= 0.13.4（已安装才检查）

用法
----
  python venv_security.py scan   [root] [jobs] [--check ID]   # 只读扫描
  python venv_security.py apply  [root] [jobs] [--check ID]   # 加固（幂等，仅可修项）
  python venv_security.py verify [root] [jobs] [--check ID]   # 功能级审计（实跑解释器）
  python venv_security.py --list                              # 列出全部检查项

根目录请用环境变量 ``ALLIN_VENV_SCAN_ROOT`` 注入（缺省扫当前目录）；
基准解释器根用 ``PYTHON314_ROOT`` / ``PYTHON313_ROOT`` / ``PYTHON312_ROOT`` 注入。
**本文件不写死任何盘符路径**（治理铁律 5 去符盘）。

纪律
----
纯标准库；scan 只读 site-packages 元数据（不启动解释器）；
verify 才实跑解释器；**不删除任何文件**（损坏的 pip 仅改名 .bak 备份，孤儿仅改名隔离）。
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

# ----------------------------------------------------------------- 常量

# 默认扫描根：各机用 ALLIN_VENV_SCAN_ROOT 环境变量覆盖；缺省扫当前目录。
# 治理铁律 5：绝不写死机器盘符路径。
DEFAULT_ROOT = os.environ.get("ALLIN_VENV_SCAN_ROOT", ".")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".tox", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "htmlcov", "build", "dist", ".idea", ".vscode"}

FLOORS = {"certifi": (2026, 10, 19), "pip": (26, 2, 2), "uv": (0, 13, 4)}
G3 = "emSign ECC Root CA - G3"

# 逐机基准解释器根：由各机环境变量注入，不写死绝对路径（治理铁律 5）。
# 未设置时对应版本不参与 home 修复（工具仅跳过该版本，不影响其余检查）。
BASE_MAP = {
    (3, 14): os.environ.get("PYTHON314_ROOT"),
    (3, 13): os.environ.get("PYTHON313_ROOT"),
    (3, 12): os.environ.get("PYTHON312_ROOT"),
}

# 离线已知漏洞基线（示例播种；按官方公告核对后追加）。
# 结构：pkg / ranges[(lo, hi)]（lo <= v < hi）/ fixed / note。
# 说明：只报告不自动升级（自动改任意依赖版本风险高），交由使用者决策。
ADVISORIES = [
    {"id": "GHSA-6q48-6c7w-9gw2", "pkg": "certifi",
     "ranges": [((2019, 3, 9), (2026, 10, 19))], "fixed": "2026.10.19",
     "note": "emSign G3 根证书（CA 私钥泄露，MITM 风险）"},
    {"id": "CVE-2024-37891", "pkg": "urllib3",
     "ranges": [((1, 26, 0), (1, 26, 19)), ((2, 0, 0), (2, 2, 2))],
     "fixed": "1.26.19 / 2.2.2", "note": "Proxy-Authorization 头跨域泄露"},
    {"id": "CVE-2024-35195", "pkg": "requests",
     "ranges": [((0, 0, 0), (2, 32, 0))], "fixed": "2.32.0",
     "note": "verify=False 会话复用证书校验绕过"},
    {"id": "CVE-2023-32681", "pkg": "requests",
     "ranges": [((0, 0, 0), (2, 31, 0))], "fixed": "2.31.0",
     "note": "重定向时 Proxy-Authorization 头泄露"},
    {"id": "CVE-2023-43804", "pkg": "urllib3",
     "ranges": [((1, 26, 0), (1, 26, 17)), ((2, 0, 0), (2, 0, 7))],
     "fixed": "1.26.17 / 2.0.7", "note": "跨域重定向时 Cookie 头泄露"},
    {"id": "CVE-2023-45803", "pkg": "urllib3",
     "ranges": [((1, 26, 0), (1, 26, 18)), ((2, 0, 0), (2, 0, 7))],
     "fixed": "1.26.18 / 2.0.7", "note": "重定向时请求体泄露"},
    {"id": "CVE-2023-5752", "pkg": "pip",
     "ranges": [((0, 0, 0), (23, 3, 0))], "fixed": "23.3",
     "note": "Mercurial VCS 安装时配置注入"},
    {"id": "CVE-2022-40897", "pkg": "setuptools",
     "ranges": [((0, 0, 0), (65, 5, 1))], "fixed": "65.5.1",
     "note": "package_index ReDoS"},
    {"id": "CVE-2024-6345", "pkg": "setuptools",
     "ranges": [((0, 0, 0), (70, 0, 0))], "fixed": "70.0.0",
     "note": "package_index 下载代码注入"},
    {"id": "CVE-2024-3651", "pkg": "idna",
     "ranges": [((0, 0, 0), (3, 7, 0))], "fixed": "3.7",
     "note": "idna.encode 构造输入 DoS"},
    {"id": "CVE-2023-50782", "pkg": "cryptography",
     "ranges": [((38, 0, 0), (42, 0, 2))], "fixed": "42.0.2",
     "note": "PKCS#1 v1.5 RSA 解密 oracle"},
    {"id": "CVE-2024-22195", "pkg": "jinja2",
     "ranges": [((0, 0, 0), (3, 1, 3))], "fixed": "3.1.3",
     "note": "xmlattr 过滤器 XSS"},
    {"id": "CVE-2024-34064", "pkg": "jinja2",
     "ranges": [((0, 0, 0), (3, 1, 4))], "fixed": "3.1.4",
     "note": "xmlattr 属性注入"},
    {"id": "CVE-2023-46136", "pkg": "werkzeug",
     "ranges": [((0, 0, 0), (3, 0, 1))], "fixed": "3.0.1",
     "note": "multipart 表单解析 DoS"},
    {"id": "CVE-2020-14343", "pkg": "pyyaml",
     "ranges": [((0, 0, 0), (5, 4, 0))], "fixed": "5.4",
     "note": "full_load 任意代码执行"},
]


# ----------------------------------------------------------------- 基础工具

def ver_tuple(v):
    """把版本串解析成**定长 3 元组**（缺位补 0），便于与基线做元组比较。"""
    nums = re.findall(r"\d+", v or "")
    if not nums:
        return None
    try:
        t = tuple(int(x) for x in nums[:3])
    except ValueError:
        return None
    return tuple(list(t) + [0] * (3 - len(t)))


def fmt_ver(t):
    return ".".join(str(x) for x in t) if t else "?"


def site_packages(venv):
    return os.path.join(venv, "Lib", "site-packages")


def find_venvs(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "pyvenv.cfg" in filenames:
            found.append(dirpath)
    return sorted(found)


def read_pkgs(venv):
    """读 certifi/pip/uv 版本：先 *.dist-info，再 virtualenv 的 *.virtualenv 标记（不启动解释器）。"""
    sp = site_packages(venv)
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


def read_all_pkgs(venv):
    """读全部已装包 {小写包名: 版本}（用于离线漏洞基线比对）。"""
    sp = site_packages(venv)
    out = {}
    if not os.path.isdir(sp):
        return out
    for entry in os.listdir(sp):
        if not entry.endswith(".dist-info") or entry.startswith("~"):
            continue
        stem = entry[: -len(".dist-info")]
        if "-" not in stem:
            continue
        name, _, ver = stem.rpartition("-")
        if name and ver:
            out[name.lower()] = ver
    return out


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
    孤儿不在 import 路径上，但磁盘上留着一份过期易受攻击的 CA 捆绑包。
    """
    sp = site_packages(venv)
    if not os.path.isdir(sp):
        return []
    return sorted(e for e in os.listdir(sp) if e.startswith("~"))


def scan_bundles(venv):
    """扫出该 venv 内**所有** CA 捆绑包，逐个统计 G3 命中数。

    返回 [(相对路径, G3 命中数, emSign 总命中数, 归属), ...]
    归属 = 'active'（正常包目录，真在 import 路径上）| 'orphan'（~ 孤儿目录，惰性残留）。
    真正的判据是 G3 命中数；emSign 总数只作参考（2026.10.19 起合法保留未受影响的 emSign 根）。
    """
    sp = site_packages(venv)
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


def planned_home(venv):
    """算出 home 应改成哪个基准解释器根（只读，不写文件）。返回 (base, old)，不可修则 (None, None)。"""
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
    for line in lines:
        if line.strip().lower().startswith("home"):
            old = line.split("=", 1)[1].strip() if "=" in line else ""
            break
    return base, old


def repair_home(venv):
    """把 pyvenv.cfg 的 home 改写为本地可用基准解释器；只改 home 一行，其余历史行原样保留。"""
    base, old = planned_home(venv)
    if not base:
        return None, None
    cfg = os.path.join(venv, "pyvenv.cfg")
    try:
        with open(cfg, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None, None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("home"):
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
    sp = site_packages(venv)
    if not os.path.isdir(sp):
        return []
    stamp = time.strftime("%Y%m%d%H%M%S")
    moved = []
    for entry in os.listdir(sp):
        if entry == "pip" or (entry.startswith("pip-") and entry.endswith(".dist-info")):
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

    特殊情形：若活跃 ``pip`` 目录缺失而 ``~ip`` 存在，说明 viv 的 pip 实际被孤儿顶掉了
    ⇒ 此时**还原**（``~ip`` → ``pip``）以修复损坏的 venv，而不是隔离它。
    返回 (隔离清单, 还原清单)。
    """
    sp = site_packages(venv)
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


# ----------------------------------------------------------------- 检查项

class Check:
    """检查项基类：id / title / severity / fixable；子类实现 scan/verify，可修项再实现 apply。"""
    id = ""
    title = ""
    severity = "medium"
    fixable = False

    def scan(self, venv, ctx):
        return []

    def verify(self, venv, ctx):
        return []

    def apply(self, venv, ctx):
        return None


class PipBootstrap(Check):
    id = "pip-bootstrap"
    title = "pip 缺失/损坏则 ensurepip 引导"
    severity = "high"
    fixable = True

    def scan(self, venv, ctx):
        pkgs = ctx["pkgs"]
        if "pip" not in pkgs:
            return ["pip 未安装"]
        return []

    def verify(self, venv, ctx):
        py = ctx["py"]
        if not py or not probe(py):
            return ["interpreter broken"]
        return [] if pip_works(py) else ["pip broken/missing"]

    def apply(self, venv, ctx):
        py = ctx["py"]
        if not py or pip_works(py):
            return None
        r = subprocess.run([py, "-m", "ensurepip", "--upgrade"],
                           capture_output=True, text=True, timeout=300)
        if pip_works(py):
            return "pip bootstrapped via ensurepip"
        moved = quarantine_broken_pip(venv)
        r = subprocess.run([py, "-m", "ensurepip", "--upgrade"],
                           capture_output=True, text=True, timeout=300)
        if pip_works(py):
            return "pip bootstrapped (quarantined: %s)" % (",".join(moved) or "none")
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
        return "ensurepip failed: " + " | ".join(tail)


class BrokenHomeRepair(Check):
    id = "broken-home-repair"
    title = "pyvenv.cfg home 失效则按版本映射修复"
    severity = "high"
    fixable = True

    def scan(self, venv, ctx):
        py = ctx["py"]
        if not py or probe(py):
            return []
        base, old = planned_home(venv)
        if base:
            return ["interpreter broken (home=%s，可映射到 %s)" % (old or "?", base)]
        return ["interpreter broken (无可用基准解释器映射)"]

    def verify(self, venv, ctx):
        py = ctx["py"]
        if py and probe(py):
            return []
        return ["interpreter broken"]

    def apply(self, venv, ctx):
        py = ctx["py"]
        if not py or probe(py):
            return None
        base, old = repair_home(venv)
        if base and probe(py):
            return "home %s -> %s" % (old or "?", base)
        return "home repair failed"


class PipCertifiUvBaseline(Check):
    id = "pip-certifi-uv-baseline"
    title = "pip / certifi / uv 版本基线"
    severity = "high"
    fixable = True

    def scan(self, venv, ctx):
        issues = []
        pkgs = ctx["pkgs"]
        cur = ver_tuple(pkgs.get("certifi"))
        if cur is not None and cur < FLOORS["certifi"]:
            issues.append("certifi %s < %s" % (pkgs.get("certifi"), fmt_ver(FLOORS["certifi"])))
        cur = ver_tuple(pkgs.get("pip"))
        if cur is not None and cur < FLOORS["pip"]:
            issues.append("pip %s < %s" % (pkgs.get("pip"), fmt_ver(FLOORS["pip"])))
        uvv = ctx.get("uv")
        if uvv:
            t = ver_tuple(uvv)
            if t is not None and t < FLOORS["uv"]:
                issues.append("uv %s < %s" % (uvv, fmt_ver(FLOORS["uv"])))
        return issues

    def verify(self, venv, ctx):
        issues = []
        py = ctx["py"]
        if not py or not probe(py):
            return ["interpreter broken"]
        r = subprocess.run([py, "-m", "pip", "--version"], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            issues.append("pip broken/missing")
        else:
            m = re.search(r"pip (\d+\.\d+\.\d+)", r.stdout)
            if m:
                t = ver_tuple(m.group(1))
                if t is not None and t < FLOORS["pip"]:
                    issues.append("pip %s < %s" % (m.group(1), fmt_ver(FLOORS["pip"])))
        # 独立 certifi（有装才查；同时在磁盘上核对 G3）
        code = ("import certifi,pathlib;"
                "p=pathlib.Path(certifi.where());"
                "t=p.read_text(errors='replace');"
                "print(certifi.__version__, t.count('emSign ECC Root CA - G3'))")
        r2 = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=120)
        if r2.returncode == 0 and r2.stdout.strip():
            parts = r2.stdout.split()
            t0 = ver_tuple(parts[0])
            if t0 is not None and t0 < FLOORS["certifi"]:
                issues.append("certifi %s < %s" % (parts[0], fmt_ver(FLOORS["certifi"])))
            if len(parts) > 1 and parts[1] != "0":
                issues.append("certifi bundle emSign-G3 x%s" % parts[1])
        uvv = ctx.get("uv")
        if uvv:
            t = ver_tuple(uvv)
            if t is not None and t < FLOORS["uv"]:
                issues.append("uv %s < %s" % (uvv, fmt_ver(FLOORS["uv"])))
        return issues

    def apply(self, venv, ctx):
        py = ctx["py"]
        if not py or not pip_works(py):
            return None  # 由 pip-bootstrap 负责
        pkgs = read_pkgs(venv)
        targets = []
        cur_pip = ver_tuple(pkgs.get("pip"))
        if cur_pip is None or cur_pip < FLOORS["pip"]:
            targets.append("pip")
        cur_cf = ver_tuple(pkgs.get("certifi"))
        if cur_cf is not None and cur_cf < FLOORS["certifi"]:
            targets.append("certifi")
        if not targets:
            return None
        r = subprocess.run([py, "-m", "pip", "install", "--upgrade"] + targets,
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            return "upgrade failed: " + " | ".join(tail)
        return "upgraded " + ",".join(targets)


class CAEmSignG3(Check):
    id = "ca-emsign-g3"
    title = "emSign ECC Root CA - G3（GHSA-6q48）活跃 CA 捆绑包残留"
    severity = "critical"
    fixable = True

    def scan(self, venv, ctx):
        issues = []
        for rel, g3, _emsign, kind in ctx["bundles"]:
            if g3 and kind == "active":
                issues.append("活跃 CA bundle 含 G3 x%d: %s" % (g3, rel))
        return issues

    def verify(self, venv, ctx):
        return self.scan(venv, ctx)

    def apply(self, venv, ctx):
        py = ctx["py"]
        leftovers = [b for b in scan_bundles(venv) if b[1] > 0 and b[3] == "active"]
        if not leftovers:
            return None
        if not py or not pip_works(py):
            return "活跃 G3 残留，但 pip 不可用，无法强制重装"
        subprocess.run([py, "-m", "pip", "install", "--upgrade", "--force-reinstall", "pip"],
                       capture_output=True, text=True, timeout=900)
        leftovers = [b for b in scan_bundles(venv) if b[1] > 0 and b[3] == "active"]
        if leftovers:
            return "强制重装 pip 后活跃 G3 仍残留: " + ", ".join(b[0] for b in leftovers)
        return "force-reinstalled pip to purge G3"


class DepVulnBaseline(Check):
    id = "dep-vuln-baseline"
    title = "离线已知漏洞基线（ADVISORIES）"
    severity = "high"
    fixable = False  # 只报告，不自动升级任意依赖

    def scan(self, venv, ctx):
        issues = []
        installed = ctx["all_pkgs"]
        for adv in ADVISORIES:
            v = installed.get(adv["pkg"].lower())
            if not v:
                continue
            t = ver_tuple(v)
            if t is None:
                continue
            for lo, hi in adv["ranges"]:
                if lo <= t < hi:
                    issues.append("%s %s 命中 %s（修复 %s）" % (adv["pkg"], v, adv["id"], adv["fixed"]))
                    break
        return issues

    def verify(self, venv, ctx):
        return self.scan(venv, ctx)


class VenvIntegrity(Check):
    id = "venv-integrity"
    title = "venv 结构完整性（解释器/元数据/重复 dist-info）"
    severity = "low"
    fixable = False

    def scan(self, venv, ctx):
        issues = []
        if not ctx["py"]:
            issues.append("缺少 Scripts/python.exe")
        if pyver(venv) == "?":
            issues.append("pyvenv.cfg 缺少 version")
        sp = site_packages(venv)
        if os.path.isdir(sp):
            seen = {}
            for entry in os.listdir(sp):
                if not entry.endswith(".dist-info") or entry.startswith("~"):
                    continue
                stem = entry[: -len(".dist-info")]
                if "-" not in stem:
                    continue
                name, _, ver = stem.rpartition("-")
                seen.setdefault(name.lower(), []).append(ver)
            for name, vers in sorted(seen.items()):
                uniq = sorted(set(vers))
                if len(uniq) > 1:
                    issues.append("重复 dist-info: %s -> %s" % (name, ",".join(uniq)))
        return issues

    def verify(self, venv, ctx):
        return self.scan(venv, ctx)


class OrphanQuarantine(Check):
    id = "orphan-quarantine"
    title = "site-packages 下 ~ 孤儿残留隔离"
    severity = "medium"
    fixable = True

    def scan(self, venv, ctx):
        orphans = ctx["orphans"]
        return ["孤儿残留: " + ",".join(orphans)] if orphans else []

    def verify(self, venv, ctx):
        orphans = orphan_entries(venv)
        return ["孤儿残留未隔离: " + ",".join(orphans)] if orphans else []

    def apply(self, venv, ctx):
        moved, restored = quarantine_orphans(venv)
        notes = []
        if moved:
            notes.append("quarantined: " + ",".join(moved))
        if restored:
            notes.append("restored: " + ",".join(restored))
        return "; ".join(notes) or None


# 注册表：新增检查只需在此追加一个实例。
CHECKS = [
    PipBootstrap(),
    BrokenHomeRepair(),
    PipCertifiUvBaseline(),
    CAEmSignG3(),
    DepVulnBaseline(),
    VenvIntegrity(),
    OrphanQuarantine(),
]
CHECKS_BY_ID = {c.id: c for c in CHECKS}


# ----------------------------------------------------------------- 上下文与命令

def build_ctx(venv, uv_ver):
    py = os.path.join(venv, "Scripts", "python.exe")
    has = os.path.isfile(py)
    return {
        "py": py if has else None,
        "pkgs": read_pkgs(venv),
        "all_pkgs": read_all_pkgs(venv),
        "bundles": scan_bundles(venv),
        "orphans": orphan_entries(venv),
        "uv": uv_ver,
    }


def cmd_list():
    print("CHECKS %d" % len(CHECKS))
    for c in CHECKS:
        print("  %-24s [%s]%s %s" % (c.id, c.severity,
                                     "" if c.fixable else " (只报告)", c.title))
    return 0


def cmd_scan(root, check_id=None):
    if not os.path.isdir(root):
        print("ROOT_MISSING " + root)
        return 1
    venvs = find_venvs(root)
    uv_ver = standalone_uv_version()
    checks = [CHECKS_BY_ID[check_id]] if check_id else CHECKS
    n_vuln = n_orphan = 0
    print("ROOT %s" % root)
    print("UV_STANDALONE %s" % (uv_ver or "not-found"))
    for v in venvs:
        ctx = build_ctx(v, uv_ver)
        per, issues = [], []
        for c in checks:
            ci = c.scan(v, ctx)
            if ci:
                per.append({"id": c.id, "severity": c.severity, "issues": ci})
                issues.extend(ci)
        if issues:
            n_vuln += 1
        if ctx["orphans"]:
            n_orphan += 1
        print(json.dumps({
            "venv": v,
            "py": pyver(v),
            "pkgs": ctx["pkgs"],
            "bundles": [{"path": b[0], "g3": b[1], "emsign": b[2], "kind": b[3]}
                        for b in ctx["bundles"]],
            "orphans": ctx["orphans"],
            "issues": issues,
            "checks": per,
            "interp": bool(ctx["py"]),
        }, ensure_ascii=False))
    print("VULNERABLE_TOTAL %d" % n_vuln)
    print("OK_TOTAL %d" % (len(venvs) - n_vuln))
    print("ORPHAN_VENV_TOTAL %d" % n_orphan)
    print("SCAN_SUMMARY root=%s total=%d vulnerable=%d clean=%d orphan_venvs=%d uv=%s"
          % (root, len(venvs), n_vuln, len(venvs) - n_vuln, n_orphan, uv_ver or "not-found"))
    return 0


def apply_venv(venv, only_id=None):
    """对单个 venv 执行加固。返回 (status, info)，status ∈ upgraded/noop/anomaly/failed。"""
    ctx = build_ctx(venv, None)
    py = ctx["py"]
    if not py:
        return ("anomaly", "no Scripts/python.exe")

    notes = []
    if not probe(py):
        base, old = repair_home(venv)
        if base is None:
            return ("failed", "interpreter broken, no local base for repair")
        if not probe(py):
            return ("failed", "home repaired to %s but interpreter still fails" % base)
        notes.append("broken-home-repair: home %s -> %s" % (old or "?", base))

    order = ["pip-bootstrap", "pip-certifi-uv-baseline", "ca-emsign-g3", "orphan-quarantine"]
    if only_id:
        order = [only_id] if only_id in order else []
    for cid in order:
        c = CHECKS_BY_ID[cid]
        note = c.apply(venv, {"py": py})
        if note:
            notes.append("%s: %s" % (cid, note))

    # 终检只看「可自动修复」的检查项；只报告项（dep-vuln / integrity）不参与 apply 成败
    ctx2 = build_ctx(venv, None)
    scope = [CHECKS_BY_ID[only_id]] if only_id else [c for c in CHECKS if c.fixable]
    still = []
    for c in scope:
        if c.fixable:
            still.extend(c.scan(venv, ctx2))
    if still:
        return ("failed", "; ".join(still))
    return ("upgraded" if notes else "noop", "; ".join(notes) or "no-op")


def cmd_apply(root, jobs, check_id=None):
    if check_id and not CHECKS_BY_ID[check_id].fixable:
        print("CHECK_NOT_FIXABLE " + check_id)
        return 1
    venvs = find_venvs(root)
    items = []
    for v in venvs:
        ctx = build_ctx(v, None)
        if check_id:
            need = bool(CHECKS_BY_ID[check_id].scan(v, ctx))
        else:
            need = any(c.scan(v, ctx) for c in CHECKS if c.fixable)
        # pip 完全缺失也要修（即使其余检查没报）
        if not need and not (ctx["py"] and "pip" not in ctx["pkgs"]):
            continue
        items.append(v)

    results = [None] * len(items)
    lock = threading.Lock()
    done = [0]

    def run(i):
        results[i] = apply_venv(items[i], check_id)
        with lock:
            done[0] += 1
            print("progress %d/%d" % (done[0], len(items)), flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(run, range(len(items))))

    upgraded = failed = anomalies = 0
    failures = []
    for v, res in zip(items, results):
        if res is None:
            continue
        status, info = res
        if status == "upgraded":
            print("[UPGRADED] %s  %s" % (v, info))
            upgraded += 1
        elif status == "anomaly":
            print("[ANOMALY] %s  %s" % (v, info))
            anomalies += 1
        elif status == "failed":
            print("[FAIL] %s  %s" % (v, info))
            failed += 1
            failures.append((v, info[:300]))
    print("APPLY_SUMMARY root=%s upgraded=%d already_ok=%d failed=%d anomaly=%d"
          % (root, upgraded, len(venvs) - len(items), failed, anomalies))
    for v, why in failures:
        print("  failed: %s (%s)" % (v, why))
    return 0 if not failed and not anomalies else 2


def cmd_verify(root, jobs, check_id=None):
    venvs = find_venvs(root)
    uv_ver = standalone_uv_version()
    checks = [CHECKS_BY_ID[check_id]] if check_id else CHECKS
    results = [None] * len(venvs)
    lock = threading.Lock()
    done = [0]

    def run(i):
        v = venvs[i]
        ctx = build_ctx(v, uv_ver)
        issues = []
        for c in checks:
            issues.extend(c.verify(v, ctx))
        results[i] = (v, issues)
        with lock:
            done[0] += 1
            print("progress %d/%d" % (done[0], len(venvs)), flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(run, range(len(venvs))))

    bad = 0
    for v, issues in results:
        if issues:
            bad += 1
            print("[ISSUE] %s  %s" % (v, "; ".join(issues)))
    print("VERIFY_SUMMARY total=%d clean=%d issue=%d uv=%s"
          % (len(venvs), len(venvs) - bad, bad, uv_ver or "not-found"))
    return 0 if bad == 0 else 2


def main(argv):
    args = argv[1:]
    if not args:
        print(__doc__)
        return 1
    if args[0] in ("--list", "list", "-l"):
        return cmd_list()
    mode = args[0]
    rest = args[1:]
    check_id = None
    if "--check" in rest:
        i = rest.index("--check")
        check_id = rest[i + 1] if i + 1 < len(rest) else None
        rest = rest[:i] + rest[i + 2:]
    if check_id and check_id not in CHECKS_BY_ID:
        print("UNKNOWN_CHECK " + check_id)
        return 1
    root = rest[0] if len(rest) > 0 else DEFAULT_ROOT
    jobs = int(rest[1]) if len(rest) > 1 else 8
    if mode == "scan":
        return cmd_scan(root, check_id)
    if mode == "verify":
        return cmd_verify(root, jobs, check_id)
    if mode == "apply":
        return cmd_apply(root, jobs, check_id)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
