#!/usr/bin/env python3
"""The week ahead: the rooms he speaks in, and everything that comes due.

Split out of `render_desk.py`, which had grown to 2300 lines and held eight
unrelated jobs. This one answers a single question, "is the week covered", and
it is the only file that knows how a day is drawn.

The first version of this was a strip of seven boxes with a job number in each,
which looked like a calendar and was useless as one: a 10.5px chip reading `13
強制発行` tells you a number is due without telling you what it is, whose it is
or whether it is late. A calendar you cannot read at a glance is decoration.

So a day here is a column of real rows. Each row carries the job number, what
the job actually is, and who is holding it, coloured the way the rest of the
page colours work: red is his, amber is stuck, blue is with someone else. Today
is wider than the rest, because today is the column he reads.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from render import (
    day_words,
    esc,
    item_state as state_of,
    next_live,
)

# An ISO date and nothing else. `chase_on` is sometimes a sentence ("Only if he
# raises it again"), and a sentence is not a day on a calendar.
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

# How many days across. Seven is this week and the next session, which is the
# horizon he actually plans against; a month view would be four times the pixels
# for a question he does not ask of this page.
DAYS = 7

# Rows before a day starts saying "and 3 more" instead of growing. Three is
# what fits without any column setting the height of the whole strip.
ROWS_PER_DAY = 3


def whose(item: dict, st: dict) -> tuple[str, str]:
    """Who is holding this, and which of the page's four colours that is.

    Same language as everywhere else on the desk, because a job that is red on
    its card and grey here is two facts about one job.
    """
    if st["state"] == "todo":
        return "You", "mine"
    if st["state"] == "hold":
        return st.get("who") or "Blocked", "held"
    who = (item.get("waits_on") or {}).get("who") or st.get("who") or ""
    return who or "Them", "theirs"


def due_rows(tickets: list[dict], today: date) -> tuple[dict[str, list[dict]], int]:
    """Everything with a real date on it, filed by the day it falls.

    Anything already overdue is pulled onto today rather than left off the left
    edge of the strip: a chase that slipped last Tuesday is more urgent than one
    that has not come up yet, not less, and a calendar that hides it is lying by
    omission.
    """
    by_day: dict[str, list[dict]] = {}
    late = 0
    horizon = (today + timedelta(days=DAYS - 1)).isoformat()
    for t in tickets:
        for i in t.get("items", []):
            st = state_of(i)
            if st["closed"]:
                continue
            when = (i.get("waits_on") or {}).get("chase_on") or ""
            if not ISO.fullmatch(when or ""):
                continue
            if when > horizon:
                continue
            who, tone = whose(i, st)
            overdue = when < today.isoformat()
            if overdue:
                late += 1
            row = {
                "id": str(i.get("id", "")),
                "title": i.get("title", ""),
                "ref": t.get("ref", ""),
                "who": who,
                "tone": "late" if overdue else tone,
                "late": overdue,
                "on": when,
            }
            by_day.setdefault(today.isoformat() if overdue else when, []).append(row)
    return by_day, late


def render(board: dict, tickets: list[dict], refs: dict[str, str]) -> str:
    """Seven days, with every room and every due job drawn in them."""
    today = date.today()
    days = [today + timedelta(days=n) for n in range(DAYS)]
    by_day, late = due_rows(tickets, today)

    rooms: dict[str, list[dict]] = {}
    for s in board.get("sessions") or []:
        if s.get("date"):
            rooms.setdefault(s["date"], []).append(s)

    cells = []
    for n, d in enumerate(days):
        iso = d.isoformat()
        sess = sorted(rooms.get(iso, []), key=lambda s: s.get("at") or "")
        jobs = sorted(by_day.get(iso, []), key=lambda r: (not r["late"], r["id"]))
        marks = "".join(
            f"""<span class="wd-room" title="{esc(s.get("label") or "")}">
              <b>{esc(s.get("at", ""))}</b>
              {esc((s.get("tab") or s.get("name") or s.get("kind") or "Session"))}</span>"""
            for s in sess
        )
        shown, rest = jobs[:ROWS_PER_DAY], jobs[ROWS_PER_DAY:]
        rows = "".join(
            f"""<a class="wd-job {esc(r["tone"])}" href="#{esc(refs.get(r["ref"], ""))}"
               title="{esc(r["title"])}">
              <span class="wd-n">{esc(r["id"])}</span>
              <span class="wd-w">{esc(r["title"])}</span>
              <span class="wd-who">{esc(r["who"])}</span></a>"""
            for r in shown
        )
        if rest:
            rows += (
                f'<span class="wd-rest">and {len(rest)} more</span>'
            )
        quiet = not sess and not jobs
        klass = " ".join(
            filter(
                None,
                [
                    "wd",
                    "today" if n == 0 else "",
                    "weekend" if d.weekday() >= 5 else "",
                    "quiet" if quiet else "",
                ],
            )
        )
        head_note = ""
        if n == 0:
            head_note = '<span class="wd-today">Today</span>'
        elif n == 1:
            head_note = '<span class="wd-soon">Tomorrow</span>'
        cells.append(f"""
      <li class="{klass}">
        <div class="wd-h">
          <span class="wd-d"><b>{esc(d.strftime("%a"))}</b>
            <i>{esc(d.strftime("%-d"))}</i></span>
          {head_note}
          {f'<span class="wd-c">{len(jobs)}</span>' if jobs else ""}
        </div>
        {f'<div class="wd-rooms">{marks}</div>' if marks else ""}
        {f'<div class="wd-jobs">{rows}</div>' if rows else ""}
        {'<span class="wd-none">&ndash;</span>' if quiet else ""}
      </li>""")

    soon = next_live(board)
    lead = ""
    if soon.get("date"):
        when = "today" if soon["date"] == today.isoformat() else day_words(soon["date"])
        lead = f'Next: {soon.get("tab") or soon.get("name") or "session"} {when}'
        if soon.get("at"):
            lead += f' at {soon["at"]}'
    busiest = max(
        ((len(v), k) for k, v in by_day.items()), default=(0, "")
    )
    warn = ""
    if busiest[0] >= 3 and busiest[1]:
        day = "today" if busiest[1] == today.isoformat() else day_words(busiest[1])
        warn = f'{busiest[0]} land {day}'
    return f"""
    <section class="week" id="week" aria-label="The week ahead">
      <header class="week-h">
        <h2>The week ahead</h2>
        {f'<span class="week-next">{esc(lead)}</span>' if lead else ""}
        {f'<span class="week-busy">{esc(warn)}</span>' if warn else ""}
        {f'<span class="week-late">{late} overdue</span>' if late else ""}
      </header>
      <ol class="week-days">{"".join(cells)}</ol>
    </section>"""
