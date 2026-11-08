#!/usr/bin/env bash
# allin Python SAST / 依赖审计 —— GitHub / Gitee 两侧共用的唯一实跑入口。
#
# 背景（S7 的机制性根因）：tools/repocheck/rules_ci.py 规则 28 只检查 SAST
# **配置存在**（_SAST_FILES / codeql-action / pre-commit 钩子里的 semgrep|bandit|...）。
# 仓内 tools/repocheck/.pre-commit-config.yaml 已有 bandit 钩子、根
# .pre-commit-config.yaml 已有 gitleaks ⇒ 规则 28 恒 ok，与「有没有真跑、结果
# 有没有人读」完全无关。本脚本不碰规则 28（不改判据、不扩大范围），只把
# 「真跑 + 结果可消费」这一层补上。
#
# 退出码契约（fail-closed）：
#   0 = 本次实跑完成（含发现；shadow mode 下发现不阻断）
#   3 = 基础设施失败：解释器不可用 / 安装失败 / import bandit 或 pip-audit 不可用 /
#       空扫描面 / 报告缺失或损坏或字段不合契约 / 工具退出码异常 / JSONL 写不进。
#   绝不使用 `|| true` / `|| echo skip` —— 没跑成必须响，不能假装跑过。
#
# 为什么「发现不阻断、而基础设施失败一律阻断」：
#   docs/记录/审计/allin增强方案调研_2026-10-28.md:48/98 与
#   docs/记录/审计/组合做大做强战略研究_2026-10-31.md:204 明确记录过决策：
#     「不 day-1 block SAST」「不全设 blocking（新门禁先 shadow mode）」
#     「不再新增门禁，除非它拦下的是一类已发生过的真事故」。
#   本脚本**尊重**这条决策，不悄悄翻转：bandit 的 medium+ 发现、pip-audit 的
#   漏洞都只做记录（stdout 摘要 + GitHub ::warning:: annotation + JSONL），
#   不把 CI 变红 —— 存量告警未建立基线前，阻断等于把全仓历史债一次性砸给
#   当前这次改动，门禁从第一天起就会失去可信度。
#   但「没跑成」和「跑了有发现」是两回事：工具没装、报告坏了、扫描面空了、
#   工具崩了，都意味着这次的结论是**空的**，把它当 0 发现放行就是自欺
#   （SKIPPED is not a pass）。故 infra 失败一律 exit 3 阻断 CI。
#
# 阻断开关（留给基线燃尽之后，不在本次开启）：
#   等 bandit medium+ / pip-audit 的存量发现被逐条评估、登记基线并燃尽后，
#   把下方 run_parser 的 Python 代码里 `exit_code = 0` 改成「有发现即非 0」，
#   并同步把 GitHub / Gitee 两侧的 job/step 从 shadow 转成 blocking。当前保持
#   shadow，开关位置就在这里，改动应可评审、可回滚。
#
# 用法（CI 与本地同口径）：
#   bash scripts/run-python-sast.sh --selfcheck   # 不联网/不装工具/不跑真扫描，注入假报告验退出码
#   bash scripts/run-python-sast.sh              # 装钉版工具 → 真跑 bandit + pip-audit → 消费结果
#   ALLIN_PYTHON=<解释器> bash scripts/run-python-sast.sh   # CI 指定解释器（默认 python3）
#
# 与 .github/workflows/gates.yml 的 python-sast job / .workflow/pipeline.yml 的
# python_sast step 调同一个脚本，两侧不允许漂移。
#
# 为什么用 "$PY" -m bandit / -m pip_audit 而不是裸命令：
#   等价于 `bandit -r ...` / `pip-audit -r ...`（同一工具、同样的 -r/-f/-o/-ll
#   参数），但保证与「装依赖的解释器」是同一个，不依赖 PATH。实测本机 Windows
#   把 bandit.exe / pip-audit.exe 装在 Scripts/ 且不在 PATH，裸命令会直接找不到
#   ⇒ 用 -m 才能在 GitHub / Gitee / 本机三处都稳定跑起来。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || { echo "ENV ERROR: 无法进入仓根 $ROOT" >&2; exit 3; }

# 解释器：CI 经 ALLIN_PYTHON 指定（与门禁同一个解释器），否则 python3。
PY="${ALLIN_PYTHON:-python3}"

