#!/usr/bin/env python3
"""Shared parts of the desk page: styling, furigana, and the common blocks.

Not a page on its own. `render_desk.py` builds the page from the board and
`render_standup.py` builds the standup view inside it, and both take their
styling, their furigana handling and their item lifecycle from here so the two
views cannot drift apart.
"""

from __future__ import annotations

import html
import json
import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

RUBY = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")
KANJI = re.compile(r"[\u4e00-\u9fff]")

# Same four meanings everywhere on the page: yours, blocked, somebody else's,
# closed. Kept in step with the CSS variables of the same names.
TONES = {
    "red": ("#b42318", "#fef4f2", "#fbd2cd"),
    "amber": ("#b25309", "#fff9ed", "#f9dda3"),
    "green": ("#046c46", "#effaf4", "#a8e7c5"),
    "grey": ("#4e5666", "#f4f6fa", "#e5e8ee"),
    "blue": ("#1257c9", "#f0f6ff", "#bedaff"),
}

# An action is with Rei, with somebody else, or finished. Sending a message
# moves it to the middle state rather than closing it, because the reply comes
# back on the same number. Third value is the sort order of the group.
LIFECYCLE = {
    "todo": ("With you", "red", 0),
    "hold": ("Not yet", "amber", 1),
    "waiting": ("Waiting", "blue", 2),
    "done": ("Done", "green", 3),
    "sent": ("Sent", "green", 3),
    "dropped": ("Dropped", "grey", 3),
}
CLOSED_STATES = {"done", "sent", "dropped"}

# Inside a group, the order is what has to happen soonest, not the number. The
# numbers are for typing, and reading the list top to bottom should be the same
# as working down it.
URGENCY = {"today": 0, "this-week": 1, "monitor": 2}


def pressing(item: dict) -> int:
    return URGENCY.get(item.get("urgency", "this-week"), 1)


def index_items(tickets: list[dict]) -> dict[str, dict]:
    """Every item by its number, so `after` can be resolved to the real item."""
    return {
        str(i.get("id")): i for t in tickets for i in t.get("items", [])
    }


def blocked_on(item: dict, index: dict[str, dict]) -> str:
    """The number this item is queued behind, when that one is still open.

    Most work on a ticket is a queue rather than a menu: the scope cannot be
    confirmed before the sheet exists, and the sheet cannot go out before the
    questions are settled. Listing all three as things to do invents two
    decisions Rei does not have, so an item names the one it follows in `after`
    and only the front of the queue is a job.

    An `after` pointing at something already closed is spent, and returns "".
    """
    after = item.get("after")
    if not after:
        return ""
    lead = index.get(str(after))
    if lead is None:
        return ""
    if lead.get("state", "todo") in CLOSED_STATES:
        return ""
    return str(after)


def chain_depth(item: dict, index: dict[str, dict], _seen: set[str] | None = None) -> int:
    """How many open items stand in front of this one.

    Depth 0 is workable now. Anything deeper sorts under the item it waits on,
    so reading a ticket top to bottom is the order the work actually happens.
    A board written by hand can point two items at each other, so the walk stops
    on a number it has already passed rather than recursing forever.
    """
    seen = _seen or {str(item.get("id"))}
    lead_id = blocked_on(item, index)
    if not lead_id or lead_id in seen:
        return 0
    seen.add(lead_id)
    return 1 + chain_depth(index[lead_id], index, seen)


def item_order(item: dict, index: dict[str, dict]) -> tuple:
    """The order items read within one ticket.

    Finished work sits at the top, folded and struck through: it is the record
    of what has already happened on the ticket, and it answers "where are we"
    before the list answers "what now". Then the open work in the order it has
    to happen, front of the queue first.
    """
    st = item_state(item)
    ident = int(item.get("id", 99)) if str(item.get("id", "")).isdigit() else 99
    if st["closed"]:
        return (0, item.get("closed_at", ""), ident)
    return (1, chain_depth(item, index), pressing(item), ident)



def furi(raw: str) -> str:
    """Escape text, then turn {漢字|かんじ} into real ruby annotations.

    Only kanji get a reading. Models reliably over-apply the markup and wrap
    katakana in it too, and ステートメント with すてーとめんと printed above it is
    noise on a line Rei is reading out loud at speed. Dropping the annotation
    here rather than in the prompt means it cannot come back with the next model.
    """
    def one(match: re.Match) -> str:
        base, reading = match.group(1), match.group(2)
        if not KANJI.search(base):
            return base
        return f"<ruby>{base}<rt>{reading}</rt></ruby>"

    return RUBY.sub(one, html.escape(raw or ""))


def esc(raw: Any) -> str:
    return html.escape(str(raw or ""))


CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]")
# Where a Japanese word can turn up inside a sentence written for Rei. Drafts,
# the terms table and thread labels are left alone: a draft is text that goes to
# somebody, and the terms table is the long version of this gloss already.
GLOSS_FIELDS = {
    "en",
    "title_en",
    "what",
    "why",
    "note",
    "title",
    "topic",
    "hint",
    "text",
    "where_it_stands",
    "progress_note",
    "done_when",
    "so_what",
    "issue",
    "why_it_matters",
    "fix_covers",
    "falls_outside",
    "accumulates",
    "verdict",
    "route",
    "steps",
    "body",
    "findings",
    "conclusion",
    "unanswered",
    "focus",
    "bring",
    "headline",
    "need",
    "fallback",
    "done_means",
    "still_open",
    "who_owns_it",
    "they_say",
    "say_en",
    "unknowns",
    "waiting_on",
    "label",
    "gist",
}
GLOSS_SKIP = {"draft", "terms", "threads", "asks"}
# Each of these holds things he reads one at a time: a block of the script, a
# line of the timeline, one job. Each starts the gloss again, because the term he
# needs explaining is the one in front of him, and the explanation being four
# blocks up the card is the same as it not being there.
GLOSS_BLOCKS = {
    "items",
    "events",
    "script",
    "news",
    "closes_when",
    "decisions",
    "pushback",
    "open_questions",
    "sessions",
    "other_notes",
    "agenda",
    "unanswered",
}
# The order the page reads a card, so the gloss lands on the first mention he
# actually sees rather than on one inside a shut fold.
GLOSS_ORDER = (
    "title_en",
    "title",
    "where_it_stands",
    "issue",
    "why_it_matters",
    "script",
    "items",
    "prepared",
    "decisions",
    "pushback",
    "consequences",
    "closes_when",
    "events",
)


def jp_heavy(text: str) -> bool:
    """Is this a Japanese sentence rather than an English one with a word in it?

    A gloss belongs in the English line. Dropping one into the Japanese he reads
    out loud would put an English clause in the middle of a sentence he is
    speaking to Tokyo Gas.
    """
    solid = [c for c in text if not c.isspace()]
    if not solid:
        return False
    return sum(1 for c in solid if CJK.match(c)) / len(solid) > 0.4


def gloss_text(text: str, glossary: dict[str, str], seen: set[str]) -> str:
    """Put the English meaning after the first Japanese term in a line.

    He reads the English to know what the Japanese line says, and a sentence
    that still has 閉栓翌日開栓 in the middle of it has not translated the part he
    needed. Once per term per card: the second mention is a word he now knows,
    and glossing every one of them turns the line back into noise.
    """
    if not text or not CJK.search(text) or jp_heavy(text):
        return text
    # Every occurrence of every term, so a term inside a longer one is left
    # alone: 開栓 sits inside 閉栓翌日開栓, and glossing it there would break the
    # word in half.
    covers = [
        (m.start(), m.end(), len(term))
        for term in glossary
        for m in re.finditer(re.escape(term), text)
    ]
    found = []
    for term in sorted(glossary, key=len, reverse=True):
        if term in seen:
            continue
        size, at = len(term), 0
        while True:
            i = text.find(term, at)
            if i < 0:
                break
            end = i + size
            inside = any(
                a <= i and end <= b and length > size for a, b, length in covers
            )
            if inside:
                at = end
                continue
            # 封書検針票IF is the name of a sheet in TG's workbook, not 封書検針票
            # followed by the letters IF, and a gloss dropped between the two
            # renames their document. A Latin letter or digit straight after the
            # term means the match is part of a longer identifier.
            tail = text[end : end + 1]
            if tail.isascii() and (tail.isalnum() or tail == "_"):
                at = end
                continue
            gloss = glossary[term]
            # The sentence often explains the word itself, as in "検針日
            # reading_date". Saying it twice is worse than not saying it. The
            # test is the one word that carries the gloss: "period" matching
            # "period boundary" would drop the gloss on a line that never says
            # which period it means.
            # The window is at least as long as the gloss, so a long one cannot
            # be re-added past the end of its own words.
            after = text[end : end + max(44, len(gloss) + 8)].lower()
            words = sorted(re.split(r"\W+", gloss.lower()), key=len)
            if words and words[-1] in after:
                seen.add(term)
                break
            found.append((i, end, gloss))
            seen.add(term)
            break
    for _, end, gloss in sorted(found, reverse=True):
        text = f"{text[:end]} ({gloss}){text[end:]}"
    return text


