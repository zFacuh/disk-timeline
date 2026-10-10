"""Discover local drives and read their usage."""

import os
import shutil
from dataclasses import dataclass

DRIVE_FIXED = 3


@dataclass
class DriveUsage:
    drive: str  # "C" on Windows, mount point elsewhere
    root: str   # "C:\\"
    total: int
    used: int
    free: int


def normalize_drive(name: str) -> str:
    """Accept "C", "c:", "C:\\" and return "C" (Windows). Other OSes keep the path."""
    if os.name == "nt":
        return name.strip().rstrip("\\/").rstrip(":").upper()
    return name


def drive_root(drive: str) -> str:
    if os.name == "nt":
        return f"{normalize_drive(drive)}:\\"
    return drive


def list_fixed_drives() -> list[str]:
    """Fixed (non-removable, non-network) drives."""
    if os.name != "nt":
        return ["/"]
    import ctypes

    kernel32 = ctypes.windll.kernel32
    mask = kernel32.GetLogicalDrives()
    drives = []
    for i in range(26):
        if mask & (1 << i):
            letter = chr(ord("A") + i)
            if kernel32.GetDriveTypeW(f"{letter}:\\") == DRIVE_FIXED:
                drives.append(letter)
    return drives


def is_drive_name(name: str) -> bool:
    return os.name == "nt" and len(normalize_drive(name)) == 1


def get_usage(drive: str) -> DriveUsage:
    """Usage of a drive ("C") or of the volume containing a directory."""
    root = drive_root(drive) if is_drive_name(drive) or os.name != "nt" else drive
    usage = shutil.disk_usage(root)
    return DriveUsage(
        drive=normalize_drive(drive),
        root=root,
        total=usage.total,
        used=usage.used,
        free=usage.free,
    )
