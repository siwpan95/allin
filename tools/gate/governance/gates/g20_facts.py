"""Gate g20 -- machine fact sources still match reality.

The recorded failure (2026-10-30)
--------------------------------
`docs/事实源/机器/DESKTOP-8RSV60V.md` was re-measured from scratch: **nine claims
no longer matched the disk**, while all 19 gates exited 0. Root cause is not a
broken gate but a coverage gap, one layer below the three that already exist:

* ``g07_doc_freshness`` checks that a fact source *carries* a time point -- not
  that the facts still hold *after* that time point;
* ``g19_docs_refs`` resolves **repository-relative** paths (``docs/…``, ``tools/…``)
  only; a machine absolute path (``G:\\…``) is never parsed, because its
  ``PATH_REF`` prefix allowlist contains no drive letters;
* ``g01_paths`` judges *dead* drive roots (parent missing); it cannot see a
  semantic expiry on a *live* drive (syntax valid, directory gone).

What is judged -- and deliberately nothing else
-----------------------------------------------
Only the two claim types that are mechanically decidable. Noise is how a gate
gets switched off, so everything else is left to humans:

* ``path-exists`` -- a line claiming a machine absolute path *exists*
  (``现已存在`` / ``现存`` / ``仍在位``) must resolve; one claiming it is gone
  (``现已不存在`` / ``已不存在`` / ``均不存在`` / ``MISSING`` / ``已删`` / ``已移除``)
  must not.
* ``count`` -- an absolute path followed by ``**N**`` or ``N 项`` must really hold
  N entries. The unit decides the counting mode: ``项`` counts every entry
  (archive directories hold loose files), while no unit or ``个仓`` / ``个目录``
  counts directories only -- ``G:\\repos`` holds 136 directories *plus* 4 files,
  and counting everything yields 140, i.e. a false drift.

Scope is the header block(s) carrying the **newest** ``> **时点**`` date. Older
blocks are history: judging them would force people to rewrite the past, and a
fact source that cannot keep its own history is worth less than one that can.

Single implementation
---------------------
The criteria live here, in the gate, and ``tools/facts/verify_facts.py`` imports
them for CLI use. The gate script must be self-contained because ``g00-meta``
runs every ``--selfcheck`` inside a sandbox that contains only ``governance/``;
a checker that reached into ``tools/facts`` would report "not importable" there.
Two copies of the criteria would both report green and disagree in silence --
exactly the failure mode ``SPEC-003 §新建三查`` exists to prevent.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_ENV, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g20-facts"
TITLE = "governance: machine fact sources still match reality"

TARGET_DIR = Path("docs") / "事实源" / "机器"
STALE_DAYS = 90

#: A machine absolute path: drive letter + separator + everything up to whitespace,
#: a backtick, or CJK punctuation.
ABS_PATH = re.compile(r"([A-Za-z]:[\\/][^`\s，。、；：（）【】「」]*)")

POSITIVE = re.compile(r"现已存在|现存|仍在位|EXISTS")
NEGATIVE = re.compile(r"现已不存在|已不存在|均不存在|MISSING|已删|已移除")

#: Count assertion: first ``**N**`` wins, then a bare ``N 项`` / ``N 个仓`` / ``N 个目录``.
COUNT_BOLD = re.compile(r"\*\*(\d+)\*\*\s*(项|个仓|个目录|个)?")
COUNT_PLAIN = re.compile(r"(\d+)\s*(项|个仓|个目录)")


def strip_tail(raw: str) -> str:
    return raw.rstrip("`.,;:)]}'\"、）。】")


def header_scope(text: str) -> tuple[str, str]:
    """Return (text of the newest-timepoint blocks, the timepoint string).

    Scope = every ``> **时点**`` block sharing the **latest** date, each running
    to the next such block or the first ``## `` heading. Earlier blocks are
    history and are never judged.

    ⚠ Known edge: if the newest block is purely structural (no numbers, no
    paths), claims in older blocks go unchecked. The convention that covers it:
    **write current values into the newest timepoint block** -- writing them into
    an older one is the same as not writing them.
    """
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(">") and "**时点**" in ln]

    if not starts:
        end = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        return "\n".join(lines[:end]), ""

    blocks: list[tuple[tuple[int, ...], str, str]] = []
    for idx, start in enumerate(starts):
        stop = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        for j in range(start + 1, stop):
            if lines[j].startswith("## "):
                stop = j
                break
        chunk = "\n".join(lines[start:stop])
        found = re.search(r"20\d\d[-/年]\d{1,2}[-/月]\d{1,2}", chunk)
        key = tuple(int(x) for x in re.findall(r"\d+", found.group(0))[:3]) if found else (0, 0, 0)
        blocks.append((key, chunk, found.group(0) if found else ""))

    newest = max(b[0] for b in blocks)
    kept = [b for b in blocks if b[0] == newest]
    return "\n".join(b[1] for b in kept), kept[0][2]


def count_entries(path: Path, mode: str = "dirs") -> int:
    """Count entries.

    ``dirs`` (default) counts directories only -- the unit for repo counts; the
    files sitting next to them are not repositories.
    ``all`` counts every entry -- the unit for ``N 项``, where loose files matter.
    """
    try:
        if mode == "all":
            return sum(1 for _ in path.iterdir())
        return sum(1 for c in path.iterdir() if c.is_dir())
    except OSError:
        return -1


def check_text(text: str, label: str) -> tuple[list[dict], str]:
    """Judge one fact-source document. Returns (findings, timepoint string)."""
    block, stamp = header_scope(text)
    findings: list[dict] = []

    for lineno, line in enumerate(block.splitlines(), 1):
        if not line.strip():
            continue

        for raw in ABS_PATH.findall(line):
            target = strip_tail(raw)
            if len(target) < 4:
                continue
            if NEGATIVE.search(line):
                if Path(target).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称不存在但实际存在：{target}", "path": target})
            elif POSITIVE.search(line):
                if not Path(target).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称存在但实际缺失：{target}", "path": target})

        candidates = [strip_tail(x) for x in ABS_PATH.findall(line)]
        candidates = [p for p in candidates if len(p) >= 4]
        if not candidates:
            continue
        target_path = Path(candidates[0])
        if not target_path.is_dir():
            continue
        match = COUNT_BOLD.search(line) or COUNT_PLAIN.search(line)
        if not match:
            continue
        claimed = int(match.group(1))
        unit = match.group(2) or ""
        mode = "all" if unit.startswith("项") else "dirs"
        actual = count_entries(target_path, mode)
        if actual >= 0 and actual != claimed:
            findings.append({"kind": "COUNT", "file": label, "line": lineno,
                             "claim": f"声称 {claimed}（口径 {mode}），实际 {actual}：{target_path}",
                             "path": str(target_path), "claimed": claimed,
                             "actual": actual, "mode": mode})
    return findings, stamp


def evaluate_staleness(stamp: str) -> str:
    """Age of the timepoint. Reported, never blocking -- how old is too old is a human call."""
    if not stamp:
        return "时点：未识别"
    digits = re.findall(r"\d+", stamp)
    if len(digits) < 3:
        return f"时点：{stamp}"
    try:
        parsed = date(int(digits[0]), int(digits[1]), int(digits[2]))
    except ValueError:
        return f"时点：{stamp}（无法解析）"
    age = (date.today() - parsed).days
    return f"时点：{stamp}（{age} 天前，{'⚠ 超 ' + str(STALE_DAYS) + ' 天' if age > STALE_DAYS else '在窗口内'}）"


def scan(root: Path) -> Report:
    report = Report(title=TITLE)
    target = root / TARGET_DIR
    if not target.is_dir():
        report.skip("no machine fact directory")
        return report
    for path in sorted(target.glob("*.md")):
        report.scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        findings, stamp = check_text(text, path.name)
        report.note(f"{path.name}: {evaluate_staleness(stamp)}")
        for fd in findings:
            report.block(fd["kind"].lower(), fd["file"], fd["line"], fd["claim"])
    return report


def selfcheck() -> int:
    """Fixtures: two must be caught, one must stay clean, none may misreport."""
    root = Path(tempfile.mkdtemp(prefix="g20-selfcheck-"))
    probe = root / "probe-dir"
    probe.mkdir()
    (probe / "only-child.txt").write_text("x", encoding="utf-8")
    absent = root / "definitely-absent-xyz"

    machine = root / TARGET_DIR
    machine.mkdir(parents=True)

    good = machine / "good.md"
    good_payload = (
        "> **时点** 2026-10-30（自检：正确值）\n"
        f"> `{probe}` 共 **1 项**\n"
        f"> `{probe}` 现已存在\n"
        "## 正文\n"
        f"> `{probe}` 共 **99 项**（历史块，应被忽略）\n"
    )
    good.write_text(good_payload, encoding="utf-8")

    cases = [
        ("wrong-count.md", f"> **时点** 2026-10-30（自检）\n> `{probe}` 共 **42 项**\n", "count"),
        ("missing-path.md", f"> **时点** 2026-10-30（自检）\n> `{absent}` 现已存在\n", "path-exists"),
    ]

    caught, clean, misreports = 0, 0, 0
    for name, payload, expected in cases:
        probe_doc = machine / name
        probe_doc.write_text(payload, encoding="utf-8")
        findings, _ = check_text(payload, name)
        if any(f["kind"].lower() == expected for f in findings):
            caught += 1
        else:
            misreports += 1
        probe_doc.unlink()

    good_findings, _ = check_text(good.read_text(encoding="utf-8"), good.name)
    if good_findings:
        misreports += 1
    else:
        clean += 1

    print(f"selfcheck: caught={caught} clean={clean} misreports={misreports}")
    print("SELFCHECK " + json.dumps({"caught": caught, "clean": clean, "misreports": misreports},
                                    separators=(",", ":")))
    return EXIT_OK if caught == 2 and clean == 1 and misreports == 0 else EXIT_BLOCKING


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    if sys.platform != "win32":
        print("ENV ERROR: g20-facts 只支持 Windows（判据基于盘符绝对路径）", file=sys.stderr)
        return EXIT_ENV

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    if not root.is_dir():
        print(f"ENV ERROR: root 不存在：{root}", file=sys.stderr)
        return EXIT_ENV

    report = scan(root)
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    baseline = Baseline(baseline_path)

    if args.write_baseline:
        baseline.write(report.findings)
        print(f"{TITLE}: baseline written with {len(report.findings)} finding(s) -> {baseline_path}")
        return EXIT_OK
    if not args.no_baseline:
        baseline.load()

    new_findings = report.findings if args.no_baseline else baseline.filter_new(report.findings)
    blocking = report.findings if args.list_all else new_findings
    rendered = report.render()
    print(rendered.splitlines()[0] if args.quiet else rendered)
    return EXIT_BLOCKING if blocking else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
