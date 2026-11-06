"""Gate g20 -- machine fact sources still match reality.

The recorded failure (2026-10-30)
--------------------------------
`docs/事实源/机器/DESKTOP-8RSV60V.md` was re-measured from scratch: **nine claims
no longer matched the disk**, while all 19 gates exited 0. Root cause is not a
broken gate but a coverage gap, one layer below the three that already exist:

* ``g07_doc_freshness`` checks that a fact source *carries* a time point -- not
  that the facts still hold *after* that time point;
* ``g19_docs_refs`` resolves **repository-relative** paths (``docs/…``, ``tools/…``)
  only; a machine absolute path (``G:\\…``) is never parsed, because its
  ``PATH_REF`` prefix allowlist contains no drive letters;
* ``g01_paths`` judges *dead* drive roots (parent missing); it cannot see a
  semantic expiry on a *live* drive (syntax valid, directory gone).

What is judged -- and deliberately nothing else
-----------------------------------------------
Only the claim types that are mechanically decidable. Noise is how a gate
gets switched off, so everything else is left to humans:

* ``path-exists`` -- a line claiming a machine absolute path *exists*
  (``现已存在`` / ``现存`` / ``仍在位``) must resolve; one claiming it is gone
  (``现已不存在`` / ``已不存在`` / ``均不存在`` / ``MISSING`` / ``已删`` / ``已移除``)
  must not.
* ``count`` -- an absolute path followed by ``**N**`` or ``N 项`` must really hold
  N entries. The unit decides the counting mode: ``项`` counts every entry
  (archive directories hold loose files), while no unit or ``个仓`` / ``个目录``
  counts directories only -- ``<盘>:\\repos`` may hold 136 directories *plus*
  4 files, and counting everything yields 140, i.e. a false drift.
* ``self-identity`` -- a line that calls a machine "本机" must name the machine
  it means (2026-11-06). See "The 本机 ambiguity" below.

The 本机 ambiguity
------------------
Each partition file is written *by* one machine and describes *that* machine,
yet every one of them says "本机" ("this machine") about itself -- so the word
carries no machine identity of its own. An agent that opens the wrong
partition file therefore reads a perfectly coherent description of **another**
machine and can carry it away as if it were its own (observed 2026-11-06 on
``@DESKTOP-8RSV60V``: the ``@DESKTOP-KQABATS`` file was read and treated as
this machine's own facts -- its "publish area: 23 repos, work area ``E:``" is
wrong for this machine in every particular).

``机器分区索引.md`` §0 rule 3 already requires "引用『本机』必须带机器名",
but nothing checked it -- a rule with no gate is a rule that decays. Two
mechanically decidable halves:

* **anchor** -- a "本机" line must carry a machine name (its own or another
  machine's) on the same line. A bare "本机" is undecidable *by construction*:
  nothing in the sentence says which machine it means.
* **ownership** -- when the "本机" line names an absolute path, that path must
  resolve on the machine that owns the file. Judged **only for the current
  machine's own file**: another machine's path legitimately does not exist
  here, so judging it locally would be the same "wrong disk" mistake the
  machine-scoping rule below exists to prevent.

Scope and honest limits: the anchor half is checked in the newest timepoint
block (same scope as the other two claim types). The ownership half is
deliberately narrower -- it cannot see a *stale* value that still exists, and
it cannot see a wrong value written into a sentence with no absolute path in
it. It catches the mechanical residue of the identity mix-up; it does not
replace the discipline of naming one's machine before touching machine facts
(``机器分区索引.md`` §3).

Machine scoping (2026-10-30, cross-machine fix)
-----------------------------------------------
A partition file describes **one** machine's disk. Judging another machine's
file on this machine compares its claims against the wrong disk and blocks
forever (observed 2026-10-30: a PowerShell 7 install path that exists on the
machine that wrote the file does not exist here). The
gate therefore judges **only the partition file of the machine it runs on**
(filename stem vs current hostname, case-insensitive); the other machines'
files are exempted with a note -- each machine verifies its own file when its
agent runs the suite there.

Scope is the header block(s) carrying the **newest** ``> **时点**`` date. Older
blocks are history: judging them would force people to rewrite the past, and a
fact source that cannot keep its own history is worth less than one that can.

Layout evolution (2026-11-06, one-machine-one-folder)
-----------------------------------------------------
The partition docs used to sit flat as ``机器/<机器名>.md``. They are moving to
``机器/<机器名>/<机器名>.md`` (one folder per machine, room for attachments under
``附属/``). The migration is per-machine (cross-machine discipline: each machine
moves its own file), so during the transition **both layouts coexist**:
top-level ``<机器名>.md`` and foldered ``<机器名>/<机器名>.md`` are both collected;
anything else inside a machine folder (``README.md``, ``附属/*``) is not a
partition doc and is ignored. A stem present in **both** layouts is migration
residue and blocks -- two same-named partition docs would make "which file is
the truth" undecidable. Once all machines have moved, top-level ``*.md`` goes
to zero and this dual collection keeps working unchanged.

Single implementation
---------------------
The criteria live here, in the gate, and ``tools/facts/verify_facts.py`` imports
them for CLI use. The gate script must be self-contained because ``g00-meta``
runs every ``--selfcheck`` inside a sandbox that contains only ``governance/``;
a checker that reached into ``tools/facts`` would report "not importable" there.
Two copies of the criteria would both report green and disagree in silence --
exactly the failure mode ``SPEC-003 §新建三查`` exists to prevent.

Exit codes follow the governance vocabulary: 0 clean, 1 blocking finding,
2 usage error, 3 environment error.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))

import govlib  # noqa: E402  (path is fixed up immediately above)
from govlib import EXIT_BLOCKING, EXIT_ENV, EXIT_OK, Baseline, Report  # noqa: E402

GATE = "g20-facts"
TITLE = "governance: machine fact sources still match reality"

TARGET_DIR = Path("docs") / "事实源" / "机器"
STALE_DAYS = 90

#: A machine absolute path: drive letter + separator + everything up to whitespace,
#: a backtick, or CJK punctuation.
ABS_PATH = re.compile(r"([A-Za-z]:[\\/][^`\s，。、；：（）【】「」]*)")

POSITIVE = re.compile(r"现已存在|现存|仍在位|EXISTS")
NEGATIVE = re.compile(r"现已不存在|已不存在|均不存在|MISSING|已删|已移除")

#: Count assertion: first ``**N**`` wins, then a bare ``N 项`` / ``N 个仓`` / ``N 个目录``.
COUNT_BOLD = re.compile(r"\*\*(\d+)\*\*\s*(项|个仓|个目录|个)?")
COUNT_PLAIN = re.compile(r"(\d+)\s*(项|个仓|个目录)")

#: A self-reference to "this machine" -- meaningless without a machine name
#: beside it, because every partition file calls itself 本机 (see the module
#: docstring, "The 本机 ambiguity").
SELF_REF = re.compile(r"本机|这台机|该机")

#: A machine name as it appears in prose: ``DESKTOP-8RSV60V`` / ``SIWPAN``.
#: Matched case-insensitively -- Windows hostnames are, and the files use both
#: ``@`SIWPAN` `` and bare ``SIWPAN``.
MACHINE_NAME = re.compile(r"DESKTOP-[A-Za-z0-9]+|SIWPAN", re.IGNORECASE)


def strip_tail(raw: str) -> str:
    return raw.rstrip("`.,;:)]}'\"、）。】")


def header_scope(text: str) -> tuple[str, str]:
    """Return (text of the newest-timepoint blocks, the timepoint string).

    Scope = every ``> **时点**`` block sharing the **latest** date, each running
    to the next such block or the first ``## `` heading. Earlier blocks are
    history and are never judged.

    ⚠ Known edge: if the newest block is purely structural (no numbers, no
    paths), claims in older blocks go unchecked. The convention that covers it:
    **write current values into the newest timepoint block** -- writing them into
    an older one is the same as not writing them.
    """
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(">") and "**时点**" in ln]

    if not starts:
        end = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        return "\n".join(lines[:end]), ""

    blocks: list[tuple[tuple[int, ...], str, str]] = []
    for idx, start in enumerate(starts):
        stop = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        for j in range(start + 1, stop):
            if lines[j].startswith("## "):
                stop = j
                break
        chunk = "\n".join(lines[start:stop])
        found = re.search(r"20\d\d[-/年]\d{1,2}[-/月]\d{1,2}", chunk)
        key = tuple(int(x) for x in re.findall(r"\d+", found.group(0))[:3]) if found else (0, 0, 0)
        blocks.append((key, chunk, found.group(0) if found else ""))

    newest = max(b[0] for b in blocks)
    kept = [b for b in blocks if b[0] == newest]
    return "\n".join(b[1] for b in kept), kept[0][2]


def count_entries(path: Path, mode: str = "dirs") -> int:
    """Count entries.

    ``dirs`` (default) counts directories only -- the unit for repo counts; the
    files sitting next to them are not repositories.
    ``all`` counts every entry -- the unit for ``N 项``, where loose files matter.
    """
    try:
        if mode == "all":
            return sum(1 for _ in path.iterdir())
        return sum(1 for c in path.iterdir() if c.is_dir())
    except OSError:
        return -1


def check_self_identity(block: str, label: str, owner: str | None) -> list[dict]:
    """Judge the "本机" self-references of one partition file.

    Two mechanically decidable halves (see the module docstring, "The 本机
    ambiguity"):

    * **anchor** -- a line that says 本机 must name a machine on the same line.
      A bare 本机 cannot be resolved by anything reading the sentence.
    * **ownership** -- a 本机 line carrying an absolute path must have that
      path resolve **on the machine that owns this file**. ``owner`` is the
      owning machine (the file's stem) and is only passed for the file that
      belongs to the machine running the gate; for another machine's file the
      ownership half is skipped (its paths legitimately do not exist here).

    ``block`` is the newest-timepoint scope, the same scope the other two
    claim types use.
    """
    findings: list[dict] = []

    for lineno, line in enumerate(block.splitlines(), 1):
        if not SELF_REF.search(line):
            continue

        # --- ownership: 本机 + an absolute path => that path is claimed to be ours
        if owner is not None:
            for raw in ABS_PATH.findall(line):
                target = strip_tail(raw)
                if len(target) < 4:
                    continue
                if not Path(target).exists():
                    findings.append({
                        "kind": "SELF-OWNERSHIP", "file": label, "line": lineno,
                        "claim": f"本机自述引用了本机不存在的路径：{target}"
                                 f"（该文件属于 {owner}；他机路径不得写成本机事实）",
                        "path": target})

        # --- anchor: 本机 must name its machine on the same line
        if not MACHINE_NAME.search(line):
            findings.append({
                "kind": "SELF-ANCHOR", "file": label, "line": lineno,
                "claim": "本机自述未标明机器名 —— 各机分区文件都以「本机」自称，"
                         "裸「本机」无法判定指哪台机器（须写明机器名，"
                         "见 机器分区索引.md §0 归属规则第 3 条）"})

    return findings


def check_text(text: str, label: str, owner: str | None = None) -> tuple[list[dict], str]:
    """Judge one fact-source document. Returns (findings, timepoint string).

    ``owner`` names the machine the file belongs to (its stem). It is passed
    only for the file of the machine running the gate; the ownership half of
    the self-identity check is skipped without it, because another machine's
    paths legitimately do not exist here.
    """
    block, stamp = header_scope(text)
    findings: list[dict] = []

    for lineno, line in enumerate(block.splitlines(), 1):
        if not line.strip():
            continue

        for raw in ABS_PATH.findall(line):
            target = strip_tail(raw)
            if len(target) < 4:
                continue
            if NEGATIVE.search(line):
                if Path(target).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称不存在但实际存在：{target}", "path": target})
            elif POSITIVE.search(line):
                if not Path(target).exists():
                    findings.append({"kind": "PATH-EXISTS", "file": label, "line": lineno,
                                     "claim": f"声称存在但实际缺失：{target}", "path": target})

        candidates = [strip_tail(x) for x in ABS_PATH.findall(line)]
        candidates = [p for p in candidates if len(p) >= 4]
        if not candidates:
            continue
        target_path = Path(candidates[0])
        if not target_path.is_dir():
            continue
        match = COUNT_BOLD.search(line) or COUNT_PLAIN.search(line)
        if not match:
            continue
        claimed = int(match.group(1))
        unit = match.group(2) or ""
        mode = "all" if unit.startswith("项") else "dirs"
        actual = count_entries(target_path, mode)
        if actual >= 0 and actual != claimed:
            findings.append({"kind": "COUNT", "file": label, "line": lineno,
                             "claim": f"声称 {claimed}（口径 {mode}），实际 {actual}：{target_path}",
                             "path": str(target_path), "claimed": claimed,
                             "actual": actual, "mode": mode})

    findings.extend(check_self_identity(block, label, owner))
    return findings, stamp


def evaluate_staleness(stamp: str) -> str:
    """Age of the timepoint. Reported, never blocking -- how old is too old is a human call."""
    if not stamp:
        return "时点：未识别"
    digits = re.findall(r"\d+", stamp)
    if len(digits) < 3:
        return f"时点：{stamp}"
    try:
        parsed = date(int(digits[0]), int(digits[1]), int(digits[2]))
    except ValueError:
        return f"时点：{stamp}（无法解析）"
    age = (date.today() - parsed).days
    return f"时点：{stamp}（{age} 天前，{'⚠ 超 ' + str(STALE_DAYS) + ' 天' if age > STALE_DAYS else '在窗口内'}）"


def current_machine() -> str:
    """Current hostname, lowercased (Windows hostnames are case-insensitive)."""
    return platform.node().lower()


def collect_machine_docs(target: Path) -> tuple[list[Path], list[tuple[str, Path, Path]]]:
    """Collect partition docs across both layouts (flat + one-machine-one-folder).

    Returns ``(docs, duplicates)``:

    * ``docs`` -- top-level ``<机器名>.md`` plus foldered ``<机器名>/<机器名>.md``
      (a subdir md counts only when its stem equals its parent dir name;
      ``README.md`` and ``附属/*`` are not partition docs).
    * ``duplicates`` -- ``[(stem, top_path, sub_path), ...]`` for stems present
      in **both** layouts. That is migration residue: two same-named partition
      docs make the "which file is the truth" decision ambiguous, so callers
      must block instead of silently picking one.
    """
    top = sorted(target.glob("*.md"))
    top_stems = {p.stem.lower(): p for p in top}
    docs = list(top)
    duplicates: list[tuple[str, Path, Path]] = []
    for sub in sorted(target.glob("*/*.md")):
        if sub.stem.lower() != sub.parent.name.lower():
            continue
        clash = top_stems.get(sub.stem.lower())
        if clash is not None:
            duplicates.append((sub.stem.lower(), clash, sub))
        else:
            docs.append(sub)
    return docs, duplicates


def scan(root: Path) -> Report:
    report = Report(title=TITLE)
    target = root / TARGET_DIR
    if not target.is_dir():
        report.skip("no machine fact directory")
        return report
    me = current_machine()
    docs, duplicates = collect_machine_docs(target)
    for stem, top_path, sub_path in duplicates:
        report.block("duplicate", top_path.name, 0,
                     f"同名分区文件并存于顶层与子目录（迁移残留）：`{top_path.name}` 与 `{sub_path}` "
                     f"—— 判定对象歧义，先删除其一（收敛口径见 机器分区索引.md §7）")
    if duplicates:
        return report
    own: Path | None = None
    for path in docs:
        if path.stem.lower() == me:
            own = path
            continue
        report.scanned += 1
        report.exempt("another machine's facts (each machine verifies its own file)")
        report.note(f"skip {path.name}: 非当前机器（{me}）的分区文件，留待该机自验")
    if own is None:
        report.note(f"当前机器（{me}）在 {TARGET_DIR} 下无同名分区文件 —— 无可判定对象"
                    f"（新增机器流程见 机器分区索引.md §1）")
        return report
    report.scanned += 1
    text = own.read_text(encoding="utf-8", errors="replace")
    # ``owner`` scopes the ownership half of the self-identity check to the
    # machine running the gate -- another machine's paths do not exist here.
    findings, stamp = check_text(text, own.name, owner=own.stem)
    report.note(f"{own.name}: {evaluate_staleness(stamp)}")
    for fd in findings:
        report.block(fd["kind"].lower(), fd["file"], fd["line"], fd["claim"])
    return report


def selfcheck() -> int:
    """Fixtures: two must be caught, one must stay clean, none may misreport."""
    root = Path(tempfile.mkdtemp(prefix="g20-selfcheck-"))
    probe = root / "probe-dir"
    probe.mkdir()
    (probe / "only-child.txt").write_text("x", encoding="utf-8")
    absent = root / "definitely-absent-xyz"

    machine = root / TARGET_DIR
    machine.mkdir(parents=True)

    good = machine / "good.md"
    good_payload = (
        "> **时点** 2026-10-30（自检：正确值）\n"
        f"> `{probe}` 共 **1 项**\n"
        f"> `{probe}` 现已存在\n"
        "## 正文\n"
        f"> `{probe}` 共 **99 项**（历史块，应被忽略）\n"
    )
    good.write_text(good_payload, encoding="utf-8")

    cases = [
        ("wrong-count.md", f"> **时点** 2026-10-30（自检）\n> `{probe}` 共 **42 项**\n", "count"),
        ("missing-path.md", f"> **时点** 2026-10-30（自检）\n> `{absent}` 现已存在\n", "path-exists"),
    ]

    caught, clean, misreports = 0, 0, 0
    for name, payload, expected in cases:
        probe_doc = machine / name
        probe_doc.write_text(payload, encoding="utf-8")
        findings, _ = check_text(payload, name)
        if any(f["kind"].lower() == expected for f in findings):
            caught += 1
        else:
            misreports += 1
        probe_doc.unlink()

    # Self-identity (2026-11-06): each half is isolated -- the fixture must be
    # caught by *that* half, not by another criterion riding along. A bare 本机
    # is caught by the anchor half; a 本机 line carrying a path that does not
    # exist here is caught by the ownership half.
    #
    # ⚠ The anchor half needs a **real** machine name (``MACHINE_NAME`` only
    # knows ``DESKTOP-*`` / ``SIWPAN``) -- a placeholder like ``SOME-MACHINE``
    # is not an anchor and would make the fixture fail for the wrong reason.
    ANCHOR = "DESKTOP-8RSV60V"
    self_cases = [
        # (payload, expected kind, owner) -- owner None => ownership half skipped
        ("bare-self.md",
         "> **时点** 2026-10-30（自检：裸本机）\n> 本机发布区 **23** 个目录\n",
         "self-anchor", None),
        ("owned-self.md",
         f"> **时点** 2026-10-30（自检：他机路径当本机）\n> 本机发布区 `{absent}` **23** 个目录\n",
         "self-ownership", ANCHOR),
        ("anchored-self.md",
         f"> **时点** 2026-10-30（自检：带锚点且路径存在）\n"
         f"> @`{ANCHOR}` 本机发布区 `{probe}` 现已存在\n",
         None, ANCHOR),
    ]
    for name, payload, expected, owner in self_cases:
        probe_doc = machine / name
        probe_doc.write_text(payload, encoding="utf-8")
        findings, _ = check_text(payload, name, owner=owner)
        kinds = {f["kind"].lower() for f in findings}
        if expected is None:
            # clean case: nothing may fire
            if findings:
                misreports += 1
            else:
                clean += 1
        elif expected in kinds:
            caught += 1
        else:
            misreports += 1
        # ⚠ 逐维隔离（2026-11-06，承交接 §134 的「三个用例都被同一个 D9 命中」教训）：
        # 断言「拦下它的是它自己那一半」，且**不得有别的判据混进来**。
        # 否则 caught 只是个高数，两条判据可能从未各自执行过。
        if expected == "self-anchor":
            if "count" in kinds or "path-exists" in kinds:
                misreports += 1
        if expected == "self-ownership":
            if "count" in kinds or "path-exists" in kinds:
                misreports += 1
        probe_doc.unlink()

    # The ownership half must NOT fire for another machine's file: its paths
    # legitimately do not exist on this machine. Without this, the criterion
    # would re-introduce the cross-machine false positive (交接 §133.4).
    foreign_payload = (
        "> **时点** 2026-10-30（自检：他机文件）\n"
        f"> @`{ANCHOR}` 本机发布区 `{absent}` **23** 个目录\n"
    )
    foreign_findings, _ = check_text(foreign_payload, "other-machine.md", owner=None)
    if any(f["kind"].lower() == "self-ownership" for f in foreign_findings):
        misreports += 1
    else:
        clean += 1

    good_findings, _ = check_text(good.read_text(encoding="utf-8"), good.name)
    if good_findings:
        misreports += 1
    else:
        clean += 1

    # Layout coverage (2026-11-06): dual-layout collection + residue detection.
    # selfcheck never calls scan() (hostname-dependent in sandboxes); the layout
    # logic is fully covered through the pure collector below.
    layout_misreports = 0
    boxed = machine / "boxed"
    boxed.mkdir()
    (boxed / "boxed.md").write_text("x", encoding="utf-8")
    (boxed / "README.md").write_text("x", encoding="utf-8")
    attached = boxed / "附属"
    attached.mkdir()
    (attached / "note.md").write_text("x", encoding="utf-8")
    (machine / "flat.md").write_text("x", encoding="utf-8")
    docs, dups = collect_machine_docs(machine)
    if dups or sorted(docs) != sorted([good, machine / "flat.md", boxed / "boxed.md"]):
        layout_misreports += 1
    (machine / "flat2.md").write_text("x", encoding="utf-8")
    (machine / "flat2").mkdir()
    (machine / "flat2" / "flat2.md").write_text("x", encoding="utf-8")
    _, dups = collect_machine_docs(machine)
    if len(dups) != 1 or dups[0][0] != "flat2":
        layout_misreports += 1

    print(f"selfcheck: caught={caught} clean={clean} misreports={misreports} layout_misreports={layout_misreports}")
    # ⚠ SELFCHECK JSON 行是 g00-meta 的严格契约（恰好三键、紧凑分隔符，见 g00_meta.SELFCHECK_LINE），
    # 布局结果只放上一行的人类可读输出；布局失配通过本函数的退出码阻断，不进这行 JSON。
    print("SELFCHECK " + json.dumps({"caught": caught, "clean": clean, "misreports": misreports},
                                    separators=(",", ":")))
    # caught: count / path-exists / self-anchor / self-ownership
    # clean:  the good fixture / anchored-self / another machine's file
    return (EXIT_OK if caught == 4 and clean == 3 and misreports == 0
            and layout_misreports == 0 else EXIT_BLOCKING)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--root", default=None, help="work tree to judge (default: discovered from this file)")
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    parser.add_argument("--selfcheck", action="store_true", help="inject fixtures and prove the gate works")
    govlib.add_baseline_argument(parser)
    args = parser.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    if sys.platform != "win32":
        print("ENV ERROR: g20-facts 只支持 Windows（判据基于盘符绝对路径）", file=sys.stderr)
        return EXIT_ENV

    root = Path(args.root).resolve() if args.root else govlib.repo_root()
    if not root.is_dir():
        print(f"ENV ERROR: root 不存在：{root}", file=sys.stderr)
        return EXIT_ENV

    report = scan(root)
    baseline_path = Path(args.baseline) if args.baseline else govlib.GOVERNANCE_DIR / "baseline" / f"{GATE}.txt"
    baseline = Baseline(baseline_path)

    if args.write_baseline:
        baseline.write(report.findings)
        print(f"{TITLE}: baseline written with {len(report.findings)} finding(s) -> {baseline_path}")
        return EXIT_OK
    if not args.no_baseline:
        baseline.load()

    new_findings = report.findings if args.no_baseline else baseline.filter_new(report.findings)
    blocking = report.findings if args.list_all else new_findings
    rendered = report.render()
    print(rendered.splitlines()[0] if args.quiet else rendered)
    return EXIT_BLOCKING if blocking else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(govlib.run_gate(main))
