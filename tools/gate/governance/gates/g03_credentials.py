"""Gate g03 -- credentials must never reach the repository or sit on disk in cleartext.

Three faces are judged, because all three have already leaked in practice:

* **tracked content** -- provider tokens, private keys, ``Authorization`` headers,
  URL userinfo, and secret-looking assignments. Candidate lines come from
  ``git grep --cached``, so the gate judges the **index**, not a possibly
  partially-staged working tree, and only candidate files are re-read.
* **``.git/config`` in full** -- a one-off token URL records the token in
  ``branch.<name>.remote``, which ``git remote -v`` never shows.
* **machine-local plaintext files** (2026-11-01) -- a PAT lying in a ``.txt`` on the
  desktop or in the workspace root never reaches the repository, yet it is exactly
  as exposed. The gate does not move credentials for anyone; it makes the red line
  mechanical: report it, then the credential goes into a managed store
  (this machine: ``~/.dsvault``, DPAPI-sealed) and the plaintext goes away.

Placeholder discipline is what keeps this gate believable: a documented value
such as ``<GITEE_TOKEN>``, ``${API_KEY}``, ``your-token-here`` or ``redacted`` is
a sample, not a leak, and the value must additionally look like a secret before
anything blocks.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, Baseline, GateError, Report  # noqa: E402

GATE = "g03-credentials"
TITLE = "governance: no credentials in tracked content, git config, or machine-local plaintext"

#: Broad prefilter handed to `git grep --cached`; precision happens in Python.
PREFILTER = (r"sk-|ghp_|github_pat_|glpat-|xox[baprs]-|AKIA|AIza|BEGIN [A-Z ]*PRIVATE KEY|"
             r"password|passwd|secret|token|api[_-]?key|apikey|Authorization|https?://|"
             r"[0-9a-fA-F]{30,}")

#: Precise patterns, most specific first. Each entry is (category, compiled pattern).
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("provider-token", re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{30,}|"
                                  r"github_pat_[A-Za-z0-9_]{30,}|glpat-[A-Za-z0-9_\-]{18,}|"
                                  r"xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|"
                                  r"AIza[0-9A-Za-z_\-]{35})\b")),
    ("url-userinfo", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^/\s:@]{1,64}:[^/\s@]{8,}@")),
    ("bearer-header", re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._\-]{20,}")),
    # 2026-11-04 工程审查 P1：原键名前缀 (?<![/&?]) 把 `?token=` / `&token=` 整个
    # 排除，且键名两端不接受引号 ⇒ JSON/YAML 引号键与 URL query 参数两种常见形态
    # 全部漏报。现改为：只挡「嵌在别的标识符里」的 (?<![A-Za-z0-9_])，键名两侧
    # 允许可选引号，覆盖 ① token = x ② "token": "x" ③ ?token=x / &api_key=x。
    ("assignment", re.compile(r"(?i)(?<![A-Za-z0-9_])[\"']?"
                              r"(access[_-]?token|api[_-]?key|apikey|auth[_-]?token|"
                              r"client[_-]?secret|password|passwd|secret|token|gitee[_-]?token)"
                              r"[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_\-./+]{16,})")),
    # Bare high-entropy hex run (e.g. a Gitee PAT committed as a raw hex string with
    # no surrounding key). Precision (entropy + length band) is applied in `scan` via
    # `looks_like_secret_hex`; this only decides *which* lines reach it. Hex that sits
    # inside a URL (preceded/followed by ':', '/' or '@') is excluded here so the
    # url-userinfo branch -- which already knows about sample hosts -- keeps authority.
    # {30,} 而非 {30,63}：原上限 63 让 64 位及更长的裸 hex 串根本进不了判定
    # （量词吃掉前 63 位后，负向前视撞上第 64 位 hex 而整体失配）。
    ("hex-secret", re.compile(r"(?<![0-9a-fA-F:/@])(?:[0-9a-fA-F]{30,})(?![0-9a-fA-F:/@])")),  # gov-paths: allow —— 字符类里的 F:/ 被 g01 WIN_PATH 误判为 windows 路径，非真路径
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

#: The machine-local scan omits the bare-hex detector. Stray 30+ hex runs are
#: ubiquitous in ordinary machine files (logs, caches, app data, build artifacts)
#: and would drown the real signal; the tracked-content and .git/config scans keep
#: the full pattern set where the Gitee-PAT threat actually lives.
MACHINE_PATTERNS = tuple((cat, pat) for cat, pat in PATTERNS if cat != "hex-secret")

#: Reading the value from the environment is configuration, not a committed secret.
ENV_REFERENCES = ("process.env", "import.meta.env", "os.environ", "os.getenv", "getenv(", "deno.env",
                  "env::var", "$env:")

#: Hosts that exist only in examples and tests.
SAMPLE_HOSTS = ("example.", ".invalid", ".test", "localhost", "127.0.0.1", "host.invalid")

#: A userinfo password slot that expands from the environment, not a literal secret.
ENV_REFERENCE_VALUE = re.compile(
    r"(?i)^(?:\$\{?[a-z_][a-z0-9_]*\}?|%[a-z_][a-z0-9_]*%|\{\{.*\}\}|<[^>]+>)$"
)

#: A userinfo pair that is obviously a documentation placeholder.
SAMPLE_USERINFO = ("user:password", "user:pass", "username:password", "user:secret", "admin:admin")

#: Same-line opt-out, used by fixture files that must contain a sample token.
ANNOTATION = "gov-credentials: allow"

#: 2026-11-07 安全加固 F-01：注解**不再是**「任何文件里出现就整行豁免」。
#: 豁免权归仓库受评审的配置，不归被扫描内容本身 —— 与 CI 增量扫描
#: scripts/scan-secrets.sh 共用同一份白名单，两侧口径不允许漂移。
#: 文件缺失/不可读时按空集合处理（fail closed：宁可把夹具判红，不开口子）。
ANNOTATION_ALLOWLIST_REL = "scripts/secret-scan-allowlist.txt"

#: 历史常量：样例文件后缀。2026-11-08 起**不再**用于整文件豁免（P0-2），
#: 保留仅为兼容外部引用与文档说明；豁免一律按内容判定。
SAMPLE_FILE_SUFFIXES = (".example", ".sample", ".template", ".dist")
SAMPLE_FILE_INFIXES = (".example.", ".sample.", ".template.", ".dist.")
SAMPLE_FILE_NAMES = frozenset({".env.example", ".env.sample", ".env.template", ".env.dist"})

MAX_FILE_BYTES = 2 * 1024 * 1024
CONFIG_CREDENTIAL = re.compile(r"https?://[^/\s:@]+:[^/\s@]{6,}@")

# --------------------------------------------------------------------------
# 第三面：机器本地「明文凭据文件」
#
# 前两面只管「进了仓的」与「.git/config 里的」；**机器上的明文文件**（桌面、工作区根、
# 用户目录）同样会泄密 —— 实测本机就有一份明文 PAT 躺在工作区根的 `.txt` 里。
# 处置：本门禁**不替人搬凭据**，只把红线机械化：**发现了就报红**，逼人把它收进受管库
# （本机 `~/.dsvault`，DPAPI 信封加密）再删明文。

#: 用户常见落点（递归到第 2 层）
MACHINE_USER_DIRS = ("Desktop", "Documents", "Downloads")

#: 合法例外：SSH 私钥本就该明文、受管库密文不是明文、依赖树与版本库不归本门禁
MACHINE_SKIP_DIRS = frozenset({".ssh", ".dsvault", ".git", "node_modules", "__pycache__",
                                ".venv", "venv", ".cache", ".npm", ".cargo", ".rustup",
                                "AppData", "Windows", "System Volume Information",
                                "$RECYCLE.BIN", ".Trash", "site-packages", "__pypackages__",
                                ".m2", ".gradle", ".nuget", ".vscode", ".idea"})

#: 非文本载体 ⇒ 跳过（含受管库密文 `.enc`、证书、私钥容器、二进制）
MACHINE_SKIP_SUFFIX = (".enc", ".key", ".pem", ".pfx", ".p12", ".crt", ".cer", ".der",
                        ".exe", ".dll", ".so", ".dylib", ".zip", ".7z", ".tar", ".gz", ".bz2",
                        ".xz", ".iso", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                        ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".sqlite", ".db", ".log")

#: 工作区根（仓根的上级）只扫第 0 层；用户目录扫到第 2 层
MACHINE_WORKSPACE_DEPTH = 0
MACHINE_USER_DEPTH = 2


def machine_scan_roots(root: Path) -> list[tuple[Path, int]]:
    """机器本地扫描根与深度：工作区根（浅）+ 用户常见目录（稍深）。"""
    out: list[tuple[Path, int]] = []
    parent = root.parent
    if parent and parent.is_dir() and parent != root:
        out.append((parent, MACHINE_WORKSPACE_DEPTH))
    home = Path.home()
    for name in MACHINE_USER_DIRS:
        p = home / name
        if p.is_dir():
            out.append((p, MACHINE_USER_DEPTH))
    return out


def _is_repo_dir(path: Path) -> bool:
    return (path / ".git").exists()


def machine_plaintext_findings(roots: list[tuple[Path, int]]) -> list[tuple[str, int, str, str]]:
    """机器本地明文凭据文件命中：[(相对路径, 行号, 类别, 行文本)]。"""
    findings: list[tuple[str, int, str, str]] = []
    for base, max_depth in roots:
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            here = Path(dirpath)
            depth = len(here.relative_to(base).parts)
            dirnames[:] = [d for d in dirnames
                           if d not in MACHINE_SKIP_DIRS
                           and not _is_repo_dir(here / d)]
            if depth >= max_depth:
                dirnames[:] = []
            for fn in filenames:
                p = here / fn
                if p.suffix.lower() in MACHINE_SKIP_SUFFIX:
                    continue
                # P0-2（2026-11-08）：文件名后缀不是豁免权。此前任何
                # *.example / *.sample / *.dist 都被整文件跳过，等于给「把真密钥
                # 塞进样例文件」留了直通口。现在照常参与内容判定：占位符由下方
                # value_is_sample() 放行，真实凭据形状照常报红。
                try:
                    if p.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for number, line in enumerate(text.splitlines(), start=1):
                    if ANNOTATION in line:
                        continue
                    for category, pattern in MACHINE_PATTERNS:
                        match = pattern.search(line)
                        if match is None:
                            continue
                        if category == "assignment":
                            value = match.group(2)
                            if value_is_sample(value, line) or not looks_secret(value):
                                continue
                        elif category == "url-userinfo":
                            if url_is_sample(match.group(0), line):
                                continue
                        elif category in ("provider-token", "bearer-header", "private-key"):
                            if value_is_sample(match.group(0), line):
                                continue
                        try:
                            shown = str(p.relative_to(base))
                        except ValueError:
                            shown = str(p)
                        findings.append((shown, number, category, line.strip()[:120]))
                        break
    return findings


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


def shannon_entropy(value: str) -> float:
    """Bits per character of Shannon entropy; a uniformly random hex string ≈ 4.0."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


