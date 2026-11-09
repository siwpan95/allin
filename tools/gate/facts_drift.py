#!/usr/bin/env python3
"""facts-drift gate -- 意图态内部一致性漂移（独立门禁，g21 模式；蓝图 g26）。

判据：结构化真身 facts.json 与以下意图态数据源的双向一致性。
      全部离线可完成，不依赖运行态采集器（运行态属 D 期，见末尾说明）。

  * ports.yaml  <-> facts.json.ports           端口事实源 vs 集中真身
  * facts[].source_file:line 真实性           真身内部可信度（文件存在 / 行号有效 / 非空行）
  * Dolt 下游 state 的 source_git_sha == HEAD  溯源一致性（与 g25 互补：g25 验证可解析，本门禁验证 == 当前 HEAD）
  * 机器 md 目录数 vs facts.json.machines     轻量级计数一致

运行态（实际监听端口 / 进程 / 磁盘）采集需装采集 agent（SSH/WMI/PowerShell），属 D 期；
本门禁不覆盖、明确标注，避免把「运行态 vs 意图态漂移」伪装成已检。

零第三方依赖（仅标准库 + yaml + 复用 cli.load_json）。
退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # noqa: F401
except ImportError:
    yaml = None  # 仅 ports.yaml 判据需要；其他判据仍可用

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "facts"))
import cli as F  # noqa: E402

GATE = "facts-drift"
EXIT_OK, EXIT_BLOCKING, EXIT_ENV = 0, 1, 3
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "facts" / "facts.json"
DEFAULT_PORTS = ROOT / "docs" / "事实源" / "ports.yaml"
DEFAULT_STATE = ROOT / "deploy" / "dolt" / "state" / "last_import.json"


def git_head() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        return None
    return None


def git_rev_parse(ref: str) -> str | None:
    """展开成完整 40-hex（短哈希也能展开），失败返回 None。与 g25 解析口径一致。"""
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", ref],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        return None
    return None


def git_is_ancestor(a: str, b: str) -> bool | None:
    """a 是否为 b 的祖先（含相等）。None=无法判定（git 异常）。"""
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        if r.returncode == 0:
            return True
        if r.returncode == 1:
            return False
    except Exception:
        return None
    return None


def check_ports(data: Path, ports_yaml: Path, findings: list[str], infos: list[str]) -> dict:
    if not ports_yaml.is_file():
        return {"mode": "SKIPPED(no ports.yaml)"}
    if yaml is None:
        return {"mode": "SKIPPED(yaml 不可用)"}
    doc = F.load_json(data)
    ydoc = yaml.safe_load(ports_yaml.read_text(encoding="utf-8")) or {}
    y_ports = {p["port"]: p for p in (ydoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    j_ports = {p["port"]: p for p in doc.get("ports", []) if isinstance(p, dict) and "port" in p}
    # 方向性判据：facts.json.ports 必须是 ports.yaml 的子集（真身不得凭空多 Port）；
    # ports.yaml 多出的是 P0-A 迁移进行中的已知缺口，记 INFO 不阻断（A 完成后自动归零）。
    for k in sorted(set(j_ports) - set(y_ports)):
        findings.append(f"facts.json 有 port {k}（{j_ports[k].get('service')}）但 ports.yaml 缺（真身有 Port 无声明源）")
    for k in sorted(set(y_ports) - set(j_ports)):
        infos.append(f"ports.yaml 有 port {k}（{y_ports[k].get('service')}）但 facts.json 缺（待 P0-A 迁移）")
    for k in sorted(set(y_ports) & set(j_ports)):
        y, j = y_ports[k], j_ports[k]
        for field in ("service", "status"):  # owner 两者形态故意不同，不纳入判据
            if y.get(field) != j.get(field):
                findings.append(f"port {k} {field} 不一致：ports.yaml={y.get(field)!r} facts.json={j.get(field)!r}")
    return {"yaml_ports": len(y_ports), "json_ports": len(j_ports),
            "common": len(set(y_ports) & set(j_ports)),
            "facts_extra": len(set(j_ports) - set(y_ports)),
            "yaml_extra": len(set(y_ports) - set(j_ports))}


def check_source_lines(data: Path, root: Path, findings: list[str]) -> dict:
    doc = F.load_json(data)
    facts = doc.get("facts", [])
    bad = 0
    for f in facts:
        sf = f.get("source_file")
        sl = f.get("source_line")
        if not sf or not isinstance(sl, int):
            findings.append(f"{f.get('fact_id')} 缺 source_file/source_line")
            bad += 1
            continue
        target = root / sf
        if not target.is_file():
            findings.append(f"{f.get('fact_id')} source_file 不存在：{sf}")
            bad += 1
            continue
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if not (1 <= sl <= len(lines)):
            findings.append(f"{f.get('fact_id')} source_line 越界：{sf}#{sl}（共 {len(lines)} 行）")
            bad += 1
        elif not lines[sl - 1].strip():
            findings.append(f"{f.get('fact_id')} source_line 空行：{sf}#{sl}")
            bad += 1
    return {"facts_total": len(facts), "source_line_bad": bad}


def check_dolt_state(state: Path, head: str | None, findings: list[str], warnings: list[str]) -> dict:
    if not state.is_file():
        return {"mode": "SKIPPED(no dolt state)"}
    st = json.loads(state.read_text(encoding="utf-8"))
    sha = st.get("source_git_sha")
    if not sha:
        return {"mode": "SKIPPED(state 无 sha)"}
    # 与 g25 同源解析口径：短哈希也能展开为完整提交；解析不了才是真损坏。
    full = git_rev_parse(sha)
    if full is None:
        findings.append(f"Dolt state source_git_sha 无法解析为真实提交：{sha!r}")
        return {"state_sha": sha, "consistent": False}
    if head is None:
        return {"mode": "SKIPPED(no git HEAD)"}
    full_head = git_rev_parse("HEAD") or head
    if full == full_head:
        return {"state_sha": full[:8], "head": full_head[:8], "consistent": True}
    # 派生物（dolt 下游）可删可重建，不强行阻断；区分滞后/超前(均 WARN) 与分歧(BLOCK)。
    behind = git_is_ancestor(full, full_head)
    ahead = git_is_ancestor(full_head, full)
    if behind is True:
        warnings.append(f"Dolt state 滞后 HEAD：state.sha={full[:8]}… HEAD={full_head[:8]}…"
                        f"（派生物可删可重建，需重新 import_from_git --apply 刷新；不阻断）")
        return {"state_sha": full[:8], "head": full_head[:8], "consistent": False, "relation": "behind"}
    if ahead is True:
        warnings.append(f"Dolt state 超前 HEAD：state.sha={full[:8]}… HEAD={full_head[:8]}…"
                        f"（导入了较新提交，疑仓库被 rebase/force-update；需排查；不阻断）")
        return {"state_sha": full[:8], "head": full_head[:8], "consistent": False, "relation": "ahead"}
    if behind is None or ahead is None:
        warnings.append(f"Dolt state 与 HEAD 关系无法判定：state.sha={full[:8]}… HEAD={full_head[:8]}…"
                        f"（git 异常；如实 WARN 不阻断）")
        return {"state_sha": full[:8], "head": full_head[:8], "consistent": False, "relation": "unknown"}
    findings.append(f"Dolt state 与 HEAD 分歧：state.sha={full[:8]}… 与 HEAD={full_head[:8]}… 无祖先关系"
                    f"（疑从错误/历史外提交导入，需排查后重新导入）")
    return {"state_sha": full[:8], "head": full_head[:8], "consistent": False, "relation": "divergent"}


def check_machines(data: Path, root: Path, findings: list[str]) -> dict:
    doc = F.load_json(data)
    j_machines = {m.get("machine_id") for m in doc.get("machines", []) if m.get("machine_id")}
    md_dir = root / "docs" / "事实源" / "机器"
    md_machines = set()
    if md_dir.is_dir():
        for p in md_dir.iterdir():
            if p.is_dir() and (p / f"{p.name}.md").is_file():
                md_machines.add(p.name)
    for k in sorted(md_machines - j_machines):
        findings.append(f"机器 md 存在但 facts.json 缺：{k}")
    for k in sorted(j_machines - md_machines):
        findings.append(f"facts.json 有机器但无 md：{k}")
    return {"json_machines": len(j_machines), "md_machines": len(md_machines)}


def check_projects(data: Path, root: Path, findings: list[str]) -> dict:
    """facts.json.projects 索引投影 ⇄ platform/registry/projects/*.yaml 同步对账。

    无 yaml 依赖（只数 .yaml 文件 + 读 facts.json 的 JSON 数组）。
    派生物纪律：projects 缺失 → SKIP（可删可重建，不强制）；在场但不同步 → 真漂移 BLOCK。
    """
    registry = root / "platform" / "registry" / "projects"
    if not registry.is_dir():
        return {"mode": "SKIPPED(no registry)"}
    registry_stems = {p.stem for p in registry.glob("*.yaml")}
    if not registry_stems:
        return {"mode": "SKIPPED(empty registry)"}
    doc = F.load_json(data)
    projects = doc.get("projects")
    if not projects:
        return {"mode": "SKIPPED(no facts.projects — 派生物可删，不强制)"}
    fact_ids = {p.get("project_id") for p in projects}
    for k in sorted(registry_stems - fact_ids):
        findings.append(f"registry 有 {k} 但 facts.json.projects 缺（未重新生成投影）")
    for k in sorted(fact_ids - registry_stems):
        findings.append(f"facts.json.projects 有 {k} 但 registry 无（投影滞后/残留）")
    for p in projects:
        sf = p.get("source_file")
        if sf and not (root / sf).is_file():
            findings.append(f"{p.get('project_id')} source_file 不存在：{sf}")
    return {"registry": len(registry_stems), "facts_projects": len(projects)}


def check_ports_mirror(root: Path, findings: list[str]) -> dict:
    """platform/registry/ports.yaml 镜像 ⇄ docs/事实源/ports.yaml 权威：镜像必须是子集 + service 匹配。

    防双源漂移（A 期 Phase 2）：镜像若凭空多端口或与权威 service 不符，即双源复活。
    无 yaml / 镜像缺失 / 权威缺失 → SKIP（派生物纪律：镜像可删可重建，不强制）。
    """
    mirror = root / "platform" / "registry" / "ports.yaml"
    auth = root / "docs" / "事实源" / "ports.yaml"
    if not mirror.is_file():
        return {"mode": "SKIPPED(no mirror)"}
    if yaml is None:
        return {"mode": "SKIPPED(yaml 不可用)"}
    if not auth.is_file():
        return {"mode": "SKIPPED(no auth ports)"}
    mdoc = yaml.safe_load(mirror.read_text(encoding="utf-8")) or {}
    adoc = yaml.safe_load(auth.read_text(encoding="utf-8")) or {}
    m_ports = {p["port"]: p for p in (mdoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    a_ports = {p["port"]: p for p in (adoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    for k in sorted(set(m_ports) - set(a_ports)):
        findings.append(f"镜像 port {k} 但权威源缺（双源漂移：镜像凭空多端口）")
    for k in sorted(set(m_ports) & set(a_ports)):
        if m_ports[k].get("service") != a_ports[k].get("service"):
            findings.append(f"镜像 port {k} service 不一致：镜像={m_ports[k].get('service')!r} "
                            f"权威={a_ports[k].get('service')!r}（双源漂移）")
    return {"mirror_ports": len(m_ports), "auth_ports": len(a_ports),
            "divergent": len(set(m_ports) - set(a_ports))}


def run(data: Path, ports_yaml: Path, state: Path, root: Path = ROOT) -> int:
    if not data.is_file():
        print(f"ENV ERROR: 结构化真身不存在：{data}")
        return EXIT_ENV
    findings: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []
    head = git_head()
    p = check_ports(data, ports_yaml, findings, infos)
    s = check_source_lines(data, root, findings)
    d = check_dolt_state(state, head, findings, warnings)
    m = check_machines(data, root, findings)
    pr = check_projects(data, root, findings)
    pm = check_ports_mirror(root, findings)
    print(f"{GATE}: ports={p.get('mode', p)} | source_line={s} | dolt_state={d.get('mode', d)} "
          f"| machines={m} | projects={pr.get('mode', pr)} | ports_mirror={pm.get('mode', pm)}")
    for x in infos:
        print(f"  INFO {x}")
    for x in warnings:
        print(f"  WARN {x}")
    for x in findings:
        print(f"  BLOCK {x}")
    clean = not findings
    print(f"{GATE}: {'clean' if clean else 'blocking'} (exit={0 if clean else 1})")
    return EXIT_OK if clean else EXIT_BLOCKING


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-drift-selftest-"))
    data = F.DEFAULT_DATA
    bad = json.loads(json.dumps(F.load_json(data)))
    bad["ports"].append({"port": 99999, "service": "phantom", "owner": "/x", "segment": "x",
                         "status": "active", "observed_at": "2026-11-09",
                         "evidence_ref": "x", "machine_id": "SIWPAN"})
    badp = root / "bad.json"
    badp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    drift_caught = run(badp, DEFAULT_PORTS, DEFAULT_STATE, ROOT)
    clean = run(data, DEFAULT_PORTS, DEFAULT_STATE, ROOT)
    ok = drift_caught == EXIT_BLOCKING and clean == EXIT_OK
    print(json.dumps({"gate": GATE, "clean": clean, "drift_caught": drift_caught,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=GATE)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--ports", type=Path, default=DEFAULT_PORTS)
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rc = run(a.data, a.ports, a.state, a.root)
    if a.json:
        print(json.dumps({"gate": GATE, "data": str(a.data), "exit": rc}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
