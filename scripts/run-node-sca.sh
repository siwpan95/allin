#!/usr/bin/env bash
# allin Node 侧 SCA（供应链依赖漏洞扫描）—— GitHub / Gitee 两侧共用的唯一实跑入口。
#
# 为什么单独一个脚本，不与 run-python-sast.sh 合并：
#   Python SAST/SCA 走 bandit + pip-audit（Python 工具链、读 requirements 文本）；
#   Node SCA 走 npm audit（npm 工具链、读两棵 lock 树的实际解析结果）。
#   两者工具链、扫描对象、失败模式都不同 —— 塞进一个脚本会让「哪一半坏了」
#   在退出码上不可分辨。故并列两个共用脚本，各自由双侧 CI 的对应 job/step 调用。
#
# 退出码契约（fail-closed）：
#   0 = 本轮实跑完成（含发现；shadow mode 下发现不阻断）
#       **也包含「端点不可达」**：那是本轮的**结论缺失**，不是「有漏洞」也不是
#       「没漏洞」，必须在 stdout 与 JSONL 里显式标 caveat，但不据此判 CI 红
#       （理由见下）。
#   3 = 基础设施失败：npm 不可用 / 报告缺失或损坏或字段不合契约 /
#       JSONL 写不进。绝不使用 `|| true` / `|| echo skip`。
#
# 为什么「发现不阻断」（shadow mode）：
#   与 run-python-sast.sh 同源，尊重仓内既定决策
#   （docs/记录/审计/allin增强方案调研_2026-10-28.md:48/98、
#     docs/记录/审计/组合做大做强战略研究_2026-10-31.md:204：
#     「不 day-1 block SAST」「不全设 blocking（新门禁先 shadow mode）」）。
#   存量依赖告警未建立基线前直接阻断，等于把历史债一次性砸给当前这次改动。
#
# 为什么「端点不可达」不阻断（刻意的口径选择，不是漏做）：
#   npm audit 需要访问 registry 的 audit 端点。远端整改报告（T12–T15）实测
#   境内端点 registry.npmjs.org/.../audits/quick 两次重试不可达；Gitee 境内
#   runner 的可达性同样未经验证。若把它当「失败」判红，Gitee 流水线会因**网络
#   环境**长期红 —— 那是把环境问题伪装成代码问题，最终结果是没人再看这条门禁。
#   故：端点不可达 ⇒ 如实记为 caveat（stdout 打 `NODE_SCA_CAVEAT`、JSONL 记
#   status=unreachable），**绝不写成 0 漏洞**。
#   与之对照：run-python-sast.sh 对 pip-audit 是 fail-closed（不可达即 exit 3），
#   因为 Python 侧端点在本机实测可达，不可达就说明环境真出问题了。
#   一句话：能验证可达的一侧 fail-closed，未验证可达的一侧如实记 caveat。
#
# 用法（CI 与本地同口径）：
#   bash scripts/run-node-sca.sh --selfcheck   # 不联网，注入假报告验退出码语义
#   bash scripts/run-node-sca.sh               # 真跑两棵 lock 树的 npm audit
#
# 与 .github/workflows/gates.yml 的 node-sca job / .workflow/pipeline.yml 的
# node_sca step 调同一个脚本，两侧不允许漂移。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo "ENV ERROR: 无法进入仓根 $ROOT" >&2; exit 3; }

AUDIT_DIR="$ROOT/tools/gate/audit"       # 已被 .gitignore 的 /tools/gate/audit/* 覆盖
JSONL_NAME="node-sca-runs.jsonl"
# 两棵 lock 树：与远端原内联步骤同口径（platform / website）。
TREES=("platform" "website")

posix_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf '%s' "$1"; fi
}

