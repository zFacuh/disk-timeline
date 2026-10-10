"""Take and store snapshots."""

import time
from dataclasses import dataclass
from typing import Callable

from . import db, drives, scanner

FIRST_SCAN_LOOKBACK = 7 * 24 * 3600  # first full scan reports files from the last week


@dataclass
class SnapshotSummary:
    drive: str
    snapshot_id: int
    used: int
    total: int
    mode: str
    files_scanned: int | None = None
    new_files: int | None = None
    errors: int | None = None
    seconds: float | None = None


def take_snapshot(
    conn,
    drive: str,
    *,
    full: bool = True,
    depth: int = 3,
    min_new_size: int = 10 * 1024 * 1024,
    top_new: int = 200,
    exclude=(),
    progress: Callable[[int, str], None] | None = None,
    root: str | None = None,
    now: float | None = None,
) -> SnapshotSummary:
    """Record usage for ``drive``; with ``full`` also scan folders and new files.

    ``root`` overrides the directory scanned (used by tests).
    """
    now = time.time() if now is None else now
    usage = drives.get_usage(root or drive)
    usage.drive = drives.normalize_drive(drive)

    if not full:
        sid = db.insert_snapshot(conn, taken_at=now, usage=usage, mode="quick")
        conn.commit()
        return SnapshotSummary(usage.drive, sid, usage.used, usage.total, "quick")

    previous = db.last_full_snapshot(conn, usage.drive)
    new_since = previous["taken_at"] if previous else now - FIRST_SCAN_LOOKBACK

    result = scanner.scan(
        root or drives.drive_root(drive),
        depth=depth,
        new_since=new_since,
        min_new_size=min_new_size,
        top_new=top_new,
        exclude=exclude,
        progress=progress,
    )
    sid = db.insert_snapshot(
        conn,
        taken_at=now,
        usage=usage,
        mode="full",
        depth=depth,
        new_since=new_since,
        files_scanned=result.files_scanned,
        errors=result.errors,
        scan_seconds=result.seconds,
    )
    db.insert_folder_sizes(conn, sid, result.folders)
    db.insert_new_files(conn, sid, result.new_files)
    conn.commit()
    return SnapshotSummary(
        usage.drive, sid, usage.used, usage.total, "full",
        files_scanned=result.files_scanned,
        new_files=len(result.new_files),
        errors=result.errors,
        seconds=result.seconds,
    )
