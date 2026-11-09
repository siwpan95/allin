#!/usr/bin/env bash
# allin 治理门禁「一键跑齐」—— 由 allin-governance-agent 调用。
#
# 依次跑三类门禁：
#   1) 20 道治理门禁 g00-meta…g20-facts（npm run check:governance）
#   2) 文档索引契约 D1–D17（npm run check:docs = python tools/gate/docs_index.py）
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
# 2026-11-08 深度审核 A1：严格模式同时下发到单门禁层 ——
# govlib.Report.skip() 在严格模式下不再以 exit 0 混进 clean。
if [ "${ALLIN_STRICT_SKIP:-0}" = "1" ]; then
  export ALLIN_GATE_STRICT_SKIP=1
fi
# 【不要在这里 export PYTHONIOENCODING】—— 2026-11-04 实测教训：
# Windows CI runner 的 stdout 默认 cp1252，中文诊断会 UnicodeEncodeError；但改成
# 全局 PYTHONIOENCODING=utf-8 会连**测试 spawn 的子进程**一起改：那些用
# subprocess.run(text=True) 且未指定 encoding 的旧测试会按 cp1252 解码 UTF-8 中文，
# 读线程抛 UnicodeDecodeError 后 stderr 变成 None，测试反而崩（kernel/tests 已实测复现）。
# 正确做法：由具体脚本自己 reconfigure stdio（见 check_gate_drift.py），别动全局环境。
fail=0
failures=()
# SKIP 计数（2026-11-07）：SKIP ≠ 通过，但此前它只散落在各步的 echo 里，
# 汇总段完全不可见 —— 「长期 SKIP 变默认绿灯」的评审意见正中这里。
# note_skip() 统一三件事：echo 留痕、log_run 记账（标签口径与历史完全一致，
# 不动 gate_metrics 的解析面）、skips[] 聚合供汇总行展示。
skips=()
# 2026-11-08 深度审核 A3：把「环境不适用」与「本应跑却没跑」分开。
# 环境性 SKIP（CI 无发布区 / 缺 Node 依赖 / 无 PowerShell / 无 platform 目录）
# 不是检查项缺失，记入 not_applicable；只有真实性 SKIP 才让 status=incomplete。
# 这样 CI 的 status=clean 才真正表示「所有适用项都跑过且通过」，而不会被
# 「含环境性 SKIP ⇒ 永远 incomplete」逼成常红，也不会再让没检查冒充通过。
BENIGN_SKIP_PATTERNS=(
  'repo_hygiene:skip('
  'smoke:e2e:skip(missing-node-deps'
  'restore-drill:skip(no-powershell'
  'platform:skip(no-platform-dir'
)
not_applicable=()

is_environmental_skip() {
  local s="$1" p
  for p in "${BENIGN_SKIP_PATTERNS[@]}"; do
    case "$s" in *"$p"*) return 0 ;; esac
  done
  return 1
}

note_skip() {
  # $1=log 标签（沿用既有 <工具>:skip(<原因>) 口径） $2=人读原因
  echo "    [SKIP] $2"
  # SKIP 是「没检查」，不是「执行成功」。留痕同时写两样东西：
  #   · 结构化字段 "skipped":true —— 这是判定的**唯一真相源**；
  #   · 标签里的 :skip(...) —— 仅为兼容本字段落地前的历史留痕（回退用）。
  # log_run 第 4 个参数即 skipped（缺省 false；note_skip 传 true）。
  # 注意：SKIP 行**不丢弃** —— 丢了就没法单列计数，逃逸率分母与 p95 的口径
  # 由 tools/gate/gate_metrics.py 统一排除（见该文件 is_skipped / real_runs）。
  log_run "$1" 0 0 true
  if is_environmental_skip "$1"; then
    not_applicable+=("$1")
  else
    skips+=("$1")
  fi
}

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

# 5MB 轮转（对齐 launch.js tasks.log 口径）：超限改名 .1（覆盖旧 .1），防 JSONL 无限膨胀。
rotate_if_large() {
  local f="$1"
  if [ -f "$f" ] && [ "$(wc -c < "$f" 2>/dev/null || echo 0)" -gt $((5 * 1024 * 1024)) ]; then
    mv -f "$f" "$f.1"
  fi
}

