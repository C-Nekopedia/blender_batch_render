"""
Simplified Blender batch render engine with threaded real-time progress.
GUI-ready: no console I/O; structured callbacks can be driven from a background thread.
"""

import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BLENDER = Path(r"D:\000\Blender 3.6\blender.exe")
DEFAULT_BATCH_SIZE = 50
DEFAULT_MEMORY_THRESHOLD = 90
DEFAULT_MEMORY_POLL = 1.0
DEFAULT_RESTART_DELAY = 5
DEFAULT_FRAME_TIMEOUT = 300
DEFAULT_RENDER_TIMEOUT = 86400  # 24h safety net

BATCH_OK = 0
BATCH_ERROR = -1

# Regex patterns for Blender output parsing
_FRAME_RE = re.compile(r"(?:Fra:|Frame:)\s*(\d+)", re.I)
_MEM_RE = re.compile(r"(?:Mem:|Memory:)\s*([0-9.]+[A-Za-z]*)", re.I)
_SAMPLE_RE = re.compile(r"Sample\s+(\d+)(?:\s*/\s*(\d+))?", re.I)
_SAVED_RE = re.compile(r"(?:Saved:|Saved to:)\s*['\"](.+?)['\"]", re.I)
_TIME_RE = re.compile(r"(?:Time:|Render Time:)\s*([0-9:.]+)", re.I)
_ZH_FRAME_RE = re.compile(r"帧号:\s*(\d+)")
_RENDER_SAMPLE_RE = re.compile(r"Rendering\s+(\d+)\s*/\s*(\d+)\s+samples", re.I)

# Blender error/warning patterns for capture and forwarding
_ERROR_RE = re.compile(r"^\s*(?:Error\b|Traceback|FATAL|SystemError)", re.I)
_GPU_ERROR_RE = re.compile(r"(?:out of (?:GPU )?memory|CUDA error|OpenCL error|Device .* not available)", re.I)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    blender: Path
    blend: Path
    output: str | None
    start: int
    end: int
    batch: int = DEFAULT_BATCH_SIZE
    memory_threshold: float = DEFAULT_MEMORY_THRESHOLD
    memory_poll_seconds: float = DEFAULT_MEMORY_POLL
    restart_delay: float = DEFAULT_RESTART_DELAY
    frame_timeout: float = DEFAULT_FRAME_TIMEOUT
    render_timeout: float = DEFAULT_RENDER_TIMEOUT


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

@dataclass
class _BatchState:
    """Internal state, written only by the main parsing thread."""
    frame: int
    mem: str = "?"
    sample: tuple[int, int] | None = None
    time: float | None = None
    restart_pending: bool = False
    restart_note: str = ""

    def mark_saved(self) -> int:
        self.sample = (1, 1)
        return self.frame + 1


@dataclass
class _FrameProgress:
    """Shared between main thread and heartbeat thread.
       GIL makes individual field reads/writes atomic for our purposes."""
    active: bool = False
    frame: int = 0
    sample_curr: int = 0
    sample_total: int | None = None
    mem: str = "?"
    frame_start: float = 0.0


# ---------------------------------------------------------------------------
# Callback interface
# ---------------------------------------------------------------------------

class RenderCallbacks:
    """Override to receive render events.

    NOTE: on_frame_progress may be called from a background thread.
          GUI implementations must dispatch to the UI thread if needed.
    """
    _stopped: bool = False

    def on_frame_progress(self, frame: int, sample_curr: int,
                          sample_total: int | None, elapsed: float,
                          mem: str): ...
    def on_frame_saved(self, frame: int, path: str, elapsed: float): ...
    def on_batch_start(self, start: int, end: int): ...
    def on_memory_restart(self, next_frame: int, note: str): ...
    def on_error(self, msg: str): ...
    def on_complete(self): ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def read_memory_usage() -> tuple[float | None, float | None]:
    """Query Windows system memory usage (percent)."""
    if sys.platform != "win32":
        return None, None
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = _MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None, None
        phys = float(st.dwMemoryLoad)
        commit = None
        if st.ullTotalPageFile:
            commit = (1 - st.ullAvailPageFile / st.ullTotalPageFile) * 100
        return phys, commit
    except Exception:
        return None, None


def _memory_note(phys: float | None, commit: float | None) -> str:
    p = f"{phys:.1f}%" if phys is not None else "?"
    c = f"{commit:.1f}%" if commit is not None else "?"
    return f"sys={p} commit={c}"


def _parse_seconds(text: str) -> float | None:
    try:
        parts = [float(x) for x in text.split(":")]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3:]
    return h * 3600 + m * 60 + s


