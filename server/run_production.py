"""Production entry point for Blender Batch Render.
Starts uvicorn with dual-stack (IPv4 + IPv6) support on Windows.
Use this instead of direct uvicorn calls for production mode.

Important: uvicorn.Config must NOT set host/port when passing custom sockets,
otherwise uvicorn will try to bind a second listener and fail with EADDRINUSE.
"""
import logging
import socket
import sys
from pathlib import Path

# Add project root to sys.path so `import server.main` works
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import uvicorn

HOST = "::"
PORT = 34567
LOGS_DIR = Path(__file__).parent.parent / "logs"


def _setup_logging():
    """Configure uvicorn to write logs to files instead of console.
    This is needed when running via pythonw.exe (no console window).
    """
    LOGS_DIR.mkdir(exist_ok=True)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(levelname)s: %(message)s"},
            "access": {"format": "%(asctime)s %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"},
        },
        "handlers": {
            "default": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOGS_DIR / "error.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 2,
                "formatter": "default",
            },
            "access": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOGS_DIR / "access.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 2,
                "formatter": "access",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }


def _create_sockets() -> list[socket.socket]:
    """Create one IPv4 and one IPv6 socket, both bound to 34567."""
    sockets: list[socket.socket] = []

    # IPv4 socket (0.0.0.0)
    sock4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock4.bind(("0.0.0.0", PORT))
    sock4.set_inheritable(True)
    sockets.append(sock4)

    # IPv6 socket (::) with IPV6_V6ONLY=1 so both sockets coexist on the same port
    sock6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    sock6.bind((HOST, PORT))
    sock6.set_inheritable(True)
    sockets.append(sock6)

    return sockets


if __name__ == "__main__":
    sockets = _create_sockets()

    # File logging when running via pythonw.exe (no console);
    # console output (uvicorn default) when running via python.exe
    if sys.executable.endswith("pythonw.exe"):
        config = uvicorn.Config("server.main:app", log_level="info", log_config=_setup_logging())
    else:
        config = uvicorn.Config("server.main:app", log_level="info")

    server = uvicorn.Server(config)
    server.run(sockets=sockets)
