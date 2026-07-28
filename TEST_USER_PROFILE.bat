@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [MV.ai] .venv is missing. Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_user_profile.py

if errorlevel 1 (
    echo.
    echo [FAILED] User profile test failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] User profile test completed.
pause
endlocal
