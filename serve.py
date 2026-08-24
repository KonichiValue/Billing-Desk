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
import os
import re
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

job = {"state": "idle", "message": "", "url": "", "at": ""}
job_lock = threading.Lock()


BOARD = ROOT / "state" / "board.json"

# Chrome reads this when you install the page as an app, and takes the Dock icon
# from it. Without it the installed app wears the Chrome logo.
MANIFEST = {
    "name": "TG Billing Desk",
    "short_name": "TG Desk",
    "description": "Every open Tokyo Gas billing ticket and what is left to do on it.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#fafafa",
    "theme_color": "#fafafa",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ],
}


def rebuild() -> str:
    """Render the desk and hand back the HTML, so a load is always current."""
    html = ROOT / "output" / "desk.html"
    subprocess.run(
        [sys.executable, "render_desk.py", str(BOARD), str(html)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [sys.executable, "render_desk_md.py", str(BOARD), str(ROOT / "output/desk.md")],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
    )
    return html.read_text(encoding="utf-8")


def set_job(state: str, message: str = "", url: str = "") -> None:
    with job_lock:
        job.update(
            state=state, message=message, url=url, at=datetime.now().strftime("%H:%M")
        )


def logged_in() -> bool:
    status = subprocess.run(
        ["cursor-agent", "status"], capture_output=True, text=True, check=False
    )
    return "not logged in" not in (status.stdout + status.stderr).lower()


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
URL_IN = re.compile(r"https://\S+")


def start_login() -> None:
    """Run the sign-in here and hand Rei the URL it prints.

    Driving Terminal through AppleScript needs an automation permission this
    process does not have, so instead the login runs as a child here and the
    page shows the link. Rei approves it in the browser, this notices, and the
    button comes back to life.
    """
    if logged_in():
        set_job("idle", "Already signed in. Press Refresh.")
        return
    try:
        proc = subprocess.Popen(
            ["cursor-agent", "login"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        set_job("needs_login", f"could not start the sign-in: {exc}")
        return

    set_job("needs_login", "Starting the sign-in")
    lines: list[str] = []
    threading.Thread(
        target=lambda: [lines.append(ANSI.sub("", ln)) for ln in proc.stdout],
        daemon=True,
    ).start()

    url, deadline = "", time.time() + 25
    while time.time() < deadline and not url:
        for line in list(lines):
            found = URL_IN.search(line)
            if found:
                url = found.group(0).rstrip('.,")')
                break
        if not url:
            time.sleep(0.5)

    if url:
        set_job("needs_login", "Approve the sign-in in your browser, then press Refresh.", url)
    else:
        set_job(
            "needs_login",
            "The sign-in printed no link. Open a Terminal and run: cursor-agent login",
        )

    # Wait for it to land rather than making him press anything twice.
    end = time.time() + 300
    while time.time() < end:
        if logged_in():
            set_job("idle", "Signed in. Press Refresh.")
            return
        if proc.poll() is not None and not url:
            return
        time.sleep(3)


def run_refresh() -> None:
    """One agent pass over prompt-refresh.md, then the page reloads itself."""
    if not (ROOT / "prompt-refresh.md").exists():
        set_job("failed", "prompt-refresh.md is missing")
        return
    agent = subprocess.run(["which", "cursor-agent"], capture_output=True, text=True)
    if agent.returncode != 0:
        set_job("failed", "cursor-agent is not installed. Type 'refresh' in a Cursor chat instead.")
        return

    if not logged_in():
        set_job("needs_login", "cursor-agent is signed out. Log in and the button works again.")
        return

    set_job("running", "Reading every open ticket and the threads behind them")
    log = ROOT / "logs" / f"refresh-{datetime.now():%Y-%m-%d}.log"
    log.parent.mkdir(exist_ok=True)
    # No --model, so it runs on whatever cursor-agent defaults to, which is Auto.
    # TG_MODEL pins a specific one when that is wanted.
    cmd = ["cursor-agent", "--print", "--force", "--approve-mcps", "--trust",
           "--workspace", str(ROOT)]
    if os.environ.get("TG_MODEL"):
        cmd += ["--model", os.environ["TG_MODEL"]]
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
        if path == "/manifest.webmanifest":
            self.send(200, json.dumps(MANIFEST).encode(), "application/manifest+json")
            return
        if path in ("/icon-192.png", "/icon-512.png", "/favicon.ico"):
            name = {"/favicon.ico": "icon-192.png"}.get(path, path.lstrip("/"))
            icon = ROOT / "app" / name
            if not icon.exists():
                icon = ROOT / "app" / "icon.png"
            if not icon.exists():
                self.send(404, b"no icon built", "text/plain")
                return
            self.send(200, icon.read_bytes(), "image/png")
            return
        if path in ("/", "/index.html"):
            if not BOARD.exists():
                self.send(404, b"No board yet. Run: tg build", "text/plain")
                return
            try:
                html = rebuild()
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
        if path == "/api/login":
            threading.Thread(target=start_login, daemon=True).start()
            self.json_out(202, {"state": "needs_login"})
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
