"""Gate g10 -- every gate must fail loudly when it cannot judge.

The recorded rule: a script that cannot find what it needs must stop with a
named cause. Silent fallback to an unusable path is the hardest failure class to
diagnose, because the run "succeeds" while judging nothing.

The probe is uniform: run each registered gate with a root that cannot exist and
require a non-zero exit **and** a message. A gate that exits zero -- or exits
non-zero in silence -- fails this gate.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, GateError, Report  # noqa: E402

GATE = "g10-failloud-probe"
TITLE = "governance: gates refuse an unusable input loudly"
PROBE_TIMEOUT_SECONDS = 300


def probe(python: str, script: Path, root: Path) -> tuple[int, str]:
    """Run one gate against an impossible root and capture its answer."""
    completed = subprocess.run(
        [python, str(script), "--root", str(root), "--quiet"],
        cwd=str(script.parent.parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=PROBE_TIMEOUT_SECONDS,
    )
    text = completed.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    return completed.returncode, text.strip()


def inspect(root: Path, registry_path: Path, python: str) -> Report:
    """Probe every registered gate for loud refusal."""
    report = Report(title=TITLE)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = registry.get("gates")
    if not isinstance(entries, list) or not entries:
        raise GateError(f"{registry_path}: 'gates' must be a non-empty list")
    with tempfile.TemporaryDirectory(prefix="gov-failloud-") as scratch:
        impossible = Path(scratch) / "not-a-work-tree"
        for entry in entries:
            script = root / str(entry["script"])
            report.scanned += 1
            code, output = probe(python, script, impossible)
            if code == 0:
                report.block("silent-zero", str(entry.get("script")), 0,
                             f"{entry.get('id')}: exits 0 on an unusable root")
                continue
            if not output:
                report.block("silent-failure", str(entry.get("script")), 0,
                             f"{entry.get('id')}: exits {code} with no message")
                continue
            report.exempt("refuses loudly", 1)
    return report


def _fixture(epilogue: str) -> str:
    return (
        "import argparse, sys\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--root', default='.')\n"
        "parser.add_argument('--quiet', action='store_true')\n"
        "parser.add_argument('--selfcheck', action='store_true')\n"
        "parser.add_argument('--baseline')\n"
        "parser.add_argument('--no-baseline', action='store_true')\n"
        "parser.add_argument('--write-baseline', action='store_true')\n"
        "parser.add_argument('--list-all', action='store_true')\n"
        "args = parser.parse_args()\n"
        + epilogue
    )


def selfcheck() -> int:
    """Prove a silent gate is caught and a loud one is not."""
    check = govlib.SelfCheck(gate=GATE)
    loud = _fixture(
        "import pathlib\n"
        "if not pathlib.Path(args.root).is_dir():\n"
        "    print('error: root does not exist: ' + args.root, file=sys.stderr)\n"
        "    sys.exit(3)\n"
        "sys.exit(0)\n"
    )
    silent_zero = _fixture("sys.exit(0)\n")
    silent_failure = _fixture(
        "import pathlib\n"
        "if not pathlib.Path(args.root).is_dir():\n"
        "    sys.exit(3)\n"
        "sys.exit(0)\n"
    )
    with govlib.Sandbox() as sandbox:
        sandbox.write("governance/gates/loud.py", loud)
        sandbox.write("governance/gates/silent_zero.py", silent_zero)
        sandbox.write("governance/gates/silent_failure.py", silent_failure)
        registry = {"version": 1, "gates": [
            {"id": "loud", "script": "governance/gates/loud.py"},
            {"id": "silent-zero", "script": "governance/gates/silent_zero.py"},
            {"id": "silent-failure", "script": "governance/gates/silent_failure.py"},
        ]}
        registry_path = sandbox.path / "governance/registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        report = inspect(sandbox.path, registry_path, sys.executable)
        kinds = {finding.kind for finding in report.findings}
        check.detects("a gate that exits zero on an unusable root", "silent-zero" in kinds)
        check.detects("a gate that fails without a message", "silent-failure" in kinds)
        check.quiet("a gate that refuses loudly",
                    any("loud" in finding.text for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree (default: discovered from this file)")
    parser.add_argument("--registry", default=None, help="registry file (default: governance/registry.json)")
    parser.add_argument("--python", default=sys.executable, help="interpreter used to run each gate")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    # The governance tree lives at <root>/governance/; derive that root from this
    # file's location so the gate works wherever the subtree is placed (it now
    # lives under allin/tools/gate/governance/, not the repo root).
    root = Path(args.root).resolve() if args.root else govlib.GOVERNANCE_DIR.parent
    registry = Path(args.registry) if args.registry else govlib.GOVERNANCE_DIR / "registry.json"
    report = inspect(root, registry, args.python)
    print(report.render().splitlines()[0] if args.quiet else report.render())
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
