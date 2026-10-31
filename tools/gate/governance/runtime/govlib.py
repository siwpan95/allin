"""Shared runtime for the governance gates of this distribution repository.

Every gate under ``governance/gates/`` imports this module, so four contracts
have exactly one implementation:

* the **exit-code vocabulary** (``0`` clean, ``1`` new blocking finding outside
  the baseline, ``2`` usage error, ``3`` environment error),
* **fail-loud repository discovery** -- a gate refuses to run when it cannot
  name the work tree it is judging, instead of silently scanning nothing,
* the **baseline ratchet** -- existing findings are frozen once so a gate can
  switch on while the repository is still being cleaned up,
* the **self-check harness** -- a gate proves both that it still catches an
  injected defect and that it still stays quiet on clean input.

Reported counts are never dropped silently: every exemption and every skip is
printed with a reason and a count, because an unaccounted exclusion is how a
gate reports "clean" while a whole class of defects walks through.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

#: Clean run: nothing blocking, or nothing outside the frozen baseline.
EXIT_OK = 0
#: At least one blocking finding that the baseline does not cover.
EXIT_BLOCKING = 1
#: The caller asked for something the gate does not support.
EXIT_USAGE = 2
#: The environment cannot support the judgment (no interpreter, no work tree).
EXIT_ENV = 3

#: ``governance/`` -- this module lives in ``governance/lib/``.
GOVERNANCE_DIR = Path(__file__).resolve().parent.parent

#: Git must never wait for a terminal in an unattended run.
GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "never",
    "GIT_PAGER": "cat",
    "LC_ALL": "C.UTF-8",
}


def git_env() -> dict[str, str]:
    """The process environment plus the no-prompt guard.

    Merging is the whole point: replacing the environment outright drops
    ``HOME``/``USERPROFILE``, so git cannot read the user's global config --
    including the ``safe.directory`` exceptions that make a checkout owned by
    another account readable at all. A gate that loses them either stops loudly
    (g03, g05) or, worse, reads an empty ``stdout`` as "nothing is wrong" (g12).
    """
    return {**os.environ, **GIT_ENV}


#: How many sample findings a gate prints before summarizing the rest.
SAMPLE_LIMIT = 20


def configure_stdio() -> None:
    """Force UTF-8 with LF-only line endings so output is identical on every host.

    Windows console translation would otherwise turn every ``\\n`` into ``\\r\\n``
    and break line-anchored parsing of a gate's own output.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace", newline="\n")


class GateError(RuntimeError):
    """A failure that must exit non-zero with a named, actionable cause."""

    def __init__(self, message: str, code: int = EXIT_ENV) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# repository discovery and git plumbing
# --------------------------------------------------------------------------- #


def repo_root(start: Path | None = None) -> Path:
    """Return the work-tree root, discovered from this file's location.

    The default value is derived, never hard-coded: the gate ships inside the
    repository, so walking up from ``governance/lib/`` finds the root on every
    machine. Passing an explicit ``--root`` (used by the self-check) overrides it.
    """
    current = (start or GOVERNANCE_DIR).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise GateError(
        f"no git work tree above {current}; run the gate from inside the repository "
        "or pass --root <work-tree>"
    )