def gloss_tree(node: Any, glossary: dict[str, str], seen: set[str]) -> None:
    """Walk a card and gloss its English, in the order the page reads it.

    `seen` covers one block. A list named in GLOSS_BLOCKS hands each of its
    entries a fresh one, so every script block, every line of the timeline and
    every job explains its own Japanese. Anything nested inside one of those
    entries shares it, which is why two lines of the same block do not both carry
    the same bracket.
    """
    def rank(key: str) -> tuple[int, str]:
        place = GLOSS_ORDER.index(key) if key in GLOSS_ORDER else len(GLOSS_ORDER)
        return place, key

    if isinstance(node, dict):
        for key in sorted(node, key=rank):
            if key in GLOSS_SKIP:
                continue
            value = node[key]
            fresh = key in GLOSS_BLOCKS
            if isinstance(value, str):
                if key in GLOSS_FIELDS:
                    node[key] = gloss_text(value, glossary, seen)
            elif isinstance(value, list):
                if key in GLOSS_FIELDS:
                    node[key] = [
                        gloss_text(v, glossary, seen) if isinstance(v, str) else v
                        for v in value
                    ]
                for entry in node[key]:
                    if not isinstance(entry, str):
                        gloss_tree(entry, glossary, set() if fresh else seen)
            else:
                gloss_tree(value, glossary, set() if fresh else seen)
    elif isinstance(node, list):
        for value in node:
            gloss_tree(value, glossary, seen)


def apply_glossary(board: dict) -> dict:
    """Gloss the whole board once, before either view renders it.

    One pass, and the blocks inside it decide where a gloss starts over. The two
    views are two cards off the same ticket and the script is a third thing
    again, being all that survives Japanese-only mode, so nothing may depend on
    him having read the block above.
    """
    glossary = board.get("glossary") or {}
    if not glossary:
        return board
    for ticket in board.get("tickets", []):
        gloss_tree(ticket, glossary, set())
    for key in ("news", "sessions", "other_notes", "script", "meeting_note"):
        if board.get(key):
            gloss_tree(board[key], glossary, set())
    return board


def plain(raw: str) -> str:
    """Strip furigana markup, leaving just the kanji. For copy buttons."""
    return RUBY.sub(r"\1", raw or "")


def code(raw: Any) -> str:
    """Escape, then let `backticks` become code. For instructions to Rei.

    A step that names `billing.unstatemented-supply-charges` is naming a thing
    he has to type or search for exactly, and a dotted string in running prose
    is where a typo hides.
    """
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(raw))


def opening(word: str) -> str:
    """First letter up, the rest left alone.

    `capitalize` lowercases everything after the first letter, which turned
    "Mon 24 Aug" into "Mon 24 aug" on every day heading on the page.
    """
    return word[:1].upper() + word[1:]


def answered(raw: Any) -> str:
    """What came back from an ask, as prose rather than as its own source.

    An answer is written the way an answer is written: a bold claim, a couple of
    paragraphs, sometimes a short list. Escaped and dropped in whole it arrived
    on the card wearing its asterisks, which made the one thing on the page he
    had asked for the hardest thing on it to read. Only the four marks an answer
    actually uses are honoured, and everything else stays literal.
    """
    text = code(raw)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.S)
    # An answer asked in front of the script comes back as the line to read out,
    # furigana and all. Printed with its braces showing it is not readable, which
    # defeats the point of asking for it there.
    text = RUBY.sub(
        lambda m: (
            f"<ruby>{m.group(1)}<rt>{m.group(2)}</rt></ruby>"
            if KANJI.search(m.group(1))
            else m.group(1)
        ),
        text,
    )
    out, items = [], []

    def flush() -> None:
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        for ln in lines:
            bullet = re.match(r"^(?:[-*\u2022]|\d+\.)\s+(.*)$", ln)
            if bullet:
                items.append(bullet.group(1))
            else:
                flush()
                out.append(f"<p>{ln}</p>")
        flush()
    return "".join(out)


def item_state(item: dict) -> dict:
    """Where one item sits: its state, label, tone, and who is holding it.

    The item carries its own state, because the board outlives the day it was
    written on. A hold is inferred when nothing has been recorded yet.
    """
    state = item.get("state") or ("hold" if item.get("hold") else "todo")
    waits = item.get("waits_on") or {}
    who = waits.get("who", "")
    at = item.get("state_at") or waits.get("since", "")
    label, tone, order = LIFECYCLE.get(state, LIFECYCLE["todo"])
    if state == "waiting" and who:
        label = f"Waiting on {who}"
    return {
        "state": state,
        "label": label,
        "tone": tone,
        "order": order,
        "closed": state in CLOSED_STATES,
        "who": who,
        "at": at,
        "note": item.get("state_note", ""),
        "sent": bool(item.get("sent_by_you")),
    }


def tracked(tickets: list[dict]) -> list[tuple[str, dict, dict]]:
    """Every item as (ticket ref, item, state), yours first, finished last.

    Within a group, an item queued behind another sorts under it, so the top of
    the list is always something Rei can pick up without reading further.
    """
    index = index_items(tickets)
    rows = [
        (t.get("ref", ""), i, item_state(i))
        for t in tickets
        for i in t.get("items", [])
    ]
    return sorted(
        rows,
        key=lambda r: (
            r[2]["order"],
            chain_depth(r[1], index),
            pressing(r[1]),
            r[1].get("id", 99),
        ),
    )


