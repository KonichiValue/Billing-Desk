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
import os
import sys
from datetime import date, datetime
from pathlib import Path

from render import item_state as state_of
from render import (
    apply_glossary,
    blocked_on,
    index_items,
    item_order,
    next_live,
    plain,
    sessions,
    tracked,
    when_words,
)


# Questions asked from the page, by what they were asked about. Here so that a
# chat picking this file up knows what has already been asked and answered on a
# job, and does not contradict an answer he is looking at.
ASKED: dict[str, list[dict]] = {}


def load_asks(path: Path) -> None:
    ASKED.clear()
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("asks", [])
    except (OSError, ValueError):
        return
    for row in rows:
        if row.get("ref"):
            ASKED.setdefault(row["ref"], []).append(row)


def render_asks(ref: str) -> list[str]:
    """What he asked from the page, so a chat does not answer it differently.

    A follow-up says so, because "why" as a standalone question in this file
    would read as a question about the job.
    """
    out = []
    for a in ASKED.get(ref, []):
        if not a.get("answer"):
            continue
        lead = "Followed up" if a.get("parent") else "Asked"
        out += [
            f"**{lead} {a.get('asked_at', '')}:** {a.get('question', '')}",
            "",
            f"> {a['answer'].replace(chr(10), chr(10) + '> ')}",
            "",
        ]
    return out


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


STAGES = ("refining", "queued", "building", "review", "released", "verified")
STAGE_WORDS = {
    "refining": "Refining",
    "queued": "Queued",
    "building": "Building",
    "review": "In review",
    "released": "Released",
    "verified": "Verified",
}


def build_lines(internal: dict) -> list[str]:
    """The Kraken build under the status, in the same order as the page.

    A chat asked "where is 保安閉栓" has to be able to answer "queued, nobody on
    it" without opening Asana, and has to see the line it may repeat to TG
    without inventing one.
    """
    b = internal.get("build") or {}
    if not b:
        if internal.get("none_yet"):
            return [f"**Kraken build.** {internal['none_yet']}", ""]
        return []
    at = STAGES.index(b["stage"]) if b.get("stage") in STAGES else -1
    rail = " > ".join(
        f"**{STAGE_WORDS[s]}**" if n == at else STAGE_WORDS[s]
        for n, s in enumerate(STAGES)
    )
    facts = [f"Engineer {b.get('engineer') or 'nobody yet'}"]
    if b.get("size"):
        facts.append(f"size {b['size']}")
    if b.get("refined_by"):
        facts.append(f"refined by {b['refined_by']}")
    if b.get("feature_flag") == "Yes":
        facts.append("behind a feature flag")
    if b.get("moved_on"):
        facts.append(f"last moved {b['moved_on']}")
    out = [
        f"**Kraken build {b.get('kt', '')}, {b.get('asana_status', '')}.** "
        f"{b.get('waiting_on', '')}",
        "",
        f"- Stage: {rail}",
        f"- {', '.join(facts)}",
    ]
    if b.get("safe_to_say"):
        out.append(f"- What TG can be told: {b['safe_to_say']}")
    return out + [""]


def closes_lines(rows: list[dict]) -> list[str]:
    """What still has to fall before the ticket closes, gates nobody owns included."""
    if not rows:
        return []
    mark = {"done": "x", "now": " ", "blocked": " ", "next": " "}
    lines = []
    for r in rows:
        st = r.get("state", "next")
        who = f" ({r.get('who')})" if r.get("who") else ""
        tail = f" {r['note']}" if r.get("note") else ""
        flag = "" if st in {"done", "next"} else f" **{st}**"
        lines.append(f"- [{mark.get(st, ' ')}] {r.get('what', '')}{who}{flag}{tail}")
    done = sum(1 for r in rows if r.get("state") == "done")
    return block(f"What is left before this closes ({done} of {len(rows)} done)", lines)


