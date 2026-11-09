#!/usr/bin/env python3
"""licenses 权威源 -> facts.json.licenses 索引投影（A 期 Phase 3）。

权威源裁定：docs/事实源/licenses.yaml（由 bootstrap_legacy_yaml.py 从
来源与许可表.md 一次性抽取；MD 降级为人类可读孪生，二者同源维护）。
facts.json.licenses 是 licenses.yaml 的派生索引投影（带 source_file 指针），删了重建即得。

索引颗粒度（Q3）：仅 id(dir)/license/status/source_file —— 来源/许可细则/归档标记等详情留在 YAML。
零第三方依赖（仅标准库 + 可选 yaml）。退出码：0 干净 / 1 finding / 2 用法 / 3 环境。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "docs" / "事实源" / "licenses.yaml"
DEFAULT_DATA = ROOT / "facts" / "facts.json"
KEY = "licenses"
ID_FIELD = "dir"


def _yaml_load(path: Path) -> dict | None:
    try:
        import yaml
    except ImportError:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def collect(auth: Path = AUTH) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not auth.is_file():
        return [], [f"权威源不存在：{auth}"]
    doc = _yaml_load(auth)
    if doc is None:
        return [], [f"权威源无法解析：{auth}"]
    rows = doc.get(KEY) or []
    if not rows:
        warnings.append("权威源无 licenses 条目")
    index = [{"dir": r[ID_FIELD], "license": r.get("license"),
              "status": r.get("status"),
              "source_file": f"docs/事实源/{KEY}.yaml"} for r in rows]
    return index, warnings


def write_index(data: Path, index: list[dict]) -> int:
    doc = json.loads(data.read_text(encoding="utf-8"))
    doc[KEY] = index
    data.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK


def check_sync(data: Path, auth: Path = AUTH) -> tuple[int, list[str]]:
    findings: list[str] = []
    if not auth.is_file():
        return EXIT_OK, ["SKIP(no auth)"]
    adoc = _yaml_load(auth)
    if adoc is None:
        return EXIT_OK, ["SKIP(auth unpar.able)"]
    a_ids = {r[ID_FIELD] for r in (adoc.get(KEY) or []) if isinstance(r, dict) and r.get(ID_FIELD)}
    doc = json.loads(data.read_text(encoding="utf-8"))
    j_index = doc.get(KEY) or []
    j_ids = {r[ID_FIELD] for r in j_index if isinstance(r, dict) and r.get(ID_FIELD)}
    for k in sorted(a_ids - j_ids):
        findings.append(f"权威源有 {k} 但 facts.json.licenses 缺（投影滞后，未重新生成）")
    for k in sorted(j_ids - a_ids):
        findings.append(f"facts.json.licenses 有 {k} 但权威源缺（投影凭空多，真漂移）")
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-licenses-selftest-"))
    auth = root / "docs" / "事实源" / "licenses.yaml"
    auth.parent.mkdir(parents=True)
    auth.write_text("licenses:\n  - dir: a\n    seq: 1\n    license: MIT\n    status: 可发布\n"
                    "  - dir: b\n    seq: 2\n    license: GPL-3.0\n    status: 仅本地参考\n", encoding="utf-8")
    data = root / "facts.json"
    data.write_text(json.dumps({"schema_version": "0.1.0", "machines": [], "facts": []}), encoding="utf-8")
    index, _ = collect(auth)
    write_index(data, index)
    rc_sync, _ = check_sync(data, auth)
    ok_sync = rc_sync == EXIT_OK
    bad = json.loads(data.read_text(encoding="utf-8"))
    bad[KEY].append({"dir": "phantom", "license": "无", "status": "x",
                     "source_file": "docs/事实源/licenses.yaml"})
    data.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc_drift, _ = check_sync(data, auth)
    ok_drift = rc_drift == EXIT_BLOCKING
    ok = ok_sync and ok_drift and len(index) == 2
    print(json.dumps({"collect": len(index), "sync_clean": ok_sync, "drift_caught": ok_drift,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="licenses -> facts.json.licenses 索引投影")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--auth", type=Path, default=AUTH)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check:
        rc, msgs = check_sync(a.data, a.auth)
        for m in msgs:
            print(f"  {'SKIP' if m.startswith('SKIP') else 'BLOCK'} [licenses] {m}")
        print(f"licenses-sync: {'clean' if rc == EXIT_OK else 'blocking'} (exit={rc})")
        return rc
    index, warnings = collect(a.auth)
    for w in warnings:
        print(f"  WARN {w}")
    if a.write:
        if not index:
            print(f"ENV ERROR: 权威源无条目：{a.auth}")
            return EXIT_ENV
        write_index(a.data, index)
        print(f"WROTE: facts.json.licenses={len(index)}（权威={a.auth}）")
        return EXIT_OK
    print(json.dumps(index, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
