@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo MV.ai image generation dependency update
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade "google-genai>=2.12.1,<3"
if errorlevel 1 (
    echo.
    echo [FAILED] Could not update google-genai.
    pause
    exit /b 1
)

echo.
call TEST_IMAGE_GENERATION.bat
endlocal
