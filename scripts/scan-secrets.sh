#!/usr/bin/env bash
# CI 密钥增量扫描 —— 补上「外部 PR 不装 pre-commit」的防线（2026-11-04 工程审查 P1-4）。
#
# 为什么只扫新增行、而不是整棵树：
#   本仓刻意保留了一批「长得像凭据」的测试夹具 —— tools/repo_hygiene.py 的 H5
#   正例、g03 的 selfcheck 夹具、交接记录里的 SHA256 / 示例 token。全树跑
#   `gitleaks detect --no-git` 会把它们全部判红，门禁立刻失去可信度（就像 g03
#   必须给 40/64 位 digest 留白名单一样）。而威胁模型是「外部贡献者往 PR 里
#   夹带密钥」—— 那必然落在本次变更的新增行里。故把扫描面收敛到
#   `git diff -U0 <base> HEAD` 的 `+` 行：新增泄露一个不漏，存量夹具一个不进。
#   删除行（-）与上下文行都不扫，避免把「删掉的示例」误判成新增泄露。
#
# 2026-11-07 安全评估加固（F-01 / F-02）：
#   F-01 内联注解原本「任何文件里带注解的那一行整行剔除」。注解本身是被扫描
#        内容的一部分 ⇒ 等于把豁免权交给被扫描者：外部贡献者只要追加一个
#        二十来字符的注释，就能把夹带的真实密钥从扫描面里抹掉。现在注解只在
#        `scripts/secret-scan-allowlist.txt` 登记的**仓库自有夹具文件**内生效；
#        出现在其它任何文件 → 该行保留给 gitleaks 且无论结论如何一律判失败。
#   F-02 原先把整个临时目录（含 diff.raw）交给 gitleaks，与「只扫新增行」的
#        自述不符：删除行实际上仍被扫描，把一个「删掉硬编码密钥」的 PR 判红。
#        现在单独建 payload/ 子目录，里面**只有**过滤后的 added-lines.txt。
#
# 用法（CI 与本地同一口径）：
#   GITLEAKS_BASE_SHA=<base-sha> bash scripts/scan-secrets.sh
#   GITLEAKS_BIN=<gitleaks 路径> GITLEAKS_BASE_SHA=<base-sha> bash scripts/scan-secrets.sh
#   bash scripts/scan-secrets.sh --selftest   # 不依赖 gitleaks，自检过滤器行为
#
# 未装 gitleaks / 基线无法确定 ⇒ exit 3（环境错），**不静默跳过**：
# 本仓口径是 SKIPPED (not a pass)，凭据防线不允许「假装跑过了」。
# 退出码：0 通过 / 1 发现密钥 / 2 注解越权（fail closed）/ 3 环境错。

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# 唯一事实源：与 g03_credentials.py 共用同一份夹具白名单，两侧口径不允许漂移。
ALLOWLIST="$ROOT/scripts/secret-scan-allowlist.txt"

