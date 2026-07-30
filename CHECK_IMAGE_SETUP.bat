@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FAILED] .venv is missing.
    echo Run INSTALL_MVAI.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" CHECK_IMAGE_SETUP.py
set RESULT=%ERRORLEVEL%
echo.
pause
exit /b %RESULT%
