#!/usr/bin/env python3
"""Shared parts of the desk page: styling, furigana, and the common blocks.

Not a page on its own. `render_desk.py` builds the page from the board and
`render_standup.py` builds the standup view inside it, and both take their
styling, their furigana handling and their item lifecycle from here so the two
views cannot drift apart.
"""

from __future__ import annotations

import html
import re
from typing import Any

RUBY = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")
KANJI = re.compile(r"[\u4e00-\u9fff]")

TONES = {
    "red": ("#b42318", "#fef3f2", "#fecdca"),
    "amber": ("#b54708", "#fffaeb", "#fedf89"),
    "green": ("#067647", "#ecfdf3", "#abefc6"),
    "grey": ("#414651", "#f5f5f5", "#e0e0e0"),
    "blue": ("#175cd3", "#eff8ff", "#b2ddff"),
}

# An action is with Rei, with somebody else, or finished. Sending a message
# moves it to the middle state rather than closing it, because the reply comes
# back on the same number. Third value is the sort order of the group.
LIFECYCLE = {
    "todo": ("With you", "red", 0),
    "hold": ("Not yet", "amber", 1),
    "waiting": ("Waiting", "blue", 2),
    "done": ("Done", "green", 3),
    "sent": ("Sent", "green", 3),
    "dropped": ("Dropped", "grey", 3),
}
CLOSED_STATES = {"done", "sent", "dropped"}



def furi(raw: str) -> str:
    """Escape text, then turn {漢字|かんじ} into real ruby annotations.

    Only kanji get a reading. Models reliably over-apply the markup and wrap
    katakana in it too, and ステートメント with すてーとめんと printed above it is
    noise on a line Rei is reading out loud at speed. Dropping the annotation
    here rather than in the prompt means it cannot come back with the next model.
    """
    def one(match: re.Match) -> str:
        base, reading = match.group(1), match.group(2)
        if not KANJI.search(base):
            return base
        return f"<ruby>{base}<rt>{reading}</rt></ruby>"

    return RUBY.sub(one, html.escape(raw or ""))


def esc(raw: Any) -> str:
    return html.escape(str(raw or ""))


def plain(raw: str) -> str:
    """Strip furigana markup, leaving just the kanji. For copy buttons."""
    return RUBY.sub(r"\1", raw or "")


def item_state(item: dict) -> dict:
    """Where one item sits: its state, label, tone, and who is holding it.

    The item carries its own state, because the board outlives the day it was
    written on. A hold is inferred when nothing has been recorded yet.
    """
    state = item.get("state") or ("hold" if item.get("hold") else "todo")
    waits = item.get("waits_on") or {}
    who = waits.get("who", "")
    at = item.get("state_at") or waits.get("since", "")
    label, tone, order = LIFECYCLE.get(state, LIFECYCLE["todo"])
    if state == "waiting" and who:
        label = f"Waiting on {who}"
    return {
        "state": state,
        "label": label,
        "tone": tone,
        "order": order,
        "closed": state in CLOSED_STATES,
        "who": who,
        "at": at,
        "note": item.get("state_note", ""),
        "sent": bool(item.get("sent_by_you")),
    }


def tracked(tickets: list[dict]) -> list[tuple[str, dict, dict]]:
    """Every item as (ticket ref, item, state), yours first, finished last."""
    rows = [
        (t.get("ref", ""), i, item_state(i))
        for t in tickets
        for i in t.get("items", [])
    ]
    return sorted(rows, key=lambda r: (r[2]["order"], r[1].get("id", 99)))


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
/* Two views, one page. The desk is what to do, the standup is what to say, and
   they share the same tickets, so switching must never feel like navigating. */
.views{display:flex;gap:2px;padding:3px;background:#f0f1f3;border-radius:9px}
.views button{font:600 13px/1 inherit;padding:7px 13px;border:0;border-radius:7px;
background:none;color:var(--mut);cursor:pointer}
.views button[aria-selected="true"]{background:#fff;color:var(--ink);
box-shadow:0 1px 2px rgba(16,24,40,.09)}
.views .badge{display:inline-block;margin-left:6px;min-width:17px;padding:0 5px;
border-radius:9px;background:#b42318;color:#fff;font-size:11px;line-height:17px;
font-weight:700;vertical-align:1px}
.views button[aria-selected="true"] .badge{background:var(--ink)}
body[data-view="desk"] #view-standup,body[data-view="standup"] #view-desk{display:none}
.keys{color:var(--soft);font-size:11.5px;margin-left:8px}
body.script-only .sub:not(.script),body.script-only .st-head .pos,
body.script-only details,body.script-only .st-brief,body.script-only .st-raise,
body.script-only .st-warn,body.script-only .st-cons{display:none}
body.script-only .jp{font-size:26px}
body.script-only .st-tk{padding:18px 22px}
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
  function putPlain(s){
    // Slack only turns `foo` into code when the clipboard carries plain text,
    // so never let a rich-text flavour reach it.
    if(navigator.clipboard&&navigator.clipboard.writeText){
      return navigator.clipboard.writeText(s).catch(function(){legacy(s)});
    }
    legacy(s);
  }
  function legacy(s){
    var a=document.createElement('textarea');
    a.value=s;a.setAttribute('readonly','');
    a.style.cssText='position:fixed;top:-1000px';
    document.body.appendChild(a);a.select();
    try{document.execCommand('copy')}finally{document.body.removeChild(a)}
  }
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      putPlain(b.dataset.copy);
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

  // The view lives on the body, so CSS does the switching and nothing reloads.
  // A hash link from one view to the other lands on the right ticket because we
  // switch first and let the browser scroll after.
  var tabs=[].slice.call(document.querySelectorAll('.views button'));
  function show(view,remember){
    if(!tabs.length)return;
    document.body.dataset.view=view;
    tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.view===view)});
    if(remember!==false)try{sessionStorage.setItem('desk-view',view)}catch(e){}
  }
  tabs.forEach(function(b){
    b.addEventListener('click',function(){show(b.dataset.view)});
  });
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[data-goto]');
    if(!a)return;
    show(a.dataset.goto);
    var target=document.querySelector(a.getAttribute('href'));
    if(target){e.preventDefault();target.scrollIntoView({behavior:'smooth',block:'start'});
      history.replaceState(null,'',a.getAttribute('href'))}
  });
  document.addEventListener('keydown',function(e){
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    var tag=(e.target.tagName||'').toLowerCase();
    if(tag==='input'||tag==='textarea')return;
    if(e.key==='1')show('desk');
    if(e.key==='2')show('standup');
    if(e.key==='s'&&t)t.click();
  });
  if(tabs.length){
    var start=document.body.dataset.view;
    try{
      var saved=sessionStorage.getItem('desk-view');
      if(saved)start=saved;
    }catch(e){}
    if(location.hash.indexOf('#s-')===0)start='standup';
    show(start,false);
  }
})();
"""