#: 行内出现这些词时，40/64 位 hex 不能再按 digest 放行 —— 它处于凭据语境。
#: 只看行文本、不看路径（仓内 ``g03_credentials.py`` 这类路径自带 credential 字样，
#: 若把路径算进来会把门禁源码与自检夹具整行误判）。
CREDENTIAL_CONTEXT = re.compile(
    r"(?i)(?:\b(?:token|secret|password|passwd|api[_-]?key|apikey|pat|credential|"
    r"auth|access[_-]?key|private[_-]?key|bearer)\b|凭据|口令|密钥|授权|令牌|访问令牌)"
)


def looks_like_secret_hex(value: str, line: str = "") -> bool:
    """A bare hex run is a credential only when it is long and high-entropy.

    40/64 位是 git SHA 与 SHA-256 的标准长度，公开仓里遍布 action 钉、提交留档、
    校验和（本机实测 68 行），一律报红会让门禁失去可信度。故默认按 digest 放行；
    **唯一例外**是整行明确处于凭据语境（token / password / 密钥…）—— 此时 Gitee
    PAT 与摘要在字符串层面不可区分，宁可报红也不能放行。带键名的 40/64 hex 由
    ``assignment`` 分支先行拦截，走不到这里。
    """
    h = value.lower()
    if not re.fullmatch(r"[0-9a-f]{30,}", h):
        return False
    if shannon_entropy(h) < 3.5:
        return False
    if len(h) in (40, 64):  # canonical git SHA / SHA-256 — a digest, not a token
        return CREDENTIAL_CONTEXT.search(line) is not None
    return True


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
    if userinfo in SAMPLE_USERINFO:
        return True
    # A password slot that expands from the environment (``${TOKEN}``, ``$TOKEN``,
    # ``%TOKEN%``, ``{{ token }}``, ``<token>``) is configuration, not a committed
    # secret -- the same allowance the assignment patterns already give.
    return ENV_REFERENCE_VALUE.match(userinfo.rsplit(":", 1)[-1]) is not None


