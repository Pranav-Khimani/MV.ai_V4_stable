@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv was not found in this MV.ai folder.
    echo Copy this patch into your working MV.ai folder first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_email_intent.py
if errorlevel 1 (
    echo.
    echo [FAILED] Email-content tests failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Email-content fix is installed.
pause
endlocal
