import os
import tempfile
import time
import unittest
from pathlib import Path

from disk_timeline import scanner

KB = 1024


def write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write(self.root / "top.bin", 10 * KB)
        write(self.root / "a" / "one.bin", 100 * KB)
        write(self.root / "a" / "b" / "two.bin", 200 * KB)
        write(self.root / "a" / "b" / "c" / "deep.bin", 400 * KB)
        write(self.root / "z" / "small.bin", 1 * KB)

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self, **kw):
        kw.setdefault("min_folder_size", 0)
        return scanner.scan(str(self.root), **kw)

    def sizes(self, result):
        return {os.path.relpath(f.path, self.root): f.size for f in result.folders}

    def test_folder_sizes_are_aggregated_up_to_depth(self):
        r = self.scan(depth=2)
        sizes = self.sizes(r)
        self.assertEqual(sizes["."], 711 * KB)
        self.assertEqual(sizes["a"], 700 * KB)
        self.assertEqual(sizes[os.path.join("a", "b")], 600 * KB)
        self.assertNotIn(os.path.join("a", "b", "c"), sizes)  # deeper than depth
        self.assertEqual(r.files_scanned, 5)
        self.assertEqual(r.errors, 0)

    def test_small_folders_are_dropped_but_root_kept(self):
        r = scanner.scan(str(self.root), depth=3, min_folder_size=150 * KB)
        sizes = self.sizes(r)
        self.assertIn(".", sizes)
        self.assertIn("a", sizes)
        self.assertNotIn("z", sizes)

    def test_new_files_respect_min_size_and_top(self):
        r = self.scan(new_since=time.time() - 3600, min_new_size=50 * KB, top_new=2)
        names = [Path(f.path).name for f in r.new_files]
        self.assertEqual(names, ["deep.bin", "two.bin"])  # largest first, capped at 2

    def test_no_new_files_without_since(self):
        r = self.scan()
        self.assertEqual(r.new_files, [])

    def test_files_older_than_since_are_ignored(self):
        r = self.scan(new_since=time.time() + 3600, min_new_size=0)
        self.assertEqual(r.new_files, [])

    def test_exclude(self):
        r = self.scan(depth=3, exclude=[str(self.root / "a")])
        self.assertEqual(self.sizes(r)["."], 11 * KB)
        self.assertEqual(r.files_scanned, 2)


if __name__ == "__main__":
    unittest.main()
