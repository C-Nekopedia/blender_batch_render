@echo off
chcp 65001 >nul
cd /d "%~dp0.."

REM Check if already running (port 34567)
netstat -an | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [start] Server already running.
    echo   WebUI: http://localhost:34567
    pause & exit /b 0
)

echo [start] Starting Blender Batch Render server...
echo   WebUI: http://localhost:34567
echo   Close this window or press Ctrl+C to stop the server.
echo.

python server/run_production.py
pause
