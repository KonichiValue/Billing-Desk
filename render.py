#!/usr/bin/env python3
"""Render the morning prep JSON into a single self-contained HTML page.

Usage:
    python3 render.py output/prep-2026-08-24.json output/prep-2026-08-24.html
    python3 render.py --error "message" output/prep-2026-08-24.html
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

RUBY = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")

TONES = {
    "red": ("#b42318", "#fef3f2", "#fecdca"),
    "amber": ("#b54708", "#fffaeb", "#fedf89"),
    "green": ("#067647", "#ecfdf3", "#abefc6"),
    "grey": ("#414651", "#f5f5f5", "#e0e0e0"),
}

URGENCY = {
    "today": ("Today", "red"),
    "this-week": ("This week", "amber"),
    "monitor": ("Monitor", "grey"),
}


def furi(raw: str) -> str:
    """Escape text, then turn {漢字|かんじ} into real ruby annotations."""
    return RUBY.sub(r"<ruby>\1<rt>\2</rt></ruby>", html.escape(raw or ""))


def esc(raw: Any) -> str:
    return html.escape(str(raw or ""))


def plain(raw: str) -> str:
    """Strip furigana markup, leaving just the kanji. For copy buttons."""
    return RUBY.sub(r"\1", raw or "")


def pill(label: str, tone: str) -> str:
    fg, bg, border = TONES.get(tone, TONES["grey"])
    return (
        f'<span class="pill" style="color:{fg};background:{bg};'
        f'border-color:{border}">{esc(label)}</span>'
    )


def link_btn(url: str, label: str) -> str:
    if not url:
        return ""
    return f'<a class="btn" href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def render_action_board(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">Nothing needs doing before the standup.</p>'
    out = []
    for row in sorted(rows, key=lambda r: r.get("rank", 99)):
        u_label, u_tone = URGENCY.get(row.get("urgency", "monitor"), URGENCY["monitor"])
        mins = row.get("est_minutes")
        out.append(
            f"""
        <li class="action">
          <div class="action-rank">{esc(row.get("rank", "-"))}</div>
          <div class="action-body">
            <div class="action-top">
              <span class="action-text">{esc(row.get("action"))}</span>
              {pill(u_label, u_tone)}
            </div>
            <div class="action-meta">
              <span class="ref">{esc(row.get("ticket_ref"))}</span>
              <span>{esc(row.get("where"))}</span>
              <span class="why">{esc(row.get("why_now"))}</span>
              {f'<span class="mins">{esc(mins)} min</span>' if mins else ""}
            </div>
          </div>
          <div class="action-go">{link_btn(row.get("link", ""), "Open")}</div>
        </li>"""
        )
    return f'<ol class="action-list">{"".join(out)}</ol>'


def render_timeline(events: list[dict]) -> str:
    if not events:
        return '<p class="empty">No discussion found in Asana or Slack.</p>'
    out = []
    for ev in events:
        who = esc(ev.get("who"))
        side = "tg" if "(TG)" in (ev.get("who") or "") else "kraken"
        url = ev.get("url", "")
        anchor = (
            f'<a href="{esc(url)}" target="_blank" rel="noopener" class="src">source</a>'
            if url
            else ""
        )
        out.append(
            f"""
        <li class="tl-item {side}">
          <div class="tl-date">{esc(ev.get("date"))}</div>
          <div class="tl-main">
            <div class="tl-who">{who} <span class="tl-where">{esc(ev.get("where"))}</span> {anchor}</div>
            <div class="tl-what">{esc(ev.get("what"))}</div>
          </div>
        </li>"""
        )
    return f'<ul class="timeline">{"".join(out)}</ul>'


def render_script(blocks: list[dict]) -> str:
    if not blocks:
        return '<p class="empty">Nothing to say on this one today.</p>'
    out = []
    for block in blocks:
        lines = []
        for line in block.get("lines", []):
            lines.append(
                f"""
          <div class="jp-line">
            <p class="jp">{furi(line.get("ja_ruby", ""))}</p>
            <p class="en">{esc(line.get("en"))}</p>
          </div>"""
            )
        raw = "\n".join(plain(l.get("ja_ruby", "")) for l in block.get("lines", []))
        out.append(
            f"""
        <div class="jp-block">
          <div class="jp-heading">
            <span class="jp-h-ja">{furi(block.get("heading", ""))}</span>
            <span class="jp-h-en">{esc(block.get("heading_en"))}</span>
            <button class="copy" data-copy="{esc(raw)}">copy</button>
          </div>
          {"".join(lines)}
        </div>"""
        )
    return "".join(out)


def render_questions(questions: list[dict]) -> str:
    if not questions:
        return ""
    out = []
    for q in questions:
        who = q.get("who", "TG")
        out.append(
            f"""
        <li class="q">
          <div class="q-en">{esc(q.get("en"))} {pill(who, "amber" if who == "TG" else "grey")}</div>
          <div class="q-ja">{furi(q.get("ja_ruby", ""))}</div>
        </li>"""
        )
    return f"""
      <section class="sub">
        <h3>Questions I need answered</h3>
        <ul class="qlist">{"".join(out)}</ul>
      </section>"""


def render_drafts(drafts: list[dict]) -> str:
    if not drafts:
        return ""
    out = []
    for d in drafts:
        body = d.get("body_ruby", "")
        is_ja = d.get("language") == "ja"
        rendered = furi(body) if is_ja else esc(body)
        trans = (
            f'<p class="draft-en">{esc(d.get("body_en"))}</p>'
            if is_ja and d.get("body_en")
            else ""
        )
        out.append(
            f"""
        <div class="draft">
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go to thread")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
          </div>
          <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
          {trans}
        </div>"""
        )
    return f"""
      <details class="sub drafts">
        <summary><h3>Draft replies ({len(drafts)})</h3></summary>
        {"".join(out)}
      </details>"""


CONSEQUENCE_ROWS = [
    ("fix_covers", "The fix covers"),
    ("falls_outside", "It does not cover"),
    ("accumulates", "So this piles up"),
    ("who_owns_it", "Owned by"),
    ("done_means", "Cleanup means"),
    ("still_open", "Still undecided"),
]


def render_consequences(c: dict) -> str:
    """The scope of a fix, and what happens to everything outside it.

    This is where TG's questions come from, so it renders even when half the
    fields are blank."""
    if not isinstance(c, dict):
        return ""
    rows = [(label, c.get(key)) for key, label in CONSEQUENCE_ROWS if c.get(key)]
    if not rows:
        return ""
    items = "".join(
        f'<div class="cons-row"><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>'
        for label, value in rows
    )
    return f"""
      <section class="sub cons">
        <h3>Scope, and what falls outside it</h3>
        <dl class="cons-list">{items}</dl>
      </section>"""


def render_ticket(t: dict) -> str:
    issue = "".join(f"<li>{esc(b)}</li>" for b in t.get("the_issue", []))
    unknowns = t.get("unknowns", [])
    unknown_block = ""
    if unknowns:
        items = "".join(f"<li>{esc(u)}</li>" for u in unknowns)
        unknown_block = f"""
      <section class="sub warn">
        <h3>Check before 10:30</h3>
        <ul>{items}</ul>
      </section>"""

    sources = t.get("sources", [])
    source_block = ""
    if sources:
        items = "".join(
            f'<li><a href="{esc(s.get("url"))}" target="_blank" rel="noopener">{esc(s.get("label"))}</a></li>'
            for s in sources
        )
        source_block = f"""
      <details class="sub sources">
        <summary><h3>Sources ({len(sources)})</h3></summary>
        <ul>{items}</ul>
      </details>"""

    days = t.get("days_since_activity")
    stale = ' <span class="stale">quiet for ' + str(days) + " days</span>" if isinstance(days, int) and days >= 3 else ""

    position = (
        f'<p class="position"><strong>Our position:</strong> {esc(t.get("our_position"))}</p>'
        if t.get("our_position")
        else ""
    )

    estimate = (
        f'<span class="est">{esc(t.get("estimate"))}</span>' if t.get("estimate") else ""
    )

    return f"""
    <article class="ticket" id="{esc(t.get("ref"))}">
      <header class="t-head">
        <div class="t-ref">{esc(t.get("order", "?"))}</div>
        <div class="t-titles">
          <h2><span class="tag">{esc(t.get("ref"))}</span>{esc(t.get("title_en"))}</h2>
          <p class="t-ja">{esc(t.get("title_ja"))}</p>
          <p class="t-meta">
            {pill(t.get("status_label", "-"), t.get("status_tone", "grey"))}
            {f'<span>{esc(t.get("board_position"))}</span>' if t.get("board_position") else ""}
            {estimate}
            {stale}
          </p>
        </div>
        <div class="t-go">{link_btn(t.get("asana_url", ""), "Asana")}</div>
      </header>

      <section class="sub">
        <h3>The issue in 20 seconds</h3>
        <ul class="issue">{issue}</ul>
        {f'<p class="matters">{esc(t.get("why_it_matters"))}</p>' if t.get("why_it_matters") else ""}
      </section>

      <section class="sub">
        <h3>Where it stands</h3>
        <p class="status">{esc(t.get("latest_status"))}</p>
        {position}
      </section>

      {render_consequences(t.get("consequences", {}))}

      <details class="sub" open>
        <summary><h3>How we got here</h3></summary>
        {render_timeline(t.get("timeline", []))}
      </details>

      <section class="sub script">
        <h3>What I say today</h3>
        {'<p class="noask">Nothing needed from TG on this one. Status only.</p>' if t.get("tg_ask_needed") is False else ""}
        {render_script(t.get("jp_script", []))}
      </section>

      {render_questions(t.get("open_questions", []))}
      {render_drafts(t.get("drafts", []))}
      {unknown_block}
      {source_block}
    </article>"""


CSS = """
:root{--ink:#181d27;--mut:#535862;--soft:#717680;--line:#e9eaeb;--bg:#fafafa;
--card:#fff;--accent:#0b5cd5;--accent-bg:#eff6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans",
"Noto Sans JP",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:0 20px 80px}
header.top{position:sticky;top:0;z-index:20;background:rgba(250,250,250,.92);
backdrop-filter:blur(8px);border-bottom:1px solid var(--line);margin-bottom:24px}
.top-in{max-width:860px;margin:0 auto;padding:14px 20px;display:flex;
align-items:center;gap:16px;flex-wrap:wrap}
.top h1{font-size:16px;margin:0;font-weight:650;letter-spacing:-.01em}
.top .date{color:var(--soft);font-size:14px}
#countdown{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:650;
font-size:14px;padding:5px 11px;border-radius:7px;background:#fff;
border:1px solid var(--line)}
#countdown.soon{background:#fef3f2;border-color:#fecdca;color:#b42318}
.toggle{font:inherit;font-size:13px;padding:5px 11px;border-radius:7px;
border:1px solid var(--line);background:#fff;cursor:pointer;color:var(--mut)}
.toggle:hover{border-color:var(--accent);color:var(--accent)}
.headline{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
border-radius:12px;padding:18px 22px;margin-bottom:24px}
.headline p{margin:0;font-size:19px;line-height:1.45;font-weight:550;letter-spacing:-.01em}
h2.board-h,h2.tickets-h{font-size:13px;text-transform:uppercase;letter-spacing:.08em;
color:var(--soft);margin:32px 0 12px;font-weight:650}
.action-list{list-style:none;margin:0;padding:0;background:var(--card);
border:1px solid var(--line);border-radius:12px;overflow:hidden}
.action{display:flex;gap:14px;padding:14px 16px;border-bottom:1px solid var(--line);
align-items:flex-start}
.action:last-child{border-bottom:0}
.action-rank{width:26px;height:26px;flex:none;border-radius:7px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:13px;font-weight:650}
.action-body{flex:1;min-width:0}
.action-top{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.action-text{font-weight:600}
.action-meta{display:flex;gap:12px;flex-wrap:wrap;color:var(--soft);font-size:13px;margin-top:3px}
.action-meta .ref{font-weight:650;color:var(--accent)}
.action-meta .why{font-style:italic}
.action-meta .mins{margin-left:auto}
.pill{display:inline-block;font-size:11.5px;font-weight:650;padding:2px 8px;
border-radius:20px;border:1px solid;letter-spacing:.01em;white-space:nowrap}
.btn{font-size:13px;text-decoration:none;color:var(--accent);border:1px solid var(--line);
background:#fff;padding:4px 10px;border-radius:7px;white-space:nowrap}
.btn:hover{border-color:var(--accent);background:var(--accent-bg)}
.ticket{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:22px;margin-bottom:20px}
.t-head{display:flex;gap:14px;align-items:flex-start;padding-bottom:16px;
border-bottom:1px solid var(--line);margin-bottom:4px}
.t-ref{width:30px;height:30px;flex:none;border-radius:8px;background:var(--accent-bg);
color:var(--accent);display:grid;place-items:center;font-size:13px;font-weight:700}
.t-titles{flex:1;min-width:0}
.t-titles h2{margin:0;font-size:19px;letter-spacing:-.015em;line-height:1.35}
.tag{display:inline-block;font-size:12.5px;font-weight:650;padding:2px 8px;
border-radius:6px;background:#f2f4f7;color:var(--mut);margin-right:9px;
vertical-align:2px;letter-spacing:0}
.est{color:#067647;font-weight:600}
.noask{margin:0 0 13px;padding:9px 13px;background:#ecfdf3;border:1px solid #abefc6;
border-radius:8px;color:#067647;font-size:14.5px;font-weight:550}
.t-ja{margin:3px 0 0;color:var(--mut);font-size:14px}
.t-meta{margin:9px 0 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.stale{color:#b54708;font-weight:600}
.sub{padding:16px 0;border-bottom:1px solid var(--line)}
.ticket>*:last-child{border-bottom:0;padding-bottom:0}
.sub h3{font-size:12.5px;text-transform:uppercase;letter-spacing:.07em;
color:var(--soft);margin:0 0 9px;font-weight:650;display:inline}
details>summary{cursor:pointer;list-style:none;padding:16px 0 9px}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"\\25B8";color:var(--soft);font-size:11px;
margin-right:7px;display:inline-block;transition:transform .15s}
details[open]>summary::before{transform:rotate(90deg)}
details.sub{padding-top:0}
.issue{margin:0;padding-left:19px}
.issue li{margin-bottom:5px}
.matters{margin:11px 0 0;padding:9px 13px;background:var(--accent-bg);
border-radius:8px;font-size:14.5px;color:#194185}
.status{margin:0}
.position{margin:9px 0 0;color:var(--mut);font-size:15px}
.cons-list{margin:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.cons-row{display:flex;gap:0;background:#fff;align-items:baseline}
.cons-row dt{flex:none;width:158px;padding:9px 13px;font-size:12.5px;
font-weight:650;color:var(--soft);background:#fcfcfc}
.cons-row dd{flex:1;min-width:0;margin:0;padding:9px 13px;font-size:14.5px}
.cons-row:last-child dd{color:#b54708;font-weight:550}
.timeline{list-style:none;margin:0;padding:0}
.tl-item{display:flex;gap:13px;padding:7px 0;border-left:2px solid var(--line);
padding-left:14px;margin-left:4px}
.tl-item.tg{border-left-color:#f7b27a}
.tl-item.kraken{border-left-color:#84caff}
.tl-date{flex:none;width:76px;color:var(--soft);font-size:13px;
font-variant-numeric:tabular-nums}
.tl-who{font-size:13px;font-weight:600}
.tl-where{color:var(--soft);font-weight:400}
.tl-what{font-size:14.5px;color:var(--mut)}
.src{font-size:12px;color:var(--accent);text-decoration:none;margin-left:5px}
.jp-block{margin-bottom:18px}
.jp-heading{display:flex;align-items:baseline;gap:10px;margin-bottom:9px;
padding-bottom:5px;border-bottom:1px dashed var(--line)}
.jp-h-ja{font-size:16px;font-weight:650}
.jp-h-en{font-size:12.5px;color:var(--soft);text-transform:uppercase;letter-spacing:.05em}
.copy{margin-left:auto;font:inherit;font-size:11.5px;color:var(--soft);background:none;
border:1px solid var(--line);border-radius:6px;padding:2px 8px;cursor:pointer}
.copy:hover{color:var(--accent);border-color:var(--accent)}
.jp-line{margin-bottom:11px;padding-left:13px;border-left:3px solid #eaecf0}
.jp{margin:0;font-size:21px;line-height:2.1;letter-spacing:.01em}
ruby rt{font-size:.5em;color:var(--accent);font-weight:600;letter-spacing:0}
.en{margin:1px 0 0;font-size:14px;color:var(--mut)}
.qlist{list-style:none;margin:0;padding:0}
.q{padding:9px 0;border-bottom:1px dashed var(--line)}
.q:last-child{border-bottom:0}
.q-en{font-weight:550;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.q-ja{font-size:18px;line-height:2;margin-top:3px;color:var(--mut)}
.draft{border:1px solid var(--line);border-radius:10px;margin-bottom:11px;overflow:hidden}
.draft-head{display:flex;gap:9px;align-items:center;padding:8px 13px;
background:#fafafa;border-bottom:1px solid var(--line);font-size:13px;color:var(--mut)}
.draft-body{padding:13px;white-space:pre-wrap}
.draft-body.ja{font-size:17px;line-height:2}
.draft-en{margin:0;padding:0 13px 13px;font-size:13.5px;color:var(--soft)}
.warn{background:#fffaeb;border:1px solid #fedf89;border-radius:10px;
padding:13px 16px;margin-top:16px}
.warn h3{color:#b54708}
.warn ul{margin:7px 0 0;padding-left:19px}
.empty{color:var(--soft);font-style:italic;margin:0}
.gaps{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 22px;margin-top:24px}
.gaps h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;
color:var(--soft);margin:0 0 9px}
.gaps ul{margin:0;padding-left:19px}
.foot{text-align:center;color:var(--soft);font-size:12.5px;margin-top:32px}
body.script-only .headline,body.script-only .board,body.script-only .sub:not(.script),
body.script-only details,body.script-only .gaps,body.script-only .t-go{display:none}
body.script-only .jp{font-size:26px}
body.script-only .ticket{padding:18px 22px}
.err{background:#fef3f2;border:1px solid #fecdca;border-radius:12px;padding:22px;
color:#b42318}
.err pre{white-space:pre-wrap;font-size:13px;background:#fff;padding:13px;
border-radius:8px;margin:13px 0 0;color:var(--ink)}
@media print{header.top,.btn,.copy,.toggle{display:none}
body{background:#fff}.ticket{break-inside:avoid;border-color:#ccc}
details{display:block}details>summary{display:none}}
"""

JS = """
(function(){
  var el=document.getElementById('countdown');
  var target=new Date(document.body.dataset.meeting);
  function tick(){
    var d=Math.floor((target-new Date())/1000);
    if(d<=0){el.textContent='Standup started';el.classList.add('soon');return}
    var h=Math.floor(d/3600),m=Math.floor(d%3600/60);
    el.textContent=(h?h+'h ':'')+m+'m to standup';
    if(d<1800)el.classList.add('soon');
  }
  if(el&&!isNaN(target)){tick();setInterval(tick,20000)}
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      navigator.clipboard.writeText(b.dataset.copy);
      var o=b.textContent;b.textContent='copied';
      setTimeout(function(){b.textContent=o},1200);
    });
  });
  var t=document.getElementById('scriptonly');
  if(t)t.addEventListener('click',function(){
    document.body.classList.toggle('script-only');
    t.textContent=document.body.classList.contains('script-only')
      ?'Show everything':'Script only';
  });
})();
"""


def shell(title: str, body: str, meeting_iso: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body data-meeting="{esc(meeting_iso)}">
{body}
<script>{JS}</script></body></html>"""


def render(data: dict) -> str:
    meeting_date = data.get("meeting_date") or date.today().isoformat()
    try:
        pretty = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%A %-d %B")
    except ValueError:
        pretty = meeting_date

    tickets = sorted(data.get("tickets", []), key=lambda t: t.get("order", 99))
    cards = "".join(render_ticket(t) for t in tickets)

    gaps = data.get("gaps", [])
    gap_block = ""
    if gaps:
        items = "".join(f"<li>{esc(g)}</li>" for g in gaps)
        gap_block = f'<section class="gaps"><h2>Open gaps</h2><ul>{items}</ul></section>'

    body = f"""
<header class="top"><div class="top-in">
  <h1>TG billing standup prep</h1>
  <span class="date">{esc(pretty)} &middot; 10:30 JST</span>
  <span id="countdown"></span>
  <button class="toggle" id="scriptonly">Script only</button>
</div></header>
<div class="wrap">
  <div class="headline"><p>{esc(data.get("headline"))}</p></div>
  <div class="board">
    <h2 class="board-h">Do first</h2>
    {render_action_board(data.get("action_board", []))}
  </div>
  <h2 class="tickets-h">{len(tickets)} open ticket{"s" if len(tickets) != 1 else ""}, in the order they come up on the board</h2>
  {cards}
  {gap_block}
  <p class="foot">Generated {esc(data.get("generated_at"))}</p>
</div>"""
    return shell(f"TG prep {meeting_date}", body, f"{meeting_date}T10:30:00+09:00")


def render_notice(reason: str, quote: str = "", url: str = "") -> str:
    body = f"""
<div class="wrap" style="padding-top:60px">
  <div class="headline" style="border-left-color:#b54708">
    <p>No billing standup today.</p>
    <p style="font-size:15px;font-weight:400;color:var(--mut);margin-top:8px">
      {esc(reason)}</p>
  </div>
  {f'<p class="quote-note" style="color:var(--soft);font-style:italic">{esc(quote)}</p>' if quote else ""}
  {f'<p>{link_btn(url, "Meeting note that said so")}</p>' if url else ""}
  <p class="foot">Build the prep anyway with <code>./run_prep.sh --force</code>.</p>
</div>"""
    return shell("No TG standup today", body)


def render_error(message: str) -> str:
    body = f"""
<div class="wrap" style="padding-top:40px">
  <div class="err">
    <h1 style="margin:0 0 8px;font-size:20px">Prep did not generate this morning</h1>
    <p style="margin:0">Run it by hand with <code>./run_prep.sh --force</code>,
    or open Asana directly. Details below.</p>
    <pre>{esc(message)}</pre>
  </div>
</div>"""
    return shell("TG prep failed", body)


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--error":
        Path(args[2]).write_text(render_error(args[1]), encoding="utf-8")
        return 0
    if len(args) >= 3 and args[0] == "--notice":
        reason, quote, url = (args[1:-1] + ["", ""])[:3]
        Path(args[-1]).write_text(render_notice(reason, quote, url), encoding="utf-8")
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
    print(f"wrote {dest} ({len(data.get('tickets', []))} tickets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
