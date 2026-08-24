#!/usr/bin/env python3
"""Render the board into one self-contained HTML file with two views.

The desk view answers "what do I do", grouped by ticket because that is how the
work gets done. The standup view answers "what do I say at 10:30", in the order
the meeting walks the board. Same tickets, same file, one source of truth, and
switching between them costs a keystroke.

Usage:
    python3 render_desk.py state/board.json output/desk.html
    python3 render_desk.py --error "message" output/desk.html
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import render_standup
from render import (
    CSS,
    JS,
    esc,
    furi,
    item_state as state_of,
    link_btn,
    next_live,
    pill,
    plain,
    script_meta,
    script_session,
    sessions,
    tracked,
    short_when,
    when_words,
)

EXTRA_CSS = """
.panel{background:var(--card);border:1px solid var(--line);border-radius:13px}
.tk .sub:last-of-type{border-bottom:0;padding-bottom:0}
.tk{padding:20px 22px;margin-bottom:18px;scroll-margin-top:78px}
.tk-head{padding-bottom:14px;border-bottom:1px solid var(--hair)}
.tk-head h2{margin:0;font-size:17.5px;letter-spacing:-.015em;line-height:1.35;
font-weight:650}
.tk-ja{margin:4px 0 0;font-size:14px;color:var(--mut)}
.tk-meta{margin:10px 0 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap;
font-size:12px;color:var(--soft)}
.tk-int{margin:9px 0 0;font-size:12px;color:var(--soft)}
.tk-int b{color:var(--amber);font-weight:700}
.tk-chip{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:6px;
background:var(--hair);color:var(--mut);border:1px solid var(--line)}
.tk-chip.warn{background:var(--red-bg);color:var(--red);border-color:var(--red-line)}

