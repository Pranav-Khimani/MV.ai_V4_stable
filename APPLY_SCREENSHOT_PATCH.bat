@echo off
setlocal
cd /d "%~dp0"

echo Applying MV.AI screenshot patch...

if not exist "ai\planner.py" (
    echo ERROR: Put this patch folder inside the MV.ai_V4 project folder first.
    pause
    exit /b 1
)

if exist "tools\screenshot_tool.py" del /q "tools\screenshot_tool.py"

copy /y "PATCH_FILES\ai\planner.py" "ai\planner.py" >nul
if errorlevel 1 goto :failed

if not exist "tools\system" mkdir "tools\system"
copy /y "PATCH_FILES\tools\system\screenshot_tool.py" "tools\system\screenshot_tool.py" >nul
if errorlevel 1 goto :failed

if exist "tools\__pycache__" rmdir /s /q "tools\__pycache__"
if exist "tools\system\__pycache__" rmdir /s /q "tools\system\__pycache__"
if exist "ai\__pycache__" rmdir /s /q "ai\__pycache__"

echo.
echo Screenshot patch applied successfully.
echo Restart MV.AI and say: take a screenshot
pause
exit /b 0

:failed
echo.
echo ERROR: The patch could not be copied.
pause
exit /b 1
