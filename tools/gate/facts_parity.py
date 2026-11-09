#!/usr/bin/env python3
"""facts-parity gate -- 结构化真身引用完整性 + 生成物漂移（独立门禁，g21 模式）。

判据分两层，都要如实报态，不把「没检查」冒充「通过」：
  * 主判据（本期启用）：facts.json 的 doc_refs[].path 必须解析到真实文件；
    generated=true 的条目登记为「待启用生成物」并计数（A 全域迁移真身反转后启用）。
  * 次判据（生成物目录在位即阻断，无开关）：生成区 marker 哈希 ⇄ facts.json 一致性；
    目录缺席时显式 SKIPPED 并标注「待 A 真身反转后启用」，登记在交接卷台账，不把跑批拖红。
    —— 即解除 P2 延迟：生成物一旦出现在仓库，本门禁即刻进入阻断态，无需任何额外配置。

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
    for r in refs:
        target = root / r["path"]
        if not target.is_file():
            findings.append(f"doc_ref {r.get('doc_id')} 指向不存在的文件：{r['path']}")
    pending = [r for r in refs if r.get("generated")]

    generated_files = sorted(generated_dir.glob("*.facts.md")) if generated_dir.is_dir() else []
    if generated_files:
        for f in generated_files:
            mid = f.name[: -len(".facts.md")]
            expected = F.expected_hash(doc, mid)
            found = F.MARKER.search(f.read_text(encoding="utf-8"))
            if not found:
                findings.append(f"{f.name}: 缺 FACTS-GENERATED marker")
            elif found.group(1) != expected:
                findings.append(f"{f.name}: 漂移 marker={found.group(1)} expected={expected}")
        parity_mode = f"active({len(generated_files)} 份)"
    else:
        parity_mode = "SKIPPED(生成物未启用，待 A 全域迁移真身反转后启用；生成物在场即刻阻断)"

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

    F.cmd_render(data, outdir, check=False)
    with_generated = run(data, outdir, ROOT)
    target = outdir / "SIWPAN.facts.md"
    target.write_text(F.MARKER.sub("<!-- FACTS-GENERATED:START sha256:0000000000000000 -->",
                                  target.read_text(encoding="utf-8")), encoding="utf-8")
    drift = run(data, outdir, ROOT)

    ok = (clean == EXIT_OK and caught_bad_ref == EXIT_BLOCKING
          and with_generated == EXIT_OK and drift == EXIT_BLOCKING)
    print(json.dumps({"gate": GATE, "clean": clean, "bad_doc_ref": caught_bad_ref,
                      "marker_active": with_generated, "marker_drift": drift,
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
