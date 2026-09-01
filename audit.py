#!/usr/bin/env python3
"""Everything on the board that has quietly gone out of date.

A sweep is good at finding what moved and bad at noticing what it left behind.
The evidence is in the logs: on 1 September the refresh read the CE ticket,
correctly recorded that both files had been re-uploaded at 10:57, and left the
item still titled "Re-upload both sheets and fix the 144s". It knew. It wrote the
fact into `progress_note`, which is additive and safe, and never went back to
reshape the item, which is the actual job. The same sweep left a chase date four
days in the past and a thread stamped 26 August on a ticket whose newest event
was the 31st.

None of that needs judgement to spot, so none of it should depend on an agent
choosing to look. This is the part a script can check: dates that have passed,
records that disagree with each other, work that points at something closed.
Whatever it prints is a thing the last sweep should have done and did not.

It never writes. Run it at the end of a refresh, fix what it lists, run it again.

    ./audit.py            everything, grouped, worst first
    ./audit.py --quiet    only the count, for a gate
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime

import board as B

DATE_IN = re.compile(r"\d{4}-\d{2}-\d{2}")
STALE_HOURS = 6


def as_date(text: object) -> date | None:
    """The first ISO date in a string, when there is one.

    Half these fields hold a condition rather than a date, "at the next session if
    the ticket stays quiet", and that is a legitimate way to write a chase. Only
    the ones that committed to a day can be late.
    """
    found = DATE_IN.search(str(text or ""))
    if not found:
        return None
    try:
        return date.fromisoformat(found.group(0))
    except ValueError:
        return None


def days_past(text: object) -> int | None:
    day = as_date(text)
    return None if day is None else (date.today() - day).days


class Report:
    """Findings, grouped by how much they mislead him."""

    def __init__(self) -> None:
        self.groups: dict[str, list[str]] = {}

    def add(self, group: str, line: str) -> None:
        self.groups.setdefault(group, []).append(line)

    @property
    def total(self) -> int:
        return sum(len(v) for v in self.groups.values())


def check_dates(b: dict, rep: Report) -> None:
    """Dates that have come and gone.

    A chase date is a promise to himself. Once it passes, the page has to say so
    rather than keep showing it in the same grey as next Tuesday.
    """
    for ticket, item in B.items(b):
        if not B.is_open(item):
            continue
        where = f"{item.get('id')} ({ticket.get('ref')})"
        waits = item.get("waits_on") or {}
        hold = item.get("hold") or {}

        late = days_past(waits.get("chase_on"))
        if late is not None and late > 0:
            rep.add(
                "Chase dates that have passed",
                f"  {where}: chase was due {waits['chase_on']}, {late} days ago, "
                f"still waiting on {waits.get('who', 'someone')}. Chase it, or move "
                f"the date to when you actually will.",
            )
        revisit = days_past(hold.get("revisit"))
        if revisit is not None and revisit > 0:
            rep.add(
                "Chase dates that have passed",
                f"  {where}: held until {hold['revisit']}, {revisit} days ago. "
                f"Lift the hold or set a new date.",
            )
        if item.get("state") == "waiting" and not waits.get("chase_on"):
            rep.add(
                "Waiting on someone, with nothing to bring it back",
                f"  {where}: with {waits.get('who', 'someone')} since "
                f"{waits.get('since', 'who knows')}, no chase date. It will sit "
                f"there forever. Give it a date or a condition.",
            )


def check_freshness(b: dict, rep: Report) -> None:
    """Records on the same ticket that disagree about when it last moved.

    A thread stamped four days older than the ticket's newest event means the
    sweep read the event and never went back to the thread it came out of. The
    next sweep then trusts the older stamp and reads from the wrong point.
    """
    for ticket in b.get("tickets", []):
        events = ticket.get("events") or []
        newest = max((as_date(e.get("on")) for e in events if as_date(e.get("on"))), default=None)
        if newest is None:
            continue
        for th in ticket.get("threads") or []:
            seen = as_date(th.get("last_at"))
            if seen is not None and seen < newest:
                rep.add(
                    "Threads stamped older than the ticket's own events",
                    f"  {ticket.get('ref')}: thread \"{th.get('label', '')[:40]}\" "
                    f"last read {th.get('last_at')}, but the ticket has an event on "
                    f"{newest}. Re-read it and move last_at, or the next sweep "
                    f"starts from the wrong line.",
                )

    stamp = b.get("checked_at")
    if stamp:
        try:
            age = (datetime.now().astimezone() - datetime.fromisoformat(stamp)).total_seconds()
            if age > STALE_HOURS * 3600:
                rep.add(
                    "The board itself",
                    f"  checked_at is {int(age // 3600)}h old ({stamp}). Anything "
                    f"read off the page now is a guess.",
                )
        except ValueError:
            rep.add("The board itself", f"  checked_at is not a timestamp: {stamp!r}")


def check_wiring(b: dict, rep: Report) -> None:
    """Numbers and links that point at nothing, or at something already finished."""
    index = {str(i.get("id")): (t, i) for t, i in B.items(b)}

    for ticket, item in B.items(b):
        if not B.is_open(item):
            continue
        where = f"{item.get('id')} ({ticket.get('ref')})"
        after = item.get("after")
        if not after:
            continue
        lead = index.get(str(after))
        if lead is None:
            rep.add(
                "Sequencing that points at nothing",
                f"  {where}: after={after}, and there is no item {after}. It will "
                f"never unblock, so it shows as a job that is not one.",
            )
        elif not B.is_open(lead[1]):
            rep.add(
                "Sequencing already spent",
                f"  {where}: after={after}, which closed. Harmless, but drop the "
                f"field so the queue reads true.",
            )

    ids = [str(i.get("id")) for _, i in B.items(b)]
    dupes = sorted({n for n in ids if ids.count(n) > 1})
    if dupes:
        rep.add(
            "Two items sharing a number",
            f"  {', '.join(dupes)}. \"Do 20\" is ambiguous and ./tick.py picks one "
            f"at random. Renumber before anything else.",
        )

    highest = max((int(n) for n in ids if n.isdigit()), default=0)
    if b.get("next_id", 0) <= highest:
        rep.add(
            "The board itself",
            f"  next_id is {b.get('next_id')} but the highest item is {highest}. "
            f"The next writer will collide.",
        )


def check_closed_tickets(b: dict, rep: Report) -> None:
    """Work still open under a ticket Asana says is finished."""
    for ticket in b.get("tickets", []):
        asana = ticket.get("asana") or {}
        if not asana.get("completed"):
            continue
        live = [i for i in ticket.get("items", []) if B.is_open(i)]
        if live:
            nums = ", ".join(str(i.get("id")) for i in live)
            rep.add(
                "Open work on a ticket Asana has closed",
                f"  {ticket.get('ref')} is completed in Asana, but {nums} "
                f"{'is' if len(live) == 1 else 'are'} still open. Close them or say "
                f"why they outlive the ticket.",
            )


def check_duplicate_targets(b: dict, rep: Report) -> None:
    """Two open drafts on one ticket addressed to the same person.

    That is one comment, not two. Three numbers that end in a single Asana comment
    cost him three readings and a decision about ordering that does not exist.
    """
    for ticket in b.get("tickets", []):
        seen: dict[str, list[str]] = {}
        for item in ticket.get("items", []):
            if not B.is_open(item):
                continue
            draft = item.get("draft") or {}
            target = str(draft.get("target") or "").strip().lower()
            if target:
                seen.setdefault(target, []).append(str(item.get("id")))
        for target, nums in seen.items():
            if len(nums) > 1:
                rep.add(
                    "Several drafts going to the same place",
                    f"  {ticket.get('ref')}: items {', '.join(nums)} all draft to "
                    f"\"{target[:50]}\". Merge them onto the oldest number and drop "
                    f"the rest.",
                )


def check_prepared(b: dict, rep: Report) -> None:
    """Prepared work built before the ticket last moved.

    The `prepared` block is the answer to a question asked at a point in time. If
    the ticket has moved since, the conclusion on the card may be answering the
    old question, and he reads that block as current.
    """
    for ticket, item in B.items(b):
        if not B.is_open(item):
            continue
        prepared = item.get("prepared") or {}
        built = as_date(prepared.get("built_at"))
        if built is None:
            continue
        events = ticket.get("events") or []
        newest = max((as_date(e.get("on")) for e in events if as_date(e.get("on"))), default=None)
        if newest is not None and newest > built:
            rep.add(
                "Prepared work older than the ticket",
                f"  {item.get('id')} ({ticket.get('ref')}): prepared "
                f"{prepared.get('built_at')}, ticket moved {newest}. Re-read it "
                f"before trusting the conclusion on the card.",
            )


def check_sessions(b: dict, rep: Report) -> None:
    """A script written for a room that has already happened."""
    sessions = b.get("sessions") or []
    past = [s for s in sessions if (as_date(s.get("date")) or date.today()) < date.today()]
    for s in past:
        rep.add(
            "Sessions that have been and gone",
            f"  {s.get('date')} {s.get('at', '')} {s.get('label') or s.get('kind', '')}"
            f" is in the past and still listed. Drop it, or the page points at the "
            f"wrong room.",
        )
    for_date = as_date((b.get("script") or {}).get("for_date"))
    if for_date and for_date < date.today():
        rep.add(
            "Sessions that have been and gone",
            f"  script.for_date is {(b.get('script') or {}).get('for_date')}. What "
            f"he reads out is written for a session that is over.",
        )


CHECKS = (
    check_dates,
    check_freshness,
    check_wiring,
    check_closed_tickets,
    check_duplicate_targets,
    check_prepared,
    check_sessions,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true", help="just the count")
    args = ap.parse_args()

    b = B.load()
    rep = Report()
    for check in CHECKS:
        check(b, rep)

    if args.quiet:
        print(f"{rep.total} things out of date")
        return 1 if rep.total else 0

    if not rep.total:
        print("Board audit: nothing out of date.")
        return 0

    print(f"Board audit: {rep.total} things the last sweep left behind.\n")
    for group, lines in rep.groups.items():
        print(f"{group}:")
        for line in lines:
            print(line)
        print()
    print("Every line above is a fix, not a warning. Make them, then run this again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
