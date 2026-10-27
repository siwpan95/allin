"""Gate g18 -- accepted risk is registered, reasoned, and expires.

Every frozen baseline key, every hygiene exemption and every declared registry
gap is risk somebody accepted. Unregistered accepted risk has three properties,
all bad: nobody remembers why it was accepted, nobody knows who owns it, and it
never comes up for review again -- it simply becomes permanent.

The governance literature is blunt about the fix: an exception is a record with
an id, the control it disables, a business reason, a compensating control, an
approver, an **expiry date** and a status, reviewed on a cadence. This gate is
that record turned into an exit code:

* ``governance/exceptions.yml`` parses and every entry is complete --
  ``id / kind / gate / target / reason / compensating / approver / expires /
  status`` -- so an exception can never be a one-line shrug;
* ids are unique and ``status`` comes from the closed set ``open | closed``;
* ``kind`` comes from the closed set, so the exception ledger stays sortable;
* **an open exception past its expiry blocks.** Accepted risk that outlives its
  review date is not accepted any more, it is just forgotten;
* coverage is reported, never silently assumed: how many frozen keys and
  exemption rows exist versus how many have a registered exception.

Coverage is a note and not a block on purpose: turning it into a block on day
one would mean writing fifty-odd records in one sitting, and a gate that reds
the repository on its first run is a gate that gets switched off.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_OK, EXIT_ENV, Report  # noqa: E402

GATE = "g18-exceptions"
TITLE = "governance: accepted risk is registered, reasoned, and expires"

EXCEPTIONS_REL = "tools/gate/governance/exceptions.yml"
BASELINE_DIR = "tools/gate/governance/baseline"
EXEMPTIONS_REL = "tools/gate/audit/repo_hygiene_exemptions.csv"
GAPS_REL = "tools/gate/governance/registry-known-gaps.txt"

REQUIRED_FIELDS = ("id", "kind", "gate", "target", "reason", "compensating", "approver", "expires", "status")
ALLOWED_KINDS = ("baseline-freeze", "hygiene-exemption", "known-gap")
ALLOWED_STATUS = ("open", "closed")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_exceptions(path: Path) -> tuple[list[dict] | None, str]:
    """Parse the exception ledger. Returns (entries, error)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, "PyYAML 不可用（无法解析 exceptions.yml）"
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None, "exceptions.yml 不可读"
    try:
        payload = yaml.safe_load(raw)
    except Exception as error:  # noqa: BLE001  (yaml raises many types)
        return None, f"exceptions.yml 解析失败：{error}"
    if not isinstance(payload, dict):
        return None, "exceptions.yml 顶层必须是对象"
    entries = payload.get("exceptions")
    if entries is None:
        return [], ""
    if not isinstance(entries, list):
        return None, "'exceptions' 必须是列表"
    return [entry for entry in entries if isinstance(entry, dict)], ""


