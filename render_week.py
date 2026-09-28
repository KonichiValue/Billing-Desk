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
    urgency_of,
)

# An ISO date and nothing else. `chase_on` is sometimes a sentence ("Only if he
# raises it again"), and a sentence is not a day on a calendar.
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")

# How many days to look ahead, and which of them get drawn.
#
# Monday to Friday of the week being looked at. A calendar should say "this
# week", because that is the unit the work is actually organised in: the cycle
# runs in weeks, the standup is Monday and Wednesday, and "is Wednesday covered"
# is a question about a week rather than about the next five days.
#
# A rolling window starting today was the first attempt and it was wrong. It
# meant the columns changed identity every morning, Thursday's strip began at
# Thursday with no way to see that Tuesday had been busy, and on a Friday it
# showed three days of next week with no heading to say so.
#
# Saturday and Sunday get no column. Nothing on this desk happens on them and no
# standup is ever scheduled on one, so they were two sevenths of the width
# carrying nothing. A date that does fall on one moves to the Friday before,
# flagged with its real date, because Friday is the last day he can act on it.
WEEK_DAYS = 5

# Rows a day draws before the rest become "and 2 more". The column scrolls, so
# this is about which rows are visible without asking, not which exist.
#
# Work sitting with *him* is never folded away, however many there are: the
# strip exists so he can see what he is doing, and "and 2 more" hiding two of
# his own jobs is the failure it was built to prevent. Only other people's
# chases count against the limit.
ROWS_PER_DAY = 4


def whose(item: dict, st: dict) -> tuple[str, str]:
    """Who is holding this, and which of the page's four colours that is.

    The words are the card's words. A job whose card pill reads "With you" and
    whose calendar row read "You" is the same fact told two ways, and the whole
    point of putting his work on the strip is that he recognises it there.
    """
    if st["state"] == "todo":
        return "With you", "mine"
    if st["state"] == "hold":
        return st.get("who") or "Held", "held"
    who = (item.get("waits_on") or {}).get("who") or st.get("who") or ""
    return f"With {who}" if who else "With them", "theirs"


def monday_of(day: date) -> date:
    """The Monday of the week `day` falls in.

    On a Saturday or Sunday this is the Monday coming, not the one just gone:
    by the weekend the week on the page is over, and what he wants to see is the
    one he is about to walk into.
    """
    if day.weekday() >= 5:
        return day + timedelta(days=7 - day.weekday())
    return day - timedelta(days=day.weekday())


def columns(monday: date) -> list[date]:
    """Monday to Friday of one week."""
    return [monday + timedelta(days=n) for n in range(WEEK_DAYS)]


def dated(item: dict, st: dict, today: date) -> str:
    """The day this job belongs on, or "" if it has no day at all.

    Two different fields, because the board dates two different things. Work
    sitting with someone else carries `waits_on.chase_on`, the day their silence
    becomes his problem again. Work sitting with *him* carries no date at all,
    only an urgency, which is why the first version of this calendar showed five
    of other people's chases and none of his own jobs: the column he was meant
    to work from was the one thing missing.

    So urgency is read as a day. `today` means today, `this-week` means the next
    working day he has not passed yet, and `monitor` is genuinely undated and
    stays off the strip. It is an inference rather than a fact, so the row says
    so and the card stays the place the real state lives.
    """
    chase = (item.get("waits_on") or {}).get("chase_on") or ""
    if ISO.fullmatch(chase or ""):
        return chase
    if st["state"] not in {"todo", "hold"}:
        return ""
    urgency = urgency_of(item)
    if urgency == "today":
        return today.isoformat()
    if urgency == "this-week":
        # Tomorrow, or Monday when tomorrow is the weekend: a job he has not got
        # to today is a job for the next day he is at the desk.
        d = today + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d.isoformat()
    return ""


def due_rows(
    tickets: list[dict], days: list[date], today: date
) -> tuple[dict[str, list[dict]], int, int]:
    """Everything with a day, filed by the column it falls in.

    Three things can happen to a date. Inside the week it lands on its own day,
    except a weekend one which moves back to Friday and says so. Before the
    week's first column it is overdue and lands on the first column he can still
    act on, because a chase that slipped is more urgent than one that has not
    come up, not less, and a calendar that hides it is lying by omission. After
    the last column it is counted and named in the header rather than drawn.
    """
    shown = {d.isoformat() for d in days}
    first, last = days[0].isoformat(), days[-1].isoformat()
    # Overdue work stacks on today when today is in this week, and on Monday
    # when he is looking at a week he has not started yet.
    catch = today.isoformat() if first <= today.isoformat() <= last else first
    by_day: dict[str, list[dict]] = {}
    late = ahead = 0
    for t in tickets:
        for i in t.get("items", []):
            st = state_of(i)
            if st["closed"]:
                continue
            when = dated(i, st, today)
            if not when:
                continue
            if when > last:
                ahead += 1
                continue
            who, tone = whose(i, st)
            overdue = when < first or when < today.isoformat()
            if overdue:
                late += 1
                lands = catch
            elif when in shown:
                lands = when
            else:
                # A Saturday or Sunday, which has no column: back to the Friday.
                d = date.fromisoformat(when)
                while d.weekday() >= 5:
                    d -= timedelta(days=1)
                lands = d.isoformat()
                if lands not in shown:
                    continue
            row = {
                "id": str(i.get("id", "")),
                "title": i.get("title", ""),
                "ref": t.get("ref", ""),
                "who": who,
                "tone": "late" if overdue else tone,
                "late": overdue,
                "on": when,
                # A job drawn on a day that is not its own says which day is,
                # or the strip quietly misreports the date.
                "moved": lands != when,
                # Whether the day came from the board or from the urgency. An
                # inferred day is drawn dashed, because "this-week means
                # tomorrow" is this renderer's opinion and not a fact he set.
                "guess": not ISO.fullmatch(
                    (i.get("waits_on") or {}).get("chase_on") or ""
                ),
            }
            by_day.setdefault(lands, []).append(row)
    return by_day, late, ahead


