#!/usr/bin/env python3
"""Render the post-standup JSON into markdown.

The HTML page is for reading. This markdown file is for working: it is what a
Cursor chat in this repo reads when Rei says "draft the reply to Nakayama-san"
or "check the codebase for X". Keep it dense, keep every link, and keep the
ticket grouping so a single block is enough context to act on.

Usage:
    python3 render_md.py output/post-2026-08-24.json output/post-2026-08-24.md
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from render import plain

URGENCY = {"today": "TODAY", "this-week": "this week", "monitor": "monitor"}


def link(label: str, url: str) -> str:
    return f"[{label}]({url})" if url else label


def block(title: str, rows: list[str]) -> list[str]:
    return [f"### {title}", "", *rows, ""] if rows else []


def first_sentence(text: str) -> str:
    """One sentence, for table cells. The rest of the why sits under the action."""
    head = text.split(". ")[0].strip()
    return head if head.endswith(".") else f"{head}."


def render_draft(d: dict, indent: str = "") -> list[str]:
    if not d:
        return []
    lang = "Japanese" if d.get("language") == "ja" else "English"
    out = [
        f"{indent}**Draft ({lang})** for {d.get('target', '')}"
        + (f" ({link('open thread', d['link'])})" if d.get("link") else ""),
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
        f"- Status: {t.get('status_label', '')}"
        + ("" if t.get("raised_at_standup", True) else " (not reached at the standup)"),
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
    for c in t.get("changed_today", []):
        changed += [
            f"- **Was:** {c.get('before', '')}",
            f"  **Now:** {c.get('after', '')}",
            f"  **So:** {c.get('so_what', '')}",
            f"  Source: {c.get('where', '')} {link('link', c.get('source_url', ''))}",
            "",
        ]
    out += block("What changed today", changed)

    actions: list[str] = []
    for a in sorted(t.get("actions", []), key=lambda x: x.get("rank", 99)):
        mins = f", {a['est_minutes']} min" if a.get("est_minutes") else ""
        hold = a.get("hold") or {}
        state = "WAIT" if hold else URGENCY.get(a.get("urgency", "monitor"), "monitor")
        actions.append(
            f"#### {a.get('rank', '-')}. {a.get('title', '')} [{state}{mins}]"
        )
        actions.append("")
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
        actions += render_draft(a.get("draft") or {})
    out += block("To do, hardest consequence first", actions)

    waiting = [
        f"- **{w.get('who', '')}** owes: {w.get('what', '')} "
        f"(due {w.get('due', 'not stated')}, chase {w.get('chase_on', '')}). "
        f"Blocks: {w.get('blocks', '')} {link('source', w.get('source_url', ''))}"
        for w in t.get("waiting_on", [])
    ]
    out += block("Waiting on someone else", waiting)

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

    return out


def render(data: dict) -> str:
    meeting_date = data.get("meeting_date") or date.today().isoformat()
    try:
        pretty = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%A %-d %B %Y")
    except ValueError:
        pretty = meeting_date

    tickets = data.get("tickets", [])
    total = sum(a.get("est_minutes") or 0 for t in tickets for a in t.get("actions", []))

    out = [
        f"# After the TG billing standup, {pretty}",
        "",
        data.get("headline", ""),
        "",
        f"Meeting note: {link('Notion', data.get('notion_url', ''))}. "
        f"Generated {data.get('generated_at', '')}.",
        "",
    ]

    nxt = data.get("next_standup") or {}
    if nxt.get("skipped"):
        out += [
            f"> **No standup on {nxt.get('date', '')}.** {nxt.get('reason', '')} "
            "Anything that was waiting for that meeting has to move into Asana.",
            "",
        ]

    held = [
        (t.get("ref", ""), a)
        for t in tickets
        for a in t.get("actions", [])
        if a.get("hold")
    ]
    if held:
        out += ["## Wait before you send", ""]
        for ref, a in held:
            hold = a["hold"]
            revisit = f" Chase on {hold['revisit']}." if hold.get("revisit") else ""
            out.append(
                f"- **{ref}: {a.get('title', '')}.** {hold.get('why', '')} "
                f"Wait for: {hold.get('until', '')}.{revisit}"
            )
        out.append("")

    ordered = sorted(
        ((t.get("ref", ""), a) for t in tickets for a in t.get("actions", [])),
        key=lambda p: p[1].get("rank", 99),
    )
    if ordered:
        out += [
            f"## Running order{f' ({total} min in total)' if total else ''}",
            "",
            "| # | Ticket | Do this | Why | When | Min |",
            "|---|---|---|---|---|---|",
        ]
        for ref, a in ordered:
            state = (
                "wait"
                if a.get("hold")
                else URGENCY.get(a.get("urgency", "monitor"), "monitor")
            )
            out.append(
                f"| {a.get('rank', '')} | {ref} | {a.get('title', '')} | "
                f"{first_sentence(a.get('why', ''))} | {state} | "
                f"{a.get('est_minutes', '')} |"
            )
        out.append("")

    for t in tickets:
        out += render_ticket(t)

    if data.get("watch"):
        out += ["## Not mine, but adjacent", ""]
        out += [
            f"- **{w.get('topic', '')}**: {w.get('why', '')} "
            f"{link('source', w.get('source_url', ''))}"
            for w in data["watch"]
        ]
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
