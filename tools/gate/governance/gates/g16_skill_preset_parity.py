"""Gate g16 -- the two governance carriers say the same thing.

The governance facts reach an agent in two shapes that have to agree:

* ``.workbuddy/skills/allin-governance-agent/SKILL.md`` -- the WorkBuddy skill,
  loaded by an agent that runs inside this workspace;
* the ``GOVERNANCE:BEGIN/END`` segment of ``preset/allin/allin.patch.yml`` --
  the same facts injected into a DeepSeek Harness agent-preset.

They drift because they are edited in different places, and the drift is
invisible until an agent follows a command that no longer exists. This gate
turns "keep the two in sync" from a rule written in prose into an exit code:

* both carriers exist and carry a non-empty governance surface;
* the preset's governance segment is a well-formed marked pair;
* every **declared core fact** (the canonical command and the canonical hub
  paths) appears on *both* sides -- one side alone is drift;
* every gate id either carrier names exists in ``governance/registry.json``, so
  neither side can advertise a check that is not shipped;
* **neither carrier carries a machine drive path.** This is the gap that let a
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
TITLE = "governance: the skill and the DSH preset carry the same facts"

#: The WorkBuddy-side carrier and the DSH-side carrier.
SKILL_REL = ".workbuddy/skills/allin-governance-agent/SKILL.md"
PRESET_REL = "preset/allin/allin.patch.yml"

GOV_BEGIN = "GOVERNANCE:BEGIN"
GOV_END = "GOVERNANCE:END"

#: Facts that must be provably present on *both* sides. Deliberately small and
#: canonical: a fact only one carrier happens to mention is normal, a fact the
#: two carriers disagree about is drift.
MUST_APPEAR_IN_BOTH: list[tuple[str, str]] = [
    ("command", "npm run check:governance"),
    ("path", "docs/INDEX.md"),
    ("path", "preset/allin/allin.patch.yml"),
    ("path", "docs/记录/"),
]

GATE_ID = re.compile(r"\bg\d\d-[a-z][a-z-]*\b")
DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")
URL = re.compile(r"https?://\S+")


def read_text(path: Path) -> str | None:
    return govlib.read_text(path)


def governance_segment(text: str) -> str | None:
    """The GOVERNANCE:BEGIN/END body, or None when the pair is not well-formed."""
    start = text.find(GOV_BEGIN)
    if start < 0:
        return None
    body_at = start + len(GOV_BEGIN)
    end = text.find(GOV_END, body_at)
    if end < 0:
        return None
    return text[body_at:end]


def load_registry_ids(root: str) -> set[str]:
    path = Path(root) / "tools" / "gate" / "governance" / "registry.json"
    text = read_text(path)
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
    sides: dict[str, str | None] = {"skill": None, "preset": None}
    rels = {"skill": SKILL_REL, "preset": PRESET_REL}

    for name, rel in rels.items():
        path = Path(root) / rel
        if not path.is_file():
            report.block("carrier-missing", rel, 0, f"{name} carrier is missing; the governance facts have no {name} home")
            continue
        text = read_text(path)
        if text is None:
            report.block("carrier-unreadable", rel, 0, f"{name} carrier is not readable UTF-8 text")
            continue
        if name == "preset":
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

    if sides["skill"] is None or sides["preset"] is None:
        report.skip("parity comparison (a carrier is unusable)")
        return report

    for kind, value in MUST_APPEAR_IN_BOTH:
        for name in ("skill", "preset"):
            if value in (sides[name] or ""):
                report.exempt(f"parity-{kind}")
            else:
                report.block("parity-drift", rels[name], 0,
                             f"{kind} '{value}' is missing from the {name} side while the other side carries it")

    known = load_registry_ids(root)
    if not known:
        report.skip("gate-id cross-check (registry.json unreadable)")
    else:
        for name in ("skill", "preset"):
            for identifier in sorted(set(GATE_ID.findall(sides[name] or ""))):
                if identifier in known:
                    report.exempt("gate-id-known")
                else:
                    report.block("stale-gate-id", rels[name], 0,
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
    """Write a two-carrier fixture; ``kind`` selects the injected defect."""
    skill_body = "\n".join([
        "# skill",
        "run `npm run check:governance`",
        "index: docs/INDEX.md",
        "carrier: preset/allin/allin.patch.yml",
        "records: docs/记录/",
        "gates: g00-meta",
    ])
    preset_body = "\n".join([
        GOV_BEGIN,
        "run `npm run check:governance`",
        "index: docs/INDEX.md",
        "carrier: preset/allin/allin.patch.yml",
        "records: docs/记录/",
        "gates: g00-meta",
        GOV_END,
    ])
    if kind == "fact-dropped":
        skill_body = "\n".join(ln for ln in skill_body.splitlines() if "docs/INDEX.md" not in ln)
    if kind == "machine-path":
        skill_body += "\ninterpreter: E:/Python314/python.exe\n"
    if kind == "stale-gate-id":
        skill_body += "\ngates: g99-does-not-exist\n"
    if kind == "preset-unmarked":
        preset_body = preset_body.replace(GOV_BEGIN, "").replace(GOV_END, "")

    skill_path = Path(base) / SKILL_REL
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    if kind != "skill-missing":
        skill_path.write_text(skill_body + "\n", encoding="utf-8", newline="\n")
    preset_path = Path(base) / PRESET_REL
    preset_path.parent.mkdir(parents=True, exist_ok=True)
    preset_path.write_text(preset_body + "\n", encoding="utf-8", newline="\n")

    registry_path = Path(base) / "tools" / "gate" / "governance" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(FIXTURE_REGISTRY, indent=2) + "\n", encoding="utf-8", newline="\n")
    return base


SELFCHECK_CASES = [
    ("clean", "both carriers agree", True),
    ("fact-dropped", "a core fact vanished from one side", False),
    ("machine-path", "a drive path entered the skill", False),
    ("stale-gate-id", "the skill names a gate that is not shipped", False),
    ("preset-unmarked", "the preset lost its governance markers", False),
    ("skill-missing", "the skill carrier is gone", False),
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
