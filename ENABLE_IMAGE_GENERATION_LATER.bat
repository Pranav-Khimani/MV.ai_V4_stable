@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" set_image_generation.py true
) else (
    py set_image_generation.py true
)

echo.
echo Restart MV.ai. A paid/eligible Gemini API project is still required.
pause
endlocal
