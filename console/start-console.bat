@echo off
chcp 65001 >nul
rem allin-console 启动器（Windows）
rem
rem 必须清 ELECTRON_RUN_AS_NODE：本机宿主进程会注入该变量，electron.exe 收到后会
rem 以纯 Node 模式运行 —— 表现为 --version 输出 Node 版本、GUI 静默退出且无报错。
set "ELECTRON_RUN_AS_NODE="
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

if not exist "node_modules\electron\dist\electron.exe" (
  echo [allin-console] 缺少 Electron 二进制，正在下载...
  set "ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/"
  node node_modules\electron\install.js || goto :fail
)

start "" "node_modules\electron\dist\electron.exe" .
exit /b 0

:fail
echo [allin-console] 启动失败：Electron 二进制不可用。
pause
exit /b 1
