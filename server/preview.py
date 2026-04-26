"""Filesystem watcher for render output preview.
Uses watchdog (ReadDirectoryChangesW on Windows) to detect new/modified
image files in the Blender output directory.
"""
import os
import re
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
    """Fires callback after a quiet period with no filesystem events."""

    def __init__(self, callback, delay: float = 0.6):
        self._callback = callback
        self._delay = delay
        self._timer: threading.Timer | None = None

    def _reset_timer(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._delay, self._callback)
        self._timer.start()

    def on_created(self, event):
        if not event.is_directory:
            self._reset_timer()

    def on_modified(self, event):
        if not event.is_directory:
            self._reset_timer()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None


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
    files.sort(key=lambda f: f['frame'])
    return files
