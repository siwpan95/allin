"""发布物自包含性的回归测试（2026-11-24 事故封印）。

**为什么需要这个文件**：`allin-governance` 的 sdist 只有走 `scripts/build_dist.py`
的「物化映射树」流程才自包含。直接用 `python -m build --sdist` 出来的包**构建成功、
twine check 通过、装不上** —— 2026-11-24 的 1.0.0 就是这么发出去的：

    error: package directory '..\\..\\tools\\repocheck' does not exist

判据放在这里而不是 CI 的新 job 里，理由是**成本**：`dist/` 被 `.gitignore` 忽略，
干净检出里根本不存在，本文件于是 skip（0 成本）；而任何一个准备发版的人，手上必然
有刚构建出来的 `dist/`，那一刻这条判据就会真的判。这正是缺陷发生的时点。

跳过时使用 `pytest.skip` 并写明原因 —— 按本仓口径，SKIP 不是 PASS。
"""

from __future__ import annotations

import tarfile
import tomllib
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT / "pyproject.toml"
DIST = PROJECT / "dist"


def _declared() -> tuple[str, dict[str, str]]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = data["project"]["version"]
    mapping = data.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    return version, mapping


def _sdist() -> Path:
    version, _ = _declared()
    candidate = DIST / f"allin_governance-{version}.tar.gz"
    if not candidate.is_file():
        pytest.skip(
            f"dist/ 里没有当前版本 {version} 的 sdist —— 干净检出或尚未构建，"
            "本判据不适用（SKIP 不是 PASS；发版前必须跑 scripts/release_preflight.py）"
        )
    return candidate


def test_sdist_carries_every_mapped_package_tree() -> None:
    """sdist 必须把每棵跨目录映射树都装进去（缺一棵 = 装的时候直接报错）。"""
    version, mapping = _declared()
    external = {pkg: path for pkg, path in mapping.items() if path.startswith("..")}
    assert external, "pyproject 里没有任何跨目录映射 —— 本测试的前提已变，请复核"

    with tarfile.open(_sdist(), "r:gz") as tar:
        names = tar.getnames()

    prefix = f"allin_governance-{version}/src/"
    for package, source in sorted(external.items()):
        inside = prefix + package.replace(".", "/") + "/"
        hits = [name for name in names if name.startswith(inside)]
        assert hits, (
            f"映射树缺失：{package}（源 {source}）没有进 sdist —— "
            "典型原因是绕过 scripts/build_dist.py 直接 `python -m build --sdist`，"
            "setuptools 不收项目根之外的文件。"
        )


def test_sdist_pyproject_is_materialized() -> None:
    """物化后的 sdist 里，`package-dir` 不许再指向 `..`。

    这条比「文件在不在」更靠前：只要 `..` 还在，安装期就会去解析一个解包后
    不存在的相对路径 —— 那是 1.0.0 的失败形态（`package directory ... does not exist`）。
    """
    version, _ = _declared()
    with tarfile.open(_sdist(), "r:gz") as tar:
        member = tar.extractfile(f"allin_governance-{version}/pyproject.toml")
        assert member is not None, "sdist 里没有 pyproject.toml"
        data = tomllib.loads(member.read().decode("utf-8"))

    mapping = data.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    escaping = {key: value for key, value in mapping.items() if str(value).startswith("..")}
    assert not escaping, (
        "sdist 的 package-dir 仍指向项目外：" + repr(escaping)
        + " —— 安装时必然报 `package directory ... does not exist`"
    )
