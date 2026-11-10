#!/usr/bin/env bash
# sql_server.sh —— P1-3：启动 dolt sql-server（localhost:3306，MySQL 线协议）
#
# 纪律（见 deploy/dolt/README.md §3）：sql-server 是**本地服务**，绑回环地址；
# 多机同步靠 dolt push/pull 到远端，不是实时多写。启动属服务态变更，需授权，沙箱不代跑。
#
# 默认 dry-run 打印计划；--apply 才真正拉起（--background 后台运行，否则前台）。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 3

# 2026-11-10 换机可移植：dolt 定位收敛到共享解析（不再硬编码安装盘位）
. "$ROOT/deploy/dolt/dolt_env.sh"
WS="$ROOT/facts/dolt-workspace"
HOST="127.0.0.1"
PORT="3306"
APPLY=0; BACKGROUND=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --background) BACKGROUND=1 ;;
  esac
done

if ! command -v dolt >/dev/null 2>&1; then
  allin_dolt_env_error; exit 3
fi
if [ ! -d "$WS/.dolt" ]; then
  echo "ENV ERROR: $WS 未初始化（先跑 import_from_git.py --apply）"; exit 3
fi
if ! command -v nohup >/dev/null 2>&1; then
  echo "ENV WARN: 无 nohup，--background 将退化为前台（Ctrl-C 退出）"
fi

echo "SQL-SERVER 目标: $HOST:$PORT  (workspace=$WS)"
if [ $APPLY -eq 1 ]; then
  if [ $BACKGROUND -eq 1 ] && command -v nohup >/dev/null 2>&1; then
    nohup dolt sql-server --host "$HOST" --port "$PORT" --log-level info \
      > "$WS/sql-server.log" 2>&1 &
    echo "  started (bg pid $!) -> log $WS/sql-server.log"
  else
    echo "  前台启动（Ctrl-C 退出）："
    exec dolt sql-server --host "$HOST" --port "$PORT"
  fi
else
  echo "  (dry-run) 真实启动需 --apply [--background]"
  echo "  等价命令: dolt sql-server --host $HOST --port $PORT"
fi
exit 0