log_run() {
  # $1=label $2=exit code $3=耗时(ms) $4=是否 SKIP（true/false，缺省按真跑 false）
  # 恒定写 `skipped` 字段保持结构稳定：真跑 false / SKIP true。旧行无此字段 ⇒
  # 消费方按真跑兼容回放（gate_metrics.py / status_service / portal / mcp 同口径）。
  # SKIP 不计入 failed / escapeRate / lastOkAt，整批全 SKIP 也不得算全绿。
  local skipped="${4:-false}"
  mkdir -p "$(dirname "$GATE_RUNS")" 2>/dev/null || true
  rotate_if_large "$GATE_RUNS"
  # 标签里的反斜杠（Windows 解释器路径）会写成像 \P 这样的非法 JSON 转义，
  # 让整行解析失败、指标少算一条 —— 统一折成正斜杠再落盘。
  local label
  label="$(printf '%s' "$1" | tr '\\' '/')"
  printf '{"ts":"%s","batch":"%s","commit":"%s","label":"%s","exit":%s,"ms":%s,"skipped":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RUN_ID" "$HEAD_SHA" "$label" "$2" "$3" "$skipped" >> "$GATE_RUNS" 2>/dev/null || true
}

# GitHub Actions 的 ::error:: workflow command 会把失败项写进 check-run annotations，
# 而 annotations 是**匿名可读**的（job logs 端点需仓库 admin 权限，实测 403）。
# 2026-11-04 复核 CI 首跑时，4 个 job 全红却只能看到通用 exit code 1 —— 这个
# 「红了但不知道哪一步红」的断层由此补上。数据里的 % / CR / LF 必须百分号编码，
# 否则 annotation 会被截断。仅 GITHUB_ACTIONS=true 时输出，本地跑批日志不受影响。
gh_escape() {
  local s="$1"
  s="${s//%/%25}"
  s="${s//$'\r'/%0D}"
  s="${s//$'\n'/%0A}"
  printf '%s' "$s"
}