# What Rei is preparing for. Usually the 10:30 standup, sometimes an onsite,
# which is the same tickets with a great deal more riding on each one.
KINDS = {
    "standup": {
        "name": "Standup",
        "tab": "Standup",
        "at": "10:30",
        "what": "the 15 minutes at 10:30",
    },
    "onsite": {
        "name": "Onsite",
        "tab": "Onsite",
        "at": "",
        "what": "a day in the room with TG",
    },
    "workshop": {
        "name": "Workshop",
        "tab": "Workshop",
        "at": "",
        "what": "the session",
    },
}


def a_session(raw: dict) -> dict:
    """Fill in what the kind of session implies, leaving what was written."""
    out = dict(raw)
    kind = out.get("kind") or "standup"
    spec = KINDS.get(kind, KINDS["standup"])
    out["kind"] = kind
    out["name"] = out.get("label") or spec["name"]
    out["tab"] = spec["tab"]
    out["at"] = out.get("at") or spec["at"]
    out["what"] = spec["what"]
    return out


def sessions(board: dict) -> list[dict]:
    """Everything Rei still has to speak at, soonest first.

    A list rather than one field, because an onsite on Wednesday and a standup
    on Monday are two different rooms with two different scripts, and a board
    that can only hold one of them forgets whichever is further away.

    Boards written before this change said `next_standup` and `standup`, so
    those are read too and nothing has to be regenerated to render.
    """
    raw = board.get("sessions")
    if raw is None:
        raw = []
        old = board.get("next_standup") or {}
        if old.get("date"):
            raw.append({"kind": "standup", **old})
        built = board.get("standup") or {}
        if built.get("date") and built.get("date") != old.get("date"):
            raw.append({"kind": "standup", "date": built["date"], "at": built.get("at")})
    today = date.today().isoformat()
    live = [a_session(s) for s in raw if (s.get("date") or "") >= today]
    return sorted(live, key=lambda s: (s.get("date", ""), s.get("at", "")))


def next_live(board: dict) -> dict:
    """The next session that is actually happening."""
    return next((s for s in sessions(board) if not s.get("skipped")), {})


def script_meta(board: dict) -> dict:
    """When the script was written, and the line it opens on."""
    meta = dict(board.get("script") or board.get("standup") or {})
    meta.setdefault("for_date", meta.get("date", ""))
    return meta


def script_session(board: dict) -> dict:
    """The session the current script was written for.

    If the script names a date, that is the room it describes, even when a
    different session is now sooner. Otherwise, the next live one.
    """
    wanted = script_meta(board).get("for_date")
    if wanted:
        match = next((s for s in sessions(board) if s.get("date") == wanted), None)
        if match:
            return match
        return a_session({"kind": "standup", "date": wanted})
    return next_live(board)


def when_words(iso: str, at: str = "") -> str:
    """2026-08-26 becomes "Wed 26 Aug", with the time when there is one."""
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    words = day.strftime("%a %-d %b")
    today = date.today()
    if day == today:
        words = "today"
    elif (day - today).days == 1:
        words = "tomorrow"
    return f"{words}, {at}" if at else words


def short_when(iso: str, at: str = "") -> str:
    """The same day in as few characters as a tab can spare: "Wed 10:30"."""
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    left = (day - date.today()).days
    words = {0: "today", 1: "tomorrow"}.get(left, day.strftime("%a"))
    if left > 6 or left < 0:
        words = day.strftime("%-d %b")
    return f"{words} {at}".strip()


def due_words(iso: str) -> str:
    """A chase or revisit date as a phrase, aged so one that has passed says so.

    The chip at the top of a card is only three words, so the sentence underneath
    is where "and you have not done it" fits. Both come from the stored date, and
    neither rewrites it: the board records when he meant to chase, and the page is
    responsible for saying how that went.
    """
    if not iso:
        return ""
    try:
        day = date.fromisoformat(DATE_IN.search(iso).group(0))
    except (AttributeError, ValueError):
        # Half of these are a condition rather than a date, "only if he raises it
        # again", and "Chase on Only if he raises it again" is not a sentence.
        words = iso.strip().rstrip(".")
        return f"Chase {words[:1].lower()}{words[1:]}."
    late = (date.today() - day).days
    when = day.strftime("%-d %b")
    if late > 0:
        return f"Chase was due {when}, {late} day{'s' if late > 1 else ''} ago."
    if late == 0:
        return "Chase today."
    return f"Chase on {when}."


def day_words(iso: str) -> str:
    """A date as he would say it: today, yesterday, or "Fri 21 Aug"."""
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    back = (date.today() - day).days
    if back == 0:
        return "today"
    if back == 1:
        return "yesterday"
    return day.strftime("%a %-d %b")


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# Everything the page is drawn from. Not the rendered files in `output/`, which
# are written fresh on every load and would change the answer every time.
SOURCES = ("state/board.json", "state/asks.json")


