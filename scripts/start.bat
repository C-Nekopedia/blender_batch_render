@echo off
chcp 65001 >nul
cd /d "%~dp0.."

REM Check if already running (port 34567 listening)
netstat -an | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [start] Server already running.
    echo   WebUI: http://localhost:34567
    pause & exit /b 0
)

echo [start] Starting Blender Batch Render server...
start "Blender Batch Render" /MIN pythonw server/run_production.py

REM Wait for server to bind port
timeout /t 4 /nobreak >nul

netstat -an | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [start] Server started.
    echo   WebUI: http://localhost:34567
) else (
    echo [start] Server may have failed to start.
    if exist logs\error.log (
        echo   --- last 5 lines of logs\error.log ---
        powershell -Command "Get-Content logs\error.log -Tail 5"
    )
)
pause
