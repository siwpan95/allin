@echo off
chcp 65001 >nul

REM 获取 py 文件路径
if "%~1"=="" (
    set /p PYFILE=Enter path to .py file: 
) else (
    set PYFILE=%~1
)

REM 提取真正的文件名（不带扩展名）
for %%F in ("%PYFILE%") do set NAME=%%~nF

echo.
echo ===============================
echo    Python EXE Builder
echo ===============================
echo Target: %PYFILE%
echo Output: dist\%NAME%.exe
echo.

echo Select mode:
echo [1] Console (with black window)
echo [2] GUI (no console window)
set /p MODE=Enter 1 or 2: 

if "%MODE%"=="1" (
    pyinstaller -F -c "%PYFILE%"
) else (
    pyinstaller -F -w "%PYFILE%"
)

echo.
if exist "dist\%NAME%.exe" (
    echo SUCCESS: dist\%NAME%.exe
    explorer dist
) else (
    echo FAILED: See errors above.
)

pause