# ---------------------------------------------------------------------------
# 扫描面：显式白名单（仓内真实入库的 Python 源码目录 / 文件）。
# 刻意不写 `find . -name '*.py'`：那会把 vendor/（入库 64 个 .py）、node_modules/、
# .venv/、docs/、site/ 等一并扫进来，扫描面由「当前磁盘状态」而不是「受评审的
# 清单」决定。白名单逐项在 validate_surface 里断言「存在且至少含一个 .py」。
# ---------------------------------------------------------------------------
SAST_SURFACE=(
  "kernel"
  "packages"
  "scripts"
  "tools"
  "preset"
  ".workbuddy/skills"
  "allin_cli.py"
  "__init__.py"
)
# bandit -x 双保险：即便白名单目录下将来出现这些子目录也不扫。
# tests/ 一并排除：测试夹具 / selfcheck 正例里故意构造的「不安全代码」不该被
# 当作生产 findings 消费（research-security 复核指出的误报面）。
SAST_EXCLUDES="vendor,node_modules,.venv,__pycache__,docs,site,.git,build,dist,tests"

AUDIT_DIR="$ROOT/tools/gate/audit"          # 已被 .gitignore 的 /tools/gate/audit/* 覆盖
BANDIT_REPORT="$AUDIT_DIR/sast-bandit-report.json"
AUDIT_REPORT="$AUDIT_DIR/sast-pip-audit-report.json"
JSONL_NAME="sast-runs.jsonl"

# Windows / MSYS2 路径归一（与 scripts/scan-secrets.sh:51-57 同口径）：
# TMPDIR 常是 Windows 原生路径，mktemp 会拼出混合分隔符路径。
posix_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf '%s' "$1"; fi
}

# ---------------------------------------------------------------------------
# 前置检查 ①：工具可用。实跑在 pip install 之后调用；selfcheck 注入恒失败的
# 解释器来模拟「工具缺失」。任何一项不可用 ⇒ return 3（绝不降级）。
# ---------------------------------------------------------------------------
require_sast_tools() {
  local py="$1"
  if ! "$py" -c 'import bandit' >/dev/null 2>&1; then
    echo "ENV ERROR: import bandit 不可用（解释器：$py）" >&2
    return 3
  fi
  # 等价于 `pip-audit --version`：同一 CLI 的 --version，只是不走 PATH。
  if ! "$py" -m pip_audit --version >/dev/null 2>&1; then
    echo "ENV ERROR: pip-audit --version 不可用（解释器：$py）" >&2
    return 3
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 前置检查 ②：扫描面非空。每个白名单项必须存在；目录须能列出至少一个 .py
# （排除噪声目录后）；文件须是 .py。空扫描面 ⇒ return 3（不把「没扫」当通过）。
# ---------------------------------------------------------------------------
validate_surface() {
  local p first
  if [ "${#SAST_SURFACE[@]}" -eq 0 ]; then
    echo "ENV ERROR: SAST 扫描面白名单为空（没有要扫的对象）" >&2
    return 3
  fi
  for p in "${SAST_SURFACE[@]}"; do
    if [ ! -e "$p" ]; then
      echo "ENV ERROR: 白名单路径不存在：$p" >&2
      return 3
    fi
    if [ -d "$p" ]; then
      first="$(find "$p" -type f -name '*.py' \
        -not -path '*/vendor/*' -not -path '*/node_modules/*' \
        -not -path '*/.venv/*' -not -path '*/__pycache__/*' \
        -not -path '*/site/*' -print -quit 2>/dev/null)"
      if [ -z "$first" ]; then
        echo "ENV ERROR: 白名单目录内没有任何 .py 文件（空扫描面）：$p" >&2
        return 3
      fi
    else
      case "$p" in
        *.py) : ;;
        *) echo "ENV ERROR: 白名单文件不是 .py：$p" >&2; return 3 ;;
      esac
    fi
  done
  return 0
}

