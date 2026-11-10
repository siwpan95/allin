"""Gate g01 -- machine-specific absolute paths in maintained files.

Iron rule 5 (no hard-coded machine paths) generalised past its Windows origin:
a path is **dead** when the directory that would contain it does not exist, and
the judgment is made against the platform the path belongs to, so the gate still
does something on Linux and macOS instead of passing vacuously.

Triage is deliberate:

* only an **effective code line** in a maintained source file can block;
* comments, documentation, fixtures, generated files and annotated sample lines
  are reported as exemptions **with counts**, never dropped silently;
* a path written for the other platform (a drive path on POSIX, a ``/Users``
  path on Windows) is reported, not blocked, because this repository ships for
  all three platforms;
* escaping artefacts such as ``"diagnostics:\\n"`` are exempted by a negative
  look-behind on the drive letter plus an escape-tail test, the same class of
  defect that once made a similar gate swallow a whole category of findings.

Exit codes follow the governance vocabulary: 0 clean, 1 new blocking finding
outside the baseline, 2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g01-paths"
TITLE = "governance: machine-specific absolute paths"

#: Trees whose contents are frozen history, vendored, generated, or third party.
SKIP_PREFIXES = (
    ".agents/notes/archived/",
    ".artifacts/",
    "apps/web/dist/",
    "audit-fragments/",  # 2026-11-10：整改/审计证据日志（含历史命令输出里的绝对路径），非维护中源码，与 tools/tier_archive 同性质
    "docs/记录/快照/",  # 2026-11-10：发布区/机器快照是历史数据卷（只增不改），内含当时机器路径非维护中源码
    "coverage/",
    "dist/",
    "lib/",
    "node_modules/",
    "tmp/",
    "tools/tier_archive/",  # 2026-10-29 落实分级索引时跑过脚本的历史追溯存档，不可执行、仅供复核
    "vendor/",
)

#: Path segments that mark a test fixture rather than product behaviour.
FIXTURE_SEGMENTS = (
    "/__fixtures__/",
    "/__mocks__/",
    "/__snapshots__/",
    "/fixtures/",
    "/snapshots/",
    "/testdata/",
    "/tests/",
)

#: Test-file names, matched as a whole name so a directory called "latest" is untouched.
#: Both pytest conventions count: ``test_module.py`` and ``module_test.py``.
TEST_FILE_NAMES = re.compile(r"(\.(spec|test)\.(ts|tsx|mts|cts|js|mjs|cjs)$)|(^test_[^/]*\.py$)"
                             r"|(_test\.(py|cpp|cc|c|h)$)")

#: Binary and asset extensions: never scanned, and counted as such.
SKIP_EXTENSIONS = frozenset(
    ".7z .avif .bin .bmp .bz2 .db .dll .dylib .eot .exe .gif .gz .ico .jar .jpeg .jpg .lock .node "
    ".otf .pdf .png .so .sqlite .tar .tgz .ttf .wasm .webp .woff .woff2 .xz .zip".split()
)

#: Documentation extensions: reported, never blocking, unless --include-docs.
#: ``.html`` is documentation too: the old-machine fact sheet is prose with machine
#: paths in it, and judging it as code turned its dead paths into blockers.
DOC_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc", ".html", ".htm"})

#: Example / template files are shipped as samples, never as effective code.
#: A file like ``源.txt.example`` has ``.example`` as its *last* suffix, so it never
#: reaches DOC_EXTENSIONS. Without this rule a sample path inside it blocks on POSIX
#: (parent directory absent) while the very same line is exempted on Windows as
#: "path written for the other platform" -- a platform-dependent false positive that
#: kept the Linux CI job red. 2026-11-04 修复：示例文件按 report-only 处理。
EXAMPLE_SUFFIXES = (".example", ".sample", ".template")

#: Comment leaders per extension family, used only to classify a line, never to hide a file.
LINE_COMMENT_LEADERS = ("//", "#", "*", "/*", "<!--", "--", ";", '"""', "'''")

