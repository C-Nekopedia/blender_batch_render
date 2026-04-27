@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set ROOT=%CD%

REM /q flag suppresses the final pause (used when called from setup.bat)
set QUIET=0
if /i "%1"=="/q" set QUIET=1

REM Remove old dist if it exists, then rebuild fresh
if exist "apps\web\dist" (
    echo [build] Removing old frontend build...
    rmdir /s /q "apps\web\dist"
)

echo [build] Building frontend...
echo.

REM Try pnpm first
where pnpm >nul 2>&1
if %errorlevel% equ 0 goto :do_build

REM pnpm not found — try installing it via npm
echo [build] pnpm not found. Checking for Node.js...
where npm >nul 2>&1
if %errorlevel% equ 0 (
    echo [build] Installing pnpm via npm...
    npm install -g pnpm
    if %errorlevel% neq 0 (
        echo [build] npm install -g pnpm failed.
        goto :err_no_node
    )
    goto :do_build
)

REM npm not found — try installing Node.js via winget
echo [build] Node.js not found. Trying winget to install...
where winget >nul 2>&1
if %errorlevel% equ 0 (
    echo [build] Installing Node.js LTS via winget...
    winget install OpenJS.NodeJS.LTS --accept-package-agreements --silent
    if %errorlevel% neq 0 (
        echo [build] winget install failed.
        goto :err_no_node
    )
    REM Refresh PATH to pick up new Node.js
    call refreshenv 2>nul || (
        for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "PATH=%%b;%PATH%"
    )
    where npm >nul 2>&1
    if %errorlevel% neq 0 (
        REM Try common Node.js install path directly
        if exist "C:\Program Files\nodejs\npm.cmd" (
            set "PATH=C:\Program Files\nodejs;%PATH%"
        ) else if exist "%ProgramFiles%\nodejs\npm.cmd" (
            set "PATH=%ProgramFiles%\nodejs;%PATH%"
        ) else if exist "%LocalAppData%\fnm\nodejs\current\npm.cmd" (
            set "PATH=%LocalAppData%\fnm\nodejs\current;%PATH%"
        ) else (
            echo [build] Node.js installed but npm not found in PATH.
            echo [build] Please restart your terminal and re-run this script.
            goto :err_no_node
        )
    )
    npm install -g pnpm
    if %errorlevel% neq 0 (
        goto :err_no_node
    )
    goto :do_build
)

:err_no_node
echo.
echo ================================================================
echo  ERROR: Node.js 18+ and pnpm are required to build the frontend.
echo.
echo  Please install Node.js manually from:
echo    https://nodejs.org/  (LTS version recommended)
echo.
echo  Then run this script again, or run:
echo    npm install -g pnpm
echo    cd apps\web
echo    pnpm install ^&^& pnpm build
echo ================================================================
pause & exit /b 1

:do_build
cd apps\web

echo [build] Installing dependencies...
call pnpm install
if %errorlevel% neq 0 (
    echo [build] pnpm install failed.
    pause & exit /b 1
)

echo [build] Building...
call pnpm build
if %errorlevel% neq 0 (
    echo [build] pnpm build failed.
    pause & exit /b 1
)

cd "%ROOT%"
echo [build] Done. Frontend built to apps\web\dist\
if %QUIET% equ 0 pause
