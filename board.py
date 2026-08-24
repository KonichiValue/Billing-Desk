#!/usr/bin/env python3
"""The board: every open TG billing ticket, and every item of work on it.

This is the one durable file. Days come and go, the standup happens or does
not, but a ticket stays open until Asana says otherwise and an item keeps its
number until it is closed. That is the difference between a record of a meeting
and a to-do list you can actually work from.

Shape of `state/board.json`:

    {
      "version": 1,
      "checked_at": "2026-08-24T18:20:00+09:00",
      "next_id": 8,
      "tickets": [
        {
          "id": "1217430352217964",        Asana gid, so nothing is duplicated
          "ref": "請求未発行",              short tag Rei uses out loud
          "title_en", "title_ja", "asana_url",
          "asana": {"status", "section", "priority", "assignee", "project"},
          "last_activity": {"at", "who", "where"},
          "where_it_stands", "terms", "threads", "internal_ticket",
          "events": [{"on": "2026-08-24", "at": "15:14", "who", "what",
                      "so_what", "where", "source_url"}],
          "items": [ ...see below... ]
        }
      ]
    }

An item is an action with a life:

    {"id": 3, "title", "why", "detail": [], "state": "todo|waiting|hold|done|
     sent|dropped", "state_at", "state_note", "waits_on", "hold", "draft",
     "where", "link", "urgency", "est_minutes", "opened", "closed_at",
     "history": [{"at", "state", "note"}]}

Only `tick.py` and the agents write here. Renderers read it and never change it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOARD = ROOT / "state" / "board.json"

OPEN_STATES = ("todo", "hold", "waiting")
CLOSED_STATES = ("done", "sent", "dropped")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path: Path | None = None) -> dict:
    path = path or BOARD
    if not path.exists():
        return {"version": 1, "checked_at": "", "next_id": 1, "tickets": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(board: dict, path: Path | None = None) -> None:
    path = path or BOARD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def items(board: dict) -> list[tuple[dict, dict]]:
    """Every item with the ticket it belongs to."""
    return [(t, i) for t in board.get("tickets", []) for i in t.get("items", [])]


def by_id(board: dict, item_id: str | int) -> tuple[dict, dict] | tuple[None, None]:
    for ticket, item in items(board):
        if str(item.get("id")) == str(item_id):
            return ticket, item
    return None, None


def next_id(board: dict) -> int:
    """Numbers are never reused, so 'do 4' means the same thing next week."""
    used = [int(i.get("id", 0)) for _, i in items(board)]
    nid = max(board.get("next_id", 1), max(used, default=0) + 1)
    board["next_id"] = nid + 1
    return nid


def set_state(item: dict, state: str, note: str = "", who: str = "") -> None:
    stamp = datetime.now().strftime("%H:%M")
    item["state"] = state
    item["state_at"] = stamp
    item["state_note"] = note
    if who:
        item.setdefault("waits_on", {})["who"] = who
        item["waits_on"].setdefault("since", stamp)
    if state in CLOSED_STATES:
        item["closed_at"] = now()
    else:
        item.pop("closed_at", None)
    item.setdefault("history", []).append(
        {"at": now(), "state": state, "note": note or (f"with {who}" if who else "")}
    )


def is_open(item: dict) -> bool:
    return item.get("state", "todo") in OPEN_STATES


def closed_today(item: dict) -> bool:
    closed = item.get("closed_at", "")
    return bool(closed) and closed[:10] == datetime.now().strftime("%Y-%m-%d")
