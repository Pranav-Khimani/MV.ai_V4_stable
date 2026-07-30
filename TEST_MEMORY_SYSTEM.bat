@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing. Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_memory_system.py
if errorlevel 1 (
    echo.
    echo [FAILED] Memory System checks failed.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_tool_schema.py
if errorlevel 1 (
    echo.
    echo [FAILED] Central tool-schema checks failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] MV.ai Memory System v0.1 is ready.
pause
endlocal