# ---------------------------------------------------------------------------
# 结果消费 + 退出码判定（Python 标准库，实跑与 selfcheck 共用同一段代码）。
#   $1 bandit 报告  $2 pip-audit 报告  $3 bandit rc  $4 pip-audit rc
#   $5 audit 目录   $6 ts  $7 period  $8 commit
#   GITHUB_ACTIONS 由环境传入，控制 ::warning:: annotation。
# 返回：0=实跑完成（含发现，shadow mode）/ 3=基础设施失败。
# 这段 Python 是「把解析逻辑改坏 selfcheck 就要变红」的那个可证伪面。
# ---------------------------------------------------------------------------
run_parser() {
  SAST_BANDIT_REPORT="$1" SAST_AUDIT_REPORT="$2" \
  SAST_BANDIT_RC="$3" SAST_AUDIT_RC="$4" \
  SAST_AUDIT_DIR="$5" SAST_TS="$6" SAST_PERIOD="$7" SAST_COMMIT="$8" \
  SAST_GITHUB_ACTIONS="${GITHUB_ACTIONS:-}" \
  "$PY" - <<'PYEOF'
import json, os, sys


def esc(s):
    # 与 scripts/run_all_gates.sh:137-143 gh_escape 同口径：% / CR / LF 百分号编码
    return str(s).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def load(path):
    if not os.path.isfile(path):
        raise RuntimeError('report file missing: %s' % path)
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise RuntimeError('report JSON unparsable: %s (%s)' % (path, e))


def need_list(obj, key, where):
    if not isinstance(obj, dict) or key not in obj or not isinstance(obj[key], list):
        raise RuntimeError('%s missing/non-list field: %s' % (where, key))
    return obj[key]


def main():
    env = os.environ
    bf = None
    av = None
    exit_code = 0
    audit_dir = env.get('SAST_AUDIT_DIR', '')
    ts = env.get('SAST_TS', '')
    period = env.get('SAST_PERIOD', '')
    commit = env.get('SAST_COMMIT', 'unknown')
    gh = env.get('SAST_GITHUB_ACTIONS', '') == 'true'
    try:
        bandit_report = env['SAST_BANDIT_REPORT']
        audit_report = env['SAST_AUDIT_REPORT']
        bandit_rc = int(env['SAST_BANDIT_RC'])
        audit_rc = int(env['SAST_AUDIT_RC'])

        # 两个工具的退出码必须被消费：0=无发现 / 1=有发现 / 其它=工具错(infra)
        if bandit_rc not in (0, 1):
            raise RuntimeError('bandit exit code abnormal (tool error): %d' % bandit_rc)
        if audit_rc not in (0, 1):
            raise RuntimeError('pip-audit exit code abnormal (tool error): %d' % audit_rc)

        b = load(bandit_report)
        a = load(audit_report)

        # bandit 输出契约（bandit==1.9.4 实测）：results 列表 + metrics._totals.loc>0
        # loc>0 证明扫描面真被扫过，不是「工具崩了却吐了个空 results」。
        results = need_list(b, 'results', 'bandit')
        metrics = b.get('metrics')
        if not isinstance(metrics, dict) or not isinstance(metrics.get('_totals'), dict):
            raise RuntimeError('bandit missing metrics._totals (empty scan / version drift)')
        loc = metrics['_totals'].get('loc')
        if not isinstance(loc, int) or loc <= 0:
            raise RuntimeError('bandit metrics._totals.loc=%r (no code scanned)' % loc)
        if 'errors' in b and not isinstance(b['errors'], list):
            raise RuntimeError('bandit errors is not a list')

        # pip-audit 输出契约（pip-audit==2.10.1 实测）：漏洞在 dependencies[].vulns，
        # 没有顶层 vulnerabilities 字段 —— 按记忆猜字段会在这里 fail-closed。
        deps = need_list(a, 'dependencies', 'pip-audit')
        if 'fixes' in a and not isinstance(a['fixes'], list):
            raise RuntimeError('pip-audit fixes is not a list')

        bf = len(results)
        av = 0
        lines = []
        for r in results:
            if not isinstance(r, dict):
                raise RuntimeError('bandit results element is not an object')
            lines.append(('BANDIT', '%s:%s  [%s] %s  %s' % (
                r.get('filename', '?'), r.get('line_number', '?'),
                r.get('test_id', '?'), r.get('issue_severity', '?'),
                r.get('issue_text', ''))))
        for d in deps:
            if not isinstance(d, dict):
                raise RuntimeError('pip-audit dependencies element is not an object')
            vulns = need_list(d, 'vulns', 'pip-audit dependency')
            name = d.get('name', '?')
            ver = d.get('version', '?')
            for v in vulns:
                av += 1
                if isinstance(v, dict):
                    lines.append(('AUDIT', '%s@%s  %s  aliases=%s  fix=%s' % (
                        name, ver, v.get('id', '?'), v.get('aliases', []),
                        v.get('fix_versions', []))))
                else:
                    lines.append(('AUDIT', '%s@%s  %s' % (name, ver, v)))

        # 结果消费：发现数与逐条摘要打到 stdout
        print('SAST bandit_findings=%d audit_vulns=%d (shadow mode: findings do NOT block)' % (bf, av))
        for tag, text in lines:
            print('  %s %s' % (tag, text))
        print('SAST_SUMMARY bandit_findings=%d audit_vulns=%d' % (bf, av))
        # GitHub Actions：每条发现转 ::warning:: annotation（匿名可读）
        if gh:
            for tag, text in lines:
                print('::warning::%s %s' % (tag, esc(text)))
    except Exception as e:
        print('SAST_INFRA_ERROR %s: %s' % (type(e).__name__, e), file=sys.stderr)
        bf = None
        av = None
        exit_code = 3

    # 机器可读摘要追加到 tools/gate/audit/sast-runs.jsonl（5MB 轮转沿用 gate-runs.jsonl 口径）
    try:
        os.makedirs(audit_dir, exist_ok=True)
        path = os.path.join(audit_dir, 'sast-runs.jsonl')
        if os.path.isfile(path) and os.path.getsize(path) > 5 * 1024 * 1024:
            os.replace(path, path + '.1')
        rec = {'ts': ts, 'period': period, 'commit': commit,
               'bandit_findings': bf, 'audit_vulns': av, 'exit': exit_code}
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
    except OSError as e:
        print('SAST_INFRA_ERROR write JSONL failed: %s' % e, file=sys.stderr)
        exit_code = 3

    sys.exit(exit_code)


try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
main()
PYEOF
}

