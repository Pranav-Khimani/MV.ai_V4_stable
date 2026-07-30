@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" set_image_generation.py false
) else (
    py set_image_generation.py false
)

echo.
echo Image analysis is still enabled.
echo Close and reopen MV.ai now.
pause
endlocal
