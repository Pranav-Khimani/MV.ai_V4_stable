@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" TEST_IMAGE_PIPELINE_FIX.py
if errorlevel 1 (
    echo.
    echo [FAILED] Image pipeline checks failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Image pipeline checks completed.
pause
endlocal
