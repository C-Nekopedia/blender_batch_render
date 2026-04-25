@echo off
chcp 65001 >nul
echo [stop] Stopping Blender Batch Render service...
net stop BlenderBatchRender 2>nul
if %errorlevel% equ 2 (
    echo [stop] Service is not running.
) else (
    echo [stop] Service stopped.
)
pause
