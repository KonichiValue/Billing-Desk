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
    python3 serve.py --lan 60   answer on the wifi for an hour, for a phone,
                                then go back to loopback by itself
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

import keep

ROOT = Path(__file__).resolve().parent
KEY = secrets.token_urlsafe(16)
TIMEOUT_SECS = 900

job = {"state": "idle", "message": "", "url": "", "at": ""}
job_lock = threading.Lock()

# What the agent is doing this second, for the card that is waiting on it. A
# question takes thirty seconds to two minutes, and a button that says "Sending"
# for all of it is indistinguishable from one that has broken. The agent prints
# as it goes, so the page can show the last thing it said and how long it has
# been going, which is the difference between waiting and wondering.
live = {"since": 0.0, "last": "", "chars": 0}
live_lock = threading.Lock()

# Questions wait in a line rather than being turned away. Asking about one job
# and then noticing something on the next card is the normal way to read the
# page, and "something is already running, ask again" makes him hold the second
# question in his head until the first lands. They still run one at a time: an
# answer that rewrites a draft is a read-modify-write of the whole board, so two
# at once would have one of them silently overwrite the other.
ask_queue: "queue.Queue[tuple[str, str, str, str]]" = queue.Queue()

# What is running right now, so Cancel can stop it. A Cancel that only hid the
# box was the worst version: he thinks he has called it off, the agent keeps
# going, and a minute later it rewrites the draft he changed his mind about.
running_now: dict[str, object] = {"proc": None, "ask_id": ""}
cancelled: set[str] = set()
cancel_lock = threading.Lock()


def cancel_ask(ask_id: str) -> str:
    """Stop a question, whether it is running or still in the line."""
    with cancel_lock:
        cancelled.add(ask_id)
        proc = running_now["proc"] if running_now["ask_id"] == ask_id else None
    if proc is not None:
        try:
            proc.terminate()
        except OSError:
            pass
        return "stopped"
    return "dropped from the queue"


def ask_worker() -> None:
    """Drain the queue, one question at a time, for the life of the server."""
    while True:
        args = ask_queue.get()
        try:
            with cancel_lock:
                dead = args[0] in cancelled
            if dead:
                row = next((r for r in load_asks() if r.get("id") == args[0]), None)
                if row:
                    row.update(state="cancelled", answer="You called this one off.")
                    save_ask(row)
                continue
            run_ask(*args)
        except Exception as exc:  # a thread that dies takes the queue with it
            row = next((r for r in load_asks() if r.get("id") == args[0]), None)
            if row:
                row.update(state="failed", answer=f"Could not run the question: {exc}")
                save_ask(row)
            set_job("failed", f"could not run the question: {exc}")
        finally:
            ask_queue.task_done()


def pending_asks() -> dict[str, str]:
    """Every question not yet answered, by id, so a card can find its own.

    A card used to watch the one global job state, which is wrong the moment two
    things are in flight: an ask that finished while a refresh was starting left
    the card spinning on "Sending" with its answer already written to disk.
    """
    with cancel_lock:
        gone = set(cancelled)
    return {
        str(r.get("id")): str(r.get("state"))
        for r in load_asks()
        if r.get("state") in ("queued", "running") and str(r.get("id")) not in gone
    }


def set_live(last: str = "", add: int = 0, start: bool = False) -> None:
    with live_lock:
        if start:
            live.update(since=time.time(), last="", chars=0)
            return
        if last:
            live["last"] = last
        live["chars"] += add


def clear_live() -> None:
    with live_lock:
        live.update(since=0.0, last="", chars=0)


BOARD = ROOT / "state" / "board.json"
ASKS = ROOT / "state" / "asks.json"
CONFIG = ROOT / "config.json"
asks_lock = threading.Lock()

def icon_src(name: str) -> str:
    """The icon path with the file's own timestamp on it.

    Chrome caches an installed app's icon against the URL it was fetched from,
    so an icon redrawn at the same path never reaches the Dock. Moving the URL
    whenever the file changes is what makes a redraw actually show up.
    """
    icon = ROOT / "app" / name
    stamp = int(icon.stat().st_mtime) if icon.exists() else 0
    return f"/{name}?v={stamp}"


