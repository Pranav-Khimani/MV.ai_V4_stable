@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [FAILED] .venv is missing.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" TEST_IMAGE_COMPAT_FIX.py
if errorlevel 1 (
  echo.
  echo [FAILED] Image compatibility test failed.
  pause
  exit /b 1
)
echo.
echo [PASSED] Image generation compatibility patch is installed.
pause
endlocal
