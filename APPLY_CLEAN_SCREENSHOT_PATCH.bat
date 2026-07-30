@echo off
setlocal
cd /d "%~dp0"

echo Applying clean screenshot patch...

if exist "tools\screenshot_tool.py" del /f /q "tools\screenshot_tool.py"
if exist "tools\__pycache__\screenshot_tool*.pyc" del /f /q "tools\__pycache__\screenshot_tool*.pyc"
if exist "tools\system\__pycache__\screenshot_tool*.pyc" del /f /q "tools\system\__pycache__\screenshot_tool*.pyc"

copy /y "PATCH_FILES\tools\system\screenshot_tool.py" "tools\system\screenshot_tool.py" >nul
copy /y "PATCH_FILES\ui\window.py" "ui\window.py" >nul

if errorlevel 1 (
    echo.
    echo Patch failed. Make sure this BAT and PATCH_FILES are inside MV.ai_V4.
    pause
    exit /b 1
)

echo.
echo Patch applied successfully.
echo Restart MV.AI completely, then say: take a screenshot
pause