def _build_cmd(config: Config, start: int, end: int) -> list[str]:
    cmd = [str(config.blender), "-b", str(config.blend)]
    if config.output:
        cmd.extend(["-o", config.output])
    cmd.extend(["-s", str(start), "-e", str(end), "-a"])
    return cmd


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            import signal
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass


class MemoryMonitor:
    def __init__(self, threshold: float, poll_seconds: float):
        self.threshold = threshold
        self.poll_seconds = poll_seconds
        self._last_check = 0.0

    def check(self) -> tuple[bool, str]:
        now = time.monotonic()
        if now - self._last_check < self.poll_seconds:
            return False, ""
        self._last_check = now
        phys, commit = read_memory_usage()
        over = (phys is not None and phys >= self.threshold) or \
               (commit is not None and commit >= self.threshold)
        if over:
            return True, _memory_note(phys, commit)
        return False, ""


# ---------------------------------------------------------------------------
# Windows Job Object — kill Blender automatically if Python exits
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.windll.kernel32

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x0100

    _JOB_HANDLE = _kernel32.CreateJobObjectW(None, None)
    if _JOB_HANDLE:
        buf = ctypes.create_string_buffer(64)
        ctypes.memset(buf, 0, 64)
        flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
        ctypes.memmove(
            ctypes.byref(buf, 16),
            ctypes.byref(wintypes.DWORD(flags)),
            4,
        )
        _kernel32.SetInformationJobObject(
            _JOB_HANDLE, 2, buf, 64,  # JobObjectBasicLimitInformation
        )
else:
    _JOB_HANDLE = None


