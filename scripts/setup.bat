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

REM Step 2: Build frontend
echo [2/4] Building frontend...
cd apps\web
call pnpm install
if %errorlevel% neq 0 (
    echo FAILED. Please ensure Node.js 18+ and pnpm are installed.
    cd ..\.. & pause & exit /b 1
)
call pnpm build
if %errorlevel% neq 0 (
    echo FAILED. Frontend build error.
    cd ..\.. & pause & exit /b 1
)
cd ..\..
echo.

REM Step 3: Register and start service
echo [3/4] Registering Windows service...
call scripts\install-service.bat
if %errorlevel% neq 0 (
    echo FAILED. See error messages above.
    pause & exit /b 1
)
echo.

REM Step 4: Open browser
echo [4/4] Opening WebUI...
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
echo ========================================
pause
