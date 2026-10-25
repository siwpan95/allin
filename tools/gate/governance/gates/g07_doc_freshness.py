"""Gate g07 -- a document that declares itself a fact source must date itself.

The recorded failure: a machine-facts snapshot declared itself the authority,
went stale within hours, and a later reader had no way to tell. Two mechanical
requirements follow, both scoped to the document's own header block:

* a **fact-source declaration** must carry a date, so a reader can weigh it;
* a **snapshot declaration** must additionally carry a supersession or expiry
  clause, so a stale copy cannot silently outrank the living record.

Scope is deliberately narrow. Agent Notes are excluded wholesale (their own
format gate governs them), as are vendored trees, and only a declaration inside
the first lines counts -- prose that merely uses the word "snapshot" while
describing a session artefact is not a fact-source claim.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g07-doc-freshness"
TITLE = "governance: declared fact sources carry a time point"

#: How far into a document its self-declaration is honoured.
HEADER_LINES = 20

EXEMPT_PREFIXES = (".agents/", "vendor/", "node_modules/")

#: A first-person authority claim: the document says what *it* is, rather than
#: mentioning snapshots in general. Only this shape counts as a declaration.
DECLARATION = (
    re.compile(r"本(?:文|文件|文档|页)[^\n。]{0,20}(?:是|为)[^\n。]{0,40}(?:事实源|快照|唯一|权威|基准)"),
    re.compile(r"以本(?:文|文件|文档)[^\n。]{0,20}为准"),
    re.compile(r"this (?:document|file|page|note) is (?:the|a)[^\n.]{0,60}"
               r"(?:source of truth|authoritative|snapshot)", re.IGNORECASE),
)

#: The declaration is about observed environment, which is what actually goes stale.
OBSERVATION_MARKERS = ("实测", "本机", "盘位", "环境事实", "机器事实", "measured", "observed",
                       "verified on", "this machine")

#: A snapshot claim additionally needs a clause that demotes it when reality moves.
SNAPSHOT_HINT = re.compile(r"(快照|snapshot)", re.IGNORECASE)

#: A recognised time point.
DATE = re.compile(r"20\d\d\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}")

#: A clause that demotes the document when reality moves on.
SUPERSESSION = (
    re.compile(r"以[^。\n]{0,40}为准"),
    re.compile(r"(订正|降级|失效|不再更新|已作废|历史快照)"),
    re.compile(r"(superseded|no longer current|historical snapshot|expires|obsolete)", re.IGNORECASE),
)

ANNOTATION = "gov-freshness: allow"


def header_block(text: str) -> str:
    """The opening lines where a document states what it is."""
    return "\n".join(text.splitlines()[:HEADER_LINES])


def scan(root: Path) -> Report:
    """Judge every tracked document that declares a fact-source role."""
    report = Report(title=TITLE)
    for path in govlib.tracked_files(root):
        if not path.endswith(".md") or path.startswith(EXEMPT_PREFIXES):
            continue
        text = govlib.read_text(root / path)
        if text is None:
            report.exempt("unreadable or binary")
            continue
        header = header_block(text)
        if ANNOTATION in header:
            report.exempt("annotated as intentionally undated")
            continue
        declares_source = any(pattern.search(header) for pattern in DECLARATION)
        if not declares_source:
            continue
        if not any(marker in header for marker in OBSERVATION_MARKERS):
            report.exempt("authority claim about something other than observed environment")
            continue
        declares_snapshot = SNAPSHOT_HINT.search(header) is not None
        report.scanned += 1
        if DATE.search(header) is None and DATE.search(text[:4000]) is None:
            report.block("undated-claim", path, 1,
                         "declares a fact-source or snapshot role without a time point")
            continue
        if declares_snapshot and not any(pattern.search(header) for pattern in SUPERSESSION):
            report.block("snapshot-without-expiry", path, 1,
                         "declares a snapshot role without a supersession or expiry clause")
            continue
        report.exempt("dated declaration", 1)
    return report


def selfcheck() -> int:
    """Prove an undated claim and an unguarded snapshot are caught."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/machine.md", "# Machine facts (2026-09-24)\n\n> 本文件是盘位的事实源。\n")
        sandbox.write("docs/live.md", "# Live record\n\nNothing declared here.\n")
        report = scan(sandbox.path)
        check.quiet("a dated fact-source declaration", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/machine.md", "# Machine facts\n\n> 本文件是盘位的事实源。\n")
        report = scan(sandbox.path)
        check.detects("an undated fact-source claim",
                      any(finding.kind == "undated-claim" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/snapshot.md",
                      "# 盘位快照（2026-09-24 上午）\n\n> 本文件是当时的盘位快照。\n")
        report = scan(sandbox.path)
        check.detects("a snapshot with no expiry clause",
                      any(finding.kind == "snapshot-without-expiry" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/snapshot.md",
                      "# 盘位快照（2026-09-24 上午）\n\n> 本文件是当时的盘位快照，盘位以实时实测为准。\n")
        report = scan(sandbox.path)
        check.quiet("a snapshot that names its successor", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write(".agents/notes/implemented/x.md", "# Note\n\n> This is the source of truth.\n")
        report = scan(sandbox.path)
        check.quiet("Agent Notes stay out of scope", bool(report.findings))
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
