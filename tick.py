#!/usr/bin/env python3
"""Mark actions on today's post-standup list as done, then rebuild both pages.

The list is only useful if it tells the truth about what is left, and updating
it should cost nothing. So:

    ./tick.py                 what is left, what is closed
    ./tick.py 1 3             close actions 1 and 3
    ./tick.py 2 -n "asked Kevin, waiting"   close 2 with a note
    ./tick.py 4 --sent        close 4 as sent rather than done
    ./tick.py 5 --dropped -n "TG answered it themselves"
    ./tick.py 1 --undo        reopen 1

Numbers are the ranks in the running order. State lives in
state/progress-<meeting-date>.json, separate from the generated report, so
regenerating the report keeps your progress.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATES = {"--done": "done", "--sent": "sent", "--dropped": "dropped"}


def latest_report() -> Path | None:
    reports = sorted((ROOT / "output").glob("post-*.json"))
    return reports[-1] if reports else None


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def actions(data: dict) -> dict[str, tuple[str, str]]:
    """rank -> (ticket ref, title)."""
    return {
        str(a.get("rank")): (t.get("ref", ""), a.get("title", ""))
        for t in data.get("tickets", [])
        for a in t.get("actions", [])
    }


def show(data: dict, progress: dict) -> None:
    rows = actions(data)
    if not rows:
        print("no actions on this list")
        return
    for rank in sorted(rows, key=lambda r: int(r) if r.isdigit() else 99):
        ref, title = rows[rank]
        st = progress.get(rank)
        mark = f"[{st['state']}]" if st else "[ open ]"
        note = f"  ({st['note']})" if st and st.get("note") else ""
        print(f"{mark} {rank}. {ref}: {title}{note}")
    open_count = len([r for r in rows if r not in progress])
    print(f"\n{open_count} of {len(rows)} still open")


def rebuild(report: Path) -> None:
    for script, ext in (("render_post.py", "html"), ("render_md.py", "md")):
        subprocess.run(
            [sys.executable, str(ROOT / script), str(report), str(report.with_suffix(f".{ext}"))],
            check=True,
            cwd=ROOT,
        )


def main() -> int:
    args = sys.argv[1:]
    report = latest_report()
    if report is None:
        print("no post-standup report in output/", file=sys.stderr)
        return 1

    data = load(report)
    meeting_date = data.get("meeting_date") or report.stem.replace("post-", "")
    state_file = ROOT / "state" / f"progress-{meeting_date}.json"
    progress = (
        load(state_file).get("actions", {})
        if state_file.exists()
        else {}
    )

    if not args:
        show(data, progress)
        return 0

    note = ""
    if "-n" in args:
        i = args.index("-n")
        note = args[i + 1] if len(args) > i + 1 else ""
        del args[i : i + 2]

    undo = "--undo" in args
    args = [a for a in args if a != "--undo"]
    state = next((STATES[a] for a in args if a in STATES), "done")
    ranks = [a for a in args if a not in STATES]

    known = actions(data)
    unknown = [r for r in ranks if r not in known]
    if unknown:
        print(f"no action numbered {', '.join(unknown)}", file=sys.stderr)
        return 1
    if not ranks:
        print("give at least one action number", file=sys.stderr)
        return 1

    stamp = datetime.now().strftime("%H:%M")
    for rank in ranks:
        if undo:
            progress.pop(rank, None)
        else:
            progress[rank] = {"state": state, "at": stamp, "note": note}

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"meeting_date": meeting_date, "actions": progress}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    rebuild(report)
    print()
    show(data, progress)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
