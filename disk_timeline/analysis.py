"""Queries over the snapshot history."""

from datetime import datetime


def usage_series(conn, drive: str) -> list[dict]:
    """Every snapshot of a drive, oldest first, with the change since the previous one."""
    rows = conn.execute(
        "SELECT id, taken_at, total, used, free, mode FROM snapshots WHERE drive = ? ORDER BY taken_at",
        (drive,),
    ).fetchall()
    out, prev = [], None
    for r in rows:
        item = dict(r)
        item["delta"] = None if prev is None else r["used"] - prev
        prev = r["used"]
        out.append(item)
    return out


def daily_series(conn, drive: str) -> list[dict]:
    """Last snapshot of each (local) day, with the change versus the previous day."""
    by_day: dict[str, dict] = {}
    for item in usage_series(conn, drive):
        day = datetime.fromtimestamp(item["taken_at"]).strftime("%Y-%m-%d")
        by_day[day] = item  # rows are ordered, so the last one of the day wins
    out, prev = [], None
    for day, item in by_day.items():
        out.append({
            "day": day,
            "taken_at": item["taken_at"],
            "used": item["used"],
            "total": item["total"],
            "free": item["free"],
            "delta": None if prev is None else item["used"] - prev,
        })
        prev = item["used"]
    return out


def full_snapshots(conn, drive: str) -> list[dict]:
    rows = conn.execute(
        """SELECT id, taken_at, used, total, depth, new_since, files_scanned, errors, scan_seconds,
                  (SELECT COUNT(*) FROM new_files n WHERE n.snapshot_id = s.id) AS new_files
           FROM snapshots s WHERE drive = ? AND mode = 'full' ORDER BY taken_at""",
        (drive,),
    ).fetchall()
    return [dict(r) for r in rows]


def _resolve_pair(conn, drive, from_id, to_id):
    snaps = full_snapshots(conn, drive)
    if not snaps:
        return None, None
    ids = [s["id"] for s in snaps]
    if to_id is None:
        to_id = ids[-1]
    if from_id is None:
        older = [i for i in ids if i < to_id]
        from_id = older[-1] if older else None
    return from_id, to_id


def folder_growth(conn, drive: str, from_id: int | None = None, to_id: int | None = None,
                  depth: int | None = None, limit: int = 50) -> dict:
    """Folders whose size changed the most between two full snapshots.

    Defaults to the two most recent full snapshots of the drive. With only one
    snapshot available every folder is reported with ``before = None``.
    """
    from_id, to_id = _resolve_pair(conn, drive, from_id, to_id)
    if to_id is None:
        return {"from": None, "to": None, "folders": []}

    depth_filter = "" if depth is None else "AND depth = :depth"
    rows = conn.execute(
        f"""
        WITH a AS (SELECT path, depth, size FROM folder_sizes WHERE snapshot_id = :from_id {depth_filter}),
             b AS (SELECT path, depth, size FROM folder_sizes WHERE snapshot_id = :to_id {depth_filter}),
             paths AS (SELECT path, depth FROM a UNION SELECT path, depth FROM b)
        SELECT p.path, p.depth, a.size AS before, b.size AS after,
               COALESCE(b.size, 0) - COALESCE(a.size, 0) AS delta
        FROM paths p
        LEFT JOIN a ON a.path = p.path
        LEFT JOIN b ON b.path = p.path
        WHERE p.depth > 0
        ORDER BY ABS(delta) DESC, p.path
        LIMIT :limit
        """,
        {"from_id": from_id if from_id is not None else -1, "to_id": to_id,
         "depth": depth, "limit": limit},
    ).fetchall()
    if from_id is None:
        # No baseline: show the biggest folders instead of meaningless deltas.
        rows = sorted(rows, key=lambda r: -(r["after"] or 0))
    return {
        "from": _snapshot_meta(conn, from_id),
        "to": _snapshot_meta(conn, to_id),
        "folders": [dict(r) for r in rows],
    }


def new_files(conn, drive: str, snapshot_id: int | None = None, limit: int = 100) -> dict:
    """Largest files added since the previous full snapshot."""
    if snapshot_id is None:
        snaps = full_snapshots(conn, drive)
        if not snaps:
            return {"snapshot": None, "files": []}
        snapshot_id = snaps[-1]["id"]
    rows = conn.execute(
        "SELECT path, size, created, modified FROM new_files WHERE snapshot_id = ? ORDER BY size DESC LIMIT ?",
        (snapshot_id, limit),
    ).fetchall()
    return {"snapshot": _snapshot_meta(conn, snapshot_id), "files": [dict(r) for r in rows]}


def recent_new_files(conn, drive: str, limit: int = 100) -> list[dict]:
    """Largest new files across all snapshots, newest snapshot first."""
    rows = conn.execute(
        """SELECT n.path, n.size, n.created, n.modified, s.taken_at AS detected_at
           FROM new_files n JOIN snapshots s ON s.id = n.snapshot_id
           WHERE s.drive = ? ORDER BY s.taken_at DESC, n.size DESC LIMIT ?""",
        (drive, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _snapshot_meta(conn, snapshot_id):
    if snapshot_id is None:
        return None
    r = conn.execute(
        "SELECT id, taken_at, used, total, new_since FROM snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    return dict(r) if r else None


def human_size(n: int | None, signed: bool = False) -> str:
    if n is None:
        return "-"
    sign = ""
    if signed:
        sign = "+" if n > 0 else ("-" if n < 0 else "±")
    value = float(abs(n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{sign}{value:.0f} {unit}" if unit == "B" else f"{sign}{value:.2f} {unit}"
        value /= 1024
    return f"{sign}{value:.2f} TB"


def parse_size(text: str) -> int:
    """'10MB', '1.5 GB', '500k' -> bytes."""
    s = text.strip().upper().replace(" ", "")
    units = {"TB": 1024**4, "GB": 1024**3, "MB": 1024**2, "KB": 1024, "T": 1024**4,
             "G": 1024**3, "M": 1024**2, "K": 1024, "B": 1}
    for suffix, mult in units.items():
        if s.endswith(suffix):
            return int(float(s[: -len(suffix)]) * mult)
    return int(float(s))
