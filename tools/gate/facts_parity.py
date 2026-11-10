#!/usr/bin/env python3
"""facts-parity gate -- 结构化真身引用完整性 + 生成物漂移（独立门禁，g21 模式）。

判据分两层，都要如实报态，不把「没检查」冒充「通过」：
  * 主判据（启用）：facts.json 的 doc_refs[].path 必须解析到真实文件；
    generated=true 的条目登记为「生成物引用」并计数，其对应 {machine_id}.facts.md
    在生成物在场时须齐备（见次判据完备性检查）。
  * 次判据（生成物目录在位即阻断，无开关）：生成区 marker 哈希 ⇄ facts.json 一致性，
    且每个 generated=true doc_ref 须有对应生成物（完备性）。
    「A 全域迁移真身反转」（派生索引投影，P0-A 三 Phase 已收口）前置条件已满足，
    故本判据为**全量启用**态：生成物一旦出现在仓库即刻进入阻断态，无需任何额外配置；
    目录缺席时显式 SKIPPED（离线北极星允许派生物缺失，render 后即被即时阻断），不把跑批拖红。

判据只有一份：哈希与解析全部复用 tools/facts/cli.py，禁止在这里写第二套。
零第三方依赖。退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "facts"))
import cli as F  # noqa: E402

GATE = "facts-parity"
EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GENERATED = ROOT / "facts" / "generated"


def run(data: Path, generated_dir: Path, root: Path = ROOT) -> int:
    if not data.is_file():
        print(f"ENV ERROR: 结构化真身不存在：{data}")
        return EXIT_ENV
    doc = F.load_json(data)
    refs = doc.get("doc_refs", [])
    findings = []
    # 深度审计 #16：doc_refs 可能被手工改坏或由生成器写坏。裸下标（r["path"]）
    # 会把「数据损坏」升级成 KeyError/TypeError 崩溃，既丢结构化 finding，又让
    # 门禁以 traceback 代替判红。先逐条校验，把坏条目转成结构化 finding，只让
    # 合法条目进入解析链；下方 doc_refs / missing 的计数口径保持不变。
    if not isinstance(refs, list):
        findings.append(f"doc_refs 结构损坏：期望 list，实为 {type(refs).__name__}")
        refs = []
    valid = []
    for i, r in enumerate(refs):
        if not isinstance(r, dict):
            findings.append(f"doc_ref <#{i}> 结构损坏：条目非 mapping（{type(r).__name__}）")
            continue
        path = r.get("path")
        if not isinstance(path, str) or not path:
            findings.append(
                f"doc_ref {r.get('doc_id', '<#%d>' % i)} 结构损坏：缺 path / path 非字符串")
            continue
        valid.append(r)

    for r in valid:
        target = root / r["path"]
        if not target.is_file():
            findings.append(f"doc_ref {r.get('doc_id')} 指向不存在的文件：{r['path']}")
    pending = [r for r in valid if r.get("generated")]

    generated_files = sorted(generated_dir.glob("*.facts.md")) if generated_dir.is_dir() else []
    if generated_files:
        # 真身反转（P0-A 派生索引投影）已收口 ⇒ g23 进入全量阻断态：
        # 既查在场生成物的 marker 漂移，也查 generated=true 引用是否齐备对应生成物（完备性）。
        names = {f.name for f in generated_files}
        for f in generated_files:
            mid = f.name[: -len(".facts.md")]
            expected = F.expected_hash(doc, mid)
            found = F.MARKER.search(f.read_text(encoding="utf-8"))
            if not found:
                findings.append(f"{f.name}: 缺 FACTS-GENERATED marker")
            elif found.group(1) != expected:
                findings.append(f"{f.name}: 漂移 marker={found.group(1)} expected={expected}")
        # 完备性：每个 generated=true 的 doc_ref 必须存在对应 {machine_id}.facts.md
        for r in pending:
            mid = Path(r["path"]).parent.name
            expect = f"{mid}.facts.md"
            if expect not in names:
                findings.append(f"generated doc_ref {r.get('doc_id')} 缺对应生成物 {expect}（render 后需重建）")
        parity_mode = f"active({len(generated_files)} 份, 完备性已查)"
    else:
        # 派生物缺位：离线北极星允许缺失（render 后即被 g23 即时阻断）；
        # 「A 全域迁移真身反转」前置条件已于 P0-A 收口满足，此处仅因派生物未生成而 SKIP，不冒充通过。
        parity_mode = "SKIPPED(派生物未生成；真身反转已完成，render 后即时启用阻断)"

    print(f"{GATE}: doc_refs={len(refs)} missing={len([x for x in findings if x.startswith('doc_ref')])} "
          f"| generated_pending={len(pending)} | marker_parity={parity_mode}")
    for x in findings:
        print(f"  BLOCK {x}")
    print(f"{GATE}: {'clean' if not findings else 'blocking'} (exit={0 if not findings else 1})")
    return EXIT_OK if not findings else EXIT_BLOCKING


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-parity-selftest-"))
    data = F.DEFAULT_DATA
    doc = F.load_json(data)
    outdir = root / "generated"

    clean = run(data, outdir, ROOT)
    broken = json.loads(json.dumps(doc))
    broken["doc_refs"][0]["path"] = "docs/definitely-missing-xyz.md"
    badp = root / "bad.json"
    badp.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    caught_bad_ref = run(badp, outdir, ROOT)

    # 深度审计 #16：结构损坏注入 —— 三条均须结构化判红（EXIT_BLOCKING）且不抛异常。
    # 放在 cmd_render 之前，此时 outdir 为空，避免生成物完备性分支干扰判定。
    injections = [
        ("refs 非 list", lambda d: d.__setitem__("doc_refs", {"oops": 1})),
        ("某 ref 缺 path", lambda d: d["doc_refs"][0].pop("path", None)),
        ("某 ref 是字符串", lambda d: d["doc_refs"].__setitem__(0, "not-a-mapping")),
    ]
    inject_results = {}
    for idx, (name, mutate) in enumerate(injections):
        broken = json.loads(json.dumps(doc))
        mutate(broken)
        p = root / ("inject_%d.json" % idx)
        p.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        try:
            inject_results[name] = run(p, outdir, ROOT)
        except Exception as e:  # noqa: BLE001 - 注入用例把「抛异常」也记为失败
            inject_results[name] = -1
            print(f"  [selftest] 注入 {name} 抛异常：{type(e).__name__}: {e}")
    inject_ok = all(v == EXIT_BLOCKING for v in inject_results.values())

    F.cmd_render(data, outdir, check=False)
    with_generated = run(data, outdir, ROOT)
    target = outdir / "SIWPAN.facts.md"
    target.write_text(F.MARKER.sub("<!-- FACTS-GENERATED:START sha256:0000000000000000 -->",
                                  target.read_text(encoding="utf-8")), encoding="utf-8")
    drift = run(data, outdir, ROOT)
    # 完备性：删掉 generated=true 引用(SIWPAN)对应的生成物 → 应 BLOCK
    target.unlink()
    missing_artifact = run(data, outdir, ROOT)
    F.cmd_render(data, outdir, check=False)  # 还原，便于临时目录回收

    ok = (clean == EXIT_OK and caught_bad_ref == EXIT_BLOCKING
          and with_generated == EXIT_OK and drift == EXIT_BLOCKING
          and missing_artifact == EXIT_BLOCKING and inject_ok)
    print(json.dumps({"gate": GATE, "clean": clean, "bad_doc_ref": caught_bad_ref,
                      "marker_active": with_generated, "marker_drift": drift,
                      "completeness_missing": missing_artifact,
                      "structure_injections": inject_results,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=GATE)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--data", type=Path, default=F.DEFAULT_DATA)
    ap.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rc = run(a.data, a.generated_dir, a.root)
    if a.json:
        print(json.dumps({"gate": GATE, "data": str(a.data),
                          "generated_dir": str(a.generated_dir), "exit": rc}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
