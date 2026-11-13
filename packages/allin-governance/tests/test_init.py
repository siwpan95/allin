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
6. 已有 `package.json` / `.gitignore` 时**合并**而不是取代；
7. 策略实现文件里不许出现完整的内联豁免注解字面量 —— 那是 F-01 的越权红线，
   出现就会让 CI 增量扫描 fail closed（2026-11-07 push run 42368707409）。

不测「跑完 14 道门禁是不是绿的」：聚合器需要 Node，属于 CI 的端到端步骤
（`.github/workflows/gates.yml` 的 `scaffold` job），放这里只会让单测依赖 Node。
**例外**：`g03-credentials` 这道单跑是纯 Python，且 2026-11-07 的缺陷正是
「init 完骨架被自己带的夹具判红」—— 这条回归必须留在单测里，不能只靠 CI。

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


def _load_credentials_gate():
    """从**本次 init 实际用的套件目录**加载 g03，避免测到另一份副本。"""
    import importlib

    suite = init_module.suite_dir()
    sys.path.insert(0, str(suite / "gates"))
    return importlib.import_module("g03_credentials")


def test_scaffold_ships_annotation_allowlist(tmp_path: Path) -> None:
    """F-01 之后 g03 只认仓内白名单；init 必须把自带夹具登记进去。

    少了这份文件，`g03_credentials.py` 里 12 处合成自检夹具会被骨架自己的
    凭据门禁判红 —— 实测 cbb7b86 之后 `init` 完就是一屏红。
    """
    assert _run(tmp_path) == 0
    allowlist = (tmp_path / init_module.ANNOTATION_ALLOWLIST_REL).read_text(encoding="utf-8")
    registered = {line.strip() for line in allowlist.splitlines()
                  if line.strip() and not line.strip().startswith("#")}
    assert "tools/gate/governance/gates/g03_credentials.py" in registered
    # 白名单必须覆盖**所有**带注解的出厂脚本，不能只修当下这一个。
    gate = _load_credentials_gate()
    for name in (init_module.SUITE_RELATIVE / "gates").glob("*.py"):
        if gate.ANNOTATION in name.read_text(encoding="utf-8", errors="replace"):
            assert name.as_posix() in registered, name.as_posix()


def test_scaffold_credentials_gate_is_green(tmp_path: Path) -> None:
    """端到端判据（纯 Python 单跑）：init 完的骨架不能被自己的夹具判红。"""
    assert _run(tmp_path) == 0
    gate = _load_credentials_gate()
    report = gate.scan(tmp_path, machine_roots=[])
    assert not report.findings, report.render()


# ── 2026-11-13 CI 双平台恒红回归（骨架 = 治理全套的子集）────────────────────
# 前两条是「资产齐不齐」，第三条才是真正的判据：**在骨架自己的目录里**
# 用子进程跑骨架自带的 g00-meta。此前 test_scaffold_credentials_gate_is_green
# 直接 import 仓内模块，借了仓内 runtime/ 的 sys.path，骨架缺文件它照样绿 ——
# 测试和被测对象不在同一个隔离环境，等于没测。

def test_scaffold_ships_all_runtime_support_modules(tmp_path: Path) -> None:
    """骨架必须自带 runtime/*.py 全量：g03 自检会 import selfcheck_fixtures。

    2026-11-13 实名事故：init 只拷 govlib.py，骨架 `g03 --selfcheck`
    ModuleNotFoundError ⇒ g00-meta 判「self-check printed no SELFCHECK summary」。
    """
    assert _run(tmp_path) == 0
    shipped = {p.name for p in (tmp_path / "tools/gate/governance/runtime").glob("*.py")}
    source = {p.name for p in (init_module.suite_dir() / "runtime").glob("*.py")}
    assert source, "找不到上游 runtime 目录（测试无法自证）"
    assert source <= shipped, f"骨架漏拷 runtime 模块：{sorted(source - shipped)}"
    assert "selfcheck_fixtures.py" in shipped


def test_registry_declares_subset_numbering_gaps(tmp_path: Path) -> None:
    """出厂 14 道是 20 道治理全套的子集 ⇒ 缺口必须逐条带理由声明。"""
    assert _run(tmp_path) == 0
    payload = json.loads(
        (tmp_path / "tools/gate/governance/registry.json").read_text(encoding="utf-8")
    )
    shipped = {int(gid[1:3]) for gid in
               (entry["id"] for entry in payload["gates"]) if gid.startswith("g")}
    gaps = {n for n in range(0, max(shipped) + 1) if n not in shipped}
    declarations = payload.get("declared_numbering_gaps", [])
    declared = {item["number"] for item in declarations}
    # g02 是 g00-meta 的内置历史白名单，不需要声明。
    assert gaps - {2} == declared, f"缺口声明与实际不符：{sorted(gaps - {2} - declared)}"
    for item in declarations:
        assert isinstance(item.get("reason"), str) and len(item["reason"].strip()) >= 12
        assert item["number"] in gaps, "声明了并非缺口的编号"


def test_scaffold_meta_gate_is_green_in_isolation(tmp_path: Path) -> None:
    """CI 等价判据：子进程在骨架目录跑骨架自带 g00-meta，必须 exit 0。

    这是 2026-11-13 CI Linux/Windows 双红的直接复现：不借仓内 sys.path、
    不 import 仓内模块。g00-meta 会逐道跑骨架门禁的 --selfcheck，
    任何 runtime 漏拷 / 编号缺口未声明都会在这里判红。
    """
    assert _run(tmp_path) == 0
    suite = tmp_path / "tools/gate/governance"
    script = suite / "gates" / "g00_meta.py"
    result = subprocess.run(
        [sys.executable, str(script),
         "--root", str(tmp_path),
         "--registry", str(suite / "registry.json"),
         "--rules", str(suite / "RULES.md")],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180,
    )
    assert result.returncode == 0, (
        f"骨架 g00-meta 判红（exit {result.returncode}）：\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "SELFCHECK" not in result.stdout or "printed no SELFCHECK" not in result.stdout


def test_init_never_embeds_full_annotation_literal() -> None:
    """策略实现文件不是已登记夹具，完整注解字面量会让 CI 增量扫描 fail closed。

    2026-11-07 push run 42368707409：本模块把注解模式整串写进普通源码，F-01
    判为「在提交内容里自行声明豁免」，gitleaks 明明 no leaks found 仍判红。
    常量按片段拼装后运行值不变，且不给任何文件增加豁免权。
    """
    gate = _load_credentials_gate()
    assert init_module.ANNOTATION_MARKER == gate.ANNOTATION
    source = Path(init_module.__file__).read_text(encoding="utf-8")
    assert gate.ANNOTATION not in source, "init.py 不得出现完整注解字面量"


def test_annotation_allowlist_merge_keeps_user_entries(tmp_path: Path) -> None:
    """白名单是受评审的仓库配置：`--force` 也不许覆盖使用者自己的条目。"""
    path = tmp_path / init_module.ANNOTATION_ALLOWLIST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 我自己的配置\nmy/own/fixture.py\n", encoding="utf-8")

    assert _run(tmp_path, "--force") == 0
    text = path.read_text(encoding="utf-8")
    assert "my/own/fixture.py" in text
    assert "tools/gate/governance/gates/g03_credentials.py" in text
    assert init_module.verify_main([str(tmp_path), "--quiet"]) == 0


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
