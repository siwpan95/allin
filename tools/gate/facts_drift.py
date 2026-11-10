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
from functools import lru_cache
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


@lru_cache(maxsize=8)
def _parse_facts_text(raw: str) -> dict:
    """M-7：facts.json 内容级缓存 —— 同一份文本只做一次 json.loads。

    `run()` 会依次跑 6 个判据，每个都重新解析一遍 88 KB 的 facts.json。
    缓存键取**文件内容本身**而非 mtime/size：自检会用同路径、相近尺寸覆盖
    注入坏数据，元数据键有返回陈旧结果的风险；内容键天然免疫这类误判。
    """
    return json.loads(raw)


def load_facts(data: Path) -> dict:
    """与 F.load_json 等价的错误语义（RuntimeError 包装），但走内容级缓存。

    返回的 dict 由调用方只读使用（本模块 6 个判据均只读）；注入坏数据的
    selftest 用 json.loads(json.dumps(...)) 自行深拷贝后再改。
    """
    try:
        raw = data.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"读取失败 {data}: {exc}") from exc
    try:
        return _parse_facts_text(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"读取失败 {data}: {exc}") from exc


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
    doc = load_facts(data)
    # H-3：此前这里裸调 yaml.safe_load，权威端口源写坏会抛 ParserError 直接崩溃；
    # 与 check_index_sync 的「静默 SKIP」正好构成同一文件内两种相反口径。统一为
    # 在场但解析失败 → BLOCK（可读诊断 + 非 0 退出），不崩溃、也不假装没检查。
    try:
        ydoc = yaml.safe_load(ports_yaml.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        findings.append(f"ports.yaml 权威源在场但解析失败，不得判绿：{ports_yaml} — {type(exc).__name__}: {exc}")
        return {"mode": "BLOCK(auth parse failed)"}
    if not isinstance(ydoc, dict):
        findings.append(f"ports.yaml 顶层不是 mapping：{ports_yaml}（{type(ydoc).__name__}）")
        return {"mode": "BLOCK(auth parse failed)"}
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
    doc = load_facts(data)
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
    # H-3 同口径：在场但读不出来是数据损坏，不是「没有这份派生物」。
    try:
        st = json.loads(state.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append(f"Dolt state 在场但解析失败，不得判绿：{state} — {type(exc).__name__}: {exc}")
        return {"mode": "BLOCK(state parse failed)"}
    if not isinstance(st, dict):
        findings.append(f"Dolt state 顶层不是对象：{state}（{type(st).__name__}）")
        return {"mode": "BLOCK(state parse failed)"}
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
    doc = load_facts(data)
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
    doc = load_facts(data)
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


def _load_yaml_list(path: Path, key: str):
    """加载权威 YAML 索引源；三种「不可用」必须可区分。

    2026-11-10 深度审计 H-3：此前 ``except Exception: return None`` 把
    「YAML 写坏了」与「文件不存在」混成同一个 ``None``，调用方按「文件不存在」
    记 ``SKIPPED(no auth)`` —— 权威源损坏这种本该红灯的状态被当成「没检查」
    静默放过，facts.json 投影滞后/凭空多的漂移判据随之整组失效。

    Returns:
        list            正常（可为空列表）
        None            文件不存在 → 调用方可 SKIP（派生物纪律：源可删可重建）
        "NO_YAML"       PyYAML 未安装 → 环境能力缺失，由调用方显式留痕
        "PARSE_FAILED:…" 文件在场但解析失败 / 结构不对 → 调用方**必须 BLOCK**
    """
    if not path.is_file():
        return None
    if yaml is None:
        return "NO_YAML"
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return f"PARSE_FAILED:{type(exc).__name__}: {exc}"
    if not isinstance(doc, dict):
        return f"PARSE_FAILED:顶层不是 mapping（{type(doc).__name__}）"
    rows = doc.get(key) or []
    if not isinstance(rows, list):
        return f"PARSE_FAILED:{key} 不是列表（{type(rows).__name__}）"
    return rows


def check_index_sync(data: Path, root: Path, findings: list[str], *,
                     name: str, auth_rel: str, key: str, id_field: str) -> dict:
    """facts.json.<key> 索引投影 ⇄ docs/事实源/<auth_rel> 同步（双向：权威缺失/投影多出均 BLOCK）。

    与 check_projects 同纪律：权威源（YAML）是 Git 内唯一被手改的机器可读源；facts.json.<key>
    是派生索引投影（删了重建即得）。投影滞后（权威有、facts 缺）→ BLOCK；投影凭空多（facts 有、权威缺）→ BLOCK。
    """
    auth = root / auth_rel
    rows = _load_yaml_list(auth, key)
    if rows is None:
        return {"mode": f"SKIPPED(no {name} auth)"}
    if rows == "NO_YAML":
        return {"mode": "SKIPPED(yaml 不可用)"}
    if isinstance(rows, str) and rows.startswith("PARSE_FAILED:"):
        # H-3：权威源在场却读不出内容 = 数据损坏，绝不能降级成「没这个文件」。
        detail = rows.split(":", 1)[1]
        findings.append(f"{name} 权威源在场但解析失败，不得判绿：{auth_rel} — {detail}")
        return {"mode": "BLOCK(auth parse failed)"}
    a_ids = {r.get(id_field) for r in rows if isinstance(r, dict) and r.get(id_field)}
    doc = load_facts(data)
    j_index = doc.get(key) or []
    j_ids = {r.get(id_field) for r in j_index if isinstance(r, dict) and r.get(id_field)}
    for k in sorted(a_ids - j_ids):
        findings.append(f"{name} 权威源有 {k} 但 facts.json.{key} 缺（投影滞后，未重新生成）")
    for k in sorted(j_ids - a_ids):
        findings.append(f"facts.json.{key} 有 {k} 但权威源缺（投影凭空多，真漂移）")
    return {"auth": len(a_ids), "facts": len(j_ids)}


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
    # H-3：镜像与权威源都在场，任一读不出来都属数据损坏，统一 BLOCK 而不是
    # 裸抛 ParserError 或静默 SKIP（「双源对账没跑」不能算通过）。
    try:
        mdoc = yaml.safe_load(mirror.read_text(encoding="utf-8")) or {}
        adoc = yaml.safe_load(auth.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        findings.append(f"ports 镜像/权威源在场但解析失败，不得判绿：{type(exc).__name__}: {exc}")
        return {"mode": "BLOCK(ports parse failed)"}
    if not isinstance(mdoc, dict) or not isinstance(adoc, dict):
        findings.append(f"ports 镜像/权威源顶层不是 mapping：mirror={type(mdoc).__name__} auth={type(adoc).__name__}")
        return {"mode": "BLOCK(ports parse failed)"}
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
    ti = check_index_sync(data, root, findings, name="tiering", auth_rel="docs/事实源/tiering.yaml", key="tiering", id_field="repo")
    to = check_index_sync(data, root, findings, name="tools", auth_rel="docs/事实源/tools.yaml", key="tools", id_field="tool")
    li = check_index_sync(data, root, findings, name="licenses", auth_rel="docs/事实源/licenses.yaml", key="licenses", id_field="dir")
    print(f"{GATE}: ports={p.get('mode', p)} | source_line={s} | dolt_state={d.get('mode', d)} "
          f"| machines={m} | projects={pr.get('mode', pr)} | ports_mirror={pm.get('mode', pm)} "
          f"| tiering={ti.get('mode', ti)} | tools={to.get('mode', to)} | licenses={li.get('mode', li)}")
    for x in infos:
        print(f"  INFO {x}")
    for x in warnings:
        print(f"  WARN {x}")
    for x in findings:
        print(f"  BLOCK {x}")
    clean = not findings
    print(f"{GATE}: {'clean' if clean else 'blocking'} (exit={0 if clean else 1})")
    return EXIT_OK if clean else EXIT_BLOCKING


def _selftest_bad_auth() -> bool:
    """H-3 回归：把权威 tiering.yaml 写成语法错误，run() 必须非 0。

    修复前的实测行为：``_load_yaml_list`` 返回 None ⇒ ``check_index_sync`` 记
    ``SKIPPED(no tiering auth)`` ⇒ findings 为空 ⇒ ``run()`` 返回 0。这个夹具把
    「权威源损坏却判绿」钉成一条可重复执行的失败用例。
    """
    import shutil
    import tempfile
    if yaml is None:
        # 无 PyYAML 时连「解析失败」都构造不出来（会走 NO_YAML 分支）；如实标注，
        # 既不算自证通过也不制造无依赖环境上的假红。
        print("  H-3 坏权威源注入：跳过（本机无 PyYAML，无法构造解析失败）")
        return True
    root = Path(tempfile.mkdtemp(prefix="allin-drift-badauth-"))
    try:
        data = root / "facts.json"
        empty_facts = json.dumps({"ports": [], "facts": [], "machines": [],
                                  "projects": [], "tiering": [], "tools": [], "licenses": []})
        # g09-python-hygiene 按行检查文本 I/O：write_text 与 encoding 必须同一行。
        data.write_text(empty_facts, encoding="utf-8")
        auth = root / "docs" / "事实源" / "tiering.yaml"
        auth.parent.mkdir(parents=True)
        auth.write_text("tiering: [ { repo: [unclosed\n  bad: : :\n", encoding="utf-8")
        rc = run(data, root / "no-ports.yaml", root / "no-state.json", root)
        caught = rc != EXIT_OK
        print(f"  H-3 坏权威源注入：run exit={rc}（期望非 0），caught={caught}")
        return caught
    finally:
        shutil.rmtree(root, ignore_errors=True)


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-drift-selftest-"))
    data = F.DEFAULT_DATA
    bad = json.loads(json.dumps(load_facts(data)))
    bad["ports"].append({"port": 99999, "service": "phantom", "owner": "/x", "segment": "x",
                         "status": "active", "observed_at": "2026-11-09",
                         "evidence_ref": "x", "machine_id": "SIWPAN"})
    badp = root / "bad.json"
    badp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    drift_caught = run(badp, DEFAULT_PORTS, DEFAULT_STATE, ROOT)
    clean = run(data, DEFAULT_PORTS, DEFAULT_STATE, ROOT)
    bad_auth_caught = _selftest_bad_auth()
    # M-7 回归：内容级缓存命中，且内容变化后立即失效（不得返回陈旧真身）。
    _parse_facts_text.cache_clear()
    cached_doc = load_facts(data)
    cache_hit = load_facts(data) is cached_doc
    fresh_doc = load_facts(badp)
    cache_invalidates = (fresh_doc is not cached_doc
                         and len(fresh_doc["ports"]) == len(cached_doc["ports"]) + 1)
    cache_ok = cache_hit and cache_invalidates
    ok = (drift_caught == EXIT_BLOCKING and clean == EXIT_OK
          and bad_auth_caught and cache_ok)
    print(json.dumps({"gate": GATE, "clean": clean, "drift_caught": drift_caught,
                      "bad_auth_caught": bad_auth_caught,
                      "facts_cache_hit": cache_hit, "facts_cache_invalidates": cache_invalidates,
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