# ---------------------------------------------------------------------------
# 把 `git diff -U0` 折成「只含新增行」的扫描文件，同时记录越权的注解。
#   $1 raw diff   $2 输出（新增行）   $3 输出（越权注解所属文件，一行一个）
#
# 用 awk 而不是 grep -v：需要知道每一行属于哪个 `+++ b/<path>`，否则无法把
# 豁免限定到具体文件。路径统一用 core.quotepath=false 取原始 UTF-8。
# ---------------------------------------------------------------------------
filter_added_lines() {
  local raw="$1" added="$2" abuse="$3"
  : > "$added"
  : > "$abuse"
  awk -v allowlist="$ALLOWLIST" -v abuse="$abuse" '
    BEGIN {
      while ((getline rec < allowlist) > 0) {
        sub(/\r$/, "", rec)
        if (rec == "" || rec ~ /^[[:space:]]*#/) continue
        allowed[rec] = 1
      }
      close(allowlist)
    }
    function is_fixture(f) {
      if (f in allowed) return 1
      # 文档化样例文件（.example / .sample / .template / .dist）整文件按样例处理，
      # 与 g03 的 SAMPLE_FILE_SUFFIXES / INFIXES 同口径。
      return (f ~ /\.(example|sample|template|dist)$/ ||
              f ~ /\.(example|sample|template|dist)\./)
    }
    /^\+\+\+ / {
      f = substr($0, 5)
      if (substr(f, 1, 2) == "b/") f = substr(f, 3)
      else f = ""                       # "+++ /dev/null"（删除文件）
      file = f
      next
    }
    /^\+/ {
      line = substr($0, 2)
      if (line ~ /gov-credentials: allow/ || line ~ /repo-hygiene: allow/) {
        if (is_fixture(file)) next      # 仓库自有夹具：按既有口径整行剔除
        print file >> abuse             # 其余：保留给 gitleaks，并标记构建必失败
        print line
        next
      }
      print line
    }
  ' "$raw" > "$added"
}

# ---------------------------------------------------------------------------
# 自检：造一段合成 diff，验证三条不变量。不需要 gitleaks / 网络 / git 历史，
# CI 与本地都能跑；门禁改坏时第一时间在这里红，而不是等真密钥漏出去才发现。
# ---------------------------------------------------------------------------
selftest() {
  local t raw added abuse fail=0
  t="$(mktemp -d "${TMPDIR:-/tmp}/allin-secrets-selftest-XXXXXX")"
  raw="$t/diff.raw"; added="$t/added-lines.txt"; abuse="$t/abuse.txt"
  cat > "$raw" <<'DIFF'
diff --git a/src/wallet.js b/src/wallet.js
--- a/src/wallet.js
+++ b/src/wallet.js
@@ -1,0 +2,2 @@
+const TOKEN = 'TOKEN_OUTSIDE_FIXTURE_0001';  // gov-credentials: allow
+const CLEAN = 'this line is harmless';
-const OLD = 'TOKEN_DELETED_LINE_0002';
diff --git a/tools/repo_hygiene.py b/tools/repo_hygiene.py
--- a/tools/repo_hygiene.py
+++ b/tools/repo_hygiene.py
@@ -1,0 +2 @@
+wr(d, "t/fixture.log", "TOKEN_INSIDE_FIXTURE_0003")  # repo-hygiene: allow
DIFF
  filter_added_lines "$raw" "$added" "$abuse"

  # ① 非白名单文件里的注解不得抹掉该行（真实密钥仍会交给 gitleaks）
  grep -qF 'TOKEN_OUTSIDE_FIXTURE_0001' "$added" \
    || { echo 'SELFT FAIL: 越权注解把非夹具文件的整行抹掉了'; fail=1; }
  # ② 越权注解必须被记录（构建据此 fail closed）
  grep -qxF 'src/wallet.js' "$abuse" \
    || { echo 'SELFT FAIL: 越权注解未记录所属文件'; fail=1; }
  # ③ 删除行绝不进入扫描面
  grep -qF 'TOKEN_DELETED_LINE_0002' "$added" \
    && { echo 'SELFT FAIL: 删除行混进了扫描面'; fail=1; }
  # ④ 白名单夹具文件里的注解仍然按原口径剔除（不把门禁自己的正例拖红）
  grep -qF 'TOKEN_INSIDE_FIXTURE_0003' "$added" \
    && { echo 'SELFT FAIL: 白名单夹具行未被剔除'; fail=1; }
  # ⑤ ++ 文件头本身不能混进扫描面
  grep -qF '+++ b/' "$added" \
    && { echo 'SELFT FAIL: diff 文件头混进了扫描面'; fail=1; }

  rm -f "$raw" "$added" "$abuse"
  rmdir "$t" 2>/dev/null || true
  if [ "$fail" -eq 0 ]; then
    echo 'scan-secrets --selftest: 5/5 通过（越权注解 / 删除行 / 夹具豁免 / 文件头）'
  fi
  return "$fail"
}

if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit $?
fi

if [ ! -r "$ALLOWLIST" ]; then
  echo "ENV ERROR: 夹具白名单不可读：$ALLOWLIST" >&2
  exit 3
fi

# GitHub Actions：install-gitleaks.sh 写了 $GITHUB_PATH，PATH 里直接能找到 gitleaks。
# Gitee Go：没有 $GITHUB_PATH（且多个 command 不共享 shell 会话），但安装脚本把二进制
# 固定放在 <安装目录>/gitleaks（默认 /tmp/gitleaks-8.18.4/gitleaks）—— 这里按同一
# 路径兜底，使两侧都只需依次调「安装脚本 + 本脚本」两个文件，不靠跨步骤传变量。
# 若自定义了 GITLEAKS_INSTALL_DIR，两个脚本必须给同一个值（安装脚本会 echo 出实际路径）。
if [ -z "${GITLEAKS_BIN:-}" ]; then
  if command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS_BIN="$(command -v gitleaks)"
  else
    for cand in "${GITLEAKS_INSTALL_DIR:-/tmp/gitleaks-8.18.4}/gitleaks" /tmp/gitleaks-8.18.4/gitleaks; do
      if [ -x "$cand" ]; then GITLEAKS_BIN="$cand"; break; fi
    done
    GITLEAKS_BIN="${GITLEAKS_BIN:-gitleaks}"
  fi
fi
if ! command -v "$GITLEAKS_BIN" >/dev/null 2>&1 && [ ! -x "$GITLEAKS_BIN" ]; then
  echo "ENV ERROR: 找不到 gitleaks（PATH / GITLEAKS_BIN=<路径> / 安装目录固定路径）。" >&2
  echo "          先跑 bash scripts/install-gitleaks.sh，或显式指定 GITLEAKS_BIN。" >&2
  exit 3
fi

BASE="${GITLEAKS_BASE_SHA:-}"
# 本地/无显式基线时回退：先与 origin/master 求分叉点，再退到 HEAD~1。
# 全 0 的 before（首次推送）同样按回退处理，否则 git diff 必失败。
if [ -z "$BASE" ] || [ "$BASE" = "0000000000000000000000000000000000000000" ]; then
  BASE="$(git merge-base HEAD origin/master 2>/dev/null || git rev-parse 'HEAD~1' 2>/dev/null || true)"
fi
if [ -z "$BASE" ]; then
  echo "ENV ERROR: 无法确定变更基线（GITLEAKS_BASE_SHA 未设置且无 origin/master / HEAD~1）。" >&2
  exit 3
fi

# --source 传目录而非单个文件：gitleaks 的 --no-git 走 filepath.Walk，
# 传目录是它最标准的用法，避开不同版本对「单文件 source」的行为差异。
# 关键：payload/ 里**只放过滤后的 added-lines.txt**；raw diff 与越权记录放在
# 外层，绝不进入 gitleaks 的扫描面（F-02）。
SCAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/allin-secrets-XXXXXX")"
PAYLOAD="$SCAN_DIR/payload"
RAW="$SCAN_DIR/diff.raw"
ABUSE="$SCAN_DIR/annotation-abuse.txt"
ADDED="$PAYLOAD/added-lines.txt"
mkdir -p "$PAYLOAD" || exit 3
trap 'rm -f "$RAW" "$ABUSE" "$ADDED"; rmdir "$PAYLOAD" "$SCAN_DIR" 2>/dev/null || true' EXIT

if ! git -c core.quotepath=false diff -U0 --no-color "$BASE" HEAD > "$RAW" 2>/dev/null; then
  echo "ENV ERROR: git diff $BASE HEAD 失败（基线 $BASE 不可达？需 fetch-depth: 0）。" >&2
  exit 3
fi

filter_added_lines "$RAW" "$ADDED" "$ABUSE"

if [ ! -s "$ADDED" ]; then
  # 即使没有扫描面，越权注解也不能随一次「空变更」悄悄溜过去。
  if [ -s "$ABUSE" ]; then
    echo 'REJECT: 本次变更使用了越权的内联豁免注解（且无其它新增行可扫）。' >&2
    sort -u "$ABUSE" | sed 's/^/    - /' >&2
    exit 2
  fi
  echo "gitleaks: 本次变更无新增行（基线 $BASE）—— 无扫描面，跳过（不声称通过）"
  exit 0
fi

echo "gitleaks: 扫描 $(wc -l < "$ADDED" | tr -d ' ') 行新增内容（基线 ${BASE:0:12}）"
"$GITLEAKS_BIN" detect --no-git --redact --source "$PAYLOAD" --exit-code 1
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "gitleaks: 新增内容未发现密钥"
else
  echo "gitleaks: 新增内容发现疑似密钥（exit=$rc）—— 详见上方（已 redact）报告"
fi

# fail closed：注解越权与 gitleaks 结论取较严重者，不允许「没扫出东西就放行」。
if [ -s "$ABUSE" ]; then
  echo 'REJECT: 内联豁免注解出现在未登记的夹具文件之外 —— 拒绝放行。' >&2
  echo '       注解只允许出现在 scripts/secret-scan-allowlist.txt 登记的文件内；' >&2
  echo '       若确为新夹具，请先在该白名单登记（受评审的仓库配置），不要写在提交内容里。' >&2
  sort -u "$ABUSE" | sed 's/^/         涉及文件：/' >&2
  rc=2
fi
exit "$rc"