def candidate_lines(root: Path) -> list[tuple[str, int, str]]:
    """Index-match candidate lines, one `(path, line, text)` tuple each."""
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "grep", "--cached", "-n", "-I", "-i", "-E", PREFILTER],
        cwd=str(root),
        env=govlib.git_env(),
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


def annotation_allowlist(root: Path, extra: set[str] | None = None) -> frozenset[str]:
    """Paths permitted to use the inline annotation.

    The set comes from a tracked, reviewable allowlist shared with
    ``scripts/scan-secrets.sh``. ``extra`` exists only so this gate's own
    selfcheck sandbox can declare its fixture paths (a sandbox has no repo
    config of its own). A missing or unreadable allowlist yields an EMPTY
    set — fail closed rather than silently restoring the old blanket opt-out.
    """
    allowed: set[str] = set()
    cfg = root / ANNOTATION_ALLOWLIST_REL
    try:
        for raw in cfg.read_text(encoding="utf-8").splitlines():
            item = raw.strip()
            if item and not item.startswith("#"):
                allowed.add(item)
    except (OSError, UnicodeError):
        pass
    if extra:
        allowed.update(extra)
    return frozenset(allowed)


def scan(root: Path, *, include_docs: bool = True,
         machine_roots: list[tuple[Path, int]] | None = None,
         annotation_paths: set[str] | None = None) -> Report:
    """Judge tracked content, `.git/config`, and machine-local plaintext files."""
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
    allowed_annotation = annotation_allowlist(root, annotation_paths)
    for path, number, line in candidates:
        # P0-2（2026-11-08）：样例后缀不再整文件豁免。占位符由
        # value_is_sample / looks_secret 按内容放行；真实令牌形状即使藏在
        # .env.example 里也必须报红（见 selfcheck 的对应回归用例）。
        if ANNOTATION in line and path in allowed_annotation:
            report.exempt("inline annotation (allowlisted fixture file)")
            continue
        # 未登记文件里的注解不构成豁免（F-01）：照常走下面的形状判定。
        # 注解本身只是被扫描内容的一部分，不能由提交者自行声明豁免权。
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
            elif category in ("provider-token", "bearer-header", "private-key", "hex-secret"):
                value = match.group(0)
                if value_is_sample(value, line):
                    report.exempt("token shape carries a synthetic marker")
                    continue
                if category == "hex-secret" and not looks_like_secret_hex(value, line):
                    report.exempt("hex run is a digest or low-entropy, not a token")
                    continue
            matched = True
            report.block(category, path, number, line)
            break
        if not matched:
            report.exempt("candidate line carried no credential shape")

    # 第三面：机器本地明文凭据文件
    roots = machine_scan_roots(root) if machine_roots is None else machine_roots
    for shown, number, category, line in machine_plaintext_findings(roots):
        report.block("machine-plaintext-" + category, shown, number, line)
    if roots:
        report.scanned += len(roots)
    else:
        report.skip("no machine-local credential roots to scan")
    return report


