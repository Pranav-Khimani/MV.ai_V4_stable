@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing. Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_debug_fixes.py
if errorlevel 1 (
    echo.
    echo [FAILED] Debug-fix test failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Offline profile test completed.
pause
endlocal
