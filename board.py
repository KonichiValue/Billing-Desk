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
                  "asana": {"status", "section", "priority", "category",
                            "severity", "assignee", "project", "completed"},
                  "no_ticket_yet": "why Asana has never heard of this",
                  "last_activity": {"at", "who", "where"},
                  "where_it_stands", "threads",
                  "closes_when": [{"what", "who", "state", "note"}],
                  "internal_ticket": {"name", "url", "build": {...}},
                  "terms": [{"term", "say", "means", "source_url"}],
                  "events": [{"on": "2026-08-24", "at": "15:14", "who", "what",
                              "so_what", "where", "source_url"}],
                  "prep": { ...see below... },
                  "items": [ ...see below... ]
                }
              ]
            }

`sessions` is every room Rei still has to speak in, soonest first. A list,
because an onsite on Wednesday and a standup on Monday are two different
rooms, and `script.for_date` says which one the current script was written for.
A standup that is not running stays in the list with `skipped` set, since "no
standup Wednesday" changes what has to move into Asana instead.

    [{"kind": "standup|onsite|workshop", "date": "2026-08-26", "at": "10:30",
      "label", "title", "place", "focus", "skipped", "reason", "quote",
      "timetable": [{"at": "11:00", "what": "...", "mine": true}],
      "agenda": [{"topic", "why", "owner"}], "bring": ["..."]}]

`timetable` is for a session that is a day rather than a slot. An onsite has a
building to be at, a standup somewhere in the middle of it and an hour when the
real discussion starts, and none of those is the time on the invite. `mine` on a
row is the part that concerns him, and those are the rows the page emphasises.
Leave it out for an ordinary standup, where `at` is the whole story.

`news` is what is moving around Rei that is not one of his tickets: a priority
that changed, an outage upstream, a decision on somebody else's ticket that
lands on his. The desk answers "what do I do" perfectly well without it, and
answers "what has changed around me" not at all, which is the thing you walk
into a room not knowing. Five rows at most, dropped as they go stale.

    [{"topic", "what", "why", "on": "2026-08-24", "source_url"}]

Questions asked from the page do not live here. They sit in `state/asks.json`,
keyed by what they were asked about, because an agent rewriting the board should
never be able to lose the reason a draft says what it says:

    {"asks": [{"id", "ref": "item:8" or "ticket:託送HOLD", "question",
               "asked_at": "2026-08-25 16:36", "answer",
               "state": "running|answered|failed"}]}

`prompt-ask.md` is what answers one, and an answer may change the item it was
asked about. Item state is not part of that: `tick.py` is the only thing that
moves an item, however plainly the question says the work is done.

`meeting_note` and `migration_note` record which standup notes were last folded
in, so a refresh does not re-read them. Same shape: `date`, `found`, `url`.
Billing standup goes in `meeting_note`; Migration daily (Mon-Thu) and Friday
X-Workstream billing mentions go in `migration_note`.

`other_notes` is the same record for a room that is neither: a one-off session
whose note was read once because something in it reached a ticket. Same shape
plus `title` and `gist`, so a later refresh knows it has already been read and
what came out of it.

    [{"date", "title", "url", "found", "gist"}]

`news` is drawn inside Need to know at the top of the work view, along with the
next session and `alert`. One block, because they are one question asked once a
morning, and it folds.

The first line of that block is not stored anywhere. It is counted from the
items every time the page is drawn: how many are his, which one to start on, how
long they add up to, and whether the next room is close enough to matter. It
used to be a sentence an agent wrote, and a sentence written yesterday about a
conversation reads as a riddle this morning.

`alert` is the exception, and it is empty almost every day: something that needs
him inside the hour and is not an item, because there is nothing to do until
somebody else moves. Two sentences that make sense to someone who has read
nothing else, and a link to the message.

    {"what": "...", "source_url": "..."}

