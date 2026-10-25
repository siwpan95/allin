"""测试用声明式假仓库构造器。

一张 ``CASE`` 表就能描述「这个仓库该命中哪条规则」：写哪些文件、要不要
建 git、打什么 tag、期望哪条规则 fail。新增规则时只需在用例表里加一行
``expect={31: "fail"}``，不用再写一堆目录创建样板。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_GIT = shutil.which("git")
HAS_GIT = _GIT is not None

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com"}


def _git(args: list[str], cwd: Path) -> None:
    """在 ``cwd`` 执行一条 git 命令（失败即抛，便于定位测试数据问题）。"""
    assert _GIT is not None
    subprocess.run(
        [_GIT, "-C", str(cwd), *args],
        check=True, capture_output=True, env=_ENV,
        creationflags=_CREATE_NO_WINDOW,
    )


def build_repo(base: Path, spec: dict) -> Path:
    """按声明建出仓库目录并返回其路径。

    ``spec`` 字段
    -------------
    ``name``    目录名（必填）
    ``files``   ``{相对路径: 文本/bytes/None}``，``None`` 表示创建空文件
    ``dirs``    需要额外创建的空目录（如 ``alloy``）
    ``git``     ``{init: bool, commits: int, tags: [str], branch: str}``
    """
    root = base / spec["name"]
    root.mkdir(parents=True, exist_ok=True)

    for rel, content in (spec.get("files") or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            path.write_bytes(b"")
        elif isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    for rel in spec.get("dirs") or ():
        (root / rel).mkdir(parents=True, exist_ok=True)

    git_spec = spec.get("git") or {}
    if git_spec.get("init") and HAS_GIT:
        _git(["init", "-q", "-b", git_spec.get("branch", "main")], root)
        _git(["add", "-A"], root)
        for index in range(max(1, int(git_spec.get("commits", 1)))):
            if index:
                # 追加提交需要一个真实改动，否则 git commit 会拒绝
                (root / f".commit_marker_{index}").write_text(str(index), encoding="utf-8")
                _git(["add", "-A"], root)
            _git(["commit", "-q", "-m", f"commit {index + 1}"], root)
        for tag in git_spec.get("tags") or ():
            _git(["tag", tag], root)

    return root


# ---------------------------------------------------------------------------
# 公共样板
# ---------------------------------------------------------------------------

#: 一段「各方面都合格」的 CI workflow：权限收窄、action 按 SHA 固定。
CI_OK = (
    "name: CI\non: [push]\npermissions:\n  contents: read\njobs:\n  t:\n"
    "    runs-on: ubuntu-latest\n    steps:\n"
    "      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11\n"
    "      - run: pytest\n"
)

#: 一个「各方面都合格」的仓库文件集，各用例在此基础上做减法。
GOOD_FILES: dict[str, str | None] = {
    "README.md": (
        "# demo\n\n简介。\n\n"
        "## 安装\n\npip install demo\n\n"
        "## 用法\n\n```python\nimport demo\n```\n\n"
        "## 开发\n\n本地说明。\n\n"
        "## 测试\n\npytest\n\n"
        "## 许可\n\nMIT License\n"
    ),
    "LICENSE": (
        "MIT License\n\nCopyright (c) 2026 demo\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\").\n"
    ),
    "pyproject.toml": (
        "[project]\nname = \"demo\"\nversion = \"1.0.0\"\n"
        "license = {text = \"MIT\"}\nrequires-python = \">=3.11\"\n"
    ),
    "__init__.py": '__version__ = "1.0.0"\n\n\ndef add(a, b):\n    return a + b\n',
    "tests/test_a.py": "def test_a():\n    assert True\n",
    "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n\n- init\n",
    ".gitignore": "__pycache__/\n*.pyc\n",
    "SECURITY.md": (
        "# Security\n\n请发邮件到 security@example.com。\n"
        "我们在 14 days 内响应，漏洞披露流程见下文。\n"
    ),
    "CONTRIBUTING.md": "# Contributing\n\n欢迎提交 pull request，或先开 issue 讨论。\n",
    ".github/workflows/ci.yml": CI_OK,
    ".github/dependabot.yml": "version: 2\nupdates: []\n",
    ".semgrep.yml": "rules: []\n",
}


def good(**overrides: str | None) -> dict[str, str | None]:
    """基于 :data:`GOOD_FILES` 生成文件集；值为 ``None`` 表示删掉该文件。"""
    files = dict(GOOD_FILES)
    for key, value in overrides.items():
        rel = key.replace("__", ".")  # README__md -> README.md
        if value is None:
            files.pop(rel, None)
        else:
            files[rel] = value
    return files
