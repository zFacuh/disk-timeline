import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from disk_timeline import cli


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "h.db")
        self.data = Path(self.tmp.name) / "data"
        (self.data / "sub").mkdir(parents=True)
        (self.data / "sub" / "big.bin").write_bytes(b"\0" * 2 * 1024 * 1024)
        self.addCleanup(os.environ.pop, "DISK_TIMELINE_DB", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--db", self.db, *argv])
        return code, out.getvalue()

    def test_reports_without_data(self):
        code, out = self.run_cli("status")
        self.assertEqual(code, 1)
        self.assertIn("disk-timeline snapshot", out)
        self.assertEqual(self.run_cli("list", "C")[0], 1)
        self.assertEqual(self.run_cli("growth", "C")[0], 1)
        self.assertEqual(self.run_cli("new", "C")[0], 1)

    def test_reports_after_snapshot(self):
        from disk_timeline import db
        from disk_timeline.snapshot import take_snapshot

        conn = db.connect(self.db)
        take_snapshot(conn, "C", root=str(self.data), min_new_size=1024 * 1024)
        conn.close()

        code, out = self.run_cli("status", "C")
        self.assertEqual(code, 0)
        self.assertIn("usado", out)
        code, out = self.run_cli("list", "C")
        self.assertEqual(code, 0)
        self.assertIn("1", out)
        code, out = self.run_cli("growth", "C")
        self.assertEqual(code, 0)
        self.assertIn("sub", out)
        code, out = self.run_cli("new", "C")
        self.assertEqual(code, 0)
        self.assertIn("big.bin", out)
        code, out = self.run_cli("new", "C", "--all")
        self.assertIn("big.bin", out)


if __name__ == "__main__":
    unittest.main()
