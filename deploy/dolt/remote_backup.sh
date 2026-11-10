#!/usr/bin/env bash
# remote_backup.sh —— P1-2：配置 Dolt remote（GitHub refs/dolt/data）+ 本地 DOLT_BACKUP 灾备
#
# 纪律（见 deploy/dolt/README.md §2/§5）：Git 真身是唯一写入权威，Dolt 是派生物；
# remote / backup 只推 visibility=public 的行，私有字段不得出本机。
#
# 默认 dry-run 打印计划；只有 --apply 才真正执行 dolt remote add / backup sync / push
# （remote add 改本机 .dolt 配置，push 需网络 + 远端权限，属需授权动作，沙箱不代跑）。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 3

# 2026-11-10 换机可移植：dolt 定位收敛到共享解析（不再硬编码安装盘位）
. "$ROOT/deploy/dolt/dolt_env.sh"
WS="$ROOT/facts/dolt-workspace"
REMOTE_NAME="allin-git"                                  # 推到 allin GitHub 仓的 refs/dolt/data
REMOTE_URL="git@github.com:siwpan95/allin.git"
BACKUP_NAME="local-backup"
# 灾备根不再写死盘符：2026-11-10 起由 DOLT_BACKUP_ROOT 提供（无默认值 —— 盘符随机器变）。
BACKUP_ROOT="${DOLT_BACKUP_ROOT:-}"
BACKUP_URL=""
if [ -n "$BACKUP_ROOT" ]; then
  BACKUP_URL="file://$(printf '%s' "$BACKUP_ROOT" | sed 's|\\|/|g')"
fi
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

if ! command -v dolt >/dev/null 2>&1; then
  allin_dolt_env_error; exit 3
fi
if [ $APPLY -eq 1 ] && [ -z "$BACKUP_URL" ]; then
  echo "ENV ERROR: 灾备根未配置（--apply 需要它）。"
  echo "  修法：设 DOLT_BACKUP_ROOT=<灾备目录>（不再默认写死某个盘符）。"
  exit 3
fi
if [ ! -d "$WS/.dolt" ]; then
  echo "ENV ERROR: $WS 未初始化（先跑 import_from_git.py --apply）"; exit 3
fi

cd "$WS" || exit 3

# 1) remote（GitHub refs/dolt/data 双核下游）
have_remote="$(dolt remote 2>/dev/null | awk -v n="$REMOTE_NAME" '$1==n{print 1}')"
if [ "$have_remote" = "1" ]; then
  echo "REMOTE 已存在: $REMOTE_NAME -> $(dolt remote 2>/dev/null | awk -v n="$REMOTE_NAME" '$1==n{print $2}')"
else
  echo "REMOTE 待添加: $REMOTE_NAME -> $REMOTE_URL"
  if [ $APPLY -eq 1 ]; then
    dolt remote add "$REMOTE_NAME" "$REMOTE_URL" && echo "  added" || echo "  add 失败（检查网络/权限）"
  fi
fi

# 2) 本地 DOLT_BACKUP 灾备
have_bk="$(dolt remote 2>/dev/null | awk -v n="$BACKUP_NAME" '$1==n{print 1}')"
if [ "$have_bk" = "1" ]; then
  echo "BACKUP 已配置: $BACKUP_NAME -> $(dolt remote 2>/dev/null | awk -v n="$BACKUP_NAME" '$1==n{print $2}')"
else
  echo "BACKUP 待配置: $BACKUP_NAME -> ${BACKUP_URL:-<未配置 DOLT_BACKUP_ROOT>}"
  if [ $APPLY -eq 1 ]; then
    dolt backup add "$BACKUP_NAME" "$BACKUP_URL" && echo "  added" || echo "  backup add 失败（检查灾备目录可写）"
  fi
fi

# 3) push / sync（--apply 才真正跑）
if [ $APPLY -eq 1 ]; then
  echo "PUSH $REMOTE_NAME ..."; dolt push "$REMOTE_NAME" && echo "  pushed" || echo "  push 失败（需网络/权限）"
  echo "SYNC $BACKUP_NAME ..."; dolt backup sync "$BACKUP_NAME" && echo "  synced" || echo "  sync 失败"
else
  echo "PUSH $REMOTE_NAME: dry-run（执行需 --apply，需网络）"
  echo "SYNC $BACKUP_NAME: dry-run（执行需 --apply，写 E:/allin-dolt-backup）"
fi
exit 0
