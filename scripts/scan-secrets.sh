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
# 用法（CI 与本地同一口径）：
#   GITLEAKS_BASE_SHA=<base-sha> bash scripts/scan-secrets.sh
#   GITLEAKS_BIN=<gitleaks 路径> GITLEAKS_BASE_SHA=<base-sha> bash scripts/scan-secrets.sh
#
# 未装 gitleaks / 基线无法确定 ⇒ exit 3（环境错），**不静默跳过**：
# 本仓口径是 SKIPPED (not a pass)，凭据防线不允许「假装跑过了」。

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

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
SCAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/allin-secrets-XXXXXX")"
RAW="$SCAN_DIR/diff.raw"
ADDED="$SCAN_DIR/added-lines.txt"
trap 'rm -f "$RAW" "$ADDED"; rmdir "$SCAN_DIR" 2>/dev/null || true' EXIT

if ! git diff -U0 --no-color "$BASE" HEAD > "$RAW" 2>/dev/null; then
  echo "ENV ERROR: git diff $BASE HEAD 失败（基线 $BASE 不可达？需 fetch-depth: 0）。" >&2
  exit 3
fi

# 只保留新增行：剔除 diff 的 `+++ b/...` 文件头，再去掉行首的 '+'。
# 带 `gov-credentials: allow` / `repo-hygiene: allow` 的行是仓内**显式声明**的
# 测试夹具（g03 与 repo_hygiene 各有一套同类注解），整行都是合成值。它们随治理
# 源码改动进入 diff 时若一并交给 gitleaks，会被通用规则判红 —— 与 g03 的
# inline annotation 同口径排除，避免门禁被自己的正例夹具拖红。
grep '^+' "$RAW" | grep -v '^+++' | sed 's/^+//' \
  | grep -v 'gov-credentials: allow' \
  | grep -v 'repo-hygiene: allow' > "$ADDED" || true

if [ ! -s "$ADDED" ]; then
  echo "gitleaks: 本次变更无新增行（基线 $BASE）—— 无扫描面，跳过（不声称通过）"
  exit 0
fi

echo "gitleaks: 扫描 $(wc -l < "$ADDED" | tr -d ' ') 行新增内容（基线 ${BASE:0:12}）"
"$GITLEAKS_BIN" detect --no-git --redact --source "$SCAN_DIR" --exit-code 1
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "gitleaks: 新增内容未发现密钥"
else
  echo "gitleaks: 新增内容发现疑似密钥（exit=$rc）—— 详见上方（已 redact）报告"
fi
exit "$rc"