`terms` carries the vocabulary of the ticket in both languages: `term` in
English, `say` as TG say it with furigana as `{漢字|かんじ}`, `means` in a
sentence or two that opens with what the thing is. He hears the Japanese in the
room and has two seconds to place it, so the Japanese is not optional.

`glossary` is the short version of the same thing, board-wide, and the renderers
use it rather than the page. A flat map of the Japanese term to two or three
words of English:

    {"閉栓翌日開栓": "open the day after close", "検針日": "meter reading date"}

Every English line on the page gets the meaning put after the first Japanese term
it contains, once per card and once again in the script, since the script is all
that is left in Japanese-only mode. So write the English plainly and leave the
gloss out of it: writing it by hand is how a term ends up explained twice in one
sentence. A term that is not in here is a term he reads without knowing, so add
it when it first appears in something written for him.

`prep` is what the ticket sounds like out loud, and only the speaking view reads
it. It is rebuilt whenever Rei presses Write prep, and it deliberately holds no
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

An item is a piece of work with a life:

            {"id": 3, "title", "prepared", "steps": [], "done_when", "why",
             "state": "todo|waiting|hold|done|sent|dropped",
             "state_at", "state_note", "waits_on", "hold", "draft",
             "where", "link", "urgency", "est_minutes", "opened", "closed_at",
             "after": 17,
             "at_standup", "at_standup_note",
             "history": [{"at", "state", "note"}]}

`after` is the item number this one queues behind, and it is the difference
between a list of five things and one thing to do. Most work on a ticket is a
sequence: the scope cannot be confirmed before the sheet exists, and the sheet
cannot go out before the questions on it are settled. Listing all three as jobs
invents two decisions Rei does not have, and the page stops telling him where to
start. So only the front of a queue is a job. The rest stay on the ticket, folded,
saying which number they follow, and each becomes a job by itself the moment the
one in front of it closes.

Use it only for a real dependency, where doing this one first would be wrong or
impossible. Two jobs that merely happen to be on the same ticket are two jobs.
Two jobs that end in the same message are not two jobs at all: fold them into one
item rather than chaining them, because he sends one message. An `after` pointing
at a closed item is spent and ignored, so nothing has to clean it up.

`steps` is what he actually does, in order, verb first, and it is the one field
an item cannot be useful without. `done_when` is the finished thing in a line,
so he can tell whether he is there. `why` is last on the card and shortest: he
does not need persuading about his own list, he needs to know what to type.

`draft` is the whole of the doing when the step is "send this", so a step that
tells him to ask, tell, confirm or reply and carries no draft is a bug.

`prepared` is the part an agent could do and therefore did. If the steps could
be followed by something without judgement, following them was the agent's job,
and what is left for Rei is checking it, deciding with it or saying it out loud.

    {"what": "one line naming the thing that now exists",
     "conclusion": "one or two plain sentences: what is true, then what it means",
     "built_at": "2026-08-25 11:20",
     "table": {"columns": [], "rows": [[...]]},   optional
     "findings": ["one fact each, so-what first, four at most"],
     "notes": [{"heading": "what kind of information this is", "body": "..."}],
     "unanswered": ["what the work could not settle"],
     "files": [{"label": "Handover sheet, Japanese, PDF",
                "path": "docs/handover-forced-issue-billing.pdf"},
               {"label": "Phase 2 visualisation, Miro",
                "url": "https://miro.com/app/board/..."}],
     "meeting_use": {"label": "Open onsite version",
                     "summary": "what was moved into the script"},
     "sources": [{"label", "url"}]}

All of it is written to be read once. One idea to a sentence, the plain word
over the dense one, numbers and file:line rather than adjectives, and the bottom
line first so he can act on it without reading further. prompt-post.md, "Write
it so he reads it once", carries the standard, and it holds for every card the
app writes. It changes how the work reads, never what is in it: `unanswered`
stays whole and every source stays cited.

