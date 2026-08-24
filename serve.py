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
    "name": "Billing Desk",
    "short_name": "Desk",
    "description": "Every open billing ticket, what is left to do, and what to say.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#f4f6fa",
    "theme_color": "#0d1524",
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


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
URL_IN = re.compile(r"https://\S+")


def cli(*args: str, timeout: int = 60) -> str:
    out = subprocess.run(
        ["cursor-agent", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    return ANSI.sub("", out.stdout + out.stderr)


def logged_in() -> bool:
    return "not logged in" not in cli("status").lower()


def unauthorised_mcps() -> list[str]:
    """Which configured MCP servers the agent cannot actually use.

    Without these a refresh has no Asana and no Slack. An agent with no tools
    does not stop: it improvises with curl and invented tokens, or starts
    another agent. Better to refuse the run and name what is missing.
    """
    missing = []
    for line in cli("mcp", "list").splitlines():
        name, _, state = line.partition(":")
        if state.strip() and "requires_authentication" in state:
            missing.append(name.strip())
    return missing


def blockers() -> tuple[list[str], str]:
    """Everything standing between the button and a real run, in one look."""
    if not logged_in():
        return ["account"], "cursor-agent is signed out."
    missing = unauthorised_mcps()
    if missing:
        names = " and ".join(n.title() for n in missing)
        verb = "needs" if len(missing) == 1 else "need"
        return missing, f"{names} {verb} authorising before a refresh can read anything."
    return [], ""


def connect_one(args: list[str], label: str, done) -> bool:
    """Run one auth command, show the link it prints, wait for it to land.

    Driving Terminal through AppleScript needs an automation permission this
    process does not have, so the command runs as a child here and the page
    shows the link. Rei approves it in the browser and this notices.
    """
    try:
        proc = subprocess.Popen(
            ["cursor-agent", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        set_job("needs_login", f"could not start {label}: {exc}")
        return False

    set_job("needs_login", f"Starting {label}")
    lines: list[str] = []
    threading.Thread(
        target=lambda: [lines.append(ANSI.sub("", ln)) for ln in proc.stdout],
        daemon=True,
    ).start()

    url, deadline = "", time.time() + 25
    while time.time() < deadline and not url and not done():
        for line in list(lines):
            found = URL_IN.search(line)
            if found:
                url = found.group(0).rstrip('.,")')
                break
        if not url:
            time.sleep(0.5)

    set_job(
        "needs_login",
        f"Approve {label} in your browser." if url else
        f"{label} printed no link. In a Terminal run: cursor-agent {' '.join(args)}",
        url,
    )

    end = time.time() + 240
    while time.time() < end:
        if done():
            return True
        if proc.poll() is not None:
            time.sleep(2)
            return done()
        time.sleep(3)
    return False


def start_login() -> None:
    """Walk everything that needs authorising, one browser approval at a time.

    The account sign-in is only half of it. Asana and Slack are separate grants,
    and a refresh without them reads nothing at all.
    """
    if not logged_in() and not connect_one(["login"], "the Cursor sign-in", logged_in):
        return
    for name in unauthorised_mcps():
        connect_one(
            ["mcp", "login", name],
            f"the {name.title()} connection",
            lambda n=name: n not in unauthorised_mcps(),
        )
    left, message = blockers()
    set_job("needs_login", message) if left else set_job("idle", "Connected. Press Refresh.")


LOCK = ROOT / "state" / "refresh.lock"


def lock_held() -> bool:
    """True when another refresh is already running, here or in a terminal."""
    if not LOCK.exists():
        return False
    try:
        pid = int(LOCK.read_text().split()[0])
        os.kill(pid, 0)
    except (ValueError, IndexError, OSError):
        LOCK.unlink(missing_ok=True)  # stale: whoever held it is gone
        return False
    return True


JOBS = {
    # endpoint name -> prompt, what the page says while it runs
    "refresh": ("prompt-refresh.md", "Reading every open ticket and the threads behind them"),
    "prep": ("prompt-prep.md", "Sweeping everything, then writing your standup script"),
}


def run_agent(kind: str) -> None:
    """One agent pass over a prompt, then the page reloads itself."""
    prompt_name, running_note = JOBS[kind]
    prompt = ROOT / prompt_name
    if not prompt.exists():
        set_job("failed", f"{prompt_name} is missing")
        return
    agent = subprocess.run(["which", "cursor-agent"], capture_output=True, text=True)
    if agent.returncode != 0:
        set_job("failed", "cursor-agent is not installed. Type 'refresh' in a Cursor chat instead.")
        return
    if lock_held():
        set_job("failed", "something is already running against the board. Let it finish.")
        return

    left, message = blockers()
    if left:
        set_job("needs_login", f"{message} Press Log in and approve each one.")
        return

    set_job("running", running_note)
    log = ROOT / "logs" / f"{kind}-{datetime.now():%Y-%m-%d}.log"
    log.parent.mkdir(exist_ok=True)
    # No --model, so it runs on whatever cursor-agent defaults to, which is Auto.
    # TG_MODEL pins a specific one when that is wanted.
    cmd = ["cursor-agent", "--print", "--force", "--approve-mcps", "--trust",
           "--workspace", str(ROOT)]
    if os.environ.get("TG_MODEL"):
        cmd += ["--model", os.environ["TG_MODEL"]]
    LOCK.write_text(f"{os.getpid()} desk-server {kind} {datetime.now():%H:%M}\n")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n=== {datetime.now():%H:%M:%S} {kind} ===\n")
        try:
            proc = subprocess.run(
                cmd + [prompt.read_text(encoding="utf-8")],
                cwd=ROOT,
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=TIMEOUT_SECS,
            )
        except subprocess.TimeoutExpired:
            set_job("failed", f"the {kind} ran past 15 minutes and was stopped")
            return
        finally:
            LOCK.unlink(missing_ok=True)
    if proc.returncode != 0:
        set_job("failed", f"the agent exited {proc.returncode}. See {log.name}")
        return
    set_job("done", "Refreshed" if kind == "refresh" else "Script written")


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
        if path in ("/api/refresh", "/api/prep"):
            with job_lock:
                if job["state"] == "running":
                    self.json_out(409, dict(job))
                    return
            kind = path.rsplit("/", 1)[1]
            set_job("running", "Starting")
            threading.Thread(target=run_agent, args=(kind,), daemon=True).start()
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
