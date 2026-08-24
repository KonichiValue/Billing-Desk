#!/usr/bin/env python3
"""Push the post-standup actions into Apple Reminders.

The page is a good place to read the list and a bad place to remember it. This
puts every action into a "TG standup" list with its rank, ticket and estimate,
due today for anything actionable and on the chase date for anything held. Held
items are titled so it is obvious they are waiting, and every reminder carries
the link to act in.

Existing reminders for the same date are removed first, so re-running after a
regenerate does not duplicate.

Usage:
    python3 remind.py output/post-2026-08-24.json
    python3 remind.py output/post-2026-08-24.json --list "Work"
    python3 remind.py output/post-2026-08-24.json --dry-run
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from render import plain

DEFAULT_LIST = "TG standup"


def applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript failed")
    return result.stdout.strip()


def quote(value: str) -> str:
    """AppleScript string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def as_date(value: str) -> str:
    """An AppleScript date expression for 09:30 on the given ISO date."""
    d = datetime.strptime(value, "%Y-%m-%d")
    return (
        f'(current date) - (time of (current date)) + (9 * hours) + (30 * minutes) '
        f'+ ({(d.date() - date.today()).days} * days)'
    )


def build(data: dict) -> list[dict]:
    meeting = data.get("meeting_date") or date.today().isoformat()
    out = []
    for ticket in data.get("tickets", []):
        ref = ticket.get("ref", "")
        for action in ticket.get("actions", []):
            hold = action.get("hold") or {}
            mins = action.get("est_minutes")
            title = f"{action.get('rank', '?')}. {ref}: {action.get('title', '')}"
            if hold:
                title = f"{title} (waiting)"
            due = hold.get("revisit") if hold else meeting
            body = [action.get("why", "")]
            if hold:
                body.append(f"On hold: {hold.get('why', '')}")
                body.append(f"Waiting for: {hold.get('until', '')}")
            body += [b for b in action.get("detail", [])]
            if action.get("link"):
                body.append(action["link"])
            if action.get("draft"):
                body.append("--- draft ---")
                body.append(plain(action["draft"].get("body_ruby", "")))
            out.append(
                {
                    "title": title,
                    "due": due or meeting,
                    "body": "\n".join(b for b in body if b),
                    "minutes": mins,
                }
            )
    return sorted(out, key=lambda r: r["title"])


def push(items: list[dict], list_name: str, tag: str) -> None:
    lines = [
        "tell application \"Reminders\"",
        f"  if not (exists list {quote(list_name)}) then make new list with properties {{name:{quote(list_name)}}}",
        f"  tell list {quote(list_name)}",
        f"    delete (every reminder whose completed is false and body contains {quote(tag)})",
    ]
    for item in items:
        note = f"{item['body']}\n\n{tag}"
        lines.append(
            "    make new reminder with properties {"
            f"name:{quote(item['title'])}, "
            f"body:{quote(note)}, "
            f"due date:{as_date(item['due'])}"
            "}"
        )
    lines += ["  end tell", "end tell"]
    applescript("\n".join(lines))


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    list_name = DEFAULT_LIST
    if "--list" in args:
        i = args.index("--list")
        list_name = args[i + 1]
        del args[i : i + 2]

    src = Path(args[0])
    if not src.exists():
        print(f"missing {src}", file=sys.stderr)
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    items = build(data)
    if not items:
        print("nothing to push")
        return 0

    tag = f"[tg-standup {data.get('meeting_date', date.today().isoformat())}]"

    if dry:
        for item in items:
            print(f"{item['due']}  {item['title']}")
        return 0

    try:
        push(items, list_name, tag)
    except RuntimeError as exc:
        print(f"could not reach Reminders: {exc}", file=sys.stderr)
        return 1
    print(f"pushed {len(items)} reminders to '{list_name}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