# Chrome reads this when you install the page as an app, and takes the Dock icon
# from it. Without it the installed app wears the Chrome logo. Built per request,
# so redrawing the icon is enough: nothing has to remember to restart the server.
def manifest() -> dict:
    return {
        "name": "Billing Desk",
        "short_name": "Desk",
        "description": "Every open billing ticket, what is left to do, and what to say.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f4f6fa",
        "theme_color": "#0d1524",
        "icons": [
            {"src": icon_src("icon-192.png"), "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": icon_src("icon-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
        ],
    }


render_lock = threading.Lock()
# The board mtime the served desk.md was last rendered from, so a plain reload
# does not redraw a file the browser never sees.
_md_rendered_mtime: float | None = None


def rebuild() -> str:
    """Render the desk and hand back the HTML, so a load is always current.

    Held behind a lock so two overlapping loads do not run two renders into the
    same file at once, which could hand back a half-written page.
    """
    global _md_rendered_mtime
    html = ROOT / "output" / "desk.html"
    with render_lock:
        # desk.html on every load: it carries the "checked N hours ago" line, so
        # it has to be current even when the board itself has not moved.
        subprocess.run(
            [sys.executable, "render_desk.py", str(BOARD), str(html)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        # desk.md is read by chats, never served from here, so only redraw it when
        # the board changed since we last wrote it. A plain reload of the page
        # then costs one render, not two.
        md = ROOT / "output" / "desk.md"
        try:
            bmtime: float | None = BOARD.stat().st_mtime
        except OSError:
            bmtime = None
        if bmtime is None or not md.exists() or _md_rendered_mtime != bmtime:
            subprocess.run(
                [sys.executable, "render_desk_md.py", str(BOARD), str(md)],
                cwd=ROOT,
                check=False,
                stdout=subprocess.DEVNULL,
            )
            _md_rendered_mtime = bmtime
        return html.read_text(encoding="utf-8")


def set_job(state: str, message: str = "", url: str = "") -> None:
    with job_lock:
        job.update(
            state=state, message=message, url=url, at=datetime.now().strftime("%H:%M")
        )


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
URL_IN = re.compile(r"https://\S+")


# The CLI holds its prose to the end in text mode, so a sweep printed nothing
# for as long as it ran and the page had a fixed sentence to show. Asking for
# events instead means every tool call arrives the moment it starts, which is
# what the wait actually consists of.
STREAM = ["--output-format", "stream-json", "--stream-partial-output"]

VERBS = {
    "shell": "Running",
    "read": "Reading",
    "write": "Writing",
    "edit": "Editing",
    "delete": "Deleting",
    "ls": "Listing",
    "grep": "Searching",
    "glob": "Looking for",
    "webSearch": "Searching the web",
    "fetch": "Fetching",
    "readLints": "Checking",
    "todoWrite": "Planning",
    "task": "Handing off to a subagent",
}
HINTS = ("command", "path", "file_path", "target_file", "relative_workspace_path",
         "pattern", "glob_pattern", "query", "search_term", "url", "toolName", "name")

# The same step, said in the words he would use. The log keeps the raw phrase,
# because that is what a slow run is diagnosed from, but the line under the
# spinner is read by someone waiting rather than someone debugging, and
# "mcp asana: get_task_stories" tells him nothing he wanted to know. Tested
# against the raw phrase in order, so the specific cases come before the general.
PLAIN = (
    ("tick.py", "Moving the job"),
    ("audit.py", "Checking what is out of date"),
    ("board.save", "Writing the change"),
    ("digest.py", "Reading the board"),
    ("import board", "Reading the board"),
    ("board.json", "Reading the board"),
    ("asana", "Reading the Asana ticket"),
    ("slack", "Reading the Slack thread"),
    ("notion", "Reading the Notion notes"),
    ("miro", "Reading the Miro board"),
    ("databricks", "Looking at the data"),
    ("kraken-core", "Reading the Kraken code"),
    ("prompt-", "Reading its own instructions"),
    ("docs/", "Reading the working files"),
)


def plain_phrase(phrase: str) -> str:
    """What that step means, for the person watching rather than the log."""
    low = phrase.lower()
    verb = phrase.split(" ", 1)[0].lower()
    # The verb wins over the path, because "Editing docs/..." is a change he is
    # about to see and reporting it as reading would be a lie about the direction.
    if verb in ("editing", "writing", "deleting"):
        return "Writing the change"
    for probe, words in PLAIN:
        if probe in low:
            return words
    if verb in ("reading", "searching", "looking", "listing"):
        return "Reading around the ticket"
    if verb == "running":
        return "Working through it"
    return phrase[:70]


def tool_phrase(call: dict) -> str:
    """One line saying what the agent has just gone off to do.

    The event names the tool in a key like `shellToolCall` and puts its arguments
    under it, so the shape carries what is worth showing without a table of
    every tool the CLI has.
    """
    key = next(iter(call), "")
    kind = key[: -len("ToolCall")] if key.endswith("ToolCall") else key
    args = (call.get(key) or {}).get("args") or {}
    hint = ""
    for name in HINTS:
        value = args.get(name)
        if isinstance(value, str) and value.strip():
            hint = value.strip()
            break
    if kind == "mcp":
        where = args.get("serverName") or args.get("server") or "Tool"
        return f"{where}: {args.get('toolName') or hint or 'call'}"[:120]
    hint = hint.replace(f"{ROOT}/", "").replace(str(ROOT), "the repo")
    verb = VERBS.get(kind) or kind or "Working"
    return (f"{verb} {hint}" if hint else verb)[:120]


def mmss(secs: float) -> str:
    return f"{int(secs) // 60:d}:{int(secs) % 60:02d}"


def read_events(stream, said: list[str], noise: list[str], calls: list[str],
                began: float, fh=None) -> None:
    """Turn the agent's event stream into progress, and into a readable log.

    Three things come out of one pass: the final message, whatever the CLI said
    that was not an event (reconnect notices, warnings), and a timed list of the
    tool calls. The last of those is how a slow sweep is diagnosed later: the log
    shows where the minutes went rather than only what it concluded.
    """
    try:
        for raw in stream:
            clean = ANSI.sub("", raw).strip()
            if not clean:
                continue
            if not clean.startswith("{"):
                noise.append(clean)
                set_live(last=clean[-200:])
                if fh is not None:
                    fh.write(clean + "\n")
                    fh.flush()
                continue
            try:
                event = json.loads(clean)
            except ValueError:
                noise.append(clean)
                continue
            kind = event.get("type")
            if kind == "assistant":
                for part in (event.get("message") or {}).get("content") or []:
                    text = part.get("text") or ""
                    if text:
                        said.append(text)
                        set_live(add=len(text))
                tail = "".join(said)[-200:].replace("\n", " ").strip()
                if tail:
                    set_live(last=tail)
            elif kind == "tool_call" and event.get("subtype") == "started":
                phrase = tool_phrase(event.get("tool_call") or {})
                calls.append(phrase)
                set_live(last=plain_phrase(phrase))
                if fh is not None:
                    fh.write(f"  [{mmss(time.time() - began)}] {phrase}\n")
                    fh.flush()
            elif kind == "result":
                # The whole final message, which is cleaner than the deltas: it
                # is the report without the narration between tool calls.
                whole = event.get("result")
                if isinstance(whole, str) and whole.strip():
                    said[:] = [whole]
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


class Ran(NamedTuple):
    text: str      # the agent's final message
    noise: str     # what the CLI said that was not an event
    code: int | None  # None means it was still going at the timeout
    took: int
    calls: int


def run_stream(cmd: list[str], payload: str, timeout: int, fh=None) -> Ran:
    """One agent run, reported as it goes."""
    began = time.time()
    set_live(start=True)
    # The CLI takes some seconds to come up before it says anything, and a blank
    # progress line in that gap reads as a hang.
    set_live(last="Starting the agent")
    proc = subprocess.Popen(
        cmd + STREAM + [payload],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    with cancel_lock:
        running_now["proc"] = proc
    said: list[str] = []
    noise: list[str] = []
    calls: list[str] = []
    reader = threading.Thread(
        target=read_events, args=(proc.stdout, said, noise, calls, began, fh), daemon=True
    )
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        code = None
    reader.join(timeout=10)
    with cancel_lock:
        running_now["proc"] = None
    return Ran("".join(said).strip(), "\n".join(noise), code,
               round(time.time() - began), len(calls))


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
    "prep": ("prompt-prep.md", "Sweeping everything, then writing your script"),
}

ASK_TIMEOUT_SECS = 420

def ask_model() -> str:
    """Which model answers a question from a card.

    Auto, like every other run here. A question and a change arrive through the
    same box and half of what comes out of it is read by Tokyo Gas, so the answer
    is worth the wait.

    The wait divides in two, and the logs say where: an ask that only answers
    comes back in 11 to 34 seconds, and one that rewrites a draft takes 100 to
    200 with six to nine tool calls. Session startup is the floor of the first
    number, so it is a tenth of a rewrite rather than most of it, and the rest is
    the Japanese itself. Item 17's draft is 4.5KB across `body_ruby` and
    `body_en`, and asking for a simpler version means emitting all of it again.
    No model choice shortens that, which is why the lever worth pulling is in
    `prompt-ask.md`: edit the board by item number in one step, and never rebuild
    pages that a page load redraws anyway.

    `config.json` under `ask` pins one when speed matters more than the wording,
    and `TG_ASK_MODEL` does it for a single question.
    """
    for var in ("TG_ASK_MODEL", "TG_MODEL"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        conf = json.loads(CONFIG.read_text(encoding="utf-8")).get("ask", {})
    except (ValueError, OSError):
        conf = {}
    return conf.get("model") or "auto"


def load_asks() -> list[dict]:
    """Every question asked from a card, and what came back.

    Kept beside the board rather than in it. The board is the work; this is the
    conversation about the work, and an agent rewriting the board should never
    be able to lose it.
    """
    if not ASKS.exists():
        return []
    try:
        return json.loads(ASKS.read_text(encoding="utf-8")).get("asks", [])
    except (ValueError, OSError):
        return []


def save_ask(row: dict) -> None:
    """Write one question, or the answer that arrives minutes later."""
    with asks_lock:
        rows = [r for r in load_asks() if r.get("id") != row.get("id")]
        rows.append(row)
        ASKS.parent.mkdir(exist_ok=True)
        ASKS.write_text(
            json.dumps({"asks": rows[-200:]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def forget_ask(ident: str) -> int:
    """Throw one exchange away, and anything asked off the back of it.

    The record is his. A question he regrets asking, or an answer that turned out
    to be about the wrong job, should not sit on the card forever, and a
    follow-up has no meaning once the thing it followed is gone.
    """
    with asks_lock:
        rows = load_asks()
        doomed = {ident}
        # A follow-up to a follow-up is possible, so keep pulling until nothing
        # new falls in.
        while True:
            more = {
                r.get("id") for r in rows if r.get("parent") in doomed and r.get("id")
            } - doomed
            if not more:
                break
            doomed |= more
        left = [r for r in rows if r.get("id") not in doomed]
        if len(left) == len(rows):
            return 0
        ASKS.parent.mkdir(exist_ok=True)
        ASKS.write_text(
            json.dumps({"asks": left}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return len(rows) - len(left)


def find_subject(ref: str) -> tuple[dict, dict]:
    """The ticket and item a question is about, from `item:8` or `ticket:<ref>`.

    Resolved here rather than trusted from the page, so the prompt is built from
    the board itself and a question can never be asked about something that is
    not on it. `board` is the whole desk, for the questions that are not about
    any one job: what to start on, what tomorrow needs, what he is missing.
    """
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    if ref == "board":
        return {"ref": "board", "title_en": "the whole desk", "items": []}, {}
    kind, _, which = ref.partition(":")
    for ticket in board.get("tickets", []):
        if kind == "ticket" and str(ticket.get("ref")) == which:
            return ticket, {}
        for item in ticket.get("items", []):
            if kind == "item" and str(item.get("id")) == which:
                return ticket, item
    return {}, {}


def board_context(question: str, extra: list[str] | None = None) -> str:
    """A question about the desk itself rather than one job on it.

    "What do I start on", "what does tomorrow need from me", "what am I
    missing": answering those means seeing everything open at once, so this is
    the shape of the whole board rather than one card, and the file itself is one
    read away when the shape is not enough.
    """
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    lines = ["", "---", "", "He is asking about the desk as a whole, not one job."]
    for s in board.get("sessions", [])[:3]:
        lines.append(
            f"Session: {s.get('kind', '')} on {s.get('date', '')} at {s.get('at', '')}"
            f", {s.get('title') or s.get('name', '')}"
            + (" (not running)" if s.get("skipped") else "")
        )
    lines.append("")
    lines.append("Every open job, by ticket:")
    shut = {"done", "dropped"}
    for t in board.get("tickets", []):
        open_items = [i for i in t.get("items", []) if i.get("state") not in shut]
        if not open_items:
            continue
        lines.append(f"  {t.get('ref', '')} ({t.get('title_en', '')}):")
        for i in open_items:
            mins = i.get("est_minutes")
            waits = (i.get("waits_on") or {}).get("who", "")
            lines.append(
                f"    {i.get('id')}. [{i.get('state', 'todo')}] {i.get('title', '')}"
                + (f" ({mins} min)" if mins else "")
                + (f", waiting on {waits}" if waits else "")
                + (f", promised to {i['committed_to']}" if i.get("committed_to") else "")
            )
    for n in board.get("news", [])[:5]:
        lines.append(f"Around him: {n.get('topic', '')}, {n.get('what', '')}")
    lines += [
        "",
        "`state/board.json` has all of it, including the drafts and prepared work,",
        "so read it rather than answering from these titles alone.",
    ]
    lines += extra or []
    lines += [
        "",
        "His question:",
        "",
        question.strip(),
        "",
    ]
    return "\n".join(lines)


def chain_to(parent: str) -> list[dict]:
    """The exchange a follow-up is a follow-up to, and whatever it came off.

    Asked from inside an answer, the question is usually one word: "why", "is
    that in the thread". Those are whole questions there and nowhere else, so
    everything above them travels with it, oldest first.
    """
    rows = {r.get("id"): r for r in load_asks()}
    chain: list[dict] = []
    seen = set()
    at = parent
    while at and at in rows and at not in seen:
        seen.add(at)
        chain.append(rows[at])
        at = rows[at].get("parent")
    return list(reversed(chain))


def followed(chain: list[dict]) -> list[str]:
    if not chain:
        return []
    lines = [
        "",
        "He is following up on this, and the last exchange is the one he means.",
        "Oldest first:",
    ]
    for r in chain:
        lines += [f"  Q: {r.get('question', '')}", f"  A: {r.get('answer', '')}"]
    return lines


ASK_NOTE_CAP = 220


def trim_history(hist: list | None) -> list:
    """History with its note bodies capped.

    A history note now carries the full body of a draft once it was sent, so it
    is not lost when the item comes back to todo. That is the record, but it is
    also the least likely thing a live question needs, and left whole it puts a
    4KB Japanese draft into every ask about the item forever. Cap it: the fact
    stays, the essay goes to board.json.
    """
    out = []
    for h in hist or []:
        note = h.get("note", "")
        if isinstance(note, str) and len(note) > ASK_NOTE_CAP:
            note = note[:ASK_NOTE_CAP] + " …(full text in board.json)"
        out.append({**h, "note": note})
    return out


PREPARED_KEEP = ("what", "conclusion", "built_at", "unanswered", "files")
PREPARED_SUMMARISE = ("table", "findings", "notes", "sources")


def slim_prepared(prep: dict | None) -> dict | None:
    """Prepared work with the bulky evidence summarised, not spelled out.

    The prepared block is the heaviest thing an item carries: item 17's is 12KB
    across its table, findings, notes and sources, and a ticket ask dumps every
    open item's block whole, so 検針票 alone ships 25KB before the question. At
    ticket level the specific row or source is rarely the point, and when it is
    the agent has the item number to read it. Keep the short, load-bearing keys
    (what it is, the conclusion, the honest-gaps list, the files it produced);
    replace the long evidence with a count so the shape is still visible.
    """
    if not prep:
        return prep
    slim = {k: v for k, v in prep.items() if k in PREPARED_KEEP}
    for k in PREPARED_SUMMARISE:
        v = prep.get(k)
        if isinstance(v, list) and v:
            slim[k] = f"{len(v)} {k} (full text in board.json under this item id)"
        elif isinstance(v, dict) and v:
            rows = v.get("rows")
            n = len(rows) if isinstance(rows, list) else len(v)
            slim[k] = f"{n}-row {k} (full text in board.json under this item id)"
    return slim


def ask_item(item: dict, full: bool) -> dict:
    """One item shaped for the prompt: whole for the job he clicked, summarised
    for the others on the ticket beside it."""
    out = dict(item)
    if item.get("history"):
        out["history"] = trim_history(item["history"])
    if not full and item.get("prepared"):
        out["prepared"] = slim_prepared(item["prepared"])
    return out


def ask_context(ref: str, question: str, parent: str = "") -> str:
    """Everything he can see about the job, so he does not have to type it.

    This is the whole point of asking from the card rather than from a fresh
    chat: "is that true about refinement" is a complete question when the draft
    that says it is attached to it.
    """
    ticket, item = find_subject(ref)
    chain = chain_to(parent)
    if ref == "board":
        return board_context(question, followed(chain))
    lines = [
        "",
        "---",
        "",
        f"Ticket: {ticket.get('ref', '')}, {ticket.get('title_en', '')}",
        f"Asana: {ticket.get('asana_url') or 'no ticket raised yet'}",
        f"Where it stands: {ticket.get('where_it_stands', '')}",
    ]
    if ticket.get("threads"):
        lines.append("Threads on this ticket:")
        for th in ticket["threads"]:
            lines.append(
                f"  - {th.get('label', '')} ({th.get('where', '')}): {th.get('url', '')}"
            )
    if item:
        lines += [
            "",
            f"He is asking about item {item.get('id')}: {item.get('title', '')}",
            "",
            "The item, verbatim from the board:",
            "```json",
            json.dumps(ask_item(item, full=True), ensure_ascii=False, indent=2),
            "```",
        ]
    else:
        # Open items in full, closed ones as a line each. A finished job's draft
        # and prepared work can be most of a ticket by weight and none of it by
        # relevance, and everything sent costs him time waiting for the answer.
        shut = {"done", "dropped"}
        items = ticket.get("items", [])
        live_items = [ask_item(i, full=False) for i in items if i.get("state") not in shut]
        lines += [
            "",
            "He is asking about the ticket as a whole. Its open items "
            "(prepared findings summarised; read board.json by item id for the full text):",
            "```json",
            json.dumps(live_items, ensure_ascii=False, indent=2),
            "```",
        ]
        closed = [i for i in items if i.get("state") in shut]
        if closed:
            lines.append("")
            lines.append("Already closed on this ticket, for context only:")
            for i in closed:
                lines.append(
                    f"  {i.get('id')}. [{i.get('state')}] {i.get('title', '')}"
                )
        # The same box sits on the speaking view, where what is on the card is
        # the words rather than the work, so the words travel with the question.
        # Without this, "rewrite what I say here" arrives with nothing to rewrite.
        if ticket.get("prep"):
            board = json.loads(BOARD.read_text(encoding="utf-8"))
            script = board.get("script") or {}
            for s in board.get("sessions", []):
                if s.get("date") == script.get("for_date"):
                    lines.append(
                        f"The script on the board is for the {s.get('kind', '')} on "
                        f"{s.get('date', '')}, {s.get('title') or s.get('name', '')}."
                    )
                    break
            lines += [
                "",
                "What he says about it at that session, the `prep` block verbatim:",
                "```json",
                json.dumps(ticket["prep"], ensure_ascii=False, indent=2),
                "```",
            ]
    above = {r.get("id") for r in chain}
    earlier = [
        r
        for r in load_asks()
        if r.get("ref") == ref and r.get("answer") and r.get("id") not in above
    ]
    if earlier:
        lines += ["", "Already asked about this, oldest first:"]
        for r in earlier[-4:]:
            lines += [f"  Q: {r.get('question', '')}", f"  A: {r.get('answer', '')}"]
    lines += followed(chain)
    lines += ["", "His question:", "", question.strip(), ""]
    return "\n".join(lines)


def run_ask(ask_id: str, ref: str, question: str, parent: str = "") -> None:
    """One question, answered against the board and pinned back onto the card."""
    # The row already exists: the request handler wrote it as `queued` so the card
    # could find itself immediately. Keep its asked_at, which is when he asked
    # rather than when the queue got round to it.
    row = next((r for r in load_asks() if r.get("id") == ask_id), None) or {
        "id": ask_id,
        "ref": ref,
        "question": question.strip(),
        "asked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if parent:
        row["parent"] = parent
    row["state"] = "running"
    save_ask(row)
    with cancel_lock:
        running_now["ask_id"] = ask_id
    # An ask may rewrite the item it was asked about, so it gets a copy too.
    keep.keep("ask")
    prompt = ROOT / "prompt-ask.md"
    if not prompt.exists():
        row.update(state="failed", answer="prompt-ask.md is missing.")
        save_ask(row)
        set_job("failed", "prompt-ask.md is missing")
        return
    left, message = blockers()
    if left:
        row.update(state="failed", answer=message)
        save_ask(row)
        set_job("needs_login", f"{message} Press Log in and approve each one.")
        return
    if lock_held():
        row.update(
            state="failed",
            answer="Something else was already running against the board. Ask again.",
        )
        save_ask(row)
        set_job("failed", "something is already running against the board")
        return

    which = ref.replace("item:", "job ").replace("ticket:", "")
    set_job("running", f"Thinking about {which}")
    model = ask_model()
    cmd = ["cursor-agent", "--print", "--force", "--approve-mcps", "--trust",
           "--workspace", str(ROOT)]
    if model != "auto":
        cmd += ["--model", model]
    LOCK.write_text(f"{os.getpid()} desk-server ask {datetime.now():%H:%M}\n")
    log = ROOT / "logs" / f"ask-{datetime.now():%Y-%m-%d}.log"
    log.parent.mkdir(exist_ok=True)
    try:
        # Streamed rather than collected, so the card can say what it is doing
        # rather than only that it is doing something. The answer is the final
        # message, which keeps the CLI's own chatter off the card.
        ran = run_stream(
            cmd,
            prompt.read_text(encoding="utf-8") + ask_context(ref, question, parent),
            ASK_TIMEOUT_SECS,
        )
        with cancel_lock:
            called_off = ask_id in cancelled
        if called_off:
            # Terminated on purpose, so the non-zero exit below is not a fault
            # and must not be reported to him as one.
            row.update(state="cancelled", answer="You called this one off.")
            save_ask(row)
            set_job("idle", "Cancelled")
            return
        if ran.code is None:
            row.update(state="failed", answer="The question ran past seven minutes and was stopped.")
            save_ask(row)
            set_job("failed", "the question ran past seven minutes and was stopped")
            return
        answer, took = ran.text, ran.took
        # Logged with the model, the wait and the number of steps, so "this is
        # slow" is a number that can be compared rather than a feeling.
        with log.open("a", encoding="utf-8") as fh:
            fh.write(
                f"\n=== {datetime.now():%H:%M:%S} {ref} on {model}, {took}s, "
                f"{ran.calls} tool calls ===\n{question}\n\n{answer}\n"
            )
        if ran.code != 0 or not answer:
            row.update(
                state="failed",
                answer=answer or f"The agent exited {ran.code} without answering.",
            )
            save_ask(row)
            set_job("failed", f"the question came back empty. See {log.name}")
            return
        row.update(state="answered", answer=answer, took_secs=took, model=model)
        save_ask(row)
        set_job("done", f"Answered in {took}s")
    except (OSError, ValueError) as exc:
        # ValueError covers a JSONDecodeError from reading the board mid-write:
        # without it the exception escapes the thread and the card spins on
        # "running" for good.
        row.update(state="failed", answer=f"Could not run the question: {exc}")
        save_ask(row)
        set_job("failed", f"could not run the question: {exc}")
    finally:
        clear_live()
        LOCK.unlink(missing_ok=True)


def agent_model(kind: str) -> str:
    """Which model a refresh or a prep runs on.

    A sweep reads threads and decides where an item stands; it is not writing
    words Tokyo Gas will hear, so it does not need the heaviest model on the
    account. `config.json` names one per kind, `TG_MODEL` overrides either for a
    single run, and leaving both unset falls back to whatever `cursor-agent`
    calls Auto.
    """
    if os.environ.get("TG_MODEL"):
        return os.environ["TG_MODEL"]
    try:
        conf = json.loads(CONFIG.read_text(encoding="utf-8")).get(kind, {})
    except (ValueError, OSError):
        conf = {}
    return conf.get("model") or "auto"


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
    keep.keep(kind)
    log = ROOT / "logs" / f"{kind}-{datetime.now():%Y-%m-%d}.log"
    log.parent.mkdir(exist_ok=True)
    model = agent_model(kind)
    cmd = ["cursor-agent", "--print", "--force", "--approve-mcps", "--trust",
           "--workspace", str(ROOT)]
    if model != "auto":
        cmd += ["--model", model]
    LOCK.write_text(f"{os.getpid()} desk-server {kind} {datetime.now():%H:%M}\n")

    try:
        for attempt in (1, 2):
            with log.open("a", encoding="utf-8") as fh:
                fh.write(f"\n=== {datetime.now():%H:%M:%S} {kind} on {model} ===\n")
                fh.flush()
                ran = run_stream(cmd, prompt.read_text(encoding="utf-8"), TIMEOUT_SECS, fh)
                fh.write(
                    f"\n{ran.text}\n"
                    f"=== {kind} ended after {ran.took}s, {ran.calls} tool calls, "
                    f"exit {ran.code} ===\n"
                )
            if ran.code is None:
                set_job("failed", f"the {kind} ran past 15 minutes and was stopped")
                return
            # A clean exit is not the same as work done. A run whose connection
            # drops can still exit nought having read nothing, and reporting that
            # as "Refreshed" is the worst of the outcomes: he walks into the room
            # on a board that nobody swept.
            if ran.code == 0 and ran.text:
                set_job("done", "Refreshed" if kind == "refresh" else "Script written")
                return
            # Worth running again only when it cannot have changed anything. No
            # tool call means no edit, so nothing can be applied twice; a sweep
            # that stopped halfway must not be repeated, because the board would
            # take the same event on two numbers.
            if attempt == 1 and not ran.text and not ran.calls:
                set_job("running", f"the connection dropped before it started. {running_note}")
                continue
            set_job("failed", failure_note(kind, ran, log.name))
            return
    finally:
        clear_live()
        LOCK.unlink(missing_ok=True)


def failure_note(kind: str, ran: Ran, log_name: str) -> str:
    """Why it stopped, in words, rather than an exit code and a filename.

    The message is read on the page by someone about to walk into a standup, so
    it has to say whether the board was touched and whether pressing the button
    again is worth anything.
    """
    said = f"{ran.text}\n{ran.noise}"
    if not ran.text and not ran.calls:
        return (
            "the connection to the agent dropped twice before it started, so nothing "
            "was read or changed. Press Refresh again, or type refresh in a Cursor chat."
        )
    if not ran.text:
        return (
            f"the {kind} stopped after {ran.calls} steps without reporting, so the board "
            f"may be half swept. Read {log_name} before pressing it again."
        )
    if re.search(r"not logged in|unauthori[sz]ed|401", said, re.I):
        return "the agent is signed out. Press Log in, then Refresh."
    if re.search(r"rate limit|quota|429", said, re.I):
        return "the agent hit a usage limit. Wait a few minutes, then Refresh."
    last = [ln for ln in ANSI.sub("", said).splitlines() if ln.strip()]
    if last:
        return f"the {kind} stopped: {last[-1][:160]} (exit {ran.code}, {log_name})"
    return (
        f"the agent exited {ran.code} without saying anything. The board is as it was. "
        f"See {log_name}"
    )


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
            # The key rides along only for a loopback caller. In --lan mode the
            # server binds the wifi, and handing the key to anything that asks
            # would let any device on the network drive real agent runs.
            client = self.client_address[0] if self.client_address else ""
            local = client in ("127.0.0.1", "::1", "::ffff:127.0.0.1")
            self.json_out(200, {"ok": True, **({"key": KEY} if local else {})})
            return
        if path == "/api/status":
            with job_lock:
                state = dict(job)
            with live_lock:
                if live["since"]:
                    state["seconds"] = int(time.time() - live["since"])
                    state["last"] = live["last"]
                    state["written"] = live["chars"]
            state["asks"] = pending_asks()
            self.json_out(200, state)
            return
        if path == "/manifest.webmanifest":
            self.send(200, json.dumps(manifest()).encode(), "application/manifest+json")
            return
        if path.startswith("/doc/"):
            # A document an item hands him: the handover sheet he gives TG, and
            # anything else the board carries as a file rather than as prose.
            # Basename only, so a path in the board cannot reach out of docs/.
            name = Path(path[len("/doc/"):]).name
            doc = ROOT / "docs" / name
            if not name or not doc.is_file():
                self.send(404, b"no such document", "text/plain")
                return
            kinds = {".pdf": "application/pdf",
                     ".html": "text/html; charset=utf-8",
                     ".md": "text/markdown; charset=utf-8"}
            ctype = kinds.get(doc.suffix.lower(), "application/octet-stream")
            self.send(200, doc.read_bytes(), ctype)
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
        if path == "/api/ask":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, OSError):
                self.json_out(400, {"error": "unreadable question"})
                return
            ref = str(body.get("ref", ""))
            question = str(body.get("question", "")).strip()
            if not question:
                self.json_out(400, {"error": "no question"})
                return
            ticket, _ = find_subject(ref)
            if not ticket:
                self.json_out(404, {"error": f"nothing on the board matches {ref}"})
                return
            parent = str(body.get("parent", "")).strip()
            ask_id = f"{int(time.time())}-{secrets.token_hex(3)}"
            # Written before the reply goes back, so the card can find itself on
            # the very next poll rather than racing the worker for it.
            save_ask(
                {
                    "id": ask_id,
                    "ref": ref,
                    "question": question,
                    "asked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "state": "queued",
                }
                | ({"parent": parent} if parent else {})
            )
            ahead = ask_queue.qsize()
            ask_queue.put((ask_id, ref, question, parent))
            if not ahead:
                set_job("running", "Starting")
            self.json_out(202, {"state": "queued", "id": ask_id, "ahead": ahead})
            return
        if path == "/api/cancel":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, OSError):
                self.json_out(400, {"error": "unreadable"})
                return
            ask_id = str(body.get("id", "")).strip()
            if not ask_id:
                self.json_out(400, {"error": "no question named"})
                return
            self.json_out(200, {"state": "cancelled", "how": cancel_ask(ask_id)})
            return
        if path == "/api/forget":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                ident = str(json.loads(self.rfile.read(length) or b"{}").get("id", ""))
            except (ValueError, OSError):
                self.json_out(400, {"error": "unreadable"})
                return
            if not ident:
                self.json_out(400, {"error": "nothing named"})
                return
            gone = forget_ask(ident)
            if not gone:
                self.json_out(404, {"error": "no such question"})
                return
            self.json_out(200, {"forgot": gone})
            return
        if path == "/api/login":
            threading.Thread(target=start_login, daemon=True).start()
            self.json_out(202, {"state": "needs_login"})
            return
        self.json_out(404, {"error": "not here"})


def lan_address() -> str:
    """The address this machine answers on over the local network.

    Only used to print a URL he can type into a phone. Nothing is published:
    the page still lives on this laptop and still needs the key.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.168.1.1", 1))
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--lan",
        type=int,
        default=0,
        metavar="MINUTES",
        help="answer on the local network for this many minutes, so a phone on "
        "the same wifi can read the page, then go back to loopback on its own. "
        "Key-protected either way, and nothing is published.",
    )
    args = parser.parse_args()

    (ROOT / "state").mkdir(exist_ok=True)
    threading.Thread(target=ask_worker, daemon=True).start()

    # Claim the port before announcing the key. `serve.json` is how `tg` and the
    # browser find this server, so a second copy started by hand while launchd
    # already holds 8787 used to write its key there and then die on the bind,
    # leaving every URL in the file rejected by the server that is actually up.
    # Failing here says the real thing: one is already running.
    try:
        server = ThreadingHTTPServer(
            ("0.0.0.0" if args.lan > 0 else "127.0.0.1", args.port), Handler
        )
    except OSError as exc:
        print(f"port {args.port} is taken, so this one stopped: {exc}", file=sys.stderr)
        print("The desk is already being served. Open it with: tg open", file=sys.stderr)
        return 1

    (ROOT / "state" / "serve.json").write_text(
        json.dumps({"port": args.port, "key": KEY, "started": time.time()}) + "\n",
        encoding="utf-8",
    )
    print(f"http://127.0.0.1:{args.port}/?k={KEY}", flush=True)

    minutes = max(0, args.lan)
    if minutes:
        addr = lan_address()
        if addr:
            print(
                f"phone on the same wifi, for {minutes} min: "
                f"http://{addr}:{args.port}/?k={KEY}",
                flush=True,
            )
        # Off the wifi again on its own. A window left open all week is the
        # thing that turns a convenience into an exposure, and remembering to
        # close it is not a plan.
        threading.Timer(minutes * 60, server.shutdown).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0
        server.server_close()
        print("wifi access closed, loopback only", flush=True)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
