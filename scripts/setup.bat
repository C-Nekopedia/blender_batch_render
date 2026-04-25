@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set ROOT=%CD%

echo ========================================
echo  Blender Batch Render - One-Click Setup
echo ========================================
echo.

REM Step 1: Install Python dependencies
echo [1/3] Installing Python dependencies...
pip install -r server\requirements.txt
if %errorlevel% neq 0 (
    echo FAILED. Please ensure Python 3.10+ is installed and in PATH.
    pause & exit /b 1
)
echo.

REM Step 2: Build frontend (auto-installs Node.js/pnpm if missing)
echo [2/3] Building frontend...
call scripts\build-frontend.bat /q
if %errorlevel% neq 0 (
    echo FAILED. See error messages above.
    pause & exit /b 1
)
echo.

REM Step 3: Start server
echo [3/3] Starting Blender Batch Render server...
start "Blender Batch Render" /MIN python server/run_production.py
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
