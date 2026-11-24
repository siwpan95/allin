"""allin_governance.cli 的回归测试。

**测什么、为什么这样测**：
本包的价值几乎全在「能不能把参数与退出码**原样**交给 repocheck」上 ——
它是一个包装层，包装层最容易犯的错就是「吞掉退出码」或「吃掉参数」。
所以这里不测 repocheck 的 30 条规则（那是它自己的 test_scanner.py 的事），
只测包装边界：

1. `--version` 报得出版本；
2. 无参数时打帮助并退 0（不是报错）；
3. **退出码原样透传** —— 这是最重要的一条：CI 靠它判红绿，包装层改写它就等于伪造结论；
4. 子命令 `--help` 不崩（args 用 REMAINDER 接收，容易把 `--help` 吃掉）；
5. repocheck 源码目录**真的在包内**（打包没打全时立刻发现，而不是等用户装完才发现）。

跑法：``python -m pytest packages/allin-governance -q``
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from allin_governance import __version__  # noqa: E402
from allin_governance.cli import _repocheck_dir, main  # noqa: E402

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_has_exactly_one_source() -> None:
    """版本号只有一个来源：`pyproject.toml` 的 `project.version`。

    **2026-11-24 改写（1.0.0 发版当天）**：原守卫断言「必须是 `0.0.0aN` 占位系列」。
    它护的是发版**之前**的命名约定，一旦真的定版就必然自证为红 —— 而 1.0.0 就是
    在这条红灯下发布出去的（见 `docs/记录/事故/`）。把「约定」当「事实」校验，
    红的那天没人分得清是代码错了还是约定过期了。

    现在的判据回到这条测试的本意（原 docstring 自己写着「两处各写一个版本号迟早
    对不上，而没人会在发布前发现」）：**两处必须相等**，版式交给 PEP 440。
    """
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert __version__ == declared, (
        f"包内 __version__={__version__!r} 与 pyproject 的 version={declared!r} 不一致；"
        "发布物元数据会以 pyproject 为准，用户看到的是另一个版本号。"
    )
    assert not __version__.startswith("0.0.0a"), (
        "占位版本系列已在 1.0.0 终止；回退到 0.0.0aN 会让 PyPI 上出现倒序版本。"
    )


def test_no_arguments_prints_help_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """无参数不应报错：给帮助、退 0（CLI 的礼貌默认，也是打包验证的第一道）。"""
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "allin-governance" in out
    assert "repocheck" in out


def test_repocheck_source_dir_ships_inside_the_package() -> None:
    """repocheck 源码必须在包内 —— 打包漏文件时这里先红，而不是等用户装完。"""
    here = _repocheck_dir()
    assert here.is_dir(), f"repocheck dir missing: {here}"
    # 抽查两个核心模块：只查目录存在不够，目录可能是空的
    assert (here / "cli.py").is_file()
    assert (here / "scanner.py").is_file()


def test_exit_code_passes_through_untouched(tmp_path: Path) -> None:
    """**核心判据**：repocheck 非 0 退出时，包装层必须原样返回那个码。

    造一个必然触发 error 的目录（无 README / 无 git / 无依赖声明），
    用 --fail-on error 让它退 1，断言包装层返回的也是 1 —— 而不是 0 或别的什么。
    """
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "x.py").write_text("print(1)\n", encoding="utf-8")

    code = main(["repocheck", str(broken), "--fail-on", "error", "--no-color"])
    assert code == 1, f"exit code swallowed: expected 1, got {code}"


def test_repocheck_help_is_not_swallowed() -> None:
    """子命令的 --help 必须能到达 repocheck 自己（REMAINDER 容易把选项吃掉）。"""
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); "
         "from allin_governance.cli import main; raise SystemExit(main(['repocheck', '--help']))"
         % (Path(__file__).resolve().parent.parent / "src")],
        # 2026-11-08：Windows 下不指定 encoding 会按 GBK 解码子进程 UTF-8 输出，
        # 读线程抛 UnicodeDecodeError 后 stdout/stderr 变 None（与 pytest.ini 注释
        # 记录的教训同源）。显式 UTF-8 + replace，测试才不会假红。
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    assert "--fail-on" in combined, f"repocheck --help did not reach repocheck:\n{combined[:600]}"
    assert result.returncode == 0
