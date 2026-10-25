"""repocheck 命令行入口：参数解析、输出分发、退出码。

依赖方向单向：``main → cli → scanner → {scanctx, rulebase, rules_*, report}``。
本模块**不 import tkinter**，因此在无显示器环境里也能安全使用。

退出码
------
``0`` 通过　``1`` 触发 ``--fail-on``　``2`` 参数错误（argparse）
``3`` 环境或内部错误（根目录不存在、没发现项目、写文件失败）
"""

from __future__ import annotations

import argparse
import os
import sys

import report
import scanner
from _optional import PACKAGE_NAMES, missing_packages
from rulebase import RANK


# ---------------------------------------------------------------------------
# 参数类型校验
# ---------------------------------------------------------------------------

def _fail_on(value: str) -> str:
    """校验 ``--fail-on`` 取值。"""
    spec = value.strip().lower()
    if spec in ("none", "any", "error", "warn"):
        return spec
    if spec.startswith("score:"):
        raw = spec.split(":", 1)[1]
        try:
            float(raw)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"score 阈值必须是数字，收到 {raw!r}") from None
        return spec
    raise argparse.ArgumentTypeError(
        f"取值非法：{value!r}（可选 none / any / error / warn / score:N）")


def _severity(value: str) -> str:
    spec = value.strip().lower()
    if spec not in RANK:
        raise argparse.ArgumentTypeError(
            f"取值非法：{value!r}（可选 info / warn / error）")
    return spec


def _rule_ids(value: str) -> tuple[int, ...]:
    """解析 ``--skip-rules 3,7,19``。"""
    ids: list[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"规则 id 必须是整数，收到 {chunk!r}") from None
    known = {rule.id for rule in scanner.RULES}
    unknown = sorted(set(ids) - known)
    if unknown:
        raise argparse.ArgumentTypeError(
            f"不存在的规则 id：{unknown}（有效范围 1-{len(scanner.RULES)}）")
    return tuple(ids)


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"必须是正整数，收到 {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"必须 ≥1，收到 {number}")
    return number


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

DESCRIPTION = """\
repocheck —— 离线仓库体检。

对一个根目录下的一级子目录逐个体检，输出 30 条规则的问题清单、健康分与
建议。全程只读本地文件与只读 git 命令，不联网、不执行项目代码。
"""

EPILOG = """\
示例
----
  repocheck                          启动图形界面
  repocheck G:/repos                 体检 G:/repos 下全部项目（文本报告）
  repocheck . --format json -o r.json    输出 JSON 报告到文件
  repocheck . --fail-on error        发现 error 级问题时退出码为 1（可进 CI）
  repocheck . --fail-on score:8.0    任一项目低于 8 分即失败
  repocheck . --min-severity warn    只显示 warn 及以上
  repocheck . --skip-rules 27,28     临时豁免低价值规则
  repocheck --dump-profile --json    查看规则清单与可选依赖能力
"""


