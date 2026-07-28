@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo MV.ai central tool schema test
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_tool_schema.py
if errorlevel 1 (
    echo.
    echo [FAILED] Central tool schema test failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Central tool schema is working.
pause
endlocal
