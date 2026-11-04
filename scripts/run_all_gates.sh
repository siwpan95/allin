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
# 一次跑批 = 一个 RUN_ID。秒级 ts 会把同一批拆成几十个「秒组」；gate_metrics.py
# 旧口径按 ts[:19] 分组，只要某一秒恰好没失败就把它当「最近一次全绿」，
# 于是一次**有失败的跑批**也可能被洗成 fresh（假绿）。落 batch 字段后，
# 指标按真正的一次跑批判定全部 exit=0 才算全绿；历史无 batch 的行由
# gate_metrics.py 按「同 commit + 时间邻近」聚类兼容，见该文件 group_batches()。
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"

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
  printf '{"ts":"%s","batch":"%s","commit":"%s","label":"%s","exit":%s,"ms":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RUN_ID" "$HEAD_SHA" "$label" "$2" "$3" >> "$GATE_RUNS" 2>/dev/null || true
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

# --- 发布区卫生门禁：发布区缺席时显式降级为 skip（不记 failed）---
# 发布区（同级 repos/ 或 $PROJECTS_ROOT）在本仓 CI 里不存在，属「没有可扫的仓」，
# 不是「卫生不合格」。若按原样跑 repo_hygiene.py --all，它会因找不到任何 git 仓而以
# env-error(3) 退出，把整批门禁拖红 —— 这正是此前 CI 连续红的根因之一（B1）。
# 本地有发布区时行为与之前完全一致；发布区缺席/为空时记 [SKIP]，不计入失败。
_run_repo_hygiene() {
  local repos_root="${PROJECTS_ROOT:-}"
  if [ -z "$repos_root" ] && [ -d "$ROOT/repos" ]; then
    repos_root="$ROOT/repos"
  fi
  if [ -z "$repos_root" ] && [ -d "${ROOT%/*}/repos" ]; then
    repos_root="${ROOT%/*}/repos"
  fi
  if [ -z "$repos_root" ] || [ ! -d "$repos_root" ]; then
    echo "==> $PY tools/repo_hygiene.py --all"
    echo "    [SKIP] 未检测到发布区（无同级 repos/ 且未设 \$PROJECTS_ROOT）：无可扫仓，非卫生不合格"
    log_run "repo_hygiene:skip(no-publish-area)" 0 0
    return 0
  fi
  local has_repo=0
  for d in "$repos_root"/*/; do
    [ -d "${d}.git" ] && { has_repo=1; break; }
  done
  if [ "$has_repo" -eq 0 ]; then
    echo "==> $PY tools/repo_hygiene.py --all"
    echo "    [SKIP] 发布区 $repos_root 下没有任何 git 仓：无可扫对象，非卫生不合格"
    log_run "repo_hygiene:skip(empty-publish-area)" 0 0
    return 0
  fi
  run "$PY" tools/repo_hygiene.py --all
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
run "$PY" tools/repocheck/main.py . --exclude tools,vendor,preset,packages,scripts,website --skip-rules 1,7 --fail-on error
# packages/ 与 website/ 都是 monorepo 的中间目录（与 tools/ 同类），故本行一并排除；
# packages/ 内部的单个包按「子件」口径单独体检（下方一行）；website/ 则另起 CI job
# 跑 `npm run smoke`（本地 19/19 全绿），其健康度不靠 repocheck 兜底。
# packages/ 当前只有一个包；新增包时要在这里补一行（或改成循环）。
if [ -d packages/allin-governance ]; then
  run "$PY" tools/repocheck/main.py packages/allin-governance \
      --exclude src,tests --skip-rules 1,2,4,5 --fail-on error
fi

# --- 2026-11-01 补齐三项此前未接进自动化的辅助门禁 ---
# 起因：README §本仓自检口径承诺 A/B/C 三条，脚本却只跑了 A) 与 C)，
# B) 自 2026-10-30 起一直红着没人发现。**门禁写了不跑 = 没有门禁**，故一并补入。
# ① README §本仓自检口径 B)：A) 已把 tools/ 排除，故 tools/ 的子件在这里单独体检。
run "$PY" tools/repocheck/main.py tools/ --exclude gate --skip-rules 1,2,4,5 --fail-on error
# ② .ps1 编码：PowerShell 5.1 对无 UTF-8 BOM 的脚本按 ANSI 解码，
#    中文变乱码并报一堆假语法错误（本机边界里那条"一边绿一边红"的编码指纹）。
run "$PY" tools/gate/check_ps1_bom.py
# ③ 仓库卫生 H1-H8：扫发布区全部仓的 git 跟踪面（136 仓）。
#    基线棘轮**只单向收紧**：已评估的存量记在 tools/gate/audit/hygiene_baseline.csv，
#    明细台账见同目录 hygiene_debt_2026-11-01.json —— 刷新基线不等于债务消失，台账才是待办清单。
#    发布区缺席时由 _run_repo_hygiene 降级为 skip（见其注释），避免把整批门禁拖红。
_run_repo_hygiene
# ④ 门禁双落点漂移自检：本工具把"两份必须一致"变成退出码（F1 收口动作）。
#    实跑比对依赖外部工作副本（/tools/gate），CI 上不存在 ⇒ SKIPPED（不是通过）；
#    故 CI 跑 --selfcheck 做工具自身逻辑回归（EOL 归一化 / 真漂移判红 / 缺对端 SKIP / 同目录守卫）。
run "$PY" tools/gate/check_gate_drift.py --selfcheck

# --- 2026-11-04 工程审查补齐：把已有测试接进跑批（测试写了不跑 = 没有测试）---
# ⑤ kernel 单元测试：导入冒烟 + 无 watchdog 回归（vendor/cordis hmr 降级路径，
#    该缺陷此前因测试从未进跑批而潜伏——kernel 在零依赖环境整体不可导入）。
#    纯标准库 unittest，零第三方依赖。
run "$PY" -m unittest discover -s kernel/tests
# ⑥ repocheck 自身 30 条规则的测试套件（695 行）。自带无 pytest 兜底跑法（仅标准库），
#    从仓根直跑时脚本目录自动进 sys.path，import report/scanner 可解析。
run "$PY" tools/repocheck/test_scanner.py
# ⑦ 仓根 README「可机检事实」护栏（2026-11-04 工程审查 Docu Top3-2 落地）：
#    README 引用的仓内路径存在性 + allin-governance 版本与 pyproject 对账 ——
#    README 不在 docs_index 判据内，本门禁是其唯一机检护栏（曾实测四处漂移静默存活）。
run "$PY" tools/gate/check_readme_refs.py

if [ "${1:-}" = "--with-platform" ]; then
  echo "----------------------------------------"
  echo "[with-platform] 额外跑 platform 门禁（需先 cd platform && npm install）"
  # 三项各自 run：原写法 ( cd platform && npm run check && npm test && npm run harness )
  # 用 && 串联，check 一红就短接，test / harness 根本没跑；而且整行不写 log_run，
  # 三项在治理指标里完全不可见（逃逸率 / 延迟预算都算不到）。改后逐项独立留痕、独立计失败。
  # 注：本机若未全量检出注册表路径，check / harness 会因 PLATFORM_PATH_CHECK 判据报环境红；
  #     这是环境事实不是代码缺陷，需要时显式带 PLATFORM_PATH_CHECK=absolute 跑本脚本。
  if [ -d platform ]; then
    run npm --prefix platform run check
    run npm --prefix platform test
    run npm --prefix platform run harness
  else
    echo "    [SKIP] 未找到 platform/ 目录"
    log_run "platform:skip(no-platform-dir)" 0 0
  fi
fi

echo "----------------------------------------"
if [ "$fail" -ne 0 ]; then
  echo "门禁未全绿，失败项："
  for f in "${failures[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "全部门禁通过。"
