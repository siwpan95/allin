"""Gate g16 -- every governance carrier says the same thing.

The governance facts reach an agent in three shapes that have to agree:

* ``.workbuddy/skills/allin-governance-agent/SKILL.md`` -- the WorkBuddy skill,
  loaded by an agent that runs inside this workspace;
* the ``GOVERNANCE:BEGIN/END`` segment of ``preset/allin/allin.patch.yml`` --
  the same facts injected into a DeepSeek Harness agent-preset;
* the ``GOVERNANCE:BEGIN/END`` segment of ``preset/allin/agent.cordis.yml`` --
  the archived directory-form preset kept for historical comparison. Nothing
  loads it, which is exactly why it sat on a 2026-09 snapshot (hard-coded drive
  root, retired document paths, "107 repos") and stayed invisible: no gate read
  it. Judging it as a carrier costs nothing and stops the archive from teaching
  a stale rule to whoever opens it next (added 2026-10-29).

They drift because they are edited in different places, and the drift is
invisible until an agent follows a command that no longer exists. This gate
turns "keep the carriers in sync" from a rule written in prose into an exit
code:

* every carrier exists and carries a non-empty governance surface;
* each preset carrier's governance segment is a well-formed marked pair;
* every **declared core fact** (the canonical command and the canonical hub
  paths) appears on *every* side -- one side alone is drift;
* every gate id any carrier names exists in ``governance/registry.json``, so no
  side can advertise a check that is not shipped;
* **no carrier carries a machine drive path.** This is the gap that let a
  stale ``G:\\...`` interpreter live inside SKILL.md: ``g01-paths`` treats
  ``.md`` as report-only, so a drive letter in a Markdown carrier was reported
  but never blocked. URLs are stripped before the scan, so ``https://host`` is
  not mistaken for a path.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, EXIT_ENV, Report  # noqa: E402

GATE = "g16-skill-preset-parity"
TITLE = "governance: every governance carrier says the same facts"

#: Carriers that must agree, and how each one's governance surface is delimited.
#: ``whole`` = the file is the governance surface; ``segment`` = only the marked
#: ``GOVERNANCE:BEGIN/END`` body counts.
CARRIERS: list[tuple[str, str, str]] = [
    ("skill", ".workbuddy/skills/allin-governance-agent/SKILL.md", "whole"),
    ("preset", "preset/allin/allin.patch.yml", "segment"),
    ("agent", "preset/allin/agent.cordis.yml", "segment"),
]

GOV_BEGIN = "GOVERNANCE:BEGIN"
GOV_END = "GOVERNANCE:END"

#: The real marker lines. Prose comments above a preset legitimately name the
#: markers ("GOVERNANCE:BEGIN/END 段"), so the segment must be anchored on these
#: comment lines, never on the first mention of the words: a substring search
#: used to hand back the comment block above the segment, and the preset side
#: then passed its fact check on a comment instead of the governance text
#: (found 2026-10-29 by the third carrier, which has no such comments).
MARKER_BEGIN_LINE = "<!-- " + GOV_BEGIN + " -->"
MARKER_END_LINE = "<!-- " + GOV_END + " -->"

#: Facts that must be provably present on *every* carrier. Deliberately small and
#: canonical: a fact only one carrier happens to mention is normal, a fact the
#: carriers disagree about is drift.
REQUIRED_FACTS: list[tuple[str, str]] = [
    ("command", "npm run check:governance"),
    ("path", "docs/INDEX.md"),
    ("path", "preset/allin/allin.patch.yml"),
    ("path", "docs/记录/"),
]

GATE_ID = re.compile(r"\bg\d\d-[a-z][a-z-]*\b")
DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")
URL = re.compile(r"https?://\S+")


def carrier_text(path: Path) -> str | None:
    """Read one carrier as UTF-8, or None when it is missing/binary.

    The encoding is explicit on purpose: a gate that judges text must never
    judge mojibake, and ``g09-python-hygiene`` refuses an IO call without one.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def governance_segment(text: str) -> str | None:
    """The GOVERNANCE:BEGIN/END body, or None when the pair is not well-formed.

    Anchored on the marker **lines**, so a prose comment above the segment cannot
    become its start (see MARKER_BEGIN_LINE for the accident this prevents).
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith(MARKER_BEGIN_LINE)), None)
    if start is None:
        return None
    stop = next((i for i, line in enumerate(lines[start + 1 :], start + 1)
                 if line.strip().startswith(MARKER_END_LINE)), None)
    if stop is None:
        return None
    return "\n".join(lines[start : stop + 1])


def load_registry_ids(root: str) -> set[str]:
    path = Path(root) / "tools" / "gate" / "governance" / "registry.json"
    text = carrier_text(path)
    if not text:
        return set()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return set()
    entries = payload.get("gates") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return set()
    return {str(entry.get("id", "")) for entry in entries if isinstance(entry, dict)}


def scan_drive_paths(report: Report, rel: str, text: str) -> None:
    """Block drive-letter paths, ignoring anything that is plainly a URL."""
    for number, line in enumerate(text.splitlines(), start=1):
        probe = URL.sub(" ", line)
        if DRIVE_PATH.search(probe):
            report.block("carrier-machine-path", rel, number,
                         f"carrier carries a machine path: {line.strip()[:160]}")
        else:
            report.exempt("carrier-line-clean")


def run(root: str, args: argparse.Namespace) -> Report:
    report = Report(title=TITLE)
    sides: dict[str, str | None] = {}

    for name, rel, mode in CARRIERS:
        sides[name] = None
        path = Path(root) / rel
        if not path.is_file():
            report.block("carrier-missing", rel, 0,
                         f"{name} carrier is missing; the governance facts have no {name} home")
            continue
        text = carrier_text(path)
        if text is None:
            report.block("carrier-unreadable", rel, 0, f"{name} carrier is not readable UTF-8 text")
            continue
        if mode == "segment":
            segment = governance_segment(text)
            if segment is None:
                report.block("carrier-structure", rel, 0,
                             f"{GOV_BEGIN}/{GOV_END} is not a well-formed pair; the preset would degrade to the factory persona")
                continue
            text = segment
        if not text.strip():
            report.block("carrier-empty", rel, 0, f"{name} carrier is empty")
            continue
        sides[name] = text
        report.scanned += 1
        scan_drive_paths(report, rel, text)

    usable = [name for name, _rel, _mode in CARRIERS if sides[name] is not None]
    if len(usable) != len(CARRIERS):
        report.skip("parity comparison (a carrier is unusable)")
        return report

    for kind, value in REQUIRED_FACTS:
        for name, rel, _mode in CARRIERS:
            if value in (sides[name] or ""):
                report.exempt(f"parity-{kind}")
            else:
                report.block("parity-drift", rel, 0,
                             f"{kind} '{value}' is missing from the {name} carrier")

    known = load_registry_ids(root)
    if not known:
        report.skip("gate-id cross-check (registry.json unreadable)")
    else:
        for name, rel, _mode in CARRIERS:
            for identifier in sorted(set(GATE_ID.findall(sides[name] or ""))):
                if identifier in known:
                    report.exempt("gate-id-known")
                else:
                    report.block("stale-gate-id", rel, 0,
                                 f"names gate id '{identifier}', which governance/registry.json does not ship")
    return report


# --------------------------------------------------------------------------- #
# self-check
# --------------------------------------------------------------------------- #

FIXTURE_REGISTRY = {
    "version": 1,
    "gates": [
        {"id": "g00-meta", "title": "meta", "script": "governance/gates/g00_meta.py", "tier": "P0",
         "rules": ["r"], "platforms": ["nt"], "requires": ["python"], "selfcheck": True},
        {"id": "g16-skill-preset-parity", "title": "parity", "script": "governance/gates/g16_skill_preset_parity.py",
         "tier": "P0", "rules": ["r"], "platforms": ["nt"], "requires": ["python"], "selfcheck": True},
    ],
}


def build_fixture(kind: str, base: str) -> str:
    """Write a three-carrier fixture; ``kind`` selects the injected defect."""
    skill_body = "\n".join([
        "# skill",
        "run `npm run check:governance`",
        "index: docs/INDEX.md",
        "carrier: preset/allin/allin.patch.yml",
        "records: docs/记录/",
        "gates: g00-meta",
    ])
    preset_body = "\n".join([
        MARKER_BEGIN_LINE,
        "run `npm run check:governance`",
        "index: docs/INDEX.md",
        "carrier: preset/allin/allin.patch.yml",
        "records: docs/记录/",
        "gates: g00-meta",
        MARKER_END_LINE,
    ])
    agent_body = preset_body
    if kind == "fact-dropped":
        skill_body = "\n".join(ln for ln in skill_body.splitlines() if "docs/INDEX.md" not in ln)
    if kind == "machine-path":
        # 盘符用拼接写出：g09-python-hygiene 的 escaped-path-literal 不给夹具豁免
        skill_body += "\ninterpreter: " + ("E" + ":/Python314/python.exe") + "\n"
    if kind == "stale-gate-id":
        skill_body += "\ngates: g99-does-not-exist\n"
    if kind == "preset-unmarked":
        preset_body = preset_body.replace(MARKER_BEGIN_LINE, "").replace(MARKER_END_LINE, "")
        agent_body = preset_body
    if kind == "agent-drift":
        agent_body = "\n".join(ln for ln in agent_body.splitlines() if "docs/记录/" not in ln)
    if kind == "agent-machine-path":
        agent_body = agent_body.replace(
            MARKER_END_LINE, "root: " + ("D" + ":/projects/allin") + "\n" + MARKER_END_LINE)

    bodies = {"skill": skill_body, "preset": preset_body, "agent": agent_body}
    for name, rel, _mode in CARRIERS:
        if kind == f"{name}-missing":
            continue
        path = Path(base) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bodies[name] + "\n", encoding="utf-8", newline="\n")

    registry_path = Path(base) / "tools" / "gate" / "governance" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(FIXTURE_REGISTRY, indent=2) + "\n", encoding="utf-8", newline="\n")
    return base


SELFCHECK_CASES = [
    ("clean", "all carriers agree", True),
    ("fact-dropped", "a core fact vanished from one carrier", False),
    ("machine-path", "a drive path entered the skill", False),
    ("stale-gate-id", "the skill names a gate that is not shipped", False),
    ("preset-unmarked", "the preset lost its governance markers", False),
    ("skill-missing", "the skill carrier is gone", False),
    ("agent-missing", "the archived agent carrier is gone", False),
    ("agent-drift", "the archived agent carrier lost a core fact", False),
    ("agent-machine-path", "a drive path entered the archived agent carrier", False),
]


def selfcheck() -> int:
    check = govlib.SelfCheck(gate=GATE)
    for kind, _desc, expect_clean in SELFCHECK_CASES:
        tmp = tempfile.mkdtemp(prefix="g16-parity-")
        try:
            build_fixture(kind, tmp)
            args = argparse.Namespace(quiet=True, list_all=False)
            report = run(tmp, args)
            flagged = bool(report.findings)
            if expect_clean:
                if flagged:
                    check.quiet(kind, True)
                    print(f"  detail: {[f'{f.kind}:{f.text}' for f in report.findings][:3]}")
                else:
                    check.quiet(kind, False)
            else:
                check.detects(kind, flagged)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return check.finish()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    govlib.configure_stdio()
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    if not root.is_dir():
        print(f"ENV ERROR: root 不存在：{root}")
        return EXIT_ENV
    report = run(str(root), args)

    baseline_path = Path(args.baseline) if args.baseline else (
        govlib.GOVERNANCE_DIR / "baseline" / "g16-skill-preset-parity.txt")
    baseline = govlib.Baseline(baseline_path).load()
    if args.write_baseline:
        baseline.write(report.findings)
        print(f"wrote baseline {baseline_path} ({len(report.findings)} key(s))")
        return EXIT_OK
    if args.no_baseline:
        new = list(report.findings)
    else:
        new = baseline.filter_new(report.findings)
        for key in baseline.stale(report.findings):
            report.note(f"stale baseline key (finding is gone): {key}")
    shown = Report(title=report.title, findings=report.findings if args.list_all else new,
                   exempted=report.exempted, skipped=report.skipped, notes=report.notes,
                   scanned=report.scanned)
    print(shown.render().splitlines()[0] if args.quiet else shown.render())
    return EXIT_BLOCKING if new else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
