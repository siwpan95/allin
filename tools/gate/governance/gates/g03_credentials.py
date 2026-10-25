"""Gate g03 -- credentials must never reach the repository.

Two faces are judged, because both have already leaked in practice:

* **tracked content** -- provider tokens, private keys, ``Authorization`` headers,
  URL userinfo, and secret-looking assignments. Candidate lines come from
  ``git grep --cached``, so the gate judges the **index**, not a possibly
  partially-staged working tree, and only candidate files are re-read.
* **``.git/config`` in full** -- a one-off token URL records the token in
  ``branch.<name>.remote``, which ``git remote -v`` never shows.

Placeholder discipline is what keeps this gate believable: a documented value
such as ``<GITEE_TOKEN>``, ``${API_KEY}``, ``your-token-here`` or ``redacted`` is
a sample, not a leak, and the value must additionally look like a secret before
anything blocks.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, GateError, Report  # noqa: E402

GATE = "g03-credentials"
TITLE = "governance: no credentials in tracked content or git config"

#: Broad prefilter handed to `git grep --cached`; precision happens in Python.
PREFILTER = (r"sk-|ghp_|github_pat_|glpat-|xox[baprs]-|AKIA|AIza|BEGIN [A-Z ]*PRIVATE KEY|"
             r"password|passwd|secret|token|api[_-]?key|apikey|Authorization|https?://")

#: Precise patterns, most specific first. Each entry is (category, compiled pattern).
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("provider-token", re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{30,}|"
                                  r"github_pat_[A-Za-z0-9_]{30,}|glpat-[A-Za-z0-9_\-]{18,}|"
                                  r"xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|"
                                  r"AIza[0-9A-Za-z_\-]{35})\b")),
    ("url-userinfo", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^/\s:@]{1,64}:[^/\s@]{8,}@")),
    ("bearer-header", re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("assignment", re.compile(r"(?i)(?<![/&?])\b(access[_-]?token|api[_-]?key|apikey|auth[_-]?token|"
                              r"client[_-]?secret|password|passwd|secret|token)\b\s*[:=]\s*"
                              r"[\"']?([A-Za-z0-9_\-./+]{16,})")),
)

#: A value that is a documented sample rather than a secret.
PLACEHOLDER_VALUE = re.compile(
    r"(?i)^(?:<[^>]*>|\$\{[^}]*\}|%[^%]*%|\{\{[^}]*\}\}|x{4,}|X{4,}|\*{4,}\.{0,3}|"
    r"example[._\-]?.*|placeholder.*|your[._\-].*|changeme.*|change[._\-]?me.*|redacted.*|"
    r"dummy.*|fake[._\-]?.*|sample.*|test[._\-]?.*|not[._\-]?a[._\-]?real.*|none|null|todo.*|"
    r"\.{3,}|…)$"
)

#: Substrings that mark a synthetic value wherever they appear inside it.
SAMPLE_MARKERS = ("test", "example", "dummy", "fake", "sample", "mock", "synthetic", "placeholder",
                  "not-real", "not_real", "notreal", "redacted", "changeme", "xxxx", "e2e",
                  "localhost", "signed-out", "for-the-renderer", "do-not-log", "do_not_log")

#: Reading the value from the environment is configuration, not a committed secret.
ENV_REFERENCES = ("process.env", "import.meta.env", "os.environ", "os.getenv", "getenv(", "deno.env",
                  "env::var", "$env:")

#: Hosts that exist only in examples and tests.
SAMPLE_HOSTS = ("example.", ".invalid", ".test", "localhost", "127.0.0.1", "host.invalid")

#: A userinfo pair that is obviously a documentation placeholder.
SAMPLE_USERINFO = ("user:password", "user:pass", "username:password", "user:secret", "admin:admin")

#: Same-line opt-out, used by fixture files that must contain a sample token.
ANNOTATION = "gov-credentials: allow"

#: Files whose whole purpose is a documented sample, by suffix or infix.
SAMPLE_FILE_SUFFIXES = (".example", ".sample", ".template", ".dist")
SAMPLE_FILE_INFIXES = (".example.", ".sample.", ".template.", ".dist.")
SAMPLE_FILE_NAMES = frozenset({".env.example", ".env.sample", ".env.template", ".env.dist"})

MAX_FILE_BYTES = 2 * 1024 * 1024
CONFIG_CREDENTIAL = re.compile(r"https?://[^/\s:@]+:[^/\s@]{6,}@")


def looks_secret(value: str) -> bool:
    """A secret-shaped value: a long unbroken run, mixing classes, carrying digits.

    Real credentials are long uninterrupted strings. A word-separated phrase such
    as ``plum-galaxy-1791`` is a fixture name, so the run must not span hyphens.
    """
    if PLACEHOLDER_VALUE.match(value):
        return False
    if len(value) < 16:
        return False
    if re.search(r"[A-Za-z0-9+/=]{16,}", value) is None:
        return False
    if re.search(r"[0-9]", value) is None:
        # Identifiers, type names, and documentation labels carry no digits; a
        # credential of this length without one is vanishingly rare.
        return False
    classes = sum(bool(re.search(pattern, value)) for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))
    return classes >= 2 or len(value) >= 32


def value_is_sample(value: str, line: str) -> bool:
    """Whether a matched value is synthetic, derived, or an environment reference."""
    if PLACEHOLDER_VALUE.match(value):
        return True
    lowered = value.lower()
    if any(marker in lowered for marker in SAMPLE_MARKERS):
        return True
    return any(reference in line for reference in ENV_REFERENCES)


def url_is_sample(match: str, line: str) -> bool:
    """Whether a URL with userinfo points at a documentation host or sample pair."""
    lowered_line = line.lower()
    if any(host in lowered_line for host in SAMPLE_HOSTS):
        return True
    userinfo = match.split("://", 1)[-1].split("@", 1)[0].lower()
    return userinfo in SAMPLE_USERINFO


def candidate_lines(root: Path) -> list[tuple[str, int, str]]:
    """Index-match candidate lines, one `(path, line, text)` tuple each."""
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "grep", "--cached", "-n", "-I", "-i", "-E", PREFILTER],
        cwd=str(root),
        env={**govlib.GIT_ENV},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    # Exit 1 means "no match", which is a clean result, not a failure.
    if completed.returncode not in (0, 1):
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise GateError(f"git grep --cached failed in {root}: {detail}")
    text = completed.stdout.decode("utf-8", "replace")
    found: list[tuple[str, int, str]] = []
    for raw in text.splitlines():
        path, _, rest = raw.partition(":")
        number, _, line = rest.partition(":")
        if not number.isdigit():
            continue
        found.append((path, int(number), line))
    return found


def scan(root: Path, *, include_docs: bool = True) -> Report:
    """Judge tracked content and `.git/config`; return the classified report."""
    report = Report(title=TITLE)
    config_path = root / ".git" / "config"
    if config_path.is_file():
        report.scanned += 1
        config = govlib.read_text(config_path) or ""
        section = ""
        for number, line in enumerate(config.splitlines(), start=1):
            stripped = line.strip()
            header = re.match(r"^\[([^\]]+)\]", stripped)
            if header is not None:
                section = header.group(1).strip().lower()
                continue
            if CONFIG_CREDENTIAL.search(line):
                report.block("config-credential", ".git/config", number, line)
            elif section.split(" ")[0] == "credential" and re.match(r"^helper\s*=\s*$", stripped):
                report.block("empty-credential-helper", ".git/config", number, line)
    else:
        report.skip("no .git/config at the root (bare or linked checkout?)", 1)

    candidates = candidate_lines(root)
    report.scanned += len({path for path, _number, _line in candidates})
    for path, number, line in candidates:
        name = Path(path).name
        if (name in SAMPLE_FILE_NAMES or name.endswith(SAMPLE_FILE_SUFFIXES)
                or any(infix in name for infix in SAMPLE_FILE_INFIXES)):
            report.exempt("documented sample file")
            continue
        if ANNOTATION in line:
            report.exempt("inline annotation")
            continue
        matched = False
        for category, pattern in PATTERNS:
            match = pattern.search(line)
            if match is None:
                continue
            if category == "assignment":
                value = match.group(2)
                if value_is_sample(value, line):
                    report.exempt("assignment value is a sample or an environment reference")
                    continue
                if not looks_secret(value):
                    report.exempt("assignment value is not secret-shaped")
                    continue
            elif category in ("url-userinfo",):
                if url_is_sample(match.group(0), line):
                    report.exempt("URL points at a documentation host or sample pair")
                    continue
            elif category in ("provider-token", "bearer-header", "private-key"):
                if value_is_sample(match.group(0), line):
                    report.exempt("token shape carries a synthetic marker")
                    continue
            matched = True
            report.block(category, path, number, line)
            break
        if not matched:
            report.exempt("candidate line carried no credential shape")
    return report


def selfcheck() -> int:
    """Prove the gate catches each credential shape and excuses real samples."""
    check = govlib.SelfCheck(gate=GATE)
    with govlib.Sandbox() as sandbox:
        sandbox.write("src/clean.ts", "const url = 'https://example.invalid/path'\n"
                                      "const note = 'password: <GITEE_TOKEN>'\n"
                                      "const sample = 'api_key = your-key-here'\n"
                                      "const word = 'tokenization of the sentence'\n"
                                      "const fixture = 'glpat-ABCDEFGHIJKLMNOPQRST'  // gov-credentials: allow\n")  # gov-credentials: allow
        sandbox.write("src/config.ts",
                      "const fromEnv = process.env.GITHUB_TOKEN\n"
                      "const fromEnv2 = 'token: ' + import.meta.env.DSH_TOKEN\n"
                      "readonly token: ToolExecutionToken\n"
                      "const token = getComputedStyle(document.body).getPropertyValue('--x-bg').trim()\n"
                      "const named = 'github-webhook-review-secret'\n"
                      "const e2e = 'github-webhook-real-e2e-secret'\n"
                      "const SECRET = 'plum-galaxy-1791'\n"
                      "const url = 'https://user:password@example.test/file?token=secret'\n")
        sandbox.write("config/settings.ts", "const key = 'sk-abcdefghijklmnop1234567890abcd'\n")  # gov-credentials: allow
        sandbox.write("src/auth.ts", "const header = 'Authorization: Bearer abcdefghijklmnop1234567890'\n")  # gov-credentials: allow
        sandbox.write("src/keys.ts", "const apiKey = 'a8f3d9e2b7c4a1f6d0e5b8c3a9f2d7e4'\n")  # gov-credentials: allow
        sandbox.write("src/legacy.ts",
                      "const token = 'https://svc:8f14e45fceea167a5a36dedd4bea2543@git.corp-net.io/x'\n")  # gov-credentials: allow
        report = scan(sandbox.path)
        blocked = {finding.kind for finding in report.findings}
        blocked_paths = {finding.path for finding in report.findings}
        check.detects("provider token", "provider-token" in blocked)
        check.detects("bearer header", "bearer-header" in blocked)
        check.detects("url userinfo", "url-userinfo" in blocked)
        check.detects("secret-shaped assignment", "assignment" in blocked)
        check.quiet("clean lines, placeholders, env references, and sample hosts",
                    "src/clean.ts" in blocked_paths or "src/config.ts" in blocked_paths)

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/ok.ts", "export const answer = 42\n")
        (sandbox.path / ".git" / "config").write_text(
            "[remote \"origin\"]\n\turl = https://gitee.com/owner/name.git\n"
            "[branch \"main\"]\n\tremote = https://owner:8f14e45fceea167a5a36dedd4bea2543@gitee.com/owner/name.git\n",  # gov-credentials: allow
            encoding="utf-8")
        report = scan(sandbox.path)
        check.detects("token recorded in branch.<name>.remote",
                      any(finding.kind == "config-credential" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/ok.ts", "export const answer = 42\n")
        config = sandbox.path / ".git" / "config"
        config.write_text(config.read_text(encoding="utf-8") + "[credential]\n\thelper =\n", encoding="utf-8")
        report = scan(sandbox.path)
        check.detects("empty credential.helper clears the helper chain",
                      any(finding.kind == "empty-credential-helper" for finding in report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/ok.ts", "export const answer = 42\n")
        report = scan(sandbox.path)
        check.quiet("a repository with no credential shape", bool(report.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("src/config.sample.ts", "const key = 'sk-abcdefghijklmnopqrstuvwxyz012345'\n")  # gov-credentials: allow
        report = scan(sandbox.path)
        check.quiet("a documented sample file suffix", bool(report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    report = scan(root)
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