def render_ticket(t: dict, index: dict[str, dict] | None = None) -> list[str]:
    index = index if index is not None else {
        str(i.get("id")): i for i in t.get("items", [])
    }
    out: list[str] = [
        f"## {t.get('ref', '')}: {t.get('title_en', '')}",
        "",
        f"**{t.get('title_ja', '')}**",
        "",
    ]
    if t.get("no_ticket_yet"):
        out.append(f"- No Asana ticket yet: {t['no_ticket_yet']}")
    else:
        out += [
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
    out += build_lines(internal)
    out += closes_lines(t.get("closes_when", []))

    terms = [
        f"- **{tm.get('term', '')}**"
        + (f" ({plain(tm['say'])})" if tm.get("say") else "")
        + f": {tm.get('means', '')} {link('source', tm.get('source_url', ''))}"
        for tm in t.get("terms", [])
    ]
    out += block("Words and shorthand on this ticket", terms)

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
    out += block("Timeline", changed)

    actions: list[str] = []
    for a in sorted(t.get("items", []), key=lambda x: item_order(x, index)):
        mins = f", {a['est_minutes']} min" if a.get("est_minutes") else ""
        hold = a.get("hold") or {}
        st = state_of(a)
        behind = blocked_on(a, index) if st["state"] in {"todo", "hold"} else ""
        active = st["state"] in {"todo", "hold"} and not behind
        label = f"AFTER {behind}" if behind else st["label"].upper()
        head = f"{a.get('id', '-')}. {a.get('title', '')} [{label}{mins}]"
        if active:
            actions += [f"#### {head}", ""]
        else:
            actions += [f"<details><summary>{head}</summary>", ""]
        note = f" {st['note']}" if st.get("note") else ""
        if behind:
            lead = index.get(behind) or {}
            actions += [
                f"> **Queued behind job {behind}.** Nothing to do here until "
                f"\u201c{lead.get('title', 'that one')}\u201d closes.",
                "",
            ]
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
        if hold:
            revisit = f" Chase on {hold['revisit']}." if hold.get("revisit") else ""
            actions += [
                f"> **Do not send this yet.** {hold.get('why', '')} "
                f"Wait for: {hold.get('until', '')}.{revisit}",
                "",
            ]
        prep = a.get("prepared") or {}
        if prep:
            built = f" ({prep['built_at']})" if prep.get("built_at") else ""
            actions += [f"**Prepared for you**{built}", ""]
            if prep.get("what"):
                actions += [prep["what"], ""]
            if prep.get("conclusion"):
                actions += [f"> **Bottom line:** {prep['conclusion']}", ""]
            tbl = prep.get("table") or {}
            if tbl.get("rows"):
                cols = tbl.get("columns", [])
                actions.append("| " + " | ".join(cols) + " |")
                actions.append("|" + "---|" * len(cols))
                for row in tbl["rows"]:
                    cells = [
                        str(c.get("text", "") if isinstance(c, dict) else c)
                        .replace("|", "\\|")
                        .replace("\n", " ")
                        for c in row
                    ]
                    actions.append("| " + " | ".join(cells) + " |")
                actions.append("")
            for f in prep.get("findings", []):
                actions.append(f"- {f}")
            if prep.get("findings"):
                actions.append("")
            for note in prep.get("notes", []):
                if note.get("heading") and note.get("body"):
                    actions += [f"**{note['heading']}:** {note['body']}", ""]
            if prep.get("unanswered"):
                actions.append("**Still unanswered**")
                actions.append("")
                for q in prep["unanswered"]:
                    actions.append(f"- {q}")
                actions.append("")
            files = [f for f in prep.get("files", []) if f.get("path") or f.get("url")]
            if files:
                actions += [
                    "Files it made: "
                    + ", ".join(
                        link(
                            f.get("label") or f.get("path") or f["url"],
                            f.get("path") or f["url"],
                        )
                        for f in files
                    ),
                    "",
                ]
            meeting = prep.get("meeting_use") or {}
            if meeting:
                actions += [
                    f"**Meeting version:** {meeting.get('summary', 'Use the What I say in the room section below.')}",
                    "",
                ]
            srcs = [s for s in prep.get("sources", []) if s.get("url")]
            if srcs:
                actions += [
                    "Built from: "
                    + ", ".join(link(s.get("label", "source"), s["url"]) for s in srcs),
                    "",
                ]
        steps = a.get("steps", [])
        if steps:
            actions.append("**Do this**")
            actions.append("")
            for n, b in enumerate(steps, 1):
                actions.append(f"{n}. {b}")
            actions.append("")
        actions.append(
            f"Do it in: {a.get('where', '')} {link('open', a.get('link', ''))}"
        )
        actions.append("")
        if a.get("done_when") and not st["closed"]:
            actions += [f"**Finished when:** {a['done_when']}", ""]
        if a.get("why"):
            actions += [f"**Why it matters:** {a['why']}", ""]
        if a.get("progress_note"):
            actions += [f"> Already happened: {a['progress_note']}", ""]
        if a.get("committed_to"):
            actions += [f"**You committed this to {a['committed_to']}.**", ""]
        if a.get("blocked_by"):
            actions += [f"Blocked by: {a['blocked_by']}", ""]
        if a.get("source_quote"):
            actions += [
                "",
                f"> {a['source_quote']}",
                f"> {link('source', a.get('source_url', ''))}",
            ]
        actions.append("")
        actions += render_draft(a.get("draft") or {}, st)
        actions += render_asks(f"item:{a.get('id')}")
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
    out += block("Asked about this ticket", render_asks(f"ticket:{t.get('ref')}"))
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
    _index = index_items(tickets)
    total = sum(
        i.get("est_minutes") or 0
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo" and not blocked_on(i, _index)
    )

    out = [
        f"# Billing desk, {pretty}",
        "",
        f"Board last checked {data.get('checked_at', 'never')}. "
        f"Numbers stay with an item until it is closed, so 'do 4' means the same "
        f"thing tomorrow.",
        "",
    ]

    alert = data.get("alert") or {}
    if isinstance(alert, str):
        alert = {"what": alert}
    if alert.get("what"):
        out += [
            f"> **Needs him now.** {alert['what']} "
            f"{link('source', alert.get('source_url', ''))}",
            "",
        ]

    live = next_live(data)
    if live.get("date"):
        when = when_words(live.get("date", ""), live.get("at", ""))
        line = f"> **Next up: {live.get('title') or live.get('name')}, {when}.**"
        if live.get("place"):
            line += f" {live['place']}."
        if live.get("focus"):
            line += f" {live['focus']}"
        out += [line, ""]
        for row in live.get("timetable", []):
            if row.get("what"):
                mark = " **<-**" if row.get("mine") else ""
                out.append(f"> - {row.get('at', '')} {row['what']}{mark}")
        if live.get("timetable"):
            out.append("")
    for sess in sessions(data):
        if sess.get("skipped"):
            out += [
                f"> **No {sess.get('name', 'standup').lower()} on "
                f"{sess.get('date', '')}.** {sess.get('reason', '')} "
                "Anything that was waiting for it has to move into Asana.",
                "",
            ]
            continue
        if sess.get("date") == live.get("date") and sess.get("at") == live.get("at"):
            continue
        when = when_words(sess.get("date", ""), sess.get("at", ""))
        line = f"> **After that: {sess.get('title') or sess.get('name')}, {when}.**"
        if sess.get("place"):
            line += f" {sess['place']}."
        if sess.get("focus"):
            line += f" {sess['focus']}"
        out += [line, ""]
        for thing in sess.get("bring", []):
            out.append(f"> - Bring: {thing}")
        if sess.get("bring"):
            out.append("")

    index = index_items(tickets)
    rows = tracked(tickets)
    if rows:
        counts: dict[str, int] = {}
        for _, a, st in rows:
            # Only work that would otherwise read "with you" diverts. An item
            # waiting on someone is already described by who holds it.
            if st["state"] == "todo" and blocked_on(a, index):
                counts["queued"] = counts.get("queued", 0) + 1
                continue
            key = "finished" if st["closed"] else st["state"]
            counts[key] = counts.get(key, 0) + 1
        summary = ", ".join(
            f"{counts[k]} {word}"
            for k, word in (
                ("todo", "with you"),
                ("queued", "queued behind another job"),
                ("hold", "not yet"),
                ("waiting", "with someone else"),
                ("finished", "finished"),
            )
            if counts.get(k)
        )
        out += [
            "## To do",
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
                behind = blocked_on(a, index)
                bits.append(f"queued behind {behind}" if behind else "with you")
                if a.get("est_minutes"):
                    bits.append(f"{a['est_minutes']} min")
            if st.get("note"):
                bits.append(st["note"])
            tail = "; ".join(b for b in bits if b)
            out.append(
                f"- **{a.get('id', '')}. {ref}: {a.get('title', '')}** ({tail})"
            )
        out.append("")
        mine = [
            (r, a)
            for r, a, s in rows
            if s["state"] == "todo" and not blocked_on(a, index)
        ]
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

    asked = render_asks("board")
    if asked:
        out += ["## Asked about the desk", "",
                "Questions about the day rather than one job, and what came back.",
                ""] + asked + [""]

    for t in tickets:
        out += render_ticket(t, index)

    news = data.get("news") or data.get("watch") or []
    if news:
        out += ["## TG news", "",
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
    load_asks(src.parent / "asks.json")
    # Write then rename, so a reader never catches the file half written.
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(render(apply_glossary(data)), encoding="utf-8")
    os.replace(tmp, dest)
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
