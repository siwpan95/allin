@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  全能宝 · Pro Edition
REM  - Auto GUI detect (Tkinter / PyQt / PySide)
REM  - Show real error on failure
REM  - Optional UPX
REM  - Multi-Python isolation
REM  - build_report.txt
REM ============================================================

REM ===== 可配置区域 =====
set PYTHON_EXE=python
set DIST=dist_all
set REPORT=build_report.txt
set USE_UPX=1
REM ======================

if not exist "%DIST%" mkdir "%DIST%"
del /q "%REPORT%" 2>nul

echo Smart Python Builder started at %DATE% %TIME% > "%REPORT%"
echo.

for %%F in (*.py) do (
    call :build "%%~F"
)

echo.
echo ============================================================
echo All builds completed. See %REPORT%
echo ============================================================
pause
exit /b

REM ------------------------------------------------------------
REM  Build one target
REM ------------------------------------------------------------
:build
set SCRIPT=%~1
set NAME=%~n1

echo.
echo ============================================================
echo Processing: %NAME%.py
echo ============================================================

REM ---------- 自动识别 GUI ----------
set AUTO_MODE=
findstr /i "tkinter" "%SCRIPT%" >nul && set AUTO_MODE=1
findstr /i "PyQt"    "%SCRIPT%" >nul && set AUTO_MODE=1
findstr /i "PySide"  "%SCRIPT%" >nul && set AUTO_MODE=1

if defined AUTO_MODE (
    echo ✅ Detected GUI framework → using -w
    set CONSOLE=-w
) else (
    echo Select mode:
    echo 1 - Console
    echo 2 - GUI
    set /p MODE=Mode [1/2]: 
    if "!MODE!"=="1" (
        set CONSOLE=-c
    ) else (
        set CONSOLE=-w
    )
)

REM ---------- UPX ----------
set UPX=
if "%USE_UPX%"=="1" (
    where upx >nul 2>&1
    if !errorlevel! equ 0 (
        set UPX=--upx-dir "%CD%"
    )
)

REM ---------- Icon ----------
set ICON=
if exist "%NAME%.ico" set ICON=--icon "%NAME%.ico"

REM ---------- Assets ----------
set DATA=
if exist "assets\%NAME%" set DATA=--add-data "assets\%NAME%;assets/%NAME%"

REM ---------- 构建命令 ----------
set CMD=^
%PYTHON_EXE% -m PyInstaller ^
-F %CONSOLE% ^
--clean ^
--name "%NAME%" ^
%ICON% %DATA% %UPX% ^
"%SCRIPT%"

echo.
echo Command:
echo %CMD%
echo.

REM ---------- 执行 ----------
%CMD%

if exist "dist\%NAME%.exe" (
    move /y "dist\%NAME%.exe" "%DIST%\" >nul
    echo ✅ SUCCESS: %NAME%.exe >> "%REPORT%"
    echo ✅ Built %NAME%.exe
) else (
    echo.
    echo ❌ FAILED TO BUILD %NAME%.py
    echo.
    echo ===== PyInstaller Output START =====
    %CMD%
    echo ===== PyInstaller Output END =====
    echo.
    echo ❌ FAILED: %NAME%.py >> "%REPORT%"
)

exit /b