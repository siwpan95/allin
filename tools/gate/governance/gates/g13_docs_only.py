"""Gate g13 -- the documentation tree holds documents, not programs or archives.

The recorded rule: the documentation hub carries ``.md``, ``.txt`` and
explanatory ``.yaml``, while scripts, build output, binaries and archived
payloads live somewhere with an owner. A stray ``.sh`` or ``.zip`` in the docs
tree is how generated material and third-party payloads start leaking into a
published repository.

Scoped to ``docs/**`` and judged on the tracked surface, with an extension
allowlist wide enough for this repository's real content (generated JSON
catalogs, schema snapshots, screenshots) and a block list for anything
executable, binary, or archived.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g13-docs-only"
TITLE = "governance: the docs tree holds documents"

SCOPE_PREFIX = "docs/"

#: Extensions allowed under docs/: prose, generated catalogs, and screenshots.
ALLOWED_SUFFIXES = (".md", ".mdx", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg",
                    ".gif", ".webp", ".svg", ".csv", ".mmd", ".css")

#: Extensions that must never appear under docs/ even though they are text.
BLOCKED_SUFFIXES = (".py", ".sh", ".bash", ".ps1", ".cmd", ".bat", ".js", ".mjs", ".ts", ".tsx",
                    ".zip", ".tar", ".gz", ".tgz", ".7z", ".bin", ".exe", ".dll", ".so", ".dylib",
                    ".log", ".lock", ".patch", ".diff")

#: Git modes that mark a file executable.
EXECUTABLE_MODES = ("100755", "100775")


def staged_entries(root: Path) -> list[tuple[str, str]]:
    """``(mode, path)`` for every tracked file, read from the index."""
    entries: list[tuple[str, str]] = []
    for record in govlib.run_git(["ls-files", "-s", "-z"], root).split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and path:
            entries.append((parts[0], path))
    return entries


def scan(root: Path) -> Report:
    """Judge the extension and mode of every tracked path under docs/."""
    report = Report(title=TITLE)
    seen = 0
    for mode, path in staged_entries(root):
        if not path.startswith(SCOPE_PREFIX):
            continue
        seen += 1
        report.scanned += 1
        suffix = Path(path).suffix.lower()
        if suffix in BLOCKED_SUFFIXES:
            report.block("blocked-extension", path, 0, f"{suffix} belongs outside the docs tree")
            continue
        if suffix not in ALLOWED_SUFFIXES:
            report.block("unexpected-extension", path, 0, f"{suffix or '(no extension)'} is not an allowed docs type")
            continue
        if mode in EXECUTABLE_MODES:
            report.block("executable-mode", path, 0, "documentation is not executable")
            continue
        report.exempt("allowed document", 1)
    if seen == 0:
        report.skip("no tracked file under docs/", 1)
    return report


def selfcheck() -> int:
    """Prove a script, an archive, and an executable bit are caught."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/guide.md", "# Guide\n")
        sandbox.write("docs/catalog.json", "{}\n")
        sandbox.write("docs/images/diagram.png", "\x89PNG\n")
        report = scan(sandbox.path)
        check.quiet("prose, generated catalogs, and screenshots", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/tool.py", "print('hi')\n")
        report = scan(sandbox.path)
        check.detects("a script inside the docs tree",
                      any(finding.kind == "blocked-extension" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/payload.zip", "PK\n")
        report = scan(sandbox.path)
        check.detects("an archive inside the docs tree",
                      any(finding.kind == "blocked-extension" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/notes.rst", "notes\n")
        report = scan(sandbox.path)
        check.detects("an unexpected documentation type",
                      any(finding.kind == "unexpected-extension" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/run.md", "# run\n")
        govlib.run_git(["update-index", "--chmod=+x", "docs/run.md"], sandbox.path)
        report = scan(sandbox.path)
        check.detects("an executable bit on documentation",
                      any(finding.kind == "executable-mode" for finding in report.findings))
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
