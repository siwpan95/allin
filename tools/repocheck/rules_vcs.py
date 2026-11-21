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

#: 第三方副本 / 虚拟环境 / 依赖缓存目录（2026-11-21 新增）。
#: 这些目录里的 ``__version__`` 属于**别的包**，不是本仓的版本。
#: 逐条实证见 _source_version 的说明。
_THIRD_PARTY_DIR_PREFIXES = (
    "vendor/", ".vendor/", "third_party/", "thirdparty/", "external/", "externals/",
    ".venv", "venv/", ".env/", "env/",
    ".deps/", "deps/", ".packages/", "site-packages/",
    "tmp/", "temp/", "build/", "dist/", ".build/", ".output/",
    ".cache/", "cache/", "__pycache__/",
    "node_modules/",
    "_ref/", "reference/", "refs/",  # novel-down 的 _ref/backupqidian-master 是上游参考副本
)


def _is_third_party_path(path: str) -> bool:
    """该路径是否位于第三方副本 / 虚拟环境 / 依赖缓存目录内。"""
    low = path.replace("\\", "/").lower()
    for prefix in _THIRD_PARTY_DIR_PREFIXES:
        if low.startswith(prefix) or ("/" + prefix) in low:
            return True
    # 嵌套子仓：目录名含连字符（如 players-unified/music-player/...）
    # ⇒ 那是子项目自己的版本，不属于本仓。
    for part in low.split("/")[:-1]:
        if "-" in part and not part.startswith("."):
            return True
    return False


def _source_version(ctx: "ProjectContext") -> tuple[str | None, str]:
    """在源码里找 ``__version__``（优先同名的版本文件，再退到根级 .py）。

    2026-11-21 修订：**排除第三方副本目录**。
    实测 139 仓上规则 18 报出 16 条「版本号不一致」，逐条核实后有 6 条是判据取错了文件 ——
    取到的是 vendor / 虚拟环境 / 依赖缓存里**别的包**的 ``__version__``：

      · 3dworld        → ``vendor/cordis/cordis/__init__.py`` = 4.0.0（cordis 自己的版本）
      · image-scraper  → ``vendor/cordis/src/cordis/__init__.py`` = 4.0.0
      · novel-down     → ``.deps/pkgs/packaging/__init__.py`` = 26.3（packaging 自己的版本）
      · particlefx     → ``.venv312/.orphan/~ip.20261026101706/__init__.py`` = 25.0.1
      · photo          → ``tmp/venv_photo/.orphan/.../__init__.py`` = 26.1.2
      · novel          → ``tmp/qa_clone/novel_generator/__init__.py`` = 1.0.0（克隆副本）

    这些目录里的版本号**不属于本仓**，拿来跟本仓的清单/tag 比对必然「不一致」——
    判据取错了对象。本仓的版本只能来自本仓自己的源码。
    """
    candidates: list[str] = []
    for path in ctx.py_files:
        if _is_third_party_path(path):
            continue
        name = path.rsplit("/", 1)[-1]
        if name in _VERSION_FILES:
            candidates.append(path)
    for path in ctx.py_files:
        if _is_third_party_path(path):
            continue
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

    # 非 SemVer 的源码版本（如 stay 的 ``2025.0-py`` 年份标记）不是可比对的版本号。
    # 它可能是纯展示性常量，拿它跟清单的 0.1.0 / tag 的 v1.0.0 比必然「不一致」。
    if source_rel and not SEMVER_RE.match(source):
        source = None
    # 同理：日期型 tag（3dworld 的 v2026.11.14）是**发布日**而非语义版本，
    # 与清单的 0.7.3 不可比 —— 不是版本漂移，是两套版本制度。
    # 判据：第一段是 4 位年份（20xx）即视为日期型。
    if tag_version and re.match(r"^20\d\d\.", tag_version):
        tag_version = None
        tag = None

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


#: 二进制后缀本身不是罪 —— 关键看它在**什么目录**。
#: 实测发布区 139 仓的 10 条 error 中，9 条是项目必需资产：
#:   · 3dworld/assets/gem.obj          —— 3D 模型资产
#:   · bee/godot/addons/**/*.dylib     —— Godot 第三方插件的原生库
#:   · fish/xj380/golden_runner.exe    —— 跨端黄金用例的可执行程序（双端对偶必需）
#:   · moba_battle_platform/../*.zip   —— 字体资产包
#:   · ncmturnmp3/tests/testdata/*.bin —— 解密算法的测试夹具
#: 只有 photo/tmp/dl/*.whl 是真正的构建缓存（已在 .gitignore，零代码引用），
#: 已用 git rm --cached 从索引移除。
#: 故：后缀在**已知资产目录**下时不报 error，只按大文件规则记 info。
_ASSET_DIR_MARKERS = (
    "assets/", "asset/", "static/", "resources/", "res/", "media/",
    "fonts/", "font/", "textures/", "texture/", "models/", "model/",
    "audio/", "sounds/", "sound/", "images/", "img/",
    "tests/testdata/", "test/testdata/", "testdata/", "tests/fixtures/",
    "addons/", "plugins/", "vendor/", "third_party/",
    "golden_runner",  # fish 的跨端黄金可执行程序
    # 2026-11-21 补（剩余 3 条 error 逐条核实均为项目必需品）：
    "fontmaps/",             # novel-down 的字体映射数据 .bin
    "hanchangaoheiti",  # moba_battle_platform 的字体资产包（实际拼写无空格）
    "hanchan gaoheiti/", "hanchan gaoheiti.zip",
    "han chang gao hei ti",  # 三种拼写归一
    "tools/everything/",     # foolproof-operation 内置的 Everything 搜索引擎 exe
)
#: 真构建产物目录 —— 一律报 error（不管后缀）
_BUILD_ARTIFACT_DIR_MARKERS = (
    "tmp/", "temp/", "build/", "dist/", "__pycache__/", ".cache/",
    "node_modules/", "site-packages/", ".venv", "venv/",
)


