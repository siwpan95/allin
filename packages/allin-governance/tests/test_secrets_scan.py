"""`secrets-scan` 判据：21 条规则、熵闸、注解作用域、外部规则、退出码。

**为什么这么测**：这个子命令是随包分发的凭据防线，误报会让人关掉它、漏报会让人
以为安全。所以每条规则都要有「应命中」用例，同时用三类**反例**钉住降噪：
占位符、无数字的标识符、未登记文件里的注解。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from allin_governance.cli import _secret_scan, main  # noqa: E402

#: 走与 CLI 相同的双形态解析：安装态取包内 `_secret_scan`，源码树取 `tools/secret_scan`。
#: **不要**直接 `from allin_governance._secret_scan import ...` —— 那个映射目录
#: 只在 wheel 里存在（2026-11-24 实测，同 `_github` / `_toolkit` 的坑）。
scanner = _secret_scan()


def _fixture(joined: str) -> str:
    """把合成密钥拼起来：**源码里不出现完整密钥串**。

    两个原因，都被实测撞过：
    1. GitHub push protection 会把注释里的"像真令牌"直接拒收（2026-11-24 撞过）；
    2. 本仓 g03 也按形态判，测试文件里的完整令牌会被判红。
    运行期拼接出来的值对被测代码完全等价，只是对扫描器不可见。
    """
    return joined.replace("|", "")


#: (rule_id, 应命中的样本) —— 每条内置规则一个正例
SAMPLES = [
    ("aws-access-key", _fixture('AKIA|Q7Z2XK4MNPQRTUVW')),
    ("github-pat", _fixture('ghp_|a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8')),
    # 前缀后必须正好 82 位（59 + 下划线 + 22）；别用连串 a/b —— 会被占位词表误伤
    ("github-fine-grained", _fixture('gith|ub_pat_a1B2c3D4e5F6g7H8i9J0a1B2c3D4e5F6g7H8i9J0a1B2c3D4e5F6g7H8i9J_Ab3dEf6hIj9kLm2nOp5qR8')),
    ("gitlab-pat", _fixture('glpa|t-Ab3dEf6hIj9kLm2nOp5q')),
    ("pypi-token", _fixture('pypi|-AgEIcHlwaS5vcmca1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w3X4y5Z6a7B8c9D0')),
    ("openai-key", _fixture('sk-p|roj-a1b2c3d4e5f6g7h8i9j0k1l2T3BlbkFJZ9y8x7w6v5u4t3s2r1q0p9o8')),
    ("anthropic-key", _fixture('sk-a|nt-a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2-Ab3dEf')),
    ("slack-bot-token", _fixture('xoxb|-123456789012-Ab3dEf6hIj9kLm2nOp5qR8sT')),
    ("slack-webhook", _fixture('http|s|:/|/hooks.slack.com/services/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')),
    ("stripe-key", _fixture('sk_l|ive_a1B2c3D4e5F6g7H8i9J0k1L2')),
    ("google-api-key", _fixture('AIza|a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R')),
    ("tencent-secret-id", _fixture('AKID|a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6')),
    ("alibaba-access-key", _fixture('LTAI|a1B2c3D4e5F6g7H8')),
    ("dockerhub-pat", _fixture('dckr|_pat_a1B2c3D4e5F6g7H8i9J0k1L2m3N')),
    ("npm-token", _fixture('npm_|a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8')),
    ("sendgrid-key", _fixture('SG.a|aaaaaaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')),
    ("twilio-key", _fixture('SKa1b2c3|d4e5f6a7b8c9d0e1f2a3b4c5d6')),
    ("jwt", _fixture('eyJa|1b2c3d4e5f6g7h8.eyJa1b2c3d4e5f6g7h8i9J0k1L2m3N4.a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0')),
    ("pem-private-key", _fixture('----|-BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAMIIEowIBAAKCAQEAMIIEowIBAAKCAQEAMIIEowIBAAKCAQEAMIIEowIBAAKCAQEAMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----')),
    ("url-basic-auth", _fixture('post|gres://user:a1B2c3D4e5F6g7H8i9J0@db.internal:5432/app')),
    ("generic-assignment", _fixture('api_|key = "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"')),
]


@pytest.mark.parametrize(("rule_id", "sample"), SAMPLES)
def test_each_builtin_rule_detects_its_sample(rule_id: str, sample: str) -> None:
    hits = list(scanner._scan_text(sample, "probe.txt", scanner.BUILTIN_RULES))
    assert any(h.rule_id == rule_id for h in hits), f"{rule_id} 未命中，实际: {[h.rule_id for h in hits]}"


def test_placeholder_value_is_ignored() -> None:
    """AWS 文档里的示例键必须被占位符表挡住，否则每次扫都是噪声。"""
    hits = list(scanner._scan_text('aws_key = "AKIAIOSFODNN7EXAMPLE"', "x.py", scanner.BUILTIN_RULES))
    assert hits == []


def test_generic_requires_letters_and_digits() -> None:
    """纯标识符（无数字）不是密钥 —— 实测被 `$token = Get-CredentialValue` 误报过。"""
    hits = list(scanner._scan_text('token = "GetCredentialValueFromStore"', "x.py", scanner.BUILTIN_RULES))
    assert hits == []


def test_uuid_and_version_are_not_secrets() -> None:
    for value in ("2f1c9e4a-1b2c-4d5e-8f90-123456789abc", "1.2.3"):
        hits = list(scanner._scan_text(f'api_key = "{value}"', "x.py", scanner.BUILTIN_RULES))
        assert hits == [], value


def test_annotation_only_honoured_in_registered_file(tmp_path: Path) -> None:
    """注解的作用域：登记文件里生效，未登记文件里**不生效**（F-01 同一口径）。"""
    line = 'secret_key = "a1B2c3D4e5F6g7H8i9J0"  # gov-credentials: allow\n'
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "secret-scan-allowlist.txt").write_text("fixtures.py\n", encoding="utf-8")
    (tmp_path / "fixtures.py").write_text(line, encoding="utf-8")
    (tmp_path / "other.py").write_text(line, encoding="utf-8")

    result = scanner.scan_path(tmp_path)
    paths = {f.path for f in result.findings}
    assert "other.py" in paths, "未登记文件里的注解不得豁免"
    assert "fixtures.py" not in paths, "登记文件里的注解应生效"


def test_external_rules_are_loaded(tmp_path: Path) -> None:
    """`--rules` 吃 gitleaks 格式；这里用一个自造规则验证加载与命中。"""
    rule_file = tmp_path / "rules.toml"
    # 先赋值再写：g09 要求 `write_text(` 同行或相邻行出现 encoding，
    # 把三引号字面量塞进调用里会让 encoding 落到 3 行之外（实测被判红）。
    # 顶层必须是 [[rules]]（先写 [rules] 表再写数组表会报 Cannot overwrite a value）。
    toml_text = """[[rules]]