/* One list, in the order the work sits: yours, blocked, theirs, finished. */
.track{overflow:hidden;margin-bottom:8px}
.track-head{display:flex;gap:12px;align-items:baseline;padding:13px 18px 11px;
border-bottom:1px solid var(--line)}
.track-head h2{margin:0;font-size:14px;letter-spacing:-.01em;font-weight:650}
.track-head span{font-size:12.5px;color:var(--soft);margin-left:auto;
font-variant-numeric:tabular-nums}
.track-closed>summary{cursor:pointer;padding:10px 18px;font-size:12px;
font-weight:650;color:var(--soft);border-top:1px solid var(--line);
background:var(--hair)}
.tr{display:flex;gap:11px;padding:10px 18px;border-bottom:1px solid var(--hair);
align-items:center;border-left:3px solid transparent}
.tr:last-child{border-bottom:0}
.tr.mine{border-left-color:var(--red);background:linear-gradient(90deg,
var(--red-bg),rgba(255,255,255,0) 42%)}
.tr.blocked{border-left-color:#e2a03f}
.tr.theirs{border-left-color:#8fbcf7}
.tr-rank{flex:none;width:21px;font-size:12px;font-weight:700;color:var(--soft);
font-variant-numeric:tabular-nums}
.tr-tag{flex:none;font-size:12px;font-weight:700;padding:2px 8px;border-radius:6px;
background:var(--hair);color:var(--mut)}
.tr-title{flex:1;min-width:0;font-size:14.5px;font-weight:550;color:inherit;
text-decoration:none}
.tr-title:hover{color:var(--accent)}
.tr-note{display:block;font-size:12px;color:var(--soft);font-weight:400;margin-top:1px}
.tr-min{flex:none;font-size:12px;color:var(--soft);font-variant-numeric:tabular-nums;
width:44px;text-align:right}
.tr.shut .tr-title{text-decoration:line-through;text-decoration-color:#a6afbe}
.tr.shut{opacity:.62}

/* One chronological thread per ticket. */
.evs-earlier{margin:0 0 12px}
.evs-earlier>summary{cursor:pointer;font-size:12px;font-weight:650;
color:var(--soft);padding:6px 0}
.evs-earlier .evs{margin-top:8px}
.evs{list-style:none;margin:0;padding:0;position:relative}
.evs:before{content:"";position:absolute;left:41px;top:6px;bottom:10px;width:2px;
background:var(--line)}
.ev{display:flex;gap:15px;padding:0 0 14px;position:relative}
.ev:last-child{padding-bottom:0}
.ev-at{flex:none;width:34px;text-align:right;font-size:12px;font-weight:700;
color:var(--soft);font-variant-numeric:tabular-nums;padding-top:2px}
.ev-body{flex:1;min-width:0;padding-left:18px;position:relative}
.ev-body:before{content:"";position:absolute;left:-5px;top:6px;width:10px;
height:10px;border-radius:50%;background:#fff;border:2px solid var(--accent)}
.ev-who{display:block;font-size:11.5px;font-weight:700;color:var(--accent);
text-transform:uppercase;letter-spacing:.05em}
.ev-what{display:block;font-size:14.5px;margin-top:2px}
.ev-so{display:block;margin-top:6px;padding:8px 12px;background:var(--accent-bg);
border:1px solid var(--accent-line);border-radius:8px;font-size:13.5px;
color:var(--accent-ink);font-weight:550}
.ev-src{display:block;font-size:11.5px;color:var(--soft);margin-top:6px}

/* Threads and shorthand. */
.thr{list-style:none;margin:0;padding:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.thr li{background:#fff;padding:10px 13px;display:flex;gap:12px;
align-items:baseline;flex-wrap:wrap}
.thr-where{flex:none;font-size:11.5px;font-weight:700;color:var(--accent);
min-width:185px}
.thr-body{flex:1;min-width:220px}
.thr-label{font-weight:600;font-size:14px}
.thr-gist{font-size:13px;color:var(--mut);margin-top:2px}
.thr-when{flex:none;font-size:11.5px;color:var(--soft);text-align:right;
font-variant-numeric:tabular-nums}
.thr-when b{display:block;color:var(--mut);font-weight:600}
.terms{margin:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.term{background:#fbfcfe;padding:10px 13px;display:flex;gap:14px;
align-items:baseline;flex-wrap:wrap}
.terms dt{flex:none;min-width:145px;font-weight:700;font-size:13.5px;
color:var(--accent-ink)}
.terms dd{flex:1;min-width:240px;margin:0;font-size:13.5px;color:var(--mut)}

/* An item, and the colour of its left edge is where it sits. */
.act{border:1px solid var(--line);border-left:3px solid var(--line);
border-radius:11px;margin-bottom:12px;overflow:hidden;background:#fff}
.act.todo{border-left-color:var(--red)}
.act.hold,.act.held{border-left-color:#e2a03f;background:#fffdf6}
.act.held .act-head{background:var(--amber-bg)}
.act.waiting{border-left-color:#8fbcf7}
.act-head{display:flex;gap:10px;padding:11px 14px;align-items:center;
flex-wrap:wrap;background:#fbfcfe;border-bottom:1px solid var(--hair)}
.act-rank{width:23px;height:23px;flex:none;border-radius:6px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:11.5px;font-weight:700}
.act-title{flex:1;min-width:0;font-weight:600;font-size:15px}
.act-sub{display:block;font-size:12px;font-weight:400;color:var(--soft);margin-top:2px}
details.act>summary{cursor:pointer;list-style:none}
details.act>summary::-webkit-details-marker{display:none}
details.act>summary::before{display:none}
details.act:not([open])>summary{border-bottom:0}
details.act .act-title{font-weight:550}
details.act.waiting{background:#fcfdff}
details.act.done,details.act.sent,details.act.dropped{opacity:.7;
border-left-color:#ccd4e0}
details.act.done .act-title,details.act.sent .act-title{text-decoration:line-through;
text-decoration-color:#a6afbe}
.act-min{color:var(--soft);font-size:12px;font-variant-numeric:tabular-nums}
.act-body{padding:13px 15px}
.act-why{margin:0 0 10px;font-size:14.5px;color:var(--ink)}
.act-why b{display:inline-block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.08em;color:var(--soft);margin-right:8px;font-weight:700;
vertical-align:1px}
.act-body ul{margin:0;padding-left:18px}
.act-body li{margin-bottom:4px;font-size:14px;color:var(--mut)}
.act-where{margin:11px 0 0;display:flex;gap:9px;align-items:center;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.act-commit{margin:11px 0 0;padding:8px 12px;background:var(--red-bg);
border:1px solid var(--red-line);border-radius:8px;font-size:13px;color:var(--red);
font-weight:550}
.act-block{margin:11px 0 0;padding:8px 12px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
color:var(--amber-ink)}
.act-quote{margin:11px 0 0;padding-left:12px;border-left:3px solid var(--line);
font-size:12.5px;color:var(--soft);font-style:italic}
.act-draft{margin:12px 0 0;border:1px solid var(--line);border-radius:9px;
overflow:hidden}
.act-draft.sent{background:#fbfcfe}
.act-draft.sent>summary{padding:9px 13px;cursor:pointer;font-size:11.5px;
font-weight:700;color:var(--soft);text-transform:uppercase;letter-spacing:.06em}
.act-draft.sent[open]>summary{border-bottom:1px solid var(--line)}
.sent-note{margin:0 0 10px;padding:8px 12px;background:var(--blue-bg);
border:1px solid var(--blue-line);border-radius:8px;font-size:13px;color:var(--blue)}
.sent-note b{display:inline-block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.07em;margin-right:8px}
.closed{margin:0 0 10px;font-size:13.5px;color:var(--green)}
.closed b{display:inline-block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.06em;margin-right:8px}
.hold{margin:0 0 11px;padding:10px 13px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
color:var(--amber-ink)}
.hold b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--amber);margin-bottom:3px}
.hold-until{color:#7a2e0e;font-weight:600}
.holds{background:var(--amber-bg);border:1px solid var(--amber-line);
border-left:4px solid var(--amber);border-radius:13px;padding:14px 19px;
margin-bottom:20px}
.holds h2{margin:0 0 8px;font-size:11.5px;text-transform:uppercase;
letter-spacing:.09em;color:var(--amber);font-weight:700}
.holds ul{margin:0;padding-left:18px}
.holds li{font-size:14px;color:var(--amber-ink);margin-bottom:4px}
.dec{background:var(--amber-bg);border:1px solid var(--amber-line);
border-radius:10px;padding:12px 15px;margin-bottom:10px}
.dec-q{font-weight:600;font-size:14.5px;color:var(--amber-ink)}
.dec ul{margin:7px 0 0;padding-left:18px;font-size:13.5px;color:var(--mut)}
.dec-owner{margin:8px 0 0;font-size:12.5px;color:var(--amber);font-weight:600}
.watch-list{margin:0;padding-left:18px}
.watch-list li{margin-bottom:5px;font-size:14px;color:var(--mut)}

/* Header actions. The one that matters in this view is the bright one. */
.refresh{border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);
color:#dce6f5;font:650 12px/1 inherit;padding:0 12px;border-radius:7px;
cursor:pointer}
.refresh:hover{background:rgba(255,255,255,.16);color:#fff}
body[data-view="desk"] #refresh,body[data-view="standup"] #prep{
background:#2f6fe4;border-color:#5b93f0;color:#fff}
body[data-view="desk"] #refresh:hover,body[data-view="standup"] #prep:hover{
background:#4881ec}
body[data-view="standup"] #prep{background:#b32a9c;border-color:#cf56b9}
body[data-view="standup"] #prep:hover{background:#c33bab}
.refresh:disabled{opacity:.5;cursor:default}
a.refresh{text-decoration:none}
.refresh-note{font-size:11.5px;color:#93a4bd;max-width:280px}
.refresh-note.bad{color:#f6b0ac}
"""


def anchor(ref: str) -> str:
    """A stable URL-safe id for a mostly-Japanese tag."""
    ascii_part = re.sub(r"[^0-9A-Za-z]+", "", ref)
    digest = hashlib.md5(ref.encode("utf-8")).hexdigest()[:6]
    return f"t-{ascii_part}{digest}" if ascii_part else f"t-{digest}"


def sub_line(st: dict) -> str:
    """The one line under a title saying what has already happened to it."""
    bits = []
    if st["state"] == "waiting":
        who = st.get("who", "them")
        since = st.get("at", "")
        bits.append(
            f"sent {since}, with {who}" if st.get("sent") else f"with {who} since {since}"
        )
    elif st["closed"]:
        bits.append(f"{st['label'].lower()} {st.get('at', '')}")
    if st.get("note"):
        bits.append(st["note"])
    return " &middot; ".join(esc(b) for b in bits)


GROUPS = {"todo": "mine", "hold": "blocked", "waiting": "theirs"}


def track_row(ref: str, item: dict, st: dict, refs: dict[str, str]) -> str:
    mins = item.get("est_minutes")
    sub = sub_line(st)
    group = "shut" if st["closed"] else GROUPS.get(st["state"], "")
    return f"""
      <li class="tr {group}">
        <span class="tr-rank">{esc(item.get("id", "-"))}</span>
        <span class="tr-tag">{esc(ref)}</span>
        <a class="tr-title" href="#{esc(refs.get(ref, anchor(ref)))}">{esc(item.get("title"))}
          {f'<span class="tr-note">{sub}</span>' if sub else ""}</a>
        {pill(st["label"], st["tone"])}
        <span class="tr-min">{f"{esc(mins)} min" if mins and not st["closed"] else ""}</span>
      </li>"""


def render_track(tickets: list[dict], refs: dict[str, str]) -> str:
    """The one list Rei works from: what is his, what is not, what is finished."""
    rows = tracked(tickets)
    if not rows:
        return ('<div class="panel" style="padding:18px 22px"><p class="empty">'
                "Nothing open across any ticket. Enjoy it.</p></div>")

    counts = {"todo": 0, "hold": 0, "waiting": 0, "closed": 0}
    live, shut = [], []
    for ref, item, st in rows:
        counts["closed" if st["closed"] else st["state"]] += 1
        (shut if st["closed"] else live).append(track_row(ref, item, st, refs))

    summary = ", ".join(
        f"{n} {word}"
        for n, word in (
            (counts["todo"], "with you"),
            (counts["hold"], "not yet"),
            (counts["waiting"], "with someone else"),
            (counts["closed"], "finished"),
        )
        if n
    )
    # Finished work folds away by default. It is a record, not a list.
    closed_block = (
        f"""
    <details class="track-closed">
      <summary>{len(shut)} finished</summary>
      <ul style="list-style:none;margin:0;padding:0">{"".join(shut)}</ul>
    </details>"""
        if shut
        else ""
    )
    return f"""
  <div class="track">
    <div class="track-head"><h2>Where you are</h2><span>{esc(summary)}</span></div>
    <ul style="list-style:none;margin:0;padding:0">{"".join(live)}</ul>
    {closed_block}
  </div>"""


def render_terms(rows: list[dict]) -> str:
    if not rows:
        return ""
    items = "".join(
        f'<div class="term"><dt>{esc(r.get("term"))}</dt>'
        f'<dd>{esc(r.get("means"))} '
        f'{link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</dd></div>'
        for r in rows
    )
    return f"""
      <section class="sub">
        <h3>What the shorthand means</h3>
        <dl class="terms">{items}</dl>
      </section>"""


def render_threads(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        out.append(
            f"""
        <li>
          <span class="thr-where">{esc(r.get("where"))}</span>
          <span class="thr-body">
            <span class="thr-label">{esc(r.get("label"))}</span>
            <span class="thr-gist">{esc(r.get("gist"))}</span>
          </span>
          <span class="thr-when"><b>{esc(r.get("last_from"))}</b>{esc(r.get("last_at"))}</span>
          {link_btn(r.get("url", ""), "Open")}
        </li>"""
        )
    return f"""
      <section class="sub">
        <h3>Every conversation this lives in</h3>
        <ul class="thr">{"".join(out)}</ul>
      </section>"""


def event_li(r: dict, show_date: bool) -> str:
    src = r.get("source_url", "")
    when = f'{r.get("on", "")[5:]} {r.get("at", "")}' if show_date else r.get("at", "")
    return f"""
        <li class="ev">
          <span class="ev-at">{esc(when)}</span>
          <span class="ev-body">
            <span class="ev-who">{esc(r.get("who", ""))}</span>
            <span class="ev-what">{esc(r.get("what"))}</span>
            {f'<span class="ev-so">{esc(r.get("so_what"))}</span>' if r.get("so_what") else ""}
            <span class="ev-src">{esc(r.get("where", ""))} {link_btn(src, "Source") if src else ""}</span>
          </span>
        </li>"""


def render_events(rows: list[dict]) -> str:
    """One chronological thread per ticket. Today open, earlier folded."""
    if not rows:
        return ""
    today = date.today().isoformat()
    ordered = sorted(rows, key=lambda x: (x.get("on", ""), x.get("at", "")))
    now = [r for r in ordered if r.get("on") == today]
    before = [r for r in ordered if r.get("on") != today]

    earlier = ""
    if before:
        earlier = f"""
        <details class="evs-earlier">
          <summary>{len(before)} earlier {"move" if len(before) == 1 else "moves"}</summary>
          <ol class="evs">{"".join(event_li(r, True) for r in before)}</ol>
        </details>"""
    heading = "Today, in order" if now else "How this got here"
    body = (
        f'<ol class="evs">{"".join(event_li(r, False) for r in now)}</ol>'
        if now
        else '<p class="empty">Nothing moved today.</p>'
    )
    return f"""
      <section class="sub">
        <h3>{heading}</h3>
        {earlier}
        {body}
      </section>"""


def render_draft(d: dict, st: dict | None = None) -> str:
    """A draft to paste, or, once it has gone, a folded record of what went."""
    if not d:
        return ""
    body = d.get("body_ruby", "")
    is_ja = d.get("language") == "ja"
    rendered = furi(body) if is_ja else esc(body)
    trans = (
        f'<p class="draft-en">{esc(d.get("body_en"))}</p>'
        if is_ja and d.get("body_en")
        else ""
    )
    inner = f"""
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go there")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
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


def render_items(rows: list[dict], raise_label: str = "Raise at standup") -> str:
    if not rows:
        return """
      <section class="sub">
        <h3>Items</h3>
        <p class="empty">Nothing on this one needs you. It is here because it is
        still open in Asana.</p>
      </section>"""
    out = []
    for r in sorted(rows, key=lambda x: (state_of(x)["order"], x.get("id", 99))):
        detail = "".join(f"<li>{esc(b)}</li>" for b in r.get("detail", []))
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
                f" Chase on {esc(waits['chase_on'])}." if waits.get("chase_on") else ""
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
            <span class="hold-until">Wait for: {esc(hold.get("until"))}</span>
            {f'<span class="hold-until"> Chase on {esc(revisit)}.</span>' if revisit else ""}</p>"""
        state_pill = pill(st["label"], st["tone"])
        if r.get("at_standup") and not done:
            state_pill += pill(raise_label, "amber")
        chase = (r.get("waits_on") or {}).get("chase_on", "")
        # Anything not sitting with Rei folds shut, so the page is only as long
        # as the work he still has.
        active = st["state"] in {"todo", "hold"}
        tag, attrs = ("div", "") if active else ("details", "")
        head_tag = "div" if active else "summary"
        sub = sub_line(st) or (f"chase {esc(chase)}" if chase else "")
        out.append(
            f"""
        <{tag} class="act {st["state"]} {"held" if hold and not done else ""} {"commit" if committed else ""}"{attrs}>
          <{head_tag} class="act-head">
            <span class="act-rank">{esc(r.get("id", "-"))}</span>
            <span class="act-title">{esc(r.get("title"))}
              {f'<span class="act-sub">{sub}</span>' if sub and not active else ""}</span>
            {state_pill}
            <span class="act-min">{f"{esc(mins)} min" if mins and active else ""}</span>
          </{head_tag}>
          <div class="act-body">
            {f'<p class="act-why"><b>Why</b>{esc(r.get("why"))}</p>' if r.get("why") else ""}
            {status_block}
            {f'<p class="act-quote">Already happened: {esc(r.get("progress_note"))}</p>' if r.get("progress_note") else ""}
            {f"<ul>{detail}</ul>" if detail else ""}
            {f'<p class="act-commit">You committed this to {esc(committed)}</p>' if committed else ""}
            {f'<p class="act-block">Blocked by: {esc(blocked)}</p>' if blocked else ""}
            <div class="act-where">
              <span>{esc(r.get("where"))}</span>
              {link_btn(r.get("link", ""), "Act here")}
            </div>
            {f'<p class="act-quote">{esc(quote)} {link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</p>' if quote else ""}
            {render_draft(r.get("draft") or {}, st)}
          </div>
        </{tag}>"""
        )
    return f"""
      <section class="sub">
        <h3>Items, and where each one sits</h3>
        {"".join(out)}
      </section>"""


def render_decisions(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        opts = "".join(f"<li>{esc(o)}</li>" for o in r.get("options", []))
        out.append(
            f"""
        <div class="dec">
          <div class="dec-q">{esc(r.get("question"))}</div>
          {f"<ul>{opts}</ul>" if opts else ""}
          <p class="dec-owner">Decided by: {esc(r.get("owner"))}
          {link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</p>
        </div>"""
        )
    return f"""
      <section class="sub">
        <h3>Still undecided</h3>
        {"".join(out)}
      </section>"""


def asana_chips(t: dict) -> str:
    """What Asana itself says about this ticket, not what the agent thinks."""
    a = t.get("asana") or {}
    bits = []
    if a.get("status"):
        bits.append(pill(a["status"], "blue"))
    for key, prefix in (("section", ""), ("priority", "Priority "), ("category", "")):
        if a.get(key):
            bits.append(f'<span class="tk-chip">{esc(prefix)}{esc(a[key])}</span>')
    if a.get("assignee") and "Rei" not in a["assignee"]:
        bits.append(f'<span class="tk-chip warn">Assigned to {esc(a["assignee"])}</span>')
    return "".join(bits)


def render_ticket(t: dict, ident: str, raise_label: str = "Raise at standup") -> str:
    internal = t.get("internal_ticket") or {}
    int_block = ""
    if internal.get("name"):
        int_block = (
            f'<p class="tk-int"><b>Internal, never to TG:</b> '
            f'{esc(internal.get("name"))} {link_btn(internal.get("url", ""), "Open")}</p>'
        )

    states = [state_of(i) for i in t.get("items", [])]
    mine = sum(1 for s in states if s["state"] == "todo")
    open_n = sum(1 for s in states if not s["closed"])
    if mine:
        posture = pill(f"{mine} with you", "red")
    elif open_n:
        posture = pill("Nothing on you", "blue")
    else:
        posture = pill("Clear", "green")

    # When there is a script for this ticket, the desk card says so and jumps
    # straight to it, because "what do I say about this" is the next question.
    say_link = (
        f'<a class="btn" href="#{esc(render_standup.anchor(ident))}" '
        f'data-goto="standup">What I say</a>'
        if (t.get("prep") or {}).get("script")
        else ""
    )

    return f"""
    <article class="tk" id="{esc(ident)}">
      <header class="tk-head">
        <h2><span class="tag">{esc(t.get("ref"))}</span> {esc(t.get("title_en"))}</h2>
        <p class="tk-ja">{esc(t.get("title_ja"))}</p>
        <p class="tk-meta">
          {posture}
          {asana_chips(t)}
          {link_btn(t.get("asana_url", ""), "Asana ticket")}
          {say_link}
        </p>
        {int_block}
      </header>

      {render_terms(t.get("terms", []))}

      <section class="sub">
        <h3>Where it stands</h3>
        <p class="status">{esc(t.get("where_it_stands"))}</p>
      </section>

      {render_events(t.get("events", []))}
      {render_items(t.get("items", []), raise_label)}
      {render_decisions(t.get("open_decisions", []))}
      {render_threads(t.get("threads", []))}
    </article>"""


def shell(
    title: str,
    body: str,
    view: str = "desk",
    meeting_iso: str = "",
    meeting_label: str = "",
) -> str:
    # The manifest and icon are what let Chrome install this as its own app, with
    # its own Dock tile. They 404 harmlessly when the page is opened from disk.
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">
<link rel="apple-touch-icon" href="/icon-512.png">
<meta name="theme-color" content="#0d1524">
<title>{esc(title)}</title>
<style>{CSS}{EXTRA_CSS}{render_standup.EXTRA_CSS}</style></head>
<body data-view="{esc(view)}" data-meeting="{esc(meeting_iso)}"
      data-meeting-label="{esc(meeting_label)}">
{body}
<script>{JS}</script></body></html>"""


# The buttons only appear when serve.py is behind the page, because a file://
# page has nothing to send the click to. serve.py swaps the key in as it serves.
def controls(prep_label: str) -> str:
    return """
  <button id="refresh" class="refresh" hidden data-run="/api/refresh"
          data-busy="Refreshing">Refresh</button>
  <button id="prep" class="refresh" hidden data-run="/api/prep"
          data-busy="Writing">%s</button>
  <button id="login" class="refresh" hidden>Log in</button>
  <a id="login-link" class="refresh" hidden target="_blank" rel="noopener">Open sign-in page</a>
  <span id="refresh-note" class="refresh-note"></span>
<script>
(function () {
  var key = "__DESK_KEY__";
  if (location.protocol !== "http:" || key.indexOf("DESK_KEY") > -1) return;
  var runners = [].slice.call(document.querySelectorAll("[data-run]"));
  var login = document.getElementById("login");
  var link = document.getElementById("login-link");
  var note = document.getElementById("refresh-note");
  runners.forEach(function (b) { b.hidden = false; });

  function say(text, tone) {
    note.textContent = text || "";
    note.className = "refresh-note" + (tone ? " " + tone : "");
  }

  function ready() {
    runners.forEach(function (b) {
      b.disabled = false;
      b.textContent = b.dataset.label || b.textContent;
    });
  }

  function poll() {
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {
      if (s.state === "running") { say(s.message + "\\u2026"); setTimeout(poll, 2000); return; }
      if (s.state === "done") { say("Done, reloading"); location.reload(); return; }
      // Signed out is not a failure, it is one click. Offer the click, and the
      // link the CLI printed once it has one. Keep polling so the moment the
      // browser approval lands the buttons come back on their own.
      if (s.state === "needs_login") {
        ready();
        login.hidden = false;
        if (s.url) { link.href = s.url; link.hidden = false; }
        say(s.message, "bad");
        setTimeout(poll, 3000);
        return;
      }
      if (s.state === "failed") { ready(); say(s.message, "bad"); return; }
      login.hidden = true;
      link.hidden = true;
      ready();
      say(s.message);
    });
  }

  runners.forEach(function (b) {
    b.dataset.label = b.textContent;
    b.addEventListener("click", function () {
      runners.forEach(function (o) { o.disabled = true; });
      b.textContent = b.dataset.busy;
      say("Starting\\u2026");
      fetch(b.dataset.run + "?k=" + encodeURIComponent(key), { method: "POST" })
        .then(poll)
        .catch(function () { ready(); say("could not reach the desk server", "bad"); });
    });
  });

  login.addEventListener("click", function () {
    login.disabled = true;
    say("Starting the sign-in\\u2026");
    fetch("/api/login?k=" + encodeURIComponent(key), { method: "POST" })
      .then(function () { setTimeout(function () { login.disabled = false; poll(); }, 1500); })
      .catch(function () { login.disabled = false; say("could not reach the desk server", "bad"); });
  });

  poll();
})();
</script>""" % prep_label


def checked_line(stamp: str) -> str:
    """How long ago the board was last brought up to date, in plain words.

    Short, because it shares the header with the tabs and the buttons, and a
    wrapped header pushes the page around every time it changes.
    """
    if not stamp:
        return "never checked"
    try:
        then = datetime.fromisoformat(stamp)
    except ValueError:
        return esc(stamp)
    mins = int((datetime.now().astimezone() - then).total_seconds() // 60)
    if mins < 2:
        return "checked just now"
    if mins < 60:
        return f"checked {mins}m ago"
    if mins < 24 * 60:
        return f"checked {mins // 60}h ago"
    return f"checked {then:%-d %b}"


def is_stale(stamp: str) -> bool:
    """Four hours is long enough for a reply to have landed unseen."""
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return True
    return (datetime.now().astimezone() - then).total_seconds() > 4 * 3600


def view_tabs(mine: int, has_script: bool, sess: dict) -> str:
    """Two tabs. "My work" and "What I say" name what you get, which "Desk" and
    "Standup" did not, and the second one carries the room it is written for.

    All on one line: the header sits above everything he reads all day, so it
    stays as short as it can while still being the most obvious thing up there.
    """
    badge = (
        f'<span class="badge">{mine}</span>'
        if mine
        else '<span class="badge quiet">0</span>'
    )
    when = short_when(sess.get("date", ""), sess.get("at", ""))
    room = f'{sess.get("name", "Standup")} {when}'.strip()
    alert = "" if has_script else '<span class="badge">!</span>'
    return f"""
  <div class="views" role="tablist" aria-label="Views">
    <button data-view="desk" role="tab" aria-selected="true">
      <span class="k">1</span><span class="lbl">My work</span>{badge}
    </button>
    <button data-view="standup" role="tab" aria-selected="false">
      <span class="k">2</span><span class="lbl">What I say</span>
      <span class="sub">{esc(room)}</span>{alert}
    </button>
  </div>"""


def opening_view(board: dict, has_script: bool) -> str:
    """What to show on load.

    On the morning of a session, with a script already written, the script is
    what he opens the laptop for. Every other moment of the day, the work is.
    """
    if not has_script:
        return "desk"
    sess = script_session(board)
    if sess.get("date") != date.today().isoformat():
        return "desk"
    at = sess.get("at") or "10:30"
    try:
        hour, minute = (int(x) for x in at.split(":")[:2])
    except ValueError:
        hour, minute = 10, 30
    now = datetime.now()
    return "standup" if (now.hour, now.minute) < (hour, minute) else "desk"


def next_up(board: dict, has_script: bool) -> str:
    """A line on the desk about the next room, and whether it has a script.

    Also where a skipped standup gets said out loud, because "no standup
    Wednesday" changes what has to move into Asana instead.
    """
    rows = sessions(board)
    if not rows:
        return ""
    live = next((s for s in rows if not s.get("skipped")), {})
    skipped = [s for s in rows if s.get("skipped")]
    if not live and not skipped:
        return ""

    off = ""
    if skipped:
        s = skipped[0]
        off = (
            f'<p class="sess-focus"><strong>No {esc(s.get("name", "standup")).lower()} '
            f'{esc(when_words(s.get("date", "")))}.</strong> {esc(s.get("reason"))} '
            "Anything that was waiting for that meeting has to move into Asana.</p>"
        )
    if not live:
        return f'<section class="sess">{off}</section>'

    # A script for Thursday is not a script for Wednesday's onsite, and saying
    # "read the script" when it describes a different room is how you walk into
    # the wrong one.
    covered = has_script and script_meta(board).get("for_date") == live.get("date")
    if covered:
        script_note = '<a class="btn" href="#top" data-goto="standup">Read the script</a>'
    elif has_script:
        for_day = when_words(script_meta(board).get("for_date", ""))
        script_note = (
            f'<span class="tk-chip warn">Script is for {esc(for_day)}, '
            f"not this</span>"
        )
    else:
        script_note = '<span class="tk-chip warn">No script yet</span>'
    return f"""
  <section class="sess">
    <div class="sess-top">
      <span class="sess-kind">Next up</span>
      <h2>{esc(live.get("title") or live.get("name"))}</h2>
      <span class="sess-when">{esc(when_words(live.get("date", ""), live.get("at", "")))}</span>
      {f'<span class="sess-where">{esc(live.get("place"))}</span>' if live.get("place") else ""}
      {script_note}
    </div>
    {f'<p class="sess-focus">{esc(live.get("focus"))}</p>' if live.get("focus") else ""}
    {off}
  </section>"""


def render(data: dict) -> str:
    pretty = date.today().strftime("%a %-d %b")

    # Tickets you owe something on come first. Everything open stays on the page.
    def ticket_order(t: dict) -> tuple:
        states = [state_of(i) for i in t.get("items", [])]
        return (
            0 if any(s["state"] == "todo" for s in states) else
            1 if any(not s["closed"] for s in states) else 2,
            min((i.get("id", 99) for i in t.get("items", [])), default=99),
        )

    tickets = sorted(data.get("tickets", []), key=ticket_order)
    refs = {t.get("ref", ""): anchor(t.get("ref", "")) for t in tickets}
    # "Raise at the onsite" and "Raise at standup" are different instructions,
    # so the pill says which room it means.
    raise_label = f'Raise at {next_live(data).get("name", "standup").lower()}'
    cards = "".join(
        render_ticket(t, refs[t.get("ref", "")], raise_label) for t in tickets
    )

    total = sum(
        i.get("est_minutes") or 0
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo"
    )

    held = [
        (t.get("ref", ""), i)
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "hold"
    ]
    hold_block = ""
    if held:
        rows = []
        for ref, act in held:
            h = act.get("hold") or {}
            chase = f" Chase on {esc(h.get('revisit'))}." if h.get("revisit") else ""
            rows.append(
                f"<li><strong>{esc(ref)}</strong>: {esc(act.get('title'))}. "
                f"Wait for {esc(h.get('until'))}.{chase}</li>"
            )
        items = "".join(rows)
        hold_block = f"""
  <div class="holds">
    <h2>Wait before you send, {len(held)} thing{"s" if len(held) != 1 else ""}</h2>
    <ul>{items}</ul>
  </div>"""

    watch = data.get("watch", [])
    watch_block = ""
    if watch:
        items = "".join(
            f'<li><strong>{esc(w.get("topic"))}</strong> &mdash; {esc(w.get("why"))} '
            f'{link_btn(w.get("source_url", ""), "Source")}</li>'
            for w in watch
        )
        watch_block = (
            f'<details class="gaps"><summary><h2>Not mine, but adjacent '
            f'({len(watch)})</h2></summary><ul class="watch-list">{items}</ul></details>'
        )

    gaps = data.get("gaps", [])
    gap_block = ""
    if gaps:
        items = "".join(f"<li>{esc(g)}</li>" for g in gaps)
        gap_block = f'<section class="gaps"><h2>Open gaps</h2><ul>{items}</ul></section>'

    mine = sum(
        1
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo"
    )

    meta = script_meta(data)
    built = meta.get("built_at", "")
    has_script = any((t.get("prep") or {}).get("script") for t in tickets)
    # A script written before the last sweep may not know the newest replies.
    stale = bool(has_script and built and built < (data.get("checked_at") or ""))
    prep_label = "Rebuild script" if has_script else "Build script"

    # The countdown only makes sense on the day of a session, and an empty value
    # is what tells the page not to draw one at all.
    today_iso = date.today().isoformat()
    soon = next_live(data)
    on_today = soon.get("date") == today_iso and soon.get("at")
    meeting = f'{today_iso}T{soon.get("at")}:00+09:00' if on_today else ""
    meeting_label = soon.get("name", "standup").lower() if on_today else ""

    body = f"""
<header class="top"><div class="top-in">
  <span class="brand"><img src="/icon-192.png" alt="" onerror="this.remove()">
  <h1>Billing desk</h1></span>
  {view_tabs(mine, has_script, script_session(data))}
  <span class="acts">
    <span class="date {"old" if is_stale(data.get("checked_at", "")) else ""}">
      {esc(pretty)} &middot; {esc(checked_line(data.get("checked_at", "")))}</span>
    <span id="countdown"></span>
    {link_btn((data.get("meeting_note") or {}).get("url", ""), "Meeting note")}
    <button class="toggle" id="scriptonly">Script only</button>
    {controls(prep_label)}
  </span>
</div></header>
<div class="wrap" id="top">
  <div id="view-desk" role="tabpanel">
    {f'<div class="headline"><p>{esc(data.get("headline"))}</p></div>' if data.get("headline") else ""}
    {next_up(data, has_script)}
    {render_track(tickets, refs)}
    <p class="foot" style="margin:0 0 22px">
    {f"About {total} min of work sits with you. " if total else ""}
    Close something by telling the chat, or with <code>tg &lt;number&gt;</code>.</p>
    {hold_block}
    <h2 class="tickets-h">{len(tickets)} open ticket{"s" if len(tickets) != 1 else ""}, everything for each one in one place</h2>
    {cards}
    {watch_block}
    {gap_block}
  </div>
  <div id="view-standup" role="tabpanel">
    {render_standup.render(data, refs, built, stale)}
  </div>
</div>"""
    return shell(
        "Billing desk", body, opening_view(data, has_script), meeting, meeting_label
    )


def render_error(message: str) -> str:
    body = f"""
<div class="wrap" style="padding-top:40px">
  <div class="err">
    <h1 style="margin:0 0 8px;font-size:20px">The desk did not build</h1>
    <p style="margin:0">The board is still there. Rebuild with
    <code>tg open</code>, or run <code>./run_post.sh --force</code> to start
    again from the meeting note. Details below.</p>
    <pre>{esc(message)}</pre>
  </div>
</div>"""
    return shell("Billing desk, build failed", body)


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--error":
        Path(args[2]).write_text(render_error(args[1]), encoding="utf-8")
        return 0
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
    if not isinstance(data, dict) or "tickets" not in data:
        print(f"{src} is missing the 'tickets' key", file=sys.stderr)
        return 1

    dest.write_text(render(data), encoding="utf-8")
    items = sum(len(t.get("items", [])) for t in data.get("tickets", []))
    print(f"wrote {dest} ({len(data['tickets'])} tickets, {items} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
