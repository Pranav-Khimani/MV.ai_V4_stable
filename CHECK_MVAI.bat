@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv\Scripts\python.exe was not found.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" check_mvai.py
set "exit_code=%errorlevel%"

if not "%exit_code%"=="0" (
    echo.
    echo [FAILED] MV.ai checks did not pass.
) else (
    echo.
    echo [PASSED] You can now run RUN_MVAI.bat.
)

pause
exit /b %exit_code%
