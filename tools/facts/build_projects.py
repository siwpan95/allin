#!/usr/bin/env python3
"""registry -> facts.json.projects 索引投影生成器（A 期，P0 首项）。

设计纪律（与离线北极星 / 单源铁律一致）：
  * platform/registry/projects/*.yaml 是 145 个项目的**唯一权威**（声明态）。
  * 本脚本只生成 facts.json 的一个「索引投影」数组 projects[]：
        project_id / name / category / version / path / publish_repo / source_file
    其中 source_file 是回指 registry YAML 的溯源指针；项目的完整内容
    （launch / verify / note / manual）仍只存在于 registry YAML，**绝不搬进 facts.json**
    —— 整段复制才会制造「双源漂移」，正是 A 要消灭的。
  * facts.json.projects 是**可重建派生物**：删了重建即得，删了也不破任何门禁
    （g26 仅校验「facts.json.projects 与 registry 同步」；在场但不同步才记 finding）。
  * 规范：registry 文件名 stem 必须等于 YAML 内 id（注册表卫生不变量），
    生成器据此把 project_id 钉成 stem，避免事实源指针与文件名脱节。

零第三方依赖（仅标准库 + 可选 yaml）。退出码：0 干净 / 1 finding / 2 用法 / 3 环境。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "platform" / "registry" / "projects"
DEFAULT_DATA = ROOT / "facts" / "facts.json"


def _yaml_load(path: Path) -> dict | None:
    try:
        import yaml  # 仅本生成器需要；门禁侧用无 yaml 的轻量对账，不依赖它
    except ImportError:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def collect(registry: Path = REGISTRY) -> tuple[list[dict], list[str]]:
    """读 registry 生成索引投影。返回 (projects, warnings)。yaml 缺失时 projects 为空。"""
    projects: list[dict] = []
    warnings: list[str] = []
    if not registry.is_dir():
        return projects, [f"registry 目录不存在：{registry}"]
    for p in sorted(registry.glob("*.yaml")):
        stem = p.stem
        doc = _yaml_load(p)
        if doc is None:
            warnings.append(f"{p.name}: 无法解析（缺 yaml 或语法错）")
            continue
        yid = doc.get("id")
        if yid and yid != stem:
            warnings.append(f"{p.name}: YAML id={yid!r} 不等于文件名 stem={stem!r}（卫生不变量破坏）")
        pub = doc.get("publish") or {}
        projects.append({
            "project_id": stem,
            "name": doc.get("name", stem),
            "category": doc.get("category", "unknown"),
            "version": doc.get("version"),
            "path": doc.get("path"),
            "publish_repo": pub.get("repo") if isinstance(pub, dict) else None,
            "source_file": f"platform/registry/projects/{p.name}",
        })
    return projects, warnings


def write_projects(data: Path, projects: list[dict]) -> int:
    doc = json.loads(data.read_text(encoding="utf-8"))
    doc["projects"] = projects
    data.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK


def check_sync(data: Path, registry: Path = REGISTRY, root: Path = ROOT) -> tuple[int, list[str]]:
    """facts.json.projects 与 registry 同步对账（无 yaml 依赖）。root 用于解析 source_file。"""
    findings: list[str] = []
    if not registry.is_dir():
        return EXIT_OK, ["SKIP(no registry dir)"]
    registry_stems = {p.stem for p in registry.glob("*.yaml")}
    if not registry_stems:
        return EXIT_OK, ["SKIP(empty registry)"]
    doc = json.loads(data.read_text(encoding="utf-8"))
    projects = doc.get("projects")
    if not projects:
        return EXIT_OK, ["SKIP(no facts.projects — 派生物可删，不强制)"]
    ids = [p.get("project_id") for p in projects]
    fact_ids = set(ids)
    missing = sorted(registry_stems - fact_ids)
    extra = sorted(fact_ids - registry_stems)
    for k in missing:
        findings.append(f"registry 有 {k} 但 facts.json.projects 缺（未重新生成投影）")
    for k in extra:
        findings.append(f"facts.json.projects 有 {k} 但 registry 无（投影滞后/残留）")
    for p in projects:
        sf = p.get("source_file")
        if sf and not (root / sf).is_file():
            findings.append(f"{p.get('project_id')} source_file 不存在：{sf}")
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-projects-selftest-"))
    reg = root / "platform" / "registry" / "projects"
    reg.mkdir(parents=True)
    (reg / "alpha.yaml").write_text("id: alpha\nname: Alpha\ncategory: tool\n", encoding="utf-8")
    (reg / "beta.yaml").write_text("id: beta\nname: Beta\ncategory: game\n", encoding="utf-8")
    data = root / "facts.json"
    data.write_text(json.dumps({"schema_version": "0.1.0", "generated_at": "x",
                                "machines": [], "facts": []}), encoding="utf-8")
    projs, warns = collect(reg)
    ok_collect = len(projs) == 2 and {p["project_id"] for p in projs} == {"alpha", "beta"}
    write_projects(data, projs)
    rc_sync, _ = check_sync(data, reg, root)
    ok_sync = rc_sync == EXIT_OK
    # 注入漂移：删一个 registry 文件后重建 facts 不更新
    (reg / "beta.yaml").unlink()
    rc_drift, _ = check_sync(data, reg)
    ok_drift = rc_drift == EXIT_BLOCKING
    ok = ok_collect and ok_sync and ok_drift
    print(json.dumps({"collect": ok_collect, "sync_clean": ok_sync, "drift_caught": ok_drift,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="registry -> facts.json.projects 索引投影")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--write", action="store_true", help="把索引投影写回 facts.json.projects")
    ap.add_argument("--check", action="store_true", help="仅校验同步，不写")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check:
        rc, msgs = check_sync(a.data, a.registry)
        for m in msgs:
            print(f"  {'SKIP' if m.startswith('SKIP') else 'BLOCK'} {m}")
        print(f"projects-sync: {'clean' if rc == EXIT_OK else 'blocking'} (exit={rc})")
        return rc
    # 默认：收集并打印，按需 --write
    projects, warnings = collect(a.registry)
    for w in warnings:
        print(f"  WARN {w}")
    if a.write:
        if not projects and not a.registry.is_dir():
            print(f"ENV ERROR: registry 不存在：{a.registry}")
            return EXIT_ENV
        write_projects(a.data, projects)
        print(f"WROTE: {len(projects)} 个 project 索引 -> {a.data}")
        return EXIT_OK
    print(json.dumps(projects, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
