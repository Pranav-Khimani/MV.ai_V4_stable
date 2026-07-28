@echo off
setlocal
cd /d "%~dp0"

echo.
echo [MV.ai] Testing ADD Stuff! and image-analysis support...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_image_support.py
if errorlevel 1 (
    echo.
    echo [FAILED] Image support checks did not pass.
    pause
    exit /b 1
)

echo.
echo [PASSED] MV.ai Vision Input v0.1 is installed correctly.
pause
endlocal
