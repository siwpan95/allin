"""可选依赖能力探测。

只用 ``importlib.util.find_spec()``，**不真正 import**：既避免拖慢启动，
也保证 PyInstaller 冻结包里缺模块时不会在导入期炸掉。

降级原则：内置实现必须自成完整（正则 / 熵计算 / tomllib），可选库只做
二次校验（例如把 ``GPL-3.0`` 规范成 ``GPL-3.0-only``）。因此装与不装，
结论口径一致，差别只在置信度。
"""

from __future__ import annotations

import importlib.util

#: 能力名 → 供文档/JSON 展示的 PyPI 包名。
PACKAGE_NAMES = {
    "license_expression": "license-expression",
    "detect_secrets": "detect-secrets",
    "markdown_it": "markdown-it-py",
    "requirements_parser": "requirements-parser",
    "packaging": "packaging",
}


def _probe(module: str) -> bool:
    """模块是否可导入（不执行 import）。"""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, AttributeError):
        return False


HAS_LICENSE_EXPRESSION = _probe("license_expression")
HAS_DETECT_SECRETS = _probe("detect_secrets")
HAS_MARKDOWN_IT = _probe("markdown_it")
# 注意：PyPI 包名是 requirements-parser，但 import 名是 requirements
HAS_REQUIREMENTS_PARSER = _probe("requirements")
HAS_PACKAGING = _probe("packaging")

#: 供 ``dump_profile()`` 与 ``--format json`` 的 ``engine.optional`` 使用。
CAPABILITIES: dict[str, bool] = {
    "license_expression": HAS_LICENSE_EXPRESSION,
    "detect_secrets": HAS_DETECT_SECRETS,
    "markdown_it": HAS_MARKDOWN_IT,
    "requirements_parser": HAS_REQUIREMENTS_PARSER,
    "packaging": HAS_PACKAGING,
}


def missing_packages() -> list[str]:
    """返回未安装的可选依赖的 PyPI 包名（供提示文案使用）。"""
    return [PACKAGE_NAMES[k] for k, ok in CAPABILITIES.items() if not ok]
