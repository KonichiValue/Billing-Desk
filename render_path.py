#!/usr/bin/env python3
"""The path to closing a ticket: its gates, and the work hanging off them.

Split out of `render_desk.py`, which had grown past 2200 lines and held eight
unrelated jobs in one file. This is the biggest single thing a ticket card
draws and the part most likely to be changed, so it gets its own file: the
spine, the items on it, and everything one item can carry (its steps, its
draft, the work already done for him).

`spine()` is the join that makes the merged section possible, and the comment
on it is the one to read before touching any of this. A gate names the items it
waits on in prose, not in a field, and an item no gate names is still his work
and still gets a row.
"""

from __future__ import annotations

import re
from pathlib import Path

import render_standup
from render import (
    ASKED,
    SPARK,
    apply_glossary,
    ask_block,
    blocked_on,
    code,
    due_words,
    esc,
    furi,
    item_order,
    item_state as state_of,
    link_btn,
    pill,
    plain,
    section,
    sub_line,
    when_tag,
)


ITEM_REF = re.compile(r"\bitems?\s+(\d+)", re.I)

def cell(value: object) -> str:
    """One cell of a prepared table, plain or carrying a verdict.

    A four-column comparison where every cell is a sentence hides the row that
    is the point of it. A cell written as {"text", "tone"} prints as a verdict
    instead, so the answer is findable before the evidence is read.
    """
    if isinstance(value, dict):
        tone = str(value.get("tone", "warn"))
        tone = tone if tone in ("good", "gap", "warn") else "warn"
        return f'<td class="pw-v"><span class="v-{tone}">{code(value.get("text"))}</span></td>'
    return f"<td>{code(value)}</td>"


def doc_btns(files: list) -> str:
    """The documents an item hands him, opened from the page it sits on.

    A handover sheet that lives only in the repo is a file he has to go and
    find, and one pasted into the page as prose is not the thing he gives
    anybody. The server carries docs/ at /doc/, so the button opens the real
    file, in the form the reader gets it.

    Some of what the work produces cannot live in `docs/` at all: a Miro board is
    the product of an afternoon and belongs beside the file it explains, so an
    entry may name a `url` instead of a `path`.
    """
    out = []
    for f in files or []:
        path = str(f.get("path", ""))
        url = str(f.get("url", ""))
        if not path and not url:
            continue
        label = f.get("label") or Path(path).name or url
        out.append(link_btn(f"/doc/{Path(path).name}" if path else url, label))
    return " ".join(o for o in out if o)


def render_draft(d: dict, st: dict | None = None) -> str:
    """A draft to paste, or, once it has gone, a folded record of what went."""
    if not d:
        return ""
    is_ja = d.get("language") == "ja"
    # Two shapes of draft. A Japanese draft keeps its furigana text in body_ruby and
    # body_en is the translation shown beneath it. An English draft (to a Kraken
    # colleague) keeps its text in body_en and has no body_ruby. Reading body_ruby
    # for both rendered every English draft blank -- the text was saved, never shown.
    # Both branches fall back through the other body keys, so a draft whose text
    # landed under body_ja or a bare body still renders instead of showing an empty
    # box: furi() passes plain text through untouched, so the worst case is no ruby,
    # never a blank card. board.check() refuses a draft with no body at all.
    if is_ja:
        body = d.get("body_ruby") or d.get("body_ja") or d.get("body", "")
        rendered = furi(body)
        trans = (
            f'<p class="draft-en">{esc(d.get("body_en"))}</p>'
            if d.get("body_en")
            else ""
        )
    else:
        body = d.get("body_en") or d.get("body_ruby") or d.get("body", "")
        rendered = esc(body)
        trans = ""
    # The draft is the thing he most often wants changed rather than explained,
    # and the box that changes it is at the foot of the card. This opens that box
    # with the ask already started, so a rewrite is one click from the words.
    inner = f"""
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go there")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
            <button class="ask-here" type="button"
                    data-ask-seed="Rewrite this draft: ">{SPARK}Rewrite or ask</button>
          </div>
          <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
          {trans}"""
    gone = st and st["state"] != "todo" and st["state"] != "hold"
    if gone:
        when = f" at {esc(st.get('at'))}" if st.get("at") else ""
        return f"""
        <details class="act-draft sent">
          <summary>What you sent{when}</summary>
          {inner}
        </details>"""
    return f'<div class="act-draft">{inner}</div>'


