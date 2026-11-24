#!/usr/bin/env python3
"""发版前置校验 —— 把「1.0.0 那次事故」的每一步都变成一个退出码。

## 这个脚本为什么存在

2026-11-24 发布 `allin-governance` 1.0.0 时，wheel 是好的，sdist 是坏的：

    $ pip install allin_governance-1.0.0.tar.gz
    error: package directory '..\\..\\tools\\repocheck' does not exist

而当时的检查序列（`twine check` PASSED + 干净 venv 装 wheel 能跑）**全绿**。
原因是每种检查各看了一半：`twine check` 只看元数据，装 wheel 只走 wheel 这条路，
没人从 sdist 装一次。于是「发布物可用」这个结论从未被真正验证过。

本脚本把这套检查固化成一条命令，并要求**发版前必须跑 `--install`**：
`--install` 才是那次事故的唯一鉴别实验（从 sdist 装、再跑子命令）。

## 用法

    python scripts/release_preflight.py            # 静态检查（秒级）
    python scripts/release_preflight.py --install  # 追加：clean venv 装 sdist + wheel 并跑子命令

退出码（与仓内治理词汇一致）：0 通过 / 1 阻断 / 2 用法错 / 3 环境错。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_USAGE = 2
EXIT_ENV = 3

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "packages" / "allin-governance"
PYPROJECT = PROJECT / "pyproject.toml"
DIST = PROJECT / "dist"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"


class Result:
    """一行结论。三种状态必须分清：ok / fail / skip，skip 不算 ok。"""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.rows.append(("ok", name, detail))

    def fail(self, name: str, detail: str) -> None:
        self.rows.append(("fail", name, detail))

    def skip(self, name: str, detail: str) -> None:
        self.rows.append(("skip", name, detail))

    def report(self) -> int:
        width = max((len(name) for _, name, _ in self.rows), default=0)
        for status, name, detail in self.rows:
            mark = {"ok": "[ok]  ", "fail": "[FAIL]", "skip": "[skip]"}[status]
            print(f"{mark} {name.ljust(width)}  {detail}")
        failed = [row for row in self.rows if row[0] == "fail"]
        skipped = [row for row in self.rows if row[0] == "skip"]
        print()
        print(
            f"PREFLIGHT ok={len(self.rows) - len(failed) - len(skipped)} "
            f"fail={len(failed)} skip={len(skipped)}"
        )
        if failed:
            print("RESULT: BLOCKED —— 未通过项见上；不要上传。")
            return EXIT_BLOCKING
        if skipped:
            print("RESULT: INCOMPLETE —— 有项未判（skip 不是 pass）；发版请用 --install 跑全。")
            return EXIT_ENV
        print("RESULT: CLEAN")
        return EXIT_OK


def read_pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def package_version() -> str:
    """从源码树读 `__version__`，不 import（避免装没装都能跑，且不吃 init 的延迟导入）。"""
    text = (PROJECT / "src" / "allin_governance" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("ENV ERROR: __init__.py 里找不到 __version__")
    return match.group(1)


def check_version_single_source(result: Result) -> str:
    declared = read_pyproject()["project"]["version"]
    in_code = package_version()
    problems: list[str] = []
    if declared != in_code:
        problems.append(f"pyproject={declared} vs __init__={in_code}")

    head = CHANGELOG.read_text(encoding="utf-8")
    first = re.search(r"^## `allin-governance` (\S+)", head, re.M)
    if not first:
        problems.append("CHANGELOG 首条标题里找不到版本号")
    elif first.group(1) != declared:
        problems.append(f"CHANGELOG 首条={first.group(1)} vs pyproject={declared}")

    marked = re.search(r"当前版本 `([^`]+)`", README.read_text(encoding="utf-8"))
    if not marked:
        problems.append("README 里找不到「当前版本 `x`」声明")
    elif marked.group(1) != declared:
        problems.append(f"README 当前版本={marked.group(1)} vs pyproject={declared}")

    if problems:
        result.fail("版本单一来源", "；".join(problems))
    else:
        result.ok("版本单一来源", f"{declared}（pyproject / __init__ / CHANGELOG / README 四处一致）")
    return declared


def check_dist_freshness(result: Result, version: str) -> None:
    """dist/ 里只许有当前版本的产物。

    `twine upload dist/*` 会把目录里所有东西一起传 —— 混进旧版本时 PyPI 对旧文件
    返回 400，命令整体失败，人却以为「这次没发出去」，而新文件其实已经上去了。
    """
    if not DIST.is_dir():
        result.fail("dist 目录", f"不存在：{DIST}（先跑 scripts/build_dist.py）")
        return
    stale = sorted(p.name for p in DIST.iterdir() if version not in p.name)
    if stale:
        result.fail(
            "dist 目录干净",
            f"混入非 {version} 的产物：{', '.join(stale)} —— `twine upload dist/*` 会连它们一起传",
        )
    else:
        result.ok("dist 目录干净", f"只含 {version} 的产物")


def check_artifacts(result: Result, version: str) -> tuple[Path | None, Path | None]:
    wheel = DIST / f"allin_governance-{version}-py3-none-any.whl"
    sdist = DIST / f"allin_governance-{version}.tar.gz"
    missing = [str(p.name) for p in (wheel, sdist) if not p.is_file()]
    if missing:
        result.fail("发布物齐备", f"缺少：{', '.join(missing)}")
        return (wheel if wheel.is_file() else None, sdist if sdist.is_file() else None)
    result.ok("发布物齐备", f"{wheel.name} / {sdist.name}")
    return wheel, sdist


def check_sdist_self_contained(result: Result, version: str, sdist: Path | None) -> None:
    if sdist is None:
        result.skip("sdist 自包含", "没有 sdist 可查")
        return
    mapping = read_pyproject().get("tool", {}).get("setuptools", {}).get("package-dir", {})
    external = {pkg: path for pkg, path in mapping.items() if str(path).startswith("..")}
    with tarfile.open(sdist, "r:gz") as tar:
        names = tar.getnames()
        member = tar.extractfile(f"allin_governance-{version}/pyproject.toml")
        inner = tomllib.loads(member.read().decode("utf-8")) if member else {}

    missing = []
    prefix = f"allin_governance-{version}/src/"
    for package in external:
        inside = prefix + package.replace(".", "/") + "/"
        if not any(name.startswith(inside) for name in names):
            missing.append(package)
    if missing:
        result.fail(
            "sdist 自包含",
            f"缺映射树：{', '.join(missing)} —— 典型原因是绕过 scripts/build_dist.py 直接 build --sdist",
        )
    else:
        result.ok("sdist 自包含", f"{len(external)} 棵映射树都在压缩包里")

    inner_mapping = inner.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    escaping = {k: v for k, v in inner_mapping.items() if str(v).startswith("..")}
    if escaping:
        result.fail(
            "sdist 已物化",
            f"package-dir 仍指向项目外：{escaping} —— 安装时必报 package directory does not exist",
        )
    else:
        result.ok("sdist 已物化", "package-dir 已改写为包内路径")


def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, **kwargs,  # type: ignore[arg-type]
    )


def check_twine(result: Result, version: str) -> None:
    probe = run([sys.executable, "-m", "twine", "--version"])
    if probe.returncode != 0:
        result.skip("twine check", "本解释器没装 twine（pip install -r requirements-release.txt）")
        return
    targets = [
        str(DIST / f"allin_governance-{version}-py3-none-any.whl"),
        str(DIST / f"allin_governance-{version}.tar.gz"),
    ]
    proc = run([sys.executable, "-m", "twine", "check", *targets])
    if proc.returncode != 0:
        result.fail("twine check", (proc.stdout + proc.stderr).strip()[:400])
    else:
        result.ok("twine check", "元数据与长描述通过")


def _venv_python(base: Path) -> Path:
    candidate = base / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not candidate.exists():
        raise SystemExit(f"ENV ERROR: venv 建好了但找不到解释器：{candidate}")
    return candidate


def install_and_smoke(result: Result, artifact: Path, label: str) -> None:
    """在一台「与仓无关」的 venv 里装这一个文件，再跑五个子命令。

    这是 1.0.0 事故唯一能判红的实验：`twine check` 与「装 wheel」都不会发现
    sdist 缺源码，只有真的从 sdist 装一次才会。
    """
    with tempfile.TemporaryDirectory(prefix="allin-preflight-") as tmp:
        env_dir = Path(tmp) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        python = _venv_python(env_dir)

        install = run([str(python), "-m", "pip", "install", "--quiet", str(artifact)])
        if install.returncode != 0:
            tail = (install.stdout + install.stderr).strip().splitlines()[-6:]
            result.fail(f"{label} 可安装", " | ".join(tail)[:500])
            return

        cli = env_dir / ("Scripts/allin-governance.exe" if sys.platform == "win32" else "bin/allin-governance")
        if not cli.exists():
            result.fail(f"{label} 可安装", f"装完了却没有入口点：{cli}")
            return

        smoke: list[tuple[str, list[str]]] = [
            ("--version", [str(cli), "--version"]),
            ("repocheck", [str(cli), "repocheck", "--help"]),
            ("scan", [str(cli), "scan", "--help"]),
            ("deps", [str(cli), "deps", "--help"]),
            ("verify", [str(cli), "verify", "--help"]),
        ]
        init_dir = Path(tmp) / "scaffold"
        init_dir.mkdir()
        smoke.append(("init", [str(cli), "init", "--dry-run", str(init_dir)]))
        for name, argv in smoke:
            proc = run(argv)
            if proc.returncode != 0:
                tail = (proc.stdout + proc.stderr).strip().splitlines()[-4:]
                result.fail(f"{label} 子命令 {name}", f"exit={proc.returncode} | " + " | ".join(tail)[:400])
                return
        result.ok(f"{label} 可安装", "五个子命令 + init --dry-run 全部 exit 0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_preflight",
        description="allin-governance 发版前置校验：版本一致 / 产物干净 / sdist 自包含 / 可安装",
    )
    parser.add_argument("--install", action="store_true",
                        help="追加干净 venv 安装（sdist + wheel）并跑子命令；发版前必须带这个")
    parser.add_argument("--json", action="store_true", help="输出机器可读结论")
    args = parser.parse_args(argv)

    if not PYPROJECT.is_file():
        print(f"ENV ERROR: 找不到 {PYPROJECT}", file=sys.stderr)
        return EXIT_ENV

    result = Result()
    version = check_version_single_source(result)
    check_dist_freshness(result, version)
    wheel, sdist = check_artifacts(result, version)
    check_sdist_self_contained(result, version, sdist)
    check_twine(result, version)

    if args.install:
        if sdist is not None:
            install_and_smoke(result, sdist, "sdist")
        if wheel is not None:
            install_and_smoke(result, wheel, "wheel")
    else:
        result.skip("安装实测", "未带 --install —— 发版前必须跑 python scripts/release_preflight.py --install")

    code = result.report()
    if args.json:
        print(json.dumps({"version": version, "rows": result.rows, "exit": code}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
