"""allin-governance —— 治理中枢的命令行入口。

**单一入口 + 子命令**，不是每个能力发一个包。理由见 REC-AU-21 D1.2：
`repocheck` 的 PyPI 名字已被无关第三方占用（Dario Giovannetti 的
github.com/kynikos/repocheck），而它本来是本仓零依赖、30 条规则、自带 CLI 的完整件 ——
与其改名重发一个新包、多维护一个发布面，不如把它收成一个子命令。

    allin-governance repocheck <目录>      # 仓库体检（30 条规则）
    allin-governance repocheck --help
    allin-governance --version

设计约束（都是本仓纪律的直接落地）：
* **零第三方运行时依赖** —— 治理工具要在「什么都没装的机器」上跑得起来，
  否则「可复制」是空话。
* **源码只有一份** —— repocheck 的真身在仓内 `tools/repocheck/`，
  打包时由 pyproject 的 package-dir 映射进本包，**不复制**。
  两份代码必然漂移，这是本仓吃过亏的（「派生副本手抄必漂」）。
* **退出码原样透传** —— 门禁与体检的价值全在退出码上，任何包装层都不得改写它。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["main", "SUBCOMMANDS"]

__version__ = "0.0.0a0"


def _repocheck_dir() -> Path:
    """repocheck 源码目录，两种运行形态各有一个落点。

    为什么要两个候选（2026-10-31 实测踩到）：
      repocheck 的源码真身在仓内 `tools/repocheck/`，打包时由 pyproject 的
      `package-dir` **映射**成包内的 `_repocheck/` —— 注意是**映射不是复制**，
      所以只有装成 wheel 之后包内才会出现 `_repocheck/`。
      而从源码树直接跑（`python -m allin_governance`、跑 pytest、`pip install -e`）
      时包内那个目录**根本不存在**，于是「找不到源码目录」—— 开发者与 CI 都无法测试。

      这不是用两个副本糊过去：两个候选指向**同一份文件**（映射关系），
      只是「源码树形态」与「安装形态」的路径不同。取第一个存在的即可。

    顺序：包内优先（安装形态，最终用户实际走的路径），源码树兜底（开发/测试）。
    """
    packaged = Path(__file__).resolve().parent / "_repocheck"
    if packaged.is_dir():
        return packaged
    # 源码树形态：packages/allin-governance/src/allin_governance/cli.py
    #   parents[0]=allin_governance  [1]=src  [2]=allin-governance  [3]=packages  [4]=仓根
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tools" / "repocheck"
        if candidate.is_dir() and (candidate / "cli.py").is_file():
            return candidate
    return packaged  # 都不在：交回包内路径，让调用方报出那个「应该在哪」的位置


def _run_repocheck(argv: list[str]) -> int:
    """把参数原样交给 repocheck 并透传退出码。

    为什么要把目录塞进 `sys.path`，而不是改成相对导入：
      repocheck 的 13 个模块之间是**平铺导入**（`import scanner`、`from rulebase import RANK`、
      `from _optional import ...`）。改成相对导入要动全部 13 个文件，
      而它同时还要在仓内以 `python tools/repocheck/main.py` 的**脚本**形态运行
      （`scripts/run_all_gates.sh` 就是这么调的）—— 脚本形态下没有父包，相对导入直接失败。
      一次改动同时要满足「包内导入」与「脚本直跑」两种形态，最稳的做法是保持平铺、
      在包这一侧把目录补进 sys.path。这样仓内那份源码一个字都不用改。
    """
    here = _repocheck_dir()
    if not here.is_dir():
        print(
            f"ENV ERROR: 找不到 repocheck 源码目录：{here}\n"
            "  这通常意味着安装包没被打全。请重装，或从源码目录运行。",
            file=sys.stderr,
        )
        return 3

    entry = str(here)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        # 延迟导入：先补 path 再 import，否则平铺导入（import scanner 等）会失败。
        # 注意导入名是 `cli` 而不是 `allin_governance._repocheck.cli` ——
        # 因为 repocheck 的模块彼此按**顶层名**互相导入（`from rulebase import RANK`），
        # 走包路径导入会让那些平铺导入找不到模块。
        import cli as repocheck_cli  # type: ignore[import-not-found]

        return int(repocheck_cli.main(argv))
    except SystemExit as exc:  # argparse 的 --help / 参数错误走 SystemExit，需透传
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    finally:
        # 不留污染：本次调用结束后把这一个条目摘掉
        if added:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _cmd_repocheck(argv: list[str]) -> int:
    return _run_repocheck(argv)


#: 子命令表。新增能力只需在这里加一行，**不要**新开一个顶层入口点。
SUBCOMMANDS: dict[str, tuple[str, object]] = {
    "repocheck": ("离线仓库体检：30 条规则，给出 0-10 健康分与 error/warn/info 三级问题", _cmd_repocheck),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="allin-governance",
        description="工作区治理中枢：可执行门禁 + 文档枢纽契约 + 仓库体检",
        epilog="子命令详细用法：allin-governance <子命令> --help",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"allin-governance {__version__}")
    # 子命令用 REMAINDER 接收，避免二次解析吃掉 repocheck 自己的参数
    parser.add_argument("subcommand", nargs="?", choices=sorted(SUBCOMMANDS), help="要执行的子命令")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="透传给子命令的参数")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    try:
        parsed = parser.parse_args(argv)
    except SystemExit as exc:  # --version / --help / 非法子命令
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)

    if parsed.subcommand is None:
        parser.print_help()
        return 0

    _description, handler = SUBCOMMANDS[parsed.subcommand]
    return int(handler(parsed.args))  # type: ignore[operator]


if __name__ == "__main__":
    raise SystemExit(main())
