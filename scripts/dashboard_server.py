"""Local dashboard for the job search. Run it, open http://127.0.0.1:8765.

Usage: python scripts/dashboard_server.py [--port 8765] [--no-browser]
Serves ui/index.html and a small JSON API over data/tracker.json (see scripts/tracker.py).
Listens on localhost only. Nothing is sent anywhere and nothing is ever submitted.
"""
import argparse
import json
import shutil
import sys
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tracker  # noqa: E402

ROOT = tracker.ROOT
UI = ROOT / "ui" / "index.html"
LOCK = threading.Lock()


def move_folder(rec, archive):
    """Move the job folder between jobs/ and jobs/_archive/ and update the record. Returns a message."""
    cur = ROOT / rec.get("folder", "") if rec.get("folder") else None
    if not cur or not cur.exists():
        return "no folder to move"
    name = cur.name
    dest_dir = ROOT / "jobs" / ("_archive" if archive else "")
    dest = dest_dir / name
    if cur.resolve() == dest.resolve():
        return "already there"
    if dest.exists():
        return "destination exists"
    shutil.move(str(cur), str(dest))
    rec["folder"] = ("jobs/_archive/" if archive else "jobs/") + name
    return "moved"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _local_only(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._local_only():
            return self._json({"error": "forbidden"}, 403)
        if self.path in ("/", "/index.html"):
            body = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/data":
            with LOCK:
                data = tracker.load()
            self._json({"data": data, "insights": tracker.insights(data), "today": date.today().isoformat(),
                        "statuses": tracker.STATUSES, "replies": tracker.REPLIES, "outreach": tracker.OUTREACH})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        # The custom header blocks cross-site form posts: a web page cannot set it without a CORS preflight.
        if not self._local_only() or self.headers.get("X-Requested-With") != "job-dashboard":
            return self._json({"error": "forbidden"}, 403)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)
        with LOCK:
            data = tracker.load()
            msg = "ok"
            if self.path == "/api/save":
                rec = req.get("record") or {}
                if not rec.get("id"):
                    return self._json({"error": "id required"}, 400)
                if rec.get("status") not in (None, *tracker.STATUSES) or rec.get("reply") not in (None, *tracker.REPLIES) or rec.get("outreach") not in (None, *tracker.OUTREACH):
                    return self._json({"error": "bad status or reply"}, 400)
                if rec.get("status") == "applied" and not rec.get("applied"):
                    rec["applied"] = date.today().isoformat()
                if rec.get("reply") in ("recruiter", "interview", "rejection", "offer") and not rec.get("reply_date"):
                    rec["reply_date"] = date.today().isoformat()
                tracker.upsert(data, rec)
            elif self.path == "/api/archive":
                rec = next((a for a in data["applications"] if a["id"] == req.get("id")), None)
                if not rec:
                    return self._json({"error": "unknown id"}, 404)
                msg = move_folder(rec, bool(req.get("archive")))
            elif self.path == "/api/delete":
                data["applications"] = [a for a in data["applications"] if a["id"] != req.get("id")]
            elif self.path == "/api/lesson":
                if req.get("delete") is not None:
                    data["lessons"] = [l for i, l in enumerate(data["lessons"]) if i != req["delete"]]
                elif req.get("text"):
                    data["lessons"].insert(0, {"date": date.today().isoformat(), "text": req["text"][:600]})
            else:
                return self._json({"error": "not found"}, 404)
            tracker.save(data)
            self._json({"ok": True, "message": msg, "data": data, "insights": tracker.insights(data)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Job dashboard running at {url} (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
