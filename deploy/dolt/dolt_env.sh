#!/usr/bin/env bash
# dolt_env.sh —— deploy/dolt 各脚本的**共享环境解析**（单一真相源）
#
# 2026-11-10 换机可移植整改：此前 asof_verify.sh / sql_server.sh / remote_backup.sh
# 各自硬编码了「dolt 安装盘位」「某台机器的 Python 绝对路径」「固定 E 盘的灾备目录」，
# 只要 dolt / Python / 灾备盘不在那几个位置就失效（换机即坏）。
# 现在统一收敛为：**env 优先、PATH 兜底、找不到就 fail-loud 并说清怎么配**。
#
# 解析顺序：
#   dolt   : ALLIN_DOLT_BIN → DOLT_HOME(/bin) → PATH
#   python : ALLIN_PYTHON → 仓内 .venv → python3 → python
#   灾备根 : DOLT_BACKUP_ROOT（**无默认值**：盘符随机器变，不猜）
#
# 常见安装位置请自行用环境变量指明（本文件刻意不写任何盘符字面量）：
#   ALLIN_DOLT_BIN=<dolt 可执行文件所在目录>
#   DOLT_HOME=<dolt 安装目录>
#   DOLT_BACKUP_ROOT=<灾备目录>

# allin_resolve_dolt —— 找到就把 dolt 目录前置到 PATH；找不到返回 1。
allin_resolve_dolt() {
  local c
  if [ -n "${ALLIN_DOLT_BIN:-}" ]; then
    c="$ALLIN_DOLT_BIN"
    if [ -x "$c/dolt" ] || [ -x "$c/dolt.exe" ]; then
      export PATH="$(cd "$(dirname "$c")" && pwd):$PATH"
      return 0
    fi
  fi
  if [ -n "${DOLT_HOME:-}" ]; then
    for c in "$DOLT_HOME/bin" "$DOLT_HOME"; do
      if [ -x "$c/dolt" ] || [ -x "$c/dolt.exe" ]; then
        export PATH="$(cd "$(dirname "$c")" && pwd):$PATH"
        return 0
      fi
    done
  fi
  command -v dolt >/dev/null 2>&1
}

# allin_resolve_python —— 打印可用的 Python 解释器路径；找不到返回 1。
allin_resolve_python() {
  local c
  for c in "${ALLIN_PYTHON:-}" \
           "$ROOT/.venv/bin/python" \
           "$ROOT/.venv/Scripts/python.exe"; do
    [ -n "$c" ] || continue
    if [ -x "$c" ]; then
      printf '%s' "$c"
      return 0
    fi
  done
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      command -v "$c"
      return 0
    fi
  done
  return 1
}

# allin_dolt_env_error —— 统一的环境错误文案（说清怎么配，而不是只说「不在 PATH」）。
allin_dolt_env_error() {
  echo "ENV ERROR: 找不到 dolt 二进制。"
  echo "  修法：设 ALLIN_DOLT_BIN=<dolt.exe 所在目录> 或 DOLT_HOME=<dolt 安装目录>，"
  echo "        或把 dolt 放进 PATH。本脚本不猜盘符（盘符与安装位置随机器变）。"
}
