@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run this file from your MV.ai project root after applying the patch.
    echo The .venv folder was not found.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "from voice.voice_assistant import VoiceAssistant; v=VoiceAssistant(lambda _command: None); v.speak_with_windows('Voice system test completed successfully.'); print('[PASSED] Voice test completed.')"

if errorlevel 1 (
    echo.
    echo [FAILED] The Windows speech test failed.
    pause
    exit /b 1
)

pause
endlocal
