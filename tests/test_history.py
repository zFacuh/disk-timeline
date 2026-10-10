import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from disk_timeline import analysis, db, scheduler
from disk_timeline.drives import DriveUsage
from disk_timeline.scanner import FolderSize, NewFile
from disk_timeline.snapshot import take_snapshot

GB = 1024 ** 3
DAY = 86400


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        self.t0 = datetime(2026, 10, 1, 21, 0).timestamp()

    def add(self, day, used, mode="full", folders=(), files=(), hour_offset=0):
        usage = DriveUsage("C", "C:\\", 500 * GB, used, 500 * GB - used)
        ts = self.t0 + day * DAY + hour_offset * 3600
        sid = db.insert_snapshot(self.conn, taken_at=ts, usage=usage, mode=mode, depth=3,
                                 new_since=ts - DAY)
        db.insert_folder_sizes(self.conn, sid, [FolderSize(p, d, s, 1) for p, d, s in folders])
        db.insert_new_files(self.conn, sid, [NewFile(s, p, ts, ts) for p, s in files])
        return sid

    def test_daily_series_keeps_last_snapshot_per_day(self):
        self.add(0, 100 * GB)
        self.add(1, 101 * GB, mode="quick")
        self.add(1, 103 * GB, mode="quick", hour_offset=1)
        self.add(2, 102 * GB)
        days = analysis.daily_series(self.conn, "C")
        self.assertEqual([d["used"] for d in days], [100 * GB, 103 * GB, 102 * GB])
        self.assertEqual([d["delta"] for d in days], [None, 3 * GB, -1 * GB])

    def test_folder_growth_between_last_two_full_snapshots(self):
        self.add(0, 100 * GB, folders=[("C:\\Users", 1, 10 * GB), ("C:\\Old", 1, 2 * GB)])
        self.add(1, 100 * GB, mode="quick")
        self.add(2, 105 * GB, folders=[("C:\\Users", 1, 14 * GB), ("C:\\Games", 1, 3 * GB)])
        g = analysis.folder_growth(self.conn, "C")
        rows = {r["path"]: r for r in g["folders"]}
        self.assertEqual(rows["C:\\Users"]["delta"], 4 * GB)
        self.assertEqual(rows["C:\\Games"]["before"], None)
        self.assertEqual(rows["C:\\Old"]["after"], None)
        self.assertEqual(rows["C:\\Old"]["delta"], -2 * GB)
        self.assertEqual(g["folders"][0]["path"], "C:\\Users")  # biggest change first

    def test_folder_growth_with_single_snapshot_lists_biggest(self):
        self.add(0, 100 * GB, folders=[("C:\\A", 1, 1 * GB), ("C:\\B", 1, 5 * GB)])
        g = analysis.folder_growth(self.conn, "C")
        self.assertIsNone(g["from"])
        self.assertEqual([f["path"] for f in g["folders"]], ["C:\\B", "C:\\A"])

    def test_new_files_latest_snapshot(self):
        self.add(0, 100 * GB, files=[("C:\\old.iso", 3 * GB)])
        self.add(1, 104 * GB, files=[("C:\\a.zip", 1 * GB), ("C:\\b.mkv", 2 * GB)])
        res = analysis.new_files(self.conn, "C")
        self.assertEqual([f["path"] for f in res["files"]], ["C:\\b.mkv", "C:\\a.zip"])
        everything = analysis.recent_new_files(self.conn, "C")
        self.assertEqual(everything[-1]["path"], "C:\\old.iso")


class SnapshotTests(unittest.TestCase):
    def test_full_snapshot_on_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sub").mkdir()
            (Path(tmp) / "sub" / "big.bin").write_bytes(b"\0" * 2 * 1024 * 1024)
            conn = db.connect(":memory:")
            s = take_snapshot(conn, "C", root=tmp, min_new_size=1024 * 1024)
            self.assertEqual(s.mode, "full")
            self.assertEqual(s.files_scanned, 1)
            self.assertEqual(s.new_files, 1)
            g = analysis.folder_growth(conn, "C")
            self.assertEqual(g["folders"][0]["path"], os.path.join(tmp, "sub"))
            quick = take_snapshot(conn, "C", root=tmp, full=False)
            self.assertEqual(quick.mode, "quick")
            self.assertEqual(len(analysis.full_snapshots(conn, "C")), 1)


class FormattingTests(unittest.TestCase):
    def test_parse_size(self):
        self.assertEqual(analysis.parse_size("10MB"), 10 * 1024 ** 2)
        self.assertEqual(analysis.parse_size("1.5 gb"), int(1.5 * GB))
        self.assertEqual(analysis.parse_size("500k"), 500 * 1024)
        self.assertEqual(analysis.parse_size("123"), 123)

    def test_human_size(self):
        self.assertEqual(analysis.human_size(0), "0 B")
        self.assertEqual(analysis.human_size(3 * GB, signed=True), "+3.00 GB")
        self.assertEqual(analysis.human_size(-512 * 1024 ** 2, signed=True), "-512.00 MB")


class SchedulerTests(unittest.TestCase):
    def test_task_xml_and_launcher(self):
        xml = scheduler.build_task_xml("07:30", r"C:\x\run_snapshot.pyw", now=datetime(2026, 10, 10, 12))
        self.assertIn("<StartBoundary>2026-10-10T07:30:00</StartBoundary>", xml)
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>", xml)
        self.assertIn('<Arguments>"C:\\x\\run_snapshot.pyw"</Arguments>', xml)
        compile(scheduler.build_launcher(quick=True), "run_snapshot.pyw", "exec")


if __name__ == "__main__":
    unittest.main()
