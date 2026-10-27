@echo off
rem allin-platform portal launcher (DSH-style: standalone web app, opened
rem in the browser automatically).
rem Paths are derived from this script's directory (%~dp0) since 2026-09-24:
rem clone the repo anywhere and double-click; paths derive from %~dp0, no hard-coded drive paths.
rem PORT=0 picks an ephemeral port: keep this window open while the portal
rem runs; close the window or press Ctrl+C to release the port.
rem Deps are installed into <repo>\node_modules (npm workspaces) when
rem missing; installs go through the local mirror proxy at
rem http://127.0.0.1:8899 (required on this network).
rem The mirror proxy is started and verified by scripts\ensure-mirror.ps1,
rem a plain readable script file instead of a long obfuscated-looking
rem inline command (keeps security software happy).
set "PLATFORM_DIR=%~dp0"
rem 便携版（.iss 安装包）随包 node 优先：node\node.exe 同仓存放时加入 PATH 前列
if exist "%PLATFORM_DIR%node\node.exe" set "PATH=%PLATFORM_DIR%node;%PATH%"
set NODE_OPTIONS=
set npm_config_registry=http://127.0.0.1:8899
set npm_config_fetch_timeout=600000
set npm_config_fetch_retries=5
rem Make sure the local mirror proxy is up before npm touches the network.
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "%PLATFORM_DIR%scripts\ensure-mirror.ps1" >nul 2>&1 || echo [warn] local mirror proxy 127.0.0.1:8899 not ready
cd /d "%PLATFORM_DIR%"
if not exist "node_modules\@allin\core" (
  echo Installing dependencies via the local mirror, please wait...
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
echo Failed to install dependencies; the local mirror proxy on
echo 127.0.0.1:8899 may be down. Fix it, then rerun this launcher.
pause
exit /b 1
