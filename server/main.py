"""FastAPI backend for Blender Batch Render Tool.
Bridges the synchronous render engine to the browser via WebSocket.
"""

import os
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')  # enable EXR codec in OpenCV

import asyncio
import atexit
import json
import logging
import socket
import subprocess
import sys
import time

from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto
from pathlib import Path

import psutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

# Ensure server/ directory is on the import path when running via uvicorn from root
sys.path.insert(0, str(Path(__file__).parent))

from engine import (
    Config,
    RenderEngine,
    RenderCallbacks,
    read_memory_usage,
    DEFAULT_BLENDER,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MEMORY_THRESHOLD,
    DEFAULT_RESTART_DELAY,
)
from preview import PreviewWatcher, scan_directory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform-specific imports (avoid runtime imports in route handlers)
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import tkinter as tk
    from tkinter import filedialog

    # Register a console control handler to kill orphaned Blender when the
    # user closes the console window (CTRL_CLOSE_EVENT).  Windows gives us
    # ~5 s before forcibly terminating the process.
    _kernel32 = ctypes.windll.kernel32
    _console_handler_t = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

    @_console_handler_t
    def _on_console_close(ctrl_type: int) -> bool:
        """Handle CTRL_CLOSE_EVENT — kill orphan Blender before exit."""
        if ctrl_type == 2:
            _kill_orphan_blender()
            return True  # signal handled; Windows terminates us afterwards
        return False

    _kernel32.SetConsoleCtrlHandler(_on_console_close, 1)


# ---------------------------------------------------------------------------
# Render state machine
# ---------------------------------------------------------------------------

class RenderState(Enum):
    IDLE = auto()
    RUNNING = auto()
    STOPPING = auto()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Blender Batch Render")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global state (single-user local tool — module globals are acceptable)
# ---------------------------------------------------------------------------

_engine: RenderEngine | None = None
_connections: list[WebSocket] = []
_render_state = RenderState.IDLE
_executor = ThreadPoolExecutor(max_workers=1)
_render_lock = asyncio.Lock()

# Preview state
_output_dir: Path | None = None
_preview_watcher: PreviewWatcher | None = None

# Last-saved settings (in-memory, persists across page refreshes)
_settings_store: dict = {}

# Settings file path for disk persistence (survives server restarts)
SETTINGS_FILE = Path(__file__).parent / "settings.json"


# ---------------------------------------------------------------------------
# Preview helpers
# ---------------------------------------------------------------------------

def _ensure_preview_watcher(file_path: str, loop: asyncio.AbstractEventLoop):
    """Initialize preview watcher on first frame-saved event."""
    global _output_dir, _preview_watcher
    if _output_dir is not None:
        return
    _output_dir = Path(file_path).parent
    _preview_watcher = PreviewWatcher(_output_dir)
    _preview_watcher.start(lambda files: asyncio.run_coroutine_threadsafe(
        _broadcast_preview(files), loop
    ))


