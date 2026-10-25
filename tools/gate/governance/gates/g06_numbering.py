"""Gate g06 -- numbering is a reference contract, so gaps and drift are defects.

Two shapes are judged, both from the recorded accident class "44 entries, 42
unique numbers, and eight citations pointing at the wrong rule":

* **ordinal version series** -- ``v0.schema.json``, ``v1``, ``v2`` … in one
  directory must form a contiguous run from the smallest member. A gap means a
  reader following the series silently skips a generation.
* **bilingual numbering equality** -- in a paired document the numbered lists of
  both languages must agree item for item: same number of lists, same labels,
  same item counts. This repository's Chinese counterparts are the same contract
  in another language, so a renumbered list on one side breaks every citation
  into the other.

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

GATE = "g06-numbering"
TITLE = "governance: numbering contracts (series continuity, pair equality)"

ORDINAL_FILE = re.compile(r"^v(\d+)(?:\.[A-Za-z0-9]+)*\.(?:json|md|yaml|yml)$")
ORDERED_ITEM = re.compile(r"^(\s*)(\d+)[.)]\s+\S")
UNORDERED_ITEM = re.compile(r"^(\s*)[-*+]\s+\S")
EXEMPT_PREFIXES = (".agents/notes/archived/", "vendor/", "docs/i18n/")


def ordinal_series(root: Path, tracked: list[str]) -> dict[tuple[str, str], list[tuple[int, str]]]:
    """Group tracked ordinal files by directory and suffix shape."""
    series: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for path in tracked:
        if path.startswith(EXEMPT_PREFIXES):
            continue
        name = path.rsplit("/", 1)[-1]
        match = ORDINAL_FILE.match(name)
        if match is None:
            continue
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        shape = name.replace(match.group(1), "N", 1)
        series.setdefault((directory, shape), []).append((int(match.group(1)), path))
    return series


def list_shapes(text: str) -> list[tuple[str, int, tuple[int, ...]]]:
    """Ordered and unordered list shapes, in document order.

    Each entry is ``(kind, item count, ordered labels)``; continuation lines and
    fenced code blocks are ignored so a code sample never counts as prose.
    """
    shapes: list[tuple[str, int, tuple[int, ...]]] = []
    current: tuple[str, list[int], int] | None = None
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        ordered = ORDERED_ITEM.match(line)
        unordered = UNORDERED_ITEM.match(line) if ordered is None else None
        if ordered is not None:
            label = int(ordered.group(2))
            if current is None or current[0] != "ordered":
                if current is not None:
                    shapes.append((current[0], current[2], tuple(current[1])))
                current = ("ordered", [label], 1)
            else:
                current[1].append(label)
                current = (current[0], current[1], current[2] + 1)
        elif unordered is not None:
            if current is None or current[0] != "unordered":
                if current is not None:
                    shapes.append((current[0], current[2], tuple(current[1])))
                current = ("unordered", [], 1)
            else:
                current = (current[0], current[1], current[2] + 1)
        elif line.strip() == "":
            if current is not None:
                shapes.append((current[0], current[2], tuple(current[1])))
                current = None
    if current is not None:
        shapes.append((current[0], current[2], tuple(current[1])))
    return shapes


def scan(root: Path) -> Report:
    """Judge ordinal series continuity and bilingual list equality."""
    report = Report(title=TITLE)
    tracked = govlib.tracked_files(root)
    for (directory, shape), members in sorted(ordinal_series(root, tracked).items()):
        if len(members) < 2:
            continue
        numbers = sorted(number for number, _path in members)
        expected = list(range(numbers[0], numbers[0] + len(numbers)))
        report.scanned += len(members)
        if numbers != expected:
            missing = sorted(set(expected) - set(numbers))
            report.block("series-gap", f"{directory}/{shape}", 0,
                         f"ordinal series skips {missing} (found {numbers})")
        else:
            report.exempt("contiguous ordinal series", len(members))

    pairs = 0
    for path in tracked:
        if not path.endswith(".md") or path.endswith(".zh.md") or path.startswith(EXEMPT_PREFIXES):
            continue
        counterpart = f"{path[:-3]}.zh.md"
        if counterpart not in tracked:
            continue
        pairs += 1
        report.scanned += 1
        source = govlib.read_text(root / path) or ""
        translated = govlib.read_text(root / counterpart) or ""
        left = list_shapes(source)
        right = list_shapes(translated)
        if len(left) != len(right):
            report.block("pair-list-count", counterpart, 0,
                         f"{len(left)} list(s) in the English source vs {len(right)} in the counterpart")
            continue
        for index, (a, b) in enumerate(zip(left, right, strict=True), start=1):
            if a[0] != b[0] or a[1] != b[1] or a[2] != b[2]:
                report.block("pair-list-shape", counterpart, 0,
                             f"list {index} differs: source {a[0]}/{a[1]} item(s)/{a[2]} vs counterpart "
                             f"{b[0]}/{b[1]} item(s)/{b[2]}")
    if pairs == 0:
        report.skip("no tracked bilingual pair in scope", 1)
    return report


def selfcheck() -> int:
    """Prove a series gap and a drifted pair are caught, and clean input is not."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/formats/v0.schema.json", "{}\n")
        sandbox.write("docs/formats/v1.schema.json", "{}\n")
        sandbox.write("docs/formats/v2.schema.json", "{}\n")
        sandbox.write("guide/index.md", "# Guide\n\n1. one\n2. two\n\n- a\n- b\n")
        sandbox.write("guide/index.zh.md", "# 指南\n\n1. 一\n2. 二\n\n- 甲\n- 乙\n")
        report = scan(sandbox.path)
        check.quiet("a contiguous series and an equal pair", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("docs/formats/v0.schema.json", "{}\n")
        sandbox.write("docs/formats/v2.schema.json", "{}\n")
        report = scan(sandbox.path)
        check.detects("a gap in an ordinal series",
                      any(finding.kind == "series-gap" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("guide/index.md", "# Guide\n\n1. one\n2. two\n3. three\n")
        sandbox.write("guide/index.zh.md", "# 指南\n\n1. 一\n2. 二\n")
        report = scan(sandbox.path)
        check.detects("a renumbered list in the counterpart",
                      any(finding.kind in ("pair-list-count", "pair-list-shape") for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("guide/index.md", "# Guide\n\n```\n1. code line\n2. code line\n```\n\n1. real\n")
        sandbox.write("guide/index.zh.md", "# 指南\n\n```\n1. 代码行\n```\n\n1. 真的\n")
        report = scan(sandbox.path)
        check.quiet("fenced code is not prose numbering", bool(report.findings))
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