# ---------------------------------------------------------------------------
# 解析一份 npm audit --json 报告并判定。
#   $1 报告路径  $2 npm 退出码  $3 树名
# 输出：`STATUS=<ok|findings|unreachable|badrc>` 一行到 stdout（供调用方聚合）
# 返回：0=ok/findings/unreachable（都不阻断）/ 3=报告损坏或契约不符
# ---------------------------------------------------------------------------
parse_tree() {
  NODE_SCA_REPORT="$1" NODE_SCA_RC="$2" NODE_SCA_TREE="$3" "$PY" - <<'PYEOF'
import json, os, sys

report = os.environ['NODE_SCA_REPORT']
rc = int(os.environ['NODE_SCA_RC'])
tree = os.environ['NODE_SCA_TREE']

if not os.path.isfile(report):
    print('NODE_SCA_INFRA_ERROR tree=%s: report file missing: %s' % (tree, report), file=sys.stderr)
    sys.exit(3)
try:
    with open(report, encoding='utf-8') as f:
        data = json.load(f)
except (OSError, ValueError) as e:
    print('NODE_SCA_INFRA_ERROR tree=%s: report JSON unparsable: %s' % (tree, e), file=sys.stderr)
    sys.exit(3)

# npm audit 在网络不可达时会吐出 {"error": {...}} 而不是常规报告 —— 这是
# 「本轮没有结论」，必须与「报告损坏」区分开（前者不阻断，后者 exit 3）。
if isinstance(data, dict) and 'error' in data and 'vulnerabilities' not in data:
    err = data.get('error')
    code = ''
    if isinstance(err, dict):
        code = str(err.get('code') or err.get('summary') or err.get('detail') or '')
    else:
        code = str(err)
    print('NODE_SCA_CAVEAT tree=%s: audit 端点不可达，本轮未取得 SCA 结论 (code=%s, npm rc=%d)'
          % (tree, code[:80], rc))
    print('STATUS=unreachable')
    sys.exit(0)

if not isinstance(data, dict) or 'vulnerabilities' not in data:
    print('NODE_SCA_INFRA_ERROR tree=%s: report missing field vulnerabilities' % tree, file=sys.stderr)
    sys.exit(3)
if not isinstance(data['vulnerabilities'], dict):
    print('NODE_SCA_INFRA_ERROR tree=%s: vulnerabilities is not an object' % tree, file=sys.stderr)
    sys.exit(3)

vulns = data['vulnerabilities']
# metadata.vulnerabilities 是各严重度的计数（npm audit v2 契约）。
meta = data.get('metadata')
counts = meta.get('vulnerabilities') if isinstance(meta, dict) else None
if not isinstance(counts, dict):
    print('NODE_SCA_INFRA_ERROR tree=%s: metadata.vulnerabilities missing' % tree, file=sys.stderr)
    sys.exit(3)

sev_order = ['critical', 'high', 'moderate', 'low', 'info']
total = sum(int(counts.get(k, 0) or 0) for k in sev_order)
print('NODE_SCA_TREE tree=%s total=%d critical=%s high=%s moderate=%s low=%s'
      % (tree, total, counts.get('critical', 0), counts.get('high', 0),
         counts.get('moderate', 0), counts.get('low', 0)))
# 逐条摘要（只列有漏洞的包，避免刷屏）
for name in sorted(vulns):
    v = vulns[name]
    if not isinstance(v, dict):
        continue
    sev = str(v.get('severity', '?'))
    if sev in ('critical', 'high', 'moderate', 'low', 'info'):
        print('  NODE_SCA %s %s@%s severity=%s range=%s fixAvailable=%s'
              % (tree, name, v.get('range', '?'), sev,
                 v.get('range', '?'), v.get('fixAvailable', '?')))
# npm audit 的退出码：0=无漏洞，1=有漏洞（--audit-level 命中），其它=工具错。
if rc not in (0, 1):
    print('NODE_SCA_INFRA_ERROR tree=%s: npm audit exit code abnormal: %d' % (tree, rc), file=sys.stderr)
    sys.exit(3)
print('STATUS=%s' % ('findings' if total > 0 else 'ok'))
sys.exit(0)
PYEOF
}

