# -*- coding: utf-8 -*-
"""`PipCertifiUvBaseline.verify` 的 pip 版本判据：**两段版本号也必须判**。

## 为什么有这一条

2026-11-25 代码审查发现：`re.search(r"pip (\\d+\\.\\d+\\.\\d+)", r.stdout)` 只认**三段**版本，
而现代 pip 打印的是 `pip 26.3 from …`（**两段**）⇒ 两段版本永远解析不到 ⇒
**低于安全基线的 pip 静默不报**。这与同批修的 `text=True` 缺 `encoding` 是同一根因的另一面：
安全基线"静默跳过"，门禁绿得没有信号（最坏的一类缺陷 —— 比报错更难发现）。

## 怎么测（不 spawn 真 pip）

`probe()` 与 `pip --version` 都通过 `subprocess` 调 `sys.executable`。把 `PYTHONPATH` 指向
一个临时目录，里面放一个假 `pip` 包（`pip/__main__.py` 打印指定版本行）——子进程
`python -m pip --version` 会优先命中它，于是版本行与退出码都可任意伪造，而 `probe()`
仍走真解释器（`python --version` 不受 `PYTHONPATH` 里假 pip 的影响）。
certifi 探测（`-c "import certifi"`）在无 certifi 时 rc≠0，按设计跳过，不影响本判据。

## 判据要点

`ver_tuple()` 已把版本补成定长 3 元组（`26.3` → `(26, 3, 0)`），所以只要**正则**能吃两段，
元组比较天然正确 —— 本文件的用例就是钉这一条。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
TARGET = TOOLS / "security" / "venv_security.py"


def _load_module():
    """按唯一模块名加载被测文件（不占用 ``sys.modules`` 里的通用名）。"""
    uid = "_venv_security_under_test"
    if uid in sys.modules:
        return sys.modules[uid]
    spec = importlib.util.spec_from_file_location(uid, TARGET)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[uid] = mod
    spec.loader.exec_module(mod)
    return mod


vs = _load_module()


def _install_fake_pip(tmp_path: Path, monkeypatch, version_line: str, rc: int = 0) -> None:
    """让子进程的 `python -m pip --version` 输出 ``version_line``（rc 可控）。"""
    root = tmp_path / "fakepip"
    pkg = root / "pip"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__main__.py").write_text(
        "import sys\nsys.stdout.write({!r} + '\\n')\nsys.exit({})\n".format(version_line, rc),
        encoding="utf-8")
    prior = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv("PYTHONPATH", str(root) + (os.pathsep + prior if prior else ""))


def _pip_issues(tmp_path: Path, monkeypatch, version_line: str) -> list[str]:
    _install_fake_pip(tmp_path, monkeypatch, version_line)
    issues = vs.PipCertifiUvBaseline().verify(tmp_path, {"py": sys.executable})
    return [i for i in issues if i.startswith("pip ")]


def test_floor_is_the_documented_one():
    """用例的期望值锚在真实基线上，基线变了这里会立刻提示改用例（而不是静默失配）。"""
    assert vs.FLOORS["pip"] == (26, 2, 2)
    assert vs.ver_tuple("26.3") == (26, 3, 0), "ver_tuple 应把两段版本补齐成 3 元组"


@pytest.mark.parametrize("version_line,must_report,why", [
    # ★ 本条是本次缺陷的负对照：修复前（正则只认三段）这里**不报**，修复后必报
    ("pip 24.0 from /fake/site-packages/pip (python 3.12)", True, "两段版本且低于基线 26.2.2"),
    ("pip 9.0 from /fake/site-packages/pip (python 3.12)", True, "两段版本，远低于基线"),
    ("pip 26.2.1 from /fake/site-packages/pip (python 3.12)", True, "三段版本且低于基线（回归护栏）"),
    ("pip 26.3 from /fake/site-packages/pip (python 3.12)", False, "两段版本但高于基线"),
    ("pip 26.2.2 from /fake/site-packages/pip (python 3.12)", False, "三段版本等于基线（不小于）"),
])
def test_pip_version_floor_accepts_two_and_three_part(tmp_path, monkeypatch, version_line,
                                                      must_report, why):
    issues = _pip_issues(tmp_path, monkeypatch, version_line)
    if must_report:
        assert issues, f"{version_line!r} 应判红（{why}），却静默通过 —— 安全基线被跳过"
        assert any("<" in i for i in issues), f"应给出『低于基线』的理由，实得 {issues}"
    else:
        assert not issues, f"{version_line!r} 不该判红（{why}），实得 {issues}"
