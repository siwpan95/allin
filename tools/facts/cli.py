#!/usr/bin/env python3
"""allin facts CLI -- 结构化事实源统一查询面（MCP 与 CLI 共用同一实现）。

设计纪律（与仓内 tools/facts/README.md 同构）：
  * 判据只有一份：MCP 工具应 import 本模块，不另写一套解析/校验逻辑；
  * 采集值不是事实：observation_runs 未经裁决不得进入 facts；
  * SQLite 是可重建的派生视图，绝不入库、绝不作为写入权威；
  * 结构化取值走 SQL/工具，不上向量库；叙述层才交给检索。
零第三方依赖（Python 标准库）。退出码：0 干净 / 1 有 finding / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from exit_codes import EXIT_OK, EXIT_BLOCKING, EXIT_USAGE, EXIT_ENV  # 单一事实源，勿重定义
def _repo_root() -> Path:
    """从脚本位置向上找仓根，不写死盘符（铁律 5 / g01-paths）。"""
    for p in Path(__file__).resolve().parents:
        if all((p / m).is_dir() for m in ("docs", "preset", "tools", "facts")):
            return p
    return Path(__file__).resolve().parents[2]


ROOT = _repo_root()
HERE = Path(__file__).resolve().parent
DEFAULT_SCHEMA = ROOT / "facts" / "facts.schema.json"
DEFAULT_DATA = ROOT / "facts" / "facts.json"
DEFAULT_DB = ROOT / "facts" / "build" / "facts.sqlite"
MARKER = re.compile(r"<!-- FACTS-GENERATED:START sha256:([0-9a-f]{16}) -->")
TABLES = ("machines", "volumes", "runtimes", "repos", "ports", "services", "facts", "doc_refs", "observation_runs")


# ---------------------------------------------------------------------------
# 权威 YAML 读取（P2 #19：tools/facts 下唯一一份；5 个 build_*.py 不再各写一套）
# ---------------------------------------------------------------------------

class AuthUnavailable(Exception):
    """权威 YAML 在场但无法解析：缺 PyYAML / 语法错 / 顶层非 mapping / 读失败。

    2026-11-10 深度审计 H-3（P1 #7）：此前各 ``build_*.py`` 的 ``_yaml_load``
    用 ``except Exception: return None`` 把「语法错」与「文件不存在 / 缺 yaml」
    混成同一个 ``None``，调用方据此降级为 ``SKIP / EXIT_OK`` —— 实测把
    ``ports.yaml`` 写坏后 ``--check`` 仍是 ``rc=0``，权威源损坏被判绿。
    P2 #19 收敛为本模块唯一一份实现，语义**绝不**退回静默 None。

    ``kind`` 标注四态中的失败子类，供调用方输出可读诊断：
    ``no_pyyaml`` / ``parse`` / ``shape``。
    """

    def __init__(self, message: str, kind: str = "parse") -> None:
        super().__init__(message)
        self.kind = kind


def yaml_load(path: Path) -> dict | None:
    """读权威 YAML —— tools/facts 下**唯一**一份读取实现（P2 #19）。

    四种状态，语义显式、不吞错（单一异常形态，延续 build_ports.py 的 AuthUnavailable）：

      * 文件不存在   → 返回 ``None``（权威源缺席，调用方决定是否 SKIP）；
      * 缺 PyYAML    → 抛 ``AuthUnavailable(kind="no_pyyaml")``；
      * 在场但解析失败 / 读失败 / 顶层非 mapping
                      → 抛 ``AuthUnavailable(kind="parse" / "shape")``；
      * 正常         → 返回 ``dict``（``yaml.safe_load(...) or {}``）。

    **绝不**用 ``None`` 代表「在场但读不出来」——那正是 P1 #7 修掉的「损坏被判绿」。
    在场却不可解析时，调用方必须显式报错 / 非 0，而非降级为 SKIP。
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        import yaml
    except ImportError as exc:
        raise AuthUnavailable(f"PyYAML 未安装：{exc}", kind="no_pyyaml") from exc
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise AuthUnavailable(
            f"YAML 解析失败：{type(exc).__name__}: {exc}", kind="parse"
        ) from exc
    if not isinstance(doc, dict):
        raise AuthUnavailable(f"顶层不是 mapping：{type(doc).__name__}", kind="shape")
    return doc


class SchemaError(Exception):
    pass


