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
from datetime import date
from typing import Any

RUBY = re.compile(r"\{([^|{}]+)\|([^|{}]+)\}")
KANJI = re.compile(r"[\u4e00-\u9fff]")

# Same four meanings everywhere on the page: yours, blocked, somebody else's,
# closed. Kept in step with the CSS variables of the same names.
TONES = {
    "red": ("#b42318", "#fef4f2", "#fbd2cd"),
    "amber": ("#b25309", "#fff9ed", "#f9dda3"),
    "green": ("#046c46", "#effaf4", "#a8e7c5"),
    "grey": ("#4e5666", "#f4f6fa", "#e5e8ee"),
    "blue": ("#1257c9", "#f0f6ff", "#bedaff"),
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


# What Rei is preparing for. Usually the 10:30 standup, sometimes an onsite,
# which is the same tickets with a great deal more riding on each one.
KINDS = {
    "standup": {
        "name": "Standup",
        "tab": "Standup",
        "at": "10:30",
        "what": "the 15 minutes at 10:30",
    },
    "onsite": {
        "name": "Onsite",
        "tab": "Onsite",
        "at": "",
        "what": "a day in the room with TG",
    },
    "workshop": {
        "name": "Workshop",
        "tab": "Workshop",
        "at": "",
        "what": "the session",
    },
}


def a_session(raw: dict) -> dict:
    """Fill in what the kind of session implies, leaving what was written."""
    out = dict(raw)
    kind = out.get("kind") or "standup"
    spec = KINDS.get(kind, KINDS["standup"])
    out["kind"] = kind
    out["name"] = out.get("label") or spec["name"]
    out["tab"] = spec["tab"]
    out["at"] = out.get("at") or spec["at"]
    out["what"] = spec["what"]
    return out


def sessions(board: dict) -> list[dict]:
    """Everything Rei still has to speak at, soonest first.

    A list rather than one field, because an onsite on Wednesday and a standup
    on Thursday are two different rooms with two different scripts, and a board
    that can only hold one of them forgets whichever is further away.

    Boards written before this change said `next_standup` and `standup`, so
    those are read too and nothing has to be regenerated to render.
    """
    raw = board.get("sessions")
    if raw is None:
        raw = []
        old = board.get("next_standup") or {}
        if old.get("date"):
            raw.append({"kind": "standup", **old})
        built = board.get("standup") or {}
        if built.get("date") and built.get("date") != old.get("date"):
            raw.append({"kind": "standup", "date": built["date"], "at": built.get("at")})
    today = date.today().isoformat()
    live = [a_session(s) for s in raw if (s.get("date") or "") >= today]
    return sorted(live, key=lambda s: (s.get("date", ""), s.get("at", "")))


def next_live(board: dict) -> dict:
    """The next session that is actually happening."""
    return next((s for s in sessions(board) if not s.get("skipped")), {})


def script_meta(board: dict) -> dict:
    """When the script was written, and the line it opens on."""
    meta = dict(board.get("script") or board.get("standup") or {})
    meta.setdefault("for_date", meta.get("date", ""))
    return meta


def script_session(board: dict) -> dict:
    """The session the current script was written for.

    If the script names a date, that is the room it describes, even when a
    different session is now sooner. Otherwise, the next live one.
    """
    wanted = script_meta(board).get("for_date")
    if wanted:
        match = next((s for s in sessions(board) if s.get("date") == wanted), None)
        if match:
            return match
        return a_session({"kind": "standup", "date": wanted})
    return next_live(board)


def when_words(iso: str, at: str = "") -> str:
    """2026-08-26 becomes "Wed 26 Aug", with the time when there is one."""
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    words = day.strftime("%a %-d %b")
    today = date.today()
    if day == today:
        words = "today"
    elif (day - today).days == 1:
        words = "tomorrow"
    return f"{words}, {at}" if at else words


def short_when(iso: str, at: str = "") -> str:
    """The same day in as few characters as a tab can spare: "Wed 10:30"."""
    if not iso:
        return ""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    left = (day - date.today()).days
    words = {0: "today", 1: "tomorrow"}.get(left, day.strftime("%a"))
    if left > 6 or left < 0:
        words = day.strftime("%-d %b")
    return f"{words} {at}".strip()


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
/* One neutral ramp, one accent that changes with the view, and four semantic
   colours that only ever mean one thing: red is yours, amber is blocked, blue
   is with somebody else, green is closed. Nothing else gets to be coloured, so
   colour on this page always carries information. */
:root{
--ink:#151a23;--mut:#4e5666;--soft:#79818f;--line:#e5e8ee;--hair:#f1f3f7;
--card:#fff;--page:#f4f6fa;--head:#0d1524;--head-2:#1a2740;
--accent:#0b5cd5;--accent-bg:#eff5ff;--accent-line:#c3daff;--accent-ink:#0a3d94;
--red:#b42318;--red-bg:#fef4f2;--red-line:#fbd2cd;
--amber:#b25309;--amber-bg:#fff9ed;--amber-line:#f9dda3;--amber-ink:#8a3d05;
--green:#046c46;--green-bg:#effaf4;--green-line:#a8e7c5;
--blue:#1257c9;--blue-bg:#f0f6ff;--blue-line:#bedaff;
--shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06);
--lift:0 2px 4px rgba(16,24,40,.06),0 8px 20px rgba(16,24,40,.06)}
/* The script view is a different room: warmer paper, plum accent. You can tell
   which view you are in from across the desk, without reading a tab. */
