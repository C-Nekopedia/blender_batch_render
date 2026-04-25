@echo off
chcp 65001 >nul
cd /d "%~dp0.."

REM Check if already running
tasklist /FI "WINDOWTITLE eq Blender Batch Render" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    echo [start] Server already running.
    echo   WebUI: http://localhost:34567
    pause & exit /b 0
)

echo [start] Starting Blender Batch Render server...
start "Blender Batch Render" /MIN python server/run_production.py

REM Wait briefly then check
timeout /t 3 /nobreak >nul
tasklist /FI "WINDOWTITLE eq Blender Batch Render" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    echo [start] Server started.
    echo   WebUI: http://localhost:34567
) else (
    echo [start] Server may have failed to start. Check logs\error.log.
)
pause