def _is_type(v, t: str) -> bool:
    return {
        "object": lambda: isinstance(v, dict),
        "array": lambda: isinstance(v, list),
        "string": lambda: isinstance(v, str),
        "integer": lambda: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda: isinstance(v, bool),
        "null": lambda: v is None,
    }.get(t, lambda: True)()


def validate_node(node, schema: dict, root: dict, path: str = "$") -> None:
    """JSON Schema 子集：required / type / enum / pattern / additionalProperties / items / minItems。"""
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return validate_node(node, target, root, path)
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not any(_is_type(node, x) for x in types):
            raise SchemaError(f"{path}: 类型应为 {'|'.join(types)}，实为 {type(node).__name__}")
    if "enum" in schema and node not in schema["enum"]:
        raise SchemaError(f"{path}: 取值 {node!r} 不在闭集 {schema['enum']}")
    if "pattern" in schema and isinstance(node, str) and not re.search(schema["pattern"], node):
        raise SchemaError(f"{path}: {node!r} 不匹配 {schema['pattern']}")
    if "minimum" in schema and isinstance(node, (int, float)) and node < schema["minimum"]:
        raise SchemaError(f"{path}: {node} < minimum {schema['minimum']}")
    if "maximum" in schema and isinstance(node, (int, float)) and node > schema["maximum"]:
        raise SchemaError(f"{path}: {node} > maximum {schema['maximum']}")
    if "minLength" in schema and isinstance(node, str) and len(node) < schema["minLength"]:
        raise SchemaError(f"{path}: 长度不足 {schema['minLength']}")
    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                raise SchemaError(f"{path}: 缺必填字段 {req}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in node:
                if k not in props:
                    raise SchemaError(f"{path}: 未声明字段 {k}（additionalProperties=false）")
        for k, v in node.items():
            if k in props:
                validate_node(v, props[k], root, f"{path}.{k}")
    if isinstance(node, list):
        if "minItems" in schema and len(node) < schema["minItems"]:
            raise SchemaError(f"{path}: 少于 minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for i, v in enumerate(node):
                validate_node(v, item_schema, root, f"{path}[{i}]")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"读取失败 {path}: {e}") from e


def cmd_validate(data: Path, schema: Path) -> int:
    doc = load_json(data)
    spec = load_json(schema)
    try:
        validate_node(doc, spec, spec)
    except SchemaError as e:
        print(f"SCHEMA FAIL: {e}")
        return EXIT_BLOCKING
    print(f"SCHEMA OK: {data.name} 符合 {schema.name} (v{doc.get('schema_version')})")
    print(f"  machines={len(doc.get('machines', []))} facts={len(doc.get('facts', []))} "
          f"doc_refs={len(doc.get('doc_refs', []))}")
    return EXIT_OK


def _flatten(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def build_db(doc: dict, db: Path) -> dict:
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE machines (machine_id TEXT PRIMARY KEY, hostname TEXT, status TEXT, observed_at TEXT, evidence_ref TEXT, payload TEXT)")
    for t in TABLES[1:]:
        if t == "facts":
            continue
        con.execute(f"CREATE TABLE {t} (row_id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, payload TEXT)")
    con.execute("""CREATE TABLE facts (
        fact_id TEXT PRIMARY KEY, subject TEXT, attribute TEXT, value_text TEXT,
        scope TEXT, status TEXT, valid_from TEXT, valid_to TEXT, observed_at TEXT,
        machine_id TEXT, evidence_ref TEXT, source_file TEXT, source_line INTEGER, payload TEXT)""")
    for m in doc.get("machines", []):
        con.execute("INSERT OR REPLACE INTO machines VALUES (?,?,?,?,?,?)",
                    (m["machine_id"], m.get("hostname", ""), m["status"], m["observed_at"],
                     m["evidence_ref"], _flatten(m)))
    for t in TABLES[1:]:
        if t == "facts":
            continue
        for row in doc.get(t, []):
            key = row.get("machine_id") or row.get("repo_id") or row.get("port") or row.get("service_id") or row.get("doc_id") or row.get("run_id") or ""
            con.execute(f"INSERT INTO {t} (key, payload) VALUES (?,?)", (str(key), _flatten(row)))
    for f in doc.get("facts", []):
        con.execute("INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f["fact_id"], f["subject"], f["attribute"], json.dumps(f["value"], ensure_ascii=False),
                     f["scope"], f["status"], f["valid_from"], f["valid_to"], f["observed_at"],
                     f.get("machine_id"), f["evidence_ref"], f.get("source_file", ""), f.get("source_line", 0),
                     _flatten(f)))
    con.execute("""CREATE VIEW current_facts AS
        SELECT * FROM facts WHERE status='current' AND valid_to IS NULL""")
    fts_engine = None
    for tokenizer in ("trigram", "unicode61"):
        try:
            con.execute(f"CREATE VIRTUAL TABLE facts_fts USING fts5(subject, attribute, value_text, tokenize='{tokenizer}')")
            fts_engine = tokenizer
            break
        except sqlite3.OperationalError:
            continue
    if fts_engine:
        for f in doc.get("facts", []):
            con.execute("INSERT INTO facts_fts (subject, attribute, value_text) VALUES (?,?,?)",
                        (f["subject"], f["attribute"], str(f["value"])))
    con.commit()
    fts_rows = con.execute("SELECT count(*) FROM facts_fts").fetchone()[0] if fts_engine else 0
    con.close()
    return {"db": str(db), "facts": len(doc.get("facts", [])),
            "fts_engine": fts_engine, "fts_rows": fts_rows,
            "sqlite": sqlite3.sqlite_version}


def cmd_build(data: Path, db: Path, schema: Path) -> int:
    rc = cmd_validate(data, schema)
    if rc != EXIT_OK:
        return rc
    info = build_db(load_json(data), db)
    print("BUILD OK: " + json.dumps(info, ensure_ascii=False))
    return EXIT_OK


def resolve_source(db: Path, source: str) -> str:
    """离线优先的数据源解析：auto = 派生库在就用库，不在自动回落纯 JSON 真身。

    回落必须在返回值里显式标注，禁止把「只读 JSON」伪装成「查过数据库」。
    """
    if source == "json":
        return "json"
    if source == "sqlite":
        if not db.exists():
            raise RuntimeError(f"指定 sqlite 但派生库不存在：{db}（可先 build）")
        return "sqlite"
    return "sqlite" if db.exists() else "json"


def _connect_ro(db: Path) -> sqlite3.Connection:
    if not db.exists():
        raise RuntimeError(f"派生库不存在，请先 build：{db}")
    return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)


