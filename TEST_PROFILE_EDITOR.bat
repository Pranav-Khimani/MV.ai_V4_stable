@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

set QT_QPA_PLATFORM=offscreen
".venv\Scripts\python.exe" test_profile_editor.py
if errorlevel 1 (
    echo.
    echo [FAILED] Profile editor tests failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] MV.ai Profile Editor is ready.
pause
endlocal
