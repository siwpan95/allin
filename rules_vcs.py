"""git 与仓库卫生类规则 17/18/20/21/22/23/29。

全部依赖 ``git ls-files`` / ``git tag`` / ``git describe`` 这类**只读**命令，
不执行项目代码、不联网。没有 .git 时由执行器统一跳过并计入分数上限，
避免「跳过越多分越高」。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

from rulebase import CheckResult, Rule, Severity

if TYPE_CHECKING:  # pragma: no cover
    from scanctx import ProjectContext

try:  # Python 3.11+ 内置
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

#: 报告里单项 detail 最多列几条。
MAX_DETAIL_ITEMS = 5

#: 语义化版本（SemVer 2.0.0 的宽松形态）。
SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


# ---------------------------------------------------------------------------
# 规则 17：CHANGELOG 落后最新 tag
# ---------------------------------------------------------------------------

def _check_changelog_stale(ctx: "ProjectContext") -> CheckResult:
    """规则 17：最新版本 tag 是否已写进 CHANGELOG。"""
    # 先看 CHANGELOG 在不在：不在就直接跳过，省掉一次 git 子进程
    rel = ctx.root_startswith("changelog")
    if rel is None:
        return CheckResult.skip("no-changelog")  # 规则 16 已报

    latest = ctx.git.latest_version_tag()
    if latest is None:
        return CheckResult.skip("no-version-tag")

    text = ctx.text(rel)
    if text is None:
        return CheckResult.skip("unreadable")

    version = latest[1:] if latest.lower().startswith("v") else latest
    if re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", text):
        return CheckResult.ok()
    return CheckResult.bad(f"最新 tag {latest} 未在 {rel} 中记录")


# ---------------------------------------------------------------------------
# 规则 18：版本号三方一致 + SemVer
# ---------------------------------------------------------------------------

def _manifest_version(ctx: "ProjectContext") -> tuple[str | None, str]:
    """读项目清单里的版本号（pyproject / setup.cfg / package.json / Cargo.toml）。"""
    if "pyproject.toml" in ctx.file_set:
        text = ctx.text("pyproject.toml")
        if text:
            version = _pyproject_version(text)
            if version:
                return version, "pyproject.toml"

    rel = None
    for name in ctx.children(""):
        low = name.lower()
        if low in ("setup.cfg", "setup.py"):
            rel = name
            break
    if rel == "setup.cfg":
        text = ctx.text(rel)
        if text:
            match = re.search(r"^\s*version\s*=\s*(\S+)", text, re.M)
            if match:
                return match.group(1).strip(), rel

    if "package.json" in ctx.file_set:
        text = ctx.text("package.json")
        if text:
            import json

            try:
                data = json.loads(text)
                raw = data.get("version")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip(), "package.json"
            except (json.JSONDecodeError, AttributeError):
                pass

    if "Cargo.toml" in ctx.file_set and tomllib is not None:
        text = ctx.text("Cargo.toml")
        if text:
            try:
                raw = (tomllib.loads(text).get("package") or {}).get("version")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip(), "Cargo.toml"
            except Exception:  # noqa: BLE001
                pass
    return None, ""


def _pyproject_version(text: str) -> str | None:
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
            project = data.get("project") or {}
            raw = project.get("version")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
            poetry = (data.get("tool") or {}).get("poetry") or {}
            raw = poetry.get("version")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        except Exception:  # noqa: BLE001
            pass
    match = re.search(r"^\s*version\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
    return match.group(1).strip() if match else None


_VERSION_FILES = ("__init__.py", "__about__.py", "__version__.py", "_version.py")
_VERSION_RE = re.compile(r"^__version__\s*(?::\s*str\s*)?=\s*[\"']([^\"']+)[\"']", re.M)


def _source_version(ctx: "ProjectContext") -> tuple[str | None, str]:
    """在源码里找 ``__version__``（优先同名的版本文件，再退到根级 .py）。"""
    candidates: list[str] = []
    for path in ctx.py_files:
        name = path.rsplit("/", 1)[-1]
        if name in _VERSION_FILES:
            candidates.append(path)
    for path in ctx.py_files:
        if path not in candidates and "/" not in path:
            candidates.append(path)

    for path in candidates[:40]:
        text = ctx.text(path)
        if text is None:
            continue
        match = _VERSION_RE.search(text)
        if match:
            return match.group(1).strip(), path
    return None, ""


def _check_version_consistency(ctx: "ProjectContext") -> CheckResult:
    """规则 18：清单 / 源码 / git tag 三处版本号是否一致且合法。"""
    manifest, manifest_rel = _manifest_version(ctx)
    source, source_rel = _source_version(ctx)

    # 没有版本声明就不必去取 tag —— 省掉一次 git 子进程（Windows 上约 100ms）
    if not manifest and not source:
        return CheckResult.skip("no-version-declared")

    tag = ctx.git.latest_version_tag()
    tag_version = tag[1:] if tag and tag.lower().startswith("v") else tag

    declared = {
        f"清单({manifest_rel})": manifest,
        f"源码({source_rel})": source,
        f"git tag({tag or '-'})": tag_version,
    }
    present = {k: v for k, v in declared.items() if v}

    if manifest and not SEMVER_RE.match(manifest):
        return CheckResult.bad(f"{manifest_rel} 的版本号 {manifest} 不符合 SemVer")

    unique = set(present.values())
    if len(unique) > 1:
        detail = " / ".join(f"{k}={v}" for k, v in present.items())
        return CheckResult.bad("版本号不一致：" + detail)

    if len(present) == 1:
        only = next(iter(present.values()))
        return CheckResult.ok() if SEMVER_RE.match(only) else CheckResult.bad(
            f"仅一处声明版本号 {only}，且不符合 SemVer")
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 20：二进制 / 大文件入库
# ---------------------------------------------------------------------------

BINARY_SUFFIXES = frozenset({
    ".exe", ".dll", ".so", ".dylib", ".pdb", ".whl", ".zip",
    ".jar", ".class", ".o", ".a", ".bin", ".msi", ".lib", ".obj",
})

LARGE_FILE_BYTES = 1 << 20  # 1 MiB


def _check_binaries(ctx: "ProjectContext") -> CheckResult:
    """规则 20：是否有二进制产物或超大文件被纳入版本控制。"""
    tracked = ctx.git.ls_files
    if not tracked:
        return CheckResult.ok()

    binaries: list[str] = []
    large: list[tuple[str, int]] = []
    for rel in tracked:
        if rel.startswith("node_modules/"):
            continue
        if _suffix(rel) in BINARY_SUFFIXES:
            binaries.append(rel)
            continue
        size = ctx.file_sizes.get(rel)
        if size and size > LARGE_FILE_BYTES:
            large.append((rel, size))

    if binaries:
        detail = ", ".join(binaries[:MAX_DETAIL_ITEMS])
        return CheckResult.bad(
            f"{len(binaries)} 个二进制文件入库：{detail}", Severity.ERROR)
    if large:
        detail = ", ".join(f"{r}({s // 1024}KB)" for r, s in large[:MAX_DETAIL_ITEMS])
        return CheckResult.bad(
            f"{len(large)} 个超过 1MB 的文件入库：{detail}", Severity.WARN)
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 21：构建产物被跟踪 / .gitignore 缺失
# ---------------------------------------------------------------------------

_ARTIFACT_RE = re.compile(
    r"(?:^|/)(?:__pycache__|node_modules|\.venv|venv|dist|build|\.pytest_cache"
    r"|\.mypy_cache|\.tox|\.ruff_cache)(?:/|$)"
    r"|\.egg-info(?:/|$)|\.py[co]$",
    re.I,
)


def _gitignore_is_empty(ctx: "ProjectContext") -> bool:
    """根 .gitignore 是否缺失或只有注释/空行。"""
    rel = None
    for name in ctx.children(""):
        if name.lower() == ".gitignore":
            rel = name
            break
    if rel is None:
        return True
    text = ctx.text(rel)
    if text is None:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return False
    return True


def _check_artifacts(ctx: "ProjectContext") -> CheckResult:
    """规则 21：构建产物是否被误纳入版本控制。"""
    tracked = [f for f in ctx.git.ls_files if _ARTIFACT_RE.search(f)]
    ignore_empty = _gitignore_is_empty(ctx)

    if tracked:
        detail = ", ".join(tracked[:MAX_DETAIL_ITEMS])
        if ignore_empty:
            return CheckResult.bad(
                f".gitignore 缺失或为空，且 {len(tracked)} 个构建产物被跟踪：{detail}",
                Severity.ERROR)
        return CheckResult.bad(
            f"{len(tracked)} 个构建产物被跟踪：{detail}", Severity.WARN)
    if ignore_empty:
        return CheckResult.bad(".gitignore 缺失或内容为空", Severity.INFO)
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则 22：敏感文件入库
# ---------------------------------------------------------------------------

_SENSITIVE_NAMES = frozenset({
    ".npmrc", ".pypirc", "credentials.json", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", "secring.gpg", "keystore.jks",
})
_SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
_ENV_EXEMPT = (".env.example", ".env.sample", ".env.template", ".env.dist", ".env.test")


def _is_sensitive(rel: str) -> bool:
    low = rel.lower()
    name = low.rsplit("/", 1)[-1]
    if name in _ENV_EXEMPT:
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _SENSITIVE_NAMES:
        return True
    if low.endswith(_SENSITIVE_SUFFIXES):
        return True
    return low.endswith(".aws/credentials")


def _check_sensitive_files(ctx: "ProjectContext") -> CheckResult:
    """规则 22：凭据类文件是否被纳入版本控制。"""
    hits = [rel for rel in ctx.git.ls_files if _is_sensitive(rel)]
    if not hits:
        return CheckResult.ok()
    detail = ", ".join(hits[:MAX_DETAIL_ITEMS])
    return CheckResult.bad(f"{len(hits)} 个敏感文件入库：{detail}")


# ---------------------------------------------------------------------------
# 规则 23：源码硬编码密钥
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS 密钥", re.compile(r"\b(?:AKIA|ASIA|A3T[A-Z0-9]|ABIA|ACCA)[A-Z2-7]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}")),
    ("GitHub 细粒度 token", re.compile(r"github_pat_[0-9A-Za-z_]{22,}")),
    ("私钥", re.compile(r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
)

_GENERIC_KEY_RE = re.compile(
    r"""(?ix)
    \b[a-z0-9_]*(?:key|api|token|secret|client|passwd|password|auth|access)[a-z0-9_]*\b
    \s*[:=]\s*
    ["']([^"'\s]{10,150})["']
    """,
)

#: 值得做密钥扫描的后缀（白名单）。用白名单而非黑名单是性能决定：
#: 仓库里签入的图片/视频常上万，逐个嗅探纯属浪费。
_SECRET_SCAN_SUFFIXES = frozenset({
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".rb", ".php", ".java", ".kt", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".lua", ".swift", ".pl",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".properties", ".xml", ".txt", ".md", ".rst", ".html", ".htm", ".sql",
    ".envrc", ".npmrc", ".pypirc", ".gitconfig",
    # 凭据类文件本身也要扫：里面往往就是私钥/证书
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".crt",
})

#: 单次密钥扫描最多读多少个文件（超出即停止，避免被巨型仓库拖死）。
_MAX_SECRET_FILES = 1500


def _suffix(rel: str) -> str:
    """取小写扩展名（含点）。比 ``Path(rel).suffix`` 快一个数量级 ——
    这条路径在大仓里会跑上万次。"""
    name = rel.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""

#: 明显是占位/示例的取值，不算泄露（AWS 官方文档示例就是 AKIA...EXAMPLE）。
_EXAMPLE_MARKERS = ("EXAMPLE", "FAKE", "DUMMY", "PLACEHOLDER", "XXXX",
                    "REDACTED", "CHANGEME", "YOUR_KEY", "MOCK")

#: 测试夹具目录：放过示例值，否则每个安全工具的自测都会自报泄漏。
_SECRET_SKIP_PREFIXES = ("tests/fixtures/", "test/fixtures/", "fixtures/",
                         "testdata/", "tests/testdata/")


def _is_placeholder(value: str) -> bool:
    """匹配到的串是否是明显的占位/示例值。"""
    upper = value.upper()
    return any(marker in upper for marker in _EXAMPLE_MARKERS)


_ENTROPY_THRESHOLD = 3.5


def shannon_entropy(text: str) -> float:
    """字符串的 Shannon 熵（bit/字符），用于识别高随机度取值。"""
    if not text:
        return 0.0
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in Counter(text).values()
    )


def _check_secrets(ctx: "ProjectContext") -> CheckResult:
    """规则 23：`git ls-files` 文本里是否有硬编码凭据。"""
    hits: list[str] = []
    scanned = 0
    for rel in ctx.git.ls_files:
        suffix = _suffix(rel)
        if suffix and suffix not in _SECRET_SCAN_SUFFIXES:
            continue
        if rel.startswith(_SECRET_SKIP_PREFIXES):
            continue
        text = ctx.text(rel)
        if text is None:
            continue
        scanned += 1

        matched = False
        for label, pattern in _SECRET_PATTERNS:
            for hit in pattern.finditer(text):
                if _is_placeholder(hit.group(0)):
                    continue
                hits.append(f"{rel}({label})")
                matched = True
                break
            if matched:
                break
        if not matched:
            for match in _GENERIC_KEY_RE.finditer(text):
                value = match.group(1)
                if _is_placeholder(value):
                    continue
                if shannon_entropy(value) >= _ENTROPY_THRESHOLD:
                    hits.append(f"{rel}(疑似硬编码密钥)")
                    break
        if len(hits) >= MAX_DETAIL_ITEMS:
            break
        if scanned >= _MAX_SECRET_FILES:
            break

    if not hits:
        return CheckResult.ok()
    return CheckResult.bad("；".join(hits))


# ---------------------------------------------------------------------------
# 规则 29：空壳仓 / 单向门面
# ---------------------------------------------------------------------------

_META_PREFIXES = ("readme", "license", "licence", "copying", "changelog")
_META_NAMES = frozenset({".gitignore", ".gitattributes", ".editorconfig", ".gitkeep"})
_SOURCE_SUFFIXES = (
    ".py", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".java", ".kt", ".c", ".cc", ".cpp", ".h", ".hpp", ".rb", ".php",
    ".cs", ".swift", ".sh", ".ps1", ".bat", ".lua", ".m", ".mm",
)
_THIN_LINES = 30
_THIN_COMMITS = 2


def _count_source_lines(ctx: "ProjectContext", paths: list[str]) -> int:
    total = 0
    for path in paths[:20]:
        text = ctx.text(path)
        if text:
            total += text.count("\n") + 1
    return total


def _check_empty_repo(ctx: "ProjectContext") -> CheckResult:
    """规则 29：纯文档仓、有源码无 README、或几行代码的空壳。"""
    tracked = ctx.git.ls_files
    if not tracked:
        return CheckResult.skip("empty-index")

    payload: list[str] = []
    for rel in tracked:
        name = rel.rsplit("/", 1)[-1].lower()
        if "/" not in rel and (name.startswith(_META_PREFIXES) or name in _META_NAMES):
            continue
        payload.append(rel)

    if not payload:
        return CheckResult.bad(
            f"纯文档仓：{len(tracked)} 个跟踪文件全部是 README/LICENSE 等元数据", Severity.ERROR)

    sources = [r for r in tracked if r.lower().endswith(_SOURCE_SUFFIXES)]
    if sources and ctx.root_startswith("readme") is None:
        return CheckResult.bad("有源码但根目录无 README", Severity.ERROR)

    # 只有源码极少时才去数提交 —— 正常仓库省掉一次 git rev-list 子进程
    if sources:
        lines = _count_source_lines(ctx, sources)
        if lines < _THIN_LINES:
            commits = ctx.git.commit_count
            if commits and commits <= _THIN_COMMITS:
                return CheckResult.bad(
                    f"源码仅 {lines} 行、提交 {commits} 次，疑似空壳仓", Severity.WARN)
    return CheckResult.ok()


# ---------------------------------------------------------------------------
# 规则表
# ---------------------------------------------------------------------------

RULES_VCS: tuple[Rule, ...] = (
    Rule(17, "docs.changelog_stale", "CHANGELOG 落后最新 tag",
         "最新语义化版本 tag 在 CHANGELOG 中检索不到",
         Severity.WARN, _check_changelog_stale, requires_git=True),
    Rule(18, "release.version_mismatch", "版本号不一致或非 SemVer",
         "清单版本 / 源码 __version__ / git describe 三处不一致，或清单版本不符合 SemVer",
         Severity.ERROR, _check_version_consistency, requires_git=True),
    Rule(20, "hygiene.binary_committed", "二进制/大文件签入",
         "git ls-files 含 .exe/.dll/.so/.whl/.zip 等，或单文件超过 1MB",
         Severity.ERROR, _check_binaries, requires_git=True),
    Rule(21, "hygiene.build_artifacts", "构建产物被跟踪",
         ".gitignore 缺失或为空；或 git ls-files 含 __pycache__/dist/build/node_modules 等",
         Severity.ERROR, _check_artifacts, requires_git=True),
    Rule(22, "security.sensitive_file", "敏感文件入库",
         "git ls-files 含 .env / id_rsa / *.pem / *.p12 / credentials.json / .npmrc 等",
         Severity.ERROR, _check_sensitive_files, requires_git=True),
    Rule(23, "security.hardcoded_secret", "源码硬编码密钥",
         "AWS/GitHub/Slack 前缀、PEM 私钥头，或键名含 key/token/secret 且取值 Shannon 熵 ≥3.5",
         Severity.ERROR, _check_secrets, requires_git=True, requires=("detect_secrets",)),
    Rule(29, "hygiene.empty_repo", "空壳仓/单向门面",
         "跟踪文件全是元数据；有源码但无 README；源码 <30 行且提交 ≤2 次",
         Severity.ERROR, _check_empty_repo, requires_git=True),
)