def _citation(row: tuple) -> str:
    return f"{row[11]}:{row[12]} @ {row[8]} | {row[10]}"


def _json_facts(data: Path, subject: str | None = None, attribute: str | None = None,
                asof: str | None = None) -> list[dict]:
    """纯 JSON 真身读取（离线 readonly 档）：不碰 SQLite、不碰网络、不碰任何服务。"""
    out = []
    for f in load_json(data).get("facts", []):
        if subject is not None and f["subject"] != subject:
            continue
        if attribute is not None and f["attribute"] != attribute:
            continue
        if f["status"] == "retracted":
            continue
        if asof:
            if not (f["valid_from"] <= asof and (f["valid_to"] is None or f["valid_to"] > asof)):
                continue
        elif not (f["status"] == "current" and f["valid_to"] is None):
            continue
        out.append(f)
    return sorted(out, key=lambda x: x["observed_at"], reverse=True)


def _emit(f: dict, source: str) -> None:
    print(json.dumps({
        "fact_id": f.get("fact_id"), "subject": f.get("subject"), "attribute": f.get("attribute"),
        "value": f.get("value"), "status": f.get("status"),
        "valid_from": f.get("valid_from"), "valid_to": f.get("valid_to"),
        "observed_at": f.get("observed_at"),
        "citation": f"{f.get('source_file','')}:{f.get('source_line',0)} @ {f.get('observed_at')} | {f.get('evidence_ref','')}",
        "source": source, "state_kind": "declared",
    }, ensure_ascii=False))


def cmd_get(db: Path, subject: str, attribute: str, asof: str | None = None,
            data: Path = DEFAULT_DATA, source: str = "auto") -> int:
    mode = resolve_source(db, source)
    if mode == "json":
        rows = _json_facts(data, subject, attribute, asof)
        for f in rows:
            _emit(f, "json(readonly)")
    else:
        con = _connect_ro(db)
        if asof:
            sql = """SELECT * FROM facts WHERE subject=? AND attribute=?
                AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) AND status!='retracted'
                ORDER BY observed_at DESC"""
            params = (subject, attribute, asof, asof)
        else:
            sql = """SELECT * FROM facts WHERE subject=? AND attribute=?
                AND status='current' AND valid_to IS NULL ORDER BY observed_at DESC"""
            params = (subject, attribute)
        rows = con.execute(sql, params).fetchall()
        con.close()
        for r in rows:
            _emit({"fact_id": r[0], "subject": r[1], "attribute": r[2],
                   "value": json.loads(r[3]), "status": r[5], "valid_from": r[6],
                   "valid_to": r[7], "observed_at": r[8], "source_file": r[11],
                   "source_line": r[12], "evidence_ref": r[10]}, "sqlite")
    if not rows:
        print(f"NOT FOUND: {subject}.{attribute} (asof={asof or 'now'}) —— 无证据，拒答而非编造")
        return EXIT_BLOCKING
    return EXIT_OK


