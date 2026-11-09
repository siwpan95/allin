#!/usr/bin/env python3
"""ports 权威源 -> facts.json.ports 索引投影 + platform/registry/ports.yaml 镜像（A 期 Phase 2）。

权威源裁定（实测，见 docs/记录/交接/A-全域迁移执行方案.md Q2）：
  * docs/事实源/ports.yaml 是端口的**唯一事实源**（机器可读版；人类可读孪生为 端口分配表.md）。
  * platform/registry/ports.yaml 经实测仅为「回退默认 / 重建自 projects 的 4 端口 stub」，非权威；
    本脚本将其**重建为 docs/事实源/ports.yaml 的可重建镜像**（消灭双源：只有 docs 一份被手改）。
  * facts.json.ports 改为 docs/事实源/ports.yaml 的派生索引投影（带 source_file），删掉「第三份手改源」。

纪律：docs/事实源/ports.yaml 是唯一被手改的源；另两份由本脚本重建，删了重建即得（离线北极星）。
零第三方依赖（仅标准库 + 可选 yaml）。退出码：0 干净 / 1 finding / 2 用法 / 3 环境。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV = 0, 1, 2,3
ROOT = Path(__file__).resolve().parents[2]
AUTH_PORTS = ROOT / "docs" / "事实源" / "ports.yaml"
MIRROR = ROOT / "platform" / "registry" / "ports.yaml"
DEFAULT_DATA = ROOT / "facts" / "facts.json"


def _yaml_load(path: Path) -> dict | None:
    try:
        import yaml
    except ImportError:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def collect_ports(auth: Path = AUTH_PORTS) -> tuple[list[dict], list[str]]:
    """读权威源，返回 (port 行, warnings)。"""
    warnings: list[str] = []
    if not auth.is_file():
        return [], [f"权威端口源不存在：{auth}"]
    doc = _yaml_load(auth)
    if doc is None:
        return [], [f"权威端口源无法解析（缺 yaml 或语法错）：{auth}"]
    ports = [p for p in (doc.get("ports") or []) if isinstance(p, dict) and "port" in p]
    if not ports:
        warnings.append("权威端口源无 ports 条目")
    # observed_at 取 change_log 最新日期（无则生成日）
    obs = "2026-11-09"
    for c in (doc.get("change_log") or []):
        d = c.get("date")
        if isinstance(d, str) and d > obs:
            obs = d
    proj = []
    for p in ports:
        proj.append({
            "port": p["port"],
            "service": p.get("service"),
            "owner": p.get("owner"),
            "status": p.get("status", "unknown"),
            "observed_at": obs,
            "evidence_ref": "docs/事实源/ports.yaml",
            "source_file": "docs/事实源/ports.yaml",
        })
    return proj, warnings


def write_facts_ports(data: Path, ports: list[dict]) -> int:
    doc = json.loads(data.read_text(encoding="utf-8"))
    doc["ports"] = ports
    data.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return EXIT_OK


def write_mirror(mirror: Path, ports: list[dict]) -> int:
    try:
        import yaml
    except ImportError:
        print(f"ENV ERROR: 写镜像需 yaml，但解释器缺 PyYAML：{mirror}")
        return EXIT_ENV
    mirror.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"port": p["port"], "service": p["service"], "owner": p.get("owner"),
                "status": p.get("status")} for p in ports]
    header = ("# ports 镜像（可重建派生物）：由 tools/facts/build_ports.py 从 docs/事实源/ports.yaml 重建。\n"
              "# 唯一被手改的端口源是 docs/事实源/ports.yaml；本文件删了重建即得，勿手改。\n")
    text = header + yaml.safe_dump({"ports": payload}, sort_keys=False, allow_unicode=True, default_flow_style=False)
    mirror.write_text(text, encoding="utf-8")
    return EXIT_OK


def check_sync(data: Path, auth: Path = AUTH_PORTS) -> tuple[int, list[str]]:
    """facts.json.ports ⇔ 权威源 同步（facts 必须是子集；多出即真漂移）。"""
    findings: list[str] = []
    if not auth.is_file():
        return EXIT_OK, ["SKIP(no auth ports)"]
    adoc = _yaml_load(auth)
    if adoc is None:
        return EXIT_OK, ["SKIP(auth unpar.able)"]
    a_ports = {p["port"]: p for p in (adoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    doc = json.loads(data.read_text(encoding="utf-8"))
    j_ports = {p["port"]: p for p in doc.get("ports", []) if isinstance(p, dict) and "port" in p}
    if not j_ports:
        return EXIT_OK, ["SKIP(no facts.ports — 派生物可删，不强制)"]
    for k in sorted(set(j_ports) - set(a_ports)):
        findings.append(f"facts.json 有 port {k} 但权威源缺（投影凭空多端口，真漂移）")
    for k in sorted(set(j_ports) & set(a_ports)):
        for field in ("service", "status"):
            if j_ports[k].get(field) != a_ports[k].get(field):
                findings.append(f"port {k} {field} 不一致：facts={j_ports[k].get(field)!r} 权威={a_ports[k].get(field)!r}")
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def check_mirror(mirror: Path, auth: Path = AUTH_PORTS) -> tuple[int, list[str]]:
    """platform/registry/ports.yaml ⇔ 权威源：镜像必须是子集 + service 匹配（防双源漂移）。"""
    findings: list[str] = []
    if not mirror.is_file():
        return EXIT_OK, ["SKIP(no mirror)"]
    if not auth.is_file():
        return EXIT_OK, ["SKIP(no auth ports)"]
    mdoc = _yaml_load(mirror)
    adoc = _yaml_load(auth)
    if mdoc is None or adoc is None:
        return EXIT_OK, ["SKIP(mirror/auth 不可解析)"]
    m_ports = {p["port"]: p for p in (mdoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    a_ports = {p["port"]: p for p in (adoc.get("ports") or []) if isinstance(p, dict) and "port" in p}
    if not m_ports:
        return EXIT_OK, ["SKIP(empty mirror)"]
    for k in sorted(set(m_ports) - set(a_ports)):
        findings.append(f"镜像有 port {k} 但权威源缺（双源漂移：镜像凭空多端口）")
    for k in sorted(set(m_ports) & set(a_ports)):
        if m_ports[k].get("service") != a_ports[k].get("service"):
            findings.append(f"镜像 port {k} service 不一致：镜像={m_ports[k].get('service')!r} 权威={a_ports[k].get('service')!r}（双源漂移）")
    return (EXIT_BLOCKING if findings else EXIT_OK), findings


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-ports-selftest-"))
    auth = root / "docs" / "事实源" / "ports.yaml"
    auth.parent.mkdir(parents=True)
    auth.write_text("ports:\n  - port: 8000\n    service: radio-panel\n    owner: /a\n    status: active\n"
                    "  - port: 8010\n    service: mixer-stream\n    owner: /b\n    status: active\n"
                    "change_log:\n  - date: 2026-11-01\n    change: x\n", encoding="utf-8")
    data = root / "facts.json"
    data.write_text(json.dumps({"schema_version": "0.1.0", "generated_at": "x", "machines": [], "facts": []}), encoding="utf-8")
    mirror = root / "platform" / "registry" / "ports.yaml"
    mirror.parent.mkdir(parents=True)
    # 干净：facts + mirror 都从 auth 重建
    ports, _ = collect_ports(auth)
    write_facts_ports(data, ports)
    write_mirror(mirror, ports)
    rc_s, _ = check_sync(data, auth)
    rc_m, _ = check_mirror(mirror, auth)
    ok_sync = rc_s == EXIT_OK and rc_m == EXIT_OK
    # 注入漂移：给 facts 多一个端口
    bad = json.loads(data.read_text(encoding="utf-8"))
    bad["ports"].append({"port": 99999, "service": "phantom", "owner": "/x", "status": "active",
                         "observed_at": "2026-11-09", "evidence_ref": "docs/事实源/ports.yaml",
                         "source_file": "docs/事实源/ports.yaml"})
    data.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc_drift, _ = check_sync(data, auth)
    ok_drift = rc_drift == EXIT_BLOCKING
    ok = ok_sync and ok_drift and len(ports) == 2
    print(json.dumps({"collect": len(ports), "sync_clean": ok_sync, "drift_caught": ok_drift,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ports 权威源 -> facts.json.ports + 镜像")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--auth", type=Path, default=AUTH_PORTS)
    ap.add_argument("--mirror", type=Path, default=MIRROR)
    ap.add_argument("--write", action="store_true", help="重建 facts.json.ports 与镜像")
    ap.add_argument("--check", action="store_true", help="仅校验同步，不写")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check:
        rc1, f1 = check_sync(a.data, a.auth)
        rc2, f2 = check_mirror(a.mirror, a.auth)
        for m in f1:
            print(f"  {'SKIP' if m.startswith('SKIP') else 'BLOCK'} [facts] {m}")
        for m in f2:
            print(f"  {'SKIP' if m.startswith('SKIP') else 'BLOCK'} [mirror] {m}")
        both = (rc1 == EXIT_OK) and (rc2 == EXIT_OK)
        print(f"ports-sync: {'clean' if both else 'blocking'} (facts={rc1} mirror={rc2})")
        return EXIT_OK if both else EXIT_BLOCKING
    # 默认收集并打印；--write 才落盘
    ports, warnings = collect_ports(a.auth)
    for w in warnings:
        print(f"  WARN {w}")
    if a.write:
        if not ports:
            print(f"ENV ERROR: 权威源无端口：{a.auth}")
            return EXIT_ENV
        write_facts_ports(a.data, ports)
        write_mirror(a.mirror, ports)
        print(f"WROTE: facts.json.ports={len(ports)} + 镜像 {a.mirror}（权威={a.auth}）")
        return EXIT_OK
    print(json.dumps(ports, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