def prepared_block(p: dict, meeting_href: str = "") -> str:
    """Work that was already done for him, above the steps that remain.

    If a step can be followed without judgement then following it was never his
    job, so the page carries the product rather than the instruction. What is
    left underneath is the part only he can do: check it, decide with it, say it.
    """
    if not p:
        return ""
    head = ""
    tbl = p.get("table") or {}
    if tbl.get("rows"):
        cols = "".join(f"<th>{code(c)}</th>" for c in tbl.get("columns", []))
        body = "".join(
            "<tr>" + "".join(cell(c) for c in row) + "</tr>" for row in tbl["rows"]
        )
        head = f'<table class="pw-t"><thead><tr>{cols}</tr></thead><tbody>{body}</tbody></table>'
    finds = "".join(f"<li>{code(f)}</li>" for f in p.get("findings", []))
    notes = "".join(
        f'<div class="pw-note"><b>{esc(n.get("heading"))}</b>'
        f'{code(n.get("body"))}</div>'
        for n in p.get("notes", [])
        if n.get("heading") and n.get("body")
    )
    meeting = p.get("meeting_use") or {}
    meeting_block = ""
    if meeting and meeting_href:
        meeting_block = (
            '<div class="pw-meeting">'
            f'<span>{esc(meeting.get("summary", "Use this in the next session."))}</span>'
            f'<a class="btn" href="#{esc(meeting_href)}" data-goto="standup">'
            f'{esc(meeting.get("label", "Open meeting version"))}</a></div>'
        )
    open_qs = "".join(f"<li>{code(q)}</li>" for q in p.get("unanswered", []))
    docs = doc_btns(p.get("files", []))
    srcs = " ".join(
        link_btn(s.get("url", ""), s.get("label", "Source"))
        for s in p.get("sources", [])
        if s.get("url")
    )
    return f"""
            <div class="act-prep">
              <p class="act-lab done">Prepared for you{f' &middot; {esc(p.get("built_at"))}' if p.get("built_at") else ""}
                <button class="ask-here" type="button"
                        data-ask-seed="About the prepared work: ">{SPARK}Ask about this</button></p>
              {f'<p class="pw-what">{code(p.get("what"))}</p>' if p.get("what") else ""}
              {f'<p class="pw-answer"><b>Bottom line</b>{code(p.get("conclusion"))}</p>' if p.get("conclusion") else ""}
              {head}
              {f'<ul class="pw-f">{finds}</ul>' if finds else ""}
              {notes}
              {f'<div class="pw-open"><b>Still unanswered</b><ul>{open_qs}</ul></div>' if open_qs else ""}
              {f'<div class="pw-src"><span>Files it made</span>{docs}</div>' if docs else ""}
              {meeting_block}
              {f'<div class="pw-src"><span>Built from</span>{srcs}</div>' if srcs else ""}
            </div>"""


def steps_block(r: dict, steps: str, active: bool) -> str:
    """The steps, first thing inside the item, with somewhere to do them.

    This block used to open with Why, which is the one question he never asks of
    his own list: he knows why it is there, he wants to know what to type. So
    the hands-on part comes first, numbered because they are in an order, with
    the place to do it attached to the last step rather than floating below.
    """
    where = esc(r.get("where") or "")
    go = link_btn(r.get("link", ""), "Open where this happens")
    place = (
        f'<div class="act-where">{f"<span>{where}</span>" if where else ""}{go}</div>'
        if where or go
        else ""
    )
    if not steps:
        # A job with no steps is a job he has to work out from its title, which
        # is the failure this block exists to prevent. Say so, rather than
        # leaving a confident-looking gap.
        if not active:
            return place
        return f"""
            <p class="act-nosteps"><b>No steps written yet</b>Ask the chat to
            break job {esc(r.get("id", "-"))} down.</p>{place}"""
    return f"""
            <div class="act-do">
              <p class="act-lab">Do this</p>
              <ol class="steps">{steps}</ol>
              {place}
            </div>"""