def cmd_asof(db: Path, day: str, data: Path = DEFAULT_DATA, source: str = "auto") -> int:
    mode = resolve_source(db, source)
    if mode == "json":
        rows = [(f["subject"], f["attribute"], f["value"], f["fact_id"], f["observed_at"])
                for f in _json_facts(data, asof=day)]
    else:
        con = _connect_ro(db)
        rows = con.execute("""SELECT subject, attribute, value_text, fact_id, observed_at FROM facts
            WHERE valid_from<=? AND (valid_to IS NULL OR valid_to>?) AND status!='retracted'
            ORDER BY subject, attribute""", (day, day)).fetchall()
        con.close()
    print(f"AS-OF {day}: {len(rows)} 条有效事实  (source={mode})")
    for r in rows:
        print(f"  {r[0]}.{r[1]} = {r[2]}  ({r[3]}, observed {r[4]})")
    return EXIT_OK


def cmd_query(db: Path, sql: str, source: str = "auto") -> int:
    if resolve_source(db, source) == "json":
        print("QUERY UNAVAILABLE: JSON readonly 档不支持任意 SQL。"
              "可用子命令：get / asof / diff / validate / render / offline-check。"
              "要跑 SQL 请先 build 派生库（它是可重建缓存，不是权威源）。")
        return EXIT_USAGE
    if not re.match(r"^\s*(SELECT|WITH|PRAGMA|EXPLAIN)\b", sql, re.I):
        print("QUERY REJECTED: 只读接口仅接受 SELECT / WITH / PRAGMA / EXPLAIN")
        return EXIT_USAGE
    con = _connect_ro(db)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"QUERY ERROR: {e}")
        return EXIT_BLOCKING
    finally:
        con.close()
    print(json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False, default=str))
    return EXIT_OK


def cmd_offline_check(data: Path, schema: Path) -> int:
    """离线北极星验收：假设拔网、停掉三栈、删光派生库，只留 git clone 出来的文本。"""
    import subprocess
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-offline-"))
    ghost = root / "no-such-derived.sqlite"
    checks = []
    try:
        spec = load_json(schema)
        validate_node(load_json(data), spec, spec)
        checks.append(("Schema 校验（纯文本、零依赖）", True))
    except (SchemaError, RuntimeError) as e:
        checks.append((f"Schema 校验: {e}", False))
    cur = _json_facts(data, "global", "gitee_remote_repo_count")
    checks.append(("get 现值 138（无派生库）", len(cur) == 1 and cur[0]["value"] == 138))
    hist = _json_facts(data, "global", "gitee_remote_repo_count", "2026-11-01")
    checks.append(("asof 2026-11-01 得 137（无派生库）", len(hist) == 1 and hist[0]["value"] == 137))
    checks.append(("query 在 JSON 档明确拒答（不伪装）",
                   cmd_query(ghost, "SELECT 1", "json") == EXIT_USAGE))
    d1, d2 = root / "a.sqlite", root / "b.sqlite"
    build_db(load_json(data), d1)
    build_db(load_json(data), d2)
    q = "SELECT fact_id,subject,attribute,value_text,valid_from,valid_to FROM facts ORDER BY fact_id"
    c1 = sqlite3.connect(str(d1)).execute(q).fetchall()
    c2 = sqlite3.connect(str(d2)).execute(q).fetchall()
    checks.append(("派生库两次 build 查询结果一致（可重建）", c1 == c2))
    gate_dir = ROOT / "tools" / "gate"
    oks = []
    for name in ("facts_parity.py", "relative_refs_gate.py"):
        p = gate_dir / name
        if p.is_file():
            r = subprocess.run([sys.executable, str(p), "--selftest"],
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
            oks.append(r.returncode == 0)
    checks.append(("g23/g24 判据可离线自检", len(oks) == 2 and all(oks)))
    print("OFFLINE CHECK (拔网 / 停栈 / 删派生库 / 仅留 git clone)")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"  note: 两次 build 字节相同 = {d1.read_bytes() == d2.read_bytes()}")
    n = sum(1 for _, ok in checks if ok)
    print(f"OFFLINE CHECK: {n}/{len(checks)} PASS  (source=json(readonly))")
    return EXIT_OK if n == len(checks) else EXIT_BLOCKING


