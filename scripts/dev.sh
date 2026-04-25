#!/usr/bin/env bash
# scripts/dev.sh — Start dev servers with reliable Ctrl+C cleanup on Windows.
# Uses taskkill /F /T to recursively kill process trees, since
# SIGINT propagation via concurrently is unreliable on Windows Git Bash.

set -u

# Source Git Bash profile to get Windows PATH entries (python, node, etc.)
if [ -f /etc/profile ]; then
    . /etc/profile
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR" || exit 1

SERVER_PID=""
WEB_PID=""

cleanup() {
    local exit_code=$?
    echo ""
    echo "[dev] Shutting down servers..."

    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[dev] Stopping server (PID $SERVER_PID)..."
        taskkill /F /T /PID "$SERVER_PID" 2>/dev/null || true
    fi

    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
        echo "[dev] Stopping web (PID $WEB_PID)..."
        taskkill /F /T /PID "$WEB_PID" 2>/dev/null || true
    fi

    # Defensive: kill any orphaned blender.exe left by hard termination
    taskkill /F /IM "blender.exe" 2>/dev/null || true

    echo "[dev] Done."
    exit "$exit_code"
}

trap cleanup SIGINT SIGTERM EXIT

echo "[dev] Starting development servers..."
echo "  Server: http://localhost:34567"
echo "  Web:    http://localhost:5173"
echo "Press Ctrl+C to stop both."

# Start Python backend
python -m uvicorn server.main:app --reload --host 127.0.0.1 --port 34567 &
SERVER_PID=$!

# Start Vite frontend
pnpm dev:web &
WEB_PID=$!

# Wait for either process to exit
wait
