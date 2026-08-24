#!/usr/bin/env python3
"""Render the post-standup JSON into a single self-contained HTML page.

Usage:
    python3 render_post.py output/post-2026-08-24.json output/post-2026-08-24.html
    python3 render_post.py --error "message" output/post-2026-08-24.html
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from render import CSS, JS, esc, furi, link_btn, pill, plain

URGENCY = {
    "today": ("Today", "red"),
    "this-week": ("This week", "amber"),
    "monitor": ("Monitor", "grey"),
}

EXTRA_CSS = """
.todo-list{list-style:none;margin:0;padding:0}
.todo{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:16px 18px;margin-bottom:12px;display:flex;gap:14px}
.todo.commit{border-left:4px solid #b42318}
.todo-rank{width:28px;height:28px;flex:none;border-radius:8px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:13.5px;font-weight:650}
.todo-main{flex:1;min-width:0}
.todo-top{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.todo-title{font-size:16.5px;font-weight:600;letter-spacing:-.01em}
.todo-detail{margin:9px 0 0;padding-left:19px}
.todo-detail li{margin-bottom:4px;font-size:14.5px;color:var(--mut)}
.todo-meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;font-size:13px;
color:var(--soft);align-items:center}
.todo-meta .ref{font-weight:650;color:var(--accent)}
.todo-meta .mins{margin-left:auto;font-variant-numeric:tabular-nums}
.commit-note{margin:9px 0 0;padding:7px 12px;background:#fef3f2;border:1px solid #fecdca;
border-radius:8px;font-size:13.5px;color:#b42318;font-weight:550}
.blocked{margin:9px 0 0;padding:7px 12px;background:#fffaeb;border:1px solid #fedf89;
border-radius:8px;font-size:13.5px;color:#b54708}
.quote{margin:11px 0 0;padding-left:12px;border-left:3px solid var(--line);
font-size:13.5px;color:var(--soft);font-style:italic}
.diff{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:0;overflow:hidden;margin-bottom:12px}
.diff-head{padding:11px 16px;background:#fcfcfc;border-bottom:1px solid var(--line);
display:flex;gap:10px;align-items:center;font-size:13px}
.diff-body{padding:14px 16px}
.diff-line{display:flex;gap:11px;margin-bottom:7px;font-size:14.5px}
.diff-line .k{flex:none;width:56px;font-size:12px;font-weight:650;
text-transform:uppercase;letter-spacing:.05em;padding-top:3px}
.diff-line.was .k{color:var(--soft)}
.diff-line.was .v{color:var(--soft);text-decoration:line-through;
text-decoration-color:#d0d5dd}
.diff-line.now .k{color:#067647}
.so-what{margin:11px 0 0;padding:9px 13px;background:var(--accent-bg);
border-radius:8px;font-size:14.5px;color:#194185;font-weight:550}
.wait{display:flex;gap:14px;padding:13px 16px;border-bottom:1px solid var(--line);
align-items:flex-start}
.wait:last-child{border-bottom:0}
.wait-who{flex:none;width:150px;font-weight:600;font-size:14.5px}
.wait-main{flex:1;min-width:0;font-size:14.5px}
.wait-blocks{color:var(--soft);font-size:13px;margin-top:3px}
.wait-chase{flex:none;text-align:right;font-size:12.5px;color:#b54708;font-weight:600}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;
overflow:hidden}
.skip{background:#fffaeb;border:1px solid #fedf89;border-left:4px solid #b54708;
border-radius:12px;padding:16px 20px;margin-bottom:24px}
.skip strong{color:#b54708}
.watch-list{margin:0;padding-left:19px}
.watch-list li{margin-bottom:6px;font-size:14.5px;color:var(--mut)}
"""


def render_todo(item: dict) -> str:
    u_label, u_tone = URGENCY.get(item.get("urgency", "monitor"), URGENCY["monitor"])
    detail = "".join(f"<li>{esc(b)}</li>" for b in item.get("detail", []))
    mins = item.get("est_minutes")
    committed = item.get("committed_to")
    blocked = item.get("blocked_by")
    quote = item.get("source_quote")

    return f"""
    <li class="todo {"commit" if committed else ""}">
      <div class="todo-rank">{esc(item.get("rank", "-"))}</div>
      <div class="todo-main">
        <div class="todo-top">
          <span class="todo-title">{esc(item.get("title"))}</span>
          {pill(u_label, u_tone)}
        </div>
        {f'<ul class="todo-detail">{detail}</ul>' if detail else ""}
        {f'<p class="commit-note">You committed this to {esc(committed)}</p>' if committed else ""}
        {f'<p class="blocked">Blocked by: {esc(blocked)}</p>' if blocked else ""}
        <div class="todo-meta">
          {f'<span class="ref">{esc(item.get("ticket_ref"))}</span>' if item.get("ticket_ref") else ""}
          <span>{esc(item.get("where"))}</span>
          {link_btn(item.get("link", ""), "Open")}
          {f'<span class="mins">{esc(mins)} min</span>' if mins else ""}
        </div>
        {f'<p class="quote">{esc(quote)}</p>' if quote else ""}
      </div>
    </li>"""


def render_changed(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for row in rows:
        out.append(
            f"""
      <div class="diff">
        <div class="diff-head">
          <span class="ref" style="font-weight:650;color:var(--accent)">{esc(row.get("ticket_ref"))}</span>
          {link_btn(row.get("source_url", ""), "Source")}
        </div>
        <div class="diff-body">
          <div class="diff-line was"><span class="k">Was</span><span class="v">{esc(row.get("before"))}</span></div>
          <div class="diff-line now"><span class="k">Now</span><span class="v">{esc(row.get("after"))}</span></div>
          {f'<p class="so-what">{esc(row.get("so_what"))}</p>' if row.get("so_what") else ""}
        </div>
      </div>"""
        )
    return f"""
  <h2 class="board-h">What the meeting changed since this morning</h2>
  {"".join(out)}"""


def render_waiting(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for row in rows:
        due = row.get("due") or "not stated"
        chase = row.get("chase_on")
        out.append(
            f"""
      <li class="wait">
        <div class="wait-who">{esc(row.get("who"))}</div>
        <div class="wait-main">
          {esc(row.get("what"))}
          {f'<div class="wait-blocks">Blocks: {esc(row.get("blocks"))}</div>' if row.get("blocks") else ""}
          <div class="wait-blocks">Due {esc(due)}</div>
        </div>
        <div class="wait-chase">{f"chase {esc(chase)}" if chase else ""}</div>
      </li>"""
        )
    return f"""
  <h2 class="board-h">Waiting on other people</h2>
  <ul class="panel" style="list-style:none;margin:0;padding:0">{"".join(out)}</ul>"""


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
        rank = d.get("for_rank")
        out.append(
            f"""
      <div class="draft">
        <div class="draft-head">
          {f'<span style="font-weight:650">#{esc(rank)}</span>' if rank else ""}
          <span>{esc(d.get("target"))}</span>
          {link_btn(d.get("link", ""), "Go there")}
          <button class="copy" data-copy="{esc(plain(body))}">copy</button>
        </div>
        <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
        {trans}
      </div>"""
        )
    return f"""
  <h2 class="board-h">Drafts, ready to copy</h2>
  {"".join(out)}"""


def render_watch(rows: list[dict]) -> str:
    if not rows:
        return ""
    items = "".join(
        f'<li><strong>{esc(r.get("topic"))}</strong> &mdash; {esc(r.get("why"))} '
        f'{link_btn(r.get("source_url", ""), "Source")}</li>'
        for r in rows
    )
    return f"""
  <details class="gaps"><summary><h2>Not mine, but adjacent ({len(rows)})</h2></summary>
  <ul class="watch-list">{items}</ul></details>"""


def shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}{EXTRA_CSS}</style></head>
<body>
{body}
<script>{JS}</script></body></html>"""


def render(data: dict) -> str:
    meeting_date = data.get("meeting_date") or date.today().isoformat()
    try:
        pretty = datetime.strptime(meeting_date, "%Y-%m-%d").strftime("%A %-d %B")
    except ValueError:
        pretty = meeting_date

    todo = sorted(data.get("todo", []), key=lambda i: i.get("rank", 99))
    total = sum(i.get("est_minutes") or 0 for i in todo)

    if todo:
        items = "".join(render_todo(i) for i in todo)
        todo_block = f"""
  <h2 class="board-h">{len(todo)} thing{"s" if len(todo) != 1 else ""} to do, hardest consequence first
  {f"&middot; about {total} min" if total else ""}</h2>
  <ol class="todo-list">{items}</ol>"""
    else:
        todo_block = """
  <h2 class="board-h">To do</h2>
  <div class="panel" style="padding:18px 22px"><p class="empty">Nothing came out of
  this standup that needs action from you.</p></div>"""

    nxt = data.get("next_standup") or {}
    skip_block = ""
    if nxt.get("skipped"):
        when = nxt.get("date")
        skip_block = f"""
  <div class="skip"><strong>No standup on {esc(when)}.</strong>
  {esc(nxt.get("reason"))} The morning prep will not build that day.</div>"""

    gaps = data.get("gaps", [])
    gap_block = ""
    if gaps:
        gitems = "".join(f"<li>{esc(g)}</li>" for g in gaps)
        gap_block = f'<section class="gaps"><h2>Open gaps</h2><ul>{gitems}</ul></section>'

    notion = link_btn(data.get("notion_url", ""), "Meeting note")

    body = f"""
<header class="top"><div class="top-in">
  <h1>After the TG billing standup</h1>
  <span class="date">{esc(pretty)}</span>
  <span style="margin-left:auto">{notion}</span>
</div></header>
<div class="wrap">
  <div class="headline"><p>{esc(data.get("headline"))}</p></div>
  {skip_block}
  {todo_block}
  {render_changed(data.get("changed", []))}
  {render_waiting(data.get("waiting_on", []))}
  {render_drafts(data.get("drafts", []))}
  {render_watch(data.get("watch", []))}
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
    if not isinstance(data, dict) or "todo" not in data:
        print(f"{src} is missing the 'todo' key", file=sys.stderr)
        return 1

    dest.write_text(render(data), encoding="utf-8")
    print(f"wrote {dest} ({len(data.get('todo', []))} actions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