The table contains only like-for-like evidence. A stakeholder's desired
outcome, an implementation constraint and a query condition are different kinds
of information, so label them in `notes` rather than dropping them into one
comparison row. A cell written as `{"text": "The one gap", "tone":
"good|gap|warn"}` prints as a verdict instead of prose, so the row that is the
point of the table is findable without reading every cell. One verdict column,
and the reasoning stays in `findings`.

`unanswered` is what the work could not settle, and it is not optional
politeness. Prepared work that hides its own gaps reads as a finished answer,
and he carries it into a room on that basis. Name the thing, and name why it is
open: nobody has been asked, or the answer given was not usable.

`files` is for work that leaves the desk as a document rather than as a message:
a handover sheet, a procedure TG keep open while they work. The document lives
in `docs/` as HTML and goes out as the PDF beside it, built by `make_doc.py`.
The page serves `docs/` at `/doc/`, so the button opens the real file rather
than a copy pasted into the board. Never furigana in one of these: `draft` text
is for Rei reading aloud, a document is for the reader who receives it.

An entry may carry a `url` rather than a `path` when the thing the work produced
cannot live in the repo, a Miro board being the case that forced it. Use it only
for something the work made. Something it merely read is a `sources` row, and
somewhere a conversation is happening is a `threads` row on the ticket.

`meeting_use` links the work product to the same ticket on the What I say view;
the meeting-ready words live in `prep`, not twice on the item.

