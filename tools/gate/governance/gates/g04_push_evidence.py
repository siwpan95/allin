"""Gate g04 -- push readiness judged from the remote, never from a stale ref.

Three judgments, each closing a recorded accident class:

* **credential-free remotes** -- a remote URL carrying ``user:token@`` writes the
  token into every subsequent clone and into ``.git/config``.
* **authoritative sync state** -- ``origin/BR`` is a cache that goes stale as soon
  as anyone pushes with a URL or from another machine; the only trustworthy
  answer is ``git ls-remote``. The state is reported as one of ``IN_SYNC``,
  ``LOCAL_AHEAD``, ``REMOTE_AHEAD``, ``DIVERGED``, ``NO_UPSTREAM``, or
  ``UNVERIFIED``.
* **an unknown remote tip is fetched before it is judged** -- ``merge-base
  --is-ancestor`` answers "not an ancestor" and "never heard of that object"
  with the same non-zero exit, so a remote commit this clone never fetched used
  to read as a divergence the gate could not actually see (2026-10-29: a
  checkout three commits behind reported ``DIVERGED``). The gate now fetches
  that one branch as a remote-tracking ref -- no local branch, index, or
  work-tree file is touched -- and judges again; when the fetch fails the state
  is ``UNVERIFIED`` and the gate skips with its cause instead of inventing a
  verdict.
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
REMOTE_TARGET_LINE = re.compile(r"^remote\.([^.]+)\.(url|pushurl)$")


def remote_targets(root: Path) -> dict[str, list[tuple[str, str]]]:
    """Every configured remote **and its push targets**: {name: [(role, url), ...]}.

    为什么要读 ``pushurl``：双核推送把镜像写成了 ``origin`` 的**第二个 pushurl**
    （Gitee + GitHub），只读 ``remote.*.url`` 只会看到 Gitee 一侧 ⇒ 镜像那一路**不被覆盖**。
    role ∈ {``url``, ``pushurl``}。
    """
    text = govlib.run_git(["config", "--get-regexp", r"^remote\..*\.(url|pushurl)$"], root, check=False)
    targets: dict[str, list[tuple[str, str]]] = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        match = REMOTE_TARGET_LINE.match(key.strip())
        if match is not None:
            targets.setdefault(match.group(1), []).append((match.group(2), value.strip()))
    return targets


def push_target_list(targets: dict[str, list[tuple[str, str]]], preferred: str) -> list[tuple[str, str]]:
    """该 remote 的**实际推送目标**：有 pushurl 就用它（可多条），否则退回 url。

    返回 [(标签, url)]，按 URL 去重（同一 URL 既作 pushurl 又是独立 remote 时只核一次）。
    标签必须能进 ref 路径（``refs/remotes/<标签>/<分支>``）⇒ 用序号形态，不用 URL 原文。
    """
    entries = targets.get(preferred)
    if not entries:
        if not targets:
            return []
        name = sorted(targets)[0]
        entries = targets[name]
        preferred = name
    pushes = [url for role, url in entries if role == "pushurl"]
    if not pushes:
        pushes = [url for role, url in entries if role == "url"]
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url in pushes:
        if url in seen:
            continue
        seen.add(url)
        out.append(("%s-push%d" % (preferred, len(out) + 1), url))
    return out


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


def object_present(root: Path, sha: str) -> bool:
    """True when this clone already holds that commit.

    ``merge-base --is-ancestor`` needs both commits in the object store; without
    this probe a missing object is indistinguishable from an unrelated history.
    """
    return govlib.run_git_result(["cat-file", "-e", f"{sha}^{{commit}}"], root).returncode == 0


def fetch_branch_ref(root: Path, remote: str, branch: str, sha: str, ref_label: str | None = None) -> bool:
    """Fetch one branch into ``refs/remotes/<label>/<branch>`` and confirm it landed.

    Only the remote-tracking ref moves: no local branch, no index entry, no
    work-tree file. Prompting is already disabled by ``govlib.git_env``, so an
    unreachable or credential-less remote fails fast instead of hanging.

    ``ref_label`` lets the **fetch source** be a URL (a second pushurl) while the
    tracking ref keeps a legal ref path (a URL cannot go into a ref name).
    """
    label = ref_label or remote
    completed = govlib.run_git_result(
        ["fetch", "--no-tags", "--quiet", remote, f"+refs/heads/{branch}:refs/remotes/{label}/{branch}"],
        root,
    )
    return completed.returncode == 0 and object_present(root, sha)


def classify_sync(root: Path, remote: str, branch: str, label: str | None = None) -> tuple[str, str, str]:
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
    if not object_present(root, remote_sha) and not fetch_branch_ref(root, remote, branch, remote_sha, label):
        # Still no object: ancestry cannot be proven either way, so never call it
        # a divergence the gate cannot see. The caller reports this as a SKIP.
        return ("UNVERIFIED", local, remote_sha)
    local_only = govlib.run_git_result(["merge-base", "--is-ancestor", remote_sha, "HEAD"], root).returncode == 0
    remote_only = govlib.run_git_result(["merge-base", "--is-ancestor", "HEAD", remote_sha], root).returncode == 0
    if local_only and not remote_only:
        return ("LOCAL_AHEAD", local, remote_sha)
    if remote_only and not local_only:
        return ("REMOTE_AHEAD", local, remote_sha)
    return ("DIVERGED", local, remote_sha)


def scan(root: Path, *, remote: str, branch: str, offline: bool) -> Report:
    """Judge remote URLs and the authoritative sync state of **every push target**.

    双核推送把镜像写成 ``origin`` 的第二个 ``pushurl``（Gitee + GitHub）⇒ 只核 ``remote.*.url``
    会让镜像那一路**不被覆盖**（2026-11-01 实测：g04 原本只读 ``url``，GitHub 侧完全没被核）。
    故：① 凭据检查覆盖 ``url`` **与** ``pushurl``（堵住"PAT 藏进 pushurl"绕过凭据红线）；
    ② 同步状态逐个核该 remote 的**所有推送目标**。
    """
    report = Report(title=TITLE)
    targets = remote_targets(root)
    report.scanned = len(targets)
    for name, entries in sorted(targets.items()):
        for role, url in entries:
            if URL_CREDENTIAL.search(url):
                report.block("credential-remote", ".git/config", 0, f"remote.{name}.{role} = {url}")
    if not targets:
        report.skip("no configured remote in this checkout", 1)
        return report
    if offline:
        report.skip("remote probe disabled by --offline", 1)
        return report

    chosen = remote if remote in targets else sorted(targets)[0]
    resolved_branch = branch or current_branch(root)
    if not resolved_branch:
        report.skip("detached HEAD: no branch to compare with the remote", 1)
        return report
    push_targets = push_target_list(targets, chosen)
    if not push_targets:
        report.skip("no push target configured", 1)
        return report
    for label, url in push_targets:
        state, local, remote_sha = classify_sync(root, url, resolved_branch, label=label)
        if state.startswith("SKIP"):
            report.skip(f"remote probe unavailable for {label}: {state[5:].strip()}", 1)
            continue
        report.note(f"{label}/{resolved_branch}: {state} (local {local[:12] or '-'}, remote {remote_sha[:12] or '-'})")
        if state == "UNVERIFIED":
            report.skip(f"{label}: remote commit {remote_sha[:12]} is absent from this clone and could not be "
                        "fetched: push readiness cannot be proven", 1)
            continue
        if state == "DIVERGED":
            report.block("diverged-branch", f".git/refs/heads/{resolved_branch}", 0,
                         f"{label}/{resolved_branch} diverged: rebase on the remote before pushing")
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

    # 2026-10-29 事故的回归夹具：落后但从未 fetch 的检出，远端提交对象不在本地。
    # 修复前 `merge-base --is-ancestor` 两端都返回非零 ⇒ 误判 DIVERGED（本机实际
    # 落后 3 笔却被报成「分叉」，提示去 rebase）。真值应是 REMOTE_AHEAD。
    with govlib.Sandbox() as sandbox:
        bare = sandbox.path / "origin.git"
        govlib.run_git(["init", "-q", "--bare", str(bare)], sandbox.path)
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "initial"], sandbox.path)
        govlib.run_git(["remote", "add", "origin", str(bare)], sandbox.path)
        govlib.run_git(["push", "-q", "origin", "HEAD:main"], sandbox.path)

        follower = sandbox.path / "follower"
        govlib.run_git(["clone", "-q", str(bare), str(follower)], sandbox.path)
        govlib.run_git([*identity, "checkout", "-q", "-B", "main", "origin/main"], follower)
        sandbox.write("src/app.ts", "export const app = 2\n")
        govlib.run_git([*identity, "commit", "-q", "-am", "remote work"], sandbox.path)
        govlib.run_git([*identity, "push", "-q", "origin", "HEAD:main"], sandbox.path)
        moved_sha = govlib.run_git(["rev-parse", "HEAD"], sandbox.path).strip()
        check.detects("the stale clone really lacks the remote commit",
                      not object_present(follower, moved_sha))
        state, _local, _remote = classify_sync(follower, "origin", "main")
        check.detects("an unfetched remote commit reads as remote ahead, never as divergence",
                      state == "REMOTE_AHEAD")
        report = scan(follower, remote="origin", branch="main", offline=False)
        check.quiet("an unfetched remote commit does not block the push check",
                    any(finding.kind == "diverged-branch" for finding in report.findings))

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
    # 2026-11-01：双核推送（origin 配两个 pushurl）—— 镜像那一路也必须被核。
    # 修前 g04 只读 remote.*.url ⇒ GitHub 侧完全没被覆盖（实测：双核仓上 g04 只报 Gitee 一侧）。
    with govlib.Sandbox() as sandbox:
        gitee = sandbox.path / "gitee.git"
        mirror = sandbox.path / "github.git"
        for bare in (gitee, mirror):
            govlib.run_git(["init", "-q", "--bare", str(bare)], sandbox.path)
        sandbox.write("src/app.ts", "export const app = 1\n")
        govlib.run_git([*identity, "commit", "-q", "-m", "initial"], sandbox.path)
        govlib.run_git(["remote", "add", "origin", str(gitee)], sandbox.path)
        # ⚠ git 语义：remote 一旦配了**显式 pushurl**，`url` 就不再是推送目标 ⇒
        # 双核必须是**两条 pushurl**（Gitee + GitHub），与 @SIWPAN / @DESKTOP-8RSV60V 同款。
        govlib.run_git(["remote", "set-url", "--add", "--push", "origin", str(gitee)], sandbox.path)
        govlib.run_git(["remote", "set-url", "--add", "--push", "origin", str(mirror)], sandbox.path)
        govlib.run_git(["push", "-q", "origin", "HEAD:main"], sandbox.path)

        report = scan(sandbox.path, remote="origin", branch="main", offline=False)
        check.detects("every push target is probed, not only the fetch url",
                      len([n for n in report.notes if ": IN_SYNC" in n]) >= 2)

        # 镜像落后（只推了 Gitee 那一路）⇒ 报 LOCAL_AHEAD，但**不阻断**（待推的常态）
        sandbox.write("src/app.ts", "export const app = 2\n")
        govlib.run_git([*identity, "commit", "-q", "-am", "local work"], sandbox.path)
        report = scan(sandbox.path, remote="origin", branch="main", offline=False)
        check.detects("the lagging mirror target is named in the notes",
                      any("LOCAL_AHEAD" in n for n in report.notes))
        check.quiet("a lagging mirror target is reported, not blocked",
                    any(f.kind == "diverged-branch" for f in report.findings))

        # 镜像那一路分叉 ⇒ 阻断（推过去会被拒）
        other = sandbox.path / "other"
        govlib.run_git(["clone", "-q", str(mirror), str(other)], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "checkout", "-q", "-B", "main", "origin/main"], sandbox.path)
        (other / "remote.txt").write_text("remote work\n", encoding="utf-8")
        govlib.run_git([*identity, "-C", str(other), "add", "-A"], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "commit", "-q", "-m", "remote work"], sandbox.path)
        govlib.run_git([*identity, "-C", str(other), "push", "-q", "origin", "main"], sandbox.path)
        report = scan(sandbox.path, remote="origin", branch="main", offline=False)
        check.detects("a diverged mirror target blocks the push check",
                      any(f.kind == "diverged-branch" for f in report.findings))

    # 2026-11-01：凭据红线不能只查 fetch url —— PAT 藏进 pushurl 是同一条红线
    with govlib.Sandbox() as sandbox:
        sandbox.write("src/app.ts", "export const app = 1\n")
        config = sandbox.path / ".git" / "config"
        config.write_text(config.read_text(encoding="utf-8")
                          + "[remote \"origin\"]\n\turl = https://gitee.com/owner/name.git\n"
                          + "[remote \"mirror\"]\n\tpushurl = https://svc:8f14e45fceea167a5a36dedd4bea2543@host.invalid/x.git\n",
                          encoding="utf-8")
        report = scan(sandbox.path, remote="origin", branch="main", offline=True)
        check.detects("a credential hidden in a pushurl is blocked",
                      any(f.kind == "credential-remote" for f in report.findings))

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
