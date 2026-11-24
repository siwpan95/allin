"""自研凭据扫描器：高精度规则 + 五层降噪（供 `allin-governance secrets-scan` 使用）。

## 为什么不直接带 gitleaks 二进制

本仓要把能力**随包装进 wheel**。gitleaks 是 Go 编译产物（单平台 22 MB），
进不了 `py3-none-any`；从源码构建又需要 Go 工具链，等于把「下载二进制」
换成「现场编译二进制」，对使用者更糟。

## 为什么不自带 222 条 gitleaks 规则

2026-11-24 实测：gitleaks 的规则集在 Python `re` 下 221/222 可编译（无 `\\p{}`、
无前瞻、无反向引用），所以「移植」在技术上成立；但移植 = 把 200+ 条长尾规则的
维护成本全继承下来，而本仓一年也用不上其中绝大多数。

故取「引擎自研 + 规则自选」：内置 21 条覆盖本仓真实会碰到的提供方；
需要长尾时用 `--rules <gitleaks 格式.toml>` 挂载外部规则（同一套引擎吃两种规则）。

## 检测链（每条都对应一类已记录的误报来源）

1. **关键词预筛**：行内没有 `key/secret/token/...` 直接跳过 —— 纯性能与降噪，
   但只对泛化规则生效；结构化规则靠"前缀特异"降噪，不吃这一层。
2. **结构化正则**：只认已知提供方的固定格式（`AKIA`+16 位、`ghp_`+36 位…），
   宁漏不误。
3. **捕获组提取**：正则命中 ≠ 密钥命中（URL 账密只取密码段）。
4. **按字符集分档的熵阈值**：hex 3.0 / alnum 3.5 / 其它 4.0 —— 单阈值会让
   base64 规则过松、hex 规则过严。
5. **占位符与形态降噪**：示例值、全小写单词、纯数字、版本号、UUID。
   另加**仓库自有注解**（`gov-credentials: allow` / `repo-hygiene: allow`）：
   与 g03、scan-secrets.sh 共用同一套词汇，一套注解三个扫描器都认。

## 明确不做

- **不做在线验证**（把密钥发给服务商 API 校验）：治理工具本身不该外泄凭据，
  且 CI 无出网时会全部降级为 unknown。信噪比靠上面五层，不靠联网。
- **不做自定义令牌的强判定**：格式未知的随机串只由泛化规则 + 熵兜底，标 `low`。
"""

from __future__ import annotations

import json
import math
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_ENV = 3

#: 与 g03_credentials.py / scan-secrets.sh 共用的行内豁免注解。
ANNOTATIONS = ("gov-credentials: allow", "repo-hygiene: allow")

#: 注解只在**登记过的夹具文件**里生效（与 F-01 安全加固同口径）：
#: 「任何文件里的注解都豁免」等于把豁免权交给被扫描内容 —— 外部贡献者只要在
#: 夹带真密钥的那行末尾加个注释就能绕过。故注解必须配合
#: `scripts/secret-scan-allowlist.txt` 的登记才对整行生效。
ANNOTATION_ALLOWLIST_REL = "scripts/secret-scan-allowlist.txt"


def load_annotation_allowlist(root: Path) -> set[str]:
    """读取登记过的夹具文件路径（POSIX 分隔符）；没有该文件则返回空集。"""
    path = root / ANNOTATION_ALLOWLIST_REL
    if not path.is_file():
        return set()
    allowed: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            allowed.add(item.replace("\\", "/"))
    return allowed


# ------------------------------------------------------------------ 熵

def shannon_entropy(text: str) -> float:
    """Shannon 熵（bits/char）。空串为 0。"""
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def charset_of(value: str) -> str:
    """粗分字符集 —— 决定用哪一档熵阈值。"""
    if re.fullmatch(r"[0-9a-fA-F]+", value):
        return "hex"
    if re.fullmatch(r"[A-Za-z0-9+/=_-]+", value):
        return "alnum"
    return "other"


