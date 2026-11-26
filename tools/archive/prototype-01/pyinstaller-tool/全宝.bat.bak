@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  Batch Build All Python Files (Current Directory)
REM ============================================================

set DIST=dist
if not exist "%DIST%" mkdir "%DIST%"

echo.
echo Building all .py files in current folder...
echo.

for %%F in (*.py) do (
    call :build_app "%%~F"
)

echo.
echo All builds finished.
pause
exit /b

REM ------------------------------------------------------------
REM  Build Single App
REM ------------------------------------------------------------
:build_app
set SCRIPT=%~1
set NAME=%~n1

echo ============================================================
echo Building %NAME%
echo ============================================================

set CONSOLE=-w
set ICON=
set DATA=

if exist "%NAME%.ico" (
    set ICON=--icon "%NAME%.ico"
)

if exist "assets\%NAME%" (
    set DATA=--add-data "assets\%NAME%;assets/%NAME%"
)

pyinstaller -F %CONSOLE% %ICON% %DATA% ^
--clean ^
--name "%NAME%" ^
"%SCRIPT%"

if exist "dist\%NAME%.exe" (
    move /y "dist\%NAME%.exe" "%DIST%\" >nul
)

exit /b