id = 'demo-token'
regex = 'demo_[0-9a-z]{12}'
"""
    rule_file.write_text(toml_text, encoding="utf-8")
    rules = scanner.BUILTIN_RULES + tuple(scanner.load_external_rules(rule_file))
    hits = list(scanner._scan_text("token = demo_a1b2c3d4e5f6", "x.txt", rules))
    assert any(h.rule_id == "demo-token" for h in hits)


def test_cli_json_envelope_and_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    secret = _fixture('AKIA|Q7Z2XK4MNPQRTUVW')
    # 用 chr(10) 拼换行：本文件的合成串一律不在源码里成串，换行也不走反斜杠转义
    (tmp_path / 'a.py').write_text('aws = "' + secret + '"' + chr(10), encoding='utf-8')
    assert main(["secrets-scan", str(tmp_path), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["findings"][0]["rule"] == "aws-access-key"
    assert "…" in payload["findings"][0]["secret"], "输出必须是脱敏值"


def test_cli_clean_tree_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.py").write_text("print('hello')\n", encoding="utf-8")
    assert main(["secrets-scan", str(tmp_path)]) == 0
    assert "发现 0" in capsys.readouterr().out


def test_cli_missing_path_is_env_error(tmp_path: Path) -> None:
    assert main(["secrets-scan", str(tmp_path / "nope")]) == 3