def background(r: dict, quote: str) -> str:
    """Why this job exists, folded, under the work it explains.

    Why it matters, what already happened and the message it came out of are
    three paragraphs he reads once, when the job first appears, and never again.
    Open they pushed the next job off the screen; shut they are one line he can
    press when a job has stopped making sense.
    """
    inside = "".join(
        [
            f'<p class="act-why"><b>Why it matters</b>{esc(r.get("why"))}</p>'
            if r.get("why")
            else "",
            f'<p class="act-quote">Already happened: {esc(r.get("progress_note"))}</p>'
            if r.get("progress_note")
            else "",
            f'<p class="act-quote">{esc(quote)} '
            f'{link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</p>'
            if quote
            else "",
        ]
    )
    if not inside:
        return ""
    return f"""
            <details class="act-more">
              <summary>Why this is here<span class="fold-hint"></span></summary>
              {inside}
            </details>"""


def item_html(
    r: dict,
    raise_label: str = "Raise at standup",
    sess: dict | None = None,
    standup_href: str = "",
    ticket_ref: str = "",
    index: dict[str, dict] | None = None,
) -> str:
    """One job, as the row the spine hangs it on.

    Split out of `render_items` so the same job renders identically whether it
    sits under a gate on the path or on its own. The markup, the classes and the
    ask box are the ones that were already here: only who calls it changed.
    """
    return render_items(
        [r], raise_label, sess, standup_href, ticket_ref, index, bare=True
    )


def render_items(
    rows: list[dict],
    raise_label: str = "Raise at standup",
    sess: dict | None = None,
    standup_href: str = "",
    ticket_ref: str = "",
    index: dict[str, dict] | None = None,
    bare: bool = False,
) -> str:
    if not rows:
        return section(
            "To do on this ticket",
            '<p class="empty">Nothing on this one needs you. It is here because '
            "it is still open in Asana.</p>",
            role="now",
        )
    index = index if index is not None else {str(r.get("id")): r for r in rows}
    out = []
    for r in sorted(rows, key=lambda x: item_order(x, index)):
        steps = "".join(f"<li>{code(b)}</li>" for b in r.get("steps", []))
        mins = r.get("est_minutes")
        committed = r.get("committed_to")
        blocked = r.get("blocked_by")
        quote = r.get("source_quote")
        hold = r.get("hold") or {}
        st = state_of(r)
        done = st["closed"]
        status_block = ""
        if done:
            note = f" {esc(st['note'])}" if st.get("note") else ""
            status_block = (
                f'<p class="closed"><b>{esc(st["label"])}</b>'
                f'{esc(st.get("at", ""))}.{note}</p>'
            )
        elif st["state"] == "waiting":
            note = f" {esc(st['note'])}." if st.get("note") else ""
            waits = r.get("waits_on") or {}
            owed = f" They owe: {esc(waits['what'])}." if waits.get("what") else ""
            chase_line = (
                f" {esc(due_words(waits['chase_on']))}" if waits.get("chase_on") else ""
            )
            sent = f"Sent {esc(st.get('at', ''))}" if st.get("sent") else "Not yours"
            status_block = (
                f'<p class="sent-note"><b>{sent}</b>'
                f'Nothing further from you until {esc(st.get("who", "they"))} '
                f"answers.{owed}{note}{chase_line}</p>"
            )
        elif hold:
            revisit = hold.get("revisit")
            status_block = f"""
            <p class="hold"><b>Do not send this yet</b>{esc(hold.get("why"))}
            <span class="hold-until">Wait for: {esc(hold.get("until"))}.</span>
            {f'<span class="hold-until"> Chase on {esc(revisit)}.</span>' if revisit else ""}</p>"""
        state_pill = pill(st["label"], st["tone"])
        if r.get("at_standup") and not done:
            state_pill += pill(raise_label, "amber")
        due, due_kind = when_tag(r, st, sess)
        when_chip = f'<span class="when {due_kind}">{esc(due)}</span>' if due else ""
        chase = (r.get("waits_on") or {}).get("chase_on", "")
        # Anything not sitting with Rei folds shut, so the page is only as long
        # as the work he still has. Work queued behind another job folds for the
        # same reason: it is not a decision until the one in front of it closes.
        behind = blocked_on(r, index) if st["state"] in {"todo", "hold"} else ""
        active = st["state"] in {"todo", "hold"} and not behind
        tag, attrs = ("div", "") if active else ("details", "")
        head_tag = "div" if active else "summary"
        sub = sub_line(st) or (esc(due).lower() if chase and due else "")
        if behind:
            lead = index.get(behind) or {}
            sub = f"after job {esc(behind)}"
            status_block = (
                f'<p class="act-block"><b>Queued behind job {esc(behind)}</b>'
                f"Nothing to do here until "
                f"&ldquo;{esc(lead.get('title', 'that one'))}&rdquo; closes.</p>"
            ) + status_block
            # A red "With you" on something he cannot start is the whole problem
            # this field exists to fix, and a due date on it is a second lie.
            state_pill = pill(f"After {behind}", "grey") + (
                pill(raise_label, "amber") if r.get("at_standup") else ""
            )
            when_chip = ""
        out.append(
            f"""
        <{tag} class="act {st["state"]} {"held" if hold and not done else ""} {"commit" if committed else ""}"{attrs}>
          <{head_tag} class="act-head">
            <span class="act-rank">{esc(r.get("id", "-"))}</span>
            <span class="act-title">{esc(r.get("title"))}
              {f'<span class="act-sub">{sub}</span>' if sub and not active else ""}</span>
            {when_chip}
            {state_pill}
            <span class="act-min">{f"{esc(mins)} min" if mins and active else ""}</span>
          </{head_tag}>
          <div class="act-body">
            {status_block}
            {prepared_block(r.get("prepared") or {}, standup_href)}
            {steps_block(r, steps, active)}
            {render_draft(r.get("draft") or {}, st)}
            {f'<p class="act-done"><b>Finished when</b>{code(r.get("done_when"))}</p>' if r.get("done_when") and not done else ""}
            {f'<p class="act-commit">You committed this to {esc(committed)}</p>' if committed else ""}
            {f'<p class="act-block">Blocked by: {esc(blocked)}</p>' if blocked else ""}
            {background(r, quote)}
            {ask_block(
                f'item:{r.get("id")}',
                f'job {r.get("id")}, {ticket_ref}' if ticket_ref else f'job {r.get("id")}',
                ASKED.get(f'item:{r.get("id")}', []),
                f'Read prompt-ask.md, then answer this about job {r.get("id")}'
                f' on {ticket_ref} ("{r.get("title", "")}"):',
                bool(r.get("draft")),
            )}
          </div>
        </{tag}>"""
        )
    if bare:
        return "".join(out)
    live = sum(1 for r in rows if not state_of(r)["closed"])
    done = len(rows) - live
    tally = f"{live} open" if live else "all done"
    if done:
        tally += f", {done} closed"
    return section(
        "To do on this ticket",
        "".join(out),
        role="now",
        count=tally,
        hint="each keeps its number until it closes",
    )


