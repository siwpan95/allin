"""Gate g00 -- the meta gate: a gate that cannot prove itself is not a gate.

Every other gate claims two things: that it still catches an injected defect,
and that it still stays quiet on clean input. This gate turns those claims into
exit codes. For each registry entry it asserts:

* the entry is complete and its script exists;
* the script exposes the whole gate contract (``--selfcheck``, ``--quiet`` and
  the four baseline switches) instead of a private subset;
* ``--selfcheck`` exits 0 and reports ``caught > 0`` with ``misreports == 0``,
  so "it printed something" can never stand in for "it detected something";
* the gate id is documented in ``governance/RULES.md``, so a rule can always be
  traced to the check that enforces it.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, GateError, Report  # noqa: E402

GATE = "g00-meta"
TITLE = "governance: gate contract self-verification"

#: 当前平台代号，取值与 registry 的 ``platforms`` 字段同一套词汇（``nt`` / ``posix``）。
#: 用它决定「这道门禁在本机能不能自证」—— 见下方 selfcheck 段的说明。
CURRENT_PLATFORM = "nt" if os.name == "nt" else "posix"

REQUIRED_FIELDS = ("id", "title", "script", "tier", "rules", "platforms", "requires", "selfcheck")
REQUIRED_SWITCHES = ("--selfcheck", "--quiet", "--baseline", "--no-baseline", "--write-baseline", "--list-all")
# 契约要求的摘要格式：`SELFCHECK {"caught":N,"clean":M,"misreports":K}`（紧凑分隔符、无空格）。
# 用契约文本本身当正则：格式偏差即判「没打印摘要」，不留「打印了就算」的模糊地带。
SELFCHECK_LINE = re.compile(r'^SELFCHECK (\{"caught":\d+,"clean":\d+,"misreports":\d+\})$', re.MULTILINE)
SELFCHECK_TIMEOUT_SECONDS = 600


def run_gate_script(python: str, script: Path, args: list[str], root: Path) -> tuple[int, str]:
    """Run one gate script with the same interpreter, capturing its output.

    Line endings are normalized before any line-anchored parsing: a child on
    Windows writes CRLF, which would otherwise defeat a ``$``-anchored pattern.
    """
    completed = subprocess.run(
        [python, str(script), *args],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=SELFCHECK_TIMEOUT_SECONDS,
    )
    text = completed.stdout.decode("utf-8", "replace")
    return completed.returncode, text.replace("\r\n", "\n").replace("\r", "\n")


def untracked_support(root: Path, registry_path: Path, tracked: set[str]) -> list[str]:
    """Governance Python files present on disk but absent from the index.

    An ignore rule can hide a support module: the repository-wide ``lib/`` rule
    already swallowed one gate runtime, and `git status` stays silent about
    ignored files, so the loss is invisible until a fresh clone fails. The
    governance directory is derived from the registry's own location, so the
    check tracks wherever the subtree is placed (it now lives under
    tools/gate/governance/ rather than at the repo root).
    """
    base = registry_path.parent
    if not base.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in base.rglob("*.py")
                  if path.relative_to(root).as_posix() not in tracked)


def inspect(root: Path, registry_path: Path, rules_path: Path, python: str) -> Report:
    """Judge every registered gate and return the classified report."""
    report = Report(title=TITLE)
    if not registry_path.is_file():
        raise GateError(f"registry not found: {registry_path}")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GateError(f"{registry_path}: invalid JSON: {error}") from error
    entries = registry.get("gates")
    if not isinstance(entries, list) or not entries:
        raise GateError(f"{registry_path}: 'gates' must be a non-empty list")
    tracked = set(govlib.tracked_files(root))
    for missing in untracked_support(root, registry_path, tracked):
        report.block("untracked-support", missing, 0,
                     f"{missing}: present on disk but absent from the git index (an ignore rule can hide it)")
    rules_text = rules_path.read_text(encoding="utf-8") if rules_path.is_file() else ""
    if not rules_text:
        report.block("registry", str(rules_path.relative_to(root)), 0, "RULES.md is missing or empty")

    for entry in entries:
        if not isinstance(entry, dict):
            report.block("registry", str(registry_path.relative_to(root)), 0, f"entry is not an object: {entry!r}")
            continue
        identifier = str(entry.get("id", "<missing id>"))
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            report.block("registry", str(registry_path.relative_to(root)), 0,
                         f"{identifier}: missing field(s) {', '.join(missing)}")
            continue
        if not entry["rules"]:
            report.block("registry", str(registry_path.relative_to(root)), 0, f"{identifier}: declares no rules")
        # Registry script paths are expressed relative to the governance subtree's
        # parent (tools/gate) — matching the base run.ts uses to resolve gate
        # scripts. Derive it from the *registry file* we were handed, not the module
        # constant GOVERNANCE_DIR: the meta gate's own --selfcheck runs against a
        # Sandbox() copy whose registry lives under a temp dir, so a fixed constant
        # would point at the real tree and the fixture scripts would never resolve.
        # registry_path.parent.parent == tools/gate in the real run, == sandbox.path
        # in the self-check, so both scenarios resolve correctly.
        script = registry_path.parent.parent / str(entry["script"])
        if not script.is_file():
            report.block("registry", str(registry_path.relative_to(root)), 0,
                         f"{identifier}: script not found at {entry['script']}")
            continue
        report.scanned += 1

        if identifier not in rules_text:
            report.block("rules-map", str(rules_path.relative_to(root)), 0,
                         f"{identifier}: not documented in RULES.md")

        code, help_text = run_gate_script(python, script, ["--help"], root)
        if code != 0:
            report.block("contract", str(script.relative_to(root)), 0, f"{identifier}: --help exited {code}")
            continue
        for switch in REQUIRED_SWITCHES:
            if switch not in help_text:
                report.block("contract", str(script.relative_to(root)), 0,
                             f"{identifier}: does not expose {switch}")
        # A gate that claims to read the host profile must be able to stop doing so,
        # because the aggregate runs repository-only.
        if entry.get("profileProbe") is True and "--no-profile" not in help_text:
            report.block("contract", str(script.relative_to(root)), 0,
                         f"{identifier}: declares profileProbe but does not expose --no-profile")

        if entry.get("selfcheck") is not True:
            report.block("contract", str(script.relative_to(root)), 0,
                         f"{identifier}: registry does not claim a self-check")
            continue
        # 平台不匹配的门禁不能要求它在**本机**自证。
        # 起因（2026-10-31，真实 CI 事故）：`g20-facts` 在 registry 里声明
        # ``platforms: ["nt"]``（它判的是 Windows 本机磁盘路径的存在性声称），
        # 但本循环此前**不看 platforms 字段**，一律跑 `--selfcheck`。
        # 于是 Linux CI 上 g20 的自检必然红：它注入的「破坏用例」需要在 NT 上
        # 才成立，在 posix 上连用例本身都跑不起来 → selfcheck 报
        # 「injected no defect it could catch」+「2 false positive(s)」→ g00 红
        # → 整条流水线红，而真正的结论是「这道门禁在 Linux 上不适用」。
        #
        # 处置口径（与 SPEC-002 / 门禁契约的「SKIP ≠ 通过」一致）：
        # **记 SKIP 并计数，不算通过、也不算失败**。这样 Linux CI 的结论是
        # 「19 道自证 + 1 道按平台跳过」，而不是假装 20 道全过。
        platforms = entry.get("platforms") or []
        if platforms and CURRENT_PLATFORM not in platforms:
            report.skip(f"{identifier}: not applicable on {CURRENT_PLATFORM} "
                        f"(declares {','.join(str(p) for p in platforms)})")
            continue
        code, output = run_gate_script(python, script, ["--selfcheck"], root)
        match = SELFCHECK_LINE.search(output)
        if match is None:
            report.block("selfcheck", str(script.relative_to(root)), 0,
                         f"{identifier}: self-check printed no SELFCHECK summary")
            continue
        payload = json.loads(match.group(1))
        caught = int(payload.get("caught", 0))
        clean = int(payload.get("clean", 0))
        misreports = int(payload.get("misreports", 0))
        if code != 0:
            report.block("selfcheck", str(script.relative_to(root)), 0,
                         f"{identifier}: self-check exited {code}")
        if caught < 1:
            report.block("selfcheck", str(script.relative_to(root)), 0,
                         f"{identifier}: self-check injected no defect it could catch")
        if clean < 1:
            report.block("selfcheck", str(script.relative_to(root)), 0,
                         f"{identifier}: self-check proved nothing about clean input")
        if misreports != 0:
            report.block("selfcheck", str(script.relative_to(root)), 0,
                         f"{identifier}: self-check reported {misreports} false positive(s)")
        if code == 0 and caught >= 1 and clean >= 1 and misreports == 0:
            report.note(f"{identifier}: contract ok (caught {caught}, clean {clean})")
    return report


def _fixture_gate(epilogue: str) -> str:
    """Build a compliant gate skeleton for the self-check, with a chosen ending."""
    return (
        "import argparse, json, sys\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--selfcheck', action='store_true')\n"
        "parser.add_argument('--quiet', action='store_true')\n"
        "parser.add_argument('--baseline')\n"
        "parser.add_argument('--no-baseline', action='store_true')\n"
        "parser.add_argument('--write-baseline', action='store_true')\n"
        "parser.add_argument('--list-all', action='store_true')\n"
        "args = parser.parse_args()\n"
        + epilogue
    )


def selfcheck() -> int:
    """Prove the meta gate rejects a broken gate and accepts a compliant one."""
    check = govlib.SelfCheck(gate=GATE)
    good_gate = _fixture_gate(
        "if args.selfcheck:\n"
        "    print('SELFCHECK ' + json.dumps({'caught': 1, 'clean': 1, 'misreports': 0}, separators=(',', ':')))\n"
        "sys.exit(0)\n"
    )
    bad_gate = _fixture_gate("sys.exit(1)\n")
    silent_gate = _fixture_gate("sys.exit(0)\n")
    with govlib.Sandbox() as sandbox:
        sandbox.write("governance/gates/ok_gate.py", good_gate)
        sandbox.write("governance/gates/bad_gate.py", bad_gate)
        sandbox.write("governance/gates/silent_gate.py", silent_gate)
        registry = {
            "version": 1,
            "gates": [
                {"id": "ok", "title": "ok", "script": "governance/gates/ok_gate.py", "tier": "P0",
                 "rules": ["r1"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True},
                {"id": "bad", "title": "bad", "script": "governance/gates/bad_gate.py", "tier": "P0",
                 "rules": ["r2"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True},
                {"id": "silent", "title": "silent", "script": "governance/gates/silent_gate.py", "tier": "P0",
                 "rules": ["r3"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True},
                {"id": "undocumented", "title": "undocumented", "script": "governance/gates/ok_gate.py",
                 "tier": "P0", "rules": ["r4"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True},
                {"id": "incomplete", "title": "incomplete", "script": "governance/gates/ok_gate.py"},
                # Claims to read the host profile while exposing no way to stop.
                {"id": "profile-claim", "title": "profile-claim", "script": "governance/gates/ok_gate.py",
                 "tier": "P0", "rules": ["r5"], "platforms": ["nt", "posix"], "requires": ["python"],
                 "selfcheck": True, "profileProbe": True},
                # 声明一个「非本机」的平台：它必须被跳过并留痕，而不是判红。
                # 平台取反而不是写死 posix —— 因为夹具要在两种宿主上都跑得通。
                {"id": "other-platform", "title": "other-platform", "script": "governance/gates/ok_gate.py",
                 "tier": "P0", "rules": ["r6"],
                 "platforms": ["posix" if CURRENT_PLATFORM == "nt" else "nt"],
                 "requires": ["python"], "selfcheck": True},
            ],
        }
        sandbox.write("governance/registry.json", json.dumps(registry, indent=2) + "\n")
        sandbox.write("governance/RULES.md",
                      "# Rules\n\n| id | rules |\n| --- | --- |\n| ok | r1 |\n| bad | r2 |\n"
                      "| silent | r3 |\n| incomplete | r5 |\n| profile-claim | r5 |\n"
                      "| other-platform | r6 |\n")

        report = inspect(sandbox.path, sandbox.path / "governance/registry.json",
                         sandbox.path / "governance/RULES.md", sys.executable)
        blocked = {f"{finding.kind}:{finding.text.split(':')[0]}" for finding in report.findings}
        check.detects("self-check that exits non-zero", any(kind.startswith("selfcheck:bad") for kind in blocked))
        check.detects("self-check that prints no summary",
                      any(kind.startswith("selfcheck:silent") for kind in blocked))
        check.detects("gate missing from RULES.md",
                      any(kind.startswith("rules-map:undocumented") for kind in blocked))
        check.detects("registry entry missing fields",
                      any(kind.startswith("registry:incomplete") for kind in blocked))
        check.detects("a gate claiming a profile probe it cannot disable",
                      any("profile-claim" in finding.text for finding in report.findings))
        # 平台跳过自证（2026-10-31 新增）：声明「不支持本机平台」的门禁必须被
        # **跳过而不是判红**，且跳过要留痕（SKIP ≠ 通过）。
        # 这个夹具补的是一个真实事故：g20-facts 声明 platforms=["nt"]，
        # 而本循环曾不看该字段 → Linux CI 上它的自检必然红，整条流水线跟着红。
        check.detects("platform skip leaves a trace",
                      any("not applicable on" in reason for reason in report.skipped))
        check.quiet("compliant gate", any(kind.startswith(("selfcheck:ok", "contract:ok", "rules-map:ok"))
                                          for kind in blocked))

    with govlib.Sandbox() as sandbox:
        sandbox.write("governance/gates/ok_gate.py", good_gate)
        sandbox.write("governance/RULES.md", "# Rules\n\n| ok |\n")
        sandbox.write("governance/registry.json", json.dumps({"version": 1, "gates": [
            {"id": "ok", "title": "ok", "script": "governance/gates/ok_gate.py", "tier": "P0",
             "rules": ["r1"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True}]}) + "\n")
        clean = inspect(sandbox.path, sandbox.path / "governance/registry.json",
                        sandbox.path / "governance/RULES.md", sys.executable)
        check.quiet("a fully compliant registry", bool(clean.findings))

    with govlib.Sandbox() as sandbox:
        sandbox.write("governance/gates/ok_gate.py", good_gate)
        # On disk but never added: exactly how an ignore rule hides a support module.
        sandbox.write("governance/runtime/hidden.py", "# support module kept out of the index\n", track=False)
        sandbox.write("governance/RULES.md", "# Rules\n\n| ok |\n")
        sandbox.write("governance/registry.json", json.dumps({"version": 1, "gates": [
            {"id": "ok", "title": "ok", "script": "governance/gates/ok_gate.py", "tier": "P0",
             "rules": ["r1"], "platforms": ["nt", "posix"], "requires": ["python"], "selfcheck": True}]}) + "\n")
        report = inspect(sandbox.path, sandbox.path / "governance/registry.json",
                         sandbox.path / "governance/RULES.md", sys.executable)
        check.detects("a support module missing from the index",
                      any(finding.kind == "untracked-support" for finding in report.findings))
    return check.finish()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--registry", default=None, help="registry file (default: governance/registry.json)")
    parser.add_argument("--rules", default=None, help="rules map (default: governance/RULES.md)")
    parser.add_argument("--python", default=sys.executable, help="interpreter used to run each gate")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    if args.selfcheck:
        return selfcheck()

    # The governance subtree lives at <root>/tools/gate/governance/, so the work
    # tree root is discovered by walking up to the git toplevel (layout-independent)
    # rather than assuming a fixed number of parent segments.
    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    registry = Path(args.registry) if args.registry else govlib.GOVERNANCE_DIR / "registry.json"
    rules = Path(args.rules) if args.rules else govlib.GOVERNANCE_DIR / "RULES.md"
    report = inspect(root, registry, rules, args.python)
    print(report.render().splitlines()[0] if args.quiet else report.render())
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
