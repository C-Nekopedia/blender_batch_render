@echo off
chcp 65001 >nul
cd /d "%~dp0.."

REM Check if port 34567 is in use
netstat -ano | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo [stop] Server is not running.
    pause & exit /b 0
)

echo [stop] Stopping Blender Batch Render server...

REM Kill the specific process holding port 34567
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":34567 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

netstat -ano | findstr ":34567 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo [stop] Server stopped.
) else (
    echo [stop] Failed to stop server.
    pause & exit /b 1
)
pause
