@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] Missing .venv. Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" test_image_feature_flag.py
if errorlevel 1 (
    echo.
    echo [FAILED] Image feature-flag checks failed.
    pause
    exit /b 1
)

echo.
echo [PASSED] Image generation is safely disabled.
pause
endlocal
