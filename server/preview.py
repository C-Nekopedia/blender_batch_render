"""Filesystem watcher for render output preview.
Uses watchdog (ReadDirectoryChangesW on Windows) to detect new/modified
image files in the Blender output directory.
"""
import os
import re
import time
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

IMAGE_EXTS = frozenset({'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.exr'})

_FRAME_NUM_RE = re.compile(r'(\d+)')


def _parse_frame(filename: str) -> int:
    """Extract frame number from filename — last group of digits before ext."""
    nums = _FRAME_NUM_RE.findall(Path(filename).stem)
    if nums:
        return int(nums[-1])
    return 0


class _DebouncedHandler(FileSystemEventHandler):
    """Fires callback after a quiet period with no filesystem events.
    Uses a polling loop instead of threading.Timer to avoid
    cancel/wake race conditions on Windows.
    """

    def __init__(self, callback, delay: float = 0.6):
        self._callback = callback
        self._delay = delay
        self._last_event = 0.0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _note_event(self):
        with self._lock:
            self._last_event = time.monotonic()

    def _poll(self):
        while self._running:
            with self._lock:
                since = time.monotonic() - self._last_event
            if self._last_event > 0 and since >= self._delay:
                self._last_event = 0.0
                try:
                    self._callback()
                except Exception:
                    pass
            time.sleep(0.15)

    def on_created(self, event):
        if not event.is_directory:
            self._note_event()

    def on_modified(self, event):
        if not event.is_directory:
            self._note_event()

    def on_moved(self, event):
        if not event.is_directory:
            self._note_event()

    def on_deleted(self, event):
        if not event.is_directory:
            self._note_event()

    def stop(self):
        self._running = False


class PreviewWatcher:
    """Watches a directory for image files, maintains a sorted list."""

    def __init__(self, directory: Path):
        self.directory = directory
        self._observer: Observer | None = None
        self._handler: _DebouncedHandler | None = None
        self._files: list[dict] = []
        self._lock = threading.Lock()

    @property
    def files(self) -> list[dict]:
        with self._lock:
            return list(self._files)

    def start(self, on_changed):
        """Start watching. `on_changed(files)` called from background thread."""
        self._scan()
        if on_changed:
            on_changed(self.files)
        self._handler = _DebouncedHandler(lambda: self._on_fs_event(on_changed))
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.directory), recursive=False)
        self._observer.start()

    def stop(self):
        if self._handler:
            self._handler.stop()
            self._handler = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None

    def _scan(self):
        with self._lock:
            self._files = scan_directory(self.directory)

    def _on_fs_event(self, on_changed):
        self._scan()
        if on_changed:
            on_changed(self.files)


def scan_directory(directory: Path) -> list[dict]:
    """Scan a directory for image files, return sorted list by frame number."""
    files = []
    try:
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            if Path(entry.name).suffix.lower() not in IMAGE_EXTS:
                continue
            st = entry.stat()
            files.append({
                'filename': entry.name,
                'size': st.st_size,
                'mtime': st.st_mtime,
                'frame': _parse_frame(entry.name),
            })
    except Exception:
        pass
    files.sort(key=lambda f: f['filename'])
    return files
