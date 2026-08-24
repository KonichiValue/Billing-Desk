#!/usr/bin/env python3
"""Serve the desk page locally, so the page can do things a file:// page cannot.

Two jobs. It renders the page fresh on every load, from the JSON and the state
file, so what you see is never a stale build. And it gives the Refresh button
somewhere to send its click: the button asks this server to run the agent, the
server reports progress, the page reloads itself when the work lands.

Local only. It binds to the loopback address and every call carries a key
generated at startup, so nothing else on the machine can start an agent run.

    python3 serve.py            start on 127.0.0.1:8787
    python3 serve.py --port N   somewhere else
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = secrets.token_urlsafe(16)
TIMEOUT_SECS = 900

job = {"state": "idle", "message": "", "at": ""}
job_lock = threading.Lock()


def latest_json() -> Path | None:
    found = sorted((ROOT / "output").glob("post-*.json"))
    return found[-1] if found else None


def rebuild(report: Path) -> str:
    """Render the page and hand back the HTML, so a load is always current."""
    html = report.with_suffix(".html")
    subprocess.run(
        [sys.executable, "render_post.py", str(report), str(html)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [sys.executable, "render_md.py", str(report), str(report.with_suffix(".md"))],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
    )
    return html.read_text(encoding="utf-8")


def set_job(state: str, message: str = "") -> None:
    with job_lock:
        job.update(state=state, message=message, at=datetime.now().strftime("%H:%M"))


def run_refresh() -> None:
    """One agent pass over prompt-refresh.md, then the page reloads itself."""
    if not (ROOT / "prompt-refresh.md").exists():
        set_job("failed", "prompt-refresh.md is missing")
        return
    agent = subprocess.run(["which", "cursor-agent"], capture_output=True, text=True)
    if agent.returncode != 0:
        set_job("failed", "cursor-agent is not installed. Type 'refresh' in a Cursor chat instead.")
        return

    status = subprocess.run(["cursor-agent", "status"], capture_output=True, text=True)
    if "not logged in" in (status.stdout + status.stderr).lower():
        set_job("failed", "cursor-agent is not logged in. Run: cursor-agent login")
        return

    set_job("running", "Reading the tickets and threads behind your open actions")
    log = ROOT / "logs" / f"refresh-{datetime.now():%Y-%m-%d}.log"
    log.parent.mkdir(exist_ok=True)
    cmd = ["cursor-agent", "--print", "--force", "--approve-mcps", "--trust",
           "--workspace", str(ROOT)]
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n=== {datetime.now():%H:%M:%S} refresh ===\n")
        try:
            proc = subprocess.run(
                cmd + [(ROOT / "prompt-refresh.md").read_text(encoding="utf-8")],
                cwd=ROOT,
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT_SECS,
            )
        except subprocess.TimeoutExpired:
            set_job("failed", "the agent ran past 15 minutes and was stopped")
            return
    if proc.returncode != 0:
        set_job("failed", f"the agent exited {proc.returncode}. See {log.name}")
        return
    set_job("done", "Refreshed")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # quiet: this runs behind an app icon
        pass

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json_out(self, code: int, payload: dict) -> None:
        self.send(code, json.dumps(payload).encode(), "application/json")

    def keyed(self) -> bool:
        return KEY in (self.path.split("?", 1)[1] if "?" in self.path else "")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.json_out(200, {"ok": True, "key": KEY})
            return
        if path == "/api/status":
            with job_lock:
                self.json_out(200, dict(job))
            return
        if path in ("/", "/index.html"):
            report = latest_json()
            if report is None:
                self.send(404, b"No list built yet. Run: tg build", "text/plain")
                return
            try:
                html = rebuild(report)
            except subprocess.CalledProcessError as exc:
                self.send(500, f"render failed: {exc}".encode(), "text/plain")
                return
            # A finished run has been collected by this load, so clear it.
            # Otherwise the page reloads, sees "done" again, and reloads forever.
            with job_lock:
                if job["state"] == "done":
                    job.update(state="idle", message=f"Last refreshed {job['at']}")
            html = html.replace("__DESK_KEY__", KEY)
            self.send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        self.send(404, b"not here", "text/plain")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if not self.keyed():
            self.json_out(403, {"error": "bad key"})
            return
        if path == "/api/refresh":
            with job_lock:
                if job["state"] == "running":
                    self.json_out(409, dict(job))
                    return
            set_job("running", "Starting")
            threading.Thread(target=run_refresh, daemon=True).start()
            self.json_out(202, {"state": "running"})
            return
        self.json_out(404, {"error": "not here"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "serve.json").write_text(
        json.dumps({"port": args.port, "key": KEY, "started": time.time()}) + "\n",
        encoding="utf-8",
    )
    print(f"http://127.0.0.1:{args.port}/?k={KEY}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
