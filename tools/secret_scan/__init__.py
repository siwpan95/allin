"""自研凭据扫描引擎（`allin-governance secrets-scan` 的实现）。

源码单一来源在仓内 `tools/secret_scan/`，打包时由 `package-dir` 映射进
`allin_governance._secret_scan`（与 `_repocheck` / `_github` 同一套纪律：
仓内只有一份源码，不复制）。
"""

from .scanner import (  # noqa: F401
    ANNOTATIONS,
    BUILTIN_RULES,
    ENTROPY_FLOOR,
    Finding,
    Rule,
    ScanResult,
    load_external_rules,
    scan_path,
    shannon_entropy,
)

__all__ = [
    "ANNOTATIONS",
    "BUILTIN_RULES",
    "ENTROPY_FLOOR",
    "Finding",
    "Rule",
    "ScanResult",
    "load_external_rules",
    "scan_path",
    "shannon_entropy",
]