def count_frozen(root: Path) -> dict[str, int]:
    """Frozen baseline keys per gate, exemption rows, and declared gaps."""
    counts: dict[str, int] = {}
    baseline = root / BASELINE_DIR
    if baseline.is_dir():
        for path in sorted(baseline.glob("*.txt")):
            try:
                keys = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                        if ln.strip() and not ln.strip().startswith("#")]
            except OSError:
                continue
            if keys:
                counts[path.stem] = len(keys)
    for rel, label in ((EXEMPTIONS_REL, "repo_hygiene_exemptions.csv"), (GAPS_REL, "registry-known-gaps.txt")):
        try:
            lines = [ln.strip() for ln in (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
        except OSError:
            continue
        if label.endswith(".csv") and lines and lines[0].lower().startswith("rule"):
            lines = lines[1:]
        if lines:
            counts[label] = len(lines)
    return counts


def run(root: str, args: argparse.Namespace) -> Report:
    report = Report(title=TITLE)
    base = Path(root)
    entries, error = load_exceptions(base / EXCEPTIONS_REL)
    if error:
        report.block("ledger-unusable", EXCEPTIONS_REL, 0, error)
        return report
    assert entries is not None
    if not entries:
        report.skip("ledger 为空（还没有登记任何例外）")
        return report

    today = dt.date.today()
    seen: dict[str, int] = {}
    open_count = 0
    for index, entry in enumerate(entries, start=1):
        report.scanned += 1
        missing = [field for field in REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
        if missing:
            report.block("incomplete-exception", EXCEPTIONS_REL, index,
                         f"第 {index} 条缺字段：{', '.join(missing)}")
            continue
        identifier = str(entry["id"]).strip()
        if identifier in seen:
            report.block("duplicate-exception", EXCEPTIONS_REL, index,
                         f"id '{identifier}' 重复（首次出现在第 {seen[identifier]} 条）")
        else:
            seen[identifier] = index
            report.exempt("id-unique")
        kind = str(entry["kind"]).strip()
        if kind in ALLOWED_KINDS:
            report.exempt("kind-known")
        else:
            report.block("kind-unknown", EXCEPTIONS_REL, index,
                         f"kind '{kind}' 越界，必须是 {', '.join(ALLOWED_KINDS)} 之一")
        status = str(entry["status"]).strip()
        if status in ALLOWED_STATUS:
            report.exempt("status-known")
        else:
            report.block("status-unknown", EXCEPTIONS_REL, index,
                         f"status '{status}' 越界，必须是 {', '.join(ALLOWED_STATUS)} 之一")
        expires = str(entry["expires"]).strip()
        if not DATE.match(expires):
            report.block("bad-expiry", EXCEPTIONS_REL, index,
                         f"expires '{expires}' 不是 YYYY-MM-DD")
            continue
        try:
            when = dt.date.fromisoformat(expires)
        except ValueError:
            report.block("bad-expiry", EXCEPTIONS_REL, index, f"expires '{expires}' 不是合法日期")
            continue
        if status == "closed":
            report.exempt("closed-exception")
            continue
        open_count += 1
        if when < today:
            report.block("expired-exception", EXCEPTIONS_REL, index,
                         f"{identifier}（{kind} / {entry['gate']}）已于 {expires} 到期，"
                         f"必须复核后关闭或续期 —— 过期即视为未复核的接受风险")
        else:
            report.exempt(f"open-until-{expires}")

    frozen = count_frozen(base)
    total_frozen = sum(frozen.values())
    report.note(f"燃尽口径：冻结/豁免/缺口共 {total_frozen} 条，已登记例外 {len(entries)} 条"
                f"（open {open_count}）")
    for source, count in sorted(frozen.items(), key=lambda kv: -kv[1])[:6]:
        report.note(f"   {source}: {count}")
    return report


# --------------------------------------------------------------------------- #
# self-check
# --------------------------------------------------------------------------- #

FIXTURE_ENTRY = "\n".join([
    "- id: EX-001",
    "  kind: baseline-freeze",
    "  gate: g09-python-hygiene",
    "  target: baseline/g09-python-hygiene.txt",
    "  reason: 存量冻结",
    "  compensating: 棘轮只冻结既有键",
    "  approver: siwpan",
    "  expires: {expires}",
    "  status: {status}",
])

SELFCHECK_CASES = [
    ("clean", True),
    ("expired", False),
    ("missing-field", False),
    ("bad-status", False),
    ("duplicate-id", False),
]


def build_fixture(kind: str, base: str) -> str:
    ledger = Path(base) / "tools" / "gate" / "governance" / "exceptions.yml"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    far = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    past = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    body = "version: 1\nexceptions:\n" + FIXTURE_ENTRY.format(expires=far, status="open") + "\n"
    if kind == "expired":
        body = "version: 1\nexceptions:\n" + FIXTURE_ENTRY.format(expires=past, status="open") + "\n"
    if kind == "missing-field":
        body = "version: 1\nexceptions:\n" + "\n".join(
            ln for ln in FIXTURE_ENTRY.format(expires=far, status="open").splitlines()
            if "approver" not in ln) + "\n"
    if kind == "bad-status":
        body = "version: 1\nexceptions:\n" + FIXTURE_ENTRY.format(expires=far, status="maybe") + "\n"
    if kind == "duplicate-id":
        body = ("version: 1\nexceptions:\n"
                + FIXTURE_ENTRY.format(expires=far, status="open") + "\n"
                + FIXTURE_ENTRY.format(expires=far, status="open") + "\n")
    ledger.write_text(body, encoding="utf-8", newline="\n")
    return base


def selfcheck() -> int:
    check = govlib.SelfCheck(gate=GATE)
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("ENV ERROR: self-check needs PyYAML")
        return EXIT_ENV
    for kind, expect_clean in SELFCHECK_CASES:
        tmp = tempfile.mkdtemp(prefix="g18-exceptions-")
        try:
            build_fixture(kind, tmp)
            report = run(tmp, argparse.Namespace())
            flagged = bool(report.findings)
            if expect_clean:
                if flagged:
                    print(f"  detail: {[f'{f.kind}:{f.text}' for f in report.findings][:3]}")
                    check.quiet(kind, True)
                else:
                    check.quiet(kind, False)
            else:
                check.detects(kind, flagged)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return check.finish()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)
    govlib.configure_stdio()
    if args.selfcheck:
        return selfcheck()
    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    if not root.is_dir():
        print(f"ENV ERROR: root 不存在：{root}")
        return EXIT_ENV
    report = run(str(root), args)
    baseline_path = Path(args.baseline) if args.baseline else (
        govlib.GOVERNANCE_DIR / "baseline" / "g18-exceptions.txt")
    baseline = govlib.Baseline(baseline_path).load()
    if args.write_baseline:
        baseline.write(report.findings)
        print(f"wrote baseline {baseline_path} ({len(report.findings)} key(s))")
        return EXIT_OK
    new = list(report.findings) if args.no_baseline else baseline.filter_new(report.findings)
    shown = Report(title=report.title, findings=report.findings if args.list_all else new,
                   exempted=report.exempted, skipped=report.skipped, notes=report.notes,
                   scanned=report.scanned)
    print(shown.render().splitlines()[0] if args.quiet else shown.render())
    return EXIT_BLOCKING if new else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