def gate_items(gate: dict, live: dict[str, dict]) -> list[str]:
    """Which of this ticket's items a gate names, in the order it names them.

    The link is prose: a gate's note says "Item 4." or "item 32 confirms it with
    Robert". There is no field for it, and adding one would mean a sweep
    maintaining a join it currently gets right by writing a sentence. So the
    sentence is read.

    Only ids that are really items on this ticket count, so "item 37" on a
    ticket whose 37 was dropped does not invent a row.
    """
    seen: list[str] = []
    for num in ITEM_REF.findall(f'{gate.get("what", "")} {gate.get("note") or ""}'):
        if num in live and num not in seen:
            seen.append(num)
    return seen


def spine(t: dict, rows: list[dict], items: list[dict]) -> tuple[list[dict], int, int]:
    """The one ordered path to closing this ticket: gates, with his work on them.

    Three sections used to say overlapping things about the same fact. Item 4 on
    保安閉栓 was a row in "To do", a gate in "What is left before this closes",
    and two events in the timeline, so the card said the same thing three times
    in three different voices and he had to read all three to be sure they
    agreed.

    This is the merge. A gate is a step on the path; the items that step is
    waiting on hang under it. The gate says what "done" means and whose it is;
    the item says what he actually types.

    **An item that no gate names is still a row of its own.** Only 20 of the 67
    gates on this board name an item, so attaching items to gates alone would
    have hidden most of his open work, which is the one thing this page exists to
    show. Orphans come first when they are his and last when they are not.
    """
    live = {str(i.get("id")): i for i in items}
    claimed: set[str] = set()
    out: list[dict] = []
    for g in rows:
        ids = gate_items(g, live)
        claimed.update(ids)
        out.append({"gate": g, "items": [live[i] for i in ids]})

    loose = [i for i in items if str(i.get("id")) not in claimed]
    mine, theirs = [], []
    for i in loose:
        st = state_of(i)
        if st["closed"]:
            theirs.append(i)
        elif st["state"] == "todo":
            mine.append(i)
        else:
            theirs.append(i)
    lead = [{"gate": None, "items": [i]} for i in mine]
    tail = [{"gate": None, "items": [i]} for i in theirs]

    done = sum(1 for g in rows if g.get("state") == "done")
    return lead + out + tail, done, len(rows)


