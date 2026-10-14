#!/usr/bin/env python3
"""When the next prioritization round is, and which of his builds need raising.

Every second Monday Heqing runs the build prioritization for the TG workstreams,
and at 08:30 JST posts the result in #team-jp-billing-cdl: the builds that got a
TG Order for the next cycle, in order, and the ones that were not pushed. Her
standing ask to the CDLs (13 Oct) is to keep their build tickets' dates and
status current, and to say which of theirs should be prioritized or adjusted.
After the thread is out it is too late to say, so the day that matters is the
working day before it.

The dates come from `config.json` (`prioritization`), not the board: a round is
`anchor` plus a multiple of `every_days`, moved to the next working day when it
lands on a weekend or a holiday, and `moved` records a round that went to
another day for any other reason. The 12 Oct round went to Tuesday 13 Oct for
Sports Day, which the holiday rule gives on its own and `moved` also records.

What his builds look like comes from the board's `prioritization` block, which
a sweep fills from every CE build whose CDL-Owner is Rei. That is the only
membership rule: a build owned by another CDL (Hitoshi's KT-109569) never
appears, however close it sits to his tickets. `board.py` documents the shape.

    ./prioritize.py          the next round, and what to raise before it
    ./prioritize.py --dates  the next six rounds

It never writes and never sends.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Done builds are not in the round at all.
FINISHED = {"done", "complete", "completed", "released", "closed", "won't do"}


def config() -> dict:
    try:
        data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("prioritization") or {}


def _iso(text) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except (TypeError, ValueError):
        return None


def working(day: date, cfg: dict) -> bool:
    return day.weekday() < 5 and day.isoformat() not in set(cfg.get("holidays") or [])


def shift(day: date, cfg: dict) -> date:
    """A round that falls on a day nobody works runs on the next one that is."""
    while not working(day, cfg):
        day += timedelta(days=1)
    return day


def actual(planned: date, cfg: dict) -> date:
    """The day a planned round really ran, or will run."""
    for row in cfg.get("moved") or []:
        if row.get("from") == planned.isoformat() and _iso(row.get("to")):
            return _iso(row["to"])
    return shift(planned, cfg)


def rounds(cfg: dict | None = None, start: date | None = None, count: int = 6) -> list[dict]:
    """The rounds from `start` on, planned and actual date, soonest first.

    Counts back from the anchor as well as forward, so the round of 13 Oct is
    the one before 26 Oct without having to be written down anywhere.
    """
    cfg = config() if cfg is None else cfg
    anchor = _iso(cfg.get("anchor"))
    every = int(cfg.get("every_days") or 14)
    if not anchor:
        return []
    start = start or date.today()
    # The first planned date whose actual day could still be on or after start.
    steps = (start - anchor).days // every - 1
    planned = anchor + timedelta(days=every * steps)
    out = []
    while len(out) < count:
        day = actual(planned, cfg)
        if day >= start:
            moved = next(
                (r.get("why", "") for r in cfg.get("moved") or []
                 if r.get("from") == planned.isoformat()), "")
            if not moved and day != planned:
                moved = "the planned day is not a working day"
            out.append({
                "planned": planned.isoformat(),
                "date": day.isoformat(),
                "at": cfg.get("thread_at", "08:30"),
                "ask_by": ask_by(day, cfg).isoformat(),
                "moved": moved,
            })
        planned += timedelta(days=every)
    return out


def previous(cfg: dict | None = None, today: date | None = None) -> dict:
    """The last round that has already run."""
    cfg = config() if cfg is None else cfg
    today = today or date.today()
    every = int(cfg.get("every_days") or 14)
    now = datetime.now().strftime("%H:%M") if today == date.today() else "23:59"
    past = [r for r in rounds(cfg, today - timedelta(days=every + 7), 3)
            if r["date"] < today.isoformat()
            or (r["date"] == today.isoformat() and now >= r["at"])]
    return past[-1] if past else {}


def ask_by(round_day: date, cfg: dict) -> date:
    """The last working day before the thread goes out.

    The thread is posted first thing on the round's own morning, so anything
    worth raising has to reach Heqing the working day before.
    """
    day = round_day - timedelta(days=1)
    while not working(day, cfg):
        day -= timedelta(days=1)
    return day


def next_round(cfg: dict | None = None, today: date | None = None) -> dict:
    """The next round whose thread has not gone out, with the days left.

    On the round's own day, before the thread time, it is still the next one.
    """
    cfg = config() if cfg is None else cfg
    today = today or date.today()
    now = datetime.now().strftime("%H:%M") if today == date.today() else "00:00"
    for r in rounds(cfg, today, 3):
        if r["date"] == today.isoformat() and now >= r["at"]:
            continue
        r["days"] = (_iso(r["date"]) - today).days
        r["ask_days"] = (_iso(r["ask_by"]) - today).days
        return r
    return {}


def kind(build: dict) -> str:
    """Which of four things a build is, for this round.

    raise    refined and sized, no TG Order: say it should be ordered
    ordered  has a TG Order: only its dates and status need to be right
    refining not refined yet, so it cannot be ordered this round
    done     finished, not part of the round
    """
    status = str(build.get("status", "")).strip().lower()
    if status in FINISHED:
        return "done"
    if str(build.get("tg_order") or "").strip():
        return "ordered"
    if build.get("refinement") == "🟢" or status == "ready to build":
        return "raise"
    return "refining"


def fixes(build: dict) -> list[str]:
    """What is out of date or missing on a build, in the words of the fix.

    Heqing's first ask is that the ticket's own dates and status are current,
    so these are the edits to make in Asana before the round, not things to
    say in the thread.
    """
    out = []
    k = kind(build)
    if k == "ordered":
        if not build.get("due_on"):
            out.append("no due date, though it has a TG Order")
        if not build.get("wave"):
            out.append("TG Order but no wave")
    # A CE build's Status after refinement is the refining engineer's to set,
    # not his (13 Oct), so a 🟢 build still reading New is not a fix for him.
    due = _iso(build.get("due_on"))
    if due and due < date.today() and k != "done":
        out.append(f"due date {build['due_on']} has passed")
    return out


def summary(board: dict, today: date | None = None) -> dict:
    """Everything the page, the markdown and the CLI say about the round."""
    cfg = config()
    block = board.get("prioritization") or {}
    builds = [b for b in block.get("builds") or [] if isinstance(b, dict)]
    rows = []
    for b in builds:
        k = kind(b)
        if k != "done":
            rows.append({**b, "kind": k, "fixes": fixes(b)})
    # Ordered builds by their TG Order; the rest keep the board's order, which
    # is the order he would ask for them in.
    order = {"raise": 0, "ordered": 1, "refining": 2}
    rows.sort(key=lambda r: (order[r["kind"]],
                             int(r["tg_order"]) if str(r.get("tg_order") or "").isdigit() else 0))
    nxt = next_round(cfg, today)
    checked = block.get("checked_at", "")
    stale = ""
    last = previous(cfg, today)
    if not builds:
        stale = "No builds have been read yet. A refresh fills this from Asana."
    elif last and checked[:10] < last["date"]:
        stale = f"Read {checked[:10] or 'never'}, before the {last['date']} round."
    elif nxt and nxt.get("ask_days", 99) <= 1 and checked[:10] < (today or date.today()).isoformat():
        stale = f"Read {checked[:10]}. Refresh before you send, the thread is {nxt['date']}."
    return {
        "config": cfg,
        "next": nxt,
        "last": last,
        "last_round": block.get("last_round") or {},
        "rows": rows,
        "raise": [r for r in rows if r["kind"] == "raise"],
        "fixes": [r for r in rows if r["fixes"]],
        "checked_at": checked,
        "stale": stale,
    }


def message(s: dict) -> str:
    """The note to Heqing, in English, built from the board so it cannot drift.

    Internal and to a Kraken reader, so KT numbers and sizes are fine here. It
    never goes anywhere by itself: the page shows it with a copy button.
    """
    nxt = s.get("next") or {}
    if not s["raise"] and not s["fixes"]:
        return ""
    when = ""
    if nxt.get("date"):
        when = f" for the {_iso(nxt['date']).strftime('%-d %b')} prioritization"
    lines = [f"Hi Heqing, my builds{when}:"]
    if s["raise"]:
        lines.append("")
        lines.append("Please consider for a TG Order:")
        for r in s["raise"]:
            bits = [r.get("size", "")]
            if r.get("why"):
                bits.append(r["why"])
            tail = ", ".join(b for b in bits if b)
            lines.append(f"• {r.get('kt', '')} {short(r.get('name', ''))}" + (f" ({tail})" if tail else ""))
    ordered = [r for r in s["rows"] if r["kind"] == "ordered"]
    if ordered:
        lines.append("")
        lines.append("Already ordered, no change: " + ", ".join(
            f"{r.get('kt')} (TG Order {r.get('tg_order')})" for r in ordered))
    return "\n".join(lines)


def short(name: str) -> str:
    """A build title without the `TG | Billing |` prefix every one of them has."""
    parts = [p.strip() for p in str(name).split("|")]
    return parts[-1] if parts else str(name)


def main() -> int:
    sys.path.insert(0, str(ROOT))
    import board as B

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dates", action="store_true", help="the next six rounds")
    args = ap.parse_args()
    if args.dates:
        for r in rounds():
            note = f"  (planned {r['planned']}, {r['moved']})" if r["moved"] else ""
            print(f"{r['date']} {r['at']}  ask Heqing by {r['ask_by']}{note}")
        return 0
    s = summary(B.load())
    nxt = s["next"]
    if nxt:
        print(f"Next round {nxt['date']} {nxt['at']} ({nxt['days']} days). "
              f"Ask Heqing by {nxt['ask_by']}.")
    if s["stale"]:
        print(f"  {s['stale']}")
    for r in s["rows"]:
        tag = {"raise": "RAISE", "ordered": f"TG#{r.get('tg_order')}", "refining": "refining"}[r["kind"]]
        print(f"  {tag:9} {r.get('kt', ''):10} {r.get('ticket') or '-':8} "
              f"{r.get('status', '')} {r.get('size', '')} due {r.get('due_on') or '-'}")
        for f in r["fixes"]:
            print(f"            fix: {f}")
    text = message(s)
    if text:
        print("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
