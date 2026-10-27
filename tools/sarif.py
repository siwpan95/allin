# -*- coding: utf-8 -*-
"""Export governance findings as SARIF 2.1.0 for code-scanning annotations.

A gate that prints to stdout is a gate only humans see. CI can annotate a pull
request with the exact file and line, but only if the findings arrive in a
format it understands -- SARIF is that format. This tool runs every registered
gate and turns its ``BLOCK`` lines into SARIF results.

By default the gates run **with** their baseline, so only *new* findings are
annotated: a frozen finding is known debt, and printing known debt on every pull
request is how annotations get ignored. ``--include-frozen`` runs the gates with
``--no-baseline --list-all`` when the full ledger is wanted (audits, dashboards).

Scope note, and it matters: this is **export, not enforcement**. The exit code
is 0 even when findings exist, because turning CI annotations into a second
blocking channel would mean two sources of truth about "did this pass" -- the
gates are that source. ``--strict`` opts into a non-zero exit for pipelines
that want the annotations to be load-bearing.

Output: ``tools/gate/audit/gate-findings.sarif.json`` (the audit directory is
ignored; SARIF is regenerated on demand, never committed).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# registry.json 里的 script 相对 tools/gate/（与 run.ts 的 ROOT 口径一致），
# 而 registry.json 本身在 tools/gate/governance/ 下 —— 两个基准不是同一层。
GATE_HOME = ROOT / "tools" / "gate"
REGISTRY = GATE_HOME / "governance" / "registry.json"
OUT = ROOT / "tools" / "gate" / "audit" / "gate-findings.sarif.json"

# `  BLOCK docs/INDEX.md:42: path-ref: path does not exist: docs/NOPE.md`
BLOCK = re.compile(r"^\s*BLOCK\s+(?P<path>.+?):(?P<line>\d+):\s+(?P<kind>[^:]+):\s+(?P<text>.*)$")

SARIF_VERSION = "2.1.0"
SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"


def gates() -> list[dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return list(data.get("gates", []))


def run_gate(gate: dict, python: str, include_frozen: bool) -> tuple[list[dict], str | None]:
    """(results, execution error) for one gate."""
    script = GATE_HOME / gate["script"]
    if not script.is_file():
        return [], f"{gate['id']}: script missing at {gate['script']}"
    args = [python, str(script)]
    if include_frozen:
        args += ["--no-baseline", "--list-all"]
    completed = subprocess.run(
        args,
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # 0 = clean, 1 = blocking findings, anything else is the gate failing to run,
    # which is an execution error and must not be silently read as "no findings".
    if completed.returncode not in (0, 1):
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return [], f"{gate['id']}: exit {completed.returncode} {detail[-1] if detail else ''}"
    results = []
    for line in completed.stdout.splitlines():
        match = BLOCK.match(line)
        if not match:
            continue
        results.append({
            "ruleId": gate["id"],
            "level": "error",
            "message": {"text": f"[{match.group('kind').strip()}] {match.group('text').strip()}"},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": match.group("path").strip(), "uriBaseId": "%SRCROOT%"},
                    "region": {"startLine": int(match.group("line"))},
                }
            }],
        })
    return results, None


def build(results: list[dict], notifications: list[dict], rules: list[dict]) -> dict:
    return {
        "$schema": SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": "allin-governance",
                    "informationUri": "https://gitee.com/siwpan/allin",
                    "semanticVersion": "1.0.0",
                    "rules": rules,
                }
            },
            "results": results,
            "invocations": [{
                "executionSuccessful": not notifications,
                "toolExecutionNotifications": notifications,
            }],
        }],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="export governance findings as SARIF 2.1.0")
    parser.add_argument("--out", default=str(OUT), help=f"output path (default: {OUT})")
    parser.add_argument("--python", default=sys.executable, help="interpreter that runs the gates")
    parser.add_argument("--include-frozen", action="store_true",
                        help="also report baseline-frozen findings (default: new findings only)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when findings exist")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    registry = gates()
    results: list[dict] = []
    notifications: list[dict] = []
    rules: list[dict] = []
    per_gate: dict[str, int] = {}
    for gate in registry:
        found, error = run_gate(gate, args.python, args.include_frozen)
        rules.append({
            "id": gate["id"],
            "shortDescription": {"text": gate.get("title", gate["id"])},
            "properties": {"tier": gate.get("tier", ""), "context": gate.get("context", "local")},
        })
        if error:
            notifications.append({"level": "error", "message": {"text": error}})
            continue
        per_gate[gate["id"]] = len(found)
        results.extend(found)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(results, notifications, rules), ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")

    if not args.quiet:
        rel = out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else str(out)
        print(f"SARIF -> {rel}  gates={len(registry)} results={len(results)} "
              f"executionErrors={len(notifications)}")
        for gate_id, count in sorted(per_gate.items(), key=lambda kv: (-kv[1], kv[0])):
            if count:
                print(f"   {gate_id}: {count}")
        for note in notifications:
            print(f"   execution error: {note['message']['text']}")
    return 1 if (args.strict and (results or notifications)) else 0


if __name__ == "__main__":
    sys.exit(main())
