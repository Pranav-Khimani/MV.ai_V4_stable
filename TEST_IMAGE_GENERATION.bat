@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo MV.ai image generation test
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_image_generation.py
if errorlevel 1 (
    echo.
    echo [FAILED] Image generation test failed.
    echo Run INSTALL_IMAGE_GENERATION.bat, then try again.
    pause
    exit /b 1
)

echo.
echo [PASSED] Image generation foundation is working.
pause
endlocal