def stamp() -> str:
    """What this page was rendered from, in one short token.

    The page carries it in `data-stamp` and asks the server for it every couple of
    seconds, so `./tick.py 26` in a terminal reloads the browser without him
    going to look for it. Size and modification time rather than a hash of the
    contents, because it is checked often and never has to be right about *what*
    changed, only that something did. `board.save()` renames the file into place,
    so there is no moment where this reads half a write.
    """
    marks = []
    for name in SOURCES + tuple(f"static/{p.name}" for p in sorted(STATIC.glob("*"))):
        try:
            info = (ROOT / name).stat()
            marks.append(f"{info.st_mtime_ns}.{info.st_size}")
        except OSError:
            marks.append("-")
    return hashlib.blake2s("-".join(marks).encode(), digest_size=6).hexdigest()


def asset(name: str) -> str:
    """One stylesheet or script, from a file rather than a Python string literal.

    A third of the renderers used to be CSS and JavaScript held in triple-quoted
    strings. Nothing could see it: no syntax check, no linter, no formatter, and
    the desk script shared its string with `%` formatting, so every modulo in it
    was written `%%`. The polling bug that left a card spinning for six minutes
    with its answer already on disk was a promise chain with no `.catch()`, which
    any linter would have flagged the moment it was typed, and none was looking.

    Read on every render rather than cached, because the render costs 15ms and an
    edit to the CSS should show up on reload without restarting the server.
    """
    return (STATIC / name).read_text(encoding="utf-8")


DATE_IN = re.compile(r"\d{4}-\d{2}-\d{2}")


def when_tag(item: dict, st: dict, sess: dict | None = None) -> tuple[str, str]:
    """When this one is due to move, in two or three words.

    The colour of an item already says whose it is. This says when, which is the
    other half of deciding what to open next, and it is the half that used to
    live buried in a hold note or a chase date three lines down.
    """
    if st["closed"]:
        return "", ""
    hold = item.get("hold") or {}
    waits = item.get("waits_on") or {}

    def day_in(*values: str) -> str:
        for value in values:
            found = DATE_IN.search(value or "")
            if found:
                return short_when(found.group(0))
        return ""

    def days_late(*values: str) -> int | None:
        """Days past the first date in these strings. 0 is today, negative is ahead.

        None means no date was written, which is a different thing from a date
        that has passed and has to read differently on the page.
        """
        for value in values:
            found = DATE_IN.search(value or "")
            if not found:
                continue
            try:
                return (date.today() - date.fromisoformat(found.group(0))).days
            except ValueError:
                return None
        return None

    def owed(word: str, *values: str) -> tuple[str, str] | None:
        """The chip for a date that was set so it would come back round.

        A date in the past is the whole point of writing one down, so it has to
        read as work. Left to `short_when` it comes out "28 Aug" in the same grey
        as a date next week, sorts as though nothing is due, and four days overdue
        looks like a plan he already has. The sweep cannot be relied on to roll
        these forward either, and rolling them forward silently would hide that he
        never chased, so the page ages them instead.
        """
        late = days_late(*values)
        if late is None:
            return None
        if late > 0:
            return f"{word}, {late}d late", "now"
        if late == 0:
            return f"{word} today", "now"
        return f"{word} {day_in(*values)}", "next"

    if st["state"] == "todo":
        if item.get("at_standup") and sess:
            return f'Say it {short_when(sess.get("date", ""))}'.strip(), "next"
        return "Do now", "now"
    if st["state"] == "hold":
        # `until` is often prose rather than a date, so it only ever supplies the
        # fallback wording, never the clock.
        due = owed("Held to", hold.get("revisit", ""))
        if due:
            return due
        day = day_in(hold.get("until", ""))
        return (f"Held to {day}" if day else "Held"), "next"
    if st["state"] == "waiting":
        due = owed("Chase", waits.get("chase_on", ""))
        if due:
            return due
        if item.get("at_standup") and sess:
            return f'Ask {short_when(sess.get("date", ""))}'.strip(), "next"
        return "No chase date", "none"
    return "", ""


ROLE_HINT = {
    "now": "what you do",
    "log": "what happened",
    "say": "what you say",
    "ref": "background",
    "warn": "careful",
}


