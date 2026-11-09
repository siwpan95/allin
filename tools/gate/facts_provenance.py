#!/usr/bin/env python3
"""facts-provenance gate (g25) -- 溯源键与事实引用的独立离线门禁。

判两层，都如实报态：
  * 主判据（始终可判、纯离线）：facts.json 每条 fact 的 source_file 必须存在，
    且 source_line 落在该文件实际行数内；evidence_ref 不得为空。
  * 次判据（下游在位时）：deploy/*/state/last_*.json 里的 source_git_sha
    必须能被 git cat-file 解析为真实提交；下游未接入时**显式 SKIPPED 并计数**，
    不冒充通过、也不把跑批拖红。

判据只有一份：JSON 读取复用 tools/facts/cli.py 的 load_json。
零第三方依赖。退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "facts"))
import cli as F  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GATE = "facts-provenance"
EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[2]
STATE_FILES = (
    ("dolt", ROOT / "deploy" / "dolt" / "state" / "last_import.json"),
    ("netbox", ROOT / "deploy" / "netbox" / "state" / "last_sync.json"),
)


def sha_resolves(root: Path, sha: str) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"],
                           capture_output=True, timeout=15)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def scan(root: Path, data: Path) -> dict:
    findings, skipped, checked = [], [], []
    doc = F.load_json(data)
    for f in doc.get("facts", []):
        fid = f.get("fact_id", "?")
        sf, sl = f.get("source_file", ""), f.get("source_line", 0)
        if not f.get("evidence_ref"):
            findings.append(f"{fid}: evidence_ref 为空（D17 留痕要求）")
        if not sf:
            findings.append(f"{fid}: source_file 为空")
            continue
        p = root / sf
        if not p.is_file():
            findings.append(f"{fid}: source_file 不存在：{sf}")
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        if not (1 <= int(sl) <= n):
            findings.append(f"{fid}: source_line {sl} 越界（{sf} 共 {n} 行）")
        else:
            checked.append(fid)
    for name, state in STATE_FILES:
        if not state.is_file():
            skipped.append(f"{name}: 下游 state 未生成（服务未接入）")
            continue
        try:
            payload = json.loads(state.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            findings.append(f"{name}: state 不是合法 JSON：{e}")
            continue
        sha = payload.get("source_git_sha", "")
        if not sha or not sha_resolves(root, sha):
            findings.append(f"{name}: source_git_sha 无法解析为真实提交：{sha!r}")
        else:
            checked.append(f"{name}:{sha}")
    return {"checked": checked, "findings": findings, "skipped": skipped}


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-provenance-selftest-"))
    (root / "docs").mkdir()
    (root / "docs" / "src.md").write_text("line1\nline2\nline3\n", encoding="utf-8")
    good = {"facts": [{"fact_id": "F-1", "source_file": "docs/src.md", "source_line": 2,
                       "evidence_ref": "docs/记录/交接/2026-11.md"}]}
    bad = {"facts": [{"fact_id": "F-2", "source_file": "docs/src.md", "source_line": 99,
                      "evidence_ref": "docs/记录/交接/2026-11.md"}]}
    missing = {"facts": [{"fact_id": "F-3", "source_file": "docs/nope.md", "source_line": 1,
                          "evidence_ref": "x"}]}
    fake_state = root / "state.json"
    fake_state.write_text(json.dumps({"source_git_sha": "definitely-not-a-commit-xyz"}),
                          encoding="utf-8")
    ok_good = len(scan_for_fixture(root, good)["findings"]) == 0
    ok_bad = len(scan_for_fixture(root, bad)["findings"]) == 1
    ok_missing = len(scan_for_fixture(root, missing)["findings"]) == 1
    ok_sha = not sha_resolves(ROOT, "definitely-not-a-commit-xyz")
    ok = ok_good and ok_bad and ok_missing and ok_sha
    print(json.dumps({"good": ok_good, "bad_line_caught": ok_bad,
                      "missing_file_caught": ok_missing, "bad_sha_rejected": ok_sha,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def scan_for_fixture(root: Path, doc: dict) -> dict:
    """只跑主判据（夹具不依赖 Git 仓库与下游 state）。"""
    findings = []
    for f in doc.get("facts", []):
        sf, sl = f.get("source_file", ""), f.get("source_line", 0)
        if not f.get("evidence_ref"):
            findings.append("evidence_ref 为空")
        p = root / sf
        if not p.is_file():
            findings.append(f"source_file 不存在：{sf}")
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        if not (1 <= int(sl) <= n):
            findings.append(f"source_line {sl} 越界")
    return {"findings": findings, "skipped": [], "checked": []}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=GATE)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--data", type=Path, default=F.DEFAULT_DATA)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.data.is_file():
        print(f"ENV ERROR: 结构化真身不存在：{a.data}")
        return EXIT_ENV
    r = scan(a.root, a.data)
    print(f"{GATE}: fact_refs_checked={len(r['checked'])} "
          f"findings={len(r['findings'])} downstream_skipped={len(r['skipped'])}")
    for x in r["findings"]:
        print(f"  BLOCK {x}")
    for x in r["skipped"]:
        print(f"  SKIPPED (not a pass) {x}")
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    return EXIT_BLOCKING if r["findings"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