def render(board: dict, tickets: list[dict], refs: dict[str, str]) -> str:
    """One week, Monday to Friday, with every room and every job due in it."""
    today = date.today()
    days = columns(monday_of(today))
    by_day, late, ahead = due_rows(tickets, days, today)

    rooms: dict[str, list[dict]] = {}
    for s in board.get("sessions") or []:
        if s.get("date"):
            rooms.setdefault(s["date"], []).append(s)

    cells = []
    for n, d in enumerate(days):
        iso = d.isoformat()
        sess = sorted(rooms.get(iso, []), key=lambda s: s.get("at") or "")
        # Late first, then his own work, then everyone else's, then by number.
        jobs = sorted(
            by_day.get(iso, []),
            key=lambda r: (not r["late"], r["tone"] != "mine", int(r["id"] or 0)),
        )
        marks = "".join(
            f"""<span class="wd-room" title="{esc(s.get("label") or "")}">
              <b>{esc(s.get("at", ""))}</b>
              {esc((s.get("tab") or s.get("name") or s.get("kind") or "Session"))}</span>"""
            for s in sess
        )
        # His own work is never folded away, however long the day is. Only the
        # rest competes for the remaining rows.
        his = [r for r in jobs if r["tone"] in {"mine", "late"}]
        others = [r for r in jobs if r not in his]
        room = max(0, ROWS_PER_DAY - len(his))
        shown, rest = his + others[:room], others[room:]
        rows = "".join(
            f"""<a class="wd-job {esc(r["tone"])}{" guess" if r["guess"] else ""}"
               href="#{esc(refs.get(r["ref"], ""))}"
               title="{esc(r["title"])}{esc(
                   f' (really due {day_words(r["on"])})' if r["moved"]
                   else " (no date on the board, placed by its urgency)"
                   if r["guess"] else ""
               )}">
              <span class="wd-n">{esc(r["id"])}</span>
              <span class="wd-w">{esc(r["title"])}</span>
              <span class="wd-who">{esc(r["who"])}{
                  esc(f' · due {day_words(r["on"])}') if r["moved"] else ""
              }</span></a>"""
            for r in shown
        )
        if rest:
            rows += (
                f'<span class="wd-rest">and {len(rest)} more</span>'
            )
        quiet = not sess and not jobs
        # A day this week that is already behind him reads back rather than
        # empty, so Monday on a Wednesday does not look like nothing is due.
        klass = " ".join(
            filter(
                None,
                [
                    "wd",
                    "today" if d == today else "",
                    "past" if d < today else "",
                    "quiet" if quiet else "",
                ],
            )
        )
        head_note = ""
        if d == today:
            head_note = '<span class="wd-today">Today</span>'
        elif d == today + timedelta(days=1):
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
    # Which week this is. "This week" on a Monday to Friday, and the dates
    # besides, because on a Saturday the strip is showing the week coming and
    # has to say so rather than looking like a stale one.
    first, last = days[0], days[-1]
    this_week = first <= today <= last
    span = (
        f'{first.strftime("%-d")}&ndash;{last.strftime("%-d %b")}'
        if first.month == last.month
        else f'{first.strftime("%-d %b")} &ndash; {last.strftime("%-d %b")}'
    )
    title = ("This week" if this_week else "Next week") + f" &middot; {span}"
    return f"""
    <section class="week" id="week" aria-label="The week">
      <header class="week-h">
        <h2>{title}</h2>
        {f'<span class="week-next">{esc(lead)}</span>' if lead else ""}
        {f'<span class="week-busy">{esc(warn)}</span>' if warn else ""}
        {f'<span class="week-ahead">{ahead} after Friday</span>' if ahead else ""}
        {f'<span class="week-late">{late} overdue</span>' if late else ""}
      </header>
      <ol class="week-days">{"".join(cells)}</ol>
    </section>"""