ENTROPY_FLOOR = {"hex": 3.0, "alnum": 3.5, "other": 4.0}


# ------------------------------------------------------------------ 规则

@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    keywords: tuple[str, ...] = ()
    group: int = 0
    entropy_gate: bool = False
    confidence: str = "high"


def _rule(rule_id: str, pattern: str, **kw) -> Rule:
    return Rule(rule_id, re.compile(pattern), **kw)


#: 内置规则：只认固定格式（前缀 + 定长/紧区间）。新增一条必须同时加一个
#: 「应当命中」与一个「不应当命中」的用例（tests/test_secrets_scan.py）。
BUILTIN_RULES: tuple[Rule, ...] = (
    _rule("aws-access-key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    _rule("github-pat", r"\bghp_[0-9A-Za-z]{36}\b"),
    _rule("github-fine-grained", r"\bgithub_pat_[0-9A-Za-z_]{82}\b"),
    _rule("gitlab-pat", r"\bglpat-[0-9A-Za-z_-]{20}\b"),
    _rule("pypi-token", r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}\b"),
    _rule("openai-key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}\b"),
    _rule("anthropic-key", r"\bsk-ant-[A-Za-z0-9_-]{40,}\b"),
    _rule("slack-bot-token", r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    _rule("slack-webhook",
          r"https://hooks\.slack\.com/services/T[A-Z0-9]{6,}/B[A-Z0-9]{6,}/[A-Za-z0-9]{16,}"),
    _rule("stripe-key", r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{24,}\b"),
    _rule("google-api-key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    _rule("tencent-secret-id", r"\bAKID[0-9A-Za-z]{32}\b"),
    _rule("alibaba-access-key", r"\bLTAI[0-9A-Za-z]{12,20}\b"),
    _rule("dockerhub-pat", r"\bdckr_pat_[A-Za-z0-9_-]{27,}\b"),
    _rule("npm-token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _rule("sendgrid-key", r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    _rule("twilio-key", r"\bSK[0-9a-fA-F]{32}\b"),
    _rule("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    _rule("pem-private-key",
          r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----[\s\S]{64,}?-----END",
          keywords=("-----begin",)),
    _rule("url-basic-auth",
          r"\b[a-z][a-z0-9+.-]{1,15}://[^/\s:@]{1,64}:([^/\s@]{6,64})@[A-Za-z0-9.-]{3,}",
          keywords=("://",), group=1, entropy_gate=True),
    # 泛化兜底：关键词锚定 + 引号/行尾取值 + 熵闸。注意**不要**在关键词前加
    # `\b`：下划线算单词字符，`\bapi_key` 在 `my_api_key` 前不成立（业内经典坑）。
    _rule("generic-assignment",
          r"""(?ix)
          (?:api[_-]?key|apikey|secret[_-]?key|access[_-]?key|auth[_-]?token|
             access[_-]?token|api[_-]?secret|client[_-]?secret|private[_-]?key|
             passw(?:or)?d|pwd|token|secret)
          \s*[:=]\s*
          ["']?([A-Za-z0-9_\-./+=]{16,128})["']?(?=[\s;,)}\]"']|$)
          """,
          keywords=("key", "secret", "token", "passw", "pwd", "auth"),
          group=1, entropy_gate=True, confidence="low"),
)

#: 示例/占位值：命中即丢。这些是各家文档里反复出现的"假密钥"与常见占位写法。
PLACEHOLDERS = (
    "akiaiosfodnn7example", "asiaiosfodnn7example",
    "changeme", "change-me", "your-key", "your_key", "yourkey", "your-token",
    "xxxxxx", "yyyyyy", "abcdefghijklmnop", "1234567890abcdef",
    "dummy", "placeholder", "redacted", "replace-me", "insert-key",
    "example", "sample", "test-key", "testkey", "fake", "mock",
    "not-a-real", "notreal", "do-not-log", "donotlog", "fixture",
)

#: 形态上就不是密钥：纯数字、点分版本号、UUID、全小写/全大写单词。
NON_SECRET_SHAPES = (
    re.compile(r"^[0-9]+$"),
    re.compile(r"^[0-9]+(?:\.[0-9]+)+$"),
    re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    re.compile(r"^[a-z]+$"),
    re.compile(r"^[A-Z]+$"),
)


def _is_noise(value: str) -> bool:
    low = value.lower()
    if any(p in low for p in PLACEHOLDERS):
        return True
    return any(shape.match(value) for shape in NON_SECRET_SHAPES)


# ------------------------------------------------------------------ 外部规则（gitleaks 兼容）

_RE2_FIXES = ((r"\z", r"\Z"),)


def _port_regex(pattern: str) -> str:
    """把 Go RE2 写法改成 Python 可编译的等价形式。

    本仓实测（2026-11-24，gitleaks master）：规则集里 0 处 `\\p{}`、0 处前瞻、
    0 处反向引用；只有两处差异需要抹平 —— `\\z`（文本末尾）与**写在中间的** `(?i)`
    （Python 3.11+ 只接受出现在表达式开头的全局标志）。
    """
    for old, new in _RE2_FIXES:
        pattern = pattern.replace(old, new)
    return _scope_inline_flags(pattern)


def _scope_inline_flags(pattern: str) -> str:
    """把 `(?i)` 收口到「所在分组末尾」，保持 Go 的语义。"""
    while True:
        idx = pattern.find("(?i)")
        if idx < 0:
            return pattern
        depth = 0
        in_class = False
        end = len(pattern)
        i = idx + 4
        while i < len(pattern):
            ch = pattern[i]
            if ch == "\\":
                i += 2
                continue
            if in_class:
                if ch == "]":
                    in_class = False
            elif ch == "[":
                in_class = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    end = i
                    break
                depth -= 1
            i += 1
        pattern = pattern[:idx] + "(?i:" + pattern[idx + 4:end] + ")" + pattern[end:]


def load_external_rules(path: Path) -> list[Rule]:
    """加载 gitleaks 格式的规则文件（只取引擎用得到的字段）。"""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for raw in data.get("rules", []):
        if not raw.get("regex"):
            continue
        rules.append(Rule(
            rule_id=str(raw["id"]),
            pattern=re.compile(_port_regex(raw["regex"])),
            keywords=tuple(str(k).lower() for k in raw.get("keywords", [])),
            group=int(raw.get("secretGroup", 0) or 0),
            entropy_gate=raw.get("entropy") is not None,
            confidence="low" if raw.get("entropy") is not None else "high",
        ))
    return rules


# ------------------------------------------------------------------ 扫描

@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str
    line: int
    secret: str
    confidence: str = "high"

    def redacted(self) -> str:
        value = self.secret
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}…{value[-4:]}（{len(value)} 位）"

    def as_dict(self) -> dict:
        return {"rule": self.rule_id, "path": self.path, "line": self.line,
                "secret": self.redacted(), "confidence": self.confidence}


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    files: int = 0
    skipped: int = 0

    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.rule_id] = out.get(f.rule_id, 0) + 1
        return dict(sorted(out.items()))


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
             ".mypy_cache", ".pytest_cache", "site-packages"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".whl",
               ".exe", ".dll", ".so", ".dylib", ".pyc", ".woff", ".woff2", ".mp4",
               ".jar", ".class", ".tar", ".7z", ".zst"}
MAX_BYTES = 5 * 1024 * 1024


def _scan_text(text: str, rel_path: str, rules: Sequence[Rule],
               annotation_files: set[str] | None = None) -> Iterator[Finding]:
    honoured = bool(annotation_files) and rel_path in (annotation_files or set())
    multiline = [r for r in rules if "[\\s\\S" in r.pattern.pattern]
    single = [r for r in rules if r not in multiline]

    for rule in multiline:
        if rule.keywords and not any(k in text.lower() for k in rule.keywords):
            continue
        for match in rule.pattern.finditer(text):
            value = match.group(rule.group) if rule.group else match.group(0)
            if value and not _is_noise(value):
                yield Finding(rule.rule_id, rel_path,
                              text.count(chr(10), 0, match.start()) + 1, value, rule.confidence)

    for line_no, line in enumerate(text.splitlines(), 1):
        # 仓库自有注解：只在登记过的夹具文件里生效（见 ANNOTATION_ALLOWLIST_REL）
        if honoured and any(note in line for note in ANNOTATIONS):
            continue
        low = line.lower()
        for rule in single:
            if rule.keywords and not any(k in low for k in rule.keywords):
                continue
            for match in rule.pattern.finditer(line):
                value = match.group(rule.group) if rule.group else match.group(0)
                if not value or _is_noise(value):
                    continue
                if rule.entropy_gate:
                    # 真密钥几乎必然"字母 + 数字"混合；`Get-CredentialValue`、
                    # `$someVariable` 这类标识符没有数字 —— 2026-11-24 实测这条
                    # 判据把脚本里的函数调用从误报里剔掉了。
                    if not (re.search(r"[A-Za-z]", value) and re.search(r"[0-9]", value)):
                        continue
                    if shannon_entropy(value) < ENTROPY_FLOOR[charset_of(value)]:
                        continue
                yield Finding(rule.rule_id, rel_path, line_no, value, rule.confidence)


def scan_path(root: Path, rules: Sequence[Rule] | None = None,
              excludes: Sequence[str] = ()) -> ScanResult:
    active = list(rules) if rules is not None else list(BUILTIN_RULES)
    annotation_files = load_annotation_allowlist(root)
    excluded = [e.replace("\\", "/") for e in excludes if e]
    result = ScanResult()
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if excluded and any(e in rel for e in excluded):
            result.skipped += 1
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            result.skipped += 1
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            result.skipped += 1
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                result.skipped += 1
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            result.skipped += 1
            continue
        result.files += 1
        result.findings.extend(_scan_text(text, rel, active, annotation_files))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="allin-governance secrets-scan",
        description="离线凭据扫描：21 条高精度规则 + 按字符集分档的熵闸 + 仓库自有注解豁免",
    )
    parser.add_argument("path", nargs="?", default=".", help="扫描目录（默认当前目录）")
    parser.add_argument("--rules", default="", help="附加规则文件（gitleaks 格式 TOML）")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--only", default="", help="只跑这些规则（逗号分隔的 rule id）")
    parser.add_argument("--exclude", default="",
                        help="跳过路径包含这些子串的文件（逗号分隔，如 vendor/,fixtures/）")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.path)
    if not root.exists():
        print(f"ENV ERROR: 路径不存在: {root}", file=sys.stderr)
        return EXIT_ENV

    rules = list(BUILTIN_RULES)
    if args.rules:
        extra_path = Path(args.rules)
        if not extra_path.is_file():
            print(f"ENV ERROR: 规则文件不存在: {extra_path}", file=sys.stderr)
            return EXIT_ENV
        rules += load_external_rules(extra_path)
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        rules = [r for r in rules if r.rule_id in wanted]
        if not rules:
            print(f"USAGE: --only 没匹配到任何规则: {args.only}", file=sys.stderr)
            return EXIT_USAGE

    excludes = [x.strip() for x in args.exclude.split(",") if x.strip()]
    result = scan_path(root, rules, excludes)
    if args.format == "json":
        payload = {
            "ok": not result.findings,
            "root": str(root),
            "files": result.files,
            "skipped": result.skipped,
            "rules": len(rules),
            "findings": [f.as_dict() for f in result.findings],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for f in result.findings:
            print(f"{f.path}:{f.line}  [{f.confidence}] {f.rule_id}  {f.redacted()}")
        print(f"扫描 {result.files} 文件（跳过 {result.skipped}）/ 规则 {len(rules)} / "
              f"发现 {len(result.findings)}")
    return EXIT_FINDINGS if result.findings else EXIT_CLEAN