def section(
    title: str,
    body: str,
    role: str = "ref",
    count: str = "",
    fold: bool = False,
    hint: str = "",
    open_: bool = False,
    remember: str = "",
) -> str:
    """One section of a ticket card, the same shape wherever it is used.

    Every section used to open with the same small grey capitals, which made a
    card one undifferentiated column. The marker colour and the weight now say
    what kind of section it is before the words do.

    `count` is words, never a bare number: "3 open" is a fact, "3" is a riddle.
    A folded section carries a Show or Hide word on the right, because a small
    triangle is not enough to tell you there is anything behind it.

    `open_` is for a section worth reading but worth getting out of the way once
    read, and `remember` keeps that choice across page loads.
    """
    n = f'<span class="n">{esc(count)}</span>' if count else ""
    # A hint is normally two or three words of aside, and small capitals suit
    # that. On a shut fold it is doing different work: it is the fact he came for,
    # so he does not have to open the fold at all. A sentence in capitals reads as
    # shouting, so a long hint on a fold is set as the sentence it is.
    plain_hint = fold and len(hint) > 28
    aside = (
        f'<span class="hint{" long" if plain_hint else ""}">{esc(hint)}</span>'
        if hint
        else ""
    )
    head = f"<h3>{esc(title)}{n}{aside}</h3>"
    if fold:
        keep = f' data-remember="{esc(remember)}"' if remember else ""
        return (
            f'<details class="sub {role}"{" open" if open_ else ""}{keep}>'
            f'<summary>{head}'
            f'<span class="fold-hint"></span></summary>{body}</details>'
        )
    return f'<section class="sub {role}">{head}{body}</section>'


def pill(label: str, tone: str) -> str:
    fg, bg, border = TONES.get(tone, TONES["grey"])
    return (
        f'<span class="pill" style="color:{fg};background:{bg};'
        f'border-color:{border}">{esc(label)}</span>'
    )


def link_btn(url: str, label: str) -> str:
    if not url:
        return ""
    return f'<a class="btn" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def render_script(blocks: list[dict]) -> str:
    if not blocks:
        return '<p class="empty">Nothing to say on this one today.</p>'
    out = []
    for block in blocks:
        lines = []
        for line in block.get("lines", []):
            lines.append(
                f"""
          <div class="jp-line">
            <p class="jp">{furi(line.get("ja_ruby", ""))}</p>
            <p class="en">{esc(line.get("en"))}</p>
          </div>"""
            )
        raw = "\n".join(plain(l.get("ja_ruby", "")) for l in block.get("lines", []))
        out.append(
            f"""
        <div class="jp-block">
          <div class="jp-heading">
            <span class="jp-h-ja">{furi(block.get("heading", ""))}</span>
            <span class="jp-h-en">{esc(block.get("heading_en"))}</span>
            <button class="copy" data-copy="{esc(raw)}">copy</button>
          </div>
          {"".join(lines)}
        </div>"""
        )
    return "".join(out)


def render_questions(questions: list[dict]) -> str:
    if not questions:
        return ""
    out = []
    for q in questions:
        who = q.get("who", "TG")
        out.append(
            f"""
        <li class="q">
          <div class="q-en">{esc(q.get("en"))} {pill(who, "amber" if who == "TG" else "grey")}</div>
          <div class="q-ja">{furi(q.get("ja_ruby", ""))}</div>
        </li>"""
        )
    return f"""
      <section class="sub">
        <h3>Questions I need answered</h3>
        <ul class="qlist">{"".join(out)}</ul>
      </section>"""


def render_drafts(drafts: list[dict]) -> str:
    if not drafts:
        return ""
    out = []
    for d in drafts:
        body = d.get("body_ruby", "")
        is_ja = d.get("language") == "ja"
        rendered = furi(body) if is_ja else esc(body)
        trans = (
            f'<p class="draft-en">{esc(d.get("body_en"))}</p>'
            if is_ja and d.get("body_en")
            else ""
        )
        out.append(
            f"""
        <div class="draft">
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go to thread")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
          </div>
          <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
          {trans}
        </div>"""
        )
    return f"""
      <details class="sub drafts">
        <summary><h3>Draft replies ({len(drafts)})</h3></summary>
        {"".join(out)}
      </details>"""


CONSEQUENCE_ROWS = [
    ("fix_covers", "The fix covers"),
    ("falls_outside", "It does not cover"),
    ("accumulates", "So this piles up"),
    ("who_owns_it", "Owned by"),
    ("done_means", "Cleanup means"),
    ("still_open", "Still undecided"),
]


# Questions asked from the cards, by what they were asked about. A module-level
# store, because the alternative is threading a second file through every render
# function between here and an item, to add one block at the bottom of a card.
# Written once, at load, and read-only after that.
ASKED: dict[str, list[dict]] = {}


def load_asks(path: Path) -> None:
    """Read the questions file, and shrug if it is not there yet."""
    ASKED.clear()
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("asks", [])
    except (OSError, ValueError):
        return
    for row in rows:
        if row.get("ref"):
            ASKED.setdefault(row["ref"], []).append(row)


