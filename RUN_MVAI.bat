@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [MV.ai] Virtual environment is missing.
    echo Run this command inside the project folder:
    echo py -3.12 -m venv .venv
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo [MV.ai] Missing .env file.
    echo Copy .env.example and rename the copy to .env.
    echo Then add your private API credentials.
    echo.
    pause
    exit /b 1
)

echo [MV.ai] Starting...
".venv\Scripts\python.exe" app.py

if errorlevel 1 (
    echo.
    echo [MV.ai] MV.ai stopped because of an error.
    pause
)

endlocal