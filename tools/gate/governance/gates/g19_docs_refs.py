"""Gate g19 -- documentation is a test suite: every claim it makes must resolve.

Docs rot in one specific direction. A command stops working because a script
moves one directory down; a path keeps being quoted long after the file was
renamed; an ``npm run <x>`` survives the script it named. Nobody notices,
because prose is not executed -- the reader discovers the lie at the worst
possible moment, in the middle of an incident.

Docs-as-tests is the cheap fix: a document is a set of assertions about the
repository, so run the assertions. This gate checks the three claims a doc
can make that this repository can actually verify:

* ``command-target`` -- a command inside a fenced block (``python x.py``,
  ``node x.js``, ``bash x.sh``) must point at a file that exists;
* ``npm-script`` -- ``npm run <name>`` must name a script that exists in the
  ``package.json`` chain (the doc's own package, up to the root one);
* ``path-ref`` -- a repository-relative path (``tools/...``, ``docs/...``) must
  point at something that exists.

Two carve-outs keep this honest instead of noisy, and both are counted so they
stay visible:

* **Frozen and foreign trees are out of scope.** ``docs/md/`` is the frozen
  history tree (the same carve-out ``docs_index`` already makes), ``vendor/``
  is somebody else's source, and ``.workbuddy/skills/`` describes *other*
  repositories' scripts. A gate that judges text it cannot resolve produces
  noise, and noise gets the gate switched off.
* **Records are snapshots, not promises.** ``docs/记录/`` is exempt from
  ``path-ref`` on purpose: a dated audit that says ``tools/pp_cli.py`` is
  describing a sibling repository *as it was that day*. 规范 and 事实源 are the
  opposite -- they claim what is true *now*, so they are judged in full.

Resolution is deliberately generous before it is strict. A doc may write a
command relative to the repository root, relative to its own directory, or with
a leading ``/`` meaning "from the root" -- all three are accepted. What is never
accepted is a target that exists nowhere.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_ENV, EXIT_OK, Report  # noqa: E402

GATE = "g19-docs-refs"
TITLE = "governance: documentation claims resolve to something that exists"

# Trees this gate cannot judge: frozen history, foreign source, and skill packs
# that document other repositories.
OUT_OF_SCOPE = (".workbuddy/", "vendor/", "docs/md/", "docs/历史/")
# ASCII alias directories are junctions onto the Chinese category dirs; judging
# them would judge the same content twice.
ALIAS_DIRS = {"spec", "facts", "records", "历史"}
# Records are dated snapshots; they are exempt from path-ref, not from commands.
SNAPSHOT_SCOPES = ("docs/记录/", "audit-fragments/")
# Runtime evidence is produced by the gates, never committed; a doc pointing at
# it is describing output, not promising a file exists.
RUNTIME_OUTPUT = ("tools/gate/audit/",)

FENCE = re.compile(r"^```([A-Za-z0-9]*)\s*$")
SHELLISH = ("bash", "sh", "shell", "console", "python", "bat", "ps1", "powershell")
# 扩展名按「长在前」排列 + 词尾边界：否则 `mcp-actions.jsonl` 会被 `js` 分支截成
# `mcp-actions.js`、`hooks.json` 被截成 `hooks.js` —— 门禁自己制造假红。
COMMAND = re.compile(
    r"^\s*(?:\$|>)?\s*(python3?|node|bash|sh)\s+([A-Za-z0-9_./\-]+?\.(?:mjs|jsonl|py|ts|js|sh))(?![A-Za-z0-9_.\-])")
NPM_RUN = re.compile(r"^\s*(?:\$|>)?\s*npm run ([A-Za-z0-9_:.\-]+)\b")
PATH_REF = re.compile(
    r"(?<![A-Za-z0-9_./\-])"
    r"((?:docs|tools|scripts|platform|kernel|preset|architecture)"
    r"/[A-Za-z0-9_./\-]+?\.(?:jsonl|yaml|yml|mjs|json|md|py|sh|ts|js|ps1|txt))(?![A-Za-z0-9_.\-])")
TOP_LEVEL = ("docs", "tools", "scripts", "platform", "kernel", "preset", "architecture")


def read_text(path: Path) -> str | None:
    """One file as UTF-8 text, or None when it is missing. Encoding is explicit."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def corpus(root: Path, files: list[str]) -> tuple[list[str], list[str]]:
    """(judged markdown, exempt markdown-with-reason) as repository-relative paths."""
    judged: list[str] = []
    exempt: list[str] = []
    for rel in files:
        if not rel.endswith(".md"):
            continue
        if rel.startswith(OUT_OF_SCOPE):
            continue
        parts = rel.split("/")
        if len(parts) > 2 and parts[0] == "docs" and parts[1] in ALIAS_DIRS:
            continue
        (exempt if rel.startswith(SNAPSHOT_SCOPES) else judged).append(rel)
    return judged, exempt


