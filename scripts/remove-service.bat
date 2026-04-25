@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [remove] Removing firewall rule...
netsh advfirewall firewall delete rule name="Blender Batch Render" >nul 2>&1

if not exist "scripts\nssm.exe" (
    echo [remove] NSSM not found. Nothing to do.
    pause & exit /b 0
)

echo [remove] Stopping service 'BlenderBatchRender'...
net stop BlenderBatchRender 2>nul

echo [remove] Removing service...
scripts\nssm.exe remove BlenderBatchRender confirm

echo [remove] Done.
pause
