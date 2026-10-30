"""repocheck 测试套件。

两种跑法：

* ``pytest test_scanner.py``  —— 推荐，逐条覆盖 30 条规则与 CLI 语义
* ``python test_scanner.py``  —— 无 pytest 时的兜底冒烟（仅标准库）

大部分用例通过 ``ProjectContext(git_files=...)`` 注入伪造的 ``git ls-files``
名单，**不 spawn 任何子进程**；只有少数验证 git 语义的用例才建真仓库。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import report
import scanner
from rulebase import Finding, score
from scanctx import ProjectContext
from test_fixtures import CI_OK, HAS_GIT, build_repo, good

try:  # 无 pytest 时也要能 import 本文件
    import pytest

    HAS_PYTEST = True
except ModuleNotFoundError:  # pragma: no cover
    pytest = None  # type: ignore[assignment]
    HAS_PYTEST = False

#: GBK 控制台打不出 ✓ 之类的字符
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (ValueError, OSError):  # pragma: no cover
        pass


if HAS_PYTEST:
    skip_if_no_git = pytest.mark.skipif(not HAS_GIT, reason="需要 git")
else:  # pragma: no cover
    def skip_if_no_git(func):
        return func


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def run_on(tmp_path: Path, files: dict, *, dirs=(), git_files=None,
           name: str = "proj", dotgit: bool = True):
    """造文件树（不 init git）并用注入的跟踪名单跑全部规则。"""
    root = build_repo(tmp_path, {"name": name, "files": files, "dirs": dirs})
    if dotgit:
        (root / ".git").mkdir(exist_ok=True)
    if git_files is None:
        git_files = sorted(files)
    ctx = ProjectContext(root, scanner.DEFAULT_EXCLUDE, git_files=tuple(git_files))
    from rulebase import run_rules

    return run_rules(ctx, scanner.RULES)


def status_map(run) -> dict[int, str]:
    """``{规则 id: pass/fail/skip/error}``。"""
    out = {f.id: f.status for f in run.findings}
    out.update({s["id"]: "skip" for s in run.skipped})
    out.update({e["id"]: "error" for e in run.errors})
    return out


def details(run) -> dict[int, str]:
    return {f.id: f.detail for f in run.findings}


# ---------------------------------------------------------------------------
# 项目发现
# ---------------------------------------------------------------------------

def test_discover_projects(tmp_path):
    base = tmp_path / "root"
    (base / "with_git" / ".git").mkdir(parents=True)
    (base / "with_marker").mkdir()
    (base / "with_marker" / "package.json").write_text("{}", encoding="utf-8")
    (base / "with_py" / "src").mkdir(parents=True)
    (base / "with_py" / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (base / "notes").mkdir()
    (base / "notes" / "todo.txt").write_text("x", encoding="utf-8")
    (base / "node_modules" / "pkg").mkdir(parents=True)
    (base / "node_modules" / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")

    found = [Path(p).name for p in scanner.discover_projects(base)]
    assert found == ["with_git", "with_marker", "with_py"]


def test_discover_depth(tmp_path):
    base = tmp_path / "root"
    deep = base / "deep" / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "x.py").write_text("x = 1\n", encoding="utf-8")

    assert scanner.discover_projects(base, max_py_depth=2) == []
    assert [Path(p).name for p in scanner.discover_projects(base, max_py_depth=4)] == ["deep"]


# ---------------------------------------------------------------------------
# 规则 1-8：核心
# ---------------------------------------------------------------------------

def test_good_repo_passes_core_rules(tmp_path):
    st = status_map(run_on(tmp_path, good()))
    for rule_id in (1, 2, 3, 4, 5, 6, 7, 8):
        assert st[rule_id] == "pass", f"规则 {rule_id} 应为 pass，实际 {st[rule_id]}"


def test_missing_basics(tmp_path):
    files = {k: v for k, v in good().items()
             if k not in ("README.md", "LICENSE", "pyproject.toml")}
    files["main.py"] = "import os\n"
    st = status_map(run_on(tmp_path, files))
    assert st[2] == "fail"   # 无 README
    assert st[4] == "fail"   # 无依赖声明
    assert st[5] == "fail"   # 无 LICENSE


def test_no_tests(tmp_path):
    files = {k: v for k, v in good().items() if not k.startswith("tests/")}
    st = status_map(run_on(tmp_path, files))
    assert st[3] == "fail"


def test_nested_workspace_test_dir_recognized(tmp_path):
    """2026-10-30 扩口：嵌套 test/ 目录（monorepo workspace）应被规则 3 认可。"""
    files = {k: v for k, v in good().items() if not k.startswith("tests/")}
    files["packages/core/test/helper.py"] = "x = 1\n"
    st = status_map(run_on(tmp_path, files))
    assert st[3] == "pass", f"嵌套 test/ 目录应使规则 3 通过，实际 {st[3]}"


def test_nested_js_test_file_recognized(tmp_path):
    """2026-10-30 扩口：JS/TS 惯例 *.test.mjs / *.spec.js（任意层级）应被认可。"""
    files = {k: v for k, v in good().items() if not k.startswith("tests/")}
    files["apps/cli/test/smoke.test.mjs"] = 'import { test } from "node:test";\n'
    files["lib/util.spec.js"] = "// spec\n"
    st = status_map(run_on(tmp_path, files))
    assert st[3] == "pass", f"*.test.mjs / *.spec.js 应使规则 3 通过，实际 {st[3]}"


def test_lookalike_dirs_do_not_satisfy_rule_3(tmp_path):
    """形近目录不误放行：contest/ 与 tests_helper/ 不是测试目录。"""
    files = {k: v for k, v in good().items() if not k.startswith("tests/")}
    files["contest/foo.py"] = "x = 1\n"
    files["tests_helper/bar.py"] = "x = 1\n"
    st = status_map(run_on(tmp_path, files))
    assert st[3] == "fail", "contest/ / tests_helper/ 不应被当作测试目录"


def test_broken_import(tmp_path):
    files = good()
    files["app.py"] = "import totally_missing_mod_xyz\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[6] == "fail"
    assert "totally_missing_mod_xyz" in details(run)[6]


def test_package_self_import_is_not_broken(tmp_path):
    """项目根本身是包时（根有 __init__.py），`from <目录名> import x` 不该误报。"""
    files = good()
    files["tests/test_b.py"] = "from proj import add\n\n\ndef test_b():\n    assert add(1, 1) == 2\n"
    st = status_map(run_on(tmp_path, files))
    assert st[6] == "pass"


def test_stale_repo_path(tmp_path):
    files = good()
    files["start.bat"] = "cd D:\\allin\\tools\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[7] == "fail"
    assert "start.bat" in details(run)[7]


def test_inline_engine_without_patch(tmp_path):
    files = good()
    run = run_on(tmp_path, files, dirs=("alloy",))
    assert status_map(run)[8] == "fail"

    files2 = dict(files)
    files2["engine.patch.yaml"] = "patches: []\n"
    run2 = run_on(tmp_path, files2, dirs=("alloy",), name="proj2")
    assert status_map(run2)[8] == "pass"


# ---------------------------------------------------------------------------
# 规则 9-16：文档类
# ---------------------------------------------------------------------------

def test_license_unrecognized(tmp_path):
    files = good()
    files["LICENSE"] = "保留所有权利。All rights reserved.\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[9] == "fail"


def test_license_inconsistent(tmp_path):
    files = good()
    files["pyproject.toml"] = (
        '[project]\nname = "demo"\nversion = "1.0.0"\nlicense = {text = "Apache-2.0"}\n')
    run = run_on(tmp_path, files)
    assert status_map(run)[10] == "fail"
    assert "不一致" in details(run)[10]


def test_license_missing_source(tmp_path):
    files = good()
    files["pyproject.toml"] = '[project]\nname = "demo"\nversion = "1.0.0"\n'
    run = run_on(tmp_path, files)
    assert status_map(run)[10] == "fail"
    assert "缺少声明来源" in details(run)[10]


def test_readme_structure_missing_sections(tmp_path):
    files = good()
    files["README.md"] = "# demo\n\n只有一句话。\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[11] == "fail"


def test_readme_dead_link(tmp_path):
    files = good()
    files["README.md"] = good()["README.md"] + "\n详见 [配置](docs/config.md)。\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[12] == "fail"
    assert "docs/config.md" in details(run)[12]


def test_readme_external_link_is_fine(tmp_path):
    files = good()
    files["README.md"] = good()["README.md"] + "\n见 [官网](https://example.com/x)。\n"
    st = status_map(run_on(tmp_path, files))
    assert st[12] == "pass"


def test_security_thin_content(tmp_path):
    files = good()
    files["SECURITY.md"] = "无\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[14] == "fail"


def test_security_in_github_dir(tmp_path):
    files = good()
    files.pop("SECURITY.md")
    files[".github/SECURITY.md"] = good()["SECURITY.md"]
    st = status_map(run_on(tmp_path, files))
    assert st[13] == "pass"


def test_changelog_bad_format(tmp_path):
    files = good()
    files["CHANGELOG.md"] = "# Changes\n\n随便写的。\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[16] == "fail"


# ---------------------------------------------------------------------------
# 规则 17-23 / 29：git 类（多数用注入名单，不 spawn）
# ---------------------------------------------------------------------------

def test_binary_committed(tmp_path):
    files = good()
    run = run_on(tmp_path, files, git_files=sorted(files) + ["tool.exe"])
    (Path(tmp_path) / "proj" / "tool.exe").write_bytes(b"\x00\x01")
    st = status_map(run_on(tmp_path, files, git_files=sorted(files) + ["tool.exe"],
                           name="proj2"))
    assert st[20] == "fail"


def test_build_artifacts_tracked(tmp_path):
    files = good()
    run = run_on(tmp_path, files, git_files=sorted(files) + ["__pycache__/a.cpython-314.pyc"])
    assert status_map(run)[21] == "fail"


def test_gitignore_missing_is_info(tmp_path):
    files = good()
    files.pop(".gitignore")
    run = run_on(tmp_path, files)
    assert status_map(run)[21] == "fail"
    finding = next(f for f in run.findings if f.id == 21)
    assert finding.severity == "info"


def test_sensitive_file(tmp_path):
    files = good()
    files[".env"] = "TOKEN=abc\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[22] == "fail"


def test_env_example_is_exempt(tmp_path):
    files = good()
    files[".env.example"] = "TOKEN=\n"
    st = status_map(run_on(tmp_path, files))
    assert st[22] == "pass"


#: 假 AWS 密钥**运行时拼接**构造 —— 本文件正是被 repocheck 自检扫描的对象，
#: 写成完整字面量会让工具自己报自己「源码硬编码密钥」。
_FAKE_AWS_KEY = "AKIA" + "QWERTYUIOPASDFGH"


def test_hardcoded_secret(tmp_path):
    files = good()
    # 刻意不用 AKIA...EXAMPLE 那类官方示例值 —— 它们会被当成占位符放过
    files["config.py"] = f'AWS_KEY = "{_FAKE_AWS_KEY}"\n'
    run = run_on(tmp_path, files)
    assert status_map(run)[23] == "fail"


def test_placeholder_secret_is_ignored(tmp_path):
    """文档/测试里常见的示例密钥不该被当成泄露。"""
    files = good()
    files["docs_sample.py"] = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
    st = status_map(run_on(tmp_path, files))
    assert st[23] == "pass"


def test_private_key_header(tmp_path):
    files = good()
    # 同样拼接构造：完整 PEM 头字面量会让本文件自报「私钥入库」
    fake_pem = "-----BEGIN RSA" + " PRIVATE KEY-----"
    files["id.pem"] = f"{fake_pem}\nabc\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[23] == "fail"


def test_empty_repo(tmp_path):
    files = {"README.md": good()["README.md"], "LICENSE": good()["LICENSE"]}
    run = run_on(tmp_path, files)
    assert status_map(run)[29] == "fail"
    assert "纯文档仓" in details(run)[29]


# ---------------------------------------------------------------------------
# 规则 19 / 24-28：CI 类
# ---------------------------------------------------------------------------

def test_ci_present(tmp_path):
    files = good()
    files[".github/workflows/ci.yml"] = CI_OK
    st = status_map(run_on(tmp_path, files))
    assert st[19] == "pass"
    assert st[25] == "pass"
    assert st[26] == "pass"


def test_ci_missing(tmp_path):
    files = {k: v for k, v in good().items() if not k.startswith(".github/")}
    run = run_on(tmp_path, files)
    assert status_map(run)[19] == "fail"
    assert status_map(run)[25] == "skip"


def test_dangerous_workflow_pr_target(tmp_path):
    files = good()
    files[".github/workflows/ci.yml"] = (
        "name: CI\non: pull_request_target\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
        "        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n")
    run = run_on(tmp_path, files)
    assert status_map(run)[24] == "fail"


def test_dangerous_workflow_script_injection(tmp_path):
    files = good()
    files[".github/workflows/ci.yml"] = (
        "name: CI\non: [issues]\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo \"${{ github.event.issue.title }}\"\n")
    run = run_on(tmp_path, files)
    assert status_map(run)[24] == "fail"


def test_token_permissions_write_all(tmp_path):
    files = good()
    files[".github/workflows/ci.yml"] = (
        "name: CI\non: [push]\npermissions: write-all\njobs:\n  t:\n"
        "    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
    run = run_on(tmp_path, files)
    assert status_map(run)[25] == "fail"


def test_unpinned_action(tmp_path):
    files = good()
    files[".github/workflows/ci.yml"] = (
        "name: CI\non: [push]\npermissions:\n  contents: read\njobs:\n  t:\n"
        "    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n")
    run = run_on(tmp_path, files)
    assert status_map(run)[26] == "fail"


def test_unpinned_requirements(tmp_path):
    files = good()
    files["requirements.txt"] = "requests>=2.0\nflask==3.0.0\n"
    run = run_on(tmp_path, files)
    finding = next(f for f in run.findings if f.id == 26)
    assert finding.status == "fail"
    assert "requests>=2.0" in finding.detail


def test_dependabot_and_sast(tmp_path):
    files = good()
    files[".github/dependabot.yml"] = "version: 2\n"
    files[".semgrep.yml"] = "rules: []\n"
    st = status_map(run_on(tmp_path, files))
    assert st[27] == "pass"
    assert st[28] == "pass"


# ---------------------------------------------------------------------------
# 规则 30
# ---------------------------------------------------------------------------

def test_bad_directory_name(tmp_path):
    files = good()
    files["my-tool/helper.py"] = "x = 1\n"
    run = run_on(tmp_path, files)
    assert status_map(run)[30] == "fail"
    assert "my-tool" in details(run)[30]


def test_dot_directory_is_ignored(tmp_path):
    files = good()
    files[".github/scripts/build.py"] = "x = 1\n"
    st = status_map(run_on(tmp_path, files))
    assert st[30] == "pass"


# ---------------------------------------------------------------------------
# 评分
# ---------------------------------------------------------------------------

def test_score_bounds():
    all_pass = [Finding(1, "k", "l", "error", True, "pass") for _ in range(3)]
    none_pass = [Finding(1, "k", "l", "error", False, "fail") for _ in range(3)]
    assert score(all_pass) == (10.0, 1.0)
    assert score(none_pass) == (0.0, 0.0)


def test_score_cap_applies():
    findings = [
        Finding(1, "k", "l", "error", True, "pass"),
        Finding(2, "k", "l", "info", False, "fail"),
    ]
    raw, _ = score(findings, cap=10.0)
    capped, _ = score(findings, cap=6.0)
    assert capped == min(raw, 6.0)


def test_no_git_caps_score(tmp_path):
    root = build_repo(tmp_path, {"name": "nogit", "files": good()})
    result = scanner.check_project(root)
    assert result["score"] <= 6.0
    skipped_ids = {s["id"] for s in result["skipped"]}
    assert {17, 18, 20, 21, 22, 23, 29} <= skipped_ids
    assert result["metrics"]["has_git"] is False


def test_skipped_not_in_denominator():
    """跳过项不计入分母：全通过时仍是 10.0，而不是被稀释。"""
    findings = [Finding(1, "k", "l", "error", True, "pass")]
    assert score(findings)[0] == 10.0


# ---------------------------------------------------------------------------
# 结果结构 / 自省
# ---------------------------------------------------------------------------

def test_result_structure(tmp_path):
    root = build_repo(tmp_path, {"name": "shape", "files": good()})
    result = scanner.check_project(root)
    for key in ("name", "path", "issues", "findings", "score", "pass_rate",
                "severity_counts", "skipped", "rule_errors", "metrics"):
        assert key in result
    finding = result["findings"][0]
    assert set(finding) == {"id", "key", "label", "severity", "passed",
                            "status", "detail", "degraded"}
    # issues 只收 error / warn
    assert all(not f["passed"] for f in result["findings"] if f["label"] in result["issues"])


def test_dump_profile_compat():
    profile = scanner.dump_profile()
    assert profile["schema"] == 2
    assert profile["version"] == scanner.__version__
    assert len(profile["rules"]) == 30
    assert [r["id"] for r in profile["rules"]] == list(range(1, 31))
    for rule in profile["rules"]:
        # agent 依赖前三个键及其顺序
        assert list(rule)[:3] == ["id", "label", "criteria"]
        assert rule["severity"] in ("error", "warn", "info")


def test_rule_ids_are_unique():
    ids = [rule.id for rule in scanner.RULES]
    keys = [rule.key for rule in scanner.RULES]
    assert len(set(ids)) == len(ids)
    assert len(set(keys)) == len(keys)


# ---------------------------------------------------------------------------
# 退出码
# ---------------------------------------------------------------------------

def _results(severity: str, passed: bool, score_value: float = 7.5) -> list[dict]:
    return [{
        "score": score_value,
        "findings": [{"id": 1, "severity": severity, "passed": passed}],
    }]


def test_fail_on_none():
    assert scanner.evaluate_fail_on(_results("error", False), "none") == 0


def test_fail_on_any():
    assert scanner.evaluate_fail_on(_results("info", False), "any") == 1
    assert scanner.evaluate_fail_on(_results("info", True), "any") == 0


def test_fail_on_error_ignores_warn():
    assert scanner.evaluate_fail_on(_results("warn", False), "error") == 0
    assert scanner.evaluate_fail_on(_results("error", False), "error") == 1


def test_fail_on_warn():
    assert scanner.evaluate_fail_on(_results("warn", False), "warn") == 1
    assert scanner.evaluate_fail_on(_results("info", False), "warn") == 0


def test_fail_on_score():
    assert scanner.evaluate_fail_on(_results("info", True, 7.5), "score:7.0") == 0
    assert scanner.evaluate_fail_on(_results("info", True, 7.5), "score:8.0") == 1


def test_fail_on_invalid_raises():
    try:
        scanner.evaluate_fail_on([], "bogus")
    except ValueError:
        return
    raise AssertionError("非法 --fail-on 应抛 ValueError")


# ---------------------------------------------------------------------------
# 编码与报告
# ---------------------------------------------------------------------------

def test_gbk_content(tmp_path):
    files = {"README.md": "# 标题\n\n## 安装\n装一下\n".encode("gbk"), "__init__.py": "x = 1\n"}
    root = build_repo(tmp_path, {"name": "gbk", "files": files})
    ctx = ProjectContext(root, scanner.DEFAULT_EXCLUDE)
    assert "标题" in (ctx.text("README.md") or "")


def test_chinese_path(tmp_path):
    files = good()
    files["文档/说明.md"] = "# 说明\n"
    files["pkg/工具.py"] = "x = 1\n"
    st = status_map(run_on(tmp_path, files))
    # 中文目录名不是合法标识符 —— 规则 30 会报，但不应影响其他规则
    assert st[1] == "pass"
    assert st[2] == "pass"


def test_render_csv_is_consistent(tmp_path):
    root = build_repo(tmp_path, {"name": "csv", "files": good()})
    result = scanner.check_project(root)
    text = report.render_csv([result])
    header = text.splitlines()[0]
    assert "健康分" in header and "问题数" in header


def test_summarize_and_payload(tmp_path):
    root = build_repo(tmp_path, {"name": "sum", "files": good()})
    results = [scanner.check_project(root)]
    summary = report.summarize(results)
    assert summary["projects"] == 1
    assert 0.0 <= summary["score_mean"] <= 10.0
    payload = report.to_payload(results, root=str(root), version=scanner.__version__)
    assert payload["schema"] == 2
    assert payload["summary"]["projects"] == 1
    assert payload["projects"][0]["findings"]


# ---------------------------------------------------------------------------
# 真 git 仓库：验证 tag / 版本 / 提交次数语义
# ---------------------------------------------------------------------------

@skip_if_no_git
def test_real_repo_all_green(tmp_path):
    root = build_repo(tmp_path, {
        "name": "realrepo", "files": good(),
        "git": {"init": True, "commits": 3, "tags": ["v1.0.0"]},
    })
    result = scanner.check_project(root)
    by_id = {f["id"]: f for f in result["findings"]}
    assert by_id[17]["status"] == "pass"   # CHANGELOG 有 1.0.0
    assert by_id[18]["status"] == "pass"   # 三处一致
    assert by_id[29]["status"] == "pass"   # 提交 3 次，不算空壳
    assert result["score"] >= 9.0


@skip_if_no_git
def test_real_repo_version_mismatch(tmp_path):
    root = build_repo(tmp_path, {
        "name": "mismatch", "files": good(),
        "git": {"init": True, "commits": 3, "tags": ["v9.9.9"]},
    })
    result = scanner.check_project(root)
    by_id = {f["id"]: f for f in result["findings"]}
    assert by_id[18]["status"] == "fail"
    assert "9.9.9" in by_id[18]["detail"]


@skip_if_no_git
def test_real_repo_changelog_stale(tmp_path):
    files = good()
    files["CHANGELOG.md"] = "# Changelog\n\n## [Unreleased]\n\n## [0.9.0] - 2025-01-01\n"
    root = build_repo(tmp_path, {
        "name": "stale", "files": files,
        "git": {"init": True, "commits": 3, "tags": ["v1.0.0"]},
    })
    result = scanner.check_project(root)
    by_id = {f["id"]: f for f in result["findings"]}
    assert by_id[17]["status"] == "fail"


# ---------------------------------------------------------------------------
# 无 pytest 兜底
# ---------------------------------------------------------------------------

def _smoke() -> int:
    """无 pytest 时的最小自检，只用标准库。"""
    base = Path(tempfile.mkdtemp(prefix="repocheck_smoke_"))
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    try:
        good_root = build_repo(base, {"name": "good", "files": good()})
        (good_root / ".git").mkdir()
        bad_root = build_repo(base, {"name": "bad", "files": {
            "main.py": "import totally_missing_mod_xyz\n"}})

        found = [Path(p).name for p in scanner.discover_projects(base)]
        check(found == ["bad", "good"], f"项目发现异常：{found}")

        good_result = scanner.check_project(good_root)
        check(good_result["metrics"]["issues_count"] == 0,
              f"健康项目不该有 error/warn 级问题：{good_result['issues']}")

        bad_result = scanner.check_project(bad_root)
        check(any("README" in issue for issue in bad_result["issues"]), "应报无 README")
        check(any("import" in issue for issue in bad_result["issues"]), "应报 import 断裂")
        check(bad_result["score"] <= 6.0, f"无 git 应压到 6.0，实际 {bad_result['score']}")

        profile = scanner.dump_profile()
        check(len(profile["rules"]) == 30, f"规则数应为 30，实际 {len(profile['rules'])}")
        check(list(profile["rules"][0])[:3] == ["id", "label", "criteria"],
              "dump_profile 前三个键必须保持 id/label/criteria")

        check(scanner.evaluate_fail_on([], "none") == 0, "fail-on none 应返回 0")
        check(scanner.evaluate_fail_on(
            [{"score": 3.0, "findings": [{"id": 1, "severity": "error", "passed": False}]}],
            "error") == 1, "fail-on error 应返回 1")

        text = report.render_text([good_result, bad_result], root=str(base))
        check("健康分" in text, "文本报告应包含健康分")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    if failures:
        print(f"冒烟失败 {len(failures)} 项：")
        for item in failures:
            print("  -", item)
        return 1
    print("冒烟通过：项目发现 / 核心规则 / 评分上限 / 自省 / 退出码 / 报告渲染")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_smoke())
