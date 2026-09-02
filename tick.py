#!/usr/bin/env python3
"""Move an item along, then rebuild the desk.

An item has one of three lives: it is with you, it is with somebody else, or it
is finished. Sending a message usually moves it to the middle one, and it comes
back to you on the same number when they reply.

    ./tick.py                            where everything is
    ./tick.py --rebuild                  redraw both pages, change nothing
    ./tick.py 4                          finished, nothing comes back
    ./tick.py 2 -w "Kevin"               sent, ball is with Kevin
    ./tick.py 2 -w "Kevin" -n "asked about the account-level hold"
    ./tick.py 2 --mine                   they replied, it is yours again
    ./tick.py 5 --dropped -n "TG answered it themselves"
    ./tick.py 1 --undo                   back to with you, forget the note

Numbers live on the board and are never reused, so "do 4" means the same thing
next week. State lives in `state/board.json` beside the item it describes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import board as B
import keep
from render import item_state

ROOT = Path(__file__).resolve().parent
MARK = {
    "todo": "[ ]",
    "hold": "[!]",
    "waiting": "[~]",
    "done": "[x]",
    "sent": "[x]",
    "dropped": "[-]",
}


def show(data: dict) -> None:
    rows = B.items(data)
    if not rows:
        print("nothing on the board")
        return
    tally: dict[str, int] = {}
    for ticket, item in sorted(rows, key=lambda r: int(r[1].get("id", 99))):
        st = item_state(item)
        tally[st["state"]] = tally.get(st["state"], 0) + 1
        who = f" on {st['who']}" if st.get("who") else ""
        note = f"  ({st['note']})" if st.get("note") else ""
        label = "" if st["state"] == "todo" else f"{st['state']}{who}"
        print(
            f"{MARK.get(st['state'], '[ ]')} {item.get('id')}. {label.ljust(22)} "
            f"{ticket.get('ref', '')}: {item.get('title', '')}{note}"
        )
    finished = sum(n for s, n in tally.items() if s in B.CLOSED_STATES)
    print(
        f"\n{tally.get('todo', 0)} with you, {tally.get('hold', 0)} not yet, "
        f"{tally.get('waiting', 0)} with someone else, {finished} finished"
    )


def rebuild() -> None:
    for script, out in (
        ("render_desk.py", "output/desk.html"),
        ("render_desk_md.py", "output/desk.md"),
    ):
        subprocess.run(
            [sys.executable, str(ROOT / script), str(B.BOARD), str(ROOT / out)],
            check=True,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("ids", nargs="*", help="item numbers from the desk")
    parser.add_argument("-n", "--note", default="", help="what happened, in a few words")
    parser.add_argument("-w", "--waiting", metavar="WHO", help="sent, now with this person")
    parser.add_argument(
        "--chase",
        metavar="WHEN",
        default="",
        help="when to chase if they stay quiet: a date (2026-09-16) or a condition. "
        "Use with -w, or on its own to set it on an item already waiting.",
    )
    parser.add_argument("--mine", action="store_true", help="it is back with you")
    parser.add_argument("--sent", action="store_true", help="finished, and it was a message")
    parser.add_argument("--dropped", action="store_true", help="finished, no longer worth doing")
    parser.add_argument("--undo", action="store_true", help="back to with you, clear the note")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="redraw both pages from the board without moving anything",
    )
    args = parser.parse_args()

    data = B.load()
    if not data.get("tickets"):
        print("no board yet. Run: tg build", file=sys.stderr)
        return 1

    # An agent that has just edited the board needs the pages redrawn and has no
    # state to move. It used to read this file to find the two render commands.
    if args.rebuild:
        rebuild()
        print("output/desk.html and output/desk.md rebuilt from the board")
        if not args.ids:
            return 0

    if not args.ids:
        show(data)
        return 0

    missing = [i for i in args.ids if B.by_id(data, i)[1] is None]
    if missing:
        print(f"no item numbered {', '.join(missing)}", file=sys.stderr)
        return 1

    for ident in args.ids:
        _, item = B.by_id(data, ident)
        if args.undo or args.mine:
            item.pop("hold", None)
            item.pop("waits_on", None)
            item["sent_by_you"] = False
            B.set_state(item, "todo", args.note)
            continue
        if args.waiting:
            item["sent_by_you"] = True
            B.set_state(item, "waiting", args.note, who=args.waiting)
            if args.chase:
                item.setdefault("waits_on", {})["chase_on"] = args.chase
        elif args.dropped:
            B.set_state(item, "dropped", args.note)
        elif args.sent:
            B.set_state(item, "sent", args.note)
        elif args.chase:
            # --chase on its own: set the chase date on an item already waiting,
            # without moving its state or resetting how long it has been there.
            item.setdefault("waits_on", {})["chase_on"] = args.chase
        else:
            B.set_state(item, "done", args.note)

    # Snapshot before writing, the same as every agent run does. tick.py is the
    # most frequent writer, so it should not be the one without a way back.
    keep.keep("tick")
    B.save(data)
    rebuild()
    show(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
