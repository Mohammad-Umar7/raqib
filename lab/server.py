"""Raqib scam lab server.

Serves the fictional replica scam sites in ``lab/sites/<label>/`` on
``http://<label>.localhost:<port>/``. Chromium resolves every ``*.localhost``
name to the loopback address, so each lab site gets its own believable
"domain" without touching DNS or the real internet.

* ``POST /__sink`` on any host swallows form data (returns 204). It is the
  only place lab pages ever send data.
* ``lab/data/redirects.json`` defines pure redirector hosts.
* Unknown hosts answer 404, which the investigator treats as "not live".

Run standalone with ``python lab/server.py`` or let the backend start it.
"""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

LAB_DIR = Path(__file__).resolve().parent
SITES_DIR = LAB_DIR / "sites"
DATA_DIR = LAB_DIR / "data"
DEFAULT_PORT = 8601

_sink_log: list[dict] = []
_sink_lock = threading.Lock()


def _load_redirects() -> dict:
    path = DATA_DIR / "redirects.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def sink_entries() -> list[dict]:
    with _sink_lock:
        return list(_sink_log)


class LabHandler(BaseHTTPRequestHandler):
    server_version = "LabHTTP/1.0"
    sys_version = ""

    # Quiet console: the backend shows lab traffic in its own UI.
    def log_message(self, fmt, *args):  # noqa: D401 - stdlib signature
        return

    def _label(self) -> str | None:
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        if host.endswith(".localhost"):
            return host[: -len(".localhost")]
        return None

    def _send(self, status: int, body: bytes = b"", ctype: str = "text/html; charset=utf-8", extra: dict | None = None):
        self.send_response(status)
        if body:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _not_found(self):
        body = (
            "<!doctype html><title>Not found</title>"
            "<body style='font-family:system-ui;padding:40px;color:#555'>"
            "<h1 style='font-weight:500'>404 · site not found</h1>"
            "<p>This lab host is not live.</p></body>"
        ).encode()
        self._send(404, body)

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def do_GET(self):  # noqa: N802
        label = self._label()
        if not label:
            return self._not_found()

        redirects = _load_redirects()
        if label in redirects:
            target = redirects[label]
            return self._send(int(target.get("status", 302)), b"", extra={"Location": target["to"]})

        site_dir = (SITES_DIR / label).resolve()
        if not site_dir.is_dir() or SITES_DIR.resolve() not in site_dir.parents:
            return self._not_found()

        path = unquote(urlsplit(self.path).path)
        if path.endswith("/"):
            path += "index.html"
        file_path = (site_dir / path.lstrip("/")).resolve()
        if site_dir not in file_path.parents and file_path != site_dir:
            return self._not_found()
        if not file_path.is_file():
            # favicon requests are common; answer quietly
            return self._not_found()

        ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, file_path.read_bytes(), ctype)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(min(length, 64_000)) if length else b""
        if urlsplit(self.path).path == "/__sink":
            with _sink_lock:
                _sink_log.append({"host": self.headers.get("Host"), "bytes": len(payload)})
                del _sink_log[:-200]
            return self._send(204)
        return self._not_found()


def start_in_thread(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), LabHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="lab-server", daemon=True)
    thread.start()
    return server


def lab_sites(port: int = DEFAULT_PORT) -> list[str]:
    """Return the base URLs of the lab sites that exist on disk."""
    if not SITES_DIR.is_dir():
        return []
    return [f"http://{p.name}.localhost:{port}/" for p in sorted(SITES_DIR.iterdir()) if p.is_dir()]


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", DEFAULT_PORT), LabHandler)
    print(f"Raqib lab serving {len(lab_sites())} sites on *.localhost:{DEFAULT_PORT}")
    for url in lab_sites():
        print("  ", url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