# ---------------------------------------------------------------------------
# 汇总：把多棵树的结论写 JSONL 并打印总结，判最终退出码。
#   $1 ok 数  $2 findings 数  $3 unreachable 数  $4 总树数  $5.. 逐树 (tree:status:total)
# ---------------------------------------------------------------------------
finish() {
  local ok_n="$1" find_n="$2" unreach_n="$3" total_n="$4"; shift 4
  local ts period commit
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  period="$(date -u +%Y-%m)"
  commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

  local status
  if [ "$unreach_n" -gt 0 ] && [ "$ok_n" -eq 0 ] && [ "$find_n" -eq 0 ]; then
    status="unreachable"
  elif [ "$unreach_n" -gt 0 ]; then
    status="partial"          # 一部分树有结论、一部分不可达 —— 不能声称全量结论
  elif [ "$find_n" -gt 0 ]; then
    status="findings"
  else
    status="ok"
  fi

  echo
  echo "NODE_SCA_SUMMARY status=$status ok=$ok_n findings=$find_n unreachable=$unreach_n trees=$total_n (shadow mode: findings do NOT block)"
  if [ "$unreach_n" -gt 0 ]; then
    echo "NODE_SCA_CAVEAT 有 $unreach_n 棵树因端点不可达未取得结论 —— 本轮**不能**声称「无漏洞」，只能声称「未取得结论」。"
  fi

  # JSONL 留痕（5MB 轮转沿用 gate-runs.jsonl 口径）
  mkdir -p "$AUDIT_DIR" 2>/dev/null || { echo "ENV ERROR: 无法创建 $AUDIT_DIR" >&2; return 3; }
  local path="$AUDIT_DIR/$JSONL_NAME"
  if [ -f "$path" ] && [ "$(wc -c < "$path" 2>/dev/null || echo 0)" -gt $((5 * 1024 * 1024)) ]; then
    mv -f "$path" "$path.1"
  fi
  local detail
  detail="$(printf '%s,' "$@" | sed 's/,$//')"
  printf '{"ts":"%s","period":"%s","commit":"%s","status":"%s","ok":%s,"findings":%s,"unreachable":%s,"trees":%s,"detail":[%s]}\n' \
    "$ts" "$period" "$commit" "$status" "$ok_n" "$find_n" "$unreach_n" "$total_n" \
    "$(printf '%s' "$detail" | sed 's/\([^,]*\)/"\1"/g')" >> "$path" 2>/dev/null || {
      echo "NODE_SCA_INFRA_ERROR 写 JSONL 失败：$path" >&2; return 3; }

  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '::warning::NODE_SCA status=%s ok=%s findings=%s unreachable=%s（shadow：不阻断；unreachable 不代表无漏洞）\n' \
      "$status" "$ok_n" "$find_n" "$unreach_n"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# --selfcheck：不联网 / 不跑真扫描，注入假报告验退出码语义。自身可证伪。
# ---------------------------------------------------------------------------
selftest() {
  local t dir fail_n=0
  t="$(posix_path "$(mktemp -d "${TMPDIR:-/tmp}/allin-nodesca-selftest-XXXXXX")")" || return 3
  trap 'rm -rf "${SELFTEST_TMP:-}"' EXIT
  SELFTEST_TMP="$t"
  dir="$t/audit"; mkdir -p "$dir" || return 3
  export AUDIT_DIR="$dir"

  echo "run-node-sca --selfcheck：注入假报告，逐分支验证退出码语义"
  echo "（不联网 / 不跑真扫描；共用实跑的 parse_tree 解析代码）"
  echo

  # ① 无漏洞报告 ⇒ ok / 0
  cat > "$t/ok.json" <<'JSON'
{"auditReportVersion":2,"vulnerabilities":{},"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}}}
JSON
  r=0; out="$(parse_tree "$t/ok.json" 0 platform 2>"$t/e1")" || r=$?
  check "① 无漏洞报告 ⇒ exit 0" 0 "$r"
  printf '%s' "$out" | grep -q 'STATUS=ok' || { echo "  [FAIL] ① 未输出 STATUS=ok"; fail_n=$((fail_n+1)); }

  # ② 有高危漏洞报告（npm rc=1）⇒ findings / 0（shadow 不阻断）
  cat > "$t/find.json" <<'JSON'
{"auditReportVersion":2,"vulnerabilities":{"lodash":{"name":"lodash","severity":"high","range":"<4.17.21","fixAvailable":true}},"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":1,"critical":0,"total":1}}}
JSON
  r=0; out="$(parse_tree "$t/find.json" 1 website 2>"$t/e2")" || r=$?
  check "② 有 high 漏洞 ⇒ exit 0（shadow）" 0 "$r"
  printf '%s' "$out" | grep -q 'STATUS=findings' || { echo "  [FAIL] ② 未输出 STATUS=findings"; fail_n=$((fail_n+1)); }
  printf '%s' "$out" | grep -q 'severity=high' || { echo "  [FAIL] ② 未列出 high 条目"; fail_n=$((fail_n+1)); }

  # ③ 端点不可达（error 字段）⇒ unreachable / 0（caveat，不假称 0 漏洞）
  cat > "$t/unreach.json" <<'JSON'
{"error":{"code":"ENOTFOUND","summary":"request to https://registry.npmjs.org/-/npm/v1/security/audits/quick failed","detail":"getaddrinfo ENOTFOUND registry.npmjs.org"}}
JSON
  r=0; out="$(parse_tree "$t/unreach.json" 1 platform 2>"$t/e3")" || r=$?
  check "③ 端点不可达 ⇒ exit 0（记 caveat）" 0 "$r"
  printf '%s' "$out" | grep -q 'STATUS=unreachable' || { echo "  [FAIL] ③ 未输出 STATUS=unreachable"; fail_n=$((fail_n+1)); }
  printf '%s' "$out" | grep -q 'NODE_SCA_CAVEAT' || { echo "  [FAIL] ③ 未打 caveat 标记（会被误读成无漏洞）"; fail_n=$((fail_n+1)); }

  # ④ 报告损坏 / 缺字段 / 工具码异常 ⇒ 3
  printf 'not json at all {{' > "$t/bad.json"
  r=0; parse_tree "$t/bad.json" 0 platform >/dev/null 2>"$t/e4" || r=$?
  check "④ 报告 JSON 语法坏 ⇒ exit 3" 3 "$r"
  r=0; parse_tree "$t/nope.json" 0 platform >/dev/null 2>"$t/e5" || r=$?
  check "④ 报告不存在 ⇒ exit 3" 3 "$r"
  cat > "$t/nofield.json" <<'JSON'
{"auditReportVersion":2,"metadata":{"vulnerabilities":{"total":0}}}
JSON
  r=0; parse_tree "$t/nofield.json" 0 platform >/dev/null 2>"$t/e6" || r=$?
  check "④ 缺 vulnerabilities 字段 ⇒ exit 3" 3 "$r"
  cat > "$t/nometa.json" <<'JSON'
{"auditReportVersion":2,"vulnerabilities":{}}
JSON
  r=0; parse_tree "$t/nometa.json" 0 platform >/dev/null 2>"$t/e7" || r=$?
  check "④ 缺 metadata.vulnerabilities ⇒ exit 3" 3 "$r"
  r=0; parse_tree "$t/ok.json" 2 platform >/dev/null 2>"$t/e8" || r=$?
  check "④ npm 退出码异常(rc=2) ⇒ exit 3" 3 "$r"

  # ⑤ finish() 的 caveat 口径：全不可达时必须落到 status=unreachable 且不退出非 0
  r=0; finish 0 0 2 2 "platform:unreachable:0" "website:unreachable:0" >"$t/f1" 2>&1 || r=$?
  check "⑤ 全树不可达 ⇒ exit 0 且 status=unreachable" 0 "$r"
  grep -q 'status=unreachable' "$t/f1" || { echo "  [FAIL] ⑤ status 不是 unreachable"; fail_n=$((fail_n+1)); }
  grep -q '不能\*\*声称「无漏洞」' "$t/f1" || { echo "  [FAIL] ⑤ 未声明「不能声称无漏洞」"; fail_n=$((fail_n+1)); }

  echo
  if [ "$fail_n" -eq 0 ]; then
    echo "run-node-sca --selfcheck: 全部通过（4 类分支 + caveat 口径断言）"
  else
    echo "run-node-sca --selfcheck: $fail_n 项失败" >&2
  fi
  return "$fail_n"
}

