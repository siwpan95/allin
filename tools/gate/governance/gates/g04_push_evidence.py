"""Gate g04 -- push readiness judged from the remote, never from a stale ref.

Three judgments, each closing a recorded accident class:

* **credential-free remotes** -- a remote URL carrying ``user:token@`` writes the
  token into every subsequent clone and into ``.git/config``.
* **authoritative sync state** -- ``origin/BR`` is a cache that goes stale as soon
  as anyone pushes with a URL or from another machine; the only trustworthy
  answer is ``git ls-remote``. The state is reported as one of ``IN_SYNC``,
  ``LOCAL_AHEAD``, ``REMOTE_AHEAD``, ``DIVERGED``, or ``NO_UPSTREAM``.
* **divergence blocks** -- a diverged branch means a plain push will be rejected,
  and the tempting next move is a force push. ``LOCAL_AHEAD`` and
  ``REMOTE_AHEAD`` are ordinary states for a distribution checkout and are
  reported, not blocked: local commits accumulate until someone is present to
  approve the push.

A network that cannot be reached is a SKIP with its cause printed -- never a
pass, and never a failure of the local checks.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g04-push-evidence"
TITLE = "governance: push readiness from authoritative remote evidence"

URL_CREDENTIAL = re.compile(r"\b[a-z][a-z0-9+.\-]*://[^/\s:@]+:[^/\s@]{6,}@")
REMOTE_URL_LINE = re.compile(r"^remote\.([^.]+)\.url$")


def remote_urls(root: Path) -> dict[str, str]:
    """Every configured remote and its URL, read through git itself."""
    text = govlib.run_git(["config", "--get-regexp", r"^remote\..*\.url$"], root, check=False)
    urls: dict[str, str] = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        match = REMOTE_URL_LINE.match(key.strip())
        if match is not None:
            urls[match.group(1)] = value.strip()
    return urls


def current_branch(root: Path) -> str:
    """The checked-out branch name, or an empty string on a detached HEAD."""
    name = govlib.run_git(["rev-parse", "--abbrev-ref", "HEAD"], root, check=False).strip()
    return "" if name in ("HEAD", "") else name


def classify_sync(root: Path, remote: str, branch: str) -> tuple[str, str, str]:
    """Return ``(state, local_sha, remote_sha)`` using `git ls-remote` as evidence."""
    local = govlib.run_git(["rev-parse", "HEAD"], root, check=False).strip()
    completed = govlib.run_git_result(["ls-remote", remote, f"refs/heads/{branch}"], root)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        return (f"SKIP ({detail[-1] if detail else 'ls-remote failed'})", local, "")
    probe = completed.stdout.decode("utf-8", "replace").strip()
    remote_sha = probe.split()[0] if probe else ""
    if not remote_sha:
        return ("NO_UPSTREAM", local, "")
    if remote_sha == local:
        return ("IN_SYNC", local, remote_sha)
    local_only = govlib.run_git_result(["merge-base", "--is-ancestor", remote_sha, "HEAD"], root).returncode == 0
    remote_only = govlib.run_git_result(["merge-base", "--is-ancestor", "HEAD", remote_sha], root).returncode == 0
    if local_only and not remote_only:
        return ("LOCAL_AHEAD", local, remote_sha)
    if remote_only and not local_only:
        return ("REMOTE_AHEAD", local, remote_sha)
    return ("DIVERGED", local, remote_sha)


def scan(root: Path, *, remote: str, branch: str, offline: bool) -> Report:
    """Judge remote URLs and the authoritative sync state."""
    report = Report(title=TITLE)
    urls = remote_urls(root)
    report.scanned = len(urls)
    for name, url in sorted(urls.items()):
        if URL_CREDENTIAL.search(url):
            report.block("credential-remote", ".git/config", 0, f"remote.{name}.url = {url}")
    if not urls:
        report.skip("no configured remote in this checkout", 1)
        return report
    if offline:
        report.skip("remote probe disabled by --offline", 1)
        return report

    chosen = remote if remote in urls else sorted(urls)[0]
    resolved_branch = branch or current_branch(root)
    if not resolved_branch:
        report.skip("detached HEAD: no branch to compare with the remote", 1)
        return report
    state, local, remote_sha = classify_sync(root, chosen, resolved_branch)
    if state.startswith("SKIP"):
        report.skip(f"remote probe unavailable: {state[5:].strip()}", 1)
        return report
    report.note(f"{chosen}/{resolved_branch}: {state} (local {local[:12] or '-'}, remote {remote_sha[:12] or '-'})")
    if state == "DIVERGED":
        report.block("diverged-branch", f".git/refs/heads/{resolved_branch}", 0,
                     f"{chosen}/{resolved_branch} diverged: rebase on the remote before pushing")
    return report


def selfcheck() -> int:
    """Prove every state is classified from the remote, using a real local remote."""
    check = govlib.SelfCheck(gate=GATE)
    identity = ["-c", "user.name=governance-selfcheck", "-c", "user.email=selfcheck@example.invalid"]
    with govlib.Sandbox() as sandbox:
        bare = sandbox.path / "origin.git"
        govlib.run_git(["init", "-q", "--bare", str(bare)], sandbox.path)
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "initial"], sandbox.path)
        govlib.run_git(["remote", "add", "origin", str(bare)], sandbox.path)
        govlib.run_git(["push", "-q", "origin", "HEAD:main"], sandbox.path)

        state, _local, _remote = classify_sync(sandbox.path, "origin", "main")
        check.detects("a pushed branch is recognised as in sync", state == "IN_SYNC")

        sandbox.write("src/app.ts", "export const app = 2\n")
        govlib.run_git([*identity, "commit", "-q", "-am", "local work"], sandbox.path)
        state, _local, _remote = classify_sync(sandbox.path, "origin", "main")
        check.detects("an unpushed commit reads as local ahead", state == "LOCAL_AHEAD")

        other = sandbox.path / "other"
        govlib.run_git(["clone", "-q", str(bare), str(other)], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "checkout", "-q", "-B", "main", "origin/main"], sandbox.path)
        (other / "remote.txt").write_text("remote work\n", encoding="utf-8")
        govlib.run_git([*identity, "-C", str(other), "add", "-A"], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "commit", "-q", "-m", "remote work"], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "push", "-q", "origin", "main"], sandbox.path)
        state, _local, _remote = classify_sync(sandbox.path, "origin", "main")
        check.detects("independent local and remote commits read as diverged", state == "DIVERGED")

        report = scan(sandbox.path, remote="origin", branch="main", offline=False)
        check.detects("divergence blocks", any(finding.kind == "diverged-branch" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        config = sandbox.path / ".git" / "config"
        config.write_text(config.read_text(encoding="utf-8")
                          + "[remote \"origin\"]\n\turl = https://svc:8f14e45fceea167a5a36dedd4bea2543@host.invalid/x.git\n",
                          encoding="utf-8")
        report = scan(sandbox.path, remote="origin", branch="main", offline=False)
        check.detects("a credential in the remote URL blocks",
                      any(finding.kind == "credential-remote" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        config = sandbox.path / ".git" / "config"
        config.write_text(config.read_text(encoding="utf-8")
                          + "[remote \"origin\"]\n\turl = https://gitee.com/owner/name.git\n", encoding="utf-8")
        report = scan(sandbox.path, remote="origin", branch="main", offline=True)
        check.quiet("an offline probe is a skip, not a finding", bool(report.findings))
        check.detects("the offline probe is reported as skipped", sum(report.skipped.values()) >= 1)
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--remote", default="origin", help="remote to compare against")
    parser.add_argument("--branch", default="", help="branch to compare (default: the checked-out branch)")
    parser.add_argument("--offline", action="store_true", help="skip the remote probe entirely")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, remote=args.remote, branch=args.branch, offline=args.offline)
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