def _assign_to_job(proc: subprocess.Popen) -> None:
    """Assign a subprocess to the kill-on-close job object.
    No-op outside Windows or if the job wasn't created."""
    if _JOB_HANDLE is None:
        return
    try:
        ctypes.windll.kernel32.AssignProcessToJobObject(_JOB_HANDLE, proc._handle)
    except Exception:
        pass  # child may already belong to another job — best effort


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RenderEngine:
    """Batch-renders Blender frames with memory-aware auto-restart and
       real-time progress via a background heartbeat thread."""

    def __init__(self, config: Config, callbacks: RenderCallbacks | None = None):
        self.config = config
        self.cb = callbacks or RenderCallbacks()
        self._process: subprocess.Popen | None = None
        self._stop_requested = False
        self._stop_heartbeat = threading.Event()

    # ---- public API ----

    def stop(self):
        """Request a graceful stop after the current frame completes."""
        self._stop_requested = True
        if self._process and self._process.poll() is None:
            _stop_process(self._process)

    def render(self):
        """Main render loop. Blocks until all batches complete or stopped."""
        cfg = self.config
        current = cfg.start
        render_start = time.monotonic()

        while current <= cfg.end and not self._stop_requested:
            # Overall timeout safety net
            if time.monotonic() - render_start > cfg.render_timeout:
                self.cb.on_error(f"Render timed out after {cfg.render_timeout}s")
                return

            end = min(current + cfg.batch - 1, cfg.end)
            result = self._run_batch(current, end)

            if result == BATCH_OK:
                current = end + 1
            elif result == BATCH_ERROR:
                return
            else:
                # result = next frame to resume from (memory restart)
                time.sleep(cfg.restart_delay)
                current = result

        if not self._stop_requested:
            self.cb.on_complete()

    # ---- internal ----

    def _heartbeat_loop(self, progress: _FrameProgress) -> None:
        """Background thread: fires on_frame_progress while a frame is active.
        Throttled to at most 2 updates/second to avoid flooding the WS.
        Also detects if Blender died unexpectedly (crash / sleep / OOM kill).
        """
        last_send = 0.0
        while not self._stop_heartbeat.is_set():
            # Check if Blender died while render was supposed to be running
            if not self._stop_requested and self._process is not None:
                code = self._process.poll()
                if code is not None and progress.active:
                    self.cb.on_error(f"Blender process died unexpectedly (exit code {code})")
            if progress.active and not self._stop_requested:
                now = time.time()
                if now - last_send >= 0.5:
                    last_send = now
                    elapsed = now - progress.frame_start
                    self.cb.on_frame_progress(
                        frame=progress.frame,
                        sample_curr=progress.sample_curr,
                        sample_total=progress.sample_total,
                        elapsed=elapsed,
                        mem=progress.mem,
                    )
            self._stop_heartbeat.wait(0.2)

    def _activate_frame(self, progress: _FrameProgress, frame: int) -> None:
        """Start the timer and mark a new frame as active."""
        progress.frame = frame
        progress.sample_curr = 0
        progress.sample_total = None
        progress.frame_start = time.time()
        progress.active = True

    def _run_batch(self, start: int, end: int) -> int:
        """Run a single batch. Returns BATCH_OK, BATCH_ERROR, or next frame on restart."""
        self.cb.on_batch_start(start, end)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        flags = 0
        if sys.platform == "win32":
            flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) |
                     getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                     getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))

        proc = subprocess.Popen(
            _build_cmd(self.config, start, end),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=flags, env=env, bufsize=1,
        )
        _assign_to_job(proc)
        self._process = proc

        state = _BatchState(frame=0)
        monitor = MemoryMonitor(self.config.memory_threshold,
                                self.config.memory_poll_seconds)

        # Quick crash check — poll with 3s timeout instead of fixed 0.3s sleep
        poll_start = time.monotonic()
        while proc.poll() is None:
            if time.monotonic() - poll_start > 3:
                break  # process is still running, proceed
            if self._stop_requested:
                _stop_process(proc)
                self._process = None
                return BATCH_ERROR
            time.sleep(0.1)
        if proc.poll() is not None:
            self.cb.on_error(f"Blender exited immediately (code {proc.poll()})")
            self._process = None
            return BATCH_ERROR

        # Start heartbeat thread for this batch
        self._stop_heartbeat.clear()
        progress = _FrameProgress()
        heartbeat = threading.Thread(target=self._heartbeat_loop, args=(progress,), daemon=True)
        heartbeat.start()

        if proc.stdout is None:
            self.cb.on_error("Blender process has no stdout pipe")
            return BATCH_ERROR

        try:
            for raw_line in proc.stdout:
                if self._stop_requested:
                    break

                line = raw_line.strip()
                if not line:
                    continue

                # -- memory check (schedule restart after current frame) --
                if not state.restart_pending:
                    should, note = monitor.check()
                    if should:
                        state.restart_pending = True
                        state.restart_note = note

                # -- new frame detected (elif to avoid matching both EN and ZH patterns) --
                if m := _FRAME_RE.search(line):
                    new_frame = int(m.group(1))
                    if new_frame != state.frame:
                        state.frame = new_frame
                        self._activate_frame(progress, state.frame)
                elif m := _ZH_FRAME_RE.search(line):
                    new_frame = int(m.group(1))
                    if new_frame != state.frame:
                        state.frame = new_frame
                        self._activate_frame(progress, state.frame)

                # -- memory string --
                if m := _MEM_RE.search(line):
                    state.mem = m.group(1)
                    progress.mem = state.mem

                # -- sample progress --
                if m := _SAMPLE_RE.search(line):
                    if not progress.active:
                        self._activate_frame(progress, state.frame)
                    progress.sample_curr = int(m.group(1))
                    if m.group(2):
                        progress.sample_total = int(m.group(2))

                # -- Rendering X / Y samples (Chinese locale Blender 3.6) --
                if m := _RENDER_SAMPLE_RE.search(line):
                    if not progress.active:
                        self._activate_frame(progress, state.frame)
                    progress.sample_curr = int(m.group(1))
                    progress.sample_total = int(m.group(2))

                # -- frame saved --
                if m := _SAVED_RE.search(line):
                    path = m.group(1)
                    next_frame = state.mark_saved()
                    elapsed = state.time or (time.time() - progress.frame_start
                                             if progress.active else 0.0)
                    state.time = None
                    progress.active = False
                    self.cb.on_frame_saved(state.frame, path, elapsed)

                    if state.restart_pending:
                        _stop_process(proc)
                        self.cb.on_memory_restart(next_frame, state.restart_note)
                        return next_frame

                # -- render time --
                if m := _TIME_RE.search(line):
                    secs = _parse_seconds(m.group(1))
                    if secs is not None:
                        state.time = secs

                # -- error capture (forward to frontend for debugging) --
                if _ERROR_RE.search(line):
                    self.cb.on_error(line)
                elif _GPU_ERROR_RE.search(line):
                    self.cb.on_error(f"[GPU] {line}")

            try:
                code = proc.wait(timeout=self.config.frame_timeout)
            except subprocess.TimeoutExpired:
                _stop_process(proc)
                code = proc.wait(timeout=5)
                self.cb.on_error("Blender process timed out")
                return BATCH_ERROR
            if code != 0:
                self.cb.on_error(f"Blender exited with code {code} (batch {start}-{end})")
                return BATCH_ERROR
            return BATCH_OK

        except KeyboardInterrupt:
            _stop_process(proc)
            return BATCH_ERROR

        finally:
            self._stop_heartbeat.set()
            heartbeat.join(timeout=3)
            self._process = None
