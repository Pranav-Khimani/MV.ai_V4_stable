@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo MV.ai Volume Fix Test
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv was not found.
    echo Copy this patch into the main MV.ai_V4 folder first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_volume_fix.py
if errorlevel 1 (
    echo.
    echo [FAILED] Volume fix checks failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Volume fix checks completed.
pause
endlocal
