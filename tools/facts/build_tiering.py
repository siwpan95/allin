#!/usr/bin/env python3
"""tiering 权威源 -> facts.json.tiering 索引投影（A 期 Phase 3）。

权威源裁定：docs/事实源/tiering.yaml（由 bootstrap_legacy_yaml.py 从
组合分级决策索引.md 一次性抽取；MD 降级为人类可读孪生，二者同源维护）。
facts.json.tiering 是 tiering.yaml 的派生索引投影（带 source_file 指针），删了重建即得。

索引颗粒度（Q3）：仅 id(repo)/tier/domain/source_file —— 动作/归档目标/备注等详情留在 YAML。
零第三方依赖（仅标准库 + 可选 yaml）。退出码：0 干净 / 1 finding / 2 用法 / 3 环境。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "docs" / "事实源" / "tiering.yaml"
DEFAULT_DATA = ROOT / "facts" / "facts.json"
KEY = "tiering"
ID_FIELD = "repo"

# P2 #19：权威 YAML 读取收敛为 tools/facts/cli.py 唯一一份；本模块删除自写 _yaml_load。
# 在场但解析失败 → cli.yaml_load 抛 AuthUnavailable，调用方必须显式非 0（不得 SKIP 判绿）。
# 跨目录稳健：保证同目录 cli / exit_codes 可 import。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli import AuthUnavailable, yaml_load  # noqa: E402


def collect(auth: Path = AUTH) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    # P2 #19：yaml_load 四态 —— 缺席→None(SKIP)、在场解析失败→抛 AuthUnavailable
    # （由 main 转非 0）、正常→dict。绝不退化成「空索引 + 一条 warning」判绿。
    doc = yaml_load(auth)
    if doc is None:
        return [], [f"权威源不存在：{auth}"]
    rows = doc.get(KEY) or []
    if not rows:
        warnings.append("权威源无 tiering 条目")
    index = [{"repo": r[ID_FIELD], "tier": r.get("tier"), "domain": r.get("domain"),
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
    # P2 #19：在场但解析失败 → BLOCK + 可读诊断，绝不 SKIP 判绿（P1 #7 口径）。
    try:
        adoc = yaml_load(auth)
    except AuthUnavailable as exc:
        return EXIT_BLOCKING, [f"权威源在场但无法解析（不得判绿）：{auth} — {exc}"]
    if adoc is None:
        return EXIT_OK, ["SKIP(no auth)"]
    a_ids = {r[ID_FIELD] for r in (adoc.get(KEY) or []) if isinstance(r, dict) and r.get(ID_FIELD)}
    doc = json.loads(data.read_text(encoding="utf-8"))
    j_index = doc.get(KEY) or []
    j_ids = {r[ID_FIELD] for r in j_index if isinstance(r, dict) and r.get(ID_FIELD)}
    for k in sorted(a_ids - j_ids):
        findings.append(f"权威源有 {k} 但 facts.json.tiering 缺（投影滞后，未重新生成）")
    for k in sorted(j_ids - a_ids):
        findings.append(f"facts.json.tiering 有 {k} 但权威源缺（投影凭空多，真漂移）")
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-tiering-selftest-"))
    auth = root / "docs" / "事实源" / "tiering.yaml"
    auth.parent.mkdir(parents=True)
    auth.write_text("tiering:\n  - repo: a\n    seq: 1\n    tier: ①核心推进\n    domain: x\n"
                    "  - repo: b\n    seq: 2\n    tier: ②保留\n    domain: y\n", encoding="utf-8")
    data = root / "facts.json"
    data.write_text(json.dumps({"schema_version": "0.1.0", "machines": [], "facts": []}), encoding="utf-8")
    index, _ = collect(auth)
    write_index(data, index)
    rc_sync, _ = check_sync(data, auth)
    ok_sync = rc_sync == EXIT_OK
    # 注入漂移：facts 多一个 repo
    bad = json.loads(data.read_text(encoding="utf-8"))
    bad[KEY].append({"repo": "phantom", "tier": "③", "domain": "z",
                     "source_file": "docs/事实源/tiering.yaml"})
    data.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc_drift, _ = check_sync(data, auth)
    ok_drift = rc_drift == EXIT_BLOCKING
    ok = ok_sync and ok_drift and len(index) == 2
    print(json.dumps({"collect": len(index), "sync_clean": ok_sync, "drift_caught": ok_drift,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="tiering -> facts.json.tiering 索引投影")
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
            print(f"  {'SKIP' if m.startswith('SKIP') else 'BLOCK'} [tiering] {m}")
        print(f"tiering-sync: {'clean' if rc == EXIT_OK else 'blocking'} (exit={rc})")
        return rc
    try:
        index, warnings = collect(a.auth)
    except AuthUnavailable as exc:
        # P2 #19：权威源在场但读不出来，绝不打印空索引后 exit 0（判绿）。
        print(f"ENV ERROR: 权威源在场但无法解析，不得判绿：{a.auth} — {exc}", file=sys.stderr)
        return EXIT_ENV
    for w in warnings:
        print(f"  WARN {w}")
    if a.write:
        if not index:
            print(f"ENV ERROR: 权威源无条目：{a.auth}")
            return EXIT_ENV
        write_index(a.data, index)
        print(f"WROTE: facts.json.tiering={len(index)}（权威={a.auth}）")
        return EXIT_OK
    print(json.dumps(index, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
