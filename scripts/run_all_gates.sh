#!/usr/bin/env bash
# allin 治理门禁「一键跑齐」—— 由 allin-governance-agent 调用。
#
# 依次跑三类门禁：
#   1) 15 道治理门禁 g00-meta…g15-docs-contract（npm run check:governance）
#   2) 文档索引契约 D1–D8（npm run check:docs = python tools/gate/docs_index.py）
#   3) 本仓 monorepo 自检口径的 repocheck（README §本仓自检口径：排除 tools/，跳过规则 1/7）
#
# 行为：任一失败继续跑完其余，最后汇总并以非 0 退出码收尾，便于 agent 判定。
# 用法：bash scripts/run_all_gates.sh
# 可选：bash scripts/run_all_gates.sh --with-platform   （额外跑 platform 的 check/test/harness）

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# 解释器不写死机器路径（g01 判据）：环境变量优先，其次按 PATH 探测 python3 / python。
# 探测必须带 tkinter：tools/repocheck/main.py 启动即 import tkinter，托管的阉割版
# Python 会直接 ModuleNotFoundError，门禁会假红。所以候选解释器要真测一下。
# 候选必须真能 import tkinter：tools/repocheck/main.py 启动即 import tkinter，
# 托管的阉割版 Python 会直接 ModuleNotFoundError，门禁会假红。
can_tk() { "$1" -c "import tkinter" >/dev/null 2>&1; }

PY=""
if [ -n "${ALLIN_PYTHON:-}" ]; then
  PY="$ALLIN_PYTHON"
else
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && can_tk "$cand"; then PY="$cand"; break; fi
  done
  # PATH 上的 python3/python 不可用时，再扫 PATH 里所有 python.exe（Windows）。
  # 路径由系统给出，源码里不出现盘符 —— g01 判据不变。
  if [ -z "$PY" ] && command -v where >/dev/null 2>&1; then
    while IFS= read -r cand; do
      cand="${cand%$'\r'}"
      [ -n "$cand" ] || continue
      if can_tk "$cand"; then PY="$cand"; break; fi
    done <<EOF
$(where python 2>/dev/null)
EOF
  fi
fi
if [ -z "$PY" ]; then
  echo "ENV ERROR: 找不到能 import tkinter 的 python（repocheck 需要它）。" >&2
  echo "          用 ALLIN_PYTHON=<完整解释器> bash scripts/run_all_gates.sh 指定。" >&2
  exit 3
fi
fail=0
failures=()

run() {
  echo "==> $*"
  if "$@"; then
    echo "    [ok]"
  else
    local rc=$?
    echo "    [FAIL] exit=$rc"
    fail=1
    failures+=("$*")
  fi
}

echo "allin 治理门禁跑齐 @ $ROOT"
echo "----------------------------------------"
run npm run check:governance
run npm run check:docs
run "$PY" tools/repocheck/main.py . --exclude tools,vendor --skip-rules 1,7 --fail-on error

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
