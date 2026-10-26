"""Gate g12 -- the work tree's object store is readable and its HEAD resolves.

The recorded accident: an external drive's online self-healing rewrote git
objects while four repositories were being written, and nothing noticed until a
human dug through git errors. Two cheap judgments catch that class immediately:

* ``HEAD^{commit}`` must resolve. ``git rev-parse --verify HEAD`` only parses the
  ref name, so it happily reports success on a repository whose objects are gone;
  the ``^{commit}`` peel forces the object to exist.
* every object reachable from HEAD must be readable -- a batch probe over the
  commit tree, not a lazy spot check.

``--deep`` adds ``git fsck --connectivity-only``. Disk-health monitoring (event
log counters, dirty bits) is deliberately **not** implemented here: it is a
Windows-only mechanism with a different owner, and a platform check that cannot
run must not masquerade as a pass.

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
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g12-integrity"
TITLE = "governance: the object store reads and HEAD resolves"


def head_commit(root: Path) -> tuple[str, str]:
    """The peeled HEAD commit, or the git error that prevented it."""
    completed = govlib.run_git_result(["rev-parse", "HEAD^{commit}"], root)
    if completed.returncode != 0:
        return "", completed.stderr.decode("utf-8", "replace").strip() or "rev-parse failed"
    return completed.stdout.decode("utf-8", "replace").strip(), ""


def unreadable_objects(root: Path, revision: str) -> list[str]:
    """Objects reachable from one commit that git cannot read back."""
    listed = govlib.run_git(["rev-list", "--objects", revision], root, check=False)
    shas = [line.split(" ", 1)[0] for line in listed.splitlines() if line.strip()]
    if not shas:
        return []
    completed = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        cwd=str(root),
        env=govlib.git_env(),
        input="\n".join(shas).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    # A failed cat-file prints nothing on stdout, and "no line says missing" would
    # then be read as "every object reads back" -- a green gate that judged nothing.
    if completed.returncode != 0:
        raise govlib.GateError(
            f"git cat-file --batch-check failed: {completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    missing: list[str] = []
    for line in completed.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "missing":
            missing.append(parts[0])
    return missing


def scan(root: Path, *, deep: bool) -> Report:
    """Judge HEAD resolution and object readability."""
    report = Report(title=TITLE)
    if not (root / ".git").exists():
        # A gate that judges git health must refuse a non-work-tree loudly rather
        # than skip: silence here is indistinguishable from "everything is fine".
        raise govlib.GateError(f"{root} is not a git work tree; nothing to verify")
    revision, error = head_commit(root)
    report.scanned += 1
    if not revision:
        report.block("head-unresolved", ".git/HEAD", 0, f"HEAD^{{commit}} does not resolve: {error}")
        return report
    missing = unreadable_objects(root, revision)
    report.scanned += len(missing)
    for sha in missing[:10]:
        report.block("object-missing", ".git/objects", 0, f"object {sha} is not readable")
    if len(missing) > 10:
        report.block("object-missing", ".git/objects", 0, f"and {len(missing) - 10} more unreadable objects")
    if not missing:
        report.exempt("every object reachable from HEAD reads back", 1)
    if deep:
        completed = govlib.run_git_result(["fsck", "--connectivity-only", "--no-progress"], root)
        if completed.returncode != 0:
            detail = completed.stdout.decode("utf-8", "replace").strip().splitlines()
            report.block("fsck-failed", ".git", 0, detail[0] if detail else "git fsck reported problems")
        else:
            report.exempt("git fsck --connectivity-only is clean", 1)
    else:
        report.skip("deep connectivity check disabled (--deep enables it)", 1)
    return report


def selfcheck() -> int:
    """Prove deleted objects and a corrupt HEAD are caught, clean trees are not."""
    check = govlib.SelfCheck(gate=GATE)
    identity = ["-c", "user.name=governance-selfcheck", "-c", "user.email=selfcheck@example.invalid"]

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        report = scan(sandbox.path, deep=True)
        check.quiet("a healthy work tree", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        objects = sandbox.path / ".git" / "objects"
        for directory in sorted(path for path in objects.iterdir() if path.is_dir()
                                and len(path.name) == 2):
            for item in directory.iterdir():
                item.chmod(0o666)
                item.unlink()
            directory.rmdir()
        report = scan(sandbox.path, deep=False)
        check.detects("objects deleted behind git's back",
                      any(finding.kind in ("object-missing", "head-unresolved") for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "feat: initial"], sandbox.path)
        (sandbox.path / ".git" / "HEAD").write_text("ref: refs/heads/does-not-exist\n", encoding="utf-8")
        report = scan(sandbox.path, deep=False)
        check.detects("a HEAD that cannot resolve",
                      any(finding.kind == "head-unresolved" for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--deep", action="store_true", help="also run git fsck --connectivity-only")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, deep=args.deep)
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