async def _broadcast_preview(files: list[dict]):
    """Broadcast preview file list to all connected WebSocket clients."""
    payload = {
        "type": "preview_update",
        "data": {
            "output_dir": str(_output_dir) if _output_dir else None,
            "files": files,
        },
        "timestamp": time.time(),
    }
    for ws in list(_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            pass


def _stop_watcher():
    """Stop the watchdog observer but keep _output_dir for post-render browsing."""
    global _preview_watcher
    if _preview_watcher:
        _preview_watcher.stop()
        _preview_watcher = None


def _reset_preview():
    """Full reset — stop watcher and clear output directory."""
    global _output_dir, _preview_watcher
    if _preview_watcher:
        _preview_watcher.stop()
        _preview_watcher = None
    _output_dir = None


# ---------------------------------------------------------------------------
# Shutdown / cleanup
# ---------------------------------------------------------------------------

def _kill_orphan_blender():
    """Defensive: kill any orphaned blender.exe processes."""
    if sys.platform != "win32":
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "blender.exe"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


atexit.register(_kill_orphan_blender)


@app.on_event("shutdown")
async def _shutdown_handler():
    """Clean up engine + thread pool on graceful server shutdown."""
    global _engine, _executor

    if _engine is not None:
        _engine.stop()
        _engine = None

    _executor.shutdown(wait=False)
    _reset_preview()
    _kill_orphan_blender()


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

class RenderConfigSchema(BaseModel):
    blender: str
    blend: str
    start: int
    end: int
    output: str | None = None
    batch: int
    memory_threshold: float
    memory_poll_seconds: float = 1.0
    restart_delay: float
    rapid_crash_limit: int = 3
    rapid_crash_window: float = 60.0


# ---------------------------------------------------------------------------
# WebSocket callback bridge
# ---------------------------------------------------------------------------

class WebSocketCallbacks(RenderCallbacks):
    """Bridge RenderCallbacks to WebSocket JSON messages.
    Broadcasts to all connected WebSocket clients.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._stopped = False

    async def _do_send(self, payload: dict) -> None:
        """Broadcast payload to all connected WebSocket clients."""
        if self._stopped and payload.get("type") not in ("complete", "error"):
            return
        # Iterate over a snapshot so removals during iteration are safe
        clients = list(_connections)
        if payload.get("type") in ("batch_start", "frame_progress", "frame_saved", "complete"):
            logger.info("WS send %s to %d client(s)", payload.get("type"), len(clients))
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    def _send(self, event_type: str, **data):
        payload = {"type": event_type, "data": data, "timestamp": time.time()}
        try:
            asyncio.run_coroutine_threadsafe(
                self._do_send(payload), self._loop
            )
        except RuntimeError:
            logger.warning("WebSocket send failed for %s (loop unavailable)", event_type)

    def on_frame_progress(self, frame: int, sample_curr: int,
                          sample_total: int | None, elapsed: float,
                          mem: str):
        self._send("frame_progress", frame=frame, sample_curr=sample_curr,
                    sample_total=sample_total, elapsed=round(elapsed, 1), mem=mem)

    def on_frame_saved(self, frame: int, path: str, elapsed: float):
        _ensure_preview_watcher(path, self._loop)
        self._send("frame_saved", frame=frame, path=path,
                    elapsed=round(elapsed, 1))

    def on_batch_start(self, start: int, end: int):
        self._send("batch_start", start=start, end=end)

    def on_memory_restart(self, next_frame: int, note: str):
        self._send("memory_restart", next_frame=next_frame, note=note)

    def on_error(self, msg: str):
        self._send("error", message=msg)

    def on_complete(self):
        self._send("complete")


# ---------------------------------------------------------------------------
# System stats helpers
# ---------------------------------------------------------------------------

def _get_cpu_usage() -> float | None:
    """Query overall CPU usage via psutil (instant, no subprocess)."""
    try:
        return psutil.cpu_percent(interval=0)
    except Exception:
        return None


def _get_gpu_usage() -> float | None:
    """Query GPU utilization.
    Priority: nvidia-smi (NVIDIA) → Windows Performance Counters (all vendors).
    """
    # 1) Try nvidia-smi for NVIDIA GPUs
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        val = result.stdout.strip().rstrip(" %")
        if val:
            return float(val)
    except Exception:
        pass

    # 2) Fallback: Windows Performance Counters via PowerShell
    #    Works with NVIDIA, AMD, Intel on Windows 10 1709+.
    try:
        result = subprocess.run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "try { "
            "$c = (Get-Counter '\\GPU Engine Utilization(*)\\Utilization Percentage' -ErrorAction Stop).CounterSamples; "
            "if ($c) { ($c | Where-Object { $_.InstanceName -match 'engtype_3D' } | "
            "Measure-Object -Maximum CookedValue).Maximum } else { '' } "
            "} catch { '' }",
        ], capture_output=True, text=True, timeout=5)
        val = result.stdout.strip()
        if val:
            return float(val)
    except Exception:
        pass

    return None


def _get_vram_usage() -> tuple[float | None, float | None]:
    """Query VRAM usage (used_mb, total_mb) via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        parts = result.stdout.strip().split(", ")
        if len(parts) == 2:
            used = float(parts[0].rstrip(" MiB"))
            total = float(parts[1].rstrip(" MiB"))
            return used, total
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Network info detection (remote access guidance)
# ---------------------------------------------------------------------------

def _detect_network_info() -> dict:
    """Detect available network addresses for remote access guides.
    Called once at module load; result cached via _NETWORK_CACHE.
    Returns all global IPv6 addresses with their interface names,
    since virtual adapters (Mihomo, VPNs, etc.) can produce unusable addresses."""
    info = {
        "ipv4": None,       # LAN IPv4 (192.168.x.x / 10.x.x.x)
        "ipv6": [],         # list of {address, name} — all usable IPv6
        "tailscale": None,  # Tailscale IPv4 (100.x.x.x)
    }

    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET6:
                    ip = addr.address.split("%")[0]
                    if not ip.startswith("fe80") and ip != "::1":
                        info["ipv6"].append({"address": ip, "name": iface})
                elif addr.family == socket.AF_INET:
                    ip = addr.address
                    iface_lower = iface.lower()
                    if (
                        ip.startswith("100.")
                        and ("tailscale" in iface_lower or "wg" in iface_lower)
                    ):
                        info["tailscale"] = ip
                    elif not ip.startswith("127.") and ip != "0.0.0.0":
                        info["ipv4"] = ip
    except Exception:
        pass

    return info

_NETWORK_CACHE = _detect_network_info()


# ---------------------------------------------------------------------------
# Hardware info detection (static, cached once at startup)
# ---------------------------------------------------------------------------

def _get_hardware_info() -> dict:
    """Query hardware info via subprocess calls. Cached at module load."""
    info = {
        "cpu": None,
        "gpu": None,
        "motherboard": None,
        "ram_gb": None,
        "os": None,
    }

    try:
        r = subprocess.run(
            ["wmic", "cpu", "get", "name", "/format:csv"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and "Name" not in l]
        if lines:
            parts = lines[0].split(",", 1)
            info["cpu"] = parts[-1].strip() if len(parts) > 1 else lines[0].strip()
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        gpu = r.stdout.strip()
        if gpu:
            info["gpu"] = gpu
    except Exception:
        pass

    if info["gpu"] is None:
        try:
            r = subprocess.run(
                ["wmic", "path", "win32_videocontroller", "get", "name", "/format:csv"],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and "Name" not in l and "name" not in l]
            info["gpu"] = lines[0] if lines else None
        except Exception:
            pass

    try:
        r = subprocess.run(
            ["wmic", "baseboard", "get", "product,Manufacturer", "/format:csv"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and all(x not in l for x in ("Manufacturer", "Node"))]
        if lines:
            parts = [p.strip() for p in lines[0].split(",") if p.strip()]
            info["motherboard"] = " ".join(parts[1:]) if len(parts) > 1 else parts[0]
    except Exception:
        pass

    try:
        total = psutil.virtual_memory().total
        info["ram_gb"] = round(total / (1024**3))
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["wmic", "os", "get", "Caption", "/format:csv"],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and "Caption" not in l and "caption" not in l]
        if lines:
            parts = lines[0].split(",", 1)
            info["os"] = parts[-1].strip() if len(parts) > 1 else lines[0].strip()
    except Exception:
        pass

    # VRAM total
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        vram = r.stdout.strip().rstrip(" MiB")
        if vram:
            info["vram_gb"] = round(float(vram) / 1024, 1)
    except Exception:
        pass

    return info

_HARDWARE_CACHE = _get_hardware_info()


# ---------------------------------------------------------------------------
# Render lifecycle helper
# ---------------------------------------------------------------------------

def _render_wrapper(engine: RenderEngine, loop: asyncio.AbstractEventLoop):
    """Run engine.render() then clean up _engine when done."""
    try:
        engine.render()
    except Exception as e:
        logger.exception("Render engine crashed: %s", e)
        try:
            engine.cb.on_error(f"Render engine crashed: {e}")
        except Exception:
            pass
    finally:
        engine.cb._stopped = True
        asyncio.run_coroutine_threadsafe(_finish_render(), loop)


async def _finish_render():
    """Transition state back to IDLE after render completes/stops."""
    global _engine, _render_state
    async with _render_lock:
        _engine = None
        _render_state = RenderState.IDLE
    _stop_watcher()


# ---------------------------------------------------------------------------
# System stats WebSocket pusher
# ---------------------------------------------------------------------------

def _collect_stats() -> tuple:
    """Synchronous: collect CPU, GPU, memory readings (runs in thread pool)."""
    return _get_cpu_usage(), _get_gpu_usage(), read_memory_usage()[0]


async def _stats_pusher(ws: WebSocket) -> None:
    """Background task: push CPU/GPU/memory stats over WS every 2 seconds.
    Blocking system calls are offloaded to the thread pool via run_in_executor
    so they don't block the event loop (and delay render progress delivery).
    """
    loop = asyncio.get_event_loop()
    try:
        while True:
            cpu, gpu, mem = await loop.run_in_executor(None, _collect_stats)
            try:
                await ws.send_json({
                    "type": "system_stats",
                    "data": {
                        "cpu": round(cpu, 1) if cpu is not None else None,
                        "gpu": round(gpu, 1) if gpu is not None else None,
                        "memory": round(mem, 1) if mem is not None else None,
                    },
                    "timestamp": time.time(),
                })
            except Exception:
                return  # WS disconnected
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/render/start")
async def start_render(cfg: RenderConfigSchema):
    global _engine, _render_state

    _reset_preview()  # clear previous render's output dir

    async with _render_lock:
        if _render_state != RenderState.IDLE:
            raise HTTPException(400, "Render already in progress")
        if not _connections:
            raise HTTPException(400, "No WebSocket connection")

        config = Config(
            blender=Path(cfg.blender),
            blend=Path(cfg.blend),
            output=cfg.output,
            start=cfg.start,
            end=cfg.end,
            batch=cfg.batch,
            memory_threshold=cfg.memory_threshold,
            memory_poll_seconds=cfg.memory_poll_seconds,
            restart_delay=cfg.restart_delay,
            rapid_crash_limit=cfg.rapid_crash_limit,
            rapid_crash_window=cfg.rapid_crash_window,
        )

        loop = asyncio.get_running_loop()
        callbacks = WebSocketCallbacks(loop)
        engine = RenderEngine(config, callbacks)
        _engine = engine
        _render_state = RenderState.RUNNING

    # Offload to thread pool; wrapper cleans up _engine when done
    loop.run_in_executor(_executor, _render_wrapper, engine, loop)

    return {"status": "started"}


@app.post("/render/stop")
async def stop_render():
    global _engine, _render_state

    async with _render_lock:
        if _render_state != RenderState.RUNNING:
            raise HTTPException(400, "No render running")
        _render_state = RenderState.STOPPING
        if _engine is not None:
            _engine.stop()
            _engine = None

    return {"status": "stopped"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    global _engine, _render_state, _connections

    await websocket.accept()

    async with _render_lock:
        _connections.append(websocket)

    stats_task = asyncio.create_task(_stats_pusher(websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "preview_init":
                    if _preview_watcher:
                        files = _preview_watcher.files
                    elif _output_dir is not None:
                        files = scan_directory(_output_dir)
                    else:
                        files = []
                    await websocket.send_json({
                        "type": "preview_update",
                        "data": {
                            "output_dir": str(_output_dir) if _output_dir else None,
                            "files": files,
                        },
                        "timestamp": time.time(),
                    })
            except (json.JSONDecodeError, RuntimeError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        stats_task.cancel()
        try:
            await stats_task
        except asyncio.CancelledError:
            pass
        async with _render_lock:
            _connections.remove(websocket)


@app.get("/api/browse-file")
async def browse_file(filter: str = ""):
    """Open native Windows file dialog (tkinter with DPI fix).

    filter format: comma-separated extensions, e.g. ".blend,.exe"
    """
    # Enable DPI awareness so the dialog is not blurry
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        filetypes = []
        if filter:
            exts = [e.strip() for e in filter.split(",") if e.strip()]
            if exts:
                desc = " ".join(exts)
                pattern = " ".join(f"*{e}" for e in exts)
                filetypes.append((f"Files ({desc})", pattern))
        filetypes.append(("All files", "*.*"))

        path = filedialog.askopenfilename(filetypes=filetypes, parent=root)
        return {"path": path if path else None}
    finally:
        root.destroy()


@app.get("/api/system-stats")
async def system_stats():
    """Return current CPU, GPU, memory, and VRAM usage."""
    cpu = _get_cpu_usage()
    gpu = _get_gpu_usage()
    mem_phys, _ = read_memory_usage()
    vram_used, vram_total = _get_vram_usage()
    return {
        "cpu": round(cpu, 1) if cpu is not None else None,
        "gpu": round(gpu, 1) if gpu is not None else None,
        "memory": round(mem_phys, 1) if mem_phys is not None else None,
        "vram_used": round(vram_used, 0) if vram_used is not None else None,
        "vram_total": round(vram_total, 0) if vram_total is not None else None,
    }


@app.get("/api/network-info")
async def network_info():
    """Return detected network addresses for remote access guidance."""
    return _NETWORK_CACHE


@app.get("/api/hardware-info")
async def hardware_info():
    """Return static hardware info (CPU, GPU, motherboard, RAM, OS)."""
    return _HARDWARE_CACHE


@app.get("/api/preview-file")
async def serve_preview_file(path: str, thumb: bool = False):
    """Serve an image file from the render output directory.
    Set ?thumb=true to get a small WebP thumbnail (320px wide).
    """
    global _output_dir
    if _output_dir is None:
        raise HTTPException(400, "No active render output directory")

    requested = (_output_dir / path).resolve()
    try:
        requested.relative_to(_output_dir.resolve())
    except ValueError:
        raise HTTPException(403, "Path traversal detected")

    if not requested.is_file():
        raise HTTPException(404, "File not found")

    ext = requested.suffix.lower()

    if thumb or ext == '.exr':
        # Thumbnails & EXR (which browsers can't display) are always converted
        cache_dir = _output_dir / ".thumb_cache"
        suffix = "_lg" if (not thumb and ext == '.exr') else ""
        cache_path = cache_dir / f"{requested.stem}{suffix}.webp"
        size = 1920 if (not thumb and ext == '.exr') else 320
        if not cache_path.exists() or cache_path.stat().st_mtime < requested.stat().st_mtime:
            cache_dir.mkdir(exist_ok=True)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _make_thumbnail, requested, cache_path, size)
        return FileResponse(cache_path, media_type='image/webp')

    media = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }
    if ext not in media:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    return FileResponse(requested, media_type=media[ext])


def _make_thumbnail(src: Path, dst: Path, size: int = 320):
    """Generate a WebP thumbnail from an image file. EXR files are tone-mapped."""
    ext = src.suffix.lower()
    if ext == '.exr':
        _convert_exr(src, dst, size)
    else:
        from PIL import Image
        img = Image.open(src)
        img.thumbnail((size, size), Image.LANCZOS)
        img.save(str(dst), 'webp', quality=75)


def _convert_exr(src: Path, dst: Path, size: int):
    """Read EXR via OpenCV, apply Reinhard tone mapping, save as WebP."""
    import cv2
    import numpy as np
    from PIL import Image

    data = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if data is None:
        raise RuntimeError(f"Failed to read EXR: {src}")
    rgb = data[:, :, ::-1]  # BGR -> RGB
    # ACES Filmic tone mapping (Narkowicz 2015 fit)
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    rgb = (rgb * (a * rgb + b)) / (rgb * (c * rgb + d) + e)
    rgb = np.clip(rgb, 0.0, 1.0)
    # Linear -> sRGB gamma
    mask = rgb <= 0.0031308
    rgb_lo = 12.92 * rgb
    rgb_hi = 1.055 * (rgb ** (1.0 / 2.4)) - 0.055
    rgb = np.where(mask, rgb_lo, rgb_hi)
    rgb = np.clip(rgb, 0.0, 1.0) * 255.0
    img = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    img.thumbnail((size, size), Image.LANCZOS)
    img.save(str(dst), 'webp', quality=75)


class SettingsSchema(BaseModel):
    """User-facing settings saved/loaded across page refreshes."""
    blender: str
    blend: str
    start: int
    end: int
    batch: int
    memory_threshold: float
    restart_delay: float


# ---------------------------------------------------------------------------
# Settings validation & persistence
# ---------------------------------------------------------------------------

def _validate_settings(s: SettingsSchema) -> list[str]:
    errors: list[str] = []
    if not s.blender or not Path(s.blender).exists():
        errors.append("Blender 路径不存在")
    if s.blend and not Path(s.blend).exists():
        errors.append("工程文件路径不存在")
    if not isinstance(s.start, int) or s.start < 0:
        errors.append("起始帧必须为 >= 0 的整数")
    if not isinstance(s.end, int) or s.end < 0:
        errors.append("结束帧必须为 >= 0 的整数")
    if s.start > s.end:
        errors.append("起始帧不能大于结束帧")
    if s.batch < 1:
        errors.append("批次大小不能小于 1")
    if s.memory_threshold < 1 or s.memory_threshold > 99:
        errors.append("内存阈值应在 1-99 之间")
    if s.restart_delay < 1:
        errors.append("重启延迟不能小于 1 秒")
    return errors


def _load_settings_file() -> dict:
    """Load saved settings from disk, or return empty dict if no file."""
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load settings file: %s", e)
    return {}


# Load persisted settings on startup
_settings_store.update(_load_settings_file())


@app.get("/api/settings")
async def get_settings():
    """Return last-saved settings, or engine defaults if none saved."""
    if _settings_store:
        return _settings_store
    return {
        "blender": str(DEFAULT_BLENDER),
        "blend": "",
        "start": 1,
        "end": 250,
        "batch": DEFAULT_BATCH_SIZE,
        "memory_threshold": DEFAULT_MEMORY_THRESHOLD,
        "restart_delay": DEFAULT_RESTART_DELAY,
    }


@app.post("/api/settings")
async def save_settings(s: SettingsSchema):
    """Validate and persist settings to disk."""
    errors = _validate_settings(s)
    if errors:
        raise HTTPException(400, detail={"message": "设置校验失败", "errors": errors})

    _settings_store.clear()
    _settings_store.update(s.model_dump())

    # Persist to disk so settings survive server restart
    try:
        SETTINGS_FILE.write_text(
            json.dumps(s.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error("Failed to write settings file: %s", e)
        raise HTTPException(500, "设置保存到文件失败")

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Production static file serving
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).parent.parent / "apps" / "web" / "dist"

if FRONTEND_DIST.is_dir():
    class _SPAFallback(StaticFiles):
        """StaticFiles with SPA fallback: serve index.html for unknown paths."""

        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except (StarletteHTTPException,) as ex:
                if ex.status_code == 404:
                    assert self.directory is not None
                    return FileResponse(Path(self.directory) / "index.html")
                raise

    app.mount("/", _SPAFallback(directory=str(FRONTEND_DIST), html=True), name="frontend")
    logger.info("Frontend static files mounted from %s", FRONTEND_DIST)
