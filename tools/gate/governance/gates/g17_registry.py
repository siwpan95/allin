"""Gate g17 -- the project registry is complete, sane, and knows its own lifecycle.

The registry is the one place that answers "which projects exist and how do you
run them". It fails silently in a specific way: a repository gets cloned next to
this one, never gets an entry, and months later nobody can say what it is or how
to start it. ``3dworld-globe`` was found exactly that way -- present on the
release面, absent from the registry.

So this gate judges:

* **identity** -- every entry declares ``id``, and the id equals the file name,
  so a path and a name can never drift apart; ids are unique;
* **declared lifecycle** -- an optional ``status`` must come from the closed set
  ``active | dormant | archived | deprecated`` (a free-text status is a status
  nobody can filter on);
* **completeness** -- every git work tree beside this repository is either
  registered or **declared** in ``governance/registry-known-gaps.txt`` with a
  reason. Undeclared and unregistered is blocking: that is the leak this gate
  exists to stop. Non-git directories are counted as exempt, never assumed;
* **observed lifecycle** -- for entries with a local clone, days since the last
  commit classify the project as active / dormant / archived-candidate. This is
  evidence for a human decision, so it is reported, not blocked.

Portability: the sibling repositories live wherever ``ALLIN_REPOS_ROOT`` says,
defaulting to ``<this repo>/../repos`` (matching the registry's ``path:
repos/<name>`` convention). When that root is absent the completeness and
lifecycle checks report ``SKIPPED (not a pass)`` -- a gate that silently judged
nothing is the one failure mode this repository refuses.

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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, EXIT_ENV, Report  # noqa: E402

GATE = "g17-registry"
TITLE = "governance: the project registry is complete and knows its lifecycle"

REGISTRY_REL = "platform/registry/projects"
GAPS_REL = "tools/gate/governance/registry-known-gaps.txt"

ALLOWED_STATUS = ("active", "dormant", "archived", "deprecated")
DORMANT_DAYS = 90
ARCHIVE_DAYS = 365

SCALAR_ID = re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE)
SCALAR_STATUS = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)
SCALAR_PATH = re.compile(r"^path:\s*(\S+)\s*$", re.MULTILINE)


def entry_text(path: Path) -> str | None:
    """Read one entry.

    ``utf-8-sig`` is deliberate: a good number of these files carry a BOM, and a
    BOM in front of ``id:`` would otherwise read as "this entry declares no id".
    """
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def load_gaps(path: Path) -> dict[str, str]:
    """Declared, reasoned gaps: directory name -> reason."""
    gaps: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return gaps
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _sep, reason = line.partition("|")
        gaps[name.strip()] = reason.strip() or "（未写明理由）"
    return gaps


def repos_root(root: Path) -> Path:
    override = os.environ.get("ALLIN_REPOS_ROOT")
    if override:
        return Path(override)
    return root.parent / "repos"


def local_dirs(repos: Path) -> tuple[list[str], list[str]]:
    """(git work trees, non-git directories) directly under the repos root."""
    git_dirs: list[str] = []
    plain_dirs: list[str] = []
    if not repos.is_dir():
        return git_dirs, plain_dirs
    for child in sorted(repos.iterdir()):
        if not child.is_dir():
            continue
        (git_dirs if (child / ".git").exists() else plain_dirs).append(child.name)
    return git_dirs, plain_dirs


def last_commit_days(repo: Path) -> int | None:
    """Days since the last commit, or None when it cannot be determined.

    The date comes from git itself rather than from ``.git`` plumbing: a ref file
    holds a commit id, not a timestamp, and anything derived from file mtimes is
    a lie waiting to happen after a fresh clone.
    """
    try:
        raw = govlib.run_git(["log", "-1", "--format=%ct"], repo, check=False).strip()
    except govlib.GateError:
        return None
    if not raw:
        return None
    try:
        stamp = int(raw.splitlines()[0])
    except (ValueError, IndexError):
        return None
    return int((time.time() - stamp) // 86400)


def run(root: str, args: argparse.Namespace) -> Report:
    report = Report(title=TITLE)
    base = Path(root)
    registry = base / REGISTRY_REL
    if not registry.is_dir():
        report.block("registry-missing", REGISTRY_REL, 0, "the project registry directory is gone")
        return report

    by_id: dict[str, Path] = {}
    for path in sorted(registry.glob("*.yaml")):
        text = entry_text(path)
        if text is None:
            report.block("entry-unreadable", str(path.relative_to(base)).replace("\\", "/"), 0,
                         "entry is not readable UTF-8 text")
            continue
        report.scanned += 1
        match = SCALAR_ID.search(text)
        if not match:
            report.block("entry-no-id", str(path.relative_to(base)).replace("\\", "/"), 0,
                         "entry declares no id")
            continue
        identifier = match.group(1)
        stem = path.stem
        if identifier != stem:
            report.block("id-name-drift", str(path.relative_to(base)).replace("\\", "/"), 0,
                         f"id '{identifier}' does not match the file name '{stem}'")
        else:
            report.exempt("id-name-agree")
        if identifier in by_id:
            report.block("duplicate-id", str(path.relative_to(base)).replace("\\", "/"), 0,
                         f"id '{identifier}' is already declared by {by_id[identifier].name}")
        else:
            by_id[identifier] = path
            report.exempt("id-unique")
        status = SCALAR_STATUS.search(text)
        if status:
            if status.group(1) in ALLOWED_STATUS:
                report.exempt("status-known")
            else:
                report.block("status-unknown", str(path.relative_to(base)).replace("\\", "/"), 0,
                             f"status '{status.group(1)}' is outside {', '.join(ALLOWED_STATUS)}")

    # ---- completeness: every local work tree is registered or declared ----
    repos = repos_root(base)
    gaps = load_gaps(base / GAPS_REL)
    # 一个本地目录算「已登记」，当它等于某条目的 id，或等于该条目 path 的基名
    # （registry 里 id 与目录名不同的情况是设计如此，例如 id=moba-battle /
    # path=repos/moba_battle_platform），两者都要接受，否则会把正常条目判红。
    known_dirs: set[str] = set(by_id)
    for path in by_id.values():
        declared = SCALAR_PATH.search(entry_text(path) or "")
        if declared:
            known_dirs.add(Path(declared.group(1)).name)
    git_dirs, plain_dirs = local_dirs(repos)
    if not repos.is_dir():
        report.skip(f"completeness (repos root absent: {repos.name}/; set ALLIN_REPOS_ROOT)")
        report.skip("lifecycle (no local clones to date)")
        return report
    for name in plain_dirs:
        report.exempt("not-a-git-worktree")
    for name in git_dirs:
        if name in known_dirs:
            report.exempt("registered")
        elif name in gaps:
            report.exempt(f"declared-gap ({name}: {gaps[name][:60]})")
        else:
            report.block("unregistered-repo", f"{repos.name}/{name}", 0,
                         f"a git work tree with no registry entry and no declared gap "
                         f"(add an entry, or declare it in {GAPS_REL} with a reason)")

    # ---- observed lifecycle (evidence, never a block) ----
    buckets = {"active": 0, "dormant": 0, "archived-candidate": 0}
    dated = 0
    for identifier, path in sorted(by_id.items()):
        text = entry_text(path) or ""
        declared = SCALAR_PATH.search(text)
        if not declared:
            report.skip("lifecycle (entry declares no path)")
            continue
        target = repos / Path(declared.group(1)).name
        if not (target / ".git").exists():
            report.skip("lifecycle (no local clone)")
            continue
        days = last_commit_days(target)
        if days is None:
            report.skip("lifecycle (last commit unreadable)")
            continue
        dated += 1
        if days <= DORMANT_DAYS:
            buckets["active"] += 1
        elif days <= ARCHIVE_DAYS:
            buckets["dormant"] += 1
        else:
            buckets["archived-candidate"] += 1
    if dated:
        report.note(f"lifecycle over {dated} local clone(s): active {buckets['active']}, "
                    f"dormant {buckets['dormant']} (> {DORMANT_DAYS}d), "
                    f"archived-candidate {buckets['archived-candidate']} (> {ARCHIVE_DAYS}d)")
    return report


# --------------------------------------------------------------------------- #
# self-check
# --------------------------------------------------------------------------- #

FIXTURE_ENTRY = "\n".join([
    "id: {name}",
    "name: fixture",
    "category: tool",
    "path: repos/{name}",
])

SELFCHECK_CASES = [
    ("clean", True),
    ("unregistered", False),
    ("id-name-drift", False),
    ("duplicate-id", False),
    ("bad-status", False),
    ("no-id", False),
]


def build_fixture(kind: str, base: str) -> str:
    registry = Path(base) / REGISTRY_REL
    registry.mkdir(parents=True, exist_ok=True)
    repos = Path(base) / "repos"
    repos.mkdir(parents=True, exist_ok=True)
    gaps = Path(base) / GAPS_REL
    gaps.parent.mkdir(parents=True, exist_ok=True)
    gaps.write_text("# declared gaps\n", encoding="utf-8", newline="\n")

    entries = {"alpha": FIXTURE_ENTRY.format(name="alpha")}
    dirs = ["alpha"]
    if kind == "unregistered":
        dirs.append("ghost")
    if kind == "id-name-drift":
        entries["beta"] = FIXTURE_ENTRY.format(name="alpha")
    if kind == "duplicate-id":
        entries["gamma"] = FIXTURE_ENTRY.format(name="alpha")
    if kind == "bad-status":
        entries["alpha"] = entries["alpha"] + "\nstatus: maybe\n"
    if kind == "no-id":
        entries["alpha"] = "name: nameless\ncategory: tool\n"

    for name, body in entries.items():
        (registry / f"{name}.yaml").write_text(body + "\n", encoding="utf-8", newline="\n")
    for name in dirs:
        (repos / name).mkdir(parents=True, exist_ok=True)
        (repos / name / ".git").mkdir(parents=True, exist_ok=True)
        (repos / name / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8", newline="\n")
        (repos / name / ".git" / "refs").mkdir(parents=True, exist_ok=True)
        (repos / name / ".git" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
        (repos / name / ".git" / "refs" / "heads" / "master").write_text(
            f"{int(time.time())} 0000000\n", encoding="utf-8", newline="\n")
    return base


def selfcheck() -> int:
    check = govlib.SelfCheck(gate=GATE)
    for kind, expect_clean in SELFCHECK_CASES:
        tmp = tempfile.mkdtemp(prefix="g17-registry-")
        try:
            build_fixture(kind, tmp)
            # 夹具的 repos 就在 tmp 下，用环境变量指过去（默认口径是 <仓根>/../repos）
            previous = os.environ.get("ALLIN_REPOS_ROOT")
            os.environ["ALLIN_REPOS_ROOT"] = str(Path(tmp) / "repos")
            try:
                report = run(tmp, argparse.Namespace())
            finally:
                if previous is None:
                    os.environ.pop("ALLIN_REPOS_ROOT", None)
                else:
                    os.environ["ALLIN_REPOS_ROOT"] = previous
            flagged = bool(report.findings)
            if expect_clean:
                if flagged:
                    print(f"  detail: {[f'{f.kind}:{f.text}' for f in report.findings][:3]}")
                    check.quiet(kind, True)
                else:
                    check.quiet(kind, False)
            else:
                check.detects(kind, flagged)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return check.finish()


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
        govlib.GOVERNANCE_DIR / "baseline" / "g17-registry.txt")
    baseline = govlib.Baseline(baseline_path).load()
    if args.write_baseline:
        baseline.write(report.findings)
        print(f"wrote baseline {baseline_path} ({len(report.findings)} key(s))")
        return EXIT_OK
    new = list(report.findings) if args.no_baseline else baseline.filter_new(report.findings)
    shown = Report(title=report.title, findings=report.findings if args.list_all else new,
                   exempted=report.exempted, skipped=report.skipped, notes=report.notes,
                   scanned=report.scanned)
    print(shown.render().splitlines()[0] if args.quiet else shown.render())
    return EXIT_BLOCKING if new else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
