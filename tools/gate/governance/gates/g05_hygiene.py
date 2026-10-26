"""Gate g05 -- repository hygiene that a clone actually has to live with.

Judged against the **index**, and only against tracked paths: a TypeScript
monorepo legitimately contains ``dist/``, ``node_modules/`` and ``build.ts``
sources, so the question is never "does this directory name exist" but "is an
artifact or a credential tracked".

Checks:

* ``root-files``  -- LICENSE, README.md and .gitignore exist (iron rule 4's trio).
* ``gitignore``   -- the ignore file covers the credential surface: ``.env``,
  ``*.pem``, ``*.key`` and bytecode caches.
* ``artifact``    -- no tracked build/release output, bytecode, log, or
  ``*.egg-info`` directory.
* ``big-blob``    -- no tracked blob above the size ceiling. The ceiling is
  measured against this repository, not copied: the largest tracked file here is
  a generated schema just over 2 MB, so 5 MiB leaves real headroom.
* ``archive``     -- a tracked ``archive``/``archived`` directory outside the
  upstream-governed Agent Notes carries a README or MANIFEST naming what it holds.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, GateError, Report  # noqa: E402

GATE = "g05-hygiene"
TITLE = "governance: repository hygiene on the tracked surface"

MIB = 1024 * 1024
#: Measured headroom: the largest tracked file in this repository is ~2.3 MB.
BIG_BLOB_LIMIT = 5 * MIB

REQUIRED_ROOT_FILES = ("LICENSE", "README.md", ".gitignore")
REQUIRED_IGNORE_FRAGMENTS = (".env", "*.pem", "*.key", "__pycache__/")

#: Directory names that never belong in the index. ``lib`` is build output here
#: and is ignored repository-wide; a tracked ``lib/`` would also be the exact
#: shape that once hid the gate runtime from the index.
ARTIFACT_SEGMENTS = frozenset({
    ".turbo", "__pycache__", "coverage", "dist", "dist-exe", "lib", "node_modules", "out", "output",
})
#: ``build``/``release`` are ordinary *source* file names here (``scripts/build.ts``,
#: ``scripts/release/``), so they only count as artifacts inside a package or at the root.
ARTIFACT_SEGMENTS_SCOPED = frozenset({"build", "release", ".next"})
SCOPED_ROOTS = ("packages/", "apps/", "")

#: Artifact file suffixes.
ARTIFACT_SUFFIXES = (".tsbuildinfo", ".pyc", ".pyo", ".log", ".egg-info", ".dist-info")

#: Trees whose contents follow somebody else's rules.
EXEMPT_PREFIXES = (".agents/notes/archived/", "vendor/")

ANNOTATION = "gov-hygiene: allow"


def staged_blob_sizes(root: Path) -> dict[str, int]:
    """Byte size of every staged blob, read through one `git cat-file` call."""
    entries = govlib.run_git(["ls-files", "-s", "-z"], root)
    sha_to_paths: dict[str, list[str]] = {}
    order: list[str] = []
    for record in entries.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or not path:
            continue
        sha_to_paths.setdefault(parts[1], []).append(path)
        order.append(parts[1])
    if not order:
        return {}
    completed = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        cwd=str(root),
        env=govlib.git_env(),
        input="\n".join(order).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise GateError(f"git cat-file --batch-check failed: {completed.stderr.decode('utf-8', 'replace').strip()}")
    sizes: dict[str, int] = {}
    for line in completed.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
    return {path: sizes.get(sha, 0) for sha, paths in sha_to_paths.items() for path in paths}


def is_artifact_path(path: str) -> str:
    """Return the offending segment, or an empty string when the path is fine."""
    segments = path.split("/")
    for index, segment in enumerate(segments[:-1]):
        if segment in ARTIFACT_SEGMENTS:
            return segment
        if segment in ARTIFACT_SEGMENTS_SCOPED:
            prefix = "/".join(segments[:index + 1])
            if prefix in ("build", "release", ".next") or prefix.startswith(("packages/", "apps/")):
                return segment
    return ""


def scan(root: Path, *, limit: int = BIG_BLOB_LIMIT) -> Report:
    """Judge the tracked surface of ``root``."""
    report = Report(title=TITLE)
    for name in REQUIRED_ROOT_FILES:
        if not (root / name).exists():
            report.block("root-files", name, 0, f"{name}: required at the repository root")
        else:
            report.scanned += 1

    ignore_file = root / ".gitignore"
    ignore_text = govlib.read_text(ignore_file) or ""
    for fragment in REQUIRED_IGNORE_FRAGMENTS:
        if fragment not in ignore_text:
            report.block("gitignore", ".gitignore", 0, f".gitignore does not cover {fragment}")

    sizes = staged_blob_sizes(root)
    archive_dirs: dict[str, list[str]] = {}
    for path, size in sorted(sizes.items()):
        if path.startswith(EXEMPT_PREFIXES):
            report.exempt("another owner's tree")
            continue
        segment = is_artifact_path(path)
        if segment:
            report.block("artifact", path, 0, f"tracked artifact directory '{segment}/'")
            continue
        if path.endswith(ARTIFACT_SUFFIXES):
            report.block("artifact", path, 0, "tracked build or bytecode artifact")
            continue
        if size > limit:
            report.block("big-blob", path, 0, f"{size / MIB:.1f} MiB exceeds the {limit / MIB:.0f} MiB ceiling")
            continue
        segments = path.split("/")
        for index, name in enumerate(segments[:-1]):
            if name in ("archive", "archived"):
                archive_dirs.setdefault("/".join(segments[:index + 1]), []).append(path)
        report.exempt("tracked source or documentation")

    for directory, members in sorted(archive_dirs.items()):
        manifest_names = ("readme.md", "manifest.md")
        direct = [member for member in members if member.count("/") == directory.count("/") + 1]
        if direct and not any(member.rsplit("/", 1)[-1].lower() in manifest_names for member in direct):
            report.block("archive", directory, 0, "archived directory carries no README.md or MANIFEST.md")
        children = {member.rsplit("/", 1)[0] for member in members
                    if member.count("/") > directory.count("/") + 1}
        for child in sorted(children):
            inside = [member for member in members if member.startswith(child + "/")]
            if not any(member.rsplit("/", 1)[-1].lower() in manifest_names for member in inside):
                report.block("archive", child, 0, "archived subdirectory carries no README.md or MANIFEST.md")
    return report


def selfcheck() -> int:
    """Prove each hygiene check fires, and that a clean tree stays quiet."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", "node_modules/\n.env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("src/app.ts", "export const app = 1\n")
        report = scan(sandbox.path, limit=BIG_BLOB_LIMIT)
        check.quiet("a clean tracked surface", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", "node_modules/\n")
        report = scan(sandbox.path)
        kinds = {finding.kind for finding in report.findings}
        check.detects("a .gitignore missing the credential surface", "gitignore" in kinds)

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", ".env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("packages/core/lib/index.js", "module.exports = {}\n")
        sandbox.write("apps/web/dist/index.html", "<html></html>\n")
        sandbox.write("scripts/coverage/report.txt", "report\n")
        report = scan(sandbox.path)
        blocked = {finding.path for finding in report.findings}
        check.detects("a tracked package build output", "packages/core/lib/index.js" in blocked)
        check.detects("a tracked dist artifact", "apps/web/dist/index.html" in blocked)
        check.detects("a tracked coverage artifact", "scripts/coverage/report.txt" in blocked)
        check.quiet("legitimate sources stay clean",
                    "scripts/build.ts" in blocked or "scripts/release/bump.ts" in blocked)

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", ".env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("scripts/release/bump.ts", "export const bump = 1\n")
        sandbox.write("scripts/build.ts", "export const build = 1\n")
        report = scan(sandbox.path)
        check.quiet("a release/build source directory is not an artifact", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", ".env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("fixtures/large.bin", "x" * 2048)
        report = scan(sandbox.path, limit=1024)
        check.detects("a blob above the ceiling", any(finding.kind == "big-blob" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", ".env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("archive/old-thing/notes.md", "old\n")
        report = scan(sandbox.path)
        check.detects("an archived directory without a manifest",
                      any(finding.kind == "archive" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("LICENSE", "MIT\n")
        sandbox.write("README.md", "# repo\n")
        sandbox.write(".gitignore", ".env\n*.pem\n*.key\n__pycache__/\n")
        sandbox.write("archive/old-thing/MANIFEST.md", "what this holds\n")
        sandbox.write("archive/old-thing/notes.md", "old\n")
        report = scan(sandbox.path)
        check.quiet("an archived directory with a manifest", bool(report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--limit-mib", type=float, default=BIG_BLOB_LIMIT / MIB, help="blob size ceiling in MiB")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, limit=int(args.limit_mib * MIB))
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