# The mark on every ask button. Four-pointed sparkles are what this means now,
# so it is recognised before the words are read, and the words then say what it
# does to this card rather than which model is behind it.
SPARK = (
    '<svg class="spark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path d="M12 2.6l1.9 5.1a3 3 0 0 0 1.8 1.8l5.1 1.9-5.1 1.9a3 3 0 0 0-1.8 '
    '1.8L12 20.2l-1.9-5.1a3 3 0 0 0-1.8-1.8L3.2 11.4l5.1-1.9a3 3 0 0 0 1.8-1.8z"/>'
    '<path d="M18.6 2.2l.7 1.9.9.3-.9.4-.7 1.9-.7-1.9-.9-.4.9-.3z"/></svg>'
)

# A starter earns its place by being a thing he actually types, finished enough
# to send as it stands. "What do you mean by" was neither: a dangling fragment he
# had to complete before it did anything, taking up the width of a real one.
STARTERS = (
    "Is this still right?",
    "What is actually left here?",
    "Catch this up with the thread",
    "Who do I need for this?",
    "This is done, close it",
)

# Asked from the speaking view. Same ticket, same thread, so the starters are not
# all about the script: the words are what he is looking at, and the ticket is
# still what he is asking about.
SAY_STARTERS = (
    "Rewrite what I say here",
    "Shorter, I have two minutes",
    "What do I say if they push on the date?",
    "What am I missing?",
    "Is this accurate?",
)

DRAFT_STARTERS = (
    "Rewrite this with the latest from the thread",
    "Shorter",
    "Softer, we are still checking",
    "Is this still right?",
    "I have sent this",
)


def qa_one(
    a: dict, open_: bool, child: bool = False, kids: str = "", foot: bool = True
) -> str:
    """One question and what came back, shut down to a single line.

    Shut, it is the question and when it was asked, which is how he finds the
    exchange he half remembers. Open, it is the answer, whatever he asked next
    about it, and the box to ask the next thing. Two buttons on it: forget this
    one, and follow it up.
    """
    state = a.get("state", "answered")
    body = a.get("answer") or (
        "Thinking. This takes a minute or two, and the page reloads itself."
        if state == "running"
        else "No answer came back."
    )
    ident = esc(a.get("id", ""))
    running = state == "running"
    return f"""
              <li class="qa {esc(state)}{" kid" if child else ""}" data-qa="{ident}">
                <details {"open" if open_ or running else ""}>
                  <summary>
                    <span class="qa-k">{"Then" if child else "You asked"}</span>
                    <span class="qa-q">{esc(a.get("question"))}</span>
                    <span class="qa-when">{esc(a.get("asked_at", ""))}</span>
                    <span class="fold-hint"></span>
                  </summary>
                  <div class="qa-a">{answered(body)}</div>
                  {kids}
                  {qa_foot(ident) if foot and not running else ""}
                </details>
                <button type="button" class="qa-del" data-forget="{ident}"
                        title="Forget this question" aria-label="Forget this question">&times;</button>
              </li>"""


def qa_foot(ident: str) -> str:
    """The way to keep pulling on one answer, inside the answer.

    Without it the next question goes in the box at the foot of the card, where
    it is a new question about the job and the agent has to be told what "it"
    was. Here the exchange goes with it, so "why?" is a whole question.
    """
    return f"""
                  <div class="qa-foot">
                    <button type="button" class="qa-follow">{SPARK}Ask about this answer</button>
                  </div>
                  <div class="fu" data-parent="{ident}" hidden>
                    <textarea rows="2" aria-label="Ask about this answer"
                      placeholder="Why? Or: what would that mean for the onsite?"></textarea>
                    <div class="ask-go">
                      <button type="button" class="ask-send" data-ask-send hidden>Send</button>
                      <button type="button" class="ask-copy">Copy for a chat</button>
                      <button type="button" class="fu-cancel">Cancel</button>
                      <span class="ask-keys">Enter sends &middot; Shift+Enter for a new line</span>
                      <span class="ask-hint"></span>
                    </div>
                  </div>"""