def build_parser() -> argparse.ArgumentParser:
    """构造 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        prog="repocheck",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "root", nargs="?", default=None,
        help="根目录；**省略则启动 GUI**（命令行模式需显式给出）")

    parser.add_argument(
        "--exclude", action="append", default=[], metavar="NAME",
        help="额外排除的目录名，可重复或用逗号分隔")
    parser.add_argument(
        "--depth", type=_positive_int, default=2, metavar="N",
        help="识别项目时向下寻找 .py 的最大层级（默认 2）")
    parser.add_argument(
        "--format", dest="fmt", choices=("text", "json", "csv", "html"),
        default="text", help="输出格式（默认 text）")
    parser.add_argument(
        "--json", action="store_true", help="等价于 --format json")
    parser.add_argument(
        "--output", "-o", default=None, metavar="PATH",
        help="写入文件；省略则输出到标准输出")
    parser.add_argument(
        "--fail-on", type=_fail_on, default="none", metavar="WHEN",
        help="none / any / error / warn / score:N（默认 none，即永远返回 0）")
    parser.add_argument(
        "--min-severity", type=_severity, default="info", metavar="LEVEL",
        help="只显示该级别及以上（info / warn / error，默认 info）")
    parser.add_argument(
        "--skip-rules", type=_rule_ids, default=(), metavar="IDS",
        help="逗号分隔的规则 id，临时豁免误报")
    parser.add_argument(
        "--workers", type=_positive_int, default=1, metavar="N",
        help="按项目并发数（默认 1；IO 与子进程为主，4~8 通常最快）")
    parser.add_argument(
        "--no-color", action="store_true", help="关闭 ANSI 颜色")
    parser.add_argument(
        "--dump-profile", action="store_true",
        help="打印规则清单与能力矩阵（不扫描）")
    parser.add_argument(
        "--version", action="version",
        version=f"repocheck {scanner.__version__}")
    return parser


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    return build_parser().parse_args(argv)


# ---------------------------------------------------------------------------
# 输出辅助
# ---------------------------------------------------------------------------

def _ensure_streams() -> None:
    """windowed exe 下 stdout 可能为 None；同时统一成 UTF-8 避免 GBK 崩。"""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _use_color(args: argparse.Namespace) -> bool:
    """是否输出 ANSI 颜色：写文件、管道、显式关闭时一律不用。"""
    if getattr(args, "no_color", False) or args.output:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def _emit_stdout(text: str) -> None:
    """写标准输出。

    即使 ``reconfigure`` 没生效（冻结包、被包装的流），也不能因为一个 ``✓``
    让整份报告崩掉 —— 编码不支持时降级为 ``replace``。
    """
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding, "replace"))


def _write(text: str, path: str | None, *, bom: bool = False) -> None:
    """写文件或标准输出。CSV 写文件时用 UTF-8 BOM 以便 Excel 直接打开。"""
    if path:
        encoding = "utf-8-sig" if bom else "utf-8"
        with open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        return
    if bom:
        _emit_stdout("\ufeff")
    # Windows 上 sys.stdout 是文本模式，会把 \n 转成 \r\n；若原文本已是 \r\n
    # （csv 模块默认），就会变成 \r\r\n 让管道读取多出空行。先归一成 \n。
    _emit_stdout(text.replace("\r\n", "\n"))
    if not text.endswith("\n"):
        _emit_stdout("\n")


def _format_profile(profile: dict) -> str:
    """``--dump-profile`` 的人类可读版。"""
    lines = [
        f"{profile['tool']} {profile['version']}（schema {profile['schema']}，规则即数据）",
        "",
    ]
    for rule in profile["rules"]:
        flags = []
        if rule["requires_git"]:
            flags.append("需 git")
        if rule["requires"]:
            flags.append("可选依赖 " + "/".join(rule["requires"]))
        suffix = f"　[{' ; '.join(flags)}]" if flags else ""
        lines.append(
            f"  [{rule['id']:>2}] {rule['severity']:<5} {rule['label']}{suffix}")
        lines.append(f"        {rule['criteria']}")
    lines.append("")
    lines.append("排除目录：" + ", ".join(profile["exclude_dirs"]))
    lines.append("项目标记：" + ", ".join(profile["project_markers"]))
    lines.append("评分公式：" + profile["score_formula"]
                 + f"（权重 {profile['severity_weights']}）")
    lines.append(f"分数上限：无 .git {profile['caps']['no_git']} / "
                 f"降级或异常 {profile['caps']['partial']}")
    disabled = [PACKAGE_NAMES[k] for k, ok in profile["optional"].items() if not ok]
    lines.append("可选依赖：" + ("全部就绪" if not disabled
                            else "未安装 " + ", ".join(disabled) + "（走内置降级实现）"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    """按解析好的参数执行，返回退出码。"""
    # 冻结包 / GBK 控制台都可能让 stdout 用的是本地编码，先统一成 UTF-8
    _ensure_streams()

    if args.dump_profile:
        profile = scanner.dump_profile()
        text = report.dumps(profile) if (args.json or args.fmt == "json") \
            else _format_profile(profile)
        try:
            _write(text, args.output)
        except OSError as exc:
            print(f"错误：写入失败：{exc}", file=sys.stderr)
            return 3
        return 0

    root = args.root or "."
    if not os.path.isdir(root):
        print(f"错误：根目录不存在或不是目录：{root}", file=sys.stderr)
        return 3

    exclude: list[str] = []
    for chunk in args.exclude:
        exclude.extend(part.strip() for part in chunk.split(",") if part.strip())

    results = scanner.scan(
        root,
        exclude=exclude,
        depth=args.depth,
        skip_ids=args.skip_rules,
        workers=args.workers,
    )
    if not results:
        print(f"未发现任何项目：{root}", file=sys.stderr)
        return 3

    summary = report.summarize(results)
    fmt = "json" if args.json else args.fmt

    if fmt == "json":
        payload = report.to_payload(
            results, root=root, version=scanner.__version__,
            schema=scanner.SCHEMA_VERSION,
            optional=dict(scanner.dump_profile()["optional"]))
        text = report.dumps(payload)
    elif fmt == "csv":
        text = report.render_csv(results, min_severity=args.min_severity)
    elif fmt == "html":
        text = report.render_html(
            results, root=root, min_severity=args.min_severity,
            summary=summary, version=scanner.__version__)
    else:
        text = report.render_text(
            results, root=root, min_severity=args.min_severity,
            color=_use_color(args), summary=summary)

    try:
        _write(text, args.output, bom=(fmt == "csv"))
    except OSError as exc:
        print(f"错误：写入失败：{exc}", file=sys.stderr)
        return 3

    # 降级提示走 stderr，不污染 CSV/JSON 的机器可读输出
    if fmt == "json" and missing_packages():
        print("提示：未安装可选依赖 " + ", ".join(missing_packages())
              + "，相关规则使用内置降级实现", file=sys.stderr)

    return scanner.evaluate_fail_on(results, args.fail_on)


def main(argv: list[str] | None = None) -> int:
    """命令行主入口（供 ``main.py`` 与 ``python -m`` 调用）。"""
    _ensure_streams()
    return run(parse(argv))


if __name__ == "__main__":
    raise SystemExit(main())
