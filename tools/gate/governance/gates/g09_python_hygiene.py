"""Gate g09 -- Python-side encoding and escape discipline.

Three recorded accident classes, each now an exit code:

* ``WIN1252``/GBK defaults: ``json.load(open(path))`` reads and writes the wrong
  encoding on a Chinese Windows console, silently writing a file that later
  fails to parse. Every text open must name ``utf-8``.
* escape artefacts: a Windows-looking path inside a non-raw string turns
  ``\\a`` into BEL and ``\\d`` into a mere warning; compiling with
  ``-W error::SyntaxWarning`` promotes those silent mistakes to failures.
* console crashes: a CLI that prints non-ASCII without reconfiguring stdout dies
  with UnicodeEncodeError on a GBK console -- and never when output is piped.

Scope: tracked ``*.py`` files outside vendored and archived trees.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g09-python-hygiene"
TITLE = "governance: Python encoding, escape, and console discipline"

EXEMPT_PREFIXES = (".agents/notes/archived/", "vendor/", "node_modules/")

#: Text I/O that must name its encoding. Binary variants are excluded: they take
#: no encoding argument at all.
IO_CALL = re.compile(r"\b(open|read_text|write_text)\s*\(")
ENCODING_HINT = re.compile(r"encoding\s*=")
#: A drive-letter path; legal only inside a raw string, where ``\\d`` stays two characters.
DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
RAW_PREFIX = re.compile(r"(?<![A-Za-z0-9_])(?:rb|br|rf|fr|r)$")
ANNOTATION = "gov-python: allow"
#: Lines that carry the check's own pattern definitions stay out of their own judgment.
PATTERN_DEFINITION = re.compile(r"re\.compile\(")
#: Readers that own their encoding explicitly, so callers cannot get it wrong.
SAFE_HELPERS = ("govlib.read_text(", "govlib.tracked_files(", "govlib.staged_blobs(")
LITERAL = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")


def local_encoding_helpers(text: str) -> set:
    """Names of functions defined *in this file* whose body names an encoding.

    Why: a gate may define its own ``read_text(path)`` wrapper that hard-codes
    ``encoding="utf-8"`` and then call it everywhere. Judging the *call site*
    alone reports that wrapper as a defect — a false positive that trains
    people to ignore the gate (debug-53). Recognising the local helper keeps
    the rule aimed at real stdlib calls. (2026-09-28; first hit by
    ``g15_docs_contract.py``.)
    """
    names = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = ast.get_source_segment(text, node) or ""
            if ENCODING_HINT.search(segment):
                names.add(node.name + "(")
    return names


def strip_literals(line: str) -> str:
    """The code skeleton of one line: quoted text and trailing comments removed.

    Prose and fixture text inside string literals mention ``open(path)`` all the
    time; only a call in real code can be an encoding defect.
    """
    without_comment = line.split("#", 1)[0] if "#" in line else line
    return LITERAL.sub("''", without_comment)


def in_raw_literal(line: str, offset: int) -> bool:
    """Whether the offset sits inside a literal whose opening quote carries an ``r`` prefix."""
    quote = max(line.rfind('"', 0, offset), line.rfind("'", 0, offset))
    if quote <= 0:
        return False
    return RAW_PREFIX.search(line[:quote]) is not None


def scan(root: Path, *, compile_check: bool = True) -> Report:
    """Judge every tracked Python file."""
    report = Report(title=TITLE)
    for path in govlib.tracked_files(root):
        if not path.endswith(".py") or path.startswith(EXEMPT_PREFIXES):
            continue
        text = govlib.read_text(root / path)
        if text is None:
            report.exempt("unreadable or binary")
            continue
        report.scanned += 1
        lines = text.splitlines()
        local_safe = local_encoding_helpers(text)
        in_docstring = False
        for index, line in enumerate(lines, start=1):
            fences = line.count('"""') + line.count("'''")
            if in_docstring:
                if fences % 2 == 1:
                    in_docstring = False
                continue
            if fences % 2 == 1 and line.lstrip().startswith(('"""', "'''", "r\"\"\"", "r'''")):
                in_docstring = True
                report.exempt("docstring prose")
                continue
            if ANNOTATION in line or PATTERN_DEFINITION.search(line):
                report.exempt("annotation or pattern definition")
                continue
            code = strip_literals(line)
            if (IO_CALL.search(code)
                    and not any(helper in code for helper in SAFE_HELPERS)
                    and not any(helper in code for helper in local_safe)):
                window = "\n".join(lines[index - 1:index + 2])
                if ENCODING_HINT.search(window) is None:
                    report.block("io-without-encoding", path, index, line)
                    continue
            for match in DRIVE_PATH.finditer(line):
                if in_raw_literal(line, match.start()):
                    report.exempt("raw string literal")
                    continue
                report.block("escaped-path-literal", path, index, line)
        if not compile_check:
            report.exempt("syntax check disabled")
            continue
        completed = subprocess.run(
            [sys.executable, "-W", "error::SyntaxWarning", "-m", "py_compile", str(root / path)],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stdout.decode("utf-8", "replace").strip().splitlines()
            report.block("syntax-warning", path, 1, detail[-1] if detail else "py_compile failed")
        else:
            report.exempt("compiles without warnings")
    return report


def selfcheck() -> int:
    """Prove each discipline fires, and that correct code stays quiet."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/read.py",
                      "import json\n"
                      "from pathlib import Path\n"
                      "def load(path: Path) -> object:\n"
                      "    return json.loads(path.read_text(encoding='utf-8'))\n"
                      "def note() -> str:\n"
                      "    return r'sample C:\\temp\\draft'\n")
        report = scan(sandbox.path)
        check.quiet("utf-8 and raw literals", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/bad_open.py", "import json\n"
                                           "def load(path):\n"
                                           "    return json.load(open(path))\n")
        report = scan(sandbox.path)
        check.detects("open() without an explicit encoding",
                      any(finding.kind == "io-without-encoding" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        # 本文件自定义的 read_text 包装已写死 encoding：调用点不该被判红（2026-09-28
        # g15_docs_contract.py 首个命中者）。反例必须与上面那条「能抓」用例成对存在。
        sandbox.write("tools/local_helper.py",
                      "import io\n"
                      "def read_text(path):\n"
                      "    with io.open(path, 'r', encoding='utf-8') as handle:\n"
                      "        return handle.read()\n"
                      "def load(path):\n"
                      "    return read_text(path)\n")
        report = scan(sandbox.path)
        check.quiet("locally defined encoding helper",
                    any(finding.kind == "io-without-encoding" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        # 同名但**没有** encoding 的本地包装仍须判红 —— 否则豁免就过宽了（debug-53）。
        sandbox.write("tools/local_helper_bad.py",
                      "import io\n"
                      "def read_text(path):\n"
                      "    return io.open(path, 'r').read()\n"
                      "def load(path):\n"
                      "    return read_text(path)\n")
        report = scan(sandbox.path)
        check.detects("locally defined helper that drops the encoding",
                      any(finding.kind == "io-without-encoding" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        # 夹具里不写连续的盘符字面量：那会被 g01-paths 判为「写死本机路径」（2026-09-28 修，
        # 源起 g09 自检夹具被 g01 抓到 —— 修数据而不是给 g01 开豁免口子，见 RULES.md §五）。
        _drive = "C" + ":"
        sandbox.write("tools/bad_path.py", "SAMPLE = 'see /opt/logs/draft'\n"
                                           "OTHER = 'see " + _drive + "\\\\temp\\\\draft'\n")  # gov-python: allow
        report = scan(sandbox.path)
        check.detects("an escape-prone path literal",
                      any(finding.kind == "escaped-path-literal" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/bad_syntax.py", "SAMPLE = 'C:\\docs\\report'\n")  # gov-python: allow
        report = scan(sandbox.path)
        check.detects("a syntax warning promoted to an error",
                      any(finding.kind == "syntax-warning" for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--no-compile", dest="compile_check", action="store_false", help="skip py_compile")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, compile_check=args.compile_check)
    baseline = Baseline(baseline_path)
    if args.write_baseline:
        baseline.write(report.findings)
        print(f"{TITLE}: baseline written with {len(report.findings)} finding(s) -> {baseline_path}")
        return EXIT_OK
    if not args.no_baseline:
        baseline.load()
    new_findings = report.findings if args.no_baseline else baseline.filter_new(report.findings)
    report.findings = report.findings if args.list_all else new_findings
    print(report.render().splitlines()[0] if args.quiet else report.render())
    return EXIT_BLOCKING if new_findings else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
