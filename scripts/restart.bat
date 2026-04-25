@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [restart] Restarting Blender Batch Render server...

REM Kill existing (by port PID)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":34567 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 3 /nobreak >nul

REM Start new
start "Blender Batch Render" /MIN pythonw server/run_production.py

REM Wait for server to bind port
timeout /t 4 /nobreak >nul

netstat -an | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [restart] Server restarted.
    echo   WebUI: http://localhost:34567
) else (
    echo [restart] Server may have failed to start.
    if exist logs\error.log (
        echo   --- last 5 lines of logs\error.log ---
        powershell -Command "Get-Content logs\error.log -Tail 5"
    )
)
pause