def cmd_diff(a: Path, b: Path) -> int:
    def index(p):
        return {(f["subject"], f["attribute"]): (f["value"], f["status"])
                for f in load_json(p).get("facts", []) if f["status"] == "current"}
    ia, ib = index(a), index(b)
    added = sorted(set(ib) - set(ia))
    removed = sorted(set(ia) - set(ib))
    changed = sorted(k for k in set(ia) & set(ib) if ia[k][0] != ib[k][0])
    print(json.dumps({"added": [f"{k[0]}.{k[1]}={ib[k][0]!r}" for k in added],
                      "removed": [f"{k[0]}.{k[1]}={ia[k][0]!r}" for k in removed],
                      "changed": [f"{k[0]}.{k[1]}: {ia[k][0]!r} -> {ib[k][0]!r}" for k in changed]},
                     ensure_ascii=False, indent=2))
    return EXIT_BLOCKING if (added or removed or changed) else EXIT_OK


def expected_hash(doc: dict, machine_id: str) -> str:
    subset = {
        "machine": next((m for m in doc.get("machines", []) if m["machine_id"] == machine_id), None),
        "facts": [f for f in doc.get("facts", []) if f.get("machine_id") == machine_id
                  or (f["scope"] == "global" and machine_id == doc["machines"][0]["machine_id"])],
    }
    return hashlib.sha256(json.dumps(subset, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def cmd_render(data: Path, outdir: Path, check: bool) -> int:
    doc = load_json(data)
    outdir.mkdir(parents=True, exist_ok=True)
    findings = []
    for m in doc.get("machines", []):
        mid = m["machine_id"]
        target = outdir / f"{mid}.facts.md"
        h = expected_hash(doc, mid)
        if check:
            if not target.exists():
                findings.append(f"{target.name}: 生成物缺失")
                continue
            found = MARKER.search(target.read_text(encoding="utf-8"))
            if not found:
                findings.append(f"{target.name}: 缺 FACTS-GENERATED marker")
            elif found.group(1) != h:
                findings.append(f"{target.name}: 漂移 marker={found.group(1)} expected={h}")
        else:
            lines = [f"# {mid}（生成物，请勿手改）", "",
                     f"<!-- FACTS-GENERATED:START sha256:{h} -->", "",
                     "| 字段 | 值 | 时点 | 证据 |", "|---|---|---|---|"]
            for k in ("hostname", "os_caption", "os_build", "cpu", "ram_gb", "status"):
                if k in m:
                    lines.append(f"| {k} | {m[k]} | {m['observed_at']} | {m['evidence_ref']} |")
            lines += ["", "<!-- FACTS-GENERATED:END -->", ""]
            target.write_text("\n".join(lines), encoding="utf-8")
    if check:
        for f in findings:
            print(f"DRIFT: {f}")
        print(f"RENDER CHECK: {len(doc.get('machines', []))} 份生成物，findings={len(findings)}")
        return EXIT_BLOCKING if findings else EXIT_OK
    print(f"RENDER OK: {len(doc.get('machines', []))} 份 -> {outdir}")
    return EXIT_OK


def cmd_selftest() -> int:
    results = []
    root = Path(tempfile.mkdtemp(prefix="allin-facts-selftest-"))
    schema, data = DEFAULT_SCHEMA, DEFAULT_DATA
    db = root / "facts.sqlite"
    outdir = root / "rendered"

    def check(name, cond):
        results.append((name, bool(cond)))

    rc = cmd_validate(data, schema)
    check("validate 好样本通过", rc == EXIT_OK)
    bad = json.loads(data.read_text(encoding="utf-8"))
    bad["facts"][0]["status"] = "自创状态"
    badp = root / "bad.json"
    badp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    check("validate 坏闭集被拦", cmd_validate(badp, schema) == EXIT_BLOCKING)
    bad2 = json.loads(data.read_text(encoding="utf-8"))
    bad2["facts"][0]["未知字段"] = 1
    badp2 = root / "bad2.json"
    badp2.write_text(json.dumps(bad2, ensure_ascii=False), encoding="utf-8")
    check("validate 未声明字段被拦", cmd_validate(badp2, schema) == EXIT_BLOCKING)

    info = build_db(load_json(data), db)
    check("build 生成派生库", info["facts"] == 4 and (root / "facts.sqlite").exists())
    check("FTS5 trigram 可用", info["fts_engine"] == "trigram" and info["fts_rows"] == 4)
    check("get 当前值 138", cmd_get(db, "global", "gitee_remote_repo_count") == EXIT_OK)
    check("asof 历史值可查", cmd_asof(db, "2026-11-01") == EXIT_OK)
    con = _connect_ro(db)
    hist = con.execute("""SELECT value_text FROM facts WHERE subject='global'
        AND attribute='gitee_remote_repo_count' AND valid_from<='2026-11-01'
        AND (valid_to IS NULL OR valid_to>'2026-11-01')""").fetchall()
    con.close()
    check("asof 2026-11-01 得 137（SCD-2 生效）", [r[0] for r in hist] == ["137"])
    check("query 只读可查", cmd_query(db, "SELECT count(*) FROM current_facts") == EXIT_OK)
    check("query 拒绝写语句", cmd_query(db, "DELETE FROM facts") == EXIT_USAGE)
    check("diff 无差异", cmd_diff(data, data) == EXIT_OK)
    changed = json.loads(data.read_text(encoding="utf-8"))
    changed["facts"][0]["value"] = 999
    changedp = root / "changed.json"
    changedp.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    check("diff 抓到取值变化", cmd_diff(data, changedp) == EXIT_BLOCKING)

    cmd_render(data, outdir, check=False)
    check("render --check 干净", cmd_render(data, outdir, check=True) == EXIT_OK)
    f = outdir / "SIWPAN.facts.md"
    f.write_text(MARKER.sub("<!-- FACTS-GENERATED:START sha256:0000000000000000 -->",
                            f.read_text(encoding="utf-8")), encoding="utf-8")
    check("render --check 抓到漂移", cmd_render(data, outdir, check=True) == EXIT_BLOCKING)
    ghost = root / "no-derived-db.sqlite"
    check("无派生库时 get 自动回落 JSON", cmd_get(ghost, "global", "gitee_remote_repo_count",
                                                data=data, source="auto") == EXIT_OK)
    check("offline-check 全绿（无派生库/无服务/无网络）",
          cmd_offline_check(data, schema) == EXIT_OK)

    passed = sum(1 for _, ok in results if ok)
    print("\n=== SELFTEST ===")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"SELFTEST: {passed}/{len(results)} passed")
    return EXIT_OK if passed == len(results) else EXIT_BLOCKING


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="allin facts CLI（结构化事实源统一查询面）")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--source", choices=["auto", "sqlite", "json"], default="auto",
                    help="auto=派生库在就用库、不在直读 JSON 真身；json=强制离线只读档")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("build")
    g = sub.add_parser("get"); g.add_argument("--subject", required=True); g.add_argument("--attribute", required=True); g.add_argument("--asof")
    a = sub.add_parser("asof"); a.add_argument("--date", required=True)
    q = sub.add_parser("query"); q.add_argument("--sql", required=True)
    d = sub.add_parser("diff"); d.add_argument("--a", type=Path, required=True); d.add_argument("--b", type=Path, required=True)
    r = sub.add_parser("render"); r.add_argument("--out", type=Path, required=True); r.add_argument("--check", action="store_true")
    sub.add_parser("offline-check", help="离线北极星验收：拔网/停栈/删派生库后仍可读事实、跑判据")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "validate": return cmd_validate(args.data, args.schema)
        if args.cmd == "build": return cmd_build(args.data, args.db, args.schema)
        if args.cmd == "offline-check": return cmd_offline_check(args.data, args.schema)
        if args.cmd == "get": return cmd_get(args.db, args.subject, args.attribute, args.asof,
                                             args.data, args.source)
        if args.cmd == "asof": return cmd_asof(args.db, args.date, args.data, args.source)
        if args.cmd == "query": return cmd_query(args.db, args.sql, args.source)
        if args.cmd == "diff": return cmd_diff(args.a, args.b)
        if args.cmd == "render": return cmd_render(args.data, args.out, args.check)
        if args.cmd == "selftest": return cmd_selftest()
    except RuntimeError as e:
        print(f"ENV ERROR: {e}")
        return EXIT_ENV
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
