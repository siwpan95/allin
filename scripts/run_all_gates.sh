#!/usr/bin/env bash
# allin 治理门禁「一键跑齐」—— 由 allin-governance-agent 调用。
#
# 依次跑三类门禁：
#   1) 20 道治理门禁 g00-meta…g20-facts（npm run check:governance）
#   2) 文档索引契约 D1–D8（npm run check:docs = python tools/gate/docs_index.py）
#   3) 本仓 monorepo 自检口径的 repocheck（README §本仓自检口径：排除 tools/，跳过规则 1/7）
#
# 行为：任一失败继续跑完其余，最后汇总并以非 0 退出码收尾，便于 agent 判定。
# 用法：bash scripts/run_all_gates.sh
# 可选：bash scripts/run_all_gates.sh --with-platform   （额外跑 platform 的 check/test/harness）

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# 解释器不写死机器路径（g01 判据）：ALLIN_PYTHON 显式指定优先，其次仓内 .venv，
# 最后才按 PATH 探测 python3 / python。
#
# 为什么必须钉死同一个解释器：门禁套件（run.ts）与本脚本里的 Python 工具若各用各的
# 解释器，同一次跑批的结论就不可复现。实测过的坑：PATH 上的便携 3.13.14 无 PyYAML，
# 而 g18-exceptions 要解析 exceptions.yml —— 套件因此报出「ledger-unusable」假红，
# 提交信息却写着「19/19 clean」。
#
# PyYAML 只有 g18-exceptions 需要；没有它的解释器仍可用（g18 自己会报环境错），
# 所以只作优先项不作硬性要求 —— 宁可少跑一道，也别把 18 道已跑的门禁一起丢掉。
can_yaml() { "$1" -c "import yaml" >/dev/null 2>&1; }
can_run()  { "$1" -c "import sys; print(sys.version_info[:2] >= (3, 9))" >/dev/null 2>&1; }

PY=""
PY_HAS_YAML="no"
if [ -n "${ALLIN_PYTHON:-}" ]; then
  PY="$ALLIN_PYTHON"
else
  # 仓内 .venv：仓库自己钉住依赖集的唯一候选（含 PyYAML），换机/换人跑结论一致。
  for cand in "$ROOT/.venv/Scripts/python.exe" "$ROOT/.venv/bin/python"; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
  done
  if [ -z "$PY" ]; then
    for cand in python3 python; do
      if command -v "$cand" >/dev/null 2>&1 && can_run "$cand"; then PY="$cand"; break; fi
    done
  fi
  # PATH 上的 python3/python 不可用时，再扫 PATH 里所有 python.exe（Windows）。
  # 路径由系统给出，源码里不出现盘符 —— g01 判据不变。
  if [ -z "$PY" ] && command -v where >/dev/null 2>&1; then
    while IFS= read -r cand; do
      cand="${cand%$'\r'}"
      [ -n "$cand" ] || continue
      if can_run "$cand"; then PY="$cand"; break; fi
    done <<EOF
$(where python 2>/dev/null)
EOF
  fi
fi
if [ -z "$PY" ]; then
  echo "ENV ERROR: 找不到可用的 Python 3.9+。" >&2
  echo "          用 ALLIN_PYTHON=<完整解释器> bash scripts/run_all_gates.sh 指定。" >&2
  exit 3
fi
if can_yaml "$PY"; then
  PY_HAS_YAML="yes"
else
  echo "WARN: 解释器缺 PyYAML（$PY）—— g18-exceptions 会报环境错，其余门禁照跑。" >&2
fi
# 让门禁套件用同一个解释器：run.ts 优先采纳 DSH_GOVERNANCE_PYTHON。
export DSH_GOVERNANCE_PYTHON="$PY"
fail=0
failures=()

# ---------------------------------------------------------------- 执行留痕
# 门禁结果此前只往 stdout 一打就没了，算不出「逃逸率 / 证据新鲜度 / 例外燃尽」。
# 每次执行落一行 JSONL（tools/gate/audit/ 已被 .gitignore 忽略，属运行时产物）。
GATE_RUNS="$ROOT/tools/gate/audit/gate-runs.jsonl"
HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

now_ms() {
  # GNU date 支持 %3N；BSD date 不支持 —— 退化到秒级（毫秒置 0），仍可统计。
  local v
  v="$(date +%s%3N 2>/dev/null)" || v=""
  case "$v" in
    ''|*%3N*|*[!0-9]*) echo $(( $(date +%s) * 1000 )) ;;
    *) echo "$v" ;;
  esac
}

log_run() {
  # $1=label $2=exit code $3=耗时(ms)
  mkdir -p "$(dirname "$GATE_RUNS")" 2>/dev/null || true
  # 标签里的反斜杠（Windows 解释器路径）会写成像 \P 这样的非法 JSON 转义，
  # 让整行解析失败、指标少算一条 —— 统一折成正斜杠再落盘。
  local label
  label="$(printf '%s' "$1" | tr '\\' '/')"
  printf '{"ts":"%s","commit":"%s","label":"%s","exit":%s,"ms":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$HEAD_SHA" "$label" "$2" "$3" >> "$GATE_RUNS" 2>/dev/null || true
}

run() {
  echo "==> $*"
  local t0 rc=0
  t0="$(now_ms)"
  if "$@"; then rc=0; else rc=$?; fi
  log_run "$*" "$rc" "$(( $(now_ms) - t0 ))"
  if [ "$rc" -eq 0 ]; then
    echo "    [ok]"
  else
    echo "    [FAIL] exit=$rc"
    fail=1
    failures+=("$*")
  fi
}

echo "allin 治理门禁跑齐 @ $ROOT"
echo "----------------------------------------"
run npm run check:governance
run "$PY" tools/gate/docs_index.py
# agent 行为回归：门禁判得了仓库，判不了「agent 行为」（仓根自发现、工具面、人格自述与
# registry 是否一致）。这组固定样例补的就是这一层 —— 改配置/提示词/工具面前后各跑一次。
run "$PY" tools/gate/agent_regression.py
# 派生副本新鲜度：治理段一份正文 + 三份副本（存档件 / bundle / 已挂载 profile 层）。
# 仓内门禁看不见仓外那份挂载层 —— 2026-10-29 它就落后了整整一代（仍写「15 道门禁」）。
# 落后即 exit 3；本机没有挂载层时该脚本记 skipped（不是通过）。
run "$PY" preset/allin/refresh-gov-block.py --check
run "$PY" tools/repocheck/main.py . --exclude tools,vendor,preset --skip-rules 1,7 --fail-on error

if [ "${1:-}" = "--with-platform" ]; then
  echo "----------------------------------------"
  echo "[with-platform] 额外跑 platform 门禁（需先 cd platform && npm install）"
  if [ -d platform ]; then
    ( cd platform && npm run check && npm test && npm run harness ) || { fail=1; failures+=("platform gates"); }
  fi
fi

echo "----------------------------------------"
if [ "$fail" -ne 0 ]; then
  echo "门禁未全绿，失败项："
  for f in "${failures[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "全部门禁通过。"
