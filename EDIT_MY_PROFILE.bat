@echo off
setlocal
cd /d "%~dp0"

if not exist "user_profile.json" (
    if exist "user_profile.example.json" (
        copy /Y "user_profile.example.json" "user_profile.json" >nul
    ) else (
        echo [MV.ai] user_profile.json is missing.
        pause
        exit /b 1
    )
)

where code >nul 2>&1
if %errorlevel%==0 (
    start "" code "user_profile.json"
) else (
    start "" notepad.exe "user_profile.json"
)

endlocal
