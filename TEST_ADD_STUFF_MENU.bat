@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Apply this patch inside your working MV.ai_V4 folder first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_add_stuff_menu.py
if errorlevel 1 (
    echo.
    echo [FAILED] ADD Stuff menu test failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] ADD Stuff menu patch is ready.
pause
endlocal