WIN_PATH = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z]):[\\/]{1,2}([^\s"\'`<>|*?()\[\]{},;]*)')
POSIX_PATH = re.compile(r'(?<![A-Za-z0-9_./-])/(Users|home|Volumes|mnt|media)/[A-Za-z0-9._-]+'
                        r'([^\s"\'`<>|*?()\[\]{},;]*)')

#: Directory prefixes that are legitimately system-owned on each platform.
SYSTEM_PREFIXES_POSIX = ("/Applications", "/Library", "/System", "/bin", "/dev", "/etc", "/lib", "/nix",
                         "/opt", "/proc", "/run", "/sbin", "/snap", "/sys", "/tmp", "/usr", "/var")  # nosec B108  # LES-005 型："/tmp" 是系统前缀分类常量，非临时目录操作
SYSTEM_PREFIXES_NT = ("c:\\program files", "c:\\program files (x86)", "c:\\programdata", "c:\\users\\public",  # gov-python: allow —— 检测用常量/自检夹具，不是真路径转义伪影
                      "c:\\windows")  # gov-python: allow —— 检测用常量/自检夹具，不是真路径转义伪影

#: Placeholders and annotations that make a sample line legitimate by construction.
PLACEHOLDER_MARKERS = ("<", ">", "$", "%", "{{", "}}", "...", "…", "~")
#: Annotation markers (anywhere on the line) that excuse a sample path. 2026-11-10:
#: also honour the sibling-gate markers (gov-python / gov-credentials / repo-hygiene : allow)
#: -- scan_hardcoded.ps1 already does; g01 formerly did not, so DSH self-test fixtures with
#: ``# gov-python: allow`` were mis-flagged. Marker name differs, exemption intent does not.
ANNOTATION_MARKERS = ("gov-paths: allow", "gov-python: allow", "gov-credentials: allow",
                      "repo-hygiene: allow", "placeholder", "example", "sample", "已失效",
                      "不存在", "占位", "仅示例")

#: An escape tail such as ``\n`` or ``\t`` right after the separator is not a path.
ESCAPE_TAIL = re.compile(r"^[nrtbfv0](?![A-Za-z0-9_./\\-])")

MAX_FILE_BYTES = 1024 * 1024
GENERATED_MARKERS = ("do not edit", "code generated", "auto-generated", "autogenerated", "@generated")


def classify_line(text: str, offset: int) -> str:
    """Return ``comment`` when the offset sits in a line comment, else ``code``.

    The test is textual on purpose: a parser per language would be a second
    implementation to keep in step, and misclassifying a line only ever moves a
    finding between "blocking" and "reported", never out of the report.
    """
    line = govlib.line_text(text, offset)
    column = offset - (text.rfind("\n", 0, offset) + 1)
    stripped = line.lstrip()
    if not stripped:
        return "code"
    if stripped.startswith(LINE_COMMENT_LEADERS):
        return "comment"
    for leader in ("//", "#"):
        index = line.find(leader)
        if index != -1 and index <= column and (index == 0 or line[index - 1] in " \t)]"):
            return "comment"
    return "code"


def is_generated(text: str) -> bool:
    """Detect generator-owned files so hand-editing them is not the gate's business."""
    head = text[:2048].lower()
    return any(marker in head for marker in GENERATED_MARKERS)


def normalize(candidate: str) -> str:
    """Collapse doubled separators left by escaping, keeping the platform."""
    return re.sub(r"([\\/])\1+", r"\1", candidate)


def machine_bound(candidate: str, platform: str) -> bool:
    """Whether the path names a *specific machine, user, or non-system drive*.

    ``in_system_prefix`` exempts OS-owned paths; the live-path exemption (below)
    exempts paths that merely *exist* on this machine. Both let a path that only
    works on the author's box pass the gate -- the portability blind spot P0-13
    fixes. A path that names a concrete non-system drive letter, or a concrete
    user home directory, is machine-bound and must block regardless of whether it
    happens to exist here (the regexes in ``machine_bound`` are the detectors).
    Annotation (``gov-paths: allow`` and sibling-gate markers) and the
    other-platform filter still apply upstream, so legitimate samples stay exempt.
    """
    lowered = candidate.lower()
    if platform == "nt":
        m = re.match(r"^([a-z]):[\\/]", lowered)
        if m and m.group(1) != "c":
            return True
        if re.match(r"^c:[\\/]users[\\/](?!public[\\/]|default[\\/])[^\\/]+[\\/]", lowered):
            return True
        return False
    # POSIX: other-platform paths are already exempted by foreign_platform().
    if re.match(r"^/home/(?!\.\./)[^/]+/", lowered):
        return True
    return False


def foreign_platform(candidate: str, platform: str) -> bool:
    """Whether the path was written for the platform that is not running the gate."""
    is_windows_path = bool(re.match(r"^[A-Za-z]:[\\/]", candidate))
    if platform == "nt":
        return not is_windows_path
    return is_windows_path


def in_system_prefix(candidate: str, platform: str) -> bool:
    """Whether the path belongs to the operating system, not to a person's checkout."""
    lowered = candidate.lower()
    if platform == "nt":
        return any(lowered.startswith(prefix) for prefix in SYSTEM_PREFIXES_NT)
    return any(candidate == prefix or candidate.startswith(prefix + "/") for prefix in SYSTEM_PREFIXES_POSIX)


def parent_missing(candidate: str) -> bool:
    """True when the directory that would contain the path does not exist."""
    path = Path(candidate)
    parent = path.parent
    if str(parent) in ("", "."):
        parent = path
    return not parent.exists()


def scan(root: Path, *, platform: str, include_docs: bool, deep: bool) -> Report:
    """Judge every tracked file of ``root`` and return the classified report."""
    report = Report(title=TITLE)
    for relative in govlib.tracked_files(root):
        if relative.startswith(SKIP_PREFIXES):
            report.exempt("vendored or generated tree")
            continue
        extension = Path(relative).suffix.lower()
        if extension in SKIP_EXTENSIONS:
            report.exempt("binary or asset extension")
            continue
        text = govlib.read_text(root / relative, limit_bytes=MAX_FILE_BYTES)
        if text is None:
            report.exempt("unreadable, binary, or oversized")
            continue
        is_doc = extension in DOC_EXTENSIONS
        is_fixture = (any(segment in f"/{relative}" for segment in FIXTURE_SEGMENTS)
                      or bool(TEST_FILE_NAMES.search(Path(relative).name)))
        is_example = relative.endswith(EXAMPLE_SUFFIXES)
        generated = is_generated(text)
        report.scanned += 1
        for match in (*WIN_PATH.finditer(text), *POSIX_PATH.finditer(text)):
            kind = "windows" if match.re is WIN_PATH else "posix"
            candidate = normalize(match.group(0))
            tail = match.group(2) if kind == "windows" else match.group(2)
            if kind == "windows" and ESCAPE_TAIL.match(tail or ""):
                report.exempt("escape or regex artefact")
                continue
            if not tail:
                report.exempt("bare anchor without a path")
                continue
            line_number = govlib.line_of(text, match.start())
            line = govlib.line_text(text, match.start())
            lowered = line.lower()
            column = match.start() - (text.rfind("\n", 0, match.start()) + 1)
            if "://" in line[:column]:
                report.exempt("path fragment inside a URL")
                continue
            if any(marker.lower() in lowered for marker in ANNOTATION_MARKERS):
                report.exempt("annotated sample line")
                continue
            if any(marker in candidate for marker in PLACEHOLDER_MARKERS):
                report.exempt("placeholder in the sample path")
                continue
            if foreign_platform(candidate, platform):
                report.exempt("path written for the other platform")
                continue
            if in_system_prefix(candidate, platform):
                report.exempt("operating-system path")
                continue
            if not deep:
                report.exempt("deep existence check disabled")
                continue
            if is_doc and not include_docs:
                report.exempt("documentation (report-only)")
                continue
            if is_fixture:
                report.exempt("test fixture or snapshot")
                continue
            if is_example:
                report.exempt("example or template file (report-only)")
                continue
            if generated:
                report.exempt("generator-owned file")
                continue
            if classify_line(text, match.start()) == "comment":
                report.exempt("comment line")
                continue
            # P0-13（2026-11-10）：机器绑定路径（非系统盘 / 具体用户 home）即使本机存在也 block
            # —— 换台机器必然失效，不能因「本机恰好有」就放行（换机盲区）。文档/夹具/示例/注释
            # 等类型豁免已在上方生效，所以此处只命中「维护中源码里的真实机器绑定路径」。
            if not parent_missing(candidate):
                if machine_bound(candidate, platform):
                    report.block(kind, relative, line_number, line)
                    continue
                report.exempt("live path on this machine")
                continue
            report.block(kind, relative, line_number, line)
    return report


def selfcheck() -> int:
    """Prove the gate catches both platform flavours and stays quiet when clean."""
    check = govlib.SelfCheck(gate=GATE)
    clean_source = (
        "const local = join(import.meta.dirname, 'config.json')\n"
        "const url = 'https://example.invalid/C:/not/a/path'\n"  # gov-python: allow —— 检测用常量/自检夹具，不是真路径转义伪影
        "const template = `report:\\n${local}`\n"
        "const escaped = /\\d+\\/\\w+/\n"
        "const home = '~/.dsh/profiles'\n"
        "// gov-paths: allow - sample without a real machine\n"
        "// const sample = 'D:\\\\work\\\\project'\n"  # gov-python: allow —— 检测用常量/自检夹具，不是真路径转义伪影
    )
    with govlib.Sandbox() as sandbox:
        # The injected paths are deliberate fixtures. The inline annotation is the documented
        # exemption, and it has to sit on the same line as the sample it excuses.
        sandbox.write("src/clean.ts", clean_source)
        sandbox.write("src/dead_windows.ts", "const root = 'D:\\\\gov-selfcheck-missing\\\\work'\n")  # gov-paths: allow; gov-python: allow
        sandbox.write("src/dead_posix.ts", "const root = '/Users/gov-selfcheck-missing/work'\n")  # gov-paths: allow
        sandbox.write("src/fixture.spec.ts", "const fake = 'D:\\\\gov-selfcheck-missing\\\\fixture'\n")  # gov-paths: allow; gov-python: allow
        sandbox.write("docs/sample.md", "Config lives in `/Users/gov-selfcheck-missing/work`.\n")  # gov-paths: allow
        # `.txt.example` 的最后后缀是 .example，不进 DOC_EXTENSIONS；这类模板文件里的
        # 示例路径曾在 POSIX 上把 g01 判红（CI Linux job 长期红的根因），必须 report-only。
        sandbox.write("config.txt.example", "示例：/Users/gov-selfcheck-missing/my-plugin\n")  # gov-paths: allow

        nt_report = scan(sandbox.path, platform="nt", include_docs=False, deep=True)
        posix_report = scan(sandbox.path, platform="posix", include_docs=False, deep=True)
        nt_blocked = {finding.path for finding in nt_report.findings}
        posix_blocked = {finding.path for finding in posix_report.findings}

        check.detects("windows dead path in code", "src/dead_windows.ts" in nt_blocked)
        check.detects("posix dead path in code", "src/dead_posix.ts" in posix_blocked)
        check.quiet("clean source file", "src/clean.ts" in nt_blocked or "src/clean.ts" in posix_blocked)
        check.quiet("documentation is report-only", "docs/sample.md" in nt_blocked)
        check.quiet("other-platform path is report-only", "src/dead_posix.ts" in nt_blocked)
        check.quiet("test-file fixture is report-only", "src/fixture.spec.ts" in nt_blocked)
        check.quiet("example/template file is report-only", "config.txt.example" in posix_blocked)

        baseline = Baseline(sandbox.path / "baseline.txt")
        baseline.write(nt_report.findings)
        baseline.load()
        check.quiet("baseline covers frozen findings", bool(baseline.filter_new(nt_report.findings)))
        sandbox.write("src/dead_windows_extra.ts", "const extra = 'D:\\\\gov-selfcheck-missing\\\\more'\n")  # gov-paths: allow; gov-python: allow
        refreshed = scan(sandbox.path, platform="nt", include_docs=False, deep=True)
        check.detects("a new finding escapes the baseline", len(baseline.filter_new(refreshed.findings)) == 1)

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/clean.ts", clean_source)
        clean_report = scan(sandbox.path, platform=sys.platform if sys.platform == "win32" else "linux", include_docs=False, deep=True)
        check.quiet("exit-code probe input is clean", bool(clean_report.findings))

    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--platform", default=None, choices=["nt", "posix"], help="path flavour to judge")
    parser.add_argument("--include-docs", action="store_true", help="let documentation findings block as well")
    parser.add_argument("--no-deep", dest="deep", action="store_false", help="report paths without the existence check")
    parser.add_argument("--quiet", action="store_true", help="print the summary only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    platform = args.platform or ("nt" if sys.platform == "win32" else "posix")
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root, platform=platform, include_docs=args.include_docs, deep=args.deep)

    baseline = Baseline(baseline_path)
    if args.write_baseline:
        baseline.write(report.findings)
        print(f"{TITLE}: baseline written with {len(report.findings)} finding(s) -> {baseline_path}")
        return EXIT_OK
    if not args.no_baseline:
        baseline.load()
    all_findings = report.findings
    new_findings = all_findings if args.no_baseline else baseline.filter_new(all_findings)
    report.findings = all_findings if args.list_all else new_findings
    if args.quiet:
        print(report.render().splitlines()[0])
    else:
        print(report.render())
    # The ratchet note must be judged against every finding, not the filtered list:
    # filtering first makes every reproduced key look stale.
    stale = baseline.stale(all_findings) if baseline.keys else []
    if stale and not args.quiet:
        print(f"  note: {len(stale)} baseline entr(ies) no longer reproduce; refresh with --write-baseline")
    return EXIT_BLOCKING if new_findings else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
