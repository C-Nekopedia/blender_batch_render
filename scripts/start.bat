@echo off
chcp 65001 >nul
echo [start] Starting Blender Batch Render service...
net start BlenderBatchRender 2>nul
if %errorlevel% equ 2 (
    echo [start] Service already running.
) else (
    echo [start] Service started.
    echo   WebUI: http://localhost:34567
)
pause
