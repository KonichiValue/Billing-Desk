#!/usr/bin/env python3
"""Render the post-standup JSON into a single self-contained HTML page.

Everything is grouped by ticket, because that is how the work gets done. The
only cross-ticket structure is the running order at the top.

Usage:
    python3 render_post.py output/post-2026-08-24.json output/post-2026-08-24.html
    python3 render_post.py --error "message" output/post-2026-08-24.html
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from render import (
    CSS,
    JS,
    action_state,
    esc,
    furi,
    link_btn,
    load_progress,
    pill,
    plain,
    tracked,
)

PROGRESS: dict = {}


def state_of(action: dict) -> dict:
    return action_state(PROGRESS, action)

EXTRA_CSS = """
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px}
.tk .sub:last-of-type{border-bottom:0;padding-bottom:0}
.index{list-style:none;margin:0;padding:0;background:var(--card);
border:1px solid var(--line);border-radius:12px;overflow:hidden}
.ix{display:flex;gap:13px;padding:13px 16px;border-bottom:1px solid var(--line);
align-items:center;text-decoration:none;color:inherit}
.ix:last-child{border-bottom:0}
.ix:hover{background:var(--accent-bg)}
.ix-rank{width:25px;height:25px;flex:none;border-radius:7px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:12.5px;font-weight:650}
.ix-tag{flex:none;font-size:13px;font-weight:650;padding:2px 9px;border-radius:6px;
background:#f2f4f7;color:var(--mut)}
.ix-act{flex:1;min-width:0;font-weight:550}
.ix-min{flex:none;color:var(--soft);font-size:13px;font-variant-numeric:tabular-nums}
.tk{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:22px;margin-bottom:22px;scroll-margin-top:80px}
.tk-head{padding-bottom:15px;border-bottom:1px solid var(--line)}
.tk-head h2{margin:0;font-size:19px;letter-spacing:-.015em;line-height:1.35}
.tk-ja{margin:5px 0 0;font-size:15px;color:var(--mut)}
.tk-meta{margin:10px 0 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.tk-int{margin:9px 0 0;font-size:12.5px;color:var(--soft)}
.tk-int b{color:#b54708;font-weight:650}
.silent{color:#b54708;font-weight:600}
.thr{list-style:none;margin:0;padding:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.thr li{background:#fff;padding:10px 13px;display:flex;gap:12px;
align-items:baseline;flex-wrap:wrap}
.thr-where{flex:none;font-size:12px;font-weight:650;color:var(--accent);
min-width:190px}
.thr-body{flex:1;min-width:220px}
.thr-label{font-weight:600;font-size:14px}
.thr-gist{font-size:13.5px;color:var(--mut);margin-top:2px}
.thr-when{flex:none;font-size:12px;color:var(--soft);text-align:right;
font-variant-numeric:tabular-nums}
.thr-when b{display:block;color:var(--mut);font-weight:600}
.terms{margin:0;display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
border-radius:10px;overflow:hidden}
.term{background:#fcfcfd;padding:10px 13px;display:flex;gap:14px;align-items:baseline;
flex-wrap:wrap}
.terms dt{flex:none;min-width:150px;font-weight:650;font-size:14px;color:var(--accent)}
.terms dd{flex:1;min-width:240px;margin:0;font-size:14px;color:var(--mut)}
.track{background:var(--card);border:1px solid var(--line);border-radius:12px;
overflow:hidden;margin-bottom:8px}
.track-head{display:flex;gap:12px;align-items:baseline;padding:14px 18px 12px;
border-bottom:1px solid var(--line)}
.track-head h2{margin:0;font-size:15px;letter-spacing:-.01em}
.track-head span{font-size:13px;color:var(--soft);margin-left:auto;
font-variant-numeric:tabular-nums}
.tr{display:flex;gap:12px;padding:11px 18px;border-bottom:1px solid var(--line);
align-items:center}
.tr:last-child{border-bottom:0}
.tr-box{flex:none;width:17px;height:17px;margin:0;accent-color:#067647;cursor:pointer}
.tr-rank{flex:none;width:23px;font-size:12.5px;font-weight:650;color:var(--soft);
font-variant-numeric:tabular-nums}
.tr-tag{flex:none;font-size:12.5px;font-weight:650;padding:2px 8px;border-radius:6px;
background:#f2f4f7;color:var(--mut)}
.tr-title{flex:1;min-width:0;font-size:14.5px;font-weight:550;color:inherit;
text-decoration:none}
.tr-title:hover{color:var(--accent)}
.tr-note{display:block;font-size:12.5px;color:var(--soft);font-weight:400;
margin-top:1px}
.tr-min{flex:none;font-size:12.5px;color:var(--soft);font-variant-numeric:tabular-nums;
width:46px;text-align:right}
.tr.shut .tr-title,.tr.ticked .tr-title{text-decoration:line-through;
text-decoration-color:#98a2b3}
.tr.shut,.tr.ticked{opacity:.6}
.track-sync{display:flex;gap:10px;align-items:center;padding:10px 18px;
background:#fffaeb;border-top:1px solid #fedf89;font-size:13px;color:#93370d}
.track-sync code{background:#fff;border:1px solid #fedf89;border-radius:6px;
padding:2px 7px;font-size:12.5px}
.act.done{opacity:.62}
.act.waiting{opacity:.85}
.sent-note{margin:0 0 11px;padding:8px 12px;background:#eff8ff;
border:1px solid #b2ddff;border-radius:8px;font-size:13.5px;color:#175cd3}
.sent-note b{display:inline-block;font-size:11px;text-transform:uppercase;
letter-spacing:.06em;margin-right:8px}
.act.done .act-title{text-decoration:line-through;text-decoration-color:#98a2b3}
.ix.done .ix-act{text-decoration:line-through;text-decoration-color:#98a2b3}
.ix.done{opacity:.6}
.closed{margin:0 0 11px;font-size:14px;color:#067647}
.closed b{display:inline-block;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;margin-right:8px}
.chg{border-left:3px solid #067647;padding:2px 0 2px 13px;margin-bottom:14px}
.chg-line{display:flex;gap:10px;font-size:14.5px;margin-bottom:5px}
.chg-line .k{flex:none;width:44px;font-size:11.5px;font-weight:650;
text-transform:uppercase;letter-spacing:.05em;padding-top:3px;color:var(--soft)}
.chg-line.was .v{color:var(--soft);text-decoration:line-through;
text-decoration-color:#d0d5dd}
.chg-so{margin:8px 0 0;padding:9px 13px;background:var(--accent-bg);
border-radius:8px;font-size:14.5px;color:#194185;font-weight:550}
.chg-src{font-size:12px;color:var(--soft);margin-top:6px}
.act{border:1px solid var(--line);border-radius:11px;margin-bottom:13px;overflow:hidden}
.act.commit{border-color:#fecdca}
.act.held{border-color:#fedf89;background:#fffdf7}
.act.held .act-head{background:#fffaeb}
.hold{margin:0 0 12px;padding:10px 13px;background:#fffaeb;border:1px solid #fedf89;
border-radius:8px;font-size:13.5px;color:#93370d}
.hold b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.06em;
color:#b54708;margin-bottom:3px}
.hold-until{color:#7a2e0e;font-weight:600}
.holds{background:#fffaeb;border:1px solid #fedf89;border-left:4px solid #b54708;
border-radius:12px;padding:15px 20px;margin-bottom:22px}
.holds h2{margin:0 0 9px;font-size:13px;text-transform:uppercase;
letter-spacing:.08em;color:#b54708}
.holds ul{margin:0;padding-left:19px}
.holds li{font-size:14.5px;color:#93370d;margin-bottom:5px}
.act-head{display:flex;gap:11px;padding:12px 15px;align-items:center;
flex-wrap:wrap;background:#fcfcfc;border-bottom:1px solid var(--line)}
.act-rank{width:24px;height:24px;flex:none;border-radius:6px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:12px;font-weight:650}
.act-title{flex:1;min-width:0;font-weight:600;font-size:15.5px}
.act-min{color:var(--soft);font-size:12.5px;font-variant-numeric:tabular-nums}
.act-body{padding:13px 15px}
.act-why{margin:0 0 11px;font-size:14.5px;color:var(--ink)}
.act-why b{display:inline-block;font-size:11px;text-transform:uppercase;
letter-spacing:.07em;color:var(--soft);margin-right:8px;font-weight:650;
vertical-align:1px}
.act-body ul{margin:0;padding-left:19px}
.act-body li{margin-bottom:5px;font-size:14.5px;color:var(--mut)}
.act-where{margin:11px 0 0;display:flex;gap:9px;align-items:center;flex-wrap:wrap;
font-size:13px;color:var(--soft)}
.act-commit{margin:11px 0 0;padding:8px 12px;background:#fef3f2;
border:1px solid #fecdca;border-radius:8px;font-size:13.5px;color:#b42318;
font-weight:550}
.act-block{margin:11px 0 0;padding:8px 12px;background:#fffaeb;
border:1px solid #fedf89;border-radius:8px;font-size:13.5px;color:#b54708}
.act-quote{margin:11px 0 0;padding-left:12px;border-left:3px solid var(--line);
font-size:13px;color:var(--soft);font-style:italic}
.act-draft{margin:13px 0 0;border:1px solid var(--line);border-radius:9px;
overflow:hidden}
.wait{list-style:none;margin:0;padding:0}
.wait li{display:flex;gap:13px;padding:11px 0;border-bottom:1px dashed var(--line);
align-items:flex-start}
.wait li:last-child{border-bottom:0}
.wait-who{flex:none;width:170px;font-weight:600;font-size:14.5px}
.wait-main{flex:1;min-width:0;font-size:14.5px}
.wait-sub{color:var(--soft);font-size:13px;margin-top:2px}
.wait-chase{flex:none;font-size:12.5px;color:#b54708;font-weight:600;
white-space:nowrap}
.dec{background:#fffaeb;border:1px solid #fedf89;border-radius:10px;
padding:12px 15px;margin-bottom:11px}
.dec-q{font-weight:600;font-size:14.5px;color:#93370d}
.dec ul{margin:7px 0 0;padding-left:19px;font-size:14px;color:var(--mut)}
.dec-owner{margin:8px 0 0;font-size:13px;color:#b54708;font-weight:600}
.skip{background:#fffaeb;border:1px solid #fedf89;border-left:4px solid #b54708;
border-radius:12px;padding:16px 20px;margin-bottom:24px}
.skip strong{color:#b54708}
.watch-list{margin:0;padding-left:19px}
.watch-list li{margin-bottom:6px;font-size:14.5px;color:var(--mut)}
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
        bits.append(f"sent {st.get('at', '')}, with {st.get('who', 'them')}")
    elif st["closed"]:
        bits.append(f"{st['label'].lower()} {st.get('at', '')}")
    if st.get("note"):
        bits.append(st["note"])
    return " &middot; ".join(esc(b) for b in bits)


def render_track(tickets: list[dict], refs: dict[str, str], meeting_date: str) -> str:
    """The one list Rei works from all afternoon: what is his, what is not."""
    rows = tracked(tickets, PROGRESS)
    if not rows:
        return '<div class="panel" style="padding:18px 22px"><p class="empty">Nothing came out of this standup that needs action from you.</p></div>'

    counts = {"todo": 0, "hold": 0, "waiting": 0, "closed": 0}
    out = []
    for ref, a, st in rows:
        counts["closed" if st["closed"] else st["state"]] += 1
        mins = a.get("est_minutes")
        sub = sub_line(st)
        out.append(
            f"""
      <li class="tr {"shut" if st["closed"] else ""}">
        <input class="tr-box" type="checkbox" value="{esc(a.get("rank"))}"
               data-closed="{"1" if st["closed"] else "0"}"
               {"checked disabled" if st["closed"] else ""}>
        <span class="tr-rank">{esc(a.get("rank", "-"))}</span>
        <span class="tr-tag">{esc(ref)}</span>
        <a class="tr-title" href="#{esc(refs.get(ref, anchor(ref)))}">{esc(a.get("title"))}
          {f'<span class="tr-note">{sub}</span>' if sub else ""}</a>
        {pill(st["label"], st["tone"])}
        <span class="tr-min">{f"{esc(mins)} min" if mins and not st["closed"] else ""}</span>
      </li>"""
        )

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
    return f"""
  <div class="track">
    <div class="track-head"><h2>Where you are</h2><span>{esc(summary)}</span></div>
    <ul style="list-style:none;margin:0;padding:0">{"".join(out)}</ul>
    <div class="track-sync" id="sync" hidden>
      <span>Ticked here but not saved:</span><code id="synccmd"></code>
      <button class="copy" id="synccopy" data-copy="">copy</button>
    </div>
  </div>
  <script>
  (function(){{
    var K='tgtick-{meeting_date}';
    var saved=JSON.parse(localStorage.getItem(K)||'[]');
    var bar=document.getElementById('sync'),cmd=document.getElementById('synccmd');
    var btn=document.getElementById('synccopy');
    var boxes=[].slice.call(document.querySelectorAll('.tr-box'));
    boxes.forEach(function(b){{
      if(b.dataset.closed==='1'){{
        saved=saved.filter(function(r){{return r!==b.value}});
        return;
      }}
      if(saved.indexOf(b.value)>-1){{b.checked=true;b.closest('.tr').classList.add('ticked')}}
      b.addEventListener('change',function(){{
        var i=saved.indexOf(b.value);
        if(b.checked&&i<0)saved.push(b.value);
        if(!b.checked&&i>-1)saved.splice(i,1);
        b.closest('.tr').classList.toggle('ticked',b.checked);
        sync();
      }});
    }});
    function sync(){{
      localStorage.setItem(K,JSON.stringify(saved));
      var line='./tick.py '+saved.slice().sort(function(a,b){{return a-b}}).join(' ');
      bar.hidden=!saved.length;
      cmd.textContent=line;
      btn.dataset.copy=line;
    }}
    sync();
  }})();
  </script>"""


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


def render_changed(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        src = r.get("source_url", "")
        where = r.get("where", "")
        out.append(
            f"""
        <div class="chg">
          <div class="chg-line was"><span class="k">Was</span><span class="v">{esc(r.get("before"))}</span></div>
          <div class="chg-line"><span class="k">Now</span><span class="v">{esc(r.get("after"))}</span></div>
          {f'<p class="chg-so">{esc(r.get("so_what"))}</p>' if r.get("so_what") else ""}
          <div class="chg-src">{esc(where)} {link_btn(src, "Source") if src else ""}</div>
        </div>"""
        )
    return f"""
      <section class="sub">
        <h3>What changed today</h3>
        {"".join(out)}
      </section>"""


def render_draft(d: dict) -> str:
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
    return f"""
        <div class="act-draft">
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go there")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
          </div>
          <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
          {trans}
        </div>"""


def render_actions(rows: list[dict]) -> str:
    if not rows:
        return """
      <section class="sub">
        <h3>To do</h3>
        <p class="empty">Nothing to do on this one right now.</p>
      </section>"""
    out = []
    for r in sorted(rows, key=lambda x: x.get("rank", 99)):
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
            note = f" {esc(st['note'])}" if st.get("note") else ""
            status_block = (
                f'<p class="sent-note"><b>Sent {esc(st.get("at", ""))}</b>'
                f'Nothing more from you until {esc(st.get("who", "they"))} '
                f"come back.{note}</p>"
            )
        elif hold:
            revisit = hold.get("revisit")
            status_block = f"""
            <p class="hold"><b>Do not send this yet</b>{esc(hold.get("why"))}
            <span class="hold-until">Wait for: {esc(hold.get("until"))}</span>
            {f'<span class="hold-until"> Chase on {esc(revisit)}.</span>' if revisit else ""}</p>"""
        state_pill = pill(st["label"], st["tone"])
        out.append(
            f"""
        <div class="act {st["state"]} {"held" if hold and not done else ""} {"commit" if committed else ""}">
          <div class="act-head">
            <span class="act-rank">{esc(r.get("rank", "-"))}</span>
            <span class="act-title">{esc(r.get("title"))}</span>
            {state_pill}
            <span class="act-min">{f"{esc(mins)} min" if mins else ""}</span>
          </div>
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
            {render_draft(r.get("draft") or {})}
          </div>
        </div>"""
        )
    return f"""
      <section class="sub">
        <h3>To do, hardest consequence first</h3>
        {"".join(out)}
      </section>"""


def render_waiting(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        chase = r.get("chase_on")
        out.append(
            f"""
        <li>
          <span class="wait-who">{esc(r.get("who"))}</span>
          <span class="wait-main">{esc(r.get("what"))}
            {f'<span class="wait-sub">Blocks: {esc(r.get("blocks"))}</span>' if r.get("blocks") else ""}
            <span class="wait-sub">Due {esc(r.get("due") or "not stated")}
            {link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</span>
          </span>
          <span class="wait-chase">{f"chase {esc(chase)}" if chase else ""}</span>
        </li>"""
        )
    return f"""
      <section class="sub">
        <h3>Waiting on someone else</h3>
        <ul class="wait">{"".join(out)}</ul>
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


def render_ticket(t: dict, ident: str) -> str:
    internal = t.get("internal_ticket") or {}
    int_block = ""
    if internal.get("name"):
        int_block = (
            f'<p class="tk-int"><b>Internal, never to TG:</b> '
            f'{esc(internal.get("name"))} {link_btn(internal.get("url", ""), "Open")}</p>'
        )

    silent = (
        '<span class="silent">Not reached at the standup</span>'
        if t.get("raised_at_standup") is False
        else ""
    )

    return f"""
    <article class="tk" id="{esc(ident)}">
      <header class="tk-head">
        <h2><span class="ix-tag">{esc(t.get("ref"))}</span> {esc(t.get("title_en"))}</h2>
        <p class="tk-ja">{esc(t.get("title_ja"))}</p>
        <p class="tk-meta">
          {pill(t.get("status_label", "-"), t.get("status_tone", "grey"))}
          {silent}
          {link_btn(t.get("asana_url", ""), "Asana ticket")}
        </p>
        {int_block}
      </header>

      {render_terms(t.get("terms", []))}

      <section class="sub">
        <h3>Where it stands</h3>
        <p class="status">{esc(t.get("where_it_stands"))}</p>
      </section>

      {render_changed(t.get("changed_today", []))}
      {render_actions(t.get("actions", []))}
      {render_waiting(t.get("waiting_on", []))}
      {render_decisions(t.get("open_decisions", []))}
      {render_threads(t.get("threads", []))}
    </article>"""


def shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}{EXTRA_CSS}</style></head>
<body>
{body}
<script>{JS}</script></body></html>"""


def render(data: dict) -> str:
    global PROGRESS
    meeting_date = data.get("meeting_date") or date.today().isoformat()
    PROGRESS = load_progress(meeting_date)
    try:
        pretty = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%A %-d %B")
    except ValueError:
        pretty = meeting_date

    tickets = data.get("tickets", [])
    refs = {t.get("ref", ""): anchor(t.get("ref", "")) for t in tickets}
    cards = "".join(render_ticket(t, refs[t.get("ref", "")]) for t in tickets)

    total = sum(
        a.get("est_minutes") or 0
        for t in tickets
        for a in t.get("actions", [])
        if state_of(a)["state"] == "todo"
    )

    held = [
        (t.get("ref", ""), a)
        for t in tickets
        for a in t.get("actions", [])
        if state_of(a)["state"] == "hold"
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

    nxt = data.get("next_standup") or {}
    skip_block = ""
    if nxt.get("skipped"):
        skip_block = f"""
  <div class="skip"><strong>No standup on {esc(nxt.get("date"))}.</strong>
  {esc(nxt.get("reason"))} Anything that was waiting for that meeting now has to
  move into Asana. The morning prep will not build that day.</div>"""

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

    body = f"""
<header class="top"><div class="top-in">
  <h1>After the TG billing standup</h1>
  <span class="date">{esc(pretty)}</span>
  <span style="margin-left:auto">{link_btn(data.get("notion_url", ""), "Meeting note")}</span>
</div></header>
<div class="wrap">
  <div class="headline"><p>{esc(data.get("headline"))}</p></div>
  {skip_block}
  {render_track(tickets, refs, meeting_date)}
  <p class="foot" style="margin:0 0 22px">Tick as you go. To make it stick for
  the next rebuild, run the command that appears, or just tell the chat.
  {f"About {total} min of work left with you." if total else ""}</p>
  {hold_block}
  <h2 class="tickets-h">{len(tickets)} ticket{"s" if len(tickets) != 1 else ""}, everything for each one in one place</h2>
  {cards}
  {watch_block}
  {gap_block}
  <p class="foot">Generated {esc(data.get("generated_at"))}</p>
</div>"""
    return shell(f"TG post-standup {meeting_date}", body)


def render_error(message: str) -> str:
    body = f"""
<div class="wrap" style="padding-top:40px">
  <div class="err">
    <h1 style="margin:0 0 8px;font-size:20px">Post-standup list did not generate</h1>
    <p style="margin:0">Run it by hand with <code>./run_post.sh --force</code>,
    or read the Notion meeting note directly. Details below.</p>
    <pre>{esc(message)}</pre>
  </div>
</div>"""
    return shell("TG post-standup failed", body)


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
    actions = sum(len(t.get("actions", [])) for t in data.get("tickets", []))
    print(f"wrote {dest} ({len(data['tickets'])} tickets, {actions} actions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
