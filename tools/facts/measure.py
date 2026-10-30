#!/usr/bin/env python3
"""measure -- 采集本机事实，输出可直接贴入 `docs/事实源/机器/<机器名>.md` 的 markdown 片段。

为什么有这个脚本
----------------
2026-10-30 对 `DESKTOP-8RSV60V` 做全量复测时，9 处过期断言全部靠手工逐项敲命令发现。
同一套命令换一台机器还得重敲一遍 —— 于是「事实源只在被复测的那一刻为真」。
本脚本把那 9 类观测固化成一条命令，让**任何机器**都能生成自己的现值快照。

它只**采集**，不改任何文件（`--out` 除外），也不判断对错 ——
对错由 `verify_facts.py` 判，两者分离是为了让"采集"永远可信。

用法
----
    python tools/facts/measure.py                 # 打印 markdown
    python tools/facts/measure.py --out x.md      # 写文件

退出码：0 成功，2 用法错误，3 环境错误（非 Windows 或缺少必需工具）。
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

EXIT_OK, EXIT_USAGE, EXIT_ENV = 0, 2, 3

# 这些目录按仓根相对写，避免把盘符写进代码（铁律 5）。
REPO_MARKERS = ("docs", "preset", "tools")


def run(cmd: list[str], timeout: int = 20) -> str:
    """跑一条命令，失败返回空串而不是抛异常 —— 采集不该因为一项失败而整体中断。

    显式指定 utf-8 + errors="replace"：中文 Windows 上 PowerShell 默认按 GBK 输出，
    直接 text=True 会撞 `UnicodeDecodeError` 并在工作线程里抛出（实测于 2026-10-30）。
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return (p.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def ps(script: str) -> str:
    """跑一段 PowerShell，返回 stdout。先钉死输出编码为 UTF-8。"""
    exe = shutil.which("pwsh") or shutil.which("powershell")
    if not exe:
        return ""
    prelude = ("$ProgressPreference='SilentlyContinue';"
               "$OutputEncoding=[Console]::OutputEncoding=[Text.Encoding]::UTF8;")
    return run([exe, "-NoProfile", "-NonInteractive", "-Command", prelude + script])


def find_repo_root() -> Path | None:
    """从脚本位置向上找仓根：含 docs/ 且含 preset/ 的那一级。"""
    for p in Path(__file__).resolve().parents:
        if all((p / m).is_dir() for m in REPO_MARKERS):
            return p
    return None


def collect_system() -> dict:
    out = {"hostname": platform.node() or "(空)", "fqdn_env": os.environ.get("COMPUTERNAME", "")}
    raw = ps("$o=Get-CimInstance Win32_OperatingSystem;"
             "'{0}|{1}|{2}' -f $o.Caption,$o.Version,$o.BuildNumber")
    parts = raw.split("|")
    out["os"] = parts[0] if parts and parts[0] else "(未知)"
    out["os_version"] = parts[1] if len(parts) > 1 else ""
    out["os_build"] = parts[2] if len(parts) > 2 else ""
    out["userprofile"] = os.environ.get("USERPROFILE", "")
    return out


def collect_volumes() -> list[dict]:
    raw = ps("Get-Volume | Where-Object {$_.DriveLetter} | Sort-Object DriveLetter | ForEach-Object {"
             "'{0}|{1}|{2}|{3}|{4}' -f $_.DriveLetter,$_.FileSystemLabel,$_.FileSystem,"
             "[int]($_.Size/1GB),[int]($_.SizeRemaining/1GB)}")
    vols = []
    for line in raw.splitlines():
        f = line.split("|")
        if len(f) >= 5:
            vols.append({"letter": f[0], "label": f[1] or "(无)",
                         "fs": f[2], "size_gb": f[3], "free_gb": f[4]})
    return vols


def collect_disks() -> list[dict]:
    raw = ps("Get-Disk | ForEach-Object {"
             "'{0}|{1}|{2}|{3}' -f $_.Number,$_.FriendlyName,$_.BusType,[int]($_.Size/1GB)}")
    disks = []
    for line in raw.splitlines():
        f = line.split("|")
        if len(f) >= 4:
            disks.append({"num": f[0], "model": f[1], "bus": f[2], "size_gb": f[3]})
    return disks


def count_dirs(path: Path) -> int:
    try:
        return sum(1 for c in path.iterdir() if c.is_dir())
    except OSError:
        return -1


def count_all(path: Path) -> int:
    try:
        return sum(1 for _ in path.iterdir())
    except OSError:
        return -1


def collect_toolchain() -> list[dict]:
    """逐个 absolute 路径跑 -V / --version，判"路径存在"不等于"版本是那个"。"""
    rows = []
    for name, probe in (("git", ["git", "--version"]),
                        ("node", ["node", "-v"]),
                        ("npm", ["npm", "-v"])):
        exe = shutil.which(name)
        if exe:
            rows.append({"tool": name, "path": exe, "version": run([exe] + probe[1:])})
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if exe:
            rows.append({"tool": "python(PATH)",
                         "path": exe,
                         "version": run([exe, "-V"])})
            break
    return rows


def collect_remotes(root: Path) -> dict:
    url = run(["git", "-C", str(root), "config", "--get", "remote.origin.url"])
    push = run(["git", "-C", str(root), "config", "--get-all", "remote.origin.pushurl"])
    head = run(["git", "-C", str(root), "rev-parse", "HEAD"])
    branch = run(["git", "-C", str(root), "symbolic-ref", "--short", "HEAD"])
    return {"origin_url": url, "pushurls": [l for l in push.splitlines() if l],
            "head": head, "branch": branch}


def collect_env() -> dict:
    keys = ("KONTAKT_TRANSCODE_ROOT", "RIME_SRC", "GITEE_TOKEN")
    out = {}
    for k in keys:
        v = os.environ.get(k, "")
        # 只报"已设置/未设置"，不打印值 —— 防止把密钥写进事实源。
        out[k] = "已设置" if v else "未设置"
    return out


def emit_markdown(root: Path) -> str:
    today = date.today().isoformat()
    sysinfo = collect_system()
    vols = collect_volumes()
    disks = collect_disks()
    tools = collect_toolchain()
    remotes = collect_remotes(root)
    envs = collect_env()

    L: list[str] = []
    L.append(f"> **时点** {today}（**`tools/facts/measure.py` 自动采集** —— "
             f"机器 `{sysinfo['hostname']}`；本段为**采集原始值**，未经人工裁决，")
    L.append(">   凡与上一版不符者，须逐项复测后再改，**不要直接覆盖**。）")
    L.append(f"> **观测工具** `tools/facts/measure.py`（`Get-Volume` / `Get-Disk` / `Get-Command` / `git config`）")
    L.append(f"> **失效条件** 换机、加减盘、重装系统、换运行时版本后立即失效")
    L.append("")
    L.append(f"### 系统")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    L.append(f"| hostname | `{sysinfo['hostname']}` |")
    L.append(f"| `$env:COMPUTERNAME` | `{sysinfo['fqdn_env'] or '(空)'}` |")
    L.append(f"| 系统 | {sysinfo['os']} {sysinfo['os_version']}（build {sysinfo['os_build']}） |")
    L.append(f"| 用户目录 | `{sysinfo['userprofile']}` |")
    L.append("")
    if vols:
        L.append("### 卷")
        L.append("")
        L.append("| 盘 | 卷标 | 文件系统 | 容量 GB | 可用 GB |")
        L.append("| --- | --- | --- | --- | --- |")
        for v in vols:
            L.append(f"| `{v['letter']}:` | `{v['label']}` | {v['fs']} | {v['size_gb']} | {v['free_gb']} |")
        L.append("")
    if disks:
        L.append("### 物理盘")
        L.append("")
        L.append("| # | 型号 | 总线 | 容量 GB |")
        L.append("| --- | --- | --- | --- |")
        for d in disks:
            L.append(f"| {d['num']} | `{d['model']}` | {d['bus']} | {d['size_gb']} |")
        L.append("")
    L.append("### 仓与归档")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    repos = root.parent / "repos"
    if repos.is_dir():
        L.append(f"| `repos/` 顶层目录 | **{count_dirs(repos)}** |")
        withgit = sum(1 for c in repos.iterdir() if c.is_dir() and (c / ".git").exists())
        L.append(f"| `repos/` 含 `.git` | **{withgit}** |")
    arch = root.parent / "archive"
    if arch.is_dir():
        L.append(f"| `archive/` 项数 | **{count_all(arch)}** |")
    L.append(f"| 本仓分支 / HEAD | `{remotes['branch']}` / `{remotes['head'][:12] or '(空)'}` |")
    L.append("")
    if tools:
        L.append("### 工具链（PATH 实际解析，非文档声称）")
        L.append("")
        L.append("| 工具 | PATH 落点 | 版本 |")
        L.append("| --- | --- | --- |")
        for t in tools:
            L.append(f"| {t['tool']} | `{t['path']}` | `{t['version'] or '(取不到)'}` |")
        L.append("")
    L.append("### 推送与远端")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("| --- | --- |")
    L.append(f"| `remote.origin.url` | `{remotes['origin_url'] or '(无)'}` |")
    L.append(f"| `remote.origin.pushurl` 条数 | **{len(remotes['pushurls'])}** |")
    for u in remotes["pushurls"]:
        L.append(f"| 　└ pushurl | `{u}` |")
    L.append("")
    L.append("### 环境变量（只报有无，不打印值）")
    L.append("")
    L.append("| 变量 | 现值 |")
    L.append("| --- | --- |")
    for k, v in envs.items():
        L.append(f"| `{k}` | {v} |")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="measure", description="采集本机事实，输出 markdown")
    ap.add_argument("--out", help="写入该文件（默认打印到 stdout）")
    ap.add_argument("--root", help="仓根（默认自动探测）")
    args = ap.parse_args(argv)

    if sys.platform != "win32":
        print("ENV ERROR: 本脚本只支持 Windows（依赖 Get-Volume / Get-Disk）", file=sys.stderr)
        return EXIT_ENV

    root = Path(args.root).resolve() if args.root else find_repo_root()
    if root is None or not (root / "docs").is_dir():
        print("ENV ERROR: 找不到仓根（需含 docs/ 与 preset/）", file=sys.stderr)
        return EXIT_ENV

    md = emit_markdown(root)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"written: {args.out} ({len(md)} chars)")
    else:
        print(md)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
