@echo off
chcp 65001 >nul
cd /d "%~dp0.."

tasklist /FI "WINDOWTITLE eq Blender Batch Render" 2>nul | findstr /i "pythonw" >nul
if %errorlevel% neq 0 (
    echo [stop] Server is not running.
    pause & exit /b 0
)

echo [stop] Stopping Blender Batch Render server...
taskkill /F /FI "WINDOWTITLE eq Blender Batch Render" >nul 2>&1
if %errorlevel% neq 0 (
    echo [stop] Failed to stop server.
    pause & exit /b 1
)
echo [stop] Server stopped.
pause
