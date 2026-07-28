@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m py_compile ui\window.py voice\voice_assistant.py
if errorlevel 1 goto :failed

".venv\Scripts\python.exe" test_add_stuff_voice_ui_fix.py
if errorlevel 1 goto :failed

echo.
echo [PASSED] Popup and voice recovery checks completed.
pause
exit /b 0

:failed
echo.
echo [FAILED] One or more checks failed.
pause
exit /b 1