def resolves(root: Path, doc: str, spec: str) -> bool:
    """True when ``spec`` names a file under any of the conventions a doc may use."""
    doc_dir = (root / doc).parent
    bases = [root, doc_dir, doc_dir.parent]
    for base in bases:
        for candidate in (base / spec, base / spec.lstrip("/")):
            if candidate.is_file():
                return True
    return False


def scripts_chain(root: Path, doc: str) -> set[str]:
    """Every npm script name from the doc's own package.json up to the root one."""
    names: set[str] = set()
    directory = (root / doc).parent
    for _ in range(8):
        package = directory / "package.json"
        text = read_text(package) if package.is_file() else None
        if text:
            try:
                names.update(json.loads(text).get("scripts", {}))
            except ValueError:
                pass  # an unparsable package.json contributes nothing, and is not our claim to judge
        if directory == root:
            break
        directory = directory.parent
    return names


def scan_doc(root: Path, rel: str, report: Report, judge_paths: bool) -> None:
    text = read_text(root / rel)
    if text is None:
        report.skip(f"unreadable ({rel})")
        return
    in_fence = False
    language = ""
    for number, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line)
        if fence:
            in_fence, language = (True, fence.group(1).lower()) if not in_fence else (False, "")
            continue
        if in_fence and language in SHELLISH:
            command = COMMAND.search(line)
            if command and not resolves(root, rel, command.group(2)):
                report.block("command-target", rel, number,
                             f"`{command.group(0).strip()}` -> no such file ({command.group(2)})")
            npm = NPM_RUN.search(line)
            if npm and npm.group(1) not in scripts_chain(root, rel):
                report.block("npm-script", rel, number,
                             f"`npm run {npm.group(1)}` -> no such script in the package.json chain")
        if judge_paths:
            for match in PATH_REF.finditer(line):
                target = match.group(1)
                if target.startswith(RUNTIME_OUTPUT):
                    continue
                if not resolves(root, rel, target):
                    report.block("path-ref", rel, number, f"path does not exist: {target}")


def run(root: str, args: argparse.Namespace) -> Report:
    base = Path(root)
    report = Report(title=TITLE)
    files = govlib.tracked_files(base)
    judged, snapshots = corpus(base, files)
    report.scanned = len(judged)
    for rel in judged:
        scan_doc(base, rel, report, judge_paths=True)
    # A record may still promise a command; only its path references are a snapshot.
    for rel in snapshots:
        scan_doc(base, rel, report, judge_paths=False)
        report.exempt("record-snapshot (path-ref not judged)", 1)
    for scope in OUT_OF_SCOPE:
        count = sum(1 for rel in files
                    if rel.endswith(".md") and rel.startswith(scope))
        if count:
            report.exempt(f"out-of-scope tree ({scope})", count)
    return report


# --------------------------------------------------------------------------- #
# self-check
# --------------------------------------------------------------------------- #

FIXTURE_DOC = """# SPEC-900 fixture

```bash
python tools/{script}.py --root .
npm run {script_name}
```

See `docs/{doc}` for the detail.
"""

SELFCHECK_CASES = [
    ("clean", True),
    ("command-missing", False),
    ("npm-missing", False),
    ("path-missing", False),
]


def build_fixture(kind: str, sandbox: govlib.Sandbox) -> None:
    script = "real" if kind != "command-missing" else "ghost"
    script_name = "check" if kind != "npm-missing" else "nosuchscript"
    doc = "INDEX.md" if kind != "path-missing" else "GHOST.md"
    sandbox.write("package.json", json.dumps({"scripts": {"check": "echo hi"}}))
    sandbox.write("docs/规范/SPEC-900-fixture.md",
                  FIXTURE_DOC.format(script=script, script_name=script_name, doc=doc))
    sandbox.write("docs/INDEX.md", "# index\n")
    if kind != "command-missing":
        sandbox.write("tools/real.py", "print('hi')\n")


def selfcheck() -> int:
    check = govlib.SelfCheck(gate=GATE)
    for kind, expect_clean in SELFCHECK_CASES:
        with govlib.Sandbox() as sandbox:
            build_fixture(kind, sandbox)
            report = run(str(sandbox.path), argparse.Namespace())
            flagged = bool(report.findings)
            if expect_clean:
                if flagged:
                    print(f"  detail: {[f'{f.kind}:{f.text}' for f in report.findings][:3]}")
                check.quiet(kind, flagged)
            else:
                check.detects(kind, flagged)
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
        govlib.GOVERNANCE_DIR / "baseline" / "g19-docs-refs.txt")
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
