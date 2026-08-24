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
              "sessions": [ ...see below... ],
              "script": {"for_date", "at", "built_at", "headline"},
              "news": [ ...see below... ],
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
                  "prep": { ...see below... },
                  "items": [ ...see below... ]
                }
              ]
            }

`sessions` is every room Rei still has to speak in, soonest first. A list,
because an onsite on Wednesday and a standup on Thursday are two different
rooms, and `script.for_date` says which one the current script was written for.
A standup that is not running stays in the list with `skipped` set, since "no
standup Wednesday" changes what has to move into Asana instead.

    [{"kind": "standup|onsite|workshop", "date": "2026-08-26", "at": "10:30",
      "label", "title", "place", "focus", "skipped", "reason", "quote",
      "agenda": [{"topic", "why", "owner"}], "bring": ["..."]}]

`news` is what is moving around Rei that is not one of his tickets: a priority
that changed, an outage upstream, a decision on somebody else's ticket that
lands on his. The desk answers "what do I do" perfectly well without it, and
answers "what has changed around me" not at all, which is the thing you walk
into a room not knowing. Five rows at most, dropped as they go stale.

    [{"topic", "what", "why", "on": "2026-08-24", "source_url"}]

`prep` is what the ticket sounds like out loud, and only the speaking view reads
it. It is rebuilt whenever Rei presses Build script, and it deliberately holds no
status of its own: that view takes `where_it_stands` from the ticket, so a script
can never contradict the desk.

    {"order": 1, "board_position": "3 of 14 on the board",
     "issue": ["plain English, two or three lines"], "why_it_matters",
     "consequences": {"fix_covers", "falls_outside", "accumulates",
                      "who_owns_it", "done_means", "still_open"},
     "open_questions": [{"en", "ja_ruby", "who"}],
     "script": [{"heading": "現状", "heading_en": "Where it stands",
                 "lines": [{"ja_ruby": "{託送|たくそう}...", "en": "..."}]}],
     "decisions": [{"need", "why", "fallback"}],      onsite only
     "pushback": [{"they_say", "say_ja", "say_en"}],   onsite only
     "tg_ask_needed": true, "estimate": "", "unknowns": [], "built_at"}

`decisions` and `pushback` are what an onsite needs and a 15 minute standup does
not: what has to be settled before everyone leaves the room, and the sentence
ready for the objection that stops it being settled.

An item with `at_standup` true is work that has to be spoken about rather than
only done, so it shows on both views: on the desk with a "raise at" pill naming
the session, in the script under the ticket it belongs to.

An item is an action with a life:

            {"id": 3, "title", "why", "detail": [], "state": "todo|waiting|hold|done|
             sent|dropped", "state_at", "state_note", "waits_on", "hold", "draft",
             "where", "link", "urgency", "est_minutes", "opened", "closed_at",
             "at_standup", "at_standup_note",
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