check() {
  if [ "$2" = "$3" ]; then
    printf '  [PASS] %-42s 期望=%s 实得=%s\n' "$1" "$2" "$3"
  else
    printf '  [FAIL] %-42s 期望=%s 实得=%s\n' "$1" "$2" "$3"
    fail_n=$((fail_n + 1))
  fi
}

PY="${ALLIN_PYTHON:-python3}"

if [ "${1:-}" = "--selfcheck" ]; then
  selftest
  exit $?
fi

# ---------------------------------------------------------------------------
# 实跑
# ---------------------------------------------------------------------------
if ! command -v npm >/dev/null 2>&1; then
  echo "ENV ERROR: 找不到 npm —— Node SCA 跑不了（需要 Node.js >= 22）" >&2
  exit 3
fi
if ! "$PY" -c 'import sys; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
  echo "ENV ERROR: 解释器不可用或低于 3.9：$PY（用 ALLIN_PYTHON 指定）" >&2
  exit 3
fi

mkdir -p "$AUDIT_DIR" || { echo "ENV ERROR: 无法创建 $AUDIT_DIR" >&2; exit 3; }
TMP="$(posix_path "$(mktemp -d "${TMPDIR:-/tmp}/allin-nodesca-XXXXXX")")" || {
  echo "ENV ERROR: 无法创建临时目录" >&2; exit 3; }