run() {
  echo "==> $*"
  local t0 rc=0 out tail_txt
  t0="$(now_ms)"
  out="$(mktemp "${TMPDIR:-/tmp}/allin-gate-XXXXXX")"
  if "$@" > "$out" 2>&1; then rc=0; else rc=$?; fi
  cat "$out"
  log_run "$*" "$rc" "$(( $(now_ms) - t0 ))" false
  if [ "$rc" -eq 0 ]; then
    echo "    [ok]"
  else
    echo "    [FAIL] exit=$rc"
    if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
      printf '::error::门禁步骤失败（exit=%s）：%s\n' "$rc" "$(gh_escape "$*")"
      # 只报「哪条命令挂了」还不足以定位，把该命令的尾部输出一并推成 annotation：
      # job logs 端点匿名 403，annotations 是唯一公开可读的通道；多行用 %0A 连接。
      tail_txt="$(tail -n 12 "$out")"
      printf '::error::失败命令尾部输出：%s\n' "$(gh_escape "$tail_txt")"
    fi
    fail=1
    failures+=("$*")
  fi
  rm -f "$out"
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
    note_skip "repo_hygiene:skip(no-publish-area)" \
      "未检测到发布区（无同级 repos/ 且未设 \$PROJECTS_ROOT）：无可扫仓，非卫生不合格"
    return 0
  fi
  local has_repo=0
  for d in "$repos_root"/*/; do
    [ -d "${d}.git" ] && { has_repo=1; break; }
  done
  if [ "$has_repo" -eq 0 ]; then
    echo "==> $PY tools/repo_hygiene.py --all"
    note_skip "repo_hygiene:skip(empty-publish-area)" \
      "发布区 $repos_root 下没有任何 git 仓：无可扫对象，非卫生不合格"
    return 0
  fi
  run "$PY" tools/repo_hygiene.py --all
}

echo "allin 治理门禁跑齐 @ $ROOT"
echo "----------------------------------------"
run npm run check:governance
# 门禁工具自身回归（selfcheck-all）：证明「每道门禁仍能检出问题」，堵住
# 「门禁被改坏却 CI 常绿」的盲区（S2 · 2026-11-08 审查闭环）。与 check:governance
# 同源调用链（run.ts --selfcheck-all），不引入新依赖、不触外部资源。
run npm run check:governance:selfcheck
run "$PY" tools/gate/docs_index.py
# docs_index 自检（D1–D17 夹具）：此前只在手工跑（「写了不跑」），且 Windows 无符号链接
# 权限时干净夹具恒被 D6 误报 ⇒ 修为「探测权限后显式 SKIP」并接入跑批。
run "$PY" tools/gate/docs_index.py --selfcheck
# S9（2026-11-08 审查闭环）：度量口径本身也是门禁 —— gate_metrics.py --selfcheck
# 接入跑批，随每次跑批回归「SKIP 单列 / 反假绿 / legacy 兼容回放」，
# 防止指标口径被改坏却 CI 常绿（门禁写了不跑 = 没有门禁）。
run "$PY" tools/gate/gate_metrics.py --selfcheck
# agent 行为回归：门禁判得了仓库，判不了「agent 行为」（仓根自发现、工具面、人格自述与
# registry 是否一致）。这组固定样例补的就是这一层 —— 改配置/提示词/工具面前后各跑一次。
run "$PY" tools/gate/agent_regression.py
# g21 agent-parity（2026-11-04 P2 编排工程化落地）：routes.yaml ⇄ SKILL.md 锚点 ⇄
# GOVERNANCE 段锚点三方对账 + 15 个专项 skill 入口存在性（M5 skill 台账门禁化）。
# 判据产物落 tools/gate/audit/g21-runs.jsonl（JSONL 逐行，audit/ 已被 .gitignore 覆盖）。
# 放在 refresh-gov-block --check 之前：失败定位从「台账↔正文」到「正文↔副本」单向推进。
run "$PY" tools/gate/agent_parity.py
# --- 结构化事实源离线地基（2026-11-09，用户按「离线可用优先」拍板 O1=B / O2=A / O3=A）---
# 四条独立脚本，照 g21 模式接跑批；g00–g20 的 **20 道聚合口径不变**，
# 且全部零第三方依赖、零服务依赖 —— 拔网 + 停三栈 + 删派生库时仍须全绿（离线北极星）。
# ① g22：结构化真身过 JSON Schema（纯文本，facts/facts.json ⇄ facts/facts.schema.json）
run "$PY" tools/facts/cli.py validate
# ② g23：doc_refs 引用完整性 + 生成区 marker 漂移。生成物未启用时**显式 SKIPPED 并计数**，
#    不冒充通过（待 P2 真身反转后启用阻断）；未做项已登记交接卷 §一百四十六。
run "$PY" tools/gate/facts_parity.py
# ③ g24：文档内相对路径。棘轮基线 tools/gate/baseline/relative-refs.txt 挂存量 10 条，
#    只阻断**新增**断链；docs/记录/ 历史卷按只增不改永久豁免（SPEC-005 §3.12）。
run "$PY" tools/gate/relative_refs_gate.py --json
# ④ 离线北极星端到端验收：无派生库时 get/asof 回落纯 JSON、判据可离线自检、派生层可重建。
run "$PY" tools/facts/cli.py offline-check
# --- B 期（2026-11-09）：溯源与导入器判据，同样零服务依赖 ---
# ⑤ g25：每条 fact 的 source_file:line 完整性 + 下游 state 的 source_git_sha 可解析；
#    下游未接入时显式 SKIPPED 并计数（不冒充通过、不拖红跑批）。
run "$PY" tools/gate/facts_provenance.py
# ⑥ Dolt 导入器判据自证：幂等 SQL / 显式 CALL DOLT_COMMIT / sha 入 SQL；不写下游、不需要 dolt 二进制。
run "$PY" deploy/dolt/import_from_git.py --selftest
# ⑥ g26：意图态内部一致性漂移（独立门禁，g21 模式；蓝图 g26）。
#    ports.yaml⇄facts.json.ports 方向性对账（facts 必须是子集，多出即真漂移；ports.yaml 多出记 INFO 不阻断，
#    待 P0-A 迁移完成后自动归零）/ facts[].source_line 真实性 / Dolt state 的 source_git_sha⇄HEAD
#    （派生物可删可重建，滞后记 WARN 不阻断，仅「分歧（无祖先关系）」属真漂移阻断）/
#    机器 md 目录数 ⇄ facts.json.machines 计数一致。
#    零第三方依赖（ports 判据需 yaml，缺则 SKIP 该判据不拖红）；拔网 + 停三栈时仍须可跑（离线北极星）。
run "$PY" tools/gate/facts_drift.py --selftest
run "$PY" tools/gate/facts_drift.py --json
# 派生副本新鲜度：治理段一份正文 + 三份副本（存档件 / bundle / 已挂载 profile 层）。
# 仓内门禁看不见仓外那份挂载层 —— 2026-10-29 它就落后了整整一代（仍写「15 道门禁」）。
# 落后即 exit 3；本机没有挂载层时该脚本记 skipped（不是通过）。
run "$PY" preset/allin/refresh-gov-block.py --check
# monorepo 扫描口径已收编进 repocheck 本身（--profile，2026-11-07）：规则豁免
# 语义由工具统一定义，不再在本脚本手写 --skip-rules（曾散落三处，属第二套口径的温床）。
# 中间目录名单是本仓布局事实，仍由 --exclude 提供。
# 2026-11-08：tests/ 是 monorepo 的内部测试目录，不是独立项目，裸跑会产生
# 「无 README / 无 LICENSE / 无依赖声明」等必然假阳性（README 已写明此口径）。
# 2026-11-09 B 期：facts/（数据面真身）与 deploy/（三栈配置）同为 monorepo 中间目录，
# 不是独立项目；裸跑会必然产生「无 LICENSE / 无依赖声明 / README 结构不完整」假阳性。
run "$PY" tools/repocheck/main.py . --profile monorepo --exclude tools,vendor,preset,packages,scripts,website,tests,facts,deploy --fail-on error
# packages/ 与 website/ 都是 monorepo 的中间目录（与 tools/ 同类），故本行一并排除；
# packages/ 内部的单个包按「子件」口径单独体检（下方一行）；website/ 则另起 CI job
# 跑 `npm run smoke`（本地 19/19 全绿），其健康度不靠 repocheck 兜底。
# packages/ 当前只有一个包；新增包时要在这里补一行（或改成循环）。
if [ -d packages/allin-governance ]; then
  run "$PY" tools/repocheck/main.py packages/allin-governance \
      --profile component --exclude src,tests --fail-on error
fi

# --- 2026-11-01 补齐三项此前未接进自动化的辅助门禁 ---
# 起因：README §本仓自检口径承诺 A/B/C 三条，脚本却只跑了 A) 与 C)，
# B) 自 2026-10-30 起一直红着没人发现。**门禁写了不跑 = 没有门禁**，故一并补入。
# ① README §本仓自检口径 B)：A) 已把 tools/ 排除，故 tools/ 的子件在这里单独体检。
run "$PY" tools/repocheck/main.py tools/ --profile component --exclude gate --fail-on error
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

# --- ⑤ 北极星三面冒烟（smoke:e2e）——
#    2026-11-06 补入。此前它在 CI 的 gates-windows job 里单独跑（且显式设了
#    ALLIN_PYTHON），但**本地跑批不含它** ⇒ 本机默认环境（PATH 上是无 PyYAML 的
#    便携 Python）下 CP1/CP2 报 ModuleNotFoundError: yaml 假红，CI 却永远绿
#    —— 「CI 绿 / 本机红」的机制性盲区。门禁写了不跑 = 没有门禁（第四例）。
#    修法：smoke_e2e.mjs 改用 scripts/resolve_python.mjs（与本脚本同源解析链：
#    ALLIN_PYTHON → 仓内 .venv → PATH，优先选带 PyYAML 的候选）。
#
#    降级口径（对齐上面 _run_repo_hygiene 的既有模式）：冒烟依赖两侧 Node 依赖
#    （platform/node_modules 的 @allin/core workspace link + website/node_modules）。
#    干净检出里它们不存在（被 .gitignore 忽略）⇒ 此时记 SKIP，不计入失败 ——
#    「没有可跑的对象」不是「北极星不合格」。依赖在位时则真跑、真判红。
if [ ! -d "$ROOT/platform/node_modules/@allin/core" ] || [ ! -d "$ROOT/website/node_modules" ]; then
  if [ "${ALLIN_E2E_REQUIRE_DEPS:-}" = "1" ]; then
    # 强约束模式：本环境声明「北极星必须真跑」，缺依赖即失败（而非静默 SKIP）。
    # 用于北极星失明不可接受的宿主/计划任务环境（S3 · 2026-11-08 审查闭环）。
    echo "==> npm run smoke:e2e（ALLIN_E2E_REQUIRE_DEPS=1：缺依赖按失败处理）"
    run npm run smoke:e2e
  else
    # 默认降级：缺依赖记 SKIP（not a pass），不计入失败——「没有可跑的对象」
    # 不是「北极星不合格」。SKIP 已在汇总行显式可见（S3 同次闭环）。
    echo "==> npm run smoke:e2e"
    note_skip "smoke:e2e:skip(missing-node-deps)" \
      "两侧 Node 依赖未安装（platform/node_modules/@allin/core 或 website/node_modules 缺失）：无可跑对象，非冒烟不合格"
    echo "    [SKIP] 装依赖后复跑：npm ci --prefix website && npm ci --prefix platform"
    echo "    [SKIP] 强约束环境可设 ALLIN_E2E_REQUIRE_DEPS=1 让缺依赖直接失败"
  fi
else
  run npm run smoke:e2e
fi

# --- 2026-11-04 工程审查补齐：把已有测试接进跑批（测试写了不跑 = 没有测试）---
# ⑤ kernel 单元测试：导入冒烟 + 无 watchdog 回归（vendor/cordis hmr 降级路径，
#    该缺陷此前因测试从未进跑批而潜伏——kernel 在零依赖环境整体不可导入）。
#    纯标准库 unittest，零第三方依赖。
run "$PY" -m unittest discover -s kernel/tests
# ⑥ repocheck 自身 30 条规则的测试套件（695 行）。自带无 pytest 兜底跑法（仅标准库），
#    从仓根直跑时脚本目录自动进 sys.path，import report/scanner 可解析。
# B1 整改：原来直跑脚本只走 test_scanner.py:723 的 _smoke()（约 10 项 check），
# 62 个 pytest 用例虽全绿却从未进跑批。改为 pytest 全量收集，与 CI 口径一致。
run "$PY" -m pytest tools/repocheck/test_scanner.py -q
# ⑦ 仓根 README「可机检事实」护栏（2026-11-04 工程审查 Docu Top3-2 落地）：
#    README 引用的仓内路径存在性 + allin-governance 版本与 pyproject 对账 ——
#    README 不在 docs_index 判据内，本门禁是其唯一机检护栏（曾实测四处漂移静默存活）。
run "$PY" tools/gate/check_readme_refs.py
# ⑧ 架构资产对账（2026-11-04 体检落地，ADR-0009）：architecture/ 的 SVG 与 adr/ 在
#    文档契约判据之外，本门禁把「SVG 数字 / adr 索引 / website 端口登记」六项声明
#    对账成退出码 —— 体检实测 5 处漂移（ADR 索引缺 0006–0008、图内三处数字落后两代）
#    曾静默存活近月，此后同类漂移跑批即红。
run "$PY" tools/gate/check_arch_assets.py
# ⑨ 月度治理盘点器自身逻辑回归（ERP P2 备用路线，2026-11-07）：真跑由
#    ALLIN-monthly-audit 计划任务负责（每台机器本地 JSONL），这里只跑夹具自测，
#    每次跑批顺带证明「月度幂等守卫 / 表内自洽 / 发布区软观测」没被改坏。
#    门禁写了不跑 = 没有门禁（第五例）。
run "$PY" tools/deploy/monthly_audit.py --selfcheck
# 备份恢复演练（B3 闭环 · 2026-11-08 审查）：证明备份可还原、数据耐久性可验证。
# 仅 Windows（有 PowerShell）真跑；其余平台缺解释器记 SKIP（not a pass），
# 与既有「缺依赖即 SKIP」纪律一致，不强行跨平台。
if command -v powershell.exe >/dev/null 2>&1; then
  run powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/deploy/test_restore_drill.ps1
else
  note_skip "restore-drill:skip(no-powershell)" \
    "当前平台无 PowerShell，无法跑备份恢复演练（Windows 专属，月度随 monthly-audit 跑）"
fi

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
    note_skip "platform:skip(no-platform-dir)" "未找到 platform/ 目录"
  fi
fi

echo "----------------------------------------"
# SKIP 聚合展示（2026-11-07）：让「没检查」在第一眼的汇总里就和「检查通过」分开，
# 不需要人去翻分步输出或注释。SKIP 数量是治理盲区的直接指标——长期非零的 SKIP
# 名单应当被定期审视（升 fixture / 收编口径 / 补环境），而不是默认绿灯。
if [ "${#skips[@]}" -gt 0 ]; then
  echo "SKIP ${#skips[@]} 项（not a pass，不计入失败）："
  printf '  - %s\n' "${skips[@]}"
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '::warning::门禁批含 %s 项 SKIP（skip ≠ pass）：%s\n' \
      "${#skips[@]}" "$(gh_escape "$(printf '%s; ' "${skips[@]}")")"
  fi
fi
# 机器可读汇总行：PR 模板 / CI 一律贴这一行，不再以「全部门禁通过。」作准出凭据。
# status: clean（所有适用项全检全绿）/ incomplete（含真实性 SKIP）/ failed
# 环境不适用项单列 not_applicable：如实留痕，但不冒充检查、也不把 CI 逼成常红。
SKIP_N="${#skips[@]}"
NA_N="${#not_applicable[@]}"
FAIL_N="${#failures[@]}"
if [ "$fail" -ne 0 ]; then
  SUMMARY_STATUS="failed"
elif [ "$SKIP_N" -gt 0 ]; then
  SUMMARY_STATUS="incomplete"
else
  SUMMARY_STATUS="clean"
fi
printf 'ALLIN_GATE_SUMMARY status=%s fail=%s skips=%s not_applicable=%s\n' \
  "$SUMMARY_STATUS" "$FAIL_N" "$SKIP_N" "$NA_N"
if [ "$NA_N" -gt 0 ]; then
  echo "环境不适用 ${NA_N} 项（不声称通过）："
  for s in "${not_applicable[@]}"; do echo "  - $s"; done
fi

if [ "$fail" -ne 0 ]; then
  echo "门禁未全绿，失败项："
  for f in "${failures[@]}"; do echo "  - $f"; done
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '::error::全部门禁未通过，共 %s 项失败：%s\n' \
      "${#failures[@]}" "$(gh_escape "$(printf '%s; ' "${failures[@]}")")"
    printf '::error::%s\n' "$(gh_escape "ALLIN_GATE_SUMMARY status=failed fail=${FAIL_N} skips=${SKIP_N}")"
  fi
  exit 1
fi
if [ "$SKIP_N" -gt 0 ]; then
  echo "门禁批未全检（含 ${SKIP_N} 项真实性 SKIP）：未检查项不算通过，禁止以「全部门禁通过。」作准出。"
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '::warning::%s\n' "$(gh_escape "ALLIN_GATE_SUMMARY status=incomplete fail=0 skips=${SKIP_N}")"
  fi
  echo "存在真实性 SKIP（非环境性），判定 exit 2（SKIP ≠ pass）。"
  exit 2
fi
# 严格模式：连环境不适用项也不接受（按需开启）。
if [ "${ALLIN_STRICT_SKIP:-0}" = "1" ] && [ "$NA_N" -gt 0 ]; then
  echo "ALLIN_STRICT_SKIP=1：含 ${NA_N} 项环境性 SKIP，判定 exit 2。"
  exit 2
fi
echo "全部门禁通过（环境不适用 ${NA_N} 项已如实标注，不计入通过）。"
