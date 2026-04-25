@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo [dev] Starting development servers...
echo   Server: http://localhost:34567
echo   Web:    http://localhost:5173
echo Press Ctrl+C to stop both.

start "blender-server" /B python -m uvicorn server.main:app --reload --host 127.0.0.1 --port 34567
start "blender-web" /B pnpm dev:web

echo.
echo Press Ctrl+C to stop servers...
pause >nul

echo [dev] Shutting down...
taskkill /F /T /FI "WINDOWTITLE eq blender-server" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq blender-web" >nul 2>&1
taskkill /F /IM "blender.exe" >nul 2>&1
echo [dev] Done.
