"""Walk a drive once, aggregating folder sizes and collecting recently added files."""

import heapq
import os
import stat
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
MIN_FOLDER_SIZE = 1024 * 1024  # folders smaller than 1 MB are not stored


@dataclass
class FolderSize:
    path: str
    depth: int
    size: int = 0
    file_count: int = 0


@dataclass(order=True)
class NewFile:
    size: int
    path: str = field(compare=False)
    created: float = field(compare=False)
    modified: float = field(compare=False)


@dataclass
class ScanResult:
    folders: list[FolderSize]
    new_files: list[NewFile]
    files_scanned: int
    errors: int
    seconds: float


def _created(st: os.stat_result) -> float:
    birth = getattr(st, "st_birthtime", None)
    if birth is not None:
        return birth
    # On Windows (Python < 3.12) st_ctime is the creation time.
    return st.st_ctime if os.name == "nt" else st.st_mtime


def _is_link_like(entry: os.DirEntry, st: os.stat_result) -> bool:
    if entry.is_symlink():
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def scan(
    root: str,
    *,
    depth: int = 3,
    new_since: float | None = None,
    min_new_size: int = 10 * 1024 * 1024,
    top_new: int = 200,
    exclude: Iterable[str] = (),
    min_folder_size: int = MIN_FOLDER_SIZE,
    progress: Callable[[int, str], None] | None = None,
    progress_every: int = 50_000,
) -> ScanResult:
    """Scan ``root`` recursively.

    Folder sizes are aggregated for every folder up to ``depth`` levels below the
    root (the root itself is depth 0). Files whose creation or modification time is
    newer than ``new_since`` and at least ``min_new_size`` bytes are collected; only
    the ``top_new`` largest are kept.
    """
    started = time.monotonic()
    root = os.path.abspath(root)
    excluded = {os.path.normcase(os.path.abspath(p)) for p in exclude}

    folders: dict[str, FolderSize] = {root: FolderSize(root, 0)}
    heap: list[NewFile] = []
    files_scanned = 0
    errors = 0

    # Each stack item: (directory, depth, folders that receive the sizes of its files)
    stack: list[tuple[str, int, tuple[FolderSize, ...]]] = [(root, 0, (folders[root],))]

    while stack:
        current, level, buckets = stack.pop()
        try:
            it = os.scandir(current)
        except OSError:
            errors += 1
            continue
        with it:
            for entry in it:
                try:
                    st = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        if _is_link_like(entry, st):
                            continue
                        if excluded and os.path.normcase(entry.path) in excluded:
                            continue
                        child_level = level + 1
                        child_buckets = buckets
                        if child_level <= depth:
                            folder = FolderSize(entry.path, child_level)
                            folders[entry.path] = folder
                            child_buckets = buckets + (folder,)
                        stack.append((entry.path, child_level, child_buckets))
                        continue
                    if not stat.S_ISREG(st.st_mode):
                        continue
                except OSError:
                    errors += 1
                    continue

                size = st.st_size
                for folder in buckets:
                    folder.size += size
                    folder.file_count += 1
                files_scanned += 1

                if new_since is not None and size >= min_new_size:
                    created = _created(st)
                    if max(created, st.st_mtime) > new_since:
                        item = NewFile(size, entry.path, created, st.st_mtime)
                        if len(heap) < top_new:
                            heapq.heappush(heap, item)
                        elif size > heap[0].size:
                            heapq.heapreplace(heap, item)

                if progress and files_scanned % progress_every == 0:
                    progress(files_scanned, current)

    kept = [f for f in folders.values() if f.depth == 0 or f.size >= min_folder_size]
    return ScanResult(
        folders=kept,
        new_files=sorted(heap, reverse=True),
        files_scanned=files_scanned,
        errors=errors,
        seconds=time.monotonic() - started,
    )
