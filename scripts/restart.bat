@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [restart] Restarting Blender Batch Render server...

REM Kill existing
taskkill /F /FI "WINDOWTITLE eq Blender Batch Render" >nul 2>&1

REM Wait for sockets to release
timeout /t 3 /nobreak >nul

REM Start new
start "Blender Batch Render" /MIN pythonw server/run_production.py

REM Wait briefly then check
timeout /t 3 /nobreak >nul
tasklist /FI "WINDOWTITLE eq Blender Batch Render" 2>nul | findstr /i "pythonw" >nul
if %errorlevel% equ 0 (
    echo [restart] Server restarted.
    echo   WebUI: http://localhost:34567
) else (
    echo [restart] Server may have failed to start. Check logs\error.log.
    type logs\error.log 2>nul
)
pause
