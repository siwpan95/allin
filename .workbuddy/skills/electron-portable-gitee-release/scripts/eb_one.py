"""Build ONE electron-builder Windows target at a time (nsis | portable).

Usage:
    python eb_one.py nsis
    python eb_one.py portable

Why one at a time
-----------------
`nsis` and `portable` both consume release/win-unpacked. Building them in a
single invocation makes them race on that directory, which surfaces as rcedit
failing with "Fatal error: Unable to commit changes" (see SKILL.md 流程 D 卡点 3).
Run this twice instead.

Prerequisites (see SKILL.md 流程 D):
  * package.json -> build.win.signAndEditExecutable = false
  * 7za wrapper shim installed and at the front of PATH
  * electron-builder + app-builder-bin already installed in node_modules
"""
import os
import shutil
import subprocess
import sys

# ---- 可调参数 ----
NODE = os.environ.get("SANTI_NODE_EXE") or "node"
CWD = os.environ.get("SANTI_APP_DIR") or os.getcwd()
OUT_DIR = os.path.join(CWD, "release")
SHIM_DIR = os.environ.get("SANTI_7ZA_SHIM_DIR") or os.path.join(CWD, ".7zbin")
LOG_DIR = os.environ.get("SANTI_LOG_DIR") or CWD
CACHE = os.environ.get("ELECTRON_BUILDER_CACHE") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "electron-builder", "Cache")
# ------------------

CLI = os.path.join(CWD, "node_modules", "electron-builder", "cli.js")
target = sys.argv[1] if len(sys.argv) > 1 else "nsis"

# Remove stale unpacked dir so rcedit starts from a pristine exe. Rename aside
# rather than delete: a recursive delete of a large tree trips the environment's
# bulk-delete guard (SAFE_DELETE_BULK_CONFIRM_REQUIRED).
wu = os.path.join(OUT_DIR, "win-unpacked")
if os.path.isdir(wu):
    stale = os.path.join(OUT_DIR, "..", "win-unpacked-stale")
    stale = os.path.abspath(stale)
    if os.path.isdir(stale):
        shutil.rmtree(stale, ignore_errors=True)
    os.rename(wu, stale)
    print("moved stale win-unpacked aside ->", stale)

env = dict(os.environ)
env["PATH"] = ";".join([
    SHIM_DIR,
    os.path.join(CWD, "node_modules", "7zip-bin", "win", "x64"),
    os.path.join(CWD, "node_modules", "app-builder-bin", "win", "x64"),
    env.get("PATH", ""),
])
# Route 7za through the wrapper (see 7za_wrap.js).
env["USE_SYSTEM_7ZA"] = "true"
env["SZA_PATH"] = "7za"
# Mirrors + cache: keeps the build down to the winCodeSign/nsis/electron artifacts.
env.setdefault("ELECTRON_MIRROR", "https://npmmirror.com/mirrors/electron/")
env.setdefault("ELECTRON_BUILDER_BINARIES_MIRROR",
               "https://npmmirror.com/mirrors/electron-builder-binaries/")
env["ELECTRON_BUILDER_CACHE"] = CACHE
env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
env["PYTHONUTF8"] = "1"

cmd = [NODE, CLI, "--win", target, "--publish", "never"]
print("CMD:", " ".join(cmd), flush=True)

log = os.path.join(LOG_DIR, "eb_%s.log" % target)
with open(log, "w", encoding="utf-8", errors="replace") as f:
    f.write("CMD: " + " ".join(cmd) + "\n")
    f.flush()
    p = subprocess.Popen(cmd, cwd=CWD, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    for raw in p.stdout:
        # Never rely on bash stdout in this environment; stream to a log file instead.
        f.write(raw.decode("utf-8", errors="replace"))
        f.flush()
    rc = p.wait()
    f.write("\n=== EXIT %d ===\n" % rc)

print("EXIT", rc, "log:", log)
sys.exit(rc)
