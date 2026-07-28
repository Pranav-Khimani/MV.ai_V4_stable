@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo        MV.ai V4 - Install and Verify
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo.
        echo [FAILED] Could not create the virtual environment.
        echo Install Python 3.12 and enable the Python launcher.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Existing virtual environment found.
)

echo [2/4] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_failed

echo [3/4] Installing MV.ai dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo.
    echo [ACTION REQUIRED] A safe .env file was created.
    echo Open .env and add your NEW Gemini key and email credentials.
    echo Do not share that file.
    echo.
)

echo [4/4] Checking the patched project...
".venv\Scripts\python.exe" check_mvai.py
if errorlevel 1 (
    echo.
    echo [FAILED] The project check found a problem.
    pause
    exit /b 1
)

echo.
echo [PASSED] MV.ai V4 is installed and patched.
echo Start it with RUN_MVAI.bat after filling in .env.
pause
exit /b 0

:install_failed
echo.
echo [FAILED] A dependency could not be installed.
echo Copy the full error shown above and send it for debugging.
pause
exit /b 1
