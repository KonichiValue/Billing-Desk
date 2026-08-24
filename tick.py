#!/usr/bin/env python3
"""Move actions on today's post-standup list along, then rebuild both pages.

An action has one of three lives: it is with you, it is with somebody else, or
it is finished. Sending a message usually moves it to the middle one, and it
comes back to you on the same number when they reply.

    ./tick.py                            where everything is
    ./tick.py 4                          finished, nothing comes back
    ./tick.py 2 -w "Kevin"               sent, ball is with Kevin
    ./tick.py 2 -w "Kevin" -n "asked about the account-level hold"
    ./tick.py 2 --mine                   they replied, it is yours again
    ./tick.py 5 --dropped -n "TG answered it themselves"
    ./tick.py 1 --undo                   forget everything about 1

Numbers are the ranks in the running order and never get reused, so "do 4"
means the same thing all day. State lives in state/progress-<meeting-date>.json,
away from the generated report, so rebuilding the report keeps it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from render import CLOSED_STATES as CLOSED
from render import action_state

ROOT = Path(__file__).resolve().parent
MARK = {
    "todo": "[ ]",
    "hold": "[!]",
    "waiting": "[~]",
    "done": "[x]",
    "sent": "[x]",
    "dropped": "[-]",
}


def latest_report() -> Path | None:
    reports = sorted((ROOT / "output").glob("post-*.json"))
    return reports[-1] if reports else None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def actions(data: dict) -> dict[str, tuple[str, dict]]:
    """rank -> (ticket ref, action)."""
    return {
        str(a.get("rank")): (t.get("ref", ""), a)
        for t in data.get("tickets", [])
        for a in t.get("actions", [])
    }


def show(data: dict, progress: dict) -> None:
    rows = actions(data)
    if not rows:
        print("no actions on this list")
        return
    tally: dict[str, int] = {}
    for rank in sorted(rows, key=lambda r: int(r) if r.isdigit() else 99):
        ref, action = rows[rank]
        st = action_state(progress, action)
        tally[st["state"]] = tally.get(st["state"], 0) + 1
        who = f" on {st['who']}" if st.get("who") else ""
        note = f"  ({st['note']})" if st.get("note") else ""
        label = "" if st["state"] == "todo" else f"{st['state']}{who}"
        print(
            f"{MARK.get(st['state'], '[ ]')} {rank}. {label.ljust(22)} "
            f"{ref}: {action.get('title', '')}{note}"
        )
    finished = sum(n for s, n in tally.items() if s in CLOSED)
    print(
        f"\n{tally.get('todo', 0)} with you, {tally.get('hold', 0)} not yet, "
        f"{tally.get('waiting', 0)} with someone else, {finished} finished"
    )


def rebuild(report: Path) -> None:
    for script, ext in (("render_post.py", "html"), ("render_md.py", "md")):
        subprocess.run(
            [sys.executable, str(ROOT / script), str(report), str(report.with_suffix(f".{ext}"))],
            check=True,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("ranks", nargs="*", help="action numbers from the running order")
    parser.add_argument("-n", "--note", default="", help="what happened, in a few words")
    parser.add_argument("-w", "--waiting", metavar="WHO", help="sent, now with this person")
    parser.add_argument("--mine", action="store_true", help="it is back with you")
    parser.add_argument("--sent", action="store_true", help="finished, and it was a message")
    parser.add_argument("--dropped", action="store_true", help="finished, no longer worth doing")
    parser.add_argument("--undo", action="store_true", help="forget the state entirely")
    args = parser.parse_args()

    report = latest_report()
    if report is None:
        print("no post-standup report in output/", file=sys.stderr)
        return 1

    data = load(report)
    meeting_date = data.get("meeting_date") or report.stem.replace("post-", "")
    state_file = ROOT / "state" / f"progress-{meeting_date}.json"
    progress = load(state_file).get("actions", {}) if state_file.exists() else {}

    if not args.ranks:
        show(data, progress)
        return 0

    known = actions(data)
    unknown = [r for r in args.ranks if r not in known]
    if unknown:
        print(f"no action numbered {', '.join(unknown)}", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%H:%M")
    for rank in args.ranks:
        if args.undo or args.mine:
            progress.pop(rank, None)
            continue
        entry = {"at": stamp, "note": args.note}
        if args.waiting:
            entry.update(state="waiting", who=args.waiting)
        elif args.dropped:
            entry["state"] = "dropped"
        elif args.sent:
            entry["state"] = "sent"
        else:
            entry["state"] = "done"
        progress[rank] = entry

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"meeting_date": meeting_date, "actions": progress}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    rebuild(report)
    show(data, progress)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
