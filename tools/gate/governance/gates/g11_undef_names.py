"""Gate g11 -- a name that is never defined anywhere in the file.

``py_compile`` proves syntax, not resolution: "used but never imported", a
``str`` divided by a ``Path``, and a line lost by a careless rewrite all compile
cleanly and fail at run time. This gate walks the module AST, collects every name
that is *defined* somewhere in the file (imports, assignments, functions,
classes, parameters, comprehension targets, ``with``/``except``/``for`` targets,
walrus bindings, globals declared anywhere) and reports names that are only ever
*loaded*.

The judgment is deliberately file-scoped and conservative: a name assigned
anywhere counts as defined, so dynamic patterns and re-exports do not produce
noise. Scope is tracked ``*.py`` outside vendored and archived trees.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g11-undef-names"
TITLE = "governance: no name is loaded without being defined"

EXEMPT_PREFIXES = (".agents/notes/archived/", "vendor/", "node_modules/")

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__",
                                 "__loader__", "__builtins__", "__debug__", "self", "cls"}

#: Names that resolve dynamically and therefore must not be reported.
DYNAMIC_ALLOWLIST = {"__all__", "WindowsError"}


def defined_names(tree: ast.AST) -> set[str]:
    """Every name the module binds anywhere, however it is bound."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arguments):
            for argument in (*node.posonlyargs, *node.args, *node.kwonlyargs):
                names.add(argument.arg)
            if node.vararg is not None:
                names.add(node.vararg.arg)
            if node.kwarg is not None:
                names.add(node.kwarg.arg)
        elif isinstance(node, (ast.Name,)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            names.update(node.names)
        elif isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split(".")[0])
    return names


def loaded_names(tree: ast.AST) -> dict[str, int]:
    """Names read by the module, with the first line each appears on."""
    loads: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loads.setdefault(node.id, node.lineno)
    return loads


def scan(root: Path) -> Report:
    """Report loaded-but-never-defined names in every tracked Python file."""
    report = Report(title=TITLE)
    for path in govlib.tracked_files(root):
        if not path.endswith(".py") or path.startswith(EXEMPT_PREFIXES):
            continue
        text = govlib.read_text(root / path)
        if text is None:
            report.exempt("unreadable or binary")
            continue
        report.scanned += 1
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError as error:
            report.block("syntax-error", path, error.lineno or 1, str(error))
            continue
        defined = defined_names(tree) | BUILTINS
        for name, line in sorted(loaded_names(tree).items(), key=lambda item: item[1]):
            if name in defined or name in DYNAMIC_ALLOWLIST:
                continue
            report.block("undefined-name", path, line, f"{name} is loaded but never defined in this file")
    return report


def selfcheck() -> int:
    """Prove an unresolved name is caught and ordinary code is not."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/good.py",
                      "import json\n"
                      "from pathlib import Path\n"
                      "def load(path: Path) -> dict:\n"
                      "    text = path.read_text(encoding='utf-8')\n"
                      "    return json.loads(text)\n")
        report = scan(sandbox.path)
        check.quiet("imports and locals resolve", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/missing_import.py",
                      "from pathlib import Path\n"
                      "def build(path: Path) -> str:\n"
                      "    return json.dumps({'p': str(path)})\n")
        report = scan(sandbox.path)
        check.detects("a module used but never imported",
                      any(finding.kind == "undefined-name" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/lost_line.py",
                      "def run() -> int:\n"
                      "    total = compute()\n"
                      "    return total\n")
        report = scan(sandbox.path)
        check.detects("a call whose definition a rewrite dropped",
                      any(finding.kind == "undefined-name" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("tools/broken.py", "def run(:\n    pass\n")
        report = scan(sandbox.path)
        check.detects("a file that does not parse",
                      any(finding.kind == "syntax-error" for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root)
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