def selfcheck() -> int:
    """Prove the gate catches each credential shape and excuses real samples."""
    from selfcheck_fixtures import Case, run_cases, signals

    # One mixed sandbox used to drive six assertions at once; the table keeps the
    # same fixture dict and yields one declarative row per assertion.
    mixed = {
        "src/clean.ts": ("const url = 'https://example.invalid/path'\n"
                         "const note = 'password: <GITEE_TOKEN>'\n"
                         "const sample = 'api_key = your-key-here'\n"
                         "const word = 'tokenization of the sentence'\n"
                         "const fixture = 'glpat-ABCDEFGHIJKLMNOPQRST'  // gov-credentials: allow\n"),  # gov-credentials: allow
        "src/config.ts": (
            "const fromEnv = process.env.GITHUB_TOKEN\n"
            "const fromEnv2 = 'token: ' + import.meta.env.DSH_TOKEN\n"
            "readonly token: ToolExecutionToken\n"
            "const token = getComputedStyle(document.body).getPropertyValue('--x-bg').trim()\n"
            "const named = 'github-webhook-review-secret'\n"
            "const e2e = 'github-webhook-real-e2e-secret'\n"
            "const SECRET = 'plum-galaxy-1791'\n"
            "const url = 'https://user:password@example.test/file?token=secret'\n"),
        "config/settings.ts": "const key = 'sk-abcdefghijklmnop1234567890abcd'\n",  # gov-credentials: allow
        "src/auth.ts": "const header = 'Authorization: Bearer abcdefghijklmnop1234567890'\n",  # gov-credentials: allow
        "src/keys.ts": "const apiKey = 'a8f3d9e2b7c4a1f6d0e5b8c3a9f2d7e4'\n",  # gov-credentials: allow
        "src/legacy.ts": ("const token = 'https://svc:8f14e45fceea167a5a36dedd4bea2543@git.corp-net.io/x'\n"),  # gov-credentials: allow
        # Deliberately no annotation: this must prove the environment-reference
        # allowance inside a URL userinfo, not the inline opt-out.
        "src/push_example.ts": "const push = 'https://<user>:${TOKEN}@gitee.com/<owner>/<repo>.git'\n",
    }
    # .git/config is written untracked by sandbox_with (git cannot stage its own
    # metadata); the branch token and the empty helper are the two config faces.
    remote_config = (
        "[remote \"origin\"]\n\turl = https://gitee.com/owner/name.git\n"  # gov-python: allow —— 自检夹具，非真路径伪影
        "[branch \"main\"]\n\tremote = https://owner:8f14e45fceea167a5a36dedd4bea2543@gitee.com/owner/name.git\n")  # gov-credentials: allow

    # Gitee 裸 hex PAT 形态（2026-11-02 审计漏报）：键名族 + 纯裸 hex，附 git SHA 对照。
    hex_files = {
        "src/gitee_config.ts": "const GITEE_TOKEN = 'a1b2c3d4e5f6789012345678901234'\n",  # gov-credentials: allow
        "src/raw_hex.ts": "a1b2c3d4e5f6789012345678901234\n",  # gov-credentials: allow
        "src/commit_sha.ts": "const head = 'e7e54de074b2d6dfe24cac08de4535875c34651f'\n",
    }

    # 2026-11-04 工程审查 P1：JSON 引号键 / URL query / 64hex / 凭据语境裸串 / 128hex，
    # 外加无凭据语境的 40/64 digest 对照。hex 夹具行尾注解让 CI 增量扫描跳过。
    hex40 = "a1b2c3d4e5f6789012345678901234567890abcd"  # gov-credentials: allow
    hex64 = "d4c3b2a1" * 8
    p1_files = {
        "src/json_key.ts": f'const cfg = {{ "token": "{hex40}" }};\n',
        "src/query.ts": f"const url = 'https://gitee.com/api/v5/user?access_token={hex40}';\n",
        "src/long_key.ts": f'const cfg = {{ "api_key": "{hex64}" }};\n',
        "src/bare_with_context.ts": f"// 凭据 token 留档：{hex40}\n",
        "src/very_long_hex.ts": "c1d2e3f4a5b6" * 10 + "c1d2e3f4\n",
        "src/quiet_digest.ts": (
            "const head = 'e7e54de074b2d6dfe24cac08de4535875c34651f'\n"  # gov-credentials: allow
            "const sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'\n"),  # gov-credentials: allow
    }

    # 第三面（机器本地明文）：@ 前缀把夹具写到索引外，等价于旧的 direct-write。
    machine_real = {"@outside/creds.txt": "token = github_pat_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8\n",  # gov-credentials: allow
                    "@outside/notes.md": "口令见受管库；此文件无凭据形态。\n"}
    machine_placeholder = {"@outside/creds.txt": "token = <GITEE_TOKEN>\n"}
    clean_repo = {"src/ok.ts": "export const answer = 42\n"}
    hidden_real = {"src/hidden.ts": "const key = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'  // gov-credentials: allow\n"}  # gov-credentials: allow
    declared_fixture = {"src/fixture.ts": "const key = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'  // gov-credentials: allow\n"}  # gov-credentials: allow

    cases = [
        Case("provider token", mixed, by="provider-token"),
        Case("bearer header", mixed, by="bearer-header"),
        Case("url userinfo", mixed, by="url-userinfo"),
        Case("secret-shaped assignment", mixed, by="assignment"),
        Case("clean lines, placeholders, env references, and sample hosts", mixed,
             expect="clean", by="src/clean.ts||src/config.ts"),
        Case("a URL userinfo that expands an environment variable", mixed,
             expect="clean", by="src/push_example.ts"),
        Case("token recorded in branch.<name>.remote",
             {**clean_repo, ".git/config": remote_config}, by="config-credential"),
        Case("empty credential.helper clears the helper chain",
             {**clean_repo, ".git/config": "[credential]\n\thelper =\n"}, by="empty-credential-helper"),
        Case("a repository with no credential shape", clean_repo, expect="clean"),
        # P0-2（2026-11-08）：样例后缀不再是豁免权。
        Case("a real token shape hidden behind a .sample suffix",
             {"src/config.sample.ts": "const key = 'sk-abcdefghijklmnopqrstuvwxyz012345'\n"},  # gov-credentials: allow
             by="src/config.sample.ts"),
        Case("a placeholder inside a sample-suffixed file stays quiet",
             {"src/config.example.ts": "const key = 'sk-example-placeholder-000000000000'\n"},
             expect="clean", by="src/config.example.ts"),
        # 第三面：机器本地明文凭据文件（2026-11-01）。
        Case("a plaintext credential file outside the repository is reported",
             machine_real, by="kind~machine-plaintext"),
        Case("a machine-local file without a credential shape stays quiet",
             machine_real, expect="clean", by="notes.md"),
        Case("a placeholder value in a machine-local file is a sample, not a leak",
             machine_placeholder, expect="clean", by="kind~machine-plaintext"),
        Case("Gitee-style token assignment (GITEE_TOKEN = <hex>)",
             hex_files, by="src/gitee_config.ts::assignment"),
        Case("bare high-entropy hex on its own line", hex_files, by="src/raw_hex.ts::hex-secret"),
        Case("a 40-char git SHA is not flagged as a secret", hex_files, expect="clean", by="src/commit_sha.ts"),
        Case("40-char hex behind a JSON quoted key", p1_files, by="src/json_key.ts::assignment"),
        Case("40-char hex in a URL query parameter", p1_files, by="src/query.ts::assignment"),
        Case("64-char hex behind a JSON quoted key", p1_files, by="src/long_key.ts::assignment"),
        Case("bare 40-char hex in a credential context", p1_files, by="src/bare_with_context.ts::hex-secret"),
        Case("128-char bare hex run (beyond the old {30,63} cap)", p1_files, by="src/very_long_hex.ts::hex-secret"),
        Case("40/64-char digests with no credential context stay quiet", p1_files,
             expect="clean", by="src/quiet_digest.ts"),
        # 2026-11-07 安全加固 F-01：注解的豁免权归仓库配置，不归被扫描内容。
        Case("an inline allow annotation outside the allowlist does not hide a real token",
             hidden_real, by="src/hidden.ts::provider-token"),
        Case("a selfcheck-declared fixture path still honours the annotation",
             declared_fixture, expect="clean", by="src/fixture.ts"),
    ]

    def check_fn(sandbox):
        root = sandbox.path
        annotation_paths = None
        if (root / "src" / "clean.ts").exists():
            annotation_paths = {"src/clean.ts"}
        elif (root / "src" / "fixture.ts").exists():
            annotation_paths = {"src/fixture.ts"}
        outside = root / "outside"
        machine_roots = [(outside, 0)] if outside.is_dir() else []
        return signals(scan(root, machine_roots=machine_roots, annotation_paths=annotation_paths))

    return run_cases(GATE, cases, check_fn)


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
    return report.exit_code(new_findings)


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