`closes_when` is every gate between here and a closed ticket, in the order it
has to fall, including the ones that are nobody's item: an engineer being
assigned, a release landing, TG checking the bills that came out after it.
Without it a ticket with no open items reads as finished when it is only quiet.
`state` is `done`, `now` (his), `blocked` or `next` (somebody else's), and `who`
names them. Point `note` at the item number when an item is already tracking the
gate, rather than restating it.

    [{"what": "An engineer assigned to the build", "who": "Kraken CE",
      "state": "next", "note": "The one thing this ticket is waiting on."}]

`no_ticket_yet` is for work he is carrying that Asana has never heard of: agreed
in a Slack thread, real enough to prepare for, and with no gid to hang it on.
The ticket takes a slug for its `id`, leaves `asana` and `asana_url` empty, and
this field says why there is no ticket and what would raise one. The card says
"work in hand" rather than "Asana ticket", so nobody goes looking for a link
that does not exist. Fill it in the moment a ticket is raised and delete it.

`internal_ticket` links the Kraken-side CE build when TG is waiting on code.
`name` and `url` open it. `build` is what the desk prints under Where it stands,
because "queued behind an engineer" is half of where a TG ticket is:

    {"kt": "KT-92085",
     "stage": "refining|queued|building|review|released|verified",
     "asana_status": "Asana's own words for it",
     "engineer": "",                    empty means nobody has picked it up
     "size": "2 SP", "refined_by": "Rie Nakayama", "refinement": "🟢",
     "feature_flag": "Yes|No",          Yes means release and switch-on differ
     "moved_on": "2026-08-24",          Asana modified_at, date only
     "waiting_on": "the one sentence saying why it is not moving",
     "safe_to_say": "the line to TG that carries none of the above"}

`stage` runs one stop past the release because a TG ticket closes when TG have
checked the bills, not when the code lands. All of it is desk only, and
`safe_to_say` is the only part that may be repeated to TG. Never in `prep`.
`none_yet` replaces `build` when no build has been raised, and says why, since
an empty queue is a fact about the ticket too.

An item with a `prepared` block has steps that start after it: read this, take
it into the room, send it. Never steps that redo it.

Only `tick.py` and the agents write here. Renderers read it and never change it.
"""

from __future__ import annotations

import json
import os
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
    # The board is written by agents, so this is the only place a bad shape can be
    # stopped. Two items sharing a number makes "do 20" ambiguous; findings held as
    # dicts takes the whole page down with a TypeError halfway through a card.
    # Refusing to write is the kind failure: the board on disk stays readable, and
    # whoever is holding it gets told what to fix.
    problems = check(board)
    if problems:
        raise ValueError(
            "the board was not written, because it would not render:\n  "
            + "\n  ".join(problems)
            + "\nFix the item in memory and save again. For a new number use "
            "board.next_id(board) rather than setting id by hand."
        )

    path = path or BOARD
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a sibling temp file and rename it into place. The rename is atomic
    # on the same filesystem, so a crash or a full disk mid-write leaves the old
    # board intact rather than truncating the one durable file to nothing.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def items(board: dict) -> list[tuple[dict, dict]]:
    """Every item with the ticket it belongs to."""
    return [(t, i) for t in board.get("tickets", []) for i in t.get("items", [])]


# What each field has to be for the renderers to survive it. The board is written
# by agents rather than by this code, so no amount of typing in Python protects
# it: the check has to happen at the boundary. `prepared.findings` held
# dictionaries once, where every reader expected strings, and the page died with a
# TypeError halfway down a card.
SHAPES: dict[str, type | tuple[type, ...]] = {
    "title": str,
    "why": str,
    "state": str,
    "urgency": str,
    "steps": list,
    "done_when": str,
    "progress_note": str,
    "state_note": str,
    "waits_on": dict,
    "hold": dict,
    "draft": dict,
    "prepared": dict,
    "history": list,
    "est_minutes": (int, float),
    "after": (int, str),
}
LISTS_OF_TEXT = ("steps",)
PREPARED_TEXT = ("findings", "unanswered", "sources", "files")


def check(board: dict) -> list[str]:
    """Everything wrong with the shape of this board, in the words of a fix.

    Not the same job as `audit.py`, which asks whether the board is out of date.
    This asks whether it is the shape the renderers expect, which is the class of
    fault that takes the whole page down rather than making one card wrong.
    """
    bad: list[str] = []
    ids: dict[str, str] = {}

    for ticket, item in items(board):
        where = f"item {item.get('id')} on {ticket.get('ref', '?')}"

        ident = str(item.get("id", ""))
        if not ident:
            bad.append(f"{where}: no id, so nothing can refer to it")
        elif ident in ids:
            bad.append(f"item {ident}: used twice, on {ids[ident]} and {ticket.get('ref')}")
        else:
            ids[ident] = str(ticket.get("ref"))

        for field, want in SHAPES.items():
            value = item.get(field)
            if value is not None and not isinstance(value, want):
                names = getattr(want, "__name__", None) or " or ".join(
                    t.__name__ for t in want
                )
                bad.append(
                    f"{where}: {field} is a {type(value).__name__}, should be {names}"
                )

        for field in LISTS_OF_TEXT:
            for n, entry in enumerate(item.get(field) or [], 1):
                if not isinstance(entry, str):
                    bad.append(
                        f"{where}: {field}[{n}] is a {type(entry).__name__}, "
                        f"should be a plain sentence"
                    )

        prepared = item.get("prepared")
        if isinstance(prepared, dict):
            for field in PREPARED_TEXT:
                for n, entry in enumerate(prepared.get(field) or [], 1):
                    if not isinstance(entry, (str, dict)):
                        bad.append(
                            f"{where}: prepared.{field}[{n}] is a "
                            f"{type(entry).__name__}"
                        )
                    elif isinstance(entry, dict) and field == "findings":
                        bad.append(
                            f"{where}: prepared.findings[{n}] is a dict. Findings "
                            f"are strings; every reader joins them as prose."
                        )

        state = item.get("state", "todo")
        if state not in OPEN_STATES + CLOSED_STATES:
            bad.append(
                f"{where}: state is {state!r}, which no renderer knows. "
                f"One of {', '.join(OPEN_STATES + CLOSED_STATES)}."
            )

    highest = max((int(n) for n in ids if n.isdigit()), default=0)
    if board.get("next_id", 0) <= highest:
        bad.append(
            f"next_id is {board.get('next_id')} but item {highest} exists, so the "
            f"next writer collides. Use board.next_id(b)."
        )
    return bad


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
