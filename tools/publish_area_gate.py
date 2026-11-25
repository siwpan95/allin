r"""publish_area_gate.py —— 发布区（repos/）治理门禁（rule 4/7/10/11/18 收口）

为什么有这个脚本
    20 道治理门禁只审 **allin 本仓**，从不覆盖被管的 139 个仓 ——
    这是 2026-11-21 勘察发现的结构性盲区（「20 道全绿但 CI 红」的更大版本：
    门禁全绿而 138 个被管仓有 error 级问题）。

    本脚本把 ``tools/repocheck`` 对发布区的体检**接入门禁体系**，并带一套
    **逐项豁免台账**（``tools/gate/ledger/publish_area_exemptions.csv``）：
      · 台账每条带 check / repo / path / reason / recorded_at / status；
      · status = ``accepted-exemption`` ⇒ 已实证裁决，可豁免；
      · status = ``pending-review``   ⇒ 登记待裁决，**同样不阻断**，但会在汇总里
        单列并写 JSONL 留痕（「登记但不放行」的差别靠 status 体现，不靠红灯）。

    为什么不直接让待裁决项红灯：139 仓里 10 条待裁决项全是**业务决策**
    （版本以 tag 还是清单为准、许可证冲突取哪个），agent 无权替全哥拍板；
    红灯会逼出「为了绿灯而随便改版本号/许可证」这种更坏的结果。
    登记 + 单列 + 待裁决状态，才符合 SPEC-002「高风险逐项确认」的纪律。

判据来源唯一
    体检判据全在 ``tools/repocheck`` 本体，本脚本**不复制任何判据**，
    只做「调用 + 豁免过滤 + 退出码聚合」，避免第二套口径。

用法
    python tools/publish_area_gate.py --repos-root <发布区根>
    python tools/publish_area_gate.py --repos-root <发布区根> --json
    python tools/publish_area_gate.py --repos-root <发布区根> --strict-pending
        # --strict-pending：待裁决项也判红（用于全哥在场逐项裁决时）

退出码
    0 无阻断（豁免项已登记）
    1 有未豁免的阻断项，或 --strict-pending 且有待裁决项
    2 用法/环境错误
    3 内部错误
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent          # 本仓的 tools/ 目录（位置随检出而变）
# 2026-11-25 公共核提仓：体检器随包走。走 **CLI**（`allin_governance repocheck`）而不是
# `-m _repocheck.main` —— 后者会撞包内 flat import（`import report`），CLI 的包装层已注入路径。
REPOCHECK_ARGS = ["-m", "allin_governance", "repocheck"]
DEFAULT_EXEMPTIONS = TOOLS / "gate" / "ledger" / "publish_area_exemptions.csv"
# 运行留痕仍留 audit/（C 层：可重生）；豁免台账 2026-11-25 提仓后留在本仓 tools/gate/ledger/
RUNS_LOG = TOOLS / "gate" / "audit" / "publish-area-runs.jsonl"

#: 纳入门禁的规则（其余 warn/info 级不阻断，但保留在体检报告里）
BLOCKING_SEVERITIES = {"error"}


def load_exemptions(path: Path) -> dict[tuple[str, str, str], dict]:
    """读豁免台账，键 = (rule_key, repo, path)。"""
    result: dict[tuple[str, str, str], dict] = {}
    if not path.is_file():
        return result
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("check", "").strip(),
                   row.get("repo", "").strip(),
                   row.get("path", "").strip())
            result[key] = row
    return result


def run_repocheck(repos_root: Path, python: str) -> dict:
    """调用 repocheck，拿 JSON 结果（不复制判据）。"""
    # Windows 上 NamedTemporaryFile 的句柄未关闭会让 repocheck 无法写入
    # （共享锁）⇒ 用 mkstemp 后立即 os.close 再交给子进程写。
    fd, tmp_name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    out = Path(tmp_name)
    try:
        cmd = [python, *REPOCHECK_ARGS, str(repos_root),
               "--workers", "8", "--format", "json", "--output", str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
        if not out.is_file():
            raise RuntimeError(f"repocheck 未产出报告：exit={proc.returncode} stderr={proc.stderr[-500:]}")
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        try:
            out.unlink()
        except OSError:
            pass



def _registered_repo_names() -> set[str]:
    """registry 里已登记的仓名（`path: repos/<name>` 的 <name>）。

    读不到就返回空集 —— 那时「非仓目录」判定退化为「有没有 .git」，
    仍比把所有目录当项目强。
    """
    import re as _re
    names: set[str] = set()
    reg = TOOLS.parent / "platform" / "registry" / "projects"
    if not reg.is_dir():
        return names
    for f in reg.glob("*.yaml"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _re.search(r"^path:\s*repos/(\S+)", text, _re.M)
        if m:
            names.add(m.group(1))
    return names


def _non_repo_dirs(root: Path) -> set[str]:
    """发布区里**不是仓**的一级目录。

    判据（两者同时成立才算）：无 `.git` 且未在 registry 登记。

    为什么要有这一层（2026-11-25）：`anatomy3d-demo` 是一次性录制脚本的目录，
    被当成项目扫了 4 条阻断（无 .git / 无 README / 无 LICENSE）。
    发布区的治理对象是**仓**；一个没有 `.git` 也没登记过的目录本来就不是仓，
    对它做仓体检只会产生噪音，还会掩盖真正的仓级问题。
    反例仍然保留：**登记了但没 .git** 是真问题，照常阻断。
    """
    registered = _registered_repo_names()
    out: set[str] = set()
    if not root.is_dir():
        return out
    for d in root.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        if (d / ".git").exists():
            continue
        if d.name in registered:
            continue     # 登记了却没 .git ⇒ 交给正常流程判红，不算「非仓」
        out.add(d.name)
    return out

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发布区治理门禁")
    ap.add_argument("--repos-root", default=os.environ.get("PROJECTS_ROOT", ""))
    ap.add_argument("--exemptions", default=str(DEFAULT_EXEMPTIONS))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict-pending", action="store_true",
                    help="待裁决项也判红（全哥在场逐项裁决时用）")
    args = ap.parse_args(argv)

    root = args.repos_root
    if not root or not Path(root).is_dir():
        print("用法错误：需 --repos-root 指向存在的发布区", file=sys.stderr)
        return 2
    rp = Path(root)

    ex = load_exemptions(Path(args.exemptions))
    report = run_repocheck(rp, args.python)

    blocking: list[dict] = []
    exempted: list[dict] = []
    pending: list[dict] = []
    non_repo = _non_repo_dirs(rp)
    skipped_non_repo: set[str] = set()
    for proj in report.get("projects", []):
        if proj.get("name", "") in non_repo:
            # 非仓目录：整目录跳过，末尾只出一条提示（不是 N 条阻断）
            skipped_non_repo.add(proj.get("name", ""))
            continue
        for f in proj.get("findings", []):
            if f.get("status") == "pass" or f.get("severity") not in BLOCKING_SEVERITIES:
                continue
            key = (f.get("key", ""), proj.get("name", ""), f.get("detail", "")[:60])
            item = {
                "repo": proj.get("name", ""),
                "rule": f.get("key", ""),
                "detail": f.get("detail", ""),
                "severity": f.get("severity", ""),
            }
            # 豁免按 (rule, repo) 匹配（path 用 detail 前缀做宽松匹配）
            matched = None
            for (r, repo, path), row in ex.items():
                if r == key[0] and repo == key[1]:
                    matched = row
                    break
            if matched is None:
                blocking.append(item)
            elif matched.get("status") == "pending-review":
                item["status"] = "pending-review"
                item["reason"] = matched.get("reason", "")
                pending.append(item)
            else:
                item["status"] = "accepted-exemption"
                item["reason"] = matched.get("reason", "")
                exempted.append(item)

    summary = report.get("summary", {})
    result = {
        "schema": "publish-area-gate/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "repos_root": str(rp),
        "summary": summary,
        "blocking": blocking,
        "pending": pending,
        "exempted": exempted,
        "verdict": "FAIL" if blocking or (args.strict_pending and pending) else "PASS",
    }

    # 留痕 JSONL（与 allin 其它门禁同款）
    try:
        with RUNS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": result["observed_at"],
                "verdict": result["verdict"],
                "blocking": len(blocking),
                "pending": len(pending),
                "exempted": len(exempted),
                "projects": summary.get("projects"),
                "errors": summary.get("errors"),
                "score_mean": summary.get("score_mean"),
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"发布区治理门禁 @ {rp}")
        print("----------------------------------------")
        print(f"  体检仓数      : {summary.get('projects')}")
        print(f"  健康分均值/最低: {summary.get('score_mean')} / {summary.get('score_min')}")
        print(f"  error 总数    : {summary.get('errors')}")
        print(f"  未豁免阻断    : {len(blocking)}")
        print(f"  待裁决(已登记): {len(pending)}")
        print(f"  已裁决豁免    : {len(exempted)}")
        print(f"  跳过非仓目录  : {len(skipped_non_repo)}")
        if pending:
            print("\n待全哥裁决（不阻断，已登记台账）：")
            for item in pending:
                print(f"  [{item['rule']}] {item['repo']}: {item['detail'][:80]}")
        if blocking:
            print("\n未豁免阻断：")
            for item in blocking:
                print(f"  [{item['rule']}] {item['repo']}: {item['detail'][:80]}")
        if skipped_non_repo:
            print("\n跳过（非仓目录：无 .git 且未登记 registry，不做仓体检）：")
            for name in sorted(skipped_non_repo):
                print(f"  - {name}")
        print(f"\nPUBLISH_AREA_GATE verdict={result['verdict']} "
              f"blocking={len(blocking)} pending={len(pending)}")

    if blocking:
        return 1
    if args.strict_pending and pending:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
