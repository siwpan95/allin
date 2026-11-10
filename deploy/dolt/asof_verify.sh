#!/usr/bin/env bash
# asof_verify.sh —— P1-4 实证：Dolt AS OF / dolt_diff_fact 能读取历史真值差异
#
# 背景（§147.4 新增③）：历史各 SHA 的 facts.json 导入表内容逐字节相同
# （machines=3 / volumes=3 / ports=13 / facts=4），从未发生过「真实 fact 变更」，
# 因此无法用真实 Git 历史证明 AS OF 能读到不同历史值。
#
# 本脚本用**纯派生工作区**闭环证明机制本身可用，绝不触碰 Git 真身：
#   1. 复制 facts/facts.json 为 prev 变体，仅把 FCT-000001 的 value 138→137（受控、可逆）；
#   2. 把 prev 变体以合成溯源键 ASOPREV 导入一个 /tmp 一次性工作区；
#   3. 再把真实 facts/facts.json 以当前真实 SHA 导入同一工作区（全量重建 = 真实内容 138）；
#   4. 用 AS OF <prev_hash> 与 AS OF <head_hash> 读取同一 fact，断言 137 vs 138；
#   5. 用 dolt_diff_fact 断言两提交间确有 ≥1 行差异。
# 全程不写 Git、不改仓根 facts/facts.json、不污染仓内 facts/dolt-workspace。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 3

# 2026-11-10 换机可移植：dolt 与 Python 的定位收敛到共享解析（deploy/dolt/dolt_env.sh）——
# 此前硬编码了本机安装盘位与某台机器的 Python 绝对路径，换机即坏。
. "$ROOT/deploy/dolt/dolt_env.sh"
if ! allin_resolve_dolt; then
  allin_dolt_env_error
  exit 3
fi

PY="$(allin_resolve_python)" || { echo "ENV ERROR: 找不到 Python（设 ALLIN_PYTHON 或用仓内 .venv）"; exit 3; }

# 一次性工作区放在仓内已 gitignore 的 facts/dolt-workspace/.asof_proof（NTFS 路径，rm 可靠）
WS="$ROOT/facts/dolt-workspace/.asof_proof"
ST="$ROOT/facts/dolt-workspace/.asof_state.json"
PREV_JSON="$ROOT/facts/dolt-workspace/.asof_prev.json"
rm -rf "$WS" "$ST" "$PREV_JSON" 2>/dev/null || true

# 受控 prev 变体：仅 FCT-000001 value 138 -> 137
"$PY" - "$ROOT/facts/facts.json" "$PREV_JSON" <<'PYEOF'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
doc = json.load(open(src, encoding="utf-8"))
for f in doc["facts"]:
    if f["fact_id"] == "FCT-000001":
        f["value"] = 137          # 受控历史值：真实为 138
json.dump(doc, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("PREV variant written: FCT-000001 value -> 137")
PYEOF

REAL_SHA="$("$PY" - "$ROOT" <<'PYEOF'
import subprocess, sys
r = subprocess.run(["git","-C",sys.argv[1],"rev-parse","--short","HEAD"],
                   capture_output=True, text=True)
print(r.stdout.strip())
PYEOF
)"

echo "== 导入 prev（合成溯源键 ASOPREV，value=137）=="
"$PY" deploy/dolt/import_from_git.py --data "$PREV_JSON" --sha ASOPREV \
  --apply --workspace "$WS" --state "$ST" | tail -3

echo "== 导入 head（真实 facts.json，value=138，SHA=$REAL_SHA）=="
"$PY" deploy/dolt/import_from_git.py --data facts/facts.json --sha "$REAL_SHA" \
  --apply --workspace "$WS" --state "$ST" | tail -3

# 一次性工作区固定 3 提交：init / prev(137) / head(138)
# 本机 dolt 版本拒绝把裸哈希当 AS OF 引用，但相对引用 HEAD / HEAD~1 与
# HASHOF() 函数均可用——直接断言历史差异，不必解析哈希。
cd "$WS" || exit 3

val_at() { # $1=ref(HEAD|HEAD~1) -> value_text（跳过 csv 表头）
  dolt sql -r csv -q "SELECT value_text FROM fact AS OF '$1' WHERE fact_id='FCT-000001'" | sed -n '2p'
}
V_PREV="$(val_at "HEAD~1")"   # 受控历史值 137
V_HEAD="$(val_at "HEAD")"     # 真实值 138

DIFF_N="$(dolt sql -r csv -q "SELECT COUNT(*) AS n FROM dolt_diff_fact WHERE to_commit=HASHOF('HEAD') AND from_commit=HASHOF('HEAD~1')" | sed -n '2p')"

PASS=1
[ "$V_PREV" = "137" ] || PASS=0
[ "$V_HEAD" = "138" ] || PASS=0
[ "${DIFF_N:-0}" -ge 1 ] 2>/dev/null || PASS=0

cat <<JSON
{
  "asof_prev_value": "$V_PREV",
  "asof_head_value": "$V_HEAD",
  "dolt_diff_rows": "$DIFF_N",
  "expected": {"prev": "137", "head": "138", "diff_ge": 1},
  "selftest": "$([ $PASS -eq 1 ] && echo PASS || echo FAIL)"
}
JSON

# 清理一次性工作区（仓内 facts/dolt-workspace 未受影响）
rm -rf "$WS" "$ST" "$PREV_JSON" 2>/dev/null || true
exit $([ $PASS -eq 1 ] && echo 0 || echo 1)
