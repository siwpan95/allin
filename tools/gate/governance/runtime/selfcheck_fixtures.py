"""Shared, declarative fixtures for the governance gates' ``--selfcheck``.

A gate proves two things about itself: it still *catches* an injected defect,
and it stays *quiet* on clean input.  Those assertions used to be written as
long, hand-copied ``with govlib.Sandbox()`` blocks -- one per scenario -- which
both bloated the gate files and invited the gates to drift apart.

This module keeps the *harness* in one place while each gate describes its
scenarios as a small table of :class:`Case` rows.  It deliberately reuses
``govlib.SelfCheck`` / ``govlib.Sandbox`` rather than reimplementing them, so
there is still exactly one place that emits the strict summary line

    SELFCHECK {"caught":N,"clean":M,"misreports":K}

(``govlib.SelfCheck.finish``) and exactly one place that builds a throwaway git
work tree (``govlib.Sandbox``).  A second judgment here would defeat the point.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import govlib


@dataclass(frozen=True)
class Case:
    """One self-check scenario: stage ``files``, then assert an outcome.

    ``expect="caught"`` asserts the gate flagged the injected defect;
    ``expect="clean"`` asserts it raised no false positive.  ``by`` selects the
    signal that must be present (caught) or absent (clean) in the outcome:

    * ``None`` -- any finding at all;
    * a bare string -- a finding ``kind`` or ``path``;
    * ``"path::kind"`` -- that kind at exactly that path;
    * ``"kind~<prefix>"`` -- any finding whose kind starts with ``<prefix>``;
    * ``"skip~<substring>"`` -- any counted skip whose reason contains it;
    * ``"a||b"`` -- any of the signals (one clean assertion covering more than
      one candidate path).
    """

    label: str
    files: dict[str, str]
    expect: str = "caught"
    by: str | None = None


@dataclass(frozen=True)
class Signals:
    """A gate report flattened into addressable ``Case.by`` keys."""

    kinds: frozenset[str]
    paths: frozenset[str]
    pairs: frozenset[str]
    skips: frozenset[str]

    def seen(self, by: str | None) -> bool:
        """Whether the selected signal was observed in the report."""
        if by is None:
            return bool(self.kinds)
        if by.startswith("kind~"):
            return any(kind.startswith(by[5:]) for kind in self.kinds)
        if by.startswith("skip~"):
            return any(by[5:] in reason for reason in self.skips)
        if "||" in by:
            return any(part in self.kinds or part in self.paths for part in by.split("||"))
        if "::" in by:
            return by in self.pairs
        return by in self.kinds or by in self.paths


def signals(report) -> Signals:
    """Flatten a gate report into the signal sets ``Case.by`` addresses.

    Skips are kept separate from findings on purpose: a gate may legitimately
    count a skip on a clean run, and ``Case`` with ``by=None`` means "no
    *finding*", not "no output of any kind".
    """
    kinds: set[str] = set()
    paths: set[str] = set()
    pairs: set[str] = set()
    for finding in report.findings:
        kinds.add(finding.kind)
        paths.add(finding.path)
        pairs.add(f"{finding.path}::{finding.kind}")
    return Signals(
        frozenset(kinds),
        frozenset(paths),
        frozenset(pairs),
        frozenset(report.skipped),
    )


def sandbox_with(files: Mapping[str, str]) -> govlib.Sandbox:
    """Build a sandbox and stage ``files`` into it.

    Two conventions keep a fixture table honest about *where* a file lives:

    * a path under ``.git/`` is written directly, because git cannot stage its
      own metadata (``govlib.Sandbox.write(..., track=False)``);
    * a key prefixed with ``@`` stages the file **untracked** (the ``@`` is
      stripped), for cases that must judge a file outside the index -- a
      machine-local credential or a link target a repository move would break.

    Tracked files are written first so the git-add calls run while the sandbox
    still has the pristine ``.git/config`` that ``govlib.Sandbox`` created; an
    untracked ``.git/config`` fixture is written last, after those calls.
    """
    box = govlib.Sandbox()
    tracked: list[tuple[str, str]] = []
    untracked: list[tuple[str, str]] = []
    for relative, content in files.items():
        if relative.startswith("@"):
            untracked.append((relative[1:], content))
        elif relative.startswith(".git/"):
            untracked.append((relative, content))
        else:
            tracked.append((relative, content))
    for relative, content in tracked:
        box.write(relative, content)
    for relative, content in untracked:
        box.write(relative, content, track=False)
    return box


def run_cases(gate: str, cases: Sequence[Case], check_fn) -> int:
    """Run every case in a fresh sandbox, then close with the strict SELFCHECK line.

    ``check_fn(sandbox)`` is the gate-specific half: it runs the gate's own
    ``scan`` against the staged sandbox and returns a :class:`Signals`.  Keeping
    only that step gate-specific is what collapses a 100+ line self-check into a
    table plus a handful of assertions.
    """
    check = govlib.SelfCheck(gate=gate)
    for case in cases:
        with sandbox_with(case.files) as sandbox:
            seen = check_fn(sandbox).seen(case.by)
            if case.expect == "caught":
                check.detects(case.label, seen)
            else:
                check.quiet(case.label, seen)
    return check.finish()
