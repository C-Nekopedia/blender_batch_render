# Blender Batch Render Tool

[**中文**](README.zh-CN.md) | **English**

A browser-based tool for batch-rendering Blender scenes remotely. Queues multiple frames into batches, restarts Blender when memory is high, and streams real-time progress to any device with a browser.

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/pc_preview.png">
    <img src="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/pc_preview.png" alt="Tasks view" width="720">
  </picture>
</div>

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/phone_preview.jpg">
    <img src="https://cdn.jsdelivr.net/gh/C-Nekopedia/blender_batch_render@master/ui_preview/phone_preview.jpg" alt="Phone preview" width="360">
  </picture>
</div>

## Features

- **Batch render** — renders frames in configurable batches, restarting Blender between batches to manage memory
- **Memory-aware** — monitors system memory and auto-restarts when a threshold is exceeded
- **Web UI** — Vue 3 frontend with terminal console, progress tracking, and system stats
- **Remote access** — connect from any device via IPv6 (direct) or Tailscale (fallback)
- **Background process** — runs as a lightweight background window, no installation needed

## Prerequisites

- Python 3.10+ (tested with 3.14)
- Blender 3.6+ (any installation — standalone, Steam, or system install)
- Node.js 18+ and pnpm (only needed for first-time frontend build)

## Quick Start

```bash
# One-click setup — installs Python deps, builds frontend, starts server
scripts\setup.bat
```

This opens the Web UI at `http://localhost:34567`.

Open the page on any device on your network:

- **Local**: `http://localhost:34567`
- **LAN**: `http://<your-lan-ip>:34567`
- **Remote (IPv6)**: `http://[your-ipv6-address]:34567`
- **Remote (Tailscale)**: `http://<tailscale-ip>:34567`

The frontend displays available remote addresses in the System Info panel.

### Manual setup

```bash
# Install Python dependencies
cd server
pip install -r requirements.txt
cd ..

# Build frontend (one-time)
cd apps/web
pnpm install && pnpm build
cd ../..

# Start the production server
python server/run_production.py
```

Or for development mode (hot-reload frontend):

```bash
# Terminal 1 — backend
python -m uvicorn server.main:app --reload --host 127.0.0.1 --port 34567

# Terminal 2 — frontend
cd apps/web && pnpm dev
```

## Server Management

```bat
scripts\setup.bat               # One-click: install deps, build frontend, start server
scripts\start.bat               # Start the server in a background window
scripts\stop.bat                # Stop the server
scripts\restart.bat             # Restart the server
scripts\build-frontend.bat      # Rebuild frontend after changes
```

The server runs as `python server/run_production.py` (dual-stack IPv4/IPv6 socket).

For development (hot-reload frontend), use one of:

```bash
scripts\dev.bat               # Windows cmd launcher
powershell scripts\dev.ps1    # PowerShell launcher
bash scripts/dev.sh           # Git Bash launcher
pnpm dev                      # Via pnpm (requires Node.js/pnpm)
```

## Architecture

```
Blender_Bacth_Render_Tool/
├── server/                    # Python FastAPI backend
│   ├── main.py                # HTTP/WS routes, settings, hardware detection
│   ├── engine.py              # Blender subprocess manager, batch render engine
│   └── run_production.py      # Dual-stack entry point (IPv4 + IPv6)
├── apps/web/                  # Vue 3 + Vite frontend
│   └── src/
│       ├── App.vue            # Main layout with sidebar navigation
│       ├── components/        # UI components
│       └── composables/       # Terminal & settings state
├── scripts/                   # Setup, control, and dev scripts
│   ├── setup.bat              # One-click install
│   ├── start.bat / stop.bat / restart.bat  # Server control
│   ├── build-frontend.bat     # Frontend rebuild
│   └── dev.bat / dev.ps1 / dev.sh  # Dev server launchers
└── docs/                      # Design specifications
```

The render engine runs Blender as a subprocess in background mode (`-b`), parses stdout for frame/sample progress, and pushes updates to all connected WebSocket clients. System memory is monitored per-batch and triggers a Blender restart if a configurable threshold is exceeded.

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws` | WebSocket | Real-time render progress and system stats push |
| `/render/start` | POST | Start rendering |
| `/render/stop` | POST | Stop rendering |
| `/api/settings` | GET/POST | Read/write render settings |
| `/api/system-stats` | GET | CPU/GPU/memory/VRAM usage |
| `/api/hardware-info` | GET | Hardware configuration (CPU, GPU, motherboard, RAM, OS) |
| `/api/network-info` | GET | Network addresses (IPv4, IPv6, Tailscale) |
| `/api/browse-file` | GET | Open native file dialog (local only) |

## FAQ

**No render log output?**
Check the WebSocket connection status. If disconnected, the server may be restarting; it will reconnect automatically within a few seconds.

**No file browse button on mobile/remote?**
The file dialog (local-only feature) is hidden when accessing remotely. Enter file paths manually.

**Server fails to start?**
Check `logs\error.log` for details. Common causes: incorrect Python path, missing Blender executable.

## License

MIT
