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
#
# 分类口径（2026-11-10 深度审计 #13）：BENIGN_SKIP_PATTERNS 是**纯环境不适用**标签
# 白名单，按「工具名 + skip(原因)」子串匹配 note_skip 的 $1 标签；命中 → not_applicable，
# 未命中 → skips[]（真实性 SKIP，status=incomplete）。新增环境性 SKIP 必须同步登记，
# 否则会被误算成「本应跑却没跑」让 status 失真（scan_hardcoded 此前即漏登）；反过来
# 也**不得**把真实失败/真实缺失塞进白名单 —— 那是把 SKIP 当 pass 的反向偷渡。
BENIGN_SKIP_PATTERNS=(
  'repo_hygiene:skip('
  # 发布区治理门禁：CI 上无同级 repos/ 是**环境不适用**，与 repo_hygiene 同款。
  # 2026-11-21 首接时漏登此标签 ⇒ CI 把它当「真实性 SKIP」判 exit 2，
  # 全量门禁本地绿但 CI 红 —— 与首次接 scan_hardcoded 时踩的是同一坑。
  'publish_area_gate:skip('
  'smoke:e2e:skip(missing-node-deps'
  'restore-drill:skip(no-powershell'
  'scan_hardcoded:skip(no-powershell'
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

# --- 发布区根推导（全脚本唯一实现）-----------------------------------------
# 两种合法布局，判据相同：
#   · 同级（历史）：<工作区>/allin 与 <工作区>/repos 并立 ⇒ 发布区 = <父>/repos
#   · 内含（2026-11-23 起）：本仓自己就住在发布区里 <repos>/allin ⇒ 发布区 = 父目录本身
# 旧推导只认同级，内含布局下得到 <repos>/repos（不存在）⇒ 下方两道发布区门禁都
# 降级成 SKIP，「没检查」被当成了「没问题」。判据取父目录**名字**而不是
# 「../repos 是否存在」：后者会在恰好有个无关 repos 目录的机器上悄悄切换目标，
# 判据换了地方却不吭声，等于没有证据。
detect_repos_root() {
  local r="${PROJECTS_ROOT:-}"
  if [ -n "$r" ]; then printf '%s' "$r"; return 0; fi
  local parent="${ROOT%/*}"
  if [ "${parent##*/}" = "repos" ]; then printf '%s' "$parent"; return 0; fi
  if [ -d "$ROOT/repos" ]; then printf '%s' "$ROOT/repos"; return 0; fi
  if [ -d "$parent/repos" ]; then printf '%s' "$parent/repos"; return 0; fi
  return 0
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
  # $5=失败输出文件路径（可选；仅失败时传，供 tail 字段取末尾）
  # 恒定写 `skipped` 字段保持结构稳定：真跑 false / SKIP true。旧行无此字段 ⇒
  # 消费方按真跑兼容回放（gate_metrics.py / status_service / portal / mcp 同口径）。
  # SKIP 不计入 failed / escapeRate / lastOkAt，整批全 SKIP 也不得算全绿。
  local skipped="${4:-false}"
  local tail_src="${5:-}"
  mkdir -p "$(dirname "$GATE_RUNS")" 2>/dev/null || true
  rotate_if_large "$GATE_RUNS"
  # 标签里的反斜杠（Windows 解释器路径）会写成像 \P 这样的非法 JSON 转义，
  # 让整行解析失败、指标少算一条 —— 统一折成正斜杠再落盘。
  local label ts
  label="$(printf '%s' "$1" | tr '\\' '/')"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # 失败尾部（P1，2026-11-25）：只记 exit≠0 且给了输出文件的行。
  #
  # 为什么值得多这几个字节：gate-runs.jsonl 此前只有「哪条命令挂了 + 退出码」，
  # 失败长什么样完全丢失（stdout 只进了当次终端，CI 里更是只能看到通用 exit 1）。
  # 下游两件事都卡在这里：
  #   · 「失败归因」类断言无法写 —— 判据只能是 exit≠0，说不出是哪类错；
  #   · 任何失败分类器都没有特征来源（§229 的 TextCNN 语料只有标签+退出码，
  #     所以只能学到类别大小，val_acc 0.302 < 基线 0.317）。
  # 这一字段是那两件事的**唯一前置**，不加则训练/归因都免谈。
  #
  # 为什么交给 Python 而不是继续用 printf 拼：上面那条注释已经写明本仓吃过
  # 「反斜杠拼坏 JSON」的亏。tail 是从门禁真实输出里截的任意文本——含引号、
  # 反斜杠、制表符、CR、以及 Windows 路径，printf 无论如何拼都不安全。
  # 成本只在失败时付（成功路径仍走上面的 printf），一次 Python 启动可忽略。
  if [ -n "$tail_src" ] && [ -f "$tail_src" ] && [ "$2" != "0" ]; then
    LOG_LABEL="$label" LOG_TS="$ts" LOG_EXIT="$2" LOG_MS="$3" LOG_SKIP="$skipped" \
    LOG_TAIL_SRC="$tail_src" LOG_RUN_ID="$RUN_ID" LOG_COMMIT="$HEAD_SHA" \
    "$PY" - >> "$GATE_RUNS" 2>/dev/null <<'PYEOF' || true
import json, os, re, sys

# Windows 下 stdout 默认是 locale 编码（cp936）；tail 里一旦有该编码表外的字符
# （emoji、生僻字、被 errors='replace' 读进来的替换符），print 会抛 UnicodeEncodeError。
# 那个异常会被外层 except 吞掉 ⇒ 整条留痕静默丢失，而门禁判绿 —— 「记账失败」
# 被伪装成「没有失败」。统一钉成 utf-8 + replace。（与 run-python-sast.sh:281-285 同口径）
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 尾部窗口：行数与字符数双限。行数保证「看得到最后几步」，字符数防单行超长
# （例如整份 traceback 里夹了一行几万字符的 JSON）把 JSONL 撑爆。
TAIL_LINES = 40
TAIL_CHARS = 4000

# 门禁输出里可能带凭据（例如某道门禁回显被扫文件的内容、或命令行里带 token）。
# 只遮蔽高置信度形态，不做泛化脱敏 —— 过度遮蔽会把真正的失败特征一起抹掉，
# 那等于花了 IO 换一堆 *** 回来。
SENSITIVE = re.compile(
    r'(?i)(sk-[A-Za-z0-9]{16,}'
    r'|ghp_[A-Za-z0-9]{20,}'
    r'|gh[opsu]_[A-Za-z0-9]{20,}'
    r'|AKIA[0-9A-Z]{16}'
    r'|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
)

try:
    with open(os.environ['LOG_TAIL_SRC'], encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    tail = '\n'.join(lines[-TAIL_LINES:])
    if len(tail) > TAIL_CHARS:
        # 截尾不截头：失败原因通常在最后几行（traceback 的末段、断言位置）。
        tail = tail[-TAIL_CHARS:]
    tail = SENSITIVE.sub('***REDACTED***', tail)
    rec = {
        'ts': os.environ.get('LOG_TS', ''),
        'batch': os.environ.get('LOG_RUN_ID', ''),
        'commit': os.environ.get('LOG_COMMIT', 'unknown'),
        'label': os.environ.get('LOG_LABEL', ''),
        'exit': int(os.environ.get('LOG_EXIT', '1')),
        'ms': int(os.environ.get('LOG_MS', '0')),
        'skipped': os.environ.get('LOG_SKIP', 'false') == 'true',
        'tail': tail,
    }
    print(json.dumps(rec, ensure_ascii=False, separators=(',', ':')))
except Exception:
    # 留痕失败不改变门禁结论（本函数向来 `|| true`）：宁可少一条 tail，
    # 也不能因为「记账失败」把一次真实跑批的判定污染成 infra 红。
    pass
PYEOF
  else
    printf '{"ts":"%s","batch":"%s","commit":"%s","label":"%s","exit":%s,"ms":%s,"skipped":%s}\n' \
      "$ts" "$RUN_ID" "$HEAD_SHA" "$label" "$2" "$3" "$skipped" >> "$GATE_RUNS" 2>/dev/null || true
  fi
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
  # 第 5 参数把本次输出文件交给留痕：exit=0 时它不会被读（见 log_run 分支），
  # 失败时由它截出 tail。$out 在下面的 rm 之前仍存在，顺序不能调。
  log_run "$*" "$rc" "$(( $(now_ms) - t0 ))" false "$out"
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
  local repos_root
  repos_root="$(detect_repos_root)"
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
# 治理门禁的入口（2026-11-23 **已切换**）：
#   默认 —— repocheck 的门禁规则族（规则 31-50）：逐条以 `--root` + 退出码复跑
#           同一批 `gates/*.py`，判据仍是同一份文件，与 run.ts 结论逐条等价。
#   回退 —— `ALLIN_GATES_VIA_NPM=1` 时走 `npm run check:governance`（run.ts）。
#
# 为什么现在敢切（上一轮不敢）：当时顾虑「切换会丢掉 tier 选择与 --selfcheck-all」。
# 核对后确认这两条都不在切换点范围内 ——
#   · `--selfcheck-all` 是本脚本下面的**独立步骤**，根本不经过这里；
#   · `check:governance` 本身不带 `--tier`（即默认跑全部 20 道），rules_gate 同样跑
#     全部 20 道；`profileProbe` 的 `--no-profile` 也已按 registry.json 复现。
#     两侧 2026-11-23 实测均为 20/20 clean。
# 保留 npm 回退而不是直接删：单一入口的价值是「只有一个真相」，不是「只有一个实现」；
# 能随时对照的另一条路，正是判据没漂的证据。
#
# `--self` 不可省：repocheck 的默认项目发现只认一级子目录，monorepo 的仓根
# 从来不是「项目」，少了它门禁规则族对 allin 自己恒不生效。
# `--only-gates` 不可省：否则规则 22/23 的仓体卫生结论会混进同一个退出码，
# 让「门禁红」与「仓体脏」无法区分。
if [ "${ALLIN_GATES_VIA_NPM:-0}" = "1" ]; then
  echo "[gates-via-npm] 回退到 run.ts 跑 20 道治理门禁"
  run npm run check:governance
else
  run "$PY" -m allin_governance repocheck . --self --only-gates \
    --exclude tools,vendor,preset,packages,scripts,website,tests,facts,deploy,console,kernel,platform \
    --fail-on error
fi
# 门禁工具自身回归（selfcheck-all）：证明「每道门禁仍能检出问题」，堵住
# 「门禁被改坏却 CI 常绿」的盲区（S2 · 2026-11-08 审查闭环）。与 check:governance
# 同源调用链（run.ts --selfcheck-all），不引入新依赖、不触外部资源。
run npm run check:governance:selfcheck

# --- ⑩ 盲门元判据（编排层，**不占 g 编号**）------------------------------------
# 「跑了、绿了、什么都没量」在退出码上与「跑了、绿了、量了没问题」完全同形 ——
# 20 道门禁里没有任何一道能判它自己。本步逐道复跑 20 道门禁，把
# `scanned 0 + exit 0 + 无任何 SKIP 标记` 判红。
#
# 依据（已进 ADR 记账的两条外部证据 + 一个本仓正实例）：
#   · *A gate that only ever passes is no gate* —— 判据有三种静默失效：死门（从不
#     被调用）、环境坏门（跑了但错误被吞成 0）、**盲门**（跑完、退 0、什么都没量）。
#     前两种本仓已有对策（编排层接线 + g00 逐道 --selfcheck + selfcheck-all），
#     第三种此前完全无人判 —— 这一层补的就是它。
#   · *A check that cannot fail tells you nothing* —— 「没跑」与「没发现问题」必须
#     可区分（pytest 无用例收集退 5、Jest 默认无测试即失败，都是这个立场）。
#   · 正实例：上一轮 `repocheck --only-gates` 注册 0 条规则却退 0，还打印「82% 通过」。
#
# 关于「不可判定」：本步**不放行**。`undetermined` 是一等结论（ADR-0011 D3-H），
# 与 measured / blind 并列计数、单列打印，且一律不退 0。
#   历史：g15-docs-contract 曾不渲染 `scanned`，一度用 `--allow-undetermined` 过渡放行
#   （见下方「已兑现」那段）。放行开关已删 —— 让一道门禁长期以「不可判定」混在批里，
#   等于发永久免检证，而且它不会自己消失，因为没人被它挡过。
#
# 成本：本步会重新跑一遍 20 道门禁（本机约 2 分钟）。这是「不做盲门」的价格 ——
# 复用聚合退出码会让一道盲门被其余 19 道盖住，那正是要防的事。
#
# 踩坑教训：绝不能让「跳过」成为新的免检章。工具要求 scanned 0 且报绿时**必须**同时
# 有显式 SKIP 标记，并把 SKIP 理由原文打出来（今天 g06-numbering 就是这一档：
# 实测仓里 0 个 *.zh.md、0 个 vN.* 序号文件 ⇒ 它的 SKIP 为真；理由同屏，才可复核）。
#
# `--coverage-delta`（⑩b，2026-11-25 ADR-0011 验收现场补）：语料来自 `git ls-files`
# ⇒ **未入索引的新文件不在任何门禁的扫描面里**。现场实录：新建 ADR-0011 后跑 g19 得
# `scanned 88 / blocking 0`，看着是绿，但 scanned 与建文件之前一模一样 —— 那不是
# 「新文件没问题」，是「新文件没被看见」。故本步额外打两件事：
#   ① 未入索引的新文件逐条列出（硬信号：语料来源的事实，可证伪）；
#   ② 与上一个**不同提交**的留痕比 scanned：本区间新增了已跟踪文件而某道 scanned 不增
#      ⇒ 覆盖未跟进（软信号，只提示）。②只作提示是因为 scanned 不变也可能只是新文件
#      不在该道语境内，要变成硬判据得先在 registry 里声明每道门的扫描域。
# 结构根因更狠：govlib.Report.exit_code() **从不读 scanned**，g00 也不看它 ——
# 整条链上没有任何一处对「你读到了东西吗」有判据。
#
# g15 已于 2.4.0 补 scanned（实测 `scanned 141 file(s); blocking 0` → measured），本步为**严格模式**；
# 原 `TODO(2.4.0): g15 补 scanned 后删除 --allow-undetermined（见 ADR-0011 D3）` 已兑现。
#   前提：`.venv` 里要装到含该修复的版本。若装的是修复前的 2.3.1，g15 仍不印 scanned
#   ⇒ 本步会红，那是「修复未部署」而不是「第二道不可判定」—— 补装即可，别加回放行开关。
run "$PY" tools/gate/check_blind_gates.py --root "$ROOT" \
  --coverage-delta --record tools/gate/audit/blind-gates.jsonl

# --- ⑪ 两半自检的元判据（同上，编排层）---------------------------------------
# 每道门禁的 `--selfcheck` 报 `SELFCHECK {"caught":N,"clean":M,"misreports":K}`：
# caught 验「红得出来」，clean 验「静得下来」。只覆盖一半的自检是有偏的 ——
# 只验静无法证明会红（「不能失败的检查什么都没告诉你」），只验红无法证明不误报。
# govlib.SelfCheck.finish() 已把 caught==0 / clean==0 判红，但门禁可以绕过它手搓
# 这一行（g15 就是），所以这条判据不能只依赖 govlib 的行为，必须逐道核输出。
run "$PY" tools/gate/check_blind_gates.py --root "$ROOT" --two-halves

run "$PY" tools/gate/docs_index.py
# docs_index 自检（D1–D17 夹具）：此前只在手工跑（「写了不跑」），且 Windows 无符号链接
# 权限时干净夹具恒被 D6 误报 ⇒ 修为「探测权限后显式 SKIP」并接入跑批。
run "$PY" tools/gate/docs_index.py --selfcheck
# P0 遗留独立核验项（§六第二阶段收口，2026-11-11）：审计/报告类**结论型文档**的
# 证据锚点与结构自洽性（E1 锚点 / E2 章节 / E3 排序 / E4 无源 / E6 口径 / E7 疑点）。
# 此前只手工跑、从未接跑批 —— 与 #12 同源的「写了不跑 = 没有检查」缺口。两条同源：
#   ① CLI 面（agent / `allin docs audit-check` 驱动面）：证明命令真能跑、历史基线为 0；
#   ② 判据自面（--selfcheck，14 探针）：证明每条判据仍会红，护栏自身失效不被 CI 常绿掩盖。
run "$PY" allin_cli.py docs audit-check --quiet
run "$PY" tools/gate/audit_doc_check.py --selfcheck
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
# 月账一致性判据（2026-11-26 接入；registry 之外，登记于 tools/gate/README.md §12）。
# 为什么不是 g 编号：它判的是 `docs/事实源/机器/<机>/月账/` 这种**各机自持**的运行时
# 记录，不是「判仓库」的套件契约；而且其中 B 条要判**异机卷**的归属通道声明 ——
# 那与 g20「只判本机分区」的作用域收敛方式不同（B 判的是「这份卷说不说得清归属」，
# 读就能看出来，不需要替他机复测硬盘），混进 g 序列会把两种作用域口径搅在一起。
# 三条判据：A 节引用必须落在真实节上 / B 卷首必须声明归属通道且「代整理」要配对复核 /
# C 「未归属提交」的数字必须与 `git rev-list --count` 实测一致。
# 他机卷只报告不阻断（铁律 6），唯一例外是 B（归属不明是本判据的正当对象）。
# 同时跑 `--selfcheck`：三条负对照（造假节号 / 缺来源标注 / 未归属数字不符）
# 不红就等于没判；`--mutate a|b|c` 是变异验证，摘掉判红分支后自检**必须**变红。
run "$PY" tools/gate/check_machine_ledger.py --root "$ROOT"
run "$PY" tools/gate/check_machine_ledger.py --root "$ROOT" --selfcheck
# 机器归属 trailer 判据（2026-11-26 接入；registry 之外，登记于 tools/gate/README.md §12）。
# 为什么不是 g 编号：它判的不是"仓库长得合不合规"，而是一条**跨机的归属一致性**——
# 「改了谁的分区」与「声明自己是哪台机」必须一致（铁律 6：只有该机可改自己的分区）。
# 与 g20（本机自述一致性）的分工：g20 判"分区内容是不是本机该写的"，本条判
# "提交这一层有没有留下机器声明"；一个是文档面，一个是历史面，作用域不同。
#
# 三段语义（混在一起就会误导）：
#   · blocking —— 改了 `<STEM>` 分区却没声明 / 声明了别机（跨机越权）/ 声明了不存在的机名（拼错）；
#   · rewritten —— merge 与平台 squash：message 由 git 生成或被服务端重写，
#     **技术上无法带 trailer**，单列不判红（`--strict-rewritten` 可收紧）；
#   · out-of-window —— 早于生效日的提交，**不适用**（不是绿也不是红）。
#
# 生效范围：只判 `EFFECTIVE_FROM`（2026-12-01）之后的提交。历史 391 笔全无 trailer，
# 追溯等于让判据一落地就常红（D18/D19 同一先例：只判生效之后，不逼迫改写历史）。
# 窗口内零提交时打印显式 SKIP（scanned 0 + exit 0 而无 SKIP = 盲门，由 ⑩ 抓）；
# 另有过期守卫：cutoff 过 45 天仍零提交 ⇒ exit 2（配错或被整体绕过，不能长期静默）。
run "$PY" tools/gate/check_machine_trailer.py
# 判据自身回归：14 例负对照（含"拼错机名必须红""中文路径必须命中分区"
# "out-of-window 不得判绿判红"）+ 变异探针（摘掉判红逻辑后自检必须变红）。
# 门禁写了不跑 = 没有门禁（第六例）。
run "$PY" tools/gate/check_machine_trailer.py --selfcheck

# 冲突标记判据（2026-11-26 接入；registry 之外，登记于 tools/gate/README.md §12）。
# 事故来源：`docs/记录/交接/2026-11.md` 曾长期残留一行 `||||||| parent of fbb7940`，
# **所有门禁都没抓到** —— docs_index 判索引契约、relative_refs 判链接、g15 判节结构，
# 没有一道看"这一行是不是 git 留下的残骸"。冲突标记是最典型的"局部像正常文本"的损坏。
#
# 判据：`git ls-files` 的每个文本文件，行首出现 `<<<<<<<` / `|||||||` / `>>>>>>>`
# 即红（**不要求尾随空格**：被编辑器吞掉空格的残骸同样是没清干净）；`=======` 只在
# 同文件已命中前三者之一时才算 —— 单独判它会把 Markdown 的 setext 标题和分隔线全打成红。
# 代码块里的冲突标记同样判红：代码块里的 `<<<<<<<` 是损坏，不是示例。
run "$PY" tools/gate/check_conflict_markers.py
# 判据自身回归：6 例（含"无尾随空格也红""代码块内仍红""`=======` 单独不判"三条负对照）。
run "$PY" tools/gate/check_conflict_markers.py --selfcheck
# P0 S-4 门禁化回归（2026-11-11 P3 季度复跑补线）：MCP 自有工具面的路径穿越回归
# （docs.cite / repo.health 的 4 条越界载荷必须 isError + CWE-22）。此前 index.js
# --selftest 只能手工跑（"写了不跑 = 没有回归"），而它是 S-4 严重级唯一护栏 ——
# 季度复跑实测发现它从未进 run_all_gates.sh / CI，故接入主链。零三方依赖：node
# 内置模块 + 仓内 js，子进程走 pythonBin()（PATH 上 python/python3，CI 的
# setup-python 提供），与 agent 回归同组。selftest 仅写 tools/gate/audit/ 运行产物
# （已被 .gitignore 的 /tools/gate/audit/* 覆盖），不改 docs/、不污染工作树。
run node platform/apps/mcp/src/index.js --selftest
# --- 结构化事实源离线地基（2026-11-09，用户按「离线可用优先」拍板 O1=B / O2=A / O3=A）---
# 四条独立脚本，照 g21 模式接跑批；g00–g20 的 **20 道聚合口径不变**，
# 且全部零第三方依赖、零服务依赖 —— 拔网 + 停三栈 + 删派生库时仍须全绿（离线北极星）。
# ① g22：结构化真身过 JSON Schema（纯文本，facts/facts.json ⇄ facts/facts.schema.json）
run "$PY" -m allin_governance._facts.cli validate
# ② g23：doc_refs 引用完整性 + 生成区 marker 漂移 + generated=true 引用完备性。
#    真身反转（P0-A 派生索引投影）已收口 ⇒ 生成物在场即**全量阻断**（marker 漂移 + 缺对应生成物），
#    缺席时显式 SKIPPED 并计数（离线北极星允许派生物缺失，render 后即被即时阻断），不冒充通过。
run "$PY" tools/gate/facts_parity.py
# ③ g24：文档内相对路径。棘轮基线 tools/gate/baseline/relative-refs.txt 挂存量 10 条，
#    只阻断**新增**断链；docs/记录/ 历史卷按只增不改永久豁免（SPEC-005 §3.12）。
run "$PY" tools/gate/relative_refs_gate.py --json
# ④ 离线北极星端到端验收：无派生库时 get/asof 回落纯 JSON、判据可离线自检、派生层可重建。
run "$PY" -m allin_governance._facts.cli offline-check
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
# 机器事实单源化（§214）：facts/machine/<机>.json 是 B' 真相，facts.json 机器段是派生。
# 判据 = 两边聚合一致；手改 facts.json 的机器段或漏跑聚合都会红。
run "$PY" -m allin_governance._facts.build_machine_index --check
# 文档/配置归属侦察（§212–214）：机器特化内容不该躺在公共层（全仓扫描，豁免清单见脚本）。
run "$PY" tools/machine_content_audit.py
# 生成器自身视角的同步自检（belt-and-suspenders，A 期 Phase 1/2/3）：
# g26 已对 ports / projects / ports_mirror / tiering / tools / licenses 做意图态对账；下列是**生成器**维度的同一类漂移判定，
# 二者各自独立，任一被改坏都跑得出红（门禁写了不跑 = 没有门禁）。
# 覆盖：Phase 1 的 projects 索引投影（145 项 ⇄ registry）、Phase 2 的 ports 索引投影 + 镜像（⇄ docs/事实源/ports.yaml）、
#      Phase 3 的 tiering/tools/licenses 索引投影（⇄ docs/事实源/*.yaml）。
# 均无 yaml 时退化为 SKIP（与 g26 的 ports 判据一致，SKIP ≠ pass）。
run "$PY" -m allin_governance._facts.build_projects --check
run "$PY" -m allin_governance._facts.build_ports --check
run "$PY" -m allin_governance._facts.build_tiering --check
run "$PY" -m allin_governance._facts.build_tools --check
run "$PY" -m allin_governance._facts.build_licenses --check
# ⑦ g27（2026-11-10 深度审计 M-10 / P2 #20）：运行时超时单一事实源。
#    docs/事实源/runtime_defaults.json 是唯一权威；在场损坏→exit 1、缺席→exit 3，
#    均不判绿（对齐 g26 的 P1 #7 口径）。独立脚本落 tools/gate/（非 governance/gates/，
#    g00-meta 沙箱只含 governance/、够不到 docs/事实源）。--selftest 含坏 JSON / 缺席 /
#    缺 unit / 值 0 / bool 值 / 非法 key 等 15 探针，--check 核 17 处迁移值不变 + 调用落地。
run "$PY" tools/gate/runtime_defaults_check.py --selftest
run "$PY" tools/gate/runtime_defaults_check.py --check
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
run "$PY" -m allin_governance repocheck . --profile monorepo --exclude tools,vendor,preset,packages,scripts,website,tests,facts,deploy --fail-on error
# packages/ 与 website/ 都是 monorepo 的中间目录（与 tools/ 同类），故本行一并排除；
# packages/ 内部的单个包按「子件」口径单独体检（下方一行）；website/ 则另起 CI job
# 跑 `npm run smoke`（本地 19/19 全绿），其健康度不靠 repocheck 兜底。
# 2026-11-25 公共核提仓：packages/allin-governance 源码已迁至独立仓
# （D:/projects/repos/allin-governance）。本仓只留旧路径指针 README，不是可体检项目，
# 该段移除；公共核自身由包仓 CI 负责。

# --- 2026-11-01 补齐三项此前未接进自动化的辅助门禁 ---
# 起因：README §本仓自检口径承诺 A/B/C 三条，脚本却只跑了 A) 与 C)，
# B) 自 2026-10-30 起一直红着没人发现。**门禁写了不跑 = 没有门禁**，故一并补入。
# ① README §本仓自检口径 B)：A) 已把 tools/ 排除，故 tools/ 的子件在这里单独体检。
run "$PY" -m allin_governance repocheck tools/ --profile component --exclude gate --fail-on error
# ② .ps1 编码：PowerShell 5.1 对无 UTF-8 BOM 的脚本按 ANSI 解码，
#    中文变乱码并报一堆假语法错误（本机边界里那条"一边绿一边红"的编码指纹）。
run "$PY" tools/gate/check_ps1_bom.py
# ③ 仓库卫生 H1-H8：扫发布区全部仓的 git 跟踪面（136 仓）。
#    基线棘轮**只单向收紧**：已评估的存量记在 tools/gate/audit/hygiene_baseline.csv，
#    明细台账见同目录 hygiene_debt_2026-11-01.json —— 刷新基线不等于债务消失，台账才是待办清单。
#    发布区缺席时由 _run_repo_hygiene 降级为 skip（见其注释），避免把整批门禁拖红。
_run_repo_hygiene
# ③-b 发布区治理门禁（2026-11-21）：repocheck 的 30 条规则覆盖被管仓，
#     与本仓 20 道门禁互补 —— 此前门禁只审 allin 自身（138 个被管仓零覆盖）。
#     待裁决项记在 tools/gate/audit/publish_area_exemptions.csv，不冒充通过：
#     汇总里单列 pending，全哥在场可用 --strict-pending 逐项裁决。
#     发布区缺席时同样降级为 skip（与 _run_repo_hygiene 同款）。
_run_publish_area_gate() {
  local repos_root
  repos_root="$(detect_repos_root)"
  if [ -z "$repos_root" ] || [ ! -d "$repos_root" ]; then
    echo "==> $PY tools/publish_area_gate.py (no-publish-area)"
    note_skip "publish_area_gate:skip(no-publish-area)" \
      "未检测到发布区（无同级 repos/ 且未设 \$PROJECTS_ROOT）：无被管仓可检"
    return 0
  fi
  local has_repo=0
  for d in "$repos_root"/*/; do
    [ -d "${d}.git" ] && { has_repo=1; break; }
  done
  if [ "$has_repo" -eq 0 ]; then
    echo "==> $PY tools/publish_area_gate.py (empty-publish-area)"
    note_skip "publish_area_gate:skip(empty-publish-area)" \
      "发布区下没有 git 仓：无被管仓可检"
    return 0
  fi
  run "$PY" tools/publish_area_gate.py --repos-root "$repos_root"
}
_run_publish_area_gate
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
    # P0-10/11（2026-11-10）：此 not_applicable 项**不等同于「北极星已验证通过」**——
    # 北极星由 gates.yml 的独立 e2e step（先 npm ci 装依赖再 npm run smoke:e2e）真实验证，
    # 本批内只是「没有可跑对象」。汇总行应把它单列、且 CI 下打 ::warning::，防止误读为全绿。
    echo "==> npm run smoke:e2e"
    note_skip "smoke:e2e:skip(missing-node-deps)" \
      "北极星三面冒烟：platform/website 依赖未装，本批内无可跑对象（非冒烟不合格）；CI 另有独立 e2e step（npm ci 装依赖后实跑）验证，本项记为环境不适用而非已通过"
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
# ⑥ P1（2026-11-10 深度审计 H-2 / H-4）：CLI 与服务层退出码、治理门禁严格模式
#    SKIP 的两组回归。此前 tests/test_allin_cli.py 的 42 个用例从未进跑批，
#    正是「测试写了不跑 = 没有测试」的同一类缺口，一并接入。
run "$PY" -m pytest tests/test_allin_cli.py tests/test_gate_strict_skip.py tests/test_auto_flow.py -q
# ⑥ P2（2026-11-10 深度审计）：本轮新增回归，同样按「写了不跑 = 没有测试」接入。
#   分三组：安全可靠性（#13-16/22）、跨模块性能与收敛（#17-19）、纯函数单测（#21）+
#   vendored 归档边界（M-2）+ 超时单一事实源（#20）。facts 相关用例全部子进程隔离，
#   不占 sys.modules["cli"]（否则会静默劫持 governance 的裸名 import cli）。
run "$PY" -m pytest tests/test_p2_sec_remediation.py tests/test_p2_convergence.py -q
run "$PY" -m pytest tests/test_vendor_cordis_archive_boundary.py tests/test_runtime_defaults.py -q
run "$PY" -m pytest tests/test_docs_contract_pure.py tests/test_repo_hygiene_pure.py tests/test_facts_cli_pure.py tests/test_gitee_release_pure.py -q
# ⑥ P3（2026-11-10 深度审计 #25/#26）：sha256 摘要单一实现（三族分治、摘要值逐字节不变）、
#    read_text 单一实现、裸 open() 改 with、CRED_PATTERNS 命名常量反查、registry 五处分义。
#   sha256util 自检单独接一条（含坏值/归一/位宽 9 探针），pytest 覆盖形态断言与逐字节一致。
run "$PY" tools/sha256util.py
run "$PY" -m pytest tests/test_p3_pure.py -q
# ⑦ 仓根 README「可机检事实」护栏（2026-11-04 工程审查 Docu Top3-2 落地）：
#    README 引用的仓内路径存在性 + allin-governance 版本与 pyproject 对账 ——
#    README 不在 docs_index 判据内，本门禁是其唯一机检护栏（曾实测四处漂移静默存活）。
run "$PY" tools/gate/check_readme_refs.py
#    P1 #10（2026-11-10 深度审计 H-5）：R2 判定面扩到 25 份现行声明文档并改
#    「集合相等」口径后，把自检也接进跑批 —— 注入旧版本号探针必须判红、恢复后判绿，
#    否则「护栏自身失效」和旧口径漂移一样静默。
run "$PY" tools/gate/check_readme_refs.py --selfcheck
# ⑧ 架构资产对账（2026-11-04 体检落地，ADR-0009）：architecture/ 的 SVG 与 adr/ 在
#    文档契约判据之外，本门禁把「SVG 数字 / adr 索引 / website 端口登记 / 包版本」七项声明
#    对账成退出码 —— 体检实测 5 处漂移（ADR 索引缺 0006–0008、图内三处数字落后两代）
#    曾静默存活近月，此后同类漂移跑批即红。2026-11-10 深度审计 H-5 补第七项：
#    SVG 里的 allin-governance 版本声明必须与 pyproject.toml 相等。
run "$PY" tools/gate/check_arch_assets.py
# ⑧b Tag 纪律（2026-11-24 全检残留项收口）：命名 / annotated / 版本对账 / 指向已推送主线。
#    这条纪律此前只写在四份文档里（SPEC-004 铁律 70、SPEC-102、SPEC-103、指南 §3.2），
#    没有任何一条能被机器判 —— 打错名字、轻量 tag 冒充发布、tag 指向没推的本地提交、
#    tag 版本与 pyproject 对不上，四类都静默通过。
#    默认跑离线判据（不需要网络，任何机器都能跑）；`ALLIN_TAGS_REMOTE=1` 追加
#    `git ls-remote` 比对（检测「本地有远端无」与「已被移动」，CI 里用这个）。
#    注意：这里**不用 note_skip** —— 远程比对是可选加强，不是环境性缺失；
#    记成 SKIP 会把每次本地跑批的 status 从 clean 降成 incomplete。
if [ "${ALLIN_TAGS_REMOTE:-0}" = "1" ]; then
  run "$PY" tools/gate/check_tags.py --remote
else
  run "$PY" tools/gate/check_tags.py
  echo "    [note] tag-check 走离线判据；远端不可变性比对请用 ALLIN_TAGS_REMOTE=1"
fi
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

# --- ⑤ 硬编码死根门禁（孤儿门禁接入跑批，P0-15 · 2026-11-10）---
# scan_hardcoded.ps1 此前只被文档提及、未接任何自动化（连 pre-commit 都仅是注释里提到），
# 属「门禁写了不跑 = 没有门禁」。它查「代码里指向盘上已失效根目录的绝对路径」，
# 按基线棘轮只拦**新增**死路径，与 g01（存在性无关机器绑定）互补。
# 基线由脚本默认值**单一真相源**给出（受跟踪的 governance/baseline/，与 g01 同款）：
# 手动跑 / 跑批 / CI 读同一份，换机不丢基线。Windows（pwsh / powershell）真跑，
# 其余平台缺解释器记 not_applicable（≠ 通过）。
if command -v pwsh >/dev/null 2>&1; then
  run pwsh -NoProfile -ExecutionPolicy Bypass -File tools/gate/scan_hardcoded.ps1 -Quiet
elif command -v powershell.exe >/dev/null 2>&1; then
  run powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gate/scan_hardcoded.ps1 -Quiet
else
  note_skip "scan_hardcoded:skip(no-powershell)" \
    "当前平台无 PowerShell，无法跑硬编码死根门禁（此前仅文档提及、未接自动化；Windows 专属）"
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
  # P0-10/11（2026-11-10）：not_applicable 不等于「已验证通过」，避免 status=clean
  # 被误读为全绿。在 CI 下打 ::warning:: 让 PR 检查显式看到「还有 N 项环境未检」。
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '::warning::门禁批含 %s 项环境不适用（not_applicable，非已验证通过）：%s\n' \
      "${NA_N}" "$(gh_escape "$(printf '%s; ' "${not_applicable[@]}")")"
  fi
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
