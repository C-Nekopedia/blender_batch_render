@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set ROOT=%CD%

echo ========================================
echo  Blender Batch Render - One-Click Setup
echo ========================================
echo.

REM Step 1: Install Python dependencies
echo [1/4] Installing Python dependencies...
pip install -r server\requirements.txt
if %errorlevel% neq 0 (
    echo FAILED. Please ensure Python 3.10+ is installed and in PATH.
    pause & exit /b 1
)
echo.

REM Step 2: Build frontend (auto-installs Node.js/pnpm if missing)
echo [2/4] Building frontend...
call scripts\build-frontend.bat /q
if %errorlevel% neq 0 (
    echo FAILED. See error messages above.
    pause & exit /b 1
)
echo.

REM Step 3: Add firewall rule for remote access
echo [3/4] Adding firewall rule...
netsh advfirewall firewall add rule name="Blender Batch Render" dir=in action=allow protocol=TCP localport=34567 >nul 2>&1
if %errorlevel% neq 0 (
    echo [3/4] WARNING: Could not add firewall rule.
    echo   Remote access may not work from other devices.
    echo   To fix, run as Administrator or manually add:
    echo     netsh advfirewall firewall add rule name="Blender Batch Render" dir=in action=allow protocol=TCP localport=34567
) else (
    echo [3/4] Firewall rule added.
)
echo.

REM Step 4: Start server
echo [4/4] Starting Blender Batch Render server...
start "Blender Batch Render" /MIN pythonw server/run_production.py
timeout /t 3 /nobreak >nul

REM Open browser
start http://localhost:34567

echo.
echo ========================================
echo  Installation complete!
echo.
echo  Local access:
echo    http://localhost:34567
echo.
echo  Remote access:
echo    Open the WebUI on your home machine
echo    to see available remote addresses.
echo.
echo  NOTE: The server runs in a background window.
echo  Use scripts\stop.bat to stop it.
echo ========================================
pause
