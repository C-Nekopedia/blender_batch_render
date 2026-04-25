@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [restart] Restarting Blender Batch Render server...

REM Kill existing (by port PID)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":34567 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 3 /nobreak >nul

echo   WebUI: http://localhost:34567
echo   Close this window or press Ctrl+C to stop the server.
echo.

python server/run_production.py
pause
