@echo off
rem allin-platform portal launcher (DSH-style: standalone web app, opened
rem in the browser automatically).
rem Paths are derived from this script's directory (%~dp0) since 2026-09-24:
rem clone the repo anywhere and double-click; paths derive from %~dp0, no hard-coded drive paths.
rem PORT=0 picks an ephemeral port: keep this window open while the portal
rem runs; close the window or press Ctrl+C to release the port.
rem Deps are installed into <repo>\node_modules (npm workspaces) when
rem missing. The local mirror proxy at http://127.0.0.1:8899 is OPTIONAL
rem (2026-11-10): when it is up we install through it, otherwise we fall
rem back to platform\.npmrc / the public registry. The mirror is probed by
rem scripts\ensure-mirror.ps1 -Optional, a plain readable script file
rem instead of a long obfuscated-looking inline command (keeps security
rem software happy).
set "PLATFORM_DIR=%~dp0"
rem 便携版（.iss 安装包）随包 node 优先：node\node.exe 同仓存放时加入 PATH 前列
if exist "%PLATFORM_DIR%node\node.exe" set "PATH=%PLATFORM_DIR%node;%PATH%"
set NODE_OPTIONS=
set npm_config_fetch_timeout=600000
set npm_config_fetch_retries=5
rem 2026-11-10 换机可移植整改：本地镜像**不再是强依赖**。
rem 此前无条件 set npm_config_registry=http://127.0.0.1:8899，而代理脚本在仓外，
rem 新机必然装不上 ⇒ npm install 100% 失败（换机即坏）。
rem 现在：探测到镜像就绪才指向它；否则回退 platform\.npmrc / 公网 registry，并把
rem 真实原因打出来（不再 >nul 2>&1 吞掉失败原因）。
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "%PLATFORM_DIR%scripts\ensure-mirror.ps1" -Optional
if errorlevel 10 goto nomirror
if errorlevel 1 goto mirrorfail
set npm_config_registry=http://127.0.0.1:8899
echo [ok] 本地镜像 127.0.0.1:8899 就绪，走镜像安装。
goto deps
:nomirror
echo [warn] 未启用本地镜像（127.0.0.1:8899 不可用）—— 已回退默认 registry。
echo [warn] 装包将走公网；如需走镜像，请先启动 %%USERPROFILE%%\.dsh\npm_local_mirror.py。
goto deps
:mirrorfail
echo [error] 镜像代理启动失败，已中止（避免 npm 半装状态）。
goto fail
:deps
cd /d "%PLATFORM_DIR%"
if not exist "node_modules\@allin\core" (
  echo Installing dependencies, please wait...
  call npm install --no-audit --no-fund
  if errorlevel 1 goto fail
)
cd /d "%PLATFORM_DIR%apps\portal"
set PORT=0
set PORTAL_AUTO_OPEN=1
node src\index.js
echo.
echo Portal stopped, port released.
pause
exit /b 0

:fail
echo.
echo Failed to install dependencies. Check your network or registry
echo settings, then rerun this launcher.
pause
exit /b 1
