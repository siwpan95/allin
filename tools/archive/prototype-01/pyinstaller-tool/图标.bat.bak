@echo off
chcp 65001 >nul

REM ===============================
REM Python EXE Builder（稳定版）
REM ===============================

if "%~1"=="" (
    set /p PYFILE=Enter path to .py file: 
) else (
    set PYFILE=%~1
)

for %%F in ("%PYFILE%") do set NAME=%%~nF

echo.
echo ===============================
echo    Python EXE Builder
echo ===============================
echo Target : %PYFILE%
echo Output : dist\%NAME%.exe
echo.

REM ===== Icon =====
set ICON=
set /p ICOFILE=Icon file (.ico only, empty to skip): 

if not "%ICOFILE%"=="" (
    if /I NOT "%ICOFILE:~-4%"==".ico" (
        echo WARNING: Only .ico files are supported. Skipping icon.
        set ICON=
    ) else (
        set ICON=%ICOFILE%
    )
)

REM ===== Mode =====
echo.
echo Select mode:
echo [1] Console
echo [2] GUI
set /p MODE=Enter 1 or 2: 

if "%MODE%"=="1" (
    if defined ICON (
        pyinstaller -F -c -i "%ICON%" "%PYFILE%"
    ) else (
        pyinstaller -F -c "%PYFILE%"
    )
) else (
    if defined ICON (
        pyinstaller -F -w -i "%ICON%" "%PYFILE%"
    ) else (
        pyinstaller -F -w "%PYFILE%"
    )
)

REM ===== Cleanup =====
if exist build rmdir /s /q build
if exist "%NAME%.spec" del /f /q "%NAME%.spec"

REM ===== Result =====
if exist "dist\%NAME%.exe" (
    echo SUCCESS: dist\%NAME%.exe
    explorer dist
) else (
    echo FAILED
)

pause