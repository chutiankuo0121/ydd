from __future__ import annotations

import sys
import threading


_LOG_LOCK = threading.Lock()


def configure_stdout() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass


def log(message: str) -> None:
    with _LOG_LOCK:
        print(message, flush=True)