# ---------------------------------------------------------------------------
# --selfcheck：不联网 / 不装工具 / 不跑真扫描。注入几组假报告与假前置条件，
# 走与实跑**同一段** require_sast_tools / validate_surface / run_parser 代码，
# 逐分支验证退出码语义。把解析逻辑改坏（例如吞掉 JSON 异常、删掉契约校验）
# 时，下面的 [FAIL] 会立刻变红 ⇒ 自身可证伪。
# ---------------------------------------------------------------------------
SELFTEST_FAIL=0
check_case() {
  # $1 分支名  $2 期望退出码  $3 实得退出码
  if [ "$2" = "$3" ]; then
    printf '  [PASS] %-46s 期望=%s 实得=%s\n' "$1" "$2" "$3"
  else
    printf '  [FAIL] %-46s 期望=%s 实得=%s\n' "$1" "$2" "$3"
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
  fi
}

selftest() {
  local t dir saved r out
  t="$(posix_path "$(mktemp -d "${TMPDIR:-/tmp}/allin-sast-selftest-XXXXXX")")" || return 3
  if [ -z "$t" ]; then echo "ENV ERROR: 无法创建自检临时目录" >&2; return 3; fi
  trap 'rm -rf "${SELFTEST_TMP:-}"' EXIT
  SELFTEST_TMP="$t"
  dir="$t/audit"
  mkdir -p "$dir" || return 3

  # 合法 bandit 报告：1 条 MEDIUM 发现、loc>0（issue_text 含 100% 验 gh_escape）
  cat > "$t/bandit-ok.json" <<'JSON'
{"errors": [], "generated_at": "selfcheck", "metrics": {"_totals": {"loc": 42, "SEVERITY.MEDIUM": 1}, "x.py": {"loc": 42}}, "results": [{"filename": "x.py", "line_number": 7, "test_id": "B999", "issue_severity": "MEDIUM", "issue_text": "selftest fixture 100% coverage"}]}
JSON
  # 合法 pip-audit 报告：1 个依赖、1 条漏洞（vulns 在 dependencies[] 内）
  cat > "$t/audit-ok.json" <<'JSON'
{"dependencies": [{"name": "demo", "version": "0.0.1", "vulns": [{"id": "PYSEC-SELFTEST", "aliases": ["CVE-0000-0000"], "fix_versions": ["0.0.2"]}]}], "fixes": []}
JSON
  printf 'this is not json {{\n' > "$t/bandit-bad.json"
  cat > "$t/audit-nofield.json" <<'JSON'
{"fixes": []}
JSON
  cat > "$t/bandit-loc0.json" <<'JSON'
{"errors": [], "metrics": {"_totals": {"loc": 0}}, "results": []}
JSON
  mkdir -p "$t/empty"

  echo "run-python-sast --selfcheck：注入假报告，逐分支验证退出码语义"
  echo "（不联网 / 不装工具 / 不跑真扫描；共用实跑的解析与前置检查代码）"
  echo

  # ① JSON 可解析（含发现）：shadow mode 下期望 0，且计数/摘要/annotation 正确
  out="$t/case1.out"
  r=0
  GITHUB_ACTIONS=true run_parser "$t/bandit-ok.json" "$t/audit-ok.json" 1 1 \
    "$dir" "2026-11-08T00:00:00Z" "2026-11" "selfcheck" > "$out" 2> "$t/case1.err" || r=$?
  check_case "① JSON 可解析(1 finding/1 vuln, rc 1/1)" 0 "$r"
  grep -q 'SAST_SUMMARY bandit_findings=1 audit_vulns=1' "$out" \
    || { echo "  [FAIL] ① 解析计数不是 1/1（解析逻辑被改坏？）"; SELFTEST_FAIL=$((SELFTEST_FAIL + 1)); }
  grep -q '::warning::' "$out" \
    || { echo "  [FAIL] ① 未生成 ::warning:: annotation"; SELFTEST_FAIL=$((SELFTEST_FAIL + 1)); }
  grep -q '100%25' "$out" \
    || { echo "  [FAIL] ① gh_escape 未把 % 编码成 %25"; SELFTEST_FAIL=$((SELFTEST_FAIL + 1)); }

  # ② 空扫描面：目录存在但无 .py / 路径不存在 / 空数组，三者都应 3；真实白名单正向 0
  saved=("${SAST_SURFACE[@]}")
  SAST_SURFACE=("$t/empty")
  r=0; validate_surface >"$t/c2.out" 2>"$t/c2.err" || r=$?
  check_case "② 空扫描面(目录无 .py)" 3 "$r"
  SAST_SURFACE=("$t/does-not-exist")
  r=0; validate_surface >"$t/c3.out" 2>"$t/c3.err" || r=$?
  check_case "② 空扫描面(路径不存在)" 3 "$r"
  SAST_SURFACE=()
  r=0; validate_surface >"$t/c4.out" 2>"$t/c4.err" || r=$?
  check_case "② 空扫描面(白名单空数组)" 3 "$r"
  SAST_SURFACE=("${saved[@]}")
  r=0; validate_surface >"$t/c5.out" 2>"$t/c5.err" || r=$?
  check_case "② 真实白名单(正向, 应通过)" 0 "$r"

  # ③ 工具缺失：注入恒失败的解释器，模拟 import bandit / pip-audit 不可用
  r=0; require_sast_tools false >"$t/c6.out" 2>"$t/c6.err" || r=$?
  check_case "③ 工具缺失(恒失败解释器)" 3 "$r"

  # ④ 报告损坏 / 字段缺失 / 工具错：五组注入都应 3
  r=0; run_parser "$t/bandit-bad.json" "$t/audit-ok.json" 0 0 \
    "$dir" "T" "P" "C" >"$t/c7.out" 2>"$t/c7.err" || r=$?
  check_case "④ 报告损坏(bandit JSON 语法坏)" 3 "$r"
  r=0; run_parser "$t/nope.json" "$t/audit-ok.json" 0 0 \
    "$dir" "T" "P" "C" >"$t/c8.out" 2>"$t/c8.err" || r=$?
  check_case "④ 报告损坏(bandit 报告不存在)" 3 "$r"
  r=0; run_parser "$t/bandit-ok.json" "$t/audit-nofield.json" 0 0 \
    "$dir" "T" "P" "C" >"$t/c9.out" 2>"$t/c9.err" || r=$?
  check_case "④ 报告损坏(audit 缺 dependencies)" 3 "$r"
  r=0; run_parser "$t/bandit-loc0.json" "$t/audit-ok.json" 0 0 \
    "$dir" "T" "P" "C" >"$t/c10.out" 2>"$t/c10.err" || r=$?
  check_case "④ 报告损坏(bandit loc=0 空扫描)" 3 "$r"
  r=0; run_parser "$t/bandit-ok.json" "$t/audit-ok.json" 2 0 \
    "$dir" "T" "P" "C" >"$t/c11.out" 2>"$t/c11.err" || r=$?
  check_case "④ 工具退出码异常(bandit rc=2)" 3 "$r"

  # JSONL 消费证据：既要有 exit=0 的行，也要有 exit=3 的行
  local jsonl="$dir/$JSONL_NAME"
  if ! grep -q '"exit":0' "$jsonl" || ! grep -q '"exit":3' "$jsonl"; then
    echo "  [FAIL] JSONL 未同时记录 exit=0 与 exit=3 两类运行"
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
  else
    printf '  [PASS] %-46s 行数=%s\n' "JSONL 记录 exit=0 与 exit=3" "$(wc -l < "$jsonl" | tr -d ' ')"
  fi

  echo
  if [ "$SELFTEST_FAIL" -eq 0 ]; then
    echo "run-python-sast --selfcheck: 全部通过（4 类分支 × 11 注入 + 计数/annotation/JSONL 断言）"
  else
    echo "run-python-sast --selfcheck: $SELFTEST_FAIL 项失败" >&2
  fi
  return "$SELFTEST_FAIL"
}

