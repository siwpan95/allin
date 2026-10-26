@echo off
REM Shim that lets USE_SYSTEM_7ZA=true route every 7za call through 7za_wrap.js.
REM Put this directory (and 7za_wrap.js) at the FRONT of PATH, and set:
REM     USE_SYSTEM_7ZA=true
REM     SZA_PATH=7za
REM Adjust the node.exe path and the wrapper path for your machine.
setlocal
set "NODE_EXE=%SANTI_NODE_EXE%"
if "%NODE_EXE%"=="" set "NODE_EXE=node"
"%NODE_EXE%" "%~dp07za_wrap.js" %*
exit /b %ERRORLEVEL%
