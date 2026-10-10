"""Create a database with simulated history to try the dashboard.

    python scripts/make_demo_db.py demo.db
    python -m disk_timeline --db demo.db serve
"""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from disk_timeline import db  # noqa: E402
from disk_timeline.drives import DriveUsage  # noqa: E402
from disk_timeline.scanner import FolderSize, NewFile  # noqa: E402

GB = 1024 ** 3
MB = 1024 ** 2

FOLDERS = {
    "C": {
        r"C:\Users": 1, r"C:\Windows": 1, r"C:\Program Files": 1,
        r"C:\Users\usuario": 2, r"C:\Users\usuario\Downloads": 3, r"C:\Users\usuario\Videos": 3,
        r"C:\Users\usuario\AppData": 3, r"C:\Users\usuario\Documents": 3,
        r"C:\Program Files\Steam": 2, r"C:\Windows\WinSxS": 2,
    },
    "D": {r"D:\Juegos": 1, r"D:\Fotos": 1, r"D:\Backups": 1, r"D:\Juegos\Steam": 2},
}
NEW_FILE_NAMES = [
    r"Downloads\ubuntu-26.04-desktop-amd64.iso", r"Videos\grabacion-partida.mp4",
    r"Downloads\dataset.zip", r"AppData\Local\Temp\installer.msi",
    r"Documents\proyecto-final.psd", r"Videos\clip-vacaciones.mov",
]


def main(path: str, days: int = 60) -> None:
    Path(path).unlink(missing_ok=True)
    conn = db.connect(path)
    rng = random.Random(42)
    now = time.time()
    state = {
        "C": {"total": 476 * GB, "used": 340 * GB},
        "D": {"total": 1863 * GB, "used": 300 * GB},
    }
    sizes = {d: {p: rng.uniform(5, 60) * GB / lvl for p, lvl in f.items()} for d, f in FOLDERS.items()}
    prev_ts = {}
    for day in range(days, -1, -1):
        ts = now - day * 86400
        for drive, s in state.items():
            change = rng.gauss(0.4, 1.2) * GB
            if rng.random() < 0.08:
                change += rng.uniform(5, 25) * GB  # occasional big install
            if rng.random() < 0.05:
                change -= rng.uniform(5, 15) * GB  # occasional cleanup
            s["used"] = int(min(max(s["used"] + change, 50 * GB), s["total"] - GB))
            usage = DriveUsage(drive, f"{drive}:\\", s["total"], s["used"], s["total"] - s["used"])
            full = day % 3 == 0 or day < 7
            if not full:
                db.insert_snapshot(conn, taken_at=ts, usage=usage, mode="quick")
                continue
            since = prev_ts.get(drive, ts - 7 * 86400)
            sid = db.insert_snapshot(conn, taken_at=ts, usage=usage, mode="full", depth=3,
                                     new_since=since, files_scanned=rng.randint(400_000, 900_000),
                                     errors=rng.randint(0, 40), scan_seconds=rng.uniform(40, 120))
            prev_ts[drive] = ts
            for p in sizes[drive]:
                sizes[drive][p] = max(0, sizes[drive][p] + rng.gauss(0.1, 0.6) * GB)
            folders = [FolderSize(f"{drive}:\\", 0, s["used"], 1)]
            folders += [FolderSize(p, FOLDERS[drive][p], int(v), rng.randint(100, 50000))
                        for p, v in sizes[drive].items()]
            db.insert_folder_sizes(conn, sid, folders)
            if drive == "C":
                picks = rng.sample(NEW_FILE_NAMES, rng.randint(1, 4))
                files = [NewFile(int(rng.uniform(20, 6000) * MB), rf"C:\Users\usuario\{n}",
                                 ts - rng.uniform(0, ts - since), ts - rng.uniform(0, ts - since))
                         for n in picks]
                db.insert_new_files(conn, sid, files)
    conn.commit()
    print(f"Base de demo creada en {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo.db")
