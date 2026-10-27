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

PY="${ALLIN_PYTHON:-E:/Python314/python.exe}"
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