def render_path(
    t: dict,
    ident: str,
    raise_label: str,
    sess: dict | None,
    standup_href: str,
    index: dict[str, dict] | None,
) -> str:
    """The path to closing this ticket: every gate, with his work hanging on it.

    One section where there were three. The rows that are still live are drawn
    open; the stretch that is already behind him folds into a single line,
    because "5 of 8 done" is the fact and the five are the footnote.
    """
    items = t.get("items", [])
    gates = t.get("closes_when", [])
    rows, done, total = spine(t, gates, items)
    ref = t.get("ref", "")

    def is_settled(row: dict) -> bool:
        if any(not state_of(i)["closed"] for i in row["items"]):
            return False
        g = row["gate"]
        return (g or {}).get("state") == "done" if g else True

    def row_html(row: dict) -> str:
        g, kids = row["gate"], row["items"]
        work = "".join(
            item_html(i, raise_label, sess, standup_href, ref, index) for i in kids
        )
        if not g:
            # An item no gate names. It is his work all the same, so it is a step
            # on the path in its own right rather than a footnote to one. It
            # still gets a marker, or it floats beside the rail rather than on
            # it, and the column stops reading as one sequence.
            solo = state_of(kids[0]) if kids else {"state": "", "closed": False}
            dot = "done" if solo["closed"] else "mine" if solo["state"] == "todo" else "next"
            return f'<li class="step loose {dot}"><span class="g-m"></span>{work}</li>'
        state = g.get("state", "next")
        mine = any(state_of(i)["state"] == "todo" for i in kids)
        note = f'<span class="g-n">{esc(g.get("note"))}</span>' if g.get("note") else ""
        who = esc(g.get("who", ""))
        return f"""
        <li class="step {esc(state)}{" has-work" if work else ""}{" mine" if mine else ""}">
          <div class="step-head">
            <span class="g-m"></span>
            <span class="g-w">{esc(g.get("what"))}{note}</span>
            {f'<span class="g-who">{who}</span>' if who else ""}
          </div>
          {f'<div class="step-work">{work}</div>' if work else ""}
        </li>"""

    live_rows = [r for r in rows if not is_settled(r)]
    past = [r for r in rows if is_settled(r)]
    live_html = "".join(row_html(r) for r in live_rows)
    # What is still live comes first. The stretch behind him is a footnote under
    # it, not a preamble to it: he opens this section to find the next move.
    body = f'<ol class="steps-list">{live_html}</ol>' if live_html else (
        '<p class="empty">Every gate on this one has fallen. It stays on the '
        "page because Asana has not closed it.</p>"
    )
    if past:
        body += f"""
        <details class="step-past" data-remember="past-{esc(ident)}">
          <summary><span class="sp-n">{len(past)}</span>
            already behind you<span class="fold-hint"></span></summary>
          <ol class="steps-list">{"".join(row_html(r) for r in past)}</ol>
        </details>"""

    nxt = next((r for r in live_rows if r["gate"]), None)
    hint = ""
    if nxt:
        who = (nxt["gate"].get("who") or "").strip()
        whose = (
            "yours"
            if who.lower() in {"you", "rei", "rei samuelsson"}
            else f"with {who}"
            if who
            else ""
        )
        hint = f"Next: {nxt['gate'].get('what', '')}" + (f", {whose}" if whose else "")
        if len(hint) > 78:
            hint = hint[:77].rsplit(" ", 1)[0] + "…"
    mine_n = sum(
        1
        for i in items
        if state_of(i)["state"] == "todo" and not blocked_on(i, index or {})
    )
    count = f"{done} of {total} done" if total else ""
    if mine_n:
        count = (count + ", " if count else "") + f"{mine_n} with you"
    return section(
        "The path to closing this",
        f'<div class="path">{body}</div>',
        role="now",
        count=count,
        hint=hint,
    )