def run_git_result(args: list[str], root: Path) -> subprocess.CompletedProcess[bytes]:
    """Run git and hand back the process, for callers that judge the exit code themselves."""
    command = ["git", "-c", "core.quotepath=false", *args]
    return subprocess.run(
        command,
        cwd=str(root),
        env=git_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_git(args: list[str], root: Path, check: bool = True) -> str:
    """Run git with prompts disabled, path quoting off, and UTF-8 decoding."""
    completed = run_git_result(args, root)
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise GateError(f"git {' '.join(args)} failed in {root}: {detail}")
    return completed.stdout.decode("utf-8", "replace")


def tracked_files(root: Path) -> list[str]:
    """Every path in the index, in git's own order, with ``/`` separators."""
    raw = run_git(["ls-files", "-z"], root)
    files = [entry for entry in raw.split("\0") if entry]
    if not files:
        raise GateError(f"{root} lists no tracked files; refusing to judge an empty corpus")
    return files


def blob_of(root: Path, path: str) -> str:
    """The staged content of one tracked path, or an empty string when absent."""
    return run_git(["show", f":{path}"], root, check=False)


# --------------------------------------------------------------------------- #
# file reading
# --------------------------------------------------------------------------- #


def read_text(path: Path, limit_bytes: int | None = None) -> str | None:  # gov-python: allow
    """Read UTF-8 text, or return ``None`` for missing, binary, or oversized input.

    Why the annotation: `g09-python-hygiene` flags any `read_text(` that does not
    spell ``encoding=`` on the same line, because the stdlib `Path.read_text`
    defaults to the locale codec. This one is a **wrapper**: it reads bytes and
    decodes explicitly below, so the locale never gets a vote. The gate's
    local-helper heuristic only recognises a helper whose body contains
    ``encoding=`` (it looks for the keyword, not for ``.decode("utf-8")``), so
    this safe wrapper reads as a defect. Annotating is the mechanism the gate
    itself documents for that gap; broadening the heuristic is the better fix
    and is left as a known limitation (2026-10-31).
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if limit_bytes is not None:
        data = data[:limit_bytes]
    if b"\0" in data:
        return None
    return data.decode("utf-8", "replace")


def line_of(text: str, offset: int) -> int:
    """1-based line number of a character offset."""
    return text.count("\n", 0, offset) + 1


def line_text(text: str, offset: int) -> str:
    """The full source line containing a character offset."""
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return text[start:] if end == -1 else text[start:end]


def digest(value: str) -> str:
    """Short stable hash used to key baseline entries by content, not line number."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    """One blocking defect, identified by file, line, and content key."""

    path: str
    line: int
    text: str
    kind: str
    key: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            self.key = f"{self.path}|{digest(self.text.strip())}|{self.kind}"


@dataclass
class Report:
    """The outcome of one gate run: what blocked, what was exempted, what was skipped."""

    title: str
    findings: list[Finding] = field(default_factory=list)
    exempted: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)
    scanned: int = 0

    def block(self, kind: str, path: str, line: int, text: str) -> None:
        self.findings.append(Finding(path=path, line=line, text=text, kind=kind))

    def exempt(self, reason: str, count: int = 1) -> None:
        """Record an exclusion so the count stays visible in the output."""
        self.exempted[reason] += count

    def skip(self, reason: str, count: int = 1) -> None:
        """Record work the gate could not perform. A skip is never a pass."""
        self.skipped[reason] += count

    def note(self, message: str) -> None:
        self.notes.append(message)

    def exit_code(self) -> int:
        return EXIT_BLOCKING if self.findings else EXIT_OK

    def render(self, sample_limit: int = SAMPLE_LIMIT) -> str:
        lines = [
            f"{self.title}: scanned {self.scanned} file(s); "
            f"blocking {len(self.findings)}; exempted {sum(self.exempted.values())}; "
            f"skipped {sum(self.skipped.values())}."
        ]
        for index, finding in enumerate(self.findings[:sample_limit]):
            lines.append(f"  BLOCK {finding.path}:{finding.line}: {finding.kind}: {finding.text.strip()[:160]}")
        remaining = len(self.findings) - sample_limit
        if remaining > 0:
            lines.append(f"  ... and {remaining} more blocking finding(s)")
        if self.exempted:
            detail = ", ".join(f"{reason}={count}" for reason, count in sorted(self.exempted.items()))
            lines.append(f"  exempted: {detail}")
        if self.skipped:
            detail = ", ".join(f"{reason}={count}" for reason, count in sorted(self.skipped.items()))
            lines.append(f"  SKIPPED (not a pass): {detail}")
        lines.extend(f"  note: {message}" for message in self.notes)
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# baseline ratchet
# --------------------------------------------------------------------------- #


class Baseline:
    """A frozen set of finding keys; only keys outside it block a run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.keys: set[str] = set()

    def load(self) -> "Baseline":
        if self.path.is_file():
            # gov-python: allow —— 调的是本文件的 read_text 包装，编码已写死。
            for entry in read_text(self.path, limit_bytes=4 * 1024 * 1024).splitlines() or []:
                entry = entry.strip()
                if entry and not entry.startswith("#"):
                    self.keys.add(entry)
        return self

    def filter_new(self, findings: list[Finding]) -> list[Finding]:
        return [finding for finding in findings if finding.key not in self.keys]

    def stale(self, findings: list[Finding]) -> list[str]:
        live = {finding.key for finding in findings}
        return sorted(self.keys - live)

    def write(self, findings: list[Finding]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = [
            "# Baseline ratchet for this gate. One finding key per line.",
            "# Refresh only after the remaining findings were reviewed in full:",
            "#   python governance/gates/<gate>.py --no-baseline --list-all",
        ]
        body.extend(sorted({finding.key for finding in findings}))
        self.path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")


def add_baseline_argument(parser) -> None:
    """Install the four baseline switches every gate exposes."""
    parser.add_argument("--baseline", default=None, help="baseline file (default: governance/baseline/<gate>.txt)")
    parser.add_argument("--no-baseline", action="store_true", help="ignore the baseline and judge everything")
    parser.add_argument("--write-baseline", action="store_true", help="freeze current findings as the baseline")
    parser.add_argument("--list-all", action="store_true", help="print every finding, not just new ones")


# --------------------------------------------------------------------------- #
# self-check harness
# --------------------------------------------------------------------------- #


@dataclass
class SelfCheck:
    """Assertions that prove a gate catches defects and stays quiet when clean."""

    gate: str
    caught: int = 0
    clean: int = 0
    misreports: int = 0
    failures: list[str] = field(default_factory=list)

    def detects(self, label: str, condition: bool) -> None:
        """Assert the gate caught an injected defect."""
        if condition:
            self.caught += 1
        else:
            self.failures.append(f"missed injected defect: {label}")

    def quiet(self, label: str, flagged: bool) -> None:
        """Assert the gate stayed quiet on clean input."""
        if flagged:
            self.misreports += 1
            self.failures.append(f"false positive on clean input: {label}")
        else:
            self.clean += 1

    def finish(self) -> int:
        # 紧凑分隔符：契约（RULES.md §自证有效）写的是 `SELFCHECK {"caught":N,"clean":M,"misreports":K}`，
        # json.dumps 的默认分隔符会带空格，与契约文本不一致。格式统一后元门禁才能按契约严格机检。
        payload = json.dumps({"caught": self.caught, "clean": self.clean, "misreports": self.misreports},
                             separators=(",", ":"))
        for failure in self.failures:
            print(f"  FAIL {failure}")
        print(f"SELFCHECK {payload}")
        if self.failures or self.caught == 0 or self.clean == 0:
            print(f"selfcheck failed for {self.gate}: a gate must catch at least one injected defect "
                  "and stay quiet on at least one clean sample")
            return EXIT_BLOCKING
        print(f"selfcheck ok for {self.gate}: caught {self.caught}, quiet on {self.clean}, misreports 0")
        return EXIT_OK


class Sandbox:
    """A throwaway git work tree the self-check injects fixtures into."""

    def __init__(self) -> None:
        self.path = Path(tempfile.mkdtemp(prefix="gov-selfcheck-"))
        run_git(["init", "-q"], self.path)

    def write(self, relative: str, content: str, track: bool = True) -> None:
        """Write one fixture; ``track=False`` leaves it out of the index on purpose."""
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        if track:
            run_git(["add", "--", relative], self.path)

    def close(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def run_gate(gate_main, argv: list[str] | None = None) -> int:
    """Run a gate entry point, mapping GateError onto its declared exit code."""
    configure_stdio()
    try:
        return int(gate_main(sys.argv[1:] if argv is None else argv))
    except GateError as error:
        print(f"error: {error}", file=sys.stderr)
        return error.code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_ENV
