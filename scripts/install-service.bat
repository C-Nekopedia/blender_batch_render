@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set ROOT=%CD%

REM Check NSSM exists
if not exist "scripts\nssm.exe" (
    echo [install] NSSM not found. Downloading...
    mkdir scripts 2>nul
    curl -L --connect-timeout 10 -o scripts\nssm.zip "https://nssm.cc/release/nssm-2.24.zip"
    if %errorlevel% neq 0 (
        echo [install] Download failed. Please manually download NSSM 2.24 from:
        echo   https://nssm.cc/download
        echo   Extract win64/nssm.exe to scripts/nssm.exe
        pause & exit /b 1
    )
    powershell -Command "Expand-Archive -Path scripts\nssm.zip -DestinationPath scripts\tmp -Force" >nul
    if exist scripts\tmp\nssm-2.24\win64\nssm.exe (
        move /y scripts\tmp\nssm-2.24\win64\nssm.exe scripts\nssm.exe >nul
    )
    rmdir /s /q scripts\tmp scripts\nssm.zip 2>nul
)

REM Remove existing service first (if any)
echo [install] Removing previous service instance...
net stop BlenderBatchRender 2>nul
scripts\nssm.exe remove BlenderBatchRender confirm 2>nul

REM Auto-detect real Python path (skip WindowsApps stub)
set PYTHON_PATH=
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_PATH (
        echo %%i|findstr /i "WindowsApps" >nul
        if errorlevel 1 set PYTHON_PATH=%%i
    )
)
if not defined PYTHON_PATH (
    echo [install] Python not found in PATH. Please install Python 3.10+.
    pause & exit /b 1
)

echo [install] Python: %PYTHON_PATH%
echo [install] Root:   %ROOT%

REM Ensure logs directory
mkdir logs 2>nul

REM Add Windows Firewall rule for remote access
echo [install] Adding firewall rule for port 34567...
netsh advfirewall firewall add rule name="Blender Batch Render" dir=in action=allow protocol=TCP localport=34567 >nul 2>&1

REM Register service
echo [install] Registering service 'BlenderBatchRender'...
scripts\nssm.exe install BlenderBatchRender "%PYTHON_PATH%" "server/run_production.py"
scripts\nssm.exe set BlenderBatchRender AppDirectory "%ROOT%"
scripts\nssm.exe set BlenderBatchRender AppStdout "%ROOT%\logs\access.log"
scripts\nssm.exe set BlenderBatchRender AppStderr "%ROOT%\logs\error.log"
scripts\nssm.exe set BlenderBatchRender AppRotateFiles 1
scripts\nssm.exe set BlenderBatchRender AppRotateOnline 1
scripts\nssm.exe set BlenderBatchRender AppRotateSeconds 86400
scripts\nssm.exe set BlenderBatchRender Start SERVICE_AUTO_START
REM 10-second boot delay so Python/network stack is ready
scripts\nssm.exe set BlenderBatchRender AppDelay 10000

REM Reload environment (ensure NSSM picks up PATH for python)
echo [install] Verifying Python...
"%PYTHON_PATH%" -c "import fastapi; print('  FastAPI:', fastapi.__version__)" 2>&1

REM Start service
echo [install] Starting service...
net start BlenderBatchRender
if %errorlevel% equ 2 (
    echo [install] Service already running.
) else if %errorlevel% neq 0 (
    echo [install] Failed to start service. Check logs\error.log.
    type logs\error.log 2>nul
    pause & exit /b 1
)

echo.
echo [install] Done!
echo   Local:   http://localhost:34567
echo   Network: http://%COMPUTERNAME%:34567
pause
