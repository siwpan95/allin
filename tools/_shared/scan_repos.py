#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_repos.py —— 发布区扫盘：项目指纹、重复检出、合集内多副本。

为什么需要它
------------
2026-11-24 清理冻结仓时，判断「某项目是否重复」全靠一次性临时脚本：
逐个目录算文件哈希、与合集子目录比对。那次暴露出三个问题：

1. **判据散在对话里**。同一件事（「这个目录是不是那份仓的副本」）每次重写一遍，
   口径还不一样：有时比文件哈希，有时比目录名，有时只看 git remote。
2. **浅克隆会骗人**。在浅克隆里 `git log origin/x` 只看得见已下载对象，
   于是「远端只有 6 个提交」这种判断是假象（本项目实测踩过两次）。
3. **「本机不存在」被当成「已废弃」**。当场误删了 3 条 registry 登记
   （anatomy3d / write-agent / portal）—— 它们只是本机没检出。

本工具把这些判据固化成一次扫盘：对每个顶层目录提取**稳定指纹**，
再按指纹找重复。它是只读的，不改任何仓。

指纹的四个来源（缺一不可，任何单一来源都会漏判）
------------------------------------------------
| 来源 | 抓什么 | 抓不到什么 |
|---|---|---|
| ``git remote origin`` | 远端仓名 —— 判断「是不是同一个远端仓的两份检出」最硬 | 本机新建未推的仓 |
| ``pyproject.toml`` / ``setup.py`` / ``package.json`` 的 name | 发布名 —— 判断「PyPI/npm 上是同一个包」 | 非打包项目 |
| 关键文件哈希集合 | 内容相似度 —— 抓「改了名但内容是同一份」 | 空壳/仅 README 的仓 |
| 目录名 | 最弱，只作辅助 | 什么都抓不到 |

**故意不把目录名当主判据**：`mcclone` / `mc-clone`、`txtlegend` / `legend`
这类 id 与目录名不一致的重复登记，本轮实测正是按文件名匹配才漏掉的。

用法
----
    python tools/scan_repos.py                      # 扫默认发布区，输出重复与多副本
    python tools/scan_repos.py --root <发布区>
    python tools/scan_repos.py --json               # 机读
    python tools/scan_repos.py --dup-only           # 只列可疑重复

退出码：0 无重复 / 1 发现可疑重复（可进 CI）/ 2 用法错误 / 3 发布区不存在。

与相邻工具的分工
----------------
| 工具 | 管什么 |
|---|---|
| ``check_repos.mjs`` | registry 清单 ↔ 远端仓的**锚点**一致性（名字、存在性） |
| ``repo_hygiene.py`` | 发布区**卫生**（未登记目录、空壳仓、产物入库） |
| ``docs_backlinks.py`` | 文档之间的**引用**关系 |
| **本工具** | **内容层面的重复** —— 同一份东西出现在几处 |
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

#: 遍历时跳过的目录：这些不是项目内容，且体量大。
SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "output", "cache", ".cache",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode", "site-packages", ".next", ".nuxt",
})

#: 算内容指纹时只取这些扩展名的文件 —— 二进制/产物既慢又无鉴别力。
TEXT_SUFFIXES = frozenset({
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".kt", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb",
    ".php", ".lua", ".swift", ".sh", ".bash", ".ps1", ".bat", ".cmd",
    ".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json", ".ini",
    ".cfg", ".html", ".css", ".sql",
})

#: 单个项目的指纹采样上限 —— 大仓只需代表性样本即可判断「是不是同一份」。
MAX_FILES_FOR_FINGERPRINT = 400

#: 「这里的东西已经搬走了」的标记文件。2026-11-24 实测：`musickit/remix` 只剩
#: `MIGRATED.txt` + 旧代码，而顶层 `remix` 才是现行项目 —— 这类残留不会被
#: 「项目标识」判据抓到（它没有 .git/pyproject），但它恰恰是「多副本」的真身。
MIGRATION_MARKERS = ("MIGRATED.txt", "MIGRATED.md", "ARCHIVED.md", "ARCHIVED.txt",
                     "MOVED.md", "DEPRECATED.md", ".migrated")

_NAME_IN_PYPROJECT = re.compile(r'^\s*name\s*=\s*["\']([^"\']+)["\']', re.M)
_VERSION_IN_PYPROJECT = re.compile(r'^\s*version\s*=\s*["\']([^"\']+)["\']', re.M)