def qa_thread(asks: list[dict]) -> str:
    """Everything asked about one card, newest last, follow-ups under their own.

    Only the newest exchange is open. The rest are one line each, and once there
    are more than three the older ones go behind a single line of their own,
    because the record of what he asked in June should not be what he scrolls
    through to reach today's answer.
    """
    if not asks:
        return ""
    kids: dict[str, list[dict]] = {}
    roots = []
    known = {a.get("id") for a in asks}
    for a in asks:
        parent = a.get("parent")
        if parent and parent in known:
            kids.setdefault(parent, []).append(a)
        else:
            roots.append(a)

    def under(ident: str) -> list[dict]:
        """Everything asked off the back of one question, in the order asked.

        Following up on a follow-up is the normal shape of digging into
        something, and a grandchild hung off a bubble it was never drawn under
        would simply not appear on the page.
        """
        out = []
        for k in kids.get(ident, []):
            out.append(k)
            out += under(k.get("id", ""))
        return out

    def bubble(a: dict, newest: bool) -> str:
        mine = under(a.get("id", ""))
        rows = "".join(
            qa_one(k, newest and i == len(mine) - 1, child=True)
            for i, k in enumerate(mine)
        )
        # The newest thread stands open, and inside it only the newest exchange:
        # what he asked last is what he came back for. One way in per thread, at
        # the foot of that last exchange, because the chain travels with it
        # either way and two identical buttons a line apart is a choice he
        # should not have to make.
        return qa_one(
            a,
            newest,
            kids=f'<ul class="qa-kids">{rows}</ul>' if mine else "",
            foot=not mine,
        )

    live = [bubble(a, i == len(roots) - 1) for i, a in enumerate(roots)]
    if len(live) > 3:
        older, recent = live[:-2], live[-2:]
        n = len(older)
        head = (
            f"""
            <details class="qa-earlier">
              <summary>{n} earlier question{"" if n == 1 else "s"} on this card
                <span class="fold-hint"></span></summary>
              <ul class="qa-list">{"".join(older)}</ul>
            </details>"""
        )
        return head + f'<ul class="qa-list">{"".join(recent)}</ul>'
    return f'<ul class="qa-list">{"".join(live)}</ul>'


def ask_block(
    ref: str,
    label: str,
    asks: list[dict],
    lead: str = "",
    has_draft: bool = False,
    kind: str = "work",
) -> str:
    """The chat for one job, on the job.

    Same box does both halves of the same conversation: "what do you mean by
    稼働確認" and "rewrite this with the latest from the refinement thread, and
    tell Tanaka-san we are still checking". Asked in a fresh chat, either one
    starts with him explaining which draft he means, and that explaining is why
    the question does not get asked.

    The answers stay on the card. A chat window is gone by tomorrow, and the
    reason a draft says what it says is worth having next to the draft.

    `kind` is which view is asking. The box is the same box and the record is the
    same record, so a question asked in front of the script is on the card on the
    work view too. Only the starters and the example change, because in front of
    the script what he wants changed is the words.
    """
    thread = [qa_thread(asks)]
    say = kind == "say"
    starters = SAY_STARTERS if say else DRAFT_STARTERS if has_draft else STARTERS
    chips = "".join(
        f'<button type="button" class="qa-chip" data-fill="{esc(s)}">{esc(s)}</button>'
        for s in starters
    )
    hint = (
        "Anything on this ticket, not only the words: it knows the jobs, the "
        "drafts, what moved, what you say at the next session and what you asked "
        "before, and it can read the threads. Same thread as the work view."
        if say
        else "Ask it anything, tell it what to change, or tell it where this now "
        "stands and it will move it. It knows this ticket, this job, the draft "
        "and what you asked before, and it can read the threads. It never sends "
        "anything."
    )
    eg = (
        "Rewrite the second line in plainer Japanese, and say we are still "
        "checking the date"
        if say
        else "Rewrite this with the latest from the refinement thread, and tell "
        "Tanaka-san we are still checking"
    )
    n = len(asks)
    return f"""
            <div class="ask" data-ask="{esc(ref)}" data-ask-lead="{esc(lead)}">
              {"".join(thread)}
              <div class="ask-bar">
                <button type="button" class="ask-open">{SPARK}Ask or change on
                  <span class="ask-of">{esc(label)}</span></button>
                {f'<span class="ask-n">{n} asked</span>' if asks else ""}
              </div>
              <div class="ask-box" hidden>
                <p class="ask-lede">{esc(hint)}</p>
                <textarea rows="2" aria-label="Ask or change on {esc(label)}"
                  placeholder="{esc(eg)}"></textarea>
                <div class="ask-chips">{chips}</div>
                <div class="ask-go">
                  <button type="button" class="ask-send" data-ask-send hidden>Send</button>
                  <button type="button" class="ask-copy">Copy for a chat</button>
                  <button type="button" class="ask-cancel">Cancel</button>
                  <span class="ask-keys">Enter sends &middot; Shift+Enter for a new line</span>
                  <span class="ask-hint"></span>
                </div>
              </div>
            </div>"""


def render_consequences(c: dict, ref: str = "") -> str:
    """The scope of a fix, and what happens to everything outside it.

    This is where TG's questions come from, so it renders even when half the
    fields are blank. Folded, because it is what he reaches for when they push,
    not what he reads before speaking, and six rows of it on every card was two
    thousand pixels between him and the next thing he says.
    """
    if not isinstance(c, dict):
        return ""
    rows = [(label, c.get(key)) for key, label in CONSEQUENCE_ROWS if c.get(key)]
    if not rows:
        return ""
    items = "".join(
        f'<div class="cons-row"><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>'
        for label, value in rows
    )
    return section(
        "Scope, and what falls outside it",
        f'<dl class="cons-list">{items}</dl>',
        role="cons",
        count=f"{len(rows)} rows",
        hint="for when they push on scope",
        fold=True,
        remember=f"cons-{ref}",
    )



