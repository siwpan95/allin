#!/usr/bin/env python3
"""构建 `allin-governance` 的 sdist 与 wheel —— 先把映射树**物化**，再打包。

## 为什么需要这个脚本（2026-10-31 实测的坑）

`packages/allin-governance/pyproject.toml` 用了跨目录映射：

```toml
[tool.setuptools.package-dir]
"allin_governance._repocheck" = "../../tools/repocheck"
"allin_governance._gatesuite" = "../../tools/gate/governance"
```

这套映射对 **wheel** 完全有效：源文件被收进 wheel，仓内仍只有一份。
但对 **sdist** 无效 —— setuptools 不能收录**项目根之外**的文件。于是：

* `python -m build --sdist` 会打印 `Successfully built ... tar.gz`；
* `twine check` 也会 `PASSED`；
* 但那个 tar.gz 里**没有** `_repocheck/` 与 `_gatesuite/`；
* 从它装出来的包，`repocheck` 与 `init` 都会在运行时找不到源码。

最坏的地方是**它一路绿灯**：失败的形态不是报错，而是一个装得上、跑不起来的包。

## 这个脚本做什么

把两棵映射树**物化**到一个临时目录里的项目副本中，改写副本的 `package-dir`
为项目内路径，再在副本里构建。于是 sdist 是自包含的。

这会不会造成「派生副本手抄必漂」？不会 —— 物化发生在**临时目录**，
每次构建都重新生成，仓内不产生副本。分发物本来就是快照；
这里做的是构建步骤，不是第二个源码。

## 用法

```bash
python scripts/build_dist.py              # sdist + wheel，产物进 packages/allin-governance/dist/
python scripts/build_dist.py --wheel-only # 只出 wheel（不物化，快）
python scripts/build_dist.py --keep       # 保留临时目录，便于排查
```

前置：`pip install build`。校验：`twine check dist/*`。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECT = ROOT / "packages" / "allin-governance"

#: 复制项目时跳过的东西：都是构建/测试副产物，带进副本只会让 sdist 变脏。
SKIP_DIRS = frozenset({"dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache"})
SKIP_SUFFIXES = (".egg-info", ".pyc")

#: 只出 wheel 时不需要改写 `package-dir`：wheel 本来就能吃跨目录映射。
PACKAGE_DIR_HEADER = "[tool.setuptools.package-dir]"


def fail(message: str) -> "SystemExit":
    print(f"BUILD ERROR: {message}", file=sys.stderr)
    return SystemExit(2)


def read_mappings(pyproject: Path) -> dict[str, str]:
    """读出 `[tool.setuptools.package-dir]` 里所有指向项目外的映射。"""
    with pyproject.open("rb") as handle:  # gov-python: allow —— 二进制读，编码无意义
        data = tomllib.load(handle)
    mapping = data.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    return {key: value for key, value in mapping.items() if value.startswith("..")}


def copy_project(destination: Path) -> None:
    """把项目复制到 `destination`，跳过构建副产物。"""
    destination.mkdir(parents=True, exist_ok=True)
    for item in PROJECT.iterdir():
        if item.name in SKIP_DIRS or item.name.endswith(SKIP_SUFFIXES):
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(
                item, target,
                ignore=shutil.ignore_patterns(*SKIP_DIRS, *SKIP_SUFFIXES),
            )
        else:
            shutil.copyfile(item, target)


def materialize(project_copy: Path, mappings: dict[str, str]) -> dict[str, str]:
    """把映射树拷进副本，并返回 `package-dir` 的新旧值对照。

    新值 = 包名映射成路径（`allin_governance._repocheck` → `src/allin_governance/_repocheck`），
    也就是**安装后的样子**。这样 sdist 解开就是读者预期的布局，而不是一堆
    `tools/` 根目录（那样虽然也能装，但看包内容的人会先愣一下）。
    """
    rewrites: dict[str, str] = {}
    for package, relative in mappings.items():
        source = (PROJECT / relative).resolve()
        if not source.is_dir():
            raise fail(f"映射源不存在：{package} -> {relative}（解析为 {source}）")
        local = "src/" + package.replace(".", "/")
        destination = project_copy / local
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(*SKIP_DIRS, "__pycache__"))
        rewrites[relative] = local
    return rewrites


def rewrite_pyproject(pyproject: Path, rewrites: dict[str, str]) -> None:
    """把副本 pyproject 里的跨目录映射改写成项目内路径。

    按**字面值替换**而不是重新序列化整个 TOML：这个文件里写满了给读代码的人看的
    注释（为什么映射、为什么零依赖、为什么是这个版本），重新序列化会把它们全丢掉。
    值在文件里各出现一次，替换是安全的；替换数不符就直接失败，不猜。
    """
    text = pyproject.read_text(encoding="utf-8")
    for old, new in rewrites.items():
        needle = f'"{old}"'
        if text.count(needle) != 1:
            raise fail(f"pyproject 里 {needle} 出现 {text.count(needle)} 次，预期 1 次；拒绝盲改")
        text = text.replace(needle, f'"{new}"')
    pyproject.write_text(text, encoding="utf-8", newline="\n")


def run_build(project_copy: Path, out_dir: Path, *, sdist: bool) -> None:
    command = [sys.executable, "-m", "build"]
    command += ["--sdist", "--wheel"] if sdist else ["--wheel"]
    command += ["--outdir", str(out_dir), "."]
    print("build:", " ".join(command))
    completed = subprocess.run(command, cwd=str(project_copy), check=False)
    if completed.returncode != 0:
        raise fail(f"构建失败（exit {completed.returncode}）")


def verify_sdist(out_dir: Path, rewrites: dict[str, str]) -> None:
    """打开刚出的 sdist，确认每棵映射树**真的在里面**。

    为什么构建完还要再验一次：这个脚本存在的唯一理由就是「构建成功 ≠ 产物完整」。
    2026-10-31 的原始缺陷正是如此 —— `python -m build --sdist` 打印
    `Successfully built`，`twine check` 也 `PASSED`，而包里没有源码。
    既然缺陷的形态是「一路绿灯」，那就在绿灯之后再加一道必须过的检查。
    """
    archives = sorted(out_dir.glob("*.tar.gz"))
    if not archives:
        raise fail(f"{out_dir} 里没有 .tar.gz，无法复核 sdist")
    archive = archives[-1]
    with tarfile.open(archive) as handle:  # gov-python: allow —— tarfile 不是文本 I/O
        names = handle.getnames()
    stripped = {name.split("/", 1)[1] for name in names if "/" in name}
    missing = [local for local in rewrites.values() if not any(n.startswith(local + "/") for n in stripped)]
    if missing:
        raise fail(
            f"{archive.name} 缺少物化后的映射树：{', '.join(missing)}\n"
            "  这正是本脚本要防的缺陷形态：构建成功、检查通过、产物不可用。"
        )
    print(f"  ✓ sdist 自包含：{len(rewrites)} 棵映射树都在 {archive.name} 里")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_dist.py",
        description="构建 allin-governance 的 sdist 与 wheel（物化跨目录映射后再打包）",
    )
    parser.add_argument("--wheel-only", action="store_true",
                        help="只出 wheel（不物化，快；sdist 仍会是坏的）")
    parser.add_argument("--keep", action="store_true", help="保留临时目录，便于排查")
    parser.add_argument("--outdir", default=None, help="产物目录（默认 packages/allin-governance/dist）")
    args = parser.parse_args(argv)

    pyproject = PROJECT / "pyproject.toml"
    if not pyproject.is_file():
        raise fail(f"找不到 {pyproject}")

    out_dir = Path(args.outdir).expanduser().resolve() if args.outdir else PROJECT / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.iterdir():
        if stale.suffix in {".whl", ".gz"}:
            stale.unlink()

    if args.wheel_only:
        # 不物化也能出正确的 wheel：跨目录映射本来就对 wheel 有效。
        run_build(PROJECT, out_dir, sdist=False)
        _report(out_dir, sdist=False)
        return 0

    mappings = read_mappings(pyproject)
    if not mappings:
        raise fail("pyproject 里没有跨目录映射；这个脚本就是为它们存在的，请先确认")
    print(f"物化 {len(mappings)} 棵映射树：")
    for package, relative in mappings.items():
        print(f"  {package:44} <- {relative}")

    temp_root = Path(tempfile.mkdtemp(prefix="allin-dist-"))
    try:
        project_copy = temp_root / "allin-governance"
        copy_project(project_copy)
        rewrites = materialize(project_copy, mappings)
        rewrite_pyproject(project_copy / "pyproject.toml", rewrites)
        for old, new in rewrites.items():
            print(f"  package-dir: {old} -> {new}")
        run_build(project_copy, out_dir, sdist=True)
        verify_sdist(out_dir, rewrites)
    finally:
        if args.keep:
            print(f"临时目录保留在 {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)

    _report(out_dir, sdist=True)
    return 0


def _report(out_dir: Path, *, sdist: bool) -> None:
    print("\n产物：")
    for item in sorted(out_dir.iterdir()):
        if item.suffix in {".whl", ".gz"}:
            print(f"  {item.name}  {item.stat().st_size:,} bytes")
    print("\n下一步校验：")
    print(f"  twine check {out_dir}/*")
    if sdist:
        print("  从一个干净 venv 装那个 .tar.gz，跑一遍 init —— sdist 的判据是「装得上且跑得起来」，")
        print("  不是「构建成功」。构建成功但缺源码，正是这个脚本存在的理由。")
    else:
        print("  ⚠ --wheel-only 下 sdist 不生成；要发 sdist 必须走物化路径。")


if __name__ == "__main__":
    raise SystemExit(main())