def _git(root: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=20, errors="replace",
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def remote_repo_name(root: Path) -> str:
    """``origin`` 的仓名（不含 owner、去 .git）。取不到返回空串。"""
    url = _git(root, "remote", "get-url", "origin")
    if not url:
        return ""
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def declared_name(root: Path) -> tuple[str, str]:
    """读发布名（PyPI/npm）。返回 ``(name, 来源文件)``，取不到返回 ``("", "")``。"""
    for fname, regex in (
        ("pyproject.toml", _NAME_IN_PYPROJECT),
        ("package.json", None),
    ):
        p = root / fname
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if fname == "package.json":
            try:
                data = json.loads(text)
                name = str(data.get("name") or "")
                if name:
                    return name, fname
            except Exception:
                pass
            continue
        m = regex.search(text)
        if m:
            return m.group(1), fname
    # setup.py 只做低置信度兜底（正则读代码不可靠，仅取第一处 name=）
    sp = root / "setup.py"
    if sp.is_file():
        m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', sp.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1), "setup.py"
    return "", ""


def content_fingerprint(root: Path) -> tuple[frozenset[str], int]:
    """内容指纹 = 前 N 个文本文件的 sha256 前缀集合；同时返回文件总数。

    用**集合**而非单个哈希：目录增减一个文件不应让「同一份东西」判成不同，
    但内容改写要能被察觉 —— 集合的 Jaccard 距离正好表达这件事。
    """
    hashes: set[str] = set()
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            path = Path(dirpath) / fn
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            total += 1
            if len(hashes) >= MAX_FILES_FOR_FINGERPRINT:
                continue
            try:
                data = path.read_bytes()
            except Exception:
                continue
            hashes.add(hashlib.sha256(data).hexdigest()[:16])
    return frozenset(hashes), total


def migration_marker(p: Path) -> str:
    """目录里是否有「已迁走」标记。返回标记名或空串。"""
    for m in MIGRATION_MARKERS:
        if (p / m).exists():
            return m
    return ""


def looks_like_project(p: Path) -> bool:
    """子目录是否像一个独立项目（而非源码子包/资源目录）。"""
    return (p / ".git").exists() or any(
        (p / f).is_file() for f in ("pyproject.toml", "setup.py", "package.json", "Cargo.toml", "go.mod")
    )


def is_collection(p: Path) -> bool:
    """顶层目录是否是「合集」（多个子项目塞在一个仓里）。

    判据：子目录 ≥ 3，且其中 ≥ 2 个自带项目标识。阈值取 3/2 是因为——
    - 取 2 会把「src/ + tests/」这类普通单仓误判成合集；
    - 取 4 会漏掉 music-prototypes 这种只有 3 个子项的合集。
    """
    try:
        children = [c for c in p.iterdir() if c.is_dir() and not c.name.startswith(".")
                    and c.name not in SKIP_DIRS]
    except Exception:
        return False
    if len(children) < 3:
        return False
    return sum(1 for c in children if looks_like_project(c)) >= 2


def iter_units(root: Path, deep: bool) -> list[tuple[str, Path]]:
    """扫描单元：顶层项目；``deep`` 时额外展开子项目。

    返回 ``(显示名, 路径)``。合集子项显示为 ``合集/子项`` —— 这既是报告里的
    定位，也是判断「同一项目出现在多个合集」的依据。

    ``deep`` 的展开**不要求父目录是「合集」**：2026-11-24 实测，`musickit/remix`
    与 `bloodmusic/remix` 的父目录子项不足 3 个，按合集阈值会漏掉，而它们恰恰
    与顶层 `remix` 是同一项目的三个版本。所以 deep 只要求子目录「像项目」，
    宁可多扫 —— 噪声由下面的判据（自带 .git 才取 remote、包含关系不算相似）压住。
    """
    units: list[tuple[str, Path]] = []
    tops = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    for top in tops:
        units.append((top.name, top))
        if not deep:
            continue
        for child in sorted(top.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child.name in SKIP_DIRS:
                continue
            if looks_like_project(child) or migration_marker(child):
                units.append((f"{top.name}/{child.name}", child))
    return units


def describe(root: Path) -> dict:
    # 只认**自带** .git：合集的子目录没有自己的 .git，`git -C` 会向上找到父仓的，
    # 于是所有子项的 remote 都变成合集仓名 —— 那会把「合集 + 子项」全判成
    # 「同远端仓多份检出」。2026-11-24 实测：dev-toolkit 的 3 个子项全被误报。
    is_git = (root / ".git").exists()
    remote = remote_repo_name(root) if is_git else ""
    name, name_src = declared_name(root)
    fp, nfiles = content_fingerprint(root)
    return {
        "dir": root.name,
        "path": str(root),
        "remote": remote,
        "name": name,
        "name_src": name_src,
        "is_git": is_git,
        "is_shallow": _git(root, "rev-parse", "--is-shallow-repository") == "true" if is_git else False,
        "commits": _git(root, "rev-list", "--count", "HEAD") if is_git else "",
        "files": nfiles,
        "marker": migration_marker(root),
        "fp": fp,
    }


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区扫盘：项目指纹与重复检出")
    ap.add_argument("--root", default=None, help="发布区根（默认 <仓根>/../repos 或 ALLIN_REPOS_ROOT）")
    ap.add_argument("--json", action="store_true", help="机读输出")
    ap.add_argument("--dup-only", action="store_true", help="只输出可疑重复")
    ap.add_argument("--deep", action="store_true",
                    help="展开合集内部子项目（找「同一项目出现在多个合集」必用）")
    ap.add_argument("--sim", type=float, default=0.5, help="内容相似度阈值（默认 0.50）")
    args = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    if args.root:
        root = Path(args.root)
    else:
        env = os.environ.get("ALLIN_REPOS_ROOT")
        if env:
            root = Path(env)
        else:
            # 本仓住在发布区里：<发布区>/allin/tools/scan_repos.py
            # ⇒ 仓根 = here.parent，发布区 = 仓根的父目录（当父目录名是 repos 时）
            repo_root = here.parent
            root = repo_root.parent if repo_root.parent.name.lower() == "repos" else repo_root / "repos"
    if not root.is_dir():
        print(f"[ERR] 发布区不存在: {root}", file=sys.stderr)
        return 3

    units = iter_units(root, args.deep)
    infos = []
    for label, path in units:
        info = describe(path)
        info["label"] = label
        info["top"] = label.split("/", 1)[0]
        info["is_child"] = "/" in label
        infos.append(info)

    # ---- 重复判定：三条独立判据，任一命中即列入（不合并成「综合分」）----
    by_remote: dict[str, list[dict]] = defaultdict(list)
    by_name: dict[str, list[dict]] = defaultdict(list)
    for it in infos:
        if it["remote"]:
            by_remote[it["remote"].lower()].append(it)
        if it["name"]:
            by_name[it["name"].lower()].append(it)

    findings: list[dict] = []
    for key, group in sorted(by_remote.items()):
        if len(group) > 1:
            findings.append({"kind": "同远端仓多份检出", "key": key,
                             "holders": [g["label"] for g in group]})
    for key, group in sorted(by_name.items()):
        if len(group) > 1:
            findings.append({"kind": "同发布名多份", "key": key,
                             "holders": [g["label"] for g in group]})

    # 内容相似：只在「文件数相近」的对之间比，避免 O(n²) 全量算
    pairs = []
    for i in range(len(infos)):
        for j in range(i + 1, len(infos)):
            a, b = infos[i], infos[j]
            # 包含关系不是重复：合集的整体必然与其子项高度相似
            pa, pb = str(a["path"]), str(b["path"])
            if pa.startswith(pb + os.sep) or pb.startswith(pa + os.sep):
                continue
            if min(a["files"], b["files"]) == 0:
                continue
            if max(a["files"], b["files"]) > min(a["files"], b["files"]) * 3:
                continue
            sim = jaccard(a["fp"], b["fp"])
            if sim >= args.sim:
                pairs.append((sim, a["label"], b["label"], a["files"], b["files"]))
    for sim, x, y, nx, ny in sorted(pairs, reverse=True):
        findings.append({"kind": "内容高度相似", "key": f"{sim:.0%}", "holders": [f"{x}({nx})", f"{y}({ny})"]})

    # ---- 同名项目跨合集 / 合集内多副本 ----
    by_leaf: dict[str, list[dict]] = defaultdict(list)
    for it in infos:
        by_leaf[it["label"].split("/")[-1].lower()].append(it)
    for key, group in sorted(by_leaf.items()):
        if len(group) > 1:
            tops_in = {g["top"] for g in group}
            kind = "同名项目跨合集" if len(tops_in) > 1 else "合集内同名多副本"
            findings.append({"kind": kind, "key": key,
                             "holders": [g["label"] for g in group]})

    # ---- 迁移残留：有 MIGRATED/ARCHIVED 标记的目录，多半是「搬走没删」----
    residues = [it for it in infos if it.get("marker")]
    if residues:
        findings.append({"kind": "疑似迁移残留（带搬走标记）", "key": str(len(residues)),
                         "holders": [f"{it['label']} [{it['marker']}]" for it in residues]})

    if args.json:
        print(json.dumps({
            "root": str(root),
            "projects": len(infos),
            "findings": findings,
            "details": [{k: v for k, v in it.items() if k != "fp"} for it in infos],
        }, ensure_ascii=False, indent=2))
        return 1 if findings else 0

    print(f"发布区：{root}")
    print(f"项目数：{len(infos)}　（含 git {sum(1 for i in infos if i['is_git'])}，"
          f"浅克隆 {sum(1 for i in infos if i['is_shallow'])}）")
    if not args.dup_only:
        print(f"\n未取到发布名的项目 {sum(1 for i in infos if not i['name'])} 个"
              f"（非打包项目属正常）；未取到 remote 的 {sum(1 for i in infos if not i['remote'])} 个")
    if not findings:
        print("\n未发现重复：每个项目只有一份。")
        return 0
    print(f"\n可疑重复 {len(findings)} 组：")
    for f in findings:
        print(f"  [{f['kind']}] {f['key']}")
        for h in f["holders"]:
            print(f"      - {h}")
    print("\n提示：本工具只报告，不处置。删除前请按「冗余三查」确认接任者。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