trap 'rm -rf "${TMP:-}"' EXIT

ok_n=0; find_n=0; unreach_n=0; total_n=0
detail=()
for tree in "${TREES[@]}"; do
  if [ ! -d "$tree" ]; then
    echo "ENV ERROR: 目录不存在：$tree" >&2
    exit 3
  fi
  total_n=$((total_n + 1))
  report="$TMP/$tree-audit.json"
  log="$TMP/$tree-audit.log"
  echo "==> npm audit --prefix $tree --audit-level=high --json"
  rc=0
  npm audit --prefix "$tree" --audit-level=high --json > "$report" 2> "$log" || rc=$?
  tail -n 6 "$log" || true
  echo "    npm exit=$rc"

  out=""
  perr=0
  out="$(parse_tree "$report" "$rc" "$tree" 2>&1)" || perr=$?
  if [ "$perr" -eq 3 ]; then
    echo "$out" >&2
    echo "ENV ERROR: $tree 的 npm audit 报告不可用（基础设施失败，不当作 0 漏洞）" >&2
    exit 3
  fi
  echo "$out"

  st="$(printf '%s' "$out" | sed -n 's/^STATUS=//p' | tail -n 1)"
  tot="$(printf '%s' "$out" | sed -n 's/^NODE_SCA_TREE tree=[^ ]* total=\([0-9]*\).*/\1/p' | tail -n 1)"
  case "$st" in
    ok)          ok_n=$((ok_n + 1)) ;;
    findings)    find_n=$((find_n + 1)) ;;
    unreachable) unreach_n=$((unreach_n + 1)) ;;
    *)
      echo "ENV ERROR: $tree 的解析结果无法判定（STATUS='$st'）" >&2
      exit 3
      ;;
  esac
  detail+=("$tree:$st:${tot:-0}")
done

rc=0
finish "$ok_n" "$find_n" "$unreach_n" "$total_n" "${detail[@]}" || rc=$?
exit "$rc"
