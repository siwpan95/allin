"""Gate g08 -- a deletion must name the capability surface and its successor.

The recorded accident: one subsystem was declared absorbed because a sibling
covered the *broadcast* surface, while its *live rendering* surface had no
successor at all -- the whole output stage disappeared with the commit. The rule
that followed ("list the capability surfaces, find a proved successor per
surface, delete nothing without one") is a judgement, but its **evidence** is
mechanical: a commit that deletes paths must carry the surface-by-successor
table, or say why the rule does not apply.

Judged over a commit range so the check works before a push:

* ``--rev``   -- one commit (default ``HEAD``).
* ``--range`` -- an explicit ``A..B`` range, e.g. what a push would publish.

A commit with no deletions in range passes without further evidence.

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
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, GateError, Report  # noqa: E402

GATE = "g08-deletion-evidence"
TITLE = "governance: deletions carry capability-surface evidence"

#: One of these names the surfaces being retired.
SURFACE_MARKERS = ("功能面", "capability surface", "function surface", "surface:")
#: One of these names the successor that takes each surface over.
SUCCESSOR_MARKERS = ("接任者", "successor", "successor:", "taken over by", "接任")
#: An explicit, reviewable opt-out for a deletion that needs no evidence.
ANNOTATION = "gov-deletion: allow"
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def deleted_paths(root: Path, revision: str) -> tuple[list[str], str]:
    """Return the deletion list and the message of one commit."""
    status = govlib.run_git_result(["diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames",
                                    revision], root)
    if status.returncode != 0:
        detail = status.stderr.decode("utf-8", "replace").strip()
        raise GateError(f"cannot read {revision}: {detail}")
    deleted: list[str] = []
    for line in status.stdout.decode("utf-8", "replace").splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[0].strip() == "D":
            deleted.append(fields[1])
    message = govlib.run_git(["log", "-1", "--format=%B", revision], root, check=False)
    return deleted, message


def has_evidence(message: str) -> bool:
    """Whether the message carries the surface-by-successor evidence."""
    surface = any(marker in message for marker in SURFACE_MARKERS)
    successor = any(marker in message for marker in SUCCESSOR_MARKERS)
    rows = sum(1 for line in message.splitlines() if TABLE_ROW.match(line))
    return surface and successor and rows >= 2


def scan(root: Path, *, revision: str | None, revision_range: str | None) -> Report:
    """Judge the deletions visible in one commit or one range."""
    report = Report(title=TITLE)
    if revision_range:
        revisions = govlib.run_git(["rev-list", "--reverse", revision_range], root).split()
        if not revisions:
            report.skip(f"range {revision_range} contains no commit", 1)
            return report
    else:
        revisions = [revision or "HEAD"]

    for rev in revisions:
        deleted, message = deleted_paths(root, rev)
        report.scanned += 1
        if not deleted:
            report.exempt("commit deletes nothing", 1)
            continue
        short = govlib.run_git(["rev-parse", "--short", rev], root, check=False).strip() or rev
        if ANNOTATION in message:
            report.exempt("deletion annotated as evidence-free", 1)
            continue
        if has_evidence(message):
            report.exempt("deletion carries a surface-by-successor table", 1)
            continue
        report.block("deletion-without-evidence", f"commit {short}", 0,
                     f"deletes {len(deleted)} path(s) without a capability-surface x successor table; "
                     f"first: {deleted[0]}")
    return report


def selfcheck() -> int:
    """Prove an unevidenced deletion is caught and an evidenced one is not."""
    check = govlib.SelfCheck(gate=GATE)
    identity = ["-c", "user.name=governance-selfcheck", "-c", "user.email=selfcheck@example.invalid"]

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/keep.ts", "export const keep = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        sandbox.write("src/added.ts", "export const added = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: add a file"], sandbox.path)
        report = scan(sandbox.path, revision="HEAD", revision_range=None)
        check.quiet("a commit that deletes nothing", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/legacy.ts", "export const legacy = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        govlib.run_git(["rm", "-q", "src/legacy.ts"], sandbox.path)
        govlib.run_git([*identity, "commit", "-q", "-m", "chore: retire the legacy renderer"], sandbox.path)
        report = scan(sandbox.path, revision="HEAD", revision_range=None)
        check.detects("a deletion with no evidence",
                      any(finding.kind == "deletion-without-evidence" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/legacy.ts", "export const legacy = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        govlib.run_git(["rm", "-q", "src/legacy.ts"], sandbox.path)
        message = ("chore: retire the legacy renderer\n\n"
                   "| 功能面 | 接任者 |\n| --- | --- |\n| 渲染推流 | src/renderer.ts（同一提交内实现） |\n"
                   "| 排程 | src/scheduler.ts（既有） |\n")
        (sandbox.path / "msg.txt").write_text(message, encoding="utf-8", newline="\n")
        govlib.run_git([*identity, "commit", "-q", "-F", "msg.txt"], sandbox.path)
        report = scan(sandbox.path, revision="HEAD", revision_range=None)
        check.quiet("a deletion with a surface-by-successor table", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/typo.ts", "export const typo = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        govlib.run_git(["rm", "-q", "src/typo.ts"], sandbox.path)
        govlib.run_git([*identity, "commit", "-q", "-m",
                        "chore: drop an empty placeholder file\n\ngov-deletion: allow\n"], sandbox.path)
        report = scan(sandbox.path, revision="HEAD", revision_range=None)
        check.quiet("a deletion annotated as evidence-free", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/keep.ts", "export const keep = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        govlib.run_git(["rm", "-q", "src/keep.ts"], sandbox.path)
        govlib.run_git([*identity, "commit", "-q", "-m", "chore: retire it"], sandbox.path)
        report = scan(sandbox.path, revision=None, revision_range="HEAD~1..HEAD")
        check.detects("a range including an unevidenced deletion",
                      any(finding.kind == "deletion-without-evidence" for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--rev", default="HEAD", help="commit to judge (default: HEAD)")
    parser.add_argument("--range", default=None, help="commit range A..B (overrides --rev)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, revision=args.rev, revision_range=args.range)
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
