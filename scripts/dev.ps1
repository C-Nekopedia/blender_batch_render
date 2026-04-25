# scripts/dev.ps1 — Start dev servers with reliable Ctrl+C cleanup on Windows.
# Uses taskkill /F /T to recursively kill process trees.

$rootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $rootDir

Write-Host "[dev] Starting development servers..."
Write-Host "  Server: http://localhost:34567"
Write-Host "  Web:    http://localhost:5173"
Write-Host "Press Ctrl+C to stop both."

try {
    $server = Start-Process -NoNewWindow -PassThru python @(
        "-m", "uvicorn", "server.main:app", "--reload", "--host", "127.0.0.1", "--port", "34567"
    )
    Start-Sleep -Milliseconds 1000
    $web = Start-Process -NoNewWindow -PassThru cmd @("/c", "pnpm dev:web")

    # Wait for either process to exit
    while (-not $server.HasExited -and -not $web.HasExited) {
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host "`n[dev] Shutting down servers..."
    if ($server -and -not $server.HasExited) {
        taskkill /F /T /PID $server.Id 2>$null
    }
    if ($web -and -not $web.HasExited) {
        taskkill /F /T /PID $web.Id 2>$null
    }
    # Defensive: kill any orphaned blender.exe
    taskkill /F /IM "blender.exe" 2>$null
    Write-Host "[dev] Done."
}
