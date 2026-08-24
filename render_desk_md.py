#!/usr/bin/env python3
"""Render the board into markdown.

The HTML page is for reading. This markdown file is for working: it is what a
Cursor chat in this repo reads when Rei says "draft the reply to Nakayama-san"
or "check the codebase for X". Keep it dense, keep every link, and keep the
ticket grouping so a single block is enough context to act on.

Usage:
    python3 render_desk_md.py state/board.json output/desk.md
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from render import item_state as state_of
from render import next_live, plain, sessions, tracked, when_words


def link(label: str, url: str) -> str:
    return f"[{label}]({url})" if url else label


def block(title: str, rows: list[str]) -> list[str]:
    return [f"### {title}", "", *rows, ""] if rows else []


def first_sentence(text: str) -> str:
    """One sentence, for table cells. The rest of the why sits under the action."""
    head = text.split(". ")[0].strip()
    return head if head.endswith(".") else f"{head}."


def render_draft(d: dict, st: dict | None = None) -> list[str]:
    if not d:
        return []
    lang = "Japanese" if d.get("language") == "ja" else "English"
    gone = st and st["state"] not in {"todo", "hold"}
    head = (
        f"**Sent {st.get('at', '')}** to {d.get('target', '')}"
        if gone
        else f"**Draft ({lang})** for {d.get('target', '')}"
    )
    out = [
        head + (f" ({link('open thread', d['link'])})" if d.get("link") else ""),
        "",
        "```",
        plain(d.get("body_ruby", "")),
        "```",
        "",
    ]
    if d.get("body_en"):
        out += ["<details><summary>English</summary>", "", "```", d["body_en"], "```", "", "</details>", ""]
    return out


def render_ticket(t: dict) -> list[str]:
    out: list[str] = [
        f"## {t.get('ref', '')}: {t.get('title_en', '')}",
        "",
        f"**{t.get('title_ja', '')}**",
        "",
        f"- Asana: {link(t.get('title_ja', 'ticket'), t.get('asana_url', ''))}",
        f"- Asana status: {(t.get('asana') or {}).get('status', 'unknown')}, "
        f"{(t.get('asana') or {}).get('section', 'no section')}, "
        f"priority {(t.get('asana') or {}).get('priority', 'unset')}",
    ]

    internal = t.get("internal_ticket") or {}
    if internal.get("name"):
        out.append(
            f"- Internal build ticket, never mentioned to TG: "
            f"{link(internal['name'], internal.get('url', ''))}"
        )
    out += ["", t.get("where_it_stands", ""), ""]

    terms = [
        f"- **{tm.get('term', '')}**: {tm.get('means', '')} "
        f"{link('source', tm.get('source_url', ''))}"
        for tm in t.get("terms", [])
    ]
    out += block("What the shorthand means", terms)

    changed = []
    for c in sorted(t.get("events", []), key=lambda x: (x.get("on", ""), x.get("at", ""))):
        when = f"{c.get('on', '')} {c.get('at', '')}".strip()
        changed.append(f"- **{when} {c.get('who', '')}** {c.get('what', '')}")
        if c.get("so_what"):
            changed.append(f"  So: {c['so_what']}")
        changed += [
            f"  Source: {c.get('where', '')} {link('link', c.get('source_url', ''))}",
            "",
        ]
    out += block("How this got here, in order", changed)

    actions: list[str] = []
    for a in sorted(
        t.get("items", []), key=lambda x: (state_of(x)["order"], x.get("id", 99))
    ):
        mins = f", {a['est_minutes']} min" if a.get("est_minutes") else ""
        hold = a.get("hold") or {}
        st = state_of(a)
        active = st["state"] in {"todo", "hold"}
        head = f"{a.get('id', '-')}. {a.get('title', '')} [{st['label'].upper()}{mins}]"
        if active:
            actions += [f"#### {head}", ""]
        else:
            actions += [f"<details><summary>{head}</summary>", ""]
        note = f" {st['note']}" if st.get("note") else ""
        if st["closed"]:
            actions += [f"> {st['label']} {st.get('at', '')}.{note}", ""]
        elif st["state"] == "waiting":
            waits = a.get("waits_on") or {}
            owed = f" They owe: {waits['what']}" if waits.get("what") else ""
            chase = f" Chase on {waits['chase_on']}." if waits.get("chase_on") else ""
            tail = f" {st['note']}." if st.get("note") else ""
            when = f"Sent {st['at']}. " if st.get("sent") else ""
            actions += [
                f"> {when}Nothing further from you until "
                f"{st.get('who', 'they')} answers.{owed}{tail}{chase}",
                "",
            ]
        if a.get("progress_note"):
            actions += [f"> Already happened: {a['progress_note']}", ""]
        if a.get("why"):
            actions += [f"**Why:** {a['why']}", ""]
        if hold:
            revisit = f" Chase on {hold['revisit']}." if hold.get("revisit") else ""
            actions += [
                f"> **Do not send this yet.** {hold.get('why', '')} "
                f"Wait for: {hold.get('until', '')}.{revisit}",
                "",
            ]
        for b in a.get("detail", []):
            actions.append(f"- {b}")
        if a.get("committed_to"):
            actions.append(f"- **You committed this to {a['committed_to']}.**")
        if a.get("blocked_by"):
            actions.append(f"- Blocked by: {a['blocked_by']}")
        actions.append(
            f"- Act in: {a.get('where', '')} {link('open', a.get('link', ''))}"
        )
        if a.get("source_quote"):
            actions += [
                "",
                f"> {a['source_quote']}",
                f"> {link('source', a.get('source_url', ''))}",
            ]
        actions.append("")
        actions += render_draft(a.get("draft") or {}, st)
        if not active:
            actions += ["</details>", ""]
    out += block("To do on this ticket", actions)

    decisions = []
    for d in t.get("open_decisions", []):
        decisions.append(f"- **{d.get('question', '')}**")
        for o in d.get("options", []):
            decisions.append(f"  - {o}")
        decisions.append(
            f"  - Decided by: {d.get('owner', '')} {link('source', d.get('source_url', ''))}"
        )
    out += block("Still undecided", decisions)

    threads = [
        f"- {link(th.get('label', 'thread'), th.get('url', ''))}: "
        f"{th.get('where', '')}. Last: {th.get('last_from', '')}, "
        f"{th.get('last_at', '')}. {th.get('gist', '')}"
        for th in t.get("threads", [])
    ]
    out += block("Every conversation this lives in", threads)
    out += render_prep(t.get("prep") or {})

    return out


def render_prep(prep: dict) -> list[str]:
    """The speaking half, in plain kanji: what he says and what he still asks.

    Furigana markup is stripped, because this file is read by an agent and by
    Rei in a chat, and `{託送|たくそう}` helps neither of them.
    """
    if not prep.get("script") and not prep.get("open_questions"):
        return []
    rows: list[str] = []
    if prep.get("issue"):
        rows += [f"- {b}" for b in prep["issue"]]
        if prep.get("why_it_matters"):
            rows.append(f"- Why it matters: {prep['why_it_matters']}")
        rows.append("")
    cons = prep.get("consequences") or {}
    labels = (
        ("fix_covers", "The fix covers"),
        ("falls_outside", "It does not cover"),
        ("accumulates", "So this piles up"),
        ("who_owns_it", "Owned by"),
        ("done_means", "Cleanup means"),
        ("still_open", "Still undecided"),
    )
    rows += [f"- **{label}:** {cons[key]}" for key, label in labels if cons.get(key)]
    if cons:
        rows.append("")
    for d in prep.get("decisions", []):
        rows.append(f"- **Settle in the room:** {d.get('need', '')}")
        if d.get("why"):
            rows.append(f"  Why now: {d['why']}")
        if d.get("fallback"):
            rows.append(f"  If they will not: {d['fallback']}")
    if prep.get("decisions"):
        rows.append("")
    for b in prep.get("script", []):
        rows += [
            f"**{b.get('heading', '')} ({b.get('heading_en', '')})**",
            "",
            "```",
            *[plain(line.get("ja_ruby", "")) for line in b.get("lines", [])],
            "```",
            "",
        ]
        rows += [f"- {line.get('en', '')}" for line in b.get("lines", [])]
        rows.append("")
    for p in prep.get("pushback", []):
        rows.append(f"- **If they say:** {p.get('they_say', '')}")
        rows.append(f"  Answer: {plain(p.get('say_ja', ''))}")
        if p.get("say_en"):
            rows.append(f"  ({p['say_en']})")
    if prep.get("pushback"):
        rows.append("")
    for q in prep.get("open_questions", []):
        rows.append(f"- **Ask {q.get('who', 'TG')}:** {q.get('en', '')}")
        rows.append(f"  {plain(q.get('ja_ruby', ''))}")
    if prep.get("unknowns"):
        rows.append("")
        rows += [f"- Check first: {u}" for u in prep["unknowns"]]
    return block("What I say in the room", rows)


def render(data: dict) -> str:
    pretty = date.today().strftime("%A %-d %B %Y")
    tickets = data.get("tickets", [])
    total = sum(
        i.get("est_minutes") or 0
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo"
    )

    out = [
        f"# Billing desk, {pretty}",
        "",
        data.get("headline", ""),
        "",
        f"Board last checked {data.get('checked_at', 'never')}. "
        f"Numbers stay with an item until it is closed, so 'do 4' means the same "
        f"thing tomorrow.",
        "",
    ]

    live = next_live(data)
    if live.get("date"):
        when = when_words(live.get("date", ""), live.get("at", ""))
        line = f"> **Next up: {live.get('title') or live.get('name')}, {when}.**"
        if live.get("focus"):
            line += f" {live['focus']}"
        out += [line, ""]
    for sess in sessions(data):
        if sess.get("skipped"):
            out += [
                f"> **No {sess.get('name', 'standup').lower()} on "
                f"{sess.get('date', '')}.** {sess.get('reason', '')} "
                "Anything that was waiting for it has to move into Asana.",
                "",
            ]

    rows = tracked(tickets)
    if rows:
        counts: dict[str, int] = {}
        for _, _, st in rows:
            key = "finished" if st["closed"] else st["state"]
            counts[key] = counts.get(key, 0) + 1
        summary = ", ".join(
            f"{counts[k]} {word}"
            for k, word in (
                ("todo", "with you"),
                ("hold", "not yet"),
                ("waiting", "with someone else"),
                ("finished", "finished"),
            )
            if counts.get(k)
        )
        out += [
            "## Everything you are carrying",
            "",
            f"**{summary}.**"
            + (f" About {total} min of work still with you." if total else ""),
            "",
        ]
        for ref, a, st in rows:
            bits = []
            if st["state"] == "waiting":
                who, since = st.get("who", "them"), st.get("at", "")
                bits.append(
                    f"sent {since}, with {who}"
                    if st.get("sent")
                    else f"with {who} since {since}"
                )
            elif st["closed"]:
                bits.append(f"{st['label'].lower()} {st.get('at', '')}")
            elif st["state"] == "hold":
                bits.append(f"not yet, until {(a.get('hold') or {}).get('until', '')}")
            else:
                bits.append("with you")
                if a.get("est_minutes"):
                    bits.append(f"{a['est_minutes']} min")
            if st.get("note"):
                bits.append(st["note"])
            tail = "; ".join(b for b in bits if b)
            out.append(
                f"- **{a.get('id', '')}. {ref}: {a.get('title', '')}** ({tail})"
            )
        out.append("")
        mine = [(r, a) for r, a, s in rows if s["state"] == "todo"]
        if not mine:
            out += ["Nothing is with you right now.", ""]
        else:
            out += ["**With you, in order:**", ""]
            for ref, a in mine:
                out.append(
                    f"{a.get('id', '')}. **{ref}: {a.get('title', '')}** "
                    f"{first_sentence(a.get('why', ''))}"
                )
            out.append("")

    for t in tickets:
        out += render_ticket(t)

    news = data.get("news") or data.get("watch") or []
    if news:
        out += ["## Around you at TG", "",
                "Not his tickets. Things that move them.", ""]
        for w in news:
            line = f"- **{w.get('topic', '')}**"
            if w.get("what"):
                line += f" {w['what']}"
            if w.get("why"):
                line += f" _{w['why']}_"
            out.append(f"{line} {link('source', w.get('source_url', ''))}")
        out.append("")

    if data.get("gaps"):
        out += ["## Open gaps", ""]
        out += [f"- {g}" for g in data["gaps"]]
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    src, dest = Path(args[0]), Path(args[1])
    if not src.exists():
        print(f"missing {src}", file=sys.stderr)
        return 1
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {src}: {exc}", file=sys.stderr)
        return 1
    dest.write_text(render(data), encoding="utf-8")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