if [ "${1:-}" = "--selfcheck" ]; then
  selftest
  exit $?
fi

# ---------------------------------------------------------------------------
# 实跑
# ---------------------------------------------------------------------------
if ! "$PY" -c 'import sys; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
  echo "ENV ERROR: 解释器不可用或低于 3.9：$PY（用 ALLIN_PYTHON 指定）" >&2
  exit 3
fi

# 空扫描面 / 白名单缺失一律 exit 3，先判再联网，省得白跑一趟。
validate_surface || exit 3

# 装钉版工具：失败一律 exit 3，绝不 || true / || echo skip。
if ! "$PY" -m pip install --quiet -r requirements-sast.txt; then
  echo "ENV ERROR: 安装 requirements-sast.txt 失败（bandit / pip-audit 不可用）" >&2
  exit 3
fi

# 装完再确认工具真的可用（import bandit / pip-audit --version）。
require_sast_tools "$PY" || exit 3

mkdir -p "$AUDIT_DIR" || { echo "ENV ERROR: 无法创建 $AUDIT_DIR" >&2; exit 3; }
TMP="$(posix_path "$(mktemp -d "${TMPDIR:-/tmp}/allin-sast-XXXXXX")")" || {
  echo "ENV ERROR: 无法创建临时目录" >&2; exit 3; }
