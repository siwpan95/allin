"""`allin_governance.init` 的回归测试。

**测什么、为什么这样测**

`init` 是「把 allin 的治理机制交付给一个陌生仓」的唯一入口，它一旦出错，
用户拿到的不是产品而是一堆红。所以这里只测**会让人当场卡住的那些边界**：

1. 生成的注册表**只含实测通过的那批门禁** —— 多一道就是给用户塞无解的题；
2. 生成物自洽：`RULES.md` 必须收录每个注册门禁（否则 `g00-meta` 直接红）、
   `GENERATED.json` 的 sha256 必须与磁盘一致（否则「快照可核对」是空话）；
3. **二次 `--force` 必须零改动** —— 否则「升级」与「什么都没变」在 git 里长得一样；
4. `--dry-run` 一个字都不许落盘；
5. **用户内容永不被覆盖**（README / LICENSE / docs/INDEX.md）——
   `--force` 的语义是升级套装，不是替人重写文档；
6. 已有 `package.json` / `.gitignore` 时**合并**而不是取代。

不测「跑完门禁是不是绿的」：那需要 Node，属于 CI 的端到端步骤
（`.github/workflows/gates.yml` 的 `scaffold` job），放这里只会让单测依赖 Node。

跑法：``python -m pytest packages/allin-governance -q``
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from allin_governance import __version__  # noqa: E402
from allin_governance import init as init_module  # noqa: E402
from allin_governance.init import GATE_IDS  # noqa: E402


def _run(target: Path, *args: str) -> int:
    return init_module.main([str(target), *args])


def test_registry_holds_exactly_the_shipped_gates(tmp_path: Path) -> None:
    """注册表 = GATE_IDS，不多不少。

    多一道：用户会看到他改不动的红（那些门禁判的是 allin 自己的资产）；
    少一道：产品少了一个承诺过的判据。两种情况都必须在单测里拦住。
    """
    assert _run(tmp_path) == 0
    payload = json.loads(
        (tmp_path / "tools/gate/governance/registry.json").read_text(encoding="utf-8")
    )
    assert [entry["id"] for entry in payload["gates"]] == list(GATE_IDS)


def test_rules_md_documents_every_registered_gate(tmp_path: Path) -> None:
    """`g00-meta` 的判据：注册了却不在 RULES.md 里出现 ⇒ 红。

    生成器必须自己先满足这条，否则用户 `init` 完第一件事就是修门禁。
    """
    assert _run(tmp_path) == 0
    rules = (tmp_path / "tools/gate/governance/RULES.md").read_text(encoding="utf-8")
    for gate_id in GATE_IDS:
        assert gate_id in rules


def test_manifest_hashes_match_the_files_on_disk(tmp_path: Path) -> None:
    """`GENERATED.json` 是「快照可核对」的唯一依据，哈希必须对得上磁盘。"""
    assert _run(tmp_path) == 0
    manifest = json.loads(
        (tmp_path / "tools/gate/governance/GENERATED.json").read_text(encoding="utf-8")
    )
    assert manifest["version"] == __version__
    assert set(manifest["gates"]) == set(GATE_IDS)
    assert manifest["files"], "清单里至少要有一个文件"
    for relative, expected in manifest["files"].items():
        digest = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        assert expected == f"sha256:{digest}", relative


def test_second_force_run_changes_nothing(tmp_path: Path) -> None:
    """幂等：`--force` 重跑不得改动任何一个字节。

    没有这条，升级套装时真正需要复核的覆盖会被一堆「零 diff 的已修改」淹掉。
    """
    assert _run(tmp_path) == 0
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert _run(tmp_path, "--force") == 0
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert before == after


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    assert _run(tmp_path, "--dry-run") == 0
    assert list(tmp_path.iterdir()) == []


def test_user_content_is_never_overwritten(tmp_path: Path) -> None:
    """`--force` 只升级套装；用户写的 README / LICENSE / 索引不属于套装。"""
    (tmp_path / "README.md").write_text("# 我自己的仓\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("我自己选的许可\n", encoding="utf-8")
    assert _run(tmp_path) == 0
    (tmp_path / "docs/INDEX.md").write_text("# 我自己的索引\n", encoding="utf-8")

    assert _run(tmp_path, "--force") == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# 我自己的仓\n"
    assert (tmp_path / "LICENSE").read_text(encoding="utf-8") == "我自己选的许可\n"
    assert (tmp_path / "docs/INDEX.md").read_text(encoding="utf-8") == "# 我自己的索引\n"


def test_existing_package_json_and_gitignore_are_merged(tmp_path: Path) -> None:
    """合并而不是取代：别人的 scripts 与忽略规则不许丢。"""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "mine", "version": "1.2.3", "scripts": {"test": "echo hi"}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    assert _run(tmp_path) == 0

    payload = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert payload["version"] == "1.2.3"
    assert payload["scripts"]["test"] == "echo hi"
    assert "run.ts" in payload["scripts"]["check:governance"]

    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "node_modules/" in ignore
    for fragment in init_module.IGNORE_FRAGMENTS:
        assert fragment in ignore, fragment


def test_no_git_flag_leaves_no_repository(tmp_path: Path) -> None:
    """`--no-git` 不得偷偷建仓 —— 有人是故意把它放进已有仓的子目录的。"""
    assert _run(tmp_path, "--no-git") == 0
    assert not (tmp_path / ".git").exists()


@pytest.mark.parametrize("gate_id", GATE_IDS)
def test_every_shipped_gate_script_reaches_the_target(tmp_path: Path, gate_id: str) -> None:
    """每道注册门禁的脚本都必须真的落在目标仓里。

    `g00-meta` 的第一条判据就是「注册表不是愿望清单」—— 生成器要是漏拷一个脚本，
    用户会拿到一条指向不存在文件的红。
    """
    assert _run(tmp_path) == 0
    script = tmp_path / f"tools/gate/governance/gates/{gate_id.replace('-', '_')}.py"
    assert script.is_file(), script


def test_survives_a_cp1252_console(tmp_path: Path) -> None:
    """回归：Windows 的 cp1252 控制台上，中文输出不得让命令失败。

    2026-10-31 真实 CI 事故：`init` 在 `windows-latest` 上抛
    `UnicodeEncodeError: 'charmap' codec can't encode`，文件都已经写好了，
    命令却以 exit 1 收场 —— 用户看到失败、磁盘上是成功，这是最坏的一种信号。

    用子进程 + `PYTHONIOENCODING=cp1252` 复现那个环境，而不是 mock：mock 掉
    `sys.stdout` 测不到「真实解释器怎么处理编码」，而这正是事故的发生点。
    """
    env = {
        **os.environ,
        "PYTHONIOENCODING": "cp1252",
        "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"),
    }
    for args in (["--help"], []):
        completed = subprocess.run(
            [sys.executable, "-m", "allin_governance", "init", str(tmp_path), *args],
            capture_output=True, text=True, env=env, check=False,
            encoding="utf-8", errors="replace",
        )
        assert completed.returncode == 0, (args, completed.stderr[-600:])
    assert (tmp_path / "tools/gate/governance/run.ts").is_file()


def test_with_exceptions_adds_g18_and_ledger(tmp_path: Path) -> None:
    """`--with-exceptions` 必须把 g18 加进注册表、生成台账、并写进 RULES.md。

    三处缺一，`g00-meta` 立刻红：注册了但没写进 RULES.md = 规则不可溯；
    注册了但脚本没拷 = 注册表成了愿望清单。所以这条测的是「三处一起动」。
    """
    assert _run(tmp_path, "--with-exceptions") == 0

    payload = json.loads(
        (tmp_path / "tools/gate/governance/registry.json").read_text(encoding="utf-8")
    )
    ids = [entry["id"] for entry in payload["gates"]]
    assert "g18-exceptions" in ids
    assert len(ids) == len(GATE_IDS) + 1

    assert (tmp_path / "tools/gate/governance/gates/g18_exceptions.py").is_file()
    ledger = (tmp_path / "tools/gate/governance/exceptions.yml").read_text(encoding="utf-8")
    assert "exceptions: []" in ledger

    rules = (tmp_path / "tools/gate/governance/RULES.md").read_text(encoding="utf-8")
    assert "g18-exceptions" in rules


def test_without_flag_g18_stays_out(tmp_path: Path) -> None:
    """默认不出厂 g18：它需要 PyYAML，与本包「零运行时依赖」的承诺冲突。"""
    assert _run(tmp_path) == 0
    payload = json.loads(
        (tmp_path / "tools/gate/governance/registry.json").read_text(encoding="utf-8")
    )
    assert "g18-exceptions" not in [entry["id"] for entry in payload["gates"]]
    assert not (tmp_path / "tools/gate/governance/exceptions.yml").exists()


def test_verify_reports_clean_snapshot(tmp_path: Path) -> None:
    assert _run(tmp_path) == 0
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 0


def test_verify_detects_tampering_and_missing(tmp_path: Path) -> None:
    """改动与缺失都必须退出 1 —— 这是「快照可核对」的唯一硬证据。"""
    assert _run(tmp_path) == 0
    gate = tmp_path / "tools/gate/governance/gates/g05_hygiene.py"
    gate.write_text(gate.read_text(encoding="utf-8") + "\n# hand edit\n", encoding="utf-8")
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 1

    assert _run(tmp_path, "--force") == 0  # 恢复快照
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 0
    (tmp_path / "tools/gate/governance/run.ts").unlink()
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 1


def test_verify_without_manifest_is_an_env_error(tmp_path: Path) -> None:
    """没有清单 ≠ 快照有问题。前者是前提不成立（3），后者是判据结论（1）。"""
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 3
