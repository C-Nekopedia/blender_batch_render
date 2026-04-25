@echo off
chcp 65001 >nul
echo [restart] Restarting Blender Batch Render service...
net stop BlenderBatchRender 2>nul
REM Wait for sockets to fully release (TIME_WAIT)
timeout /t 3 /nobreak >nul
net start BlenderBatchRender 2>nul
if %errorlevel% equ 2 (
    echo [restart] Failed to restart.
) else (
    echo [restart] Service restarted.
    echo   WebUI: http://localhost:34567
)
pause
