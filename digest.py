#!/usr/bin/env python3
"""Everything a sweep needs to read off the board, in one call.

A refresh used to open `state/board.json` fifteen times: a one-liner to list the
tickets, another for the threads, another to remember what an item said, a dump
into `/tmp` and a read back out of it. Each of those is a round trip worth
several seconds, and together they were most of an eight minute refresh, none of
it spent talking to Asana or Slack.

So this prints the whole readable half of the board at once: what is on it, what
is open, where each ticket stands, which threads to read and when each was last
read. `--full` adds closed items and untruncated prose for the rare sweep that
needs them.

It never writes. The writing half is `import board; b = board.load(); ...;
board.save(b)`, and `./tick.py` rebuilds the pages.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import audit
import board as B

WRAP = 160
ROOT = Path(__file__).resolve().parent


def _project_gids() -> list[str]:
    """The two TG project gids the gate query runs against, from config.json."""
    try:
        conf = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        return [p["gid"] for p in conf.get("asana", {}).get("projects", []) if p.get("gid")]
    except (OSError, ValueError, KeyError):
        return []


def _age(stamp: str) -> str:
    """How stale the board is, in the words Rei would use out loud."""
    if not stamp:
        return "never"
    try:
        then = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    secs = (datetime.now().astimezone() - then).total_seconds()
    if secs < 0:
        return "in the future"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m ago"
    hours, mins = divmod(mins, 60)
    if hours < 24:
        return f"{hours}h {mins}m ago"
    return f"{hours // 24}d {hours % 24}h ago"


def _clip(text: object, limit: int, full: bool = False) -> str:
    s = " ".join(str(text or "").split())
    if full or len(s) <= limit:
        return s
    return s[:limit].rstrip() + f"... (+{len(s) - limit} chars)"


def _out(line: str = "") -> None:
    print(line)


def _ticket_head(t: dict, full: bool) -> None:
    ref = t.get("ref") or t.get("id")
    asana = t.get("asana") or {}
    _out(f"=== {ref}   gid {t.get('id', '?')} ===")
    _out(f"    title_ja: {_clip(t.get('title_ja'), 90, full)}")
    _out(f"    title_en: {_clip(t.get('title_en'), 90, full)}")
    if t.get("asana_url"):
        _out(f"    url: {t['asana_url']}")
    if asana:
        bits = [
            f"{k}={asana[k]}"
            for k in ("status", "section", "priority", "severity", "assignee", "completed")
            if asana.get(k) not in (None, "")
        ]
        if bits:
            _out("    asana: " + "  ".join(bits))
    if t.get("no_ticket_yet"):
        _out(f"    NO TICKET YET: {_clip(t['no_ticket_yet'], 120, full)}")

    it = t.get("internal_ticket") or {}
    if it.get("none_yet"):
        _out(f"    internal: none, because {_clip(it['none_yet'], 110, full)}")
    elif it:
        bld = it.get("build") or {}
        bits = [f"{k}={bld[k]}" for k in ("kt", "stage", "engineer", "size") if bld.get(k)]
        _out(f"    internal: {it.get('name', '?')} {' '.join(bits)}")
        if bld.get("waiting_on"):
            _out(f"      waiting_on: {_clip(bld['waiting_on'], 110, full)}")

    la = t.get("last_activity") or {}
    if la:
        _out(f"    last_activity: {la.get('at', '?')} {la.get('who', '')} ({la.get('where', '')})")
    _out(f"    where_it_stands: {_clip(t.get('where_it_stands'), 400, full)}")

    gates = t.get("closes_when") or []
    if gates:
        _out(f"    closes_when ({len(gates)}):")
        for g in gates:
            who = f" [{g['who']}]" if g.get("who") else ""
            _out(f"      ({g.get('state', '?'):<7}){who} {_clip(g.get('what'), 100, full)}")
            if full and g.get("note"):
                _out(f"          note: {_clip(g['note'], 200, True)}")

    threads = t.get("threads") or []
    if threads:
        _out(f"    threads ({len(threads)}), read the ones with live discussion:")
        for th in threads:
            last = f"{th.get('last_from', '?')} @ {th.get('last_at', '?')}"
            _out(f"      - [{th.get('where', '?')}] {_clip(th.get('label'), 60, full)} | last: {last}")
            _out(f"        {th.get('url', '')}")
            if full and th.get("gist"):
                _out(f"        gist: {_clip(th['gist'], 200, True)}")

    events = t.get("events") or []
    if events:
        shown = events if full else events[-4:]
        _out(f"    events ({len(events)} total, showing {len(shown)}):")
        for e in shown:
            _out(
                f"      - {e.get('on', '?')} {e.get('at', '')} {e.get('who', '?')}: "
                f"{_clip(e.get('what'), 130, full)}"
            )


def _item_line(i: dict, full: bool) -> None:
    state = i.get("state", "todo")
    mark = {"todo": " ", "waiting": "~", "hold": "H", "done": "x", "sent": "x", "dropped": "-"}
    flag = mark.get(state, "?")
    waits = i.get("waits_on") or {}
    tail = f" -> {waits.get('who')}" if waits.get("who") else ""
    _out(
        f"      [{flag}] {str(i.get('id', '?')):>3}  {state:<8} {i.get('urgency', '-'):<10}"
        f" {i.get('est_minutes', '?')}m  {_clip(i.get('title'), 90, full)}{tail}"
    )
    meta = []
    if i.get("after"):
        meta.append(f"after={i['after']}")
    if i.get("at_standup"):
        meta.append("at_standup")
    if i.get("hold"):
        meta.append(f"HOLD: {_clip(i['hold'], 70, full)}")
    d = i.get("draft")
    if d:
        meta.append(f"draft={d.get('language', '?')}->{_clip(d.get('target'), 40, full)}")
    p = i.get("prepared")
    if p:
        meta.append(
            f"prepared({len(p.get('findings', []))} findings,"
            f" {len(p.get('files', []))} files, built {p.get('built_at', '?')})"
        )
    if meta:
        _out("            " + " | ".join(meta))
    if i.get("where"):
        _out(f"            where: {_clip(i.get('where'), 90, full)}")
    for n, s in enumerate(i.get("steps") or [], 1):
        _out(f"            step {n}: {_clip(s, 150, full)}")
    if i.get("done_when"):
        _out(f"            done_when: {_clip(i.get('done_when'), 150, full)}")
    if i.get("progress_note"):
        _out(f"            progress: {_clip(i.get('progress_note'), 200, full)}")
    if i.get("state_note"):
        _out(f"            state_note: {_clip(i.get('state_note'), 120, full)}")


def _sweep_plan(b: dict) -> None:
    """The worklist for a sweep, made from the watermarks rather than reasoned out.

    A sweep used to work out what to read by dumping the board through a dozen
    one-liners: which tickets, which threads, from when. All of that is already on
    the board, so this prints it as instructions the sweep can follow without
    opening `state/board.json` at all. Read exactly what this names, from the
    timestamps it names, and nothing turns into reconnaissance.
    """
    checked = b.get("checked_at", "")
    since = checked[:10] if checked else "never"
    gids = _project_gids()
    _out("SWEEP PLAN  (read this, not the raw board -- built from the watermarks above)")
    _out(
        "  1. Asana gate, ONE call: search_tasks modified_at.after=" + (since or "?")
        + (f" projects={','.join(gids)}" if gids else "")
    )
    _out(
        "     Deep-read (get_task / get_task_stories) only the gids it returns, plus any"
    )
    _out(
        "     ticket whose thread moved below. An unchanged ticket costs the one gate call."
    )
    _out("  2. Threads worth reading -- only those NOT looked at since the ticket last moved.")
    _out("     After you look at one, set th['checked'] = board.now() so it drops off next time.")
    for t in b.get("tickets", []):
        threads = t.get("threads") or []
        if not threads:
            continue
        events = t.get("events") or []
        newest = max(
            (audit.as_date(e.get("on")) for e in events if audit.as_date(e.get("on"))),
            default=None,
        )
        need, quiet = [], 0
        for th in threads:
            looked = max(
                (d for d in (audit.as_date(th.get("checked")), audit.as_date(th.get("last_at"))) if d),
                default=None,
            )
            if newest is not None and looked is not None and looked >= newest:
                quiet += 1
            else:
                need.append(th)
        if not need:
            _out(f"     {t.get('ref')}: all {len(threads)} looked at since the last event -- skip")
            continue
        _out(f"     {t.get('ref')}:" + (f"  ({quiet} quiet, skip)" if quiet else ""))
        for th in need:
            _out(
                f"       - [{th.get('where', '?')}] from {th.get('last_at', '?')}"
                f"  {th.get('url', '')}"
            )
    _out("  3. Build tickets, re-read only if the gate flags them:")
    any_build = False
    for t in b.get("tickets", []):
        bld = (t.get("internal_ticket") or {}).get("build") or {}
        if bld.get("kt"):
            any_build = True
            _out(
                f"       - {bld['kt']} ({t.get('ref')}) stage={bld.get('stage', '?')}"
                f" moved_on={bld.get('moved_on', '?')}"
            )
    if not any_build:
        _out("       - none on the board")
    _out("  4. Open items, so a reply maps straight to a number to move:")
    for t in b.get("tickets", []):
        opens = [i for i in t.get("items", []) if B.is_open(i)]
        if not opens:
            continue
        bits = []
        for i in opens:
            who = (i.get("waits_on") or {}).get("who")
            tail = f"->{who}" if who else ""
            bits.append(f"{i.get('id')}({i.get('state', 'todo')}{tail})")
        _out(f"       {t.get('ref')}: " + "  ".join(bits))
    _out()


CHEATSHEET = """WRITE CHEATSHEET  (the whole of a sweep's writing -- no help(board), no board.json dump)

The three edits a sweep repeats need NO python -- use ./note.py, one command each:

  ./note.py checked 保安閉栓                     # stamp every thread on the ticket as looked-at now
  ./note.py checked 検針票諸元 --thread slack     # only threads whose url contains "slack"
  ./note.py checked 託送HOLD --thread <url> --last-at "2026-09-02 14:30" --last-from "Heqing"  # a newer message was there
  ./note.py event 保安閉栓 --who "Robert Balayan, Kraken CE" --what "..." --so-what "..." --where Slack --url "https://..."
  ./note.py swept                               # set checked_at = now (once, near the end)

Item STATE is ./tick.py (never hand-edit it):
  ./tick.py 34 -w "Sayaka, TG" -n "answered, awaiting sign-off"   # sent, ball with them
  ./tick.py 8 --mine        # they replied, back to him     ./tick.py 5 --dropped -n "TG handled it"

For the rest -- a draft to rewrite, a new item, a news row -- load once, mutate, save once.
board.save refuses a shape no renderer can survive, so a clean return is the confirmation;
do not read the file back:

  import board
  b = board.load()
  t = next(x for x in b["tickets"] if x["ref"] == "検針票諸元")   # a ticket by its tag
  _, i = board.by_id(b, 8)                                        # an item by its number

  i["draft"] = {"language": "ja", "target": "Tanaka-san", "body_ruby": "..."}   # after ./tick.py 8 --mine
  i["progress_note"] = "..."

  t["items"].append({"id": board.next_id(b), "state": "todo", "title": "...",   # genuinely new work
                     "steps": ["..."], "done_when": "...", "why": "...", "urgency": "today"})

  b.setdefault("news", []).append({"topic": "...", "what": "...", "why": "...",  # news row, five at most
                                   "on": "2026-09-02", "source_url": "..."})
  board.save(b)

REBUILD:  ./tick.py --rebuild   (once, at the end -- redraws both pages, moves nothing)
SCHEMA:   the docstring at the top of board.py is the contract. Read it once if you must;
          never run help(board), and never dump state/board.json to see a current value."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", action="store_true", help="closed items too, and no truncation")
    ap.add_argument("--items-only", action="store_true", help="just the work, no ticket context")
    args = ap.parse_args()
    full = args.full

    b = B.load()
    all_items = B.items(b)
    open_items = [(t, i) for t, i in all_items if B.is_open(i)]
    by_state: dict[str, int] = {}
    for _, i in all_items:
        by_state[i.get("state", "todo")] = by_state.get(i.get("state", "todo"), 0) + 1

    _out("BOARD DIGEST  (state/board.json, read-only)")
    _out(f"checked_at: {b.get('checked_at', 'never')}  ({_age(b.get('checked_at', ''))})")
    _out(f"next_id: {b.get('next_id')}   version: {b.get('version')}")
    _out(
        f"counts: {len(b.get('tickets', []))} tickets, {len(all_items)} items"
        f" ({len(open_items)} open) | " + ", ".join(f"{k}={v}" for k, v in sorted(by_state.items()))
    )
    id_counts = Counter(str(i.get("id")) for _, i in all_items)
    dupes = [ident for ident, n in id_counts.items() if n > 1]
    if dupes:
        _out(f"!! DUPLICATE ITEM NUMBERS: {sorted(dupes)} -- fix before writing")
    _out()

    # What the last sweep left behind, printed before anything else it might read.
    # A sweep is good at finding what moved and bad at noticing what it did not go
    # back and change, and every line here is the second kind: a date that has
    # passed, two records that disagree, a thread whose watermark is older than the
    # events taken out of it. That last one is why a sweep can run clean and still
    # miss things, because the next one reads forward from the stale mark.
    rep = audit.Report()
    for check in audit.CHECKS:
        check(b, rep)
    if rep.total:
        _out(f"OUT OF DATE ({rep.total}) -- fix these in this sweep, they are not warnings")
        for group, lines in rep.groups.items():
            _out(f"  {group}:")
            for line in lines:
                _out("  " + line)
        _out("  Run ./audit.py when you are done. It should print nothing.")
        _out()

    if not args.items_only:
        _sweep_plan(b)

    if not args.items_only:
        sessions = b.get("sessions") or []
        script = b.get("script") or {}
        _out(f"SESSIONS ({len(sessions)}, soonest first)   script.for_date={script.get('for_date', '-')}")
        for s in sessions:
            skip = "  SKIPPED: " + str(s.get("reason", "")) if s.get("skipped") else ""
            _out(
                f"  {s.get('date', '?')} {s.get('at', ''):<6} {s.get('kind', '?'):<9}"
                f" {_clip(s.get('label') or s.get('title'), 70, full)}{skip}"
            )
            for row in s.get("timetable") or []:
                if row.get("mine") or full:
                    star = "*" if row.get("mine") else " "
                    _out(f"      {star} {row.get('at', '?')} {_clip(row.get('what'), 100, full)}")
        _out()

        alert = b.get("alert") or {}
        if alert.get("what"):
            _out(f"ALERT: {_clip(alert['what'], 300, full)}")
            _out(f"       {alert.get('source_url', '')}")
            _out()

        news = b.get("news") or []
        _out(f"NEWS ({len(news)})")
        for n in news:
            _out(f"  - {n.get('on', '?')} {n.get('topic', '')}")
            _out(f"    {_clip(n.get('what'), 240, full)}")
            if n.get("why"):
                _out(f"    reaches you: {_clip(n['why'], 200, full)}")
        _out()

        for key in ("meeting_note", "migration_note"):
            note = b.get(key) or {}
            if note:
                _out(
                    f"{key}: date={note.get('date', '-')} found={note.get('found', '-')}"
                    f" {note.get('url', '')}"
                )
        for note in b.get("other_notes") or []:
            _out(f"other_note: {note.get('date', '-')} {_clip(note.get('title'), 60, full)}")
        _out(f"glossary: {len(b.get('glossary') or {})} terms")
        _out()

    _out("TICKETS AND WORK")
    _out()
    for t in b.get("tickets", []):
        if not args.items_only:
            _ticket_head(t, full)
        else:
            _out(f"=== {t.get('ref')} ===")
        rows = [i for i in t.get("items", []) if full or B.is_open(i)]
        closed = len(t.get("items", [])) - len(rows)
        _out(f"    items ({len(rows)} shown{'' if full else f', {closed} closed hidden'}):")
        for i in rows:
            _item_line(i, full)
        _out()

    _out(CHEATSHEET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
