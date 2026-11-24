"""allin-governance —— 治理中枢的命令行入口。

**单一入口 + 子命令**，不是每个能力发一个包。理由见 REC-AU-21 D1.2：
`repocheck` 的 PyPI 名字已被无关第三方占用（Dario Giovannetti 的
github.com/kynikos/repocheck），而它本来是本仓零依赖、30 条规则、自带 CLI 的完整件 ——
与其改名重发一个新包、多维护一个发布面，不如把它收成一个子命令。

    allin-governance repocheck <目录>      # 仓库体检（30 条规则）
    allin-governance repocheck --help
    allin-governance init [目录]           # 生成可跑的最小治理骨架（14 道门禁）
    allin-governance verify [目录]         # 复核快照是否仍与生成清单一致
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

from . import _stdio, __version__

# `__version__` 从包根取，**不在这里再定义一次**：两处各写一个版本号
# 迟早对不上，而「包说 a1、CLI 说 a0」这种漂移没人会在发布前发现。
__all__ = ["main", "SUBCOMMANDS"]


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


def _root_to_positional(argv: list[str]) -> list[str]:
    """把 `--root X` 归一成位置参数 X —— 统一子命令契约（SPEC-206 §3 A7）。

    背景：`scan` / `deps` 原生用 `--root`，`repocheck` / `verify` 原生用位置参数。
    同一套 CLI 里两种写法会让下游「按记忆猜」，2026-11-25 的换机 E2E 实测正是
    照 plan 写 `scan <repos>` / `repocheck <repos>` 双双 exit 2。
    这里让**两者都接受**：`--root` 只是位置参数的别名，不改变底层工具。
    """
    out: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root" and i + 1 < len(argv):
            out.append(argv[i + 1])
            i += 2
            continue
        if a.startswith("--root="):
            out.append(a.split("=", 1)[1])
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def _cmd_repocheck(argv: list[str]) -> int:
    return _run_repocheck(_root_to_positional(argv))


def _cmd_verify(argv: list[str]) -> int:
    """复核 `init` 生成的快照是否仍与 GENERATED.json 一致。"""
    from . import init as init_module

    return init_module.verify_main(_root_to_positional(argv))


def _cmd_init(argv: list[str]) -> int:
    """生成治理骨架。

    延迟导入 `init`：它要 import 一套模板常量，而 `--version` / `--help`
    这些高频短路径不该为此付启动成本（也避免与 `_package_version()` 形成环）。
    """
    from . import init as init_module

    return init_module.main(argv)


def _shared_dir() -> Path:
    """`tools/_shared` 的源码树落点（安装态下走包内 `_toolkit`，不会用到这里）。"""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tools" / "_shared"
        if candidate.is_dir() and (candidate / "scan_repos.py").is_file():
            return candidate
    return Path(__file__).resolve().parent / "_toolkit"


def _toolkit_modules():
    """取 `scan_repos` / `deps_doctor`，安装态与源码树态各一条路。

    与 `_github_modules()` 同源问题：`_toolkit` 由 `package-dir` 映射进 wheel，
    源码树里不存在。此前的实现无条件 `from ._toolkit import ...`，因此
    `allin-governance scan --help` 只在**装完之后**可用 —— 开发态与测试里必炸。
    存量缺口自 a8（工具随包分发）起就在，2026-11-24 的「每个子命令都要跑一次」
    测试才把它照出来。
    """
    try:
        from ._toolkit import deps_doctor, scan_repos  # type: ignore[import-not-found]
        return scan_repos, deps_doctor
    except (ImportError, ValueError):
        pass

    entry = str(_shared_dir())
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        import deps_doctor as flat_deps  # type: ignore[import-not-found]
        import scan_repos as flat_scan  # type: ignore[import-not-found]
        return flat_scan, flat_deps
    finally:
        if added:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _cmd_scan(argv: list[str]) -> int:
    """发布区扫盘：项目指纹、重复检出、迁移残留（Python 版）。"""
    scan_repos, _deps = _toolkit_modules()
    return scan_repos.main(argv)


def _cmd_deps(argv: list[str]) -> int:
    """依赖体检：requirements 声明 · 解释器实装 · 仓内 import 三者对账。"""
    _scan, deps_doctor = _toolkit_modules()
    return deps_doctor.main(argv)


def _secret_scan():
    """取 `secret_scan` 模块（安装态走包内 `_secret_scan`，源码树走仓内路径）。

    与 `_github_modules()` 同一纪律：映射目录只在 wheel 里存在，
    源码树形态必须能跑 —— 否则 `pytest packages/allin-governance` 直接炸。
    """
    try:
        from ._secret_scan import scanner  # type: ignore[import-not-found]
        return scanner
    except (ImportError, ValueError):
        pass

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "tools" / "secret_scan"
        if candidate.is_dir() and (candidate / "scanner.py").is_file():
            entry = str(parent / "tools")
            added = entry not in sys.path
            if added:
                sys.path.insert(0, entry)
            try:
                from secret_scan import scanner as flat  # type: ignore[import-not-found]
                return flat
            finally:
                if added:
                    try:
                        sys.path.remove(entry)
                    except ValueError:
                        pass
    raise ImportError("找不到 secret_scan/scanner.py（安装态与源码态都不在）")


def _facts_modules():
    """取 `measure` / `verify_facts` 两个模块，安装态与源码树态各一条路。

    与 `_github_modules()` 同一纪律：`_facts/` 是打包时由 `package-dir` 从
    `tools/facts/` 映射出来的，源码树里**不存在** `allin_governance._facts`。
    两个模块都已改为「相对导入优先、平铺导入兜底」，故两条路都能跑。

    为什么这两个进公共核：换机第 0 步是「说清这台机器有什么」——
    盘、运行时、PATH 实际解析。`measure` 找不到仓根时走**无仓模式**
    （只采集本机事实，仓与远端两段显式标注「未采集 ≠ 0」），所以新机器
    装完包、还没 clone 仓也能用。
    """
    try:
        from ._facts import measure, verify_facts  # type: ignore[import-not-found]

        return measure, verify_facts
    except (ImportError, ValueError):
        pass

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tools" / "facts"
        if candidate.is_dir() and (candidate / "measure.py").is_file():
            entry = str(candidate)
            added = entry not in sys.path
            if added:
                sys.path.insert(0, entry)
            try:
                from measure import main as measure_main  # type: ignore[import-not-found]
                from verify_facts import main as verify_main  # type: ignore[import-not-found]
            finally:
                if added:
                    try:
                        sys.path.remove(entry)
                    except ValueError:
                        pass
            return measure_main, verify_main
    raise ImportError("找不到 tools/facts（安装态与源码态都不在）")


def _cmd_facts(argv: list[str]) -> int:
    """机器事实：`measure` 采集本机、`verify` 校验分区文件的断言。

    分工与仓内脚本完全一致（判据只有一份）：`facts measure` → `tools/facts/measure.py`，
    `facts verify` → `tools/facts/verify_facts.py`（后者复用 g20 的判据实现，
    安装态从包内 `_gatesuite.gates.g20_facts` 取，不另写一套）。
    """
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "用法: allin-governance facts <measure|verify> [选项]\n"
            "  measure [--root <仓根>] [--out <文件>]   采集本机事实（无仓根时只采本机，仓段标注未采集）\n"
            "  verify  [--root <仓根>] [--file <文件>] [--all] [--json] [--selftest]\n"
            "         校验机器事实源里可机检的断言（PATH-EXISTS / COUNT）",
            file=sys.stderr,
        )
        return 2 if not argv else 0

    sub, rest = argv[0], argv[1:]
    measure_mod, verify_mod = _facts_modules()
    if sub == "measure":
        return measure_mod(rest) if callable(measure_mod) else measure_mod.main(rest)
    if sub == "verify":
        return verify_mod(rest) if callable(verify_mod) else verify_mod.main(rest)
    print(f"未知子命令: facts {sub}（可选 measure / verify）", file=sys.stderr)
    return 2


def _cmd_secrets_scan(argv: list[str]) -> int:
    """离线凭据扫描：21 条高精度规则 + 熵闸 + 仓库自有注解豁免。

    与 `scripts/scan-secrets.sh` 的分工：那个负责「本次变更新增行」（CI 门禁），
    这个负责「任意目录/历史快照的一次性体检」，不需要 gitleaks 二进制。
    """
    return _secret_scan().main(argv)


def _github_dir() -> Path:
    """`tools/github` 的源码树落点（安装态下应走包内 `_github`，不会用到这里）。"""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "tools" / "github"
        if candidate.is_dir() and (candidate / "github_release.py").is_file():
            return candidate
    return Path(__file__).resolve().parent / "_github"


def _github_modules():
    """取 `github_release` / `sync_repos` 两个模块，安装态与源码树态各一条路。

    与 `_repocheck_dir()` 同一纪律（2026-11-24 事故补）：`_github/` 是打包时由
    `package-dir` 映射出来的，**源码树里根本不存在** —— 原实现无条件
    `from ._github import ...`，于是 `pytest packages/allin-governance` 与
    开发态直接 `ModuleNotFoundError`。安装态另有一个更严重的缺陷：两个工具的
    `main()` 当时不接受参数，而这里传了 argv ⇒ `allin-governance github <cmd>`
    每次 TypeError（1.0.1 已发布版本实测，见 docs/记录/事故/）。
    """
    try:
        from ._github import github_release, sync_repos  # type: ignore[import-not-found]
        return github_release, sync_repos
    except (ImportError, ValueError):
        pass

    entry = str(_github_dir())
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        import github_release as flat_release  # type: ignore[import-not-found]
        import sync_repos as flat_sync  # type: ignore[import-not-found]
        return flat_release, flat_sync
    finally:
        if added:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _cmd_github(argv: list[str]) -> int:
    """GitHub 建仓/推送/三端巡检（gitee 为权威，单向 gitee → 本地 → GitHub）。

    子命令：whoami|list|create|public|remote|push|verify|sync（github_release.py）
    三端巡检：传 github-sync <list|pull|drift|sync> 走 sync_repos.py。
    令牌走 GITHUB_TOKEN 环境变量或 Windows GCM；工具本身不打印、不入库。
    """
    github_release, sync_repos = _github_modules()
    try:
        if argv and argv[0] == 'github-sync':
            return sync_repos.main(argv[1:])
        return github_release.main(argv)
    except SystemExit as exc:  # 两个工具都用 argparse：--help / 参数错误走 SystemExit
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)


#: 子命令表。新增能力只需在这里加一行，**不要**新开一个顶层入口点。
SUBCOMMANDS: dict[str, tuple[str, object]] = {
    "repocheck": ("离线仓库体检：30 条规则，给出 0-10 健康分与 error/warn/info 三级问题", _cmd_repocheck),
    "init": ("生成可跑的最小治理骨架：14 道门禁 + 文档四分类 + registry + 基线", _cmd_init),
    "verify": ("复核 init 生成的套装快照是否仍与 GENERATED.json 记载的一致", _cmd_verify),
    "scan": ("发布区扫盘：项目指纹 / 重复检出 / 迁移残留（只报告不处置）", _cmd_scan),
    "deps": ("依赖体检：requirements 声明 · 解释器实装 · 仓内 import 三者对账", _cmd_deps),
    "github": ("GitHub 建仓/推送/三端巡检（gitee 为权威）；github-sync 子命令走巡检器", _cmd_github),
    "secrets-scan": ("离线凭据扫描：21 条高精度规则 + 按字符集分档的熵闸（不需要 gitleaks 二进制）",
                     _cmd_secrets_scan),
    "facts": ("机器事实：采集本机（盘/运行时/工具链）＋ 校验分区文件断言（measure / verify）",
              _cmd_facts),
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
    # 第一件事：把控制台编码钉成 UTF-8。
    # 起因见 `_stdio` 的模块注释 —— Windows 上 cp1252 控制台遇到中文会
    # 在**打印阶段**抛 UnicodeEncodeError，于是「文件已经写好了」却以 exit 1 收场。
    # 放在这里而不是各子命令里：`--help` 与所有子命令共用同一条出口。
    _stdio.configure()
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
    # 子命令一律走 argparse（`--help` / 参数错误抛 SystemExit）。`main()` 的契约是
    # **返回 int**，所以在这里统一收口 —— 此前只有 repocheck 自己兜了，其余四个
    # （init/verify/scan/deps）会把 SystemExit 抛给调用方：命令行看不出问题，
    # 但任何以函数方式调用 `main()` 的地方（测试、嵌入方）行为与文档不一致。
    try:
        return int(handler(parsed.args))  # type: ignore[operator]
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)


if __name__ == "__main__":
    raise SystemExit(main())
