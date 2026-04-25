@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [build] Installing frontend dependencies...
cd apps\web
call pnpm install
if %errorlevel% neq 0 (
    echo [build] pnpm install failed. Is Node.js 18+ and pnpm installed?
    pause & exit /b 1
)

echo [build] Building frontend...
call pnpm build
if %errorlevel% neq 0 (
    echo [build] pnpm build failed.
    pause & exit /b 1
)

echo [build] Done. Frontend built to apps\web\dist\
pause
