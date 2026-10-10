"""Paths and defaults."""

import os
from pathlib import Path

DEFAULT_DEPTH = 3
DEFAULT_MIN_NEW_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_TOP_NEW_FILES = 200
DEFAULT_PORT = 8765


def data_dir() -> Path:
    """Directory where the history database lives."""
    override = os.environ.get("DISK_TIMELINE_HOME")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "disk-timeline"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "disk-timeline"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "history.db"
