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

STARTERS = (
    "Is this accurate?",
    "What do you mean by",
    "Who should I confirm this with?",
    "Check this against the code",
    "What am I missing?",
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
    "Is this accurate?",
    "What am I missing?",
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
        else "Ask it anything, or tell it what to change. It knows this ticket, "
        "this job, the draft and what you asked before, and it can read the "
        "threads."
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


CSS = """
/* One neutral ramp, one accent that changes with the view, and four semantic
   colours that only ever mean one thing: red is yours, amber is blocked, blue
   is with somebody else, green is closed. Nothing else gets to be coloured, so
   colour on this page always carries information. */
:root{
--ink:#151a23;--mut:#4e5666;--soft:#79818f;--line:#e5e8ee;--hair:#f1f3f7;
--card:#fff;--page:#f4f6fa;--head:#0d1524;--head-2:#1a2740;
--accent:#0b5cd5;--accent-bg:#eff5ff;--accent-line:#c3daff;--accent-ink:#0a3d94;
--red:#b42318;--red-bg:#fef4f2;--red-line:#fbd2cd;
--amber:#b25309;--amber-bg:#fff9ed;--amber-line:#f9dda3;--amber-ink:#8a3d05;
--green:#046c46;--green-bg:#effaf4;--green-line:#a8e7c5;
--blue:#1257c9;--blue-bg:#f0f6ff;--blue-line:#bedaff;
/* Asking, and what came back. Its own colour, because an answer from the desk
   is neither the work nor the words: it is the thing you did not know. */
--plum:#7c3aed;--plum-bg:#f7f5ff;--plum-line:#ddd6fe;--plum-ink:#5b21b6;
--shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06);
--lift:0 2px 4px rgba(16,24,40,.06),0 8px 20px rgba(16,24,40,.06)}
/* The script view is a different room: warmer paper, plum accent. You can tell
   which view you are in from across the desk, without reading a tab. */
body[data-view="standup"]{--accent:#9c1b85;--accent-bg:#fdf1fa;--accent-line:#f1c3e6;
--accent-ink:#78116a;--page:#faf6f9}
*{box-sizing:border-box}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.views button:focus-visible{outline-color:#fff}
body{margin:0;background:var(--page);color:var(--ink);
font:15.5px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans",
"Noto Sans JP",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:22px 20px 90px}
/* The script is read out loud, so it gets a narrower column than the desk. */
body[data-view="standup"] .wrap{max-width:840px}

/* Header. Dark, because the switcher has to be the most findable thing here.
   Its own layer, and the jump bar below it too. Two stacked sticky bars, one of
   them blurring what is behind it, had the browser repainting both on every
   frame of a fast scroll, and the header flickered while it caught up. */
header.top{position:sticky;top:0;z-index:30;
background:linear-gradient(180deg,var(--head-2),var(--head));color:#e6ecf7;
box-shadow:inset 0 -1px 0 rgba(255,255,255,.06),0 4px 16px rgba(9,14,26,.14);
transform:translateZ(0);will-change:transform;backface-visibility:hidden}
/* Wider than the page it sits over: this row is navigation, not prose, and it
   has to hold the tabs and the buttons without wrapping. One line tall, since
   every pixel here is taken off the top of what he is actually reading. */
.top-in{max-width:1180px;margin:0 auto;padding:4px 20px;display:flex;
align-items:center;gap:10px;flex-wrap:wrap}
/* One height for everything in this row, so no single control can push the bar
   taller than the tabs need. */
.top .btn,.toggle,.refresh,#countdown,.views button{height:26px;box-sizing:border-box;
display:inline-flex;align-items:center;line-height:1}
.brand{display:flex;align-items:center;gap:8px}
.brand img{width:20px;height:20px;border-radius:6px;display:block}
/* The name of the page, kept for the tab strip and for a screen reader but not
   drawn: the icon says which desk this is, the tabs say which half of it, and
   the width the words cost is the difference between a bar that stays one line
   and one that grows a second. */
.top h1{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
clip-path:inset(50%);white-space:nowrap;border:0}
.top .date{color:#8a9bb8;font-size:12px;white-space:nowrap}
/* Hours old means a reply may have landed unseen, which is worth a colour. */
.top .date.old{color:#f4c27a}
.top .btn{color:#c9d6ea;border-color:rgba(255,255,255,.16);
background:rgba(255,255,255,.07);font-size:12px;padding:0 10px}
.top .btn:hover{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.28);
color:#fff}
.acts{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
justify-content:flex-end}
#countdown{font-variant-numeric:tabular-nums;font-weight:650;font-size:12.5px;
padding:0 10px;border-radius:7px;color:#dae4f5;background:rgba(255,255,255,.09);
border:1px solid rgba(255,255,255,.14)}
#countdown:empty{display:none}
#countdown.soon{background:#fee4e2;border-color:#fda29b;color:#912018}
.toggle{font:600 12px/1 inherit;padding:0 10px;border-radius:7px;
border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.07);
cursor:pointer;color:#c9d6ea}
.toggle:hover{background:rgba(255,255,255,.14);color:#fff}
/* Stripping the page back to the Japanese is only a thing you want while
   speaking, so the button lives in that view. */
body[data-view="desk"] #scriptonly{display:none}

/* Two views, one page. Big target, live count, and the key that switches it. */
.views{display:flex;gap:3px;padding:3px;background:rgba(255,255,255,.08);
border:1px solid rgba(255,255,255,.10);border-radius:10px}
.views button{gap:7px;font:inherit;padding:0 11px;
border:0;border-radius:8px;background:none;color:#a9b8d2;cursor:pointer;
text-align:left;white-space:nowrap}
.views button:hover{color:#fff;background:rgba(255,255,255,.07)}
.views button[aria-selected="true"]{background:#fff;color:#0d1524;
box-shadow:0 1px 3px rgba(9,14,26,.4)}
.views .lbl{font-size:13px;font-weight:650;letter-spacing:-.005em}
/* The room this script is for, alongside the label rather than under it, so the
   whole bar stays one line tall. No rule between the two: it read as a border on
   the tab rather than a divider between two words. */
.views .sub{font-size:11.5px;font-weight:550;opacity:.62;padding-left:8px}
.views .k{flex:none;font:700 10px/14px inherit;min-width:14px;text-align:center;
border-radius:4px;background:rgba(255,255,255,.13);color:#c2cee3}
.views button[aria-selected="true"] .k{background:#eef1f6;color:#6b7789}
.views .badge{flex:none;min-width:17px;padding:0 5px;border-radius:9px;
background:#e0483b;color:#fff;font:700 10.5px/17px inherit;text-align:center}
.views button[aria-selected="true"] .badge{background:var(--red);color:#fff}
.views .badge.quiet{background:rgba(255,255,255,.16);color:#dbe4f2}
body[data-view="desk"] #view-standup,body[data-view="standup"] #view-desk{display:none}

/* Cards. Every panel on both views is the same object. */
.tk,.st-tk,.track,.panel,.st-run,.st-empty,.gaps{background:var(--card);
border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
.st-lead{background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--accent);border-radius:13px;padding:16px 20px;
margin-bottom:20px;box-shadow:var(--shadow)}
.st-lead p{margin:0;font-size:17px;line-height:1.5;font-weight:550;
letter-spacing:-.01em}
h2.tickets-h{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;
color:var(--soft);margin:28px 0 11px;font-weight:700}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;
border-radius:20px;border:1px solid;letter-spacing:.01em;white-space:nowrap}
.btn{font-size:12.5px;text-decoration:none;color:var(--accent);
border:1px solid var(--line);background:#fff;padding:4px 10px;border-radius:7px;
white-space:nowrap;font-weight:550}
.btn:hover{border-color:var(--accent-line);background:var(--accent-bg)}
.tag{display:inline-block;font-size:12.5px;font-weight:700;padding:2px 9px;
border-radius:6px;background:var(--accent-bg);color:var(--accent-ink);
margin-right:8px;vertical-align:2px;letter-spacing:0}
.est{color:var(--green);font-weight:600}
/* When a thing is due to move. Deliberately quiet next to the state colour:
   whose it is comes first, when it moves comes second. */
.when{flex:none;font-size:11.5px;font-weight:700;color:var(--soft);
white-space:nowrap;letter-spacing:.01em}
.when.now{color:var(--red)}
.when.next{color:var(--amber)}
.when.none{color:#9aa3b2;font-weight:600;font-style:italic}

/* Sections inside a card. The marker bar says what kind of section it is, so a
   card reads as parts rather than one column of identical grey capitals. */
.sub{padding:16px 0;border-bottom:1px solid var(--hair)}
.tk>*:last-child,.st-tk>*:last-child{border-bottom:0;padding-bottom:0}
.sub h3{font-size:12.5px;letter-spacing:.005em;color:var(--mut);margin:0 0 10px;
font-weight:750;display:inline-flex;align-items:center;gap:9px;vertical-align:middle;
text-transform:none;width:calc(100% - 22px)}
.sub h3:before{content:"";flex:none;width:3px;height:14px;border-radius:2px;
background:var(--line)}
.sub h3 .n{font-size:11px;font-weight:700;color:var(--soft);background:var(--hair);
border:1px solid var(--line);border-radius:20px;padding:0 7px}
.sub h3 .hint{margin-left:auto;font-size:11px;font-weight:600;color:#9aa3b2;
text-transform:uppercase;letter-spacing:.06em}
/* A hint long enough to be a sentence is set as one, and is allowed to be the
   thing you read on a shut fold. */
.sub h3 .hint.long{text-transform:none;letter-spacing:0;font-size:12px;
font-weight:500;color:var(--mut);text-align:right}
/* On a folded section the hint runs into the Show word, so it gives way. */
details.sub>summary>h3 .hint{margin-right:10px}
/* Red is the work, accent is the talking, grey is background you can skip. */
.sub.now h3{color:var(--ink);font-size:14.5px;letter-spacing:-.01em}
.sub.now h3:before{background:var(--red);height:17px;width:4px}
.sub.say h3,.sub.key h3{color:var(--accent-ink);font-size:14.5px;letter-spacing:-.01em}
.sub.say h3:before,.sub.key h3:before{background:var(--accent);height:17px;width:4px}
.sub.log h3:before{background:var(--accent-line)}
.sub.warn h3:before{background:var(--amber)}
.sub.ref h3{color:var(--soft)}
.sub.ask h3{color:var(--soft)}
.sub.ask h3:before{background:var(--plum,#8b5cf6)}
.sub.cons h3{color:var(--soft)}
.sub.cons h3:before{background:var(--amber-line)}
details>summary{cursor:pointer;list-style:none;padding:15px 0 8px}
details>summary::-webkit-details-marker{display:none}
details.sub{padding-top:0}
/* A folded section is one row: the marker, the words, the count, and a word
   saying whether there is anything behind it. */
details.sub>summary{display:flex;align-items:center;padding:14px 10px;
margin:0 -10px;border-radius:9px}
details.sub>summary:hover{background:var(--hair)}
details.sub[open]>summary{padding-bottom:8px}
details.sub>summary>h3{margin:0;width:auto;flex:1}
details.sub>summary:hover .fold-hint{color:var(--accent);border-color:var(--accent-line)}
/* Say Show or Hide in words. A triangle alone does not tell you there is
   anything behind it, which is how a folded section reads as an empty one. */
.fold-hint{flex:none;margin-left:auto;font:650 9.5px/1 inherit;
text-transform:uppercase;letter-spacing:.06em;color:var(--soft);
border:1px solid var(--line);border-radius:4px;padding:3px 5px;background:#fff}
.fold-hint:after{content:"Show"}
details[open]>summary .fold-hint:after{content:"Hide"}
.status,.st-stands{margin:0;font-size:15px;color:var(--ink)}
.matters{margin:10px 0 0;padding:9px 13px;background:var(--accent-bg);
border:1px solid var(--accent-line);border-radius:8px;font-size:14px;
color:var(--accent-ink)}
.cons-list{margin:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.cons-row{display:flex;background:#fff;align-items:baseline}
.cons-row dt{flex:none;width:152px;padding:9px 13px;font-size:11.5px;
font-weight:700;color:var(--soft);background:#fbfcfe;text-transform:uppercase;
letter-spacing:.04em}
.cons-row dd{flex:1;min-width:0;margin:0;padding:9px 13px;font-size:14px}
.cons-row:last-child dd{color:var(--amber);font-weight:550}

/* The spoken script. Smaller than it was: this is read at speed, and 19px with
   a reading above it is already taller than a normal line. */
.jp-block{margin-bottom:16px}
.jp-heading{display:flex;align-items:baseline;gap:10px;margin-bottom:8px;
padding-bottom:5px;border-bottom:1px solid var(--accent-line)}
.jp-h-ja{font-size:15px;font-weight:700;color:var(--accent-ink)}
.jp-h-en{font-size:11.5px;color:var(--soft);text-transform:uppercase;
letter-spacing:.06em;font-weight:600}
.copy{margin-left:auto;font:600 11px/1 inherit;color:var(--soft);background:#fff;
border:1px solid var(--line);border-radius:6px;padding:4px 8px;cursor:pointer}
.copy:hover{color:var(--accent);border-color:var(--accent-line)}
.jp-line{margin-bottom:10px;padding-left:12px;border-left:3px solid var(--accent-line)}
.jp{margin:0;font-size:17.5px;line-height:1.9;letter-spacing:.005em}
ruby rt{font-size:.48em;color:var(--accent);font-weight:600;letter-spacing:0}
.en{margin:2px 0 0;font-size:13px;color:var(--soft);line-height:1.45}
.qlist{list-style:none;margin:0;padding:0}
.q{padding:9px 0;border-bottom:1px dashed var(--line)}
.q:last-child{border-bottom:0}
.q-en{font-weight:600;font-size:14.5px;display:flex;gap:8px;align-items:center;
flex-wrap:wrap}
.q-ja{font-size:16px;line-height:1.85;margin-top:3px;color:var(--mut)}

/* Drafts. Monospace-free, but plain enough that pasting is the obvious move. */
.draft{border:1px solid var(--line);border-radius:10px;margin-bottom:11px;
overflow:hidden}
.draft-head{display:flex;gap:9px;align-items:center;padding:8px 12px;
background:#fbfcfe;border-bottom:1px solid var(--line);font-size:12.5px;
color:var(--mut);font-weight:550}
.draft-body{padding:13px;white-space:pre-wrap;font-size:14.5px;line-height:1.6}
.draft-body.ja{font-size:15px;line-height:1.9}
.draft-en{margin:0;padding:0 13px 13px;font-size:13px;color:var(--soft)}
.warn{background:var(--amber-bg);border:1px solid var(--amber-line);
border-radius:10px;padding:12px 15px;margin-top:15px}
.warn h3{color:var(--amber)}
.warn ul{margin:6px 0 0;padding-left:18px;font-size:14px;color:var(--amber-ink)}
.empty{color:var(--soft);font-style:italic;margin:0;font-size:14.5px}
.gaps{padding:16px 20px;margin-top:22px}
.gaps h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;
color:var(--soft);margin:0;display:inline-block;font-weight:700}
.gaps ul{margin:8px 0 0;padding-left:18px}
.foot{text-align:center;color:var(--soft);font-size:12px;margin-top:28px}
.keys{color:#7b8cab;font-size:11px}

/* Getting somewhere fast. The chips are the obvious way and cost no learning;
   the finder is the fast way once you know it is there. */
/* No frost on this one any more. A blurred sticky bar under a sticky header had
   the compositor re-sampling what was behind it every frame, which is what made
   the dark bar above stutter on a fast scroll, and at this opacity there was
   never anything to see through it. */
.jump{position:sticky;top:42px;z-index:20;display:flex;gap:6px;align-items:center;
flex-wrap:wrap;margin:0 0 16px;padding:7px 11px;border:1px solid var(--line);
border-radius:11px;background:#fbfcfe;box-shadow:var(--shadow);
transform:translateZ(0);will-change:transform;backface-visibility:hidden}
.jump .lab{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;
color:var(--soft);font-weight:700;padding-right:2px}
.jump a{font-size:12.5px;font-weight:600;color:var(--mut);text-decoration:none;
padding:3px 9px;border-radius:7px;border:1px solid transparent;white-space:nowrap}
.jump a:hover{background:var(--hair);color:var(--ink)}
.jump a.on{background:var(--accent-bg);color:var(--accent-ink);
border-color:var(--accent-line)}
.jump a .c{font-size:10.5px;font-weight:700;color:var(--red);margin-left:5px}
.jump a .ord{font-size:10.5px;font-weight:600;color:var(--soft);margin-left:6px}
.jump .find{margin-left:auto;font:600 11.5px/1 inherit;color:var(--soft);
background:#fff;border:1px solid var(--line);border-radius:7px;padding:5px 9px;
cursor:pointer;display:flex;gap:6px;align-items:center}
.jump .find:hover{color:var(--accent);border-color:var(--accent-line)}
kbd{font:700 10.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
background:var(--hair);border:1px solid var(--line);border-bottom-width:2px;
border-radius:4px;padding:3px 5px;color:var(--mut)}

/* The finder. Type a ticket, a number or a word and land on it. */
.pal{position:fixed;inset:0;z-index:60;background:rgba(9,14,26,.44);
display:flex;align-items:flex-start;justify-content:center;padding:11vh 16px 16px}
.pal-box{width:min(640px,100%);background:#fff;border-radius:15px;
box-shadow:0 24px 60px rgba(9,14,26,.35);overflow:hidden;display:flex;
flex-direction:column;max-height:74vh}
.pal input{border:0;border-bottom:1px solid var(--line);padding:16px 19px;
font:16px/1.4 inherit;outline:0;color:var(--ink)}
.pal ul{list-style:none;margin:0;padding:7px;overflow:auto}
.pal li{padding:9px 11px;border-radius:9px;display:flex;gap:10px;
align-items:center;cursor:pointer}
.pal li[aria-selected="true"]{background:var(--accent-bg)}
.pal .p-tag{flex:none;font-size:10.5px;font-weight:700;color:var(--accent-ink);
background:var(--accent-bg);border:1px solid var(--accent-line);padding:1px 7px;
border-radius:5px}
.pal .p-t{flex:1;min-width:0;font-size:14px;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.pal .p-s{flex:none;font-size:11.5px;color:var(--soft)}
.pal .p-none{padding:16px 19px;color:var(--soft);font-size:14px;font-style:italic}
.pal-foot{padding:9px 14px;border-top:1px solid var(--line);background:#fbfcfe;
font-size:11.5px;color:var(--soft);display:flex;gap:14px}

/* How to work this thing. Reachable from the header on every view, because the
   answer to "how do I close this" should never be somewhere else. */
dialog.help{border:0;padding:0;border-radius:16px;width:min(680px,92vw);
box-shadow:0 24px 60px rgba(9,14,26,.4);color:var(--ink)}
dialog.help::backdrop{background:rgba(9,14,26,.5)}
.help-in{padding:24px 28px 26px;position:relative}
.help-in h2{margin:0 0 4px;font-size:19px;letter-spacing:-.015em}
.help-in .lead{margin:0 0 18px;color:var(--mut);font-size:14px}
.help-in h3{margin:18px 0 7px;font-size:12.5px;font-weight:750;color:var(--ink);
display:flex;align-items:center;gap:8px}
.help-in h3:before{content:"";width:3px;height:14px;border-radius:2px;
background:var(--accent)}
.help-in p{margin:0 0 8px;font-size:14px;color:var(--mut)}
.help-in code{font:600 12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
background:var(--hair);border:1px solid var(--line);border-radius:5px;padding:1px 5px;
color:var(--accent-ink)}
.say-list{list-style:none;margin:0;padding:0;display:grid;gap:1px;
background:var(--line);border:1px solid var(--line);border-radius:10px;
overflow:hidden}
.say-list li{background:#fff;padding:8px 12px;display:flex;gap:12px;
align-items:baseline;font-size:13.5px}
.say-list .said{flex:none;min-width:186px;font-weight:650;color:var(--accent-ink);
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.say-list .does{flex:1;min-width:0;color:var(--mut)}
.help-close{position:absolute;top:14px;right:16px;font:700 13px/1 inherit;
background:#fff;border:1px solid var(--line);border-radius:7px;padding:6px 10px;
cursor:pointer;color:var(--mut)}
.help-close:hover{color:var(--ink);border-color:var(--soft)}

/* The strip under your work: how to close something, in the page, not a manual. */
.howto{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:0 0 20px;
padding:11px 15px;border:1px dashed var(--line);border-radius:11px;
background:rgba(255,255,255,.6);font-size:13px;color:var(--mut)}
.howto b{color:var(--ink);font-weight:650}
.howto>span{flex:1;min-width:300px}
.howto code{font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
background:#fff;border:1px solid var(--line);border-radius:5px;padding:2px 6px;
color:var(--accent-ink);white-space:nowrap}
.howto .more{margin-left:auto;font:650 12px/1 inherit;background:#fff;
border:1px solid var(--line);border-radius:7px;padding:6px 11px;cursor:pointer;
color:var(--accent)}
.howto .more:hover{border-color:var(--accent-line);background:var(--accent-bg)}

/* Script-only: everything that is not Japanese gets out of the way. The one
   thing that stays is the ask. Reading his own words out loud is exactly when he
   notices the line is wrong, and having to leave the reading view to say so is
   how a wrong line survives to the meeting. */
body.script-only .sub:not(.script):not(.ask),body.script-only .st-head .pos,
body.script-only details,body.script-only .st-brief,body.script-only .st-raise,
body.script-only .st-warn,body.script-only .st-cons,body.script-only .st-land,
body.script-only .st-run,body.script-only .sess{display:none}
/* Rewrite or ask stays. It sits in the Say this header, on the words themselves,
   and reading them out loud is when he notices one is wrong. */
body.script-only .say .ask-here{display:inline-flex}
body.script-only .sub.ask details{display:block}
body.script-only .sub.ask{border-top:1px solid var(--line);margin-top:16px}
body.script-only .sub.ask>h3{display:none}
body.script-only .jp{font-size:21px;line-height:2}
body.script-only .en{font-size:13.5px}
body.script-only .st-tk{padding:18px 22px}
.err{background:var(--red-bg);border:1px solid var(--red-line);border-radius:12px;
padding:22px;color:var(--red)}
.err pre{white-space:pre-wrap;font-size:13px;background:#fff;padding:13px;
border-radius:8px;margin:13px 0 0;color:var(--ink)}
/* A window narrower than the desk it was drawn for. The header is navigation and
   it wraps, so the way to keep it short is to drop what is written elsewhere on
   the page rather than to let it grow a third line: two is already a lot of the
   top of the screen, and a bar that changes height as he resizes moves
   everything he is reading.

   The brand is decoration. The room this script is for is in Next room and at
   the top of the speaking view. The date and how long ago it was checked are the
   first real loss, so they go last, and the countdown pill stays throughout
   because it is the one thing up here that is about the next hour. */
@media (max-width:1240px){
.brand,.views .sub{display:none}
}
@media (max-width:1020px){
.top .date{display:none}
}

/* On a phone the whole page is one column, and the header keeps the tabs, the
   two buttons and nothing else. */
@media (max-width:640px){
.wrap{padding:14px 12px 60px}
.top-in{padding:5px 10px;gap:6px;min-width:0}
.brand,.date,#countdown,.views .sub,.views .k{display:none}
.top .btn{display:none}
.views,.acts{min-width:0}
.top-in{overflow-x:hidden}
.views,.acts{overflow-x:auto;scrollbar-width:none}
.views::-webkit-scrollbar,.acts::-webkit-scrollbar{display:none}
.views button{padding:0 9px;flex:none}
/* Flex children default to their content width, which is what pushes a phone
   into sideways scrolling. Nothing on this page needs to be wider than it. */
.tr-title,.act-title,.n-what,.thr-body,.nk-sum,.q-en,.mv-what,.terms dd,
.howto>span,.act-head,.tk-meta,.st-run a{min-width:0}
.terms dt{width:auto}
.term{flex-direction:column;gap:4px}
.tk,.st-tk{padding-left:14px;padding-right:14px}
.tk-head{margin:0 -14px;padding-left:14px;padding-right:14px}
.tr,.news li,.nk-news li{flex-wrap:wrap}
.tr-title,.n-what{flex-basis:100%;order:-1}
.tr-min,.act-min{display:none}
.thr-where{min-width:0;flex-basis:100%}
.cons-row{flex-wrap:wrap}
.cons-row dt{width:100%;padding-bottom:0}
.jp{font-size:16.5px;line-height:1.85}
.jump{position:static}
}
@media print{header.top,.btn,.copy,.toggle,.views,.jump,.howto{display:none}
body{background:#fff}.tk,.st-tk{break-inside:avoid;border-color:#ccc;box-shadow:none}
details{display:block}details>summary{display:none}}
"""

JS = """
(function(){
  var el=document.getElementById('countdown');
  var target=new Date(document.body.dataset.meeting);
  var what=(document.body.dataset.meetingLabel||'standup').toLowerCase();
  function tick(){
    var d=Math.floor((target-new Date())/1000);
    if(d<=0){el.textContent=what+' started';el.classList.add('soon');return}
    var h=Math.floor(d/3600),m=Math.floor(d%3600/60);
    el.textContent=(h?h+'h ':'')+m+'m to '+what;
    if(d<1800)el.classList.add('soon');
  }
  if(el&&!isNaN(target)){tick();setInterval(tick,20000)}
  function putPlain(s){
    // Slack only turns `foo` into code when the clipboard carries plain text,
    // so never let a rich-text flavour reach it.
    if(navigator.clipboard&&navigator.clipboard.writeText){
      return navigator.clipboard.writeText(s).catch(function(){legacy(s)});
    }
    legacy(s);
  }
  function legacy(s){
    var a=document.createElement('textarea');
    a.value=s;a.setAttribute('readonly','');
    a.style.cssText='position:fixed;top:-1000px';
    document.body.appendChild(a);a.select();
    try{document.execCommand('copy')}finally{document.body.removeChild(a)}
  }
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      putPlain(b.dataset.copy);
      var o=b.textContent;b.textContent='copied';
      setTimeout(function(){b.textContent=o},1200);
    });
  });
  var t=document.getElementById('scriptonly');
  if(t)t.addEventListener('click',function(){
    document.body.classList.toggle('script-only');
    t.textContent=document.body.classList.contains('script-only')
      ?'Show everything':'Japanese only';
  });

  // The view lives on the body, so CSS does the switching and nothing reloads.
  // A hash link from one view to the other lands on the right ticket because we
  // switch first and let the browser scroll after.
  var tabs=[].slice.call(document.querySelectorAll('.views button'));
  var where={};
  function show(view,remember){
    if(!tabs.length)return;
    var from=document.body.dataset.view;
    if(from&&from!==view)where[from]=window.scrollY;
    document.body.dataset.view=view;
    tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.view===view)});
    if(remember!==false)try{sessionStorage.setItem('desk-view',view)}catch(e){}
    // Coming back to a view lands where you left it. Arriving for the first
    // time starts at the top, not halfway down because the other view was.
    if(from&&from!==view&&!location.hash)window.scrollTo(0,where[view]||0);
  }
  tabs.forEach(function(b){
    b.addEventListener('click',function(){show(b.dataset.view)});
  });
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[data-goto]');
    if(!a)return;
    show(a.dataset.goto);
    var target=document.querySelector(a.getAttribute('href'));
    if(target){e.preventDefault();target.scrollIntoView({behavior:'smooth',block:'start'});
      history.replaceState(null,'',a.getAttribute('href'))}
  });
  // The finder. Everything on the page is in one index, so a ticket tag, an
  // item number or a word out of a title all land in the same place.
  var pal=document.getElementById('pal');
  var palIn=pal&&pal.querySelector('input');
  var palList=pal&&pal.querySelector('ul');
  var index=[];
  try{index=JSON.parse(document.getElementById('desk-index').textContent)}catch(e){}
  var hits=[],at=0;

  function jump(row){
    closePal();
    if(row.view)show(row.view);
    var el=document.getElementById(row.id);
    if(el){el.scrollIntoView({behavior:'smooth',block:'start'});
      history.replaceState(null,'','#'+row.id)}
  }
  function draw(){
    if(!hits.length){palList.innerHTML='<li class="p-none">Nothing matches</li>';return}
    palList.innerHTML=hits.map(function(r,i){
      return '<li role="option" data-i="'+i+'" aria-selected="'+(i===at)+'">'+
        '<span class="p-tag">'+r.tag+'</span>'+
        '<span class="p-t">'+r.label+'</span>'+
        '<span class="p-s">'+(r.sub||'')+'</span></li>';
    }).join('');
  }
  function filter(q){
    q=(q||'').trim().toLowerCase();
    hits=q?index.filter(function(r){return r.hay.indexOf(q)>-1}).slice(0,12)
          :index.slice(0,12);
    at=0;draw();
  }
  function openPal(){
    if(!pal)return;
    pal.hidden=false;palIn.value='';filter('');palIn.focus();
  }
  function closePal(){if(pal)pal.hidden=true}
  if(pal){
    palIn.addEventListener('input',function(){filter(palIn.value)});
    palIn.addEventListener('keydown',function(e){
      if(e.key==='ArrowDown'){at=Math.min(at+1,hits.length-1);draw();e.preventDefault()}
      else if(e.key==='ArrowUp'){at=Math.max(at-1,0);draw();e.preventDefault()}
      else if(e.key==='Enter'&&hits[at]){jump(hits[at]);e.preventDefault()}
      else if(e.key==='Escape')closePal();
    });
    palList.addEventListener('click',function(e){
      var li=e.target.closest('li[data-i]');
      if(li&&hits[li.dataset.i])jump(hits[li.dataset.i]);
    });
    pal.addEventListener('click',function(e){if(e.target===pal)closePal()});
    [].forEach.call(document.querySelectorAll('[data-find]'),function(b){
      b.addEventListener('click',openPal);
    });
  }

  // A fold he shut stays shut. Reopening the page every hour and closing the
  // same three sections again is how a page stops being used.
  [].forEach.call(document.querySelectorAll('details[data-remember]'),function(d){
    var key='fold-'+d.dataset.remember;
    try{
      var was=localStorage.getItem(key);
      if(was!==null)d.open=was==='1';
    }catch(e){}
    d.addEventListener('toggle',function(){
      try{localStorage.setItem(key,d.open?'1':'0')}catch(e){}
    });
  });

  // The ask box: the chat for one job. Opening it, the one-tap starters, and the
  // way out for when the page is a file on disk with no server behind it, which
  // is the same words with the job named, on the clipboard.
  function openAsk(box,seed){
    var panel=box.querySelector('.ask-box');
    var field=box.querySelector('textarea');
    panel.hidden=false;
    box.querySelector('.ask-bar').hidden=true;
    if(seed&&!field.value)field.value=seed;
    field.focus();
    field.selectionStart=field.selectionEnd=field.value.length;
    // Say which of the two this box is. A page with no server behind it can
    // only hand the words to a chat, and a copy button that looks like the
    // whole feature is worse than one that admits what it is.
    var send=box.querySelector('.ask-send');
    var keys=box.querySelector('.ask-keys');
    if(keys)keys.innerHTML=(send&&!send.hidden)
      ?'Enter sends \\u00b7 Shift+Enter for a new line'
      :'No desk server behind this page, so Enter copies it for a chat instead';
    return field;
  }
  function closeAsk(box){
    box.querySelector('.ask-box').hidden=true;
    box.querySelector('.ask-bar').hidden=false;
    box.querySelector('.ask-hint').textContent='';
  }
  document.addEventListener('click',function(e){
    // Rewrite this draft, from the draft. The box that does it is at the foot of
    // the card, so the button up here opens it with the sentence started.
    var here=e.target.closest('.ask-here');
    if(here){
      // The nearest of the three, so a button in a draft header opens that
      // job's box and one in a Say this header opens the speaking card's.
      var within=here.closest('.act-body,.tk,.st-tk');
      var target=within&&within.querySelector('.ask');
      if(target){
        var f=openAsk(target,here.dataset.askSeed||'');
        target.scrollIntoView({behavior:'smooth',block:'center'});
        f.focus();
      }
      return;
    }
    var box=e.target.closest('.ask');
    if(!box)return;
    // Two composers can be open in one block: the box at the foot of the card,
    // and the one inside whichever answer he is pulling on. Every button works
    // on the one it is inside.
    var here=e.target.closest('.fu')||box.querySelector('.ask-box');
    var field=here.querySelector('textarea');
    var follow=e.target.closest('.qa-follow');
    if(follow){
      var fu=follow.closest('details').querySelector('.fu');
      fu.hidden=false;
      follow.closest('.qa-foot').hidden=true;
      var t=fu.querySelector('textarea');
      t.focus();
      return;
    }
    if(e.target.closest('.fu-cancel')){
      var mine=e.target.closest('.fu');
      mine.hidden=true;
      var foot=mine.parentNode.querySelector('.qa-foot');
      if(foot)foot.hidden=false;
      return;
    }
    if(e.target.closest('.ask-open')){
      openAsk(box,'');
    }else if(e.target.closest('.ask-cancel')){
      closeAsk(box);
    }else if(e.target.closest('.qa-chip')){
      var add=e.target.closest('.qa-chip').dataset.fill;
      field.value=field.value.trim()?field.value.trim()+' '+add:add;
      field.focus();
      field.selectionStart=field.selectionEnd=field.value.length;
    }else if(e.target.closest('.ask-copy')){
      var q=(field.value||'').trim();
      // Following up in a chat means handing over what it is a follow-up to,
      // otherwise "why?" arrives on its own and means nothing.
      var lead=box.dataset.askLead||'';
      var about=e.target.closest('.qa');
      if(about){
        var asked=about.querySelector('.qa-q');
        var got=about.querySelector('.qa-a');
        lead+='\\n\\nHe is following up on this exchange.\\n\\nQ: '
          +(asked?asked.textContent.trim():'')+'\\n\\nA: '
          +(got?got.textContent.trim():'');
      }
      putPlain(lead+(q?'\\n\\n'+q:''));
      var hint=here.querySelector('.ask-hint')||box.querySelector('.ask-hint');
      hint.textContent=q?'Copied. Paste it into a chat on this folder.'
        :'Copied the job. Paste it into a chat and type what you want.';
    }
  });
  // Enter sends, the way it does in every chat. Shift-Enter is a new line, and
  // escape puts the box away.
  document.addEventListener('keydown',function(e){
    var panel=e.target.closest&&(e.target.closest('.ask-box')||e.target.closest('.fu'));
    if(!panel||e.target!==panel.querySelector('textarea'))return;
    var box=panel.closest('.ask');
    if(e.key==='Escape'){
      if(panel.classList.contains('fu')){
        panel.hidden=true;
        var foot=panel.parentNode.querySelector('.qa-foot');
        if(foot)foot.hidden=false;
      }else{closeAsk(box)}
      return;
    }
    if(e.key!=='Enter'||e.shiftKey||e.altKey)return;
    e.preventDefault();
    var send=panel.querySelector('.ask-send');
    // No server behind the page, so the only thing Enter can honestly do is
    // hand the words over for a chat.
    (send&&!send.hidden?send:panel.querySelector('.ask-copy')).click();
  });

  var help=document.getElementById('help');
  function openHelp(){if(help&&!help.open)help.showModal()}
  if(help){
    [].forEach.call(document.querySelectorAll('[data-help]'),function(b){
      b.addEventListener('click',openHelp);
    });
    help.addEventListener('click',function(e){if(e.target===help)help.close()});
    var x=help.querySelector('.help-close');
    if(x)x.addEventListener('click',function(){help.close()});
  }

  // The chip for the ticket you are looking at lights up as you scroll.
  var chips=[].slice.call(document.querySelectorAll('.jump a[href^="#t-"]'));
  if(chips.length&&'IntersectionObserver' in window){
    var seen={};
    var eye=new IntersectionObserver(function(rows){
      rows.forEach(function(r){seen[r.target.id]=r.isIntersecting});
      var live=chips.filter(function(a){return seen[a.getAttribute('href').slice(1)]});
      chips.forEach(function(a){a.classList.remove('on')});
      if(live.length)live[0].classList.add('on');
    },{rootMargin:'-90px 0px -70% 0px'});
    chips.forEach(function(a){
      var el=document.getElementById(a.getAttribute('href').slice(1));
      if(el)eye.observe(el);
    });
  }

  document.addEventListener('keydown',function(e){
    if((e.metaKey||e.ctrlKey)&&e.key==='k'){openPal();e.preventDefault();return}
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    var tag=(e.target.tagName||'').toLowerCase();
    if(tag==='input'||tag==='textarea')return;
    if(e.key==='1')show('desk');
    if(e.key==='2')show('standup');
    if(e.key==='s'&&t)t.click();
    if(e.key==='/'){openPal();e.preventDefault()}
    if(e.key==='?')openHelp();
    if(e.key==='Escape')closePal();
  });
  if(tabs.length){
    var start=document.body.dataset.view;
    try{
      var saved=sessionStorage.getItem('desk-view');
      if(saved)start=saved;
    }catch(e){}
    if(location.hash.indexOf('#s-')===0)start='standup';
    show(start,false);
  }
  // Scroll-spy: light the jump link for the section at the top of the view, so
  // the rail always says where you are down a long board. A top-line test rather
  // than a mid-band one, so a gap between sections never leaves nothing lit.
  (function(){
    var nav=document.querySelector('nav.jump');
    if(!nav)return;
    var links=[].slice.call(nav.querySelectorAll('a[href^="#"]'));
    var map={},targets=[];
    links.forEach(function(a){
      var id=decodeURIComponent(a.getAttribute('href').slice(1));
      var el=document.getElementById(id);
      if(el){map[id]=a;targets.push(el);}
    });
    if(!targets.length)return;
    var ticking=false;
    function paint(){
      ticking=false;
      // Last section whose top has scrolled above the line is the one in view;
      // later in document order wins, so a ticket lights over its container.
      var line=140,current=targets[0].id;
      for(var i=0;i<targets.length;i++){
        if(targets[i].getBoundingClientRect().top-line<=0)current=targets[i].id;
      }
      links.forEach(function(a){a.classList.toggle('on',map[current]===a);});
    }
    function onScroll(){if(!ticking){ticking=true;requestAnimationFrame(paint);}}
    window.addEventListener('scroll',onScroll,{passive:true});
    window.addEventListener('resize',onScroll,{passive:true});
    paint();
  })();
})();
"""