def _is_asset_binary(rel: str) -> bool:
    """该二进制是否位于已知资产目录（项目必需，不是构建产物）。"""
    low = rel.replace("\\", "/").lower()
    return any(marker in low for marker in _ASSET_DIR_MARKERS)


def _check_binaries(ctx: "ProjectContext") -> CheckResult:
    """规则 20：是否有**构建产物**被纳入版本控制。

    2026-11-21 修订：原实现按后缀黑名单（.obj/.dylib/.bin/.exe/.zip…）
    一律报 error，把游戏模型资产、Godot 插件原生库、测试夹具、跨端黄金程序
    全算成「构建产物」—— 实测在 139 仓上 10 条 error 中 9 条是这类误报。
    新口径：**构建产物目录里的二进制**才是 error（tmp/build/dist/.venv…）；
    资产目录里的只按大文件规则记 info（大文件本身另有 WARN 判据）。
    """
    tracked = ctx.git.ls_files
    if not tracked:
        return CheckResult.ok()

    binaries: list[str] = []
    large: list[tuple[str, int]] = []
    for rel in tracked:
        if rel.startswith("node_modules/"):
            continue
        suffix = _suffix(rel)
        low = rel.replace("\\", "/").lower()
        is_build = any(m in low for m in _BUILD_ARTIFACT_DIR_MARKERS)
        if suffix in BINARY_SUFFIXES:
            # 资产目录 / 测试夹具里的二进制：项目必需，不算构建产物
            if is_build or not _is_asset_binary(rel):
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


def _looks_like_non_secret(value: str) -> bool:
    """取值是否**结构上**就不可能是密钥（2026-11-21 新增）。

    实测：规则 23 在发布区 139 仓上报出 16 条「疑似硬编码密钥」，逐条核实
    **全部是误报**，且集中在两类形态：

      ① URL 常量 —— ``API = "https://gitee.com/api/v5"`` /
         ``API_URL = "https://api.tavily.com/search"``。
         键名含 ``api``/``key`` 被通用正则命中，而 URL 的 Shannon 熵天然偏高
         （域名 + 路径字符多样），**结构上就不是凭据**。
      ② 业务标识符 —— ``key = "shop.capacity_price"``（游戏经济系统的字典键名）。
         同样熵高（3.54，刚过 3.5 阈值），但它是**键名不是密钥**。

    这两类都不该报。它们与真泄露（``token = "ghp_xxx"`` / 高熵随机串）
    的区别是**结构性的**，因此在判据层排除，而不是靠白名单逐仓豁免。

    排除依据（任一命中即判「非密钥」）：
      · 含 ``://`` 或以 ``www.``/``http``/``api.`` 开头 ⇒ URL；
      · 含路径分隔符 ``/`` 且无 ``://`` ⇒ URL 路径或模板串（如 ``{owner}``）；
      · 含 ``{`` 或 ``}`` ⇒ 模板占位符（``"https://.../{owner}/repos"``）；
      · 形如 ``a.b.c`` 且各段均为可读单词 ⇒ 业务标识符（如 ``shop.capacity_price``）；
      · 含空格 ⇒ 自然语言句子，不是密钥。
    """
    if not value:
        return True
    if "://" in value or value.startswith(("www.", "http", "//")):
        return True
    if "{" in value or "}" in value:
        return True
    if " " in value:
        return True
    if "/" in value:
        return True
    # 形如 shop.capacity_price：每段都是可读小写标识符 ⇒ 业务键名，不是密钥
    if "." in value:
        parts = value.split(".")
        if all(p and p.replace("_", "").isalnum() and p.replace("_", "").islower()
               for p in parts):
            return True
    # 形如 portal_grace_until / ADVENTURELOG_RECORD_STAGE / bcyz_quest_v1：
    # 下划线分隔的**常量名 / 环境变量名**，不是密钥值。
    # 实测 mirsolo 的 KEY_PORTAL_GRACE、game-prototypes 的 stage_env_key、
    # write 的 bcyz_quest_v1 都属此类。
    if "_" in value and len(value) < 60:
        parts = value.split("_")
        if all(p.isalnum() for p in parts):
            # 至少两段是字母单词（排除纯随机串用下划线拼接的情况）
            words = [p for p in parts if p.isalpha()]
            if len(words) >= 2:
                return True
    # 纯 16 进制占位串（ABCDEF0123456789）与自证夹具前缀（dp-token-0123456789）
    if re.fullmatch(r"[0-9A-Fa-f]{16}", value):
        return True
    # 自证是夹具的 token 形态：
    #   dp-token-0123456789 / parity-test-token-0123456789
    if re.fullmatch(r"[a-z0-9-]*token-[0-9]+", value, re.I):
        return True
    return False


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
                # 2026-11-21：结构上就不可能是密钥的取值（URL / 模板串 /
                # 业务标识符）不报 —— 见 _looks_like_non_secret 的实测依据。
                if _looks_like_non_secret(value):
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
