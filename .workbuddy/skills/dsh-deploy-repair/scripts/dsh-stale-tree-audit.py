#!/usr/bin/env python3
"""dsh-stale-tree-audit — 只读体检补充：抓出 `start-dsh-web.py --check` 看不见的「陈旧树」。

背景（2026-10-08 实测）：换基底 / rebase 到新上游快照后，如果只改了源码与
pnpm-lock.yaml 却没重跑 install+build，`--check` 依然「all green」，但启动会
以 `failed to import` + `client bundles not found` 直接失败。原因有三：

  1. `--check` 的 dependencies 判据只是 `node_modules/.modules.yaml` 是否存在；
  2. `--check` 的 build output 判据只有 apps/web/dist/index.html 与
     apps/cli/lib/types/bin.js 两个文件，不看每个包的 lib/index.js、lib/client.js；
  3. `--check` 默认查 `~/.dsh`，对每检出独立 home（DSH_HOME=./.dsh-home）会查错对象。

本脚本只读，输出四节：
  A. 锁文件漂移：committed pnpm-lock.yaml vs node_modules/.pnpm/lock.yaml 的 importers 差异
     （「只在 committed 里」= 这些包/依赖从未被安装）
  B. 包级链接缺失：package.json 声明的依赖在 <pkg>/node_modules/<name> 不存在
  C. 构建产物缺失：有 src/client/ 却没有 lib/client.js；以及缺 lib/index.js 的包
  D. 产物新鲜度：src 最新 mtime vs lib 最新 mtime（产物是否早于源码）

用法:
  python dsh-stale-tree-audit.py [checkout_root]
退出码: 0 = 未发现陈旧迹象; 1 = 发现（见输出）
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

SKIP_DIR_MARKERS = ("node_modules", "dist", ".git")


# --------------------------------------------------------------------------
# lockfile parsing
# --------------------------------------------------------------------------
def parse_importers(path: pathlib.Path) -> dict[str, dict[str, str]]:
    """{importer_path: {dep_name: version_spec}} — 只认 2/4/6 空格三级缩进。"""
    out: dict[str, dict[str, str]] = {}
    if not path.exists():
        return out
    in_importers = False
    cur: str | None = None
    block: str | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^importers:\s*$", line):
            in_importers = True
            continue
        if in_importers and re.match(r"^[A-Za-z#]", line):
            break  # 离开 importers 段
        if not in_importers:
            continue
        m = re.match(r"^  (\S.*?):\s*$", line)
        if m:
            cur = m.group(1).strip().strip("'\"")
            out.setdefault(cur, {})
            block = None
            continue
        m = re.match(r"^    (dependencies|optionalDependencies|devDependencies):\s*$", line)
        if m:
            block = m.group(1)
            continue
        if re.match(r"^    \S", line):
            block = None
            continue
        if cur and block:
            m = re.match(r"^      '?(\S[^':]*?)'?:\s*(.+?)\s*$", line)
            if m:
                out[cur][m.group(1)] = m.group(2)
    return out


# --------------------------------------------------------------------------
# filesystem probes
# --------------------------------------------------------------------------
def walk_mtime(root: pathlib.Path, pattern: str) -> tuple[float, pathlib.Path] | None:
    newest: tuple[float, pathlib.Path] | None = None
    for p in root.rglob(pattern):
        if any(part in SKIP_DIR_MARKERS for part in p.parts):
            continue
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if newest is None or m > newest[0]:
            newest = (m, p)
    return newest


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not (root / "pnpm-lock.yaml").exists():
        print(f"!! {root} 不像 dsh 检出（缺 pnpm-lock.yaml）")
        return 1
    findings = 0

    # ---------------- A. lockfile drift ----------------
    committed = parse_importers(root / "pnpm-lock.yaml")
    installed = parse_importers(root / "node_modules" / ".pnpm" / "lock.yaml")
    print("=" * 78)
    print(f"A. LOCKFILE DRIFT   committed={len(committed)}  installed={len(installed)}")
    print("=" * 78)
    never_installed = sorted(set(committed) - set(installed))
    if never_installed:
        findings += len(never_installed)
        print(f"   [!] {len(never_installed)} importer(s) in committed but NEVER installed:")
        for k in never_installed:
            print(f"       + {k}")
    stale = sorted(set(installed) - set(committed))
    if stale:
        findings += len(stale)
        print(f"   [!] {len(stale)} importer(s) installed but no longer in tree:")
        for k in stale:
            print(f"       - {k}")
    drifted = []
    for k in sorted(set(committed) & set(installed)):
        c, i = set(committed[k]), set(installed[k])
        if c != i:
            drifted.append((k, sorted(c - i), sorted(i - c)))
    if drifted:
        findings += len(drifted)
        print(f"   [!] {len(drifted)} importer(s) with dep drift (committed has, install lacks):")
        for k, added, removed in drifted:
            print(f"       ~ {k}: +{len(added)}/-{len(removed)}")
            if added:
                print(f"           now-required: {', '.join(added[:10])}")
    if not (never_installed or stale or drifted):
        print("   [ok] importers identical")
    print()

    # ---------------- B. unlinked deps ----------------
    print("=" * 78)
    print("B. UNLINKED DECLARED DEPS  (<pkg>/node_modules/<dep> 不存在)")
    print("=" * 78)
    scanned = 0
    unlinked: list[tuple[str, list[str]]] = []
    for pj in sorted(root.glob("packages/*/*/package.json")):
        if "node_modules" in pj.parts:
            continue
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"   [parse-error] {pj}: {exc}")
            continue
        scanned += 1
        declared: dict[str, str] = {}
        for field in ("dependencies", "optionalDependencies"):
            declared.update(data.get(field) or {})
        missing = [f"{n}@{spec}" for n, spec in sorted(declared.items())
                   if not (pj.parent / "node_modules" / n).exists()]
        if missing:
            unlinked.append((str(pj.parent.relative_to(root)).replace("\\", "/"), missing))
    print(f"   scanned {scanned} packages; {len(unlinked)} with unlinked deps")
    for rel, missing in unlinked:
        findings += 1
        print(f"   [!] {rel}  ({len(missing)} missing)")
        print(f"       {', '.join(missing)}")
    print()

    # ---------------- C. missing artifacts ----------------
    print("=" * 78)
    print("C. MISSING BUILD ARTIFACTS")
    print("=" * 78)
    no_index, no_client = [], []
    for pj in sorted(root.glob("packages/*/*/package.json")):
        if "node_modules" in pj.parts:
            continue
        d = pj.parent
        if not (d / "lib" / "index.js").exists():
            no_index.append(str(d.relative_to(root)).replace("\\", "/"))
        if (d / "src" / "client").is_dir() and not (d / "lib" / "client.js").exists():
            no_client.append(str(d.relative_to(root)).replace("\\", "/"))
    if no_index:
        findings += len(no_index)
        print(f"   [!] {len(no_index)} package(s) missing lib/index.js (host face):")
        for k in no_index:
            print(f"       - {k}")
    if no_client:
        findings += len(no_client)
        print(f"   [!] {len(no_client)} package(s) have src/client/ but no lib/client.js:")
        for k in no_client:
            print(f"       - {k}")
    if not (no_index or no_client):
        print("   [ok] all package faces present")
    print()

    # ---------------- D. staleness ----------------
    print("=" * 78)
    print("D. STALENESS  (build output vs source)")
    print("=" * 78)
    # 只把 packages/*/*/src 下的 .ts 当源码：lib/ 里的 *.d.ts 与 *.js 都是产物，
    # 混进来会让「源码比产物新」误报（2026-10-08 实测：lib/types/**/*.d.ts 被当成源码）。
    src = walk_mtime(root, "packages/*/*/src/**/*.ts") or walk_mtime(root, "packages/*/src/**/*.ts")
    lib = walk_mtime(root, "packages/*/*/lib/**/*.js")
    if src and lib:
        import datetime
        fs = datetime.datetime.fromtimestamp(src[0]).strftime("%Y-%m-%d %H:%M")
        fl = datetime.datetime.fromtimestamp(lib[0]).strftime("%Y-%m-%d %H:%M")
        print(f"   newest src : {fs}  ({src[1].relative_to(root)})")
        print(f"   newest lib : {fl}  ({lib[1].relative_to(root)})")
        if src[0] > lib[0]:
            findings += 1
            behind = sum(1 for p in root.glob("packages/*/*/src/**/*.ts")
                         if p.stat().st_mtime > lib[0])
            print(f"   [!] source is NEWER than every build artifact "
                  f"({behind} .ts file(s) newer) -> run `pnpm run build`")
        else:
            print("   [ok] artifacts are newer than source")
    print()
    print("=" * 78)
    print(f"RESULT: {'STALE / INCOMPLETE' if findings else 'clean'}  (findings={findings})")
    print("=" * 78)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
