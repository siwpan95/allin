"""Gate g14 -- the governance preset stays mountable and stays honest.

The preset is the only artifact in this repository that a user *installs*, so its
structure is a contract:

* the governance block is present, ordered, and free of machine paths -- a drive
  letter inside it would follow every installation;
* the preset declares its own id (`allin`), so the factory `cordis`/`standard`
  presets remain available and a failed mount degrades instead of breaking a
  session;
* the plugin-name sequence equals the shipped preset's sequence, which turns
  "upstream reshaped the capability set" into a red gate instead of a surprise;
* every gate id the persona names exists in the registry, so the text cannot
  advertise a check that is not shipped;
* the in-repository files the persona tells the agent to read exist.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Report  # noqa: E402

GATE = "g14-preset"
TITLE = "governance: the preset stays mountable and honest"

# In allin the active governance preset is the cordis declarative carrier at
# preset/allin/allin.patch.yml (not a root-level governance/preset/ copy).
PRESET = "preset/allin/allin.patch.yml"
SHIPPED = "packages/bundle/web-app/presets/cordis.patch.yml"

BEGIN = "<!-- GOVERNANCE:BEGIN -->"
END = "<!-- GOVERNANCE:END -->"
DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")
PLUGIN_NAME = re.compile(r"^\s+name: '([^']+)'\s*$", re.MULTILINE)
GATE_ID = re.compile(r"`(g\d\d-[a-z-]+)`")
REQUIRED_REFERENCES = ("docs/INDEX.md", "docs/规范/SPEC-001-铁律.md", "docs/规范/SPEC-002-协作工作流程.md", "docs/事实源/本机事实.md")
REQUIRED_DECLARATIONS = ("- id: preset-allin", "name: '@deepseek-ai/dsh-agent-preset'", "id: allin", "order: 5")

#: Profile location probed for installed bundles: it lives outside the repository,
#: which is exactly why a repository move can break it without any in-repo gate noticing.
PROFILE_RELATIVE = ("profiles", "web")


def default_profile_dir() -> Path:
    """The active profile directory, derived from the environment, never hard-coded."""
    home = os.environ.get("DSH_HOME")
    base = Path(home) if home else Path(os.environ.get("USERPROFILE") or Path.home()) / ".dsh"
    return base.joinpath(*PROFILE_RELATIVE)


def profile_findings(profile: Path, report: Report) -> None:
    """Judge the profile's own bundle dependencies.

    A bundle installed with ``link:`` points at a directory elsewhere on disk; move
    or rename that directory and the link dangles, the plugin manager can no longer
    resolve the bundle, and a restarted DSH silently loses the preset. Nothing
    inside the repository can see that, so the probe reads the profile manifest.

    Only ``link:``/``file:`` dependencies are judged: the shipped ``@deepseek-ai/*``
    bundles resolve from the DSH installation rather than from the profile, and
    they are the installation's business, not a repository move's.
    """
    manifest = profile / "package.json"
    if not manifest.is_file():
        report.skip(f"profile manifest absent at {profile}", 1)
        return
    try:
        declaration = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.block("profile-manifest", str(manifest), 0, f"invalid JSON: {error}")
        return

    dependencies = declaration.get("dependencies", {}) or {}
    linked = {str(name): str(spec) for name, spec in dependencies.items()
              if isinstance(spec, str) and spec.startswith(("link:", "file:"))}
    bundles = declaration.get("dsh", {}).get("profile", {}).get("bundles", []) or []
    if not linked:
        report.skip("profile installs no local bundle; nothing a move could break", 1)
        return

    for name, spec in sorted(linked.items()):
        relative = spec.split(":", 1)[1]
        declared = Path(relative)
        target = declared if declared.is_absolute() else (profile / relative)
        if not target.exists():
            report.block("bundle-unresolved", spec, 0,
                         f"{name}: link target {target} does not exist "
                         "(the source directory was moved or renamed); re-run the plugin add")
            continue
        installed = profile / "node_modules" / name
        if not installed.exists():
            # Path.exists() follows symlinks, so a dangling link lands here too.
            report.block("bundle-unresolved", str(installed), 0,
                         f"{name}: not installed under the profile (dangling link or missing install)")
            continue
        package = installed / "package.json"
        if not package.is_file():
            report.block("bundle-unresolved", str(installed), 0, f"{name}: bundle has no package.json")
            continue
        try:
            meta = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            report.block("profile-manifest", str(package), 0, f"invalid JSON: {error}")
            continue
        patch_relative = (meta.get("dsh", {}).get("bundle", {}) or {}).get("patch")
        if not patch_relative:
            report.exempt("bundle declares no patch")
            continue
        patch = installed / str(patch_relative)
        if not patch.is_file():
            report.block("bundle-patch-missing", str(patch), 0,
                         f"{name}: declares dsh.bundle.patch={patch_relative}, which does not exist")
            continue
        patch_text = govlib.read_text(patch) or ""
        if (BEGIN in patch_text) != (END in patch_text):
            report.block("bundle-markers", str(patch), 0, f"{name}: governance markers are unpaired in the patch")
            continue
        report.note(f"profile bundle {name} resolves to {installed} (patch {patch_relative})")

    for name in bundles:
        if str(name) not in linked:
            report.exempt("bundle resolved from the DSH installation, not the profile")


def plugin_names(text: str) -> list[str]:
    """The plugin-name sequence of a preset declaration, in order."""
    return PLUGIN_NAME.findall(text)


def scan(root: Path, registry_path: Path, profile: Path | None = None) -> Report:
    """Judge the preset against the shipped declaration, the registry, and the profile."""
    report = Report(title=TITLE)
    preset_path = root / PRESET
    if not preset_path.is_file():
        report.block("preset-missing", PRESET, 0, "the governance preset is not in the tree")
        return report
    text = govlib.read_text(preset_path) or ""
    report.scanned += 1

    for declaration in REQUIRED_DECLARATIONS:
        if declaration not in text:
            report.block("declaration", PRESET, 0, f"missing declaration: {declaration}")

    if BEGIN not in text or END not in text:
        report.block("markers", PRESET, 0, "the governance block markers are not both present")
        return report
    if text.index(BEGIN) > text.index(END):
        report.block("markers", PRESET, 0, "the governance markers are out of order")
        return report
    block = text.split(BEGIN, 1)[1].split(END, 1)[0]

    for number, line in enumerate(block.splitlines(), start=1):
        if DRIVE_PATH.search(line):
            report.block("machine-path", PRESET, number, line)

    for reference in REQUIRED_REFERENCES:
        # The allin preset names each reference inside the governance block as
        # `<仓根>/docs/...`, so match the bare path fragment (not a backtick-wrapped
        # token) and then confirm the file exists on disk.
        if reference not in block:
            report.block("reference-text", PRESET, 0, f"the persona no longer names {reference}")
        elif not (root / reference).is_file():
            report.block("reference-missing", PRESET, 0, f"{reference} is named but does not exist")

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registered = {str(entry.get("id")) for entry in registry.get("gates", []) if isinstance(entry, dict)}
    for identifier in sorted(set(GATE_ID.findall(block))):
        if identifier not in registered:
            report.block("unknown-gate", PRESET, 0, f"the persona names {identifier}, which is not registered")

    shipped_path = root / SHIPPED
    if not shipped_path.is_file():
        report.skip("shipped preset not present; capability drift unchecked", 1)
        if profile is not None:
            profile_findings(profile, report)
        return report
    shipped = plugin_names(govlib.read_text(shipped_path) or "")
    current = plugin_names(text)
    if not shipped or not current:
        report.skip("no plugin names extracted; drift unchecked", 1)
    elif shipped != current:
        report.block("capability-drift", PRESET, 0,
                     f"plugin sequence differs from the shipped preset ({len(current)} vs {len(shipped)} entries); "
                     "replay the patch as documented in governance/preset/README.md")
    else:
        report.exempt("plugin sequence matches the shipped preset", 1)
    if profile is not None:
        profile_findings(profile, report)
    return report


def selfcheck() -> int:
    """Prove structural drift, missing markers, and machine paths are caught."""
    check = govlib.SelfCheck(gate=GATE)
    base = (
        "- insert:\n"
        "    - id: preset-allin\n"
        "      name: '@deepseek-ai/dsh-agent-preset'\n"
        "      config:\n"
        "        id: allin\n"
        "        order: 5\n"
        "        plugins:\n"
        "          - id: persona\n"
        "            name: '@deepseek-ai/dsh-persona'\n"
        "            config:\n"
        "              prefix: |-\n"
        "                base text\n"
        f"                {BEGIN}governance text naming `docs/INDEX.md`, `docs/规范/SPEC-001-铁律.md`, "
"`docs/规范/SPEC-002-协作工作流程.md`, `docs/事实源/本机事实.md` and `g00-meta`\n"
        f"                {END}\n"
        "          - id: agent-instructions\n"
        "            name: '@deepseek-ai/dsh-agent-instructions'\n"
    )
    registry = {"version": 1, "gates": [{"id": "g00-meta"}]}
    shipped = ("- insert:\n"
               "    - id: preset-cordis\n"
               "      name: '@deepseek-ai/dsh-agent-preset'\n"
               "      config:\n"
               "        id: cordis\n"
               "        order: 4\n"
               "        plugins:\n"
               "          - id: persona\n"
               "            name: '@deepseek-ai/dsh-persona'\n"
               "          - id: agent-instructions\n"
               "            name: '@deepseek-ai/dsh-agent-instructions'\n")

    def sandbox_with(preset_text: str) -> govlib.Sandbox:
        box = govlib.Sandbox()
        box.write("preset/allin/allin.patch.yml", preset_text)
        box.write("docs/INDEX.md", "# index\n")
        box.write("docs/规范/SPEC-001-铁律.md", "# spec\n")
        box.write("docs/规范/SPEC-002-协作工作流程.md", "# spec\n")
        box.write("docs/事实源/本机事实.md", "# facts\n")
        box.write("tools/gate/governance/registry.json", json.dumps(registry))
        box.write(SHIPPED, shipped)
        return box

    with sandbox_with(base) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json")
        check.quiet("a mountable preset that matches the shipped sequence", bool(report.findings))

    with sandbox_with(base.replace(END, "")) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json")
        check.detects("a missing governance end marker",
                      any(finding.kind == "markers" for finding in report.findings))

    with sandbox_with(base.replace("governance text", "governance text in D:\\\\work")) as sandbox:  # gov-python: allow
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json")
        check.detects("a machine path inside the governance block",
                      any(finding.kind == "machine-path" for finding in report.findings))

    drifted = base.replace("          - id: agent-instructions\n"
                           "            name: '@deepseek-ai/dsh-agent-instructions'\n", "")
    with sandbox_with(drifted) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json")
        check.detects("a plugin sequence that no longer matches the shipped preset",
                      any(finding.kind == "capability-drift" for finding in report.findings))

    with sandbox_with(base.replace("`g00-meta`", "`g99-ghost`")) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json")
        check.detects("a persona naming an unregistered gate",
                      any(finding.kind == "unknown-gate" for finding in report.findings))

    # Profile probes: the failure mode of a moved repository is a dangling link outside it.
    def profile_sandbox(spec: str, patch: str | None = None, name: str = "mine-bundle") -> govlib.Sandbox:
        """A sandbox with a valid in-repo preset plus a profile that links a local bundle."""
        box = sandbox_with(base)
        source = box.path / "elsewhere" / name
        source.mkdir(parents=True, exist_ok=True)
        bundle_manifest = json.dumps({"name": name, "dsh": {"bundle": {"patch": "cordis.patch.yml"}}}) + "\n"
        (source / "package.json").write_text(bundle_manifest, encoding="utf-8", newline="\n")
        box.write(f"profile/node_modules/{name}/package.json", bundle_manifest)
        if patch is not None:
            (source / "cordis.patch.yml").write_text(patch, encoding="utf-8", newline="\n")
            box.write(f"profile/node_modules/{name}/cordis.patch.yml", patch)
        box.write("profile/package.json",
                  json.dumps({"name": "dsh-profile-web", "private": True,
                              "dependencies": {name: spec},
                              "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", name]}}}) + "\n")
        return box

    with profile_sandbox("link:../elsewhere", f"{BEGIN}ok{END}\n") as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json",
                      profile=sandbox.path / "profile")
        check.quiet("a profile whose local bundle resolves", bool(report.findings))

    with profile_sandbox("link:../removed-by-a-move", f"{BEGIN}ok{END}\n") as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json",
                      profile=sandbox.path / "profile")
        check.detects("a link target that a move removed",
                      any(finding.kind == "bundle-unresolved" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        box = sandbox_with(base)
        box.write("profile/package.json",
                  json.dumps({"name": "dsh-profile-web",
                              "dependencies": {"mine-bundle": "link:../elsewhere"},
                              "dsh": {"profile": {"bundles": ["mine-bundle"]}}}) + "\n")
        report = scan(box.path, box.path / "tools/gate/governance/registry.json", profile=box.path / "profile")
        check.detects("a local bundle that is not installed under the profile",
                      any(finding.kind == "bundle-unresolved" for finding in report.findings))

    with profile_sandbox("link:../elsewhere", None) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json",
                      profile=sandbox.path / "profile")
        check.detects("a bundle whose declared patch is missing",
                      any(finding.kind == "bundle-patch-missing" for finding in report.findings))

    with profile_sandbox("link:../elsewhere", f"{BEGIN}no end marker here\n") as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json",
                      profile=sandbox.path / "profile")
        check.detects("a mounted patch with unpaired governance markers",
                      any(finding.kind == "bundle-markers" for finding in report.findings))

    with sandbox_with(base) as sandbox:
        report = scan(sandbox.path, sandbox.path / "tools/gate/governance/registry.json",
                      profile=sandbox.path / "absent-profile")
        check.detects("an absent profile is a counted skip, never a pass",
                      any("profile manifest absent" in reason for reason in report.skipped))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--registry", default=None, help="registry file (default: governance/registry.json)")
    parser.add_argument("--profile", default=None,
                        help="DSH profile directory to probe for installed bundles "
                             "(default: $DSH_HOME/profiles/web, or the user profile's .dsh)")
    parser.add_argument("--no-profile", dest="profile_check", action="store_false",
                        help="skip the profile probe (repository-only judgment)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    # The governance subtree lives at <root>/tools/gate/governance/, so the work
    # tree root is discovered by walking up to the git toplevel (layout-independent)
    # rather than assuming a fixed number of parent segments.
    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    registry = Path(args.registry) if args.registry else govlib.GOVERNANCE_DIR / "registry.json"
    profile = None
    if args.profile_check:
        profile = Path(args.profile).resolve() if args.profile else default_profile_dir()
    report = scan(root, registry, profile=profile)
    print(report.render().splitlines()[0] if args.quiet else report.render())
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
