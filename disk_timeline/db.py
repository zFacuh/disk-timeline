"""SQLite storage for snapshots."""

import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at      REAL    NOT NULL,          -- unix timestamp
    drive         TEXT    NOT NULL,
    total         INTEGER NOT NULL,
    used          INTEGER NOT NULL,
    free          INTEGER NOT NULL,
    mode          TEXT    NOT NULL,          -- 'quick' | 'full'
    depth         INTEGER,
    new_since     REAL,                      -- new files are newer than this
    files_scanned INTEGER,
    errors        INTEGER,
    scan_seconds  REAL
);
CREATE INDEX IF NOT EXISTS ix_snapshots_drive_time ON snapshots(drive, taken_at);

CREATE TABLE IF NOT EXISTS folder_sizes (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path        TEXT    NOT NULL,
    depth       INTEGER NOT NULL,
    size        INTEGER NOT NULL,
    file_count  INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, path)
);

CREATE TABLE IF NOT EXISTS new_files (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path        TEXT    NOT NULL,
    size        INTEGER NOT NULL,
    created     REAL,
    modified    REAL
);
CREATE INDEX IF NOT EXISTS ix_new_files_snapshot ON new_files(snapshot_id);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def insert_snapshot(conn, *, taken_at, usage, mode, depth=None, new_since=None,
                    files_scanned=None, errors=None, scan_seconds=None) -> int:
    cur = conn.execute(
        """INSERT INTO snapshots (taken_at, drive, total, used, free, mode, depth,
                                  new_since, files_scanned, errors, scan_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (taken_at, usage.drive, usage.total, usage.used, usage.free, mode, depth,
         new_since, files_scanned, errors, scan_seconds),
    )
    return cur.lastrowid


def insert_folder_sizes(conn, snapshot_id, folders) -> None:
    conn.executemany(
        "INSERT INTO folder_sizes (snapshot_id, path, depth, size, file_count) VALUES (?, ?, ?, ?, ?)",
        ((snapshot_id, f.path, f.depth, f.size, f.file_count) for f in folders),
    )


def insert_new_files(conn, snapshot_id, files) -> None:
    conn.executemany(
        "INSERT INTO new_files (snapshot_id, path, size, created, modified) VALUES (?, ?, ?, ?, ?)",
        ((snapshot_id, f.path, f.size, f.created, f.modified) for f in files),
    )


def last_full_snapshot(conn, drive, before=None):
    sql = "SELECT * FROM snapshots WHERE drive = ? AND mode = 'full'"
    args = [drive]
    if before is not None:
        sql += " AND taken_at < ?"
        args.append(before)
    sql += " ORDER BY taken_at DESC LIMIT 1"
    return conn.execute(sql, args).fetchone()


def drives(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT drive FROM snapshots ORDER BY drive")]
