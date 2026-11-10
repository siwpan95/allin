#!/usr/bin/env python3
"""Git YAML/JSON 真身 -> NetBox 的**单向幂等导入**骨架。

纪律（对应 ADR-0003「默认只读、写入需显式确认」与 SPEC-001 单一事实源）：
  * Git 是唯一写入权威；NetBox 是派生的资产视图，绝不反向写回 Git；
  * 默认 --dry-run，只有显式 --apply 且提供 NETBOX_URL / NETBOX_TOKEN 才发请求；
  * 用本地 state 文件记录 payload 摘要实现幂等，不依赖「查询 NetBox 现有对象」；
  * 不把 visibility != public 的字段同步进任何可对外访问的实例；
  * 每次写入把 source_git_sha 写进 NetBox changelog_message —— 与 Dolt dolt_log、
    GraphRAG citation 共用同一溯源键，可直接三方 join（不必建中间 ingest_run 表）。

零第三方依赖（urllib）。退出码：0 干净 / 1 有变化或失败 / 2 用法错 / 3 环境错。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EXIT_OK, EXIT_CHANGED, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
DEFAULT_DATA = Path(__file__).resolve().parents[2] / "facts" / "facts.json"

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
import runtime_defaults as _rd  # noqa: E402


def digest(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def git_sha(root: Path) -> str:
    """当前 Git 真身短 SHA；取不到就明确写 UNKNOWN，绝不编造溯源键。"""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, encoding="utf-8", timeout=_rd.timeout("git_probe"))
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def payloads(doc: dict, sha: str = "UNKNOWN") -> dict[str, dict]:
    """真身 -> NetBox REST payload。只同步 public 可见字段。

    ⚠ changelog_message 是 NetBox 4.1+ ObjectChange 的 <=200 字符备注字段
      （官方 https://netboxlabs.com/docs/netbox/en/stable/features/change-logging/）。
      落仓前需用真实 NetBox 4.7 验证字段名：若 REST 拒绝未知 body 字段，
      改为请求头 X-Changelog-Message（官方客户端 netbox_client.py 同款兼容思路）。
    """
    note = f"source_git_sha={sha}"[:200]
    out: dict[str, dict] = {}
    for m in doc.get("machines", []):
        if m.get("visibility", "public") != "public":
            continue
        key = f"dcim.devices/{m['machine_id']}"
        out[key] = {
            "endpoint": "/api/dcim/devices/",
            "body": {
                "name": m["machine_id"],
                "status": "active" if m["status"] == "active" else "offline",
                "changelog_message": note,
                "custom_fields": {
                    "allin_os_build": m.get("os_build", ""),
                    "allin_ram_gb": m.get("ram_gb"),
                    "allin_observed_at": m["observed_at"],
                    "allin_evidence_ref": m["evidence_ref"],
                    "allin_fact_source": "git:docs/事实源/_structured/facts.json",
                },
                "comments": "由 allin facts sync 单向生成；请勿在 NetBox 内编辑（会被下次同步覆盖）",
            },
        }
    for p in doc.get("ports", []):
        if p.get("visibility", "public") != "public":
            continue
        key = f"ipam.services/{p['port']}-{p['service']}"
        out[key] = {
            "endpoint": "/api/ipam/services/",
            "body": {"name": p["service"], "ports": [p["port"]], "protocol": "tcp",
                     "changelog_message": note,
                     "custom_fields": {"allin_status": p["status"],
                                       "allin_observed_at": p["observed_at"],
                                       "allin_evidence_ref": p["evidence_ref"]}},
        }
    return out


def stable(item: dict) -> dict:
    """幂等摘要必须排除 changelog_message，否则每次 Git commit 都会全量重推。"""
    return {"endpoint": item["endpoint"],
            "body": {k: v for k, v in item["body"].items() if k != "changelog_message"}}


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def plan(doc: dict, state: dict, sha: str = "UNKNOWN") -> tuple[list, list, list]:
    now = {k: digest(stable(v)) for k, v in payloads(doc, sha).items()}
    create = [k for k in now if k not in state]
    update = [k for k in now if k in state and state[k] != now[k]]
    unchanged = [k for k in now if k in state and state[k] == now[k]]
    return create, update, unchanged


def apply_remote(base: str, token: str, doc: dict, keys: list[str], sha: str) -> int:
    """最小写实现：仅 POST（更新走 POST + NetBox 的 upsert 由外部定制脚本承担）。生产应改为先 GET 再 PATCH。"""
    items = payloads(doc, sha)
    # NetBox 4.5+ 用 v2 token：Authorization: Bearer nbt_<key>.<token>；
    # legacy v1 "Token <t>" 自 4.6 弃用、5.0 移除。
    # 与官方 netbox-mcp-server 的 netbox_client.py 同一兼容逻辑。
    auth = f"Bearer {token}" if token.startswith("nbt_") else f"Token {token}"
    ok, fail = 0, 0
    for k in keys:
        item = items[k]
        req = urllib.request.Request(
            base.rstrip("/") + item["endpoint"],
            data=json.dumps(item["body"], ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": auth, "Content-Type": "application/json",
                     "Accept": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=_rd.timeout("network_probe")) as r:
                print(f"  APPLY {k} -> HTTP {r.status}")
                ok += 1
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"  APPLY {k} -> FAIL {e}")
            fail += 1
    return fail


def selftest() -> int:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="allin-netbox-sync-"))
    state = root / "state.json"
    doc = json.loads(DEFAULT_DATA.read_text(encoding="utf-8"))
    c1, u1, _ = plan(doc, {}, "abc1234")
    p = payloads(doc, "abc1234")
    sha_written = all("source_git_sha=abc1234" in v["body"].get("changelog_message", "") for v in p.values())
    state.write_text(json.dumps({k: digest(stable(v)) for k, v in p.items()}), encoding="utf-8")
    c2, u2, un2 = plan(doc, load_state(state), "abc1234")
    c_sha, u_sha, un_sha = plan(doc, load_state(state), "def5678")   # 换 SHA 不得触发全量重推
    changed = json.loads(json.dumps(doc))
    changed["machines"][0]["os_build"] = "99999"
    c3, u3, _ = plan(changed, load_state(state), "def5678")
    ok = (len(c1) > 0 and sha_written and c2 == [] and u2 == [] and len(un2) == len(c1)
          and c_sha == [] and u_sha == [] and len(un_sha) == len(c1)
          and u3 == ["dcim.devices/SIWPAN"])
    print(json.dumps({"first_run_creates": len(c1), "changelog_message_written": sha_written,
                      "second_run_creates": len(c2), "second_run_unchanged": len(un2),
                      "sha_change_causes_repush": bool(c_sha or u_sha),
                      "changed_machine_updates": u3,
                      "selftest": "PASS" if ok else "FAIL"}, ensure_ascii=False))
    return EXIT_OK if ok else EXIT_CHANGED


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="allin facts -> NetBox 单向幂等同步")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                    help="Git 仓根（从脚本位置自发现，不写死盘符：铁律 5 / g01-paths）")
    ap.add_argument("--git-sha", default=None, help="显式指定溯源 SHA（默认 git rev-parse --short HEAD）")
    ap.add_argument("--state", type=Path, default=None, help="同步状态文件（默认 <data>/../netbox_state.json，不入库）")
    ap.add_argument("--apply", action="store_true", help="真正写 NetBox；需 NETBOX_URL / NETBOX_TOKEN")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    sha = a.git_sha or git_sha(a.root)
    state_path = a.state or (Path(__file__).resolve().parent / "state" / "netbox_state.json")
    doc = json.loads(a.data.read_text(encoding="utf-8"))
    state = load_state(state_path)
    create, update, unchanged = plan(doc, state, sha)
    print(json.dumps({"source_git_sha": sha, "create": create, "update": update,
                      "unchanged": len(unchanged), "mode": "apply" if a.apply else "dry-run"},
                     ensure_ascii=False, indent=2))
    if not a.apply:
        print("DRY-RUN: 未写 NetBox。加 --apply 才生效（ADR-0003 写入需显式确认）。")
        return EXIT_OK
    base, token = os.environ.get("NETBOX_URL"), os.environ.get("NETBOX_TOKEN")
    if not base or not token:
        print("ENV ERROR: --apply 需要 NETBOX_URL 与 NETBOX_TOKEN（绝不硬编码）")
        return EXIT_ENV
    fails = apply_remote(base, token, doc, create + update, sha)
    if fails == 0:
        state_path.write_text(json.dumps({k: digest(stable(v)) for k, v in payloads(doc, sha).items()},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
    return EXIT_OK if fails == 0 else EXIT_CHANGED


if __name__ == "__main__":
    raise SystemExit(main())
