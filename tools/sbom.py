# -*- coding: utf-8 -*-
"""Generate a CycloneDX SBOM for this repository's declared dependencies.

Scope is deliberately the *declared* surface: ``package.json`` files under
``platform/`` and ``pyproject.toml`` under ``kernel/``. That is the part a
consumer inherits when they clone this repository, and it is the part that can
be produced without a lockfile or a network round trip.

The research consensus is explicit about the rollout order: generate the SBOM on
release and **attest, don't gate**. Nothing here fails a build; the artifact is
evidence for whoever asks "what is in this thing".

Output: ``tools/gate/audit/sbom.cdx.json`` (the audit directory is ignored, so
the artifact never becomes stale tracked content).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "gate" / "audit" / "sbom.cdx.json"

PY_NAMED = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(?:[=<>!~]=?|@)\s*([^,;\s]+)", re.MULTILINE)
PY_PEP508 = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*$", re.MULTILINE)


def node_components() -> list[dict]:
    found: list[dict] = []
    for manifest in sorted(ROOT.glob("platform/**/package.json")):
        if "node_modules" in manifest.parts:
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        scope = manifest.parent.relative_to(ROOT).as_posix()
        for field in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, spec in sorted((payload.get(field) or {}).items()):
                found.append({
                    "type": "library",
                    "name": name,
                    "version": normalise_spec(spec),
                    "purl": f"pkg:npm/{name}",
                    "scope": field,
                    "evidence": f"{scope}/package.json",
                })
    return found


def normalise_spec(spec: str) -> str:
    """A range is not a version; keep it, but strip the range operators."""
    cleaned = str(spec).strip().lstrip("^~>=< v")
    return cleaned or "unspecified"


def python_components() -> list[dict]:
    found: list[dict] = []
    for manifest in sorted(list(ROOT.glob("kernel/**/pyproject.toml")) + [ROOT / "pyproject.toml"]):
        if not manifest.is_file():
            continue
        try:
            text = manifest.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        block = re.search(r"^\[(?:project\.)?(?:dependencies|optional-dependencies)[^\]]*\]\s*$(.*?)(?=^\[|\Z)",
                          text, re.MULTILINE | re.DOTALL)
        if not block:
            continue
        scope = manifest.parent.relative_to(ROOT).as_posix()
        for line in block.group(1).splitlines():
            line = line.strip().strip(",").strip('"').strip("'")
            if not line or line.startswith("#"):
                continue
            match = PY_NAMED.match(line) or PY_PEP508.match(line)
            if not match:
                continue
            name = match.group(1)
            version = match.group(2) if match.lastindex and match.lastindex > 1 else "unspecified"
            found.append({
                "type": "library",
                "name": name,
                "version": version.lstrip("= "),
                "purl": f"pkg:pypi/{name}",
                "scope": "dependencies",
                "evidence": f"{scope}/pyproject.toml",
            })
    return found


def build() -> dict:
    components = node_components() + python_components()
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:allin-sbom-{int(dt.datetime.now().timestamp())}",
        "version": 1,
        "metadata": {
            "timestamp": stamp,
            "component": {"type": "application", "name": "allin", "version": "0.1.0"},
            "properties": [
                {"name": "sbom.scope", "value": "declared dependencies only (no lockfile resolution)"},
                {"name": "sbom.gate", "value": "attest-only: generated on demand, does not fail a build"},
            ],
        },
        "components": components,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="generate a CycloneDX SBOM of declared dependencies")
    parser.add_argument("--out", default=str(OUT), help=f"output path (default: {OUT})")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    bom = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bom, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not args.quiet:
        npm = sum(1 for c in bom["components"] if c["purl"].startswith("pkg:npm/"))
        pypi = sum(1 for c in bom["components"] if c["purl"].startswith("pkg:pypi/"))
        print(f"SBOM -> {out.relative_to(ROOT).as_posix()}  components={len(bom['components'])} (npm {npm} / pypi {pypi})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