body[data-view="standup"]{--accent:#9c1b85;--accent-bg:#fdf1fa;--accent-line:#f1c3e6;
--accent-ink:#78116a;--page:#faf6f9}
*{box-sizing:border-box}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.views button:focus-visible{outline-color:#fff}
body{margin:0;background:var(--page);color:var(--ink);
font:15.5px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans",
"Noto Sans JP",sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:22px 20px 90px}
/* The script is read out loud, so it gets a narrower column than the desk. */
body[data-view="standup"] .wrap{max-width:840px}

/* Header. Dark, because the switcher has to be the most findable thing here. */
header.top{position:sticky;top:0;z-index:30;
background:linear-gradient(180deg,var(--head-2),var(--head));color:#e6ecf7;
box-shadow:inset 0 -1px 0 rgba(255,255,255,.06),0 4px 16px rgba(9,14,26,.14)}
/* Wider than the page it sits over: this row is navigation, not prose, and it
   has to hold the tabs and the buttons without wrapping. One line tall, since
   every pixel here is taken off the top of what he is actually reading. */
.top-in{max-width:1180px;margin:0 auto;padding:6px 20px;display:flex;
align-items:center;gap:10px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:8px}
.brand img{width:20px;height:20px;border-radius:6px;display:block}
.top h1{font-size:13px;margin:0;font-weight:650;color:#fff;letter-spacing:-.005em;
white-space:nowrap}
.top .date{color:#8a9bb8;font-size:12px;white-space:nowrap}
/* Hours old means a reply may have landed unseen, which is worth a colour. */
.top .date.old{color:#f4c27a}
.top .btn{color:#c9d6ea;border-color:rgba(255,255,255,.16);
background:rgba(255,255,255,.07);font-size:12px;padding:4px 9px}
.top .btn:hover{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.28);
color:#fff}
.acts{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
justify-content:flex-end}
#countdown{font-variant-numeric:tabular-nums;font-weight:650;font-size:12.5px;
padding:4px 10px;border-radius:7px;color:#dae4f5;background:rgba(255,255,255,.09);
border:1px solid rgba(255,255,255,.14)}
#countdown:empty{display:none}
#countdown.soon{background:#fee4e2;border-color:#fda29b;color:#912018}
.toggle{font:600 12px/1 inherit;padding:5px 10px;border-radius:7px;
border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.07);
cursor:pointer;color:#c9d6ea}
.toggle:hover{background:rgba(255,255,255,.14);color:#fff}
/* Stripping the page back to the Japanese is only a thing you want while
   speaking, so the button lives in that view. */
body[data-view="desk"] #scriptonly{display:none}

/* Two views, one page. Big target, live count, and the key that switches it. */
.views{display:flex;gap:3px;padding:3px;background:rgba(255,255,255,.08);
border:1px solid rgba(255,255,255,.10);border-radius:10px}
.views button{display:flex;align-items:center;gap:7px;font:inherit;padding:5px 11px;
border:0;border-radius:8px;background:none;color:#a9b8d2;cursor:pointer;
text-align:left;white-space:nowrap}
.views button:hover{color:#fff;background:rgba(255,255,255,.07)}
.views button[aria-selected="true"]{background:#fff;color:#0d1524;
box-shadow:0 1px 3px rgba(9,14,26,.4)}
.views .lbl{font-size:13px;font-weight:650;letter-spacing:-.005em}
/* The room this script is for, alongside the label rather than under it, so the
   whole bar stays one line tall. */
.views .sub{font-size:11.5px;font-weight:550;opacity:.62;padding-left:7px;
border-left:1px solid currentColor}
.views .k{flex:none;font:700 10px/14px inherit;min-width:14px;text-align:center;
border-radius:4px;background:rgba(255,255,255,.13);color:#c2cee3}
.views button[aria-selected="true"] .k{background:#eef1f6;color:#6b7789}
.views .badge{flex:none;min-width:18px;padding:0 5px;border-radius:9px;
background:#e0483b;color:#fff;font:700 10.5px/18px inherit;text-align:center}
.views button[aria-selected="true"] .badge{background:var(--red);color:#fff}
.views .badge.quiet{background:rgba(255,255,255,.16);color:#dbe4f2}
body[data-view="desk"] #view-standup,body[data-view="standup"] #view-desk{display:none}

/* Cards. Every panel on both views is the same object. */
.tk,.st-tk,.track,.panel,.st-run,.st-empty,.gaps{background:var(--card);
border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
.headline,.st-lead{background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--accent);border-radius:13px;padding:16px 20px;
margin-bottom:20px;box-shadow:var(--shadow)}
.headline p,.st-lead p{margin:0;font-size:17px;line-height:1.5;font-weight:550;
letter-spacing:-.01em}
h2.tickets-h{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;
color:var(--soft);margin:28px 0 11px;font-weight:700}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;
border-radius:20px;border:1px solid;letter-spacing:.01em;white-space:nowrap}
.btn{font-size:12.5px;text-decoration:none;color:var(--accent);
border:1px solid var(--line);background:#fff;padding:4px 10px;border-radius:7px;
white-space:nowrap;font-weight:550}
.btn:hover{border-color:var(--accent-line);background:var(--accent-bg)}
.tag{display:inline-block;font-size:12.5px;font-weight:700;padding:2px 9px;
border-radius:6px;background:var(--accent-bg);color:var(--accent-ink);
margin-right:8px;vertical-align:2px;letter-spacing:0}
.est{color:var(--green);font-weight:600}

/* Sections inside a card, and the fold-away ones. */
.sub{padding:15px 0;border-bottom:1px solid var(--hair)}
.tk>*:last-child,.st-tk>*:last-child{border-bottom:0;padding-bottom:0}
.sub h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;
color:var(--soft);margin:0 0 8px;font-weight:700;display:inline-block}
details>summary{cursor:pointer;list-style:none;padding:15px 0 8px}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"\\25B8";color:var(--soft);font-size:10px;
margin-right:7px;display:inline-block;transition:transform .15s}
details[open]>summary::before{transform:rotate(90deg)}
details.sub{padding-top:0}
.status,.st-stands{margin:0;font-size:15px;color:var(--ink)}
.matters{margin:10px 0 0;padding:9px 13px;background:var(--accent-bg);
border:1px solid var(--accent-line);border-radius:8px;font-size:14px;
color:var(--accent-ink)}
.cons-list{margin:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.cons-row{display:flex;background:#fff;align-items:baseline}
.cons-row dt{flex:none;width:152px;padding:9px 13px;font-size:11.5px;
font-weight:700;color:var(--soft);background:#fbfcfe;text-transform:uppercase;
letter-spacing:.04em}
.cons-row dd{flex:1;min-width:0;margin:0;padding:9px 13px;font-size:14px}
.cons-row:last-child dd{color:var(--amber);font-weight:550}

/* The spoken script. Smaller than it was: this is read at speed, and 19px with
   a reading above it is already taller than a normal line. */
.jp-block{margin-bottom:16px}
.jp-heading{display:flex;align-items:baseline;gap:10px;margin-bottom:8px;
padding-bottom:5px;border-bottom:1px solid var(--accent-line)}
.jp-h-ja{font-size:15px;font-weight:700;color:var(--accent-ink)}
.jp-h-en{font-size:11.5px;color:var(--soft);text-transform:uppercase;
letter-spacing:.06em;font-weight:600}
.copy{margin-left:auto;font:600 11px/1 inherit;color:var(--soft);background:#fff;
border:1px solid var(--line);border-radius:6px;padding:4px 8px;cursor:pointer}
.copy:hover{color:var(--accent);border-color:var(--accent-line)}
.jp-line{margin-bottom:10px;padding-left:12px;border-left:3px solid var(--accent-line)}
.jp{margin:0;font-size:19px;line-height:1.95;letter-spacing:.005em}
ruby rt{font-size:.46em;color:var(--accent);font-weight:600;letter-spacing:0}
.en{margin:2px 0 0;font-size:13px;color:var(--soft);line-height:1.45}
.qlist{list-style:none;margin:0;padding:0}
.q{padding:9px 0;border-bottom:1px dashed var(--line)}
.q:last-child{border-bottom:0}
.q-en{font-weight:600;font-size:14.5px;display:flex;gap:8px;align-items:center;
flex-wrap:wrap}
.q-ja{font-size:17px;line-height:1.9;margin-top:3px;color:var(--mut)}

/* Drafts. Monospace-free, but plain enough that pasting is the obvious move. */
.draft{border:1px solid var(--line);border-radius:10px;margin-bottom:11px;
overflow:hidden}
.draft-head{display:flex;gap:9px;align-items:center;padding:8px 12px;
background:#fbfcfe;border-bottom:1px solid var(--line);font-size:12.5px;
color:var(--mut);font-weight:550}
.draft-body{padding:13px;white-space:pre-wrap;font-size:14.5px;line-height:1.6}
.draft-body.ja{font-size:16px;line-height:1.95}
.draft-en{margin:0;padding:0 13px 13px;font-size:13px;color:var(--soft)}
.warn{background:var(--amber-bg);border:1px solid var(--amber-line);
border-radius:10px;padding:12px 15px;margin-top:15px}
.warn h3{color:var(--amber)}
.warn ul{margin:6px 0 0;padding-left:18px;font-size:14px;color:var(--amber-ink)}
.empty{color:var(--soft);font-style:italic;margin:0;font-size:14.5px}
.gaps{padding:16px 20px;margin-top:22px}
.gaps h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.09em;
color:var(--soft);margin:0;display:inline-block;font-weight:700}
.gaps ul{margin:8px 0 0;padding-left:18px}
.foot{text-align:center;color:var(--soft);font-size:12px;margin-top:28px}
.keys{color:#7b8cab;font-size:11px}

/* Script-only: everything that is not Japanese gets out of the way. */
body.script-only .sub:not(.script),body.script-only .st-head .pos,
body.script-only details,body.script-only .st-brief,body.script-only .st-raise,
body.script-only .st-warn,body.script-only .st-cons,body.script-only .st-land,
body.script-only .st-run,body.script-only .sess{display:none}
body.script-only .jp{font-size:23px;line-height:2.05}
body.script-only .en{font-size:13.5px}
body.script-only .st-tk{padding:18px 22px}
.err{background:var(--red-bg);border:1px solid var(--red-line);border-radius:12px;
padding:22px;color:var(--red)}
.err pre{white-space:pre-wrap;font-size:13px;background:#fff;padding:13px;
border-radius:8px;margin:13px 0 0;color:var(--ink)}
@media print{header.top,.btn,.copy,.toggle,.views{display:none}
body{background:#fff}.tk,.st-tk{break-inside:avoid;border-color:#ccc;box-shadow:none}
details{display:block}details>summary{display:none}}
"""

JS = """
(function(){
  var el=document.getElementById('countdown');
  var target=new Date(document.body.dataset.meeting);
  var what=(document.body.dataset.meetingLabel||'standup').toLowerCase();
  function tick(){
    var d=Math.floor((target-new Date())/1000);
    if(d<=0){el.textContent=what+' started';el.classList.add('soon');return}
    var h=Math.floor(d/3600),m=Math.floor(d%3600/60);
    el.textContent=(h?h+'h ':'')+m+'m to '+what;
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
  var where={};
  function show(view,remember){
    if(!tabs.length)return;
    var from=document.body.dataset.view;
    if(from&&from!==view)where[from]=window.scrollY;
    document.body.dataset.view=view;
    tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.view===view)});
    if(remember!==false)try{sessionStorage.setItem('desk-view',view)}catch(e){}
    // Coming back to a view lands where you left it. Arriving for the first
    // time starts at the top, not halfway down because the other view was.
    if(from&&from!==view&&!location.hash)window.scrollTo(0,where[view]||0);
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
