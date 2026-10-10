"""Local web dashboard: static files + a small JSON API."""

import json
import os
import subprocess
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import analysis, db, drives

WEB_DIR = Path(__file__).with_name("web")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}
# Browsers can't send this header cross-origin without a CORS preflight we never
# answer, so requiring it on POST blocks other websites from driving the API.
CSRF_HEADER = "X-Disk-Timeline"


class Job:
    """At most one snapshot runs at a time; the dashboard polls its state."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"running": False}

    def start(self, drive_list, full):
        with self.lock:
            if self.state.get("running"):
                return False
            self.state = {"running": True, "full": full, "drives": drive_list,
                          "started": time.time(), "current": None, "files": 0, "done": []}
        threading.Thread(target=self._run, args=(drive_list, full), daemon=True).start()
        return True

    def _run(self, drive_list, full):
        from .snapshot import take_snapshot

        conn = db.connect()
        try:
            for d in drive_list:
                self.state["current"] = d

                def progress(count, _path):
                    self.state["files"] = count

                s = take_snapshot(conn, d, full=full, progress=progress)
                self.state["done"].append(s.drive)
            self.state["error"] = None
        except Exception as e:  # surface any failure to the UI
            self.state["error"] = str(e)
        finally:
            conn.close()
            self.state["running"] = False
            self.state["finished"] = time.time()


JOB = Job()


def _int(qs, key):
    v = qs.get(key, [None])[0]
    return int(v) if v not in (None, "") else None


class Handler(BaseHTTPRequestHandler):
    server_version = "disk-timeline"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    # ---- helpers -------------------------------------------------------
    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    # ---- routes --------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/":
            return self._send_file(WEB_DIR / "index.html")
        if url.path.startswith("/static/"):
            name = url.path[len("/static/"):]
            target = (WEB_DIR / name).resolve()
            if WEB_DIR.resolve() not in target.parents:
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self._send_file(target)
        if url.path.startswith("/api/"):
            try:
                return self._api_get(url.path[5:], qs)
            except Exception as e:
                return self._send_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.send_error(HTTPStatus.NOT_FOUND)

    def _api_get(self, route, qs):
        drive = qs.get("drive", [None])[0]
        if drive:
            drive = drives.normalize_drive(drive)
        conn = db.connect()
        try:
            if route == "drives":
                out = []
                for d in db.drives(conn):
                    days = analysis.daily_series(conn, d)
                    out.append({"drive": d, "root": drives.drive_root(d), "latest": days[-1] if days else None,
                                "days": len(days)})
                return self._send_json(out)
            if route == "daily":
                return self._send_json(analysis.daily_series(conn, drive))
            if route == "series":
                return self._send_json(analysis.usage_series(conn, drive))
            if route == "snapshots":
                return self._send_json(analysis.full_snapshots(conn, drive))
            if route == "growth":
                return self._send_json(analysis.folder_growth(
                    conn, drive, _int(qs, "from"), _int(qs, "to"), _int(qs, "depth"), _int(qs, "limit") or 50))
            if route == "new":
                return self._send_json(analysis.new_files(conn, drive, _int(qs, "snapshot"), _int(qs, "limit") or 100))
            if route == "recent-new":
                return self._send_json(analysis.recent_new_files(conn, drive, _int(qs, "limit") or 100))
            if route == "job":
                return self._send_json(JOB.state)
        finally:
            conn.close()
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        url = urlparse(self.path)
        if self.headers.get(CSRF_HEADER) != "1":
            return self._send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        body = self._read_json()
        if url.path == "/api/snapshot":
            targets = [drives.normalize_drive(d) for d in body.get("drives") or []] or drives.list_fixed_drives()
            started = JOB.start(targets, full=bool(body.get("full")))
            return self._send_json({"started": started, "job": JOB.state},
                                   HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT)
        if url.path == "/api/reveal":
            path = body.get("path") or ""
            if os.name != "nt" or not os.path.exists(path):
                return self._send_json({"error": "no existe"}, HTTPStatus.NOT_FOUND)
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return self._send_json({"ok": True})
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def serve(host="127.0.0.1", port=8765, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Panel disponible en {url}  (Ctrl+C para salir)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