trap 'rm -rf "${TMP:-}"' EXIT
BANDIT_LOG="$TMP/bandit.log"
AUDIT_LOG="$TMP/pip-audit.log"

echo "==> bandit -r ${SAST_SURFACE[*]} -x <excludes> -ll -f json -o $BANDIT_REPORT"
bandit_rc=0
"$PY" -m bandit -r "${SAST_SURFACE[@]}" -x "$SAST_EXCLUDES" -ll \
  -f json -o "$BANDIT_REPORT" > "$BANDIT_LOG" 2>&1 || bandit_rc=$?
tail -n 12 "$BANDIT_LOG"
echo "    bandit exit=$bandit_rc"

echo "==> pip-audit -r requirements-dev.txt -r requirements-release.txt -f json -o $AUDIT_REPORT"
audit_rc=0
"$PY" -m pip_audit -r requirements-dev.txt -r requirements-release.txt \
  -f json -o "$AUDIT_REPORT" > "$AUDIT_LOG" 2>&1 || audit_rc=$?
tail -n 12 "$AUDIT_LOG"
echo "    pip-audit exit=$audit_rc"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PERIOD="$(date -u +%Y-%m)"
if ! COMMIT="$(git rev-parse --short HEAD 2>/dev/null)"; then
  COMMIT="unknown"
fi

# 统一消费结果：解析两份 JSON、打印摘要/annotation、写 JSONL、判定最终退出码。
rc=0
run_parser "$BANDIT_REPORT" "$AUDIT_REPORT" "$bandit_rc" "$audit_rc" \
  "$AUDIT_DIR" "$TS" "$PERIOD" "$COMMIT" || rc=$?
exit "$rc"
