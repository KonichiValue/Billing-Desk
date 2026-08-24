#!/usr/bin/env python3
"""The standup view: the same tickets as the desk, in the order the meeting
walks them, with the words to say out loud.

This is not a second page. It renders into the same HTML file as the desk and
reads the same `state/board.json`, because the two views answering to different
files is exactly how a script ends up describing a status that has moved on.

The desk answers "what do I do". This answers "what do I say at 10:30", and
every ticket carries a link back to its items on the desk.
"""

from __future__ import annotations

from render import (
    esc,
    furi,
    item_state as state_of,
    link_btn,
    pill,
    plain,
    render_consequences,
    render_script,
)

EXTRA_CSS = """
.st-lead{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
border-radius:12px;padding:16px 20px;margin-bottom:20px}
.st-lead p{margin:0;font-size:18px;line-height:1.45;font-weight:550;letter-spacing:-.01em}
.st-run{list-style:none;margin:0 0 24px;padding:0;background:var(--card);
border:1px solid var(--line);border-radius:12px;overflow:hidden}
.st-run li{display:flex;gap:12px;align-items:center;padding:11px 16px;
border-bottom:1px solid var(--line)}
.st-run li:last-child{border-bottom:0}
.st-run .n{flex:none;width:24px;height:24px;border-radius:7px;background:var(--accent-bg);
color:var(--accent);display:grid;place-items:center;font-size:12.5px;font-weight:700}
.st-run a{flex:1;min-width:0;text-decoration:none;color:inherit;font-weight:550;
font-size:14.5px}
.st-run a:hover{color:var(--accent)}
.st-run .say{flex:none;font-size:12.5px;color:var(--soft)}
.st-tk{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:22px;margin-bottom:20px;scroll-margin-top:80px}
.st-head{padding-bottom:15px;border-bottom:1px solid var(--line)}
.st-head h2{margin:0;font-size:19px;letter-spacing:-.015em;line-height:1.35}
.st-head .ja{margin:5px 0 0;font-size:15px;color:var(--mut)}
.st-head .pos{margin:9px 0 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.st-brief{padding:16px 0;border-bottom:1px solid var(--line)}
.st-brief ul{margin:0;padding-left:19px}
.st-brief li{margin-bottom:5px}
.st-brief .matters{margin:11px 0 0;padding:9px 13px;background:var(--accent-bg);
border-radius:8px;font-size:14.5px;color:#194185}
.st-stands{margin:0;font-size:15px}
.st-raise{margin:14px 0 0;padding:0;list-style:none}
.st-raise li{display:flex;gap:10px;align-items:baseline;padding:9px 13px;
background:#fef3f2;border:1px solid #fecdca;border-radius:9px;margin-bottom:7px}
.st-raise .n{flex:none;font-size:11.5px;font-weight:700;color:#b42318;
text-transform:uppercase;letter-spacing:.05em}
.st-raise .t{flex:1;min-width:0;font-size:14.5px;color:#912018}
.st-raise a{font-size:12.5px;color:var(--accent);text-decoration:none;white-space:nowrap}
.st-warn{margin-top:16px;background:#fffaeb;border:1px solid #fedf89;border-radius:10px;
padding:13px 16px}
.st-warn h3{color:#b54708;font-size:12.5px;text-transform:uppercase;
letter-spacing:.07em;margin:0 0 7px;font-weight:650}
.st-warn ul{margin:0;padding-left:19px;font-size:14.5px;color:#93370d}
.st-secret{margin:9px 0 0;font-size:12.5px;color:#b54708}
.st-none{margin:0 0 13px;padding:9px 13px;background:#ecfdf3;border:1px solid #abefc6;
border-radius:8px;color:#067647;font-size:14.5px;font-weight:550}
.st-empty{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:34px 30px;text-align:center}
.st-empty h2{margin:0 0 8px;font-size:19px;letter-spacing:-.015em}
.st-empty p{margin:0 auto 18px;max-width:460px;color:var(--mut);font-size:15px}
.st-stale{margin-bottom:18px;padding:11px 16px;background:#fffaeb;
border:1px solid #fedf89;border-radius:10px;font-size:14px;color:#93370d}
"""


def anchor(ident: str) -> str:
    """Standup anchors mirror the desk's, with an s- prefix, so a ticket can
    link to its own other half."""
    return "s-" + ident.removeprefix("t-")


def raise_rows(t: dict, desk_id: str) -> str:
    """Items the board says to raise in the meeting, pulled straight from the
    desk so nothing has to be written twice."""
    rows = []
    for item in t.get("items", []):
        if not item.get("at_standup"):
            continue
        st = state_of(item)
        if st["closed"]:
            continue
        rows.append(
            f"""
        <li>
          <span class="n">{esc(item.get("id", "-"))}</span>
          <span class="t">{esc(item.get("title"))}
            {f'<span class="st-secret">{esc(item.get("at_standup_note"))}</span>' if item.get("at_standup_note") else ""}</span>
          <a href="#{esc(desk_id)}" data-goto="desk">on the desk</a>
        </li>"""
        )
    if not rows:
        return ""
    return f'<ul class="st-raise">{"".join(rows)}</ul>'


def render_ticket(t: dict, ident: str, desk_id: str) -> str:
    prep = t.get("prep") or {}
    issue = "".join(f"<li>{esc(b)}</li>" for b in prep.get("issue", []))
    unknowns = prep.get("unknowns", [])
    warn = ""
    if unknowns:
        rows = "".join(f"<li>{esc(u)}</li>" for u in unknowns)
        warn = f"""
      <section class="st-warn">
        <h3>Check before you speak</h3>
        <ul>{rows}</ul>
      </section>"""

    internal = t.get("internal_ticket") or {}
    secret = (
        f'<p class="st-secret">Never to TG: {esc(internal.get("name"))}. '
        "No dates, no sizing, no queue position.</p>"
        if internal.get("name")
        else ""
    )

    open_items = [i for i in t.get("items", []) if not state_of(i)["closed"]]
    desk_link = (
        f'<a href="#{esc(desk_id)}" data-goto="desk">'
        f'{len(open_items)} open item{"s" if len(open_items) != 1 else ""} on the desk</a>'
        if open_items
        else ""
    )

    return f"""
    <article class="st-tk" id="{esc(ident)}">
      <header class="st-head">
        <h2><span class="ix-tag">{esc(t.get("ref"))}</span> {esc(t.get("title_en"))}</h2>
        <p class="ja">{esc(t.get("title_ja"))}</p>
        <p class="pos">
          {pill("Nothing to ask", "green") if prep.get("tg_ask_needed") is False else pill("Ask on the table", "amber")}
          {f'<span>{esc(prep.get("board_position"))}</span>' if prep.get("board_position") else ""}
          {f'<span class="est">{esc(prep.get("estimate"))}</span>' if prep.get("estimate") else ""}
          {desk_link}
          {link_btn(t.get("asana_url", ""), "Asana")}
        </p>
      </header>

      {f'''<section class="st-brief">
        <h3>The issue in 20 seconds</h3>
        <ul>{issue}</ul>
        {f'<p class="matters">{esc(prep.get("why_it_matters"))}</p>' if prep.get("why_it_matters") else ""}
      </section>''' if issue else ""}

      <section class="sub">
        <h3>Where it stands</h3>
        <p class="st-stands">{esc(t.get("where_it_stands"))}</p>
        {raise_rows(t, desk_id)}
      </section>

      <section class="st-cons">{render_consequences(prep.get("consequences", {}))}</section>

      <section class="sub script">
        <h3>What I say</h3>
        {'<p class="st-none">Status only. Nothing needed from TG.</p>' if prep.get("tg_ask_needed") is False else ""}
        {render_script(prep.get("script", []))}
      </section>

      {render_questions(prep.get("open_questions", []))}
      {warn}
      {secret}
    </article>"""


def render_questions(questions: list[dict]) -> str:
    """Kept here rather than shared: at standup a question is a thing he asks
    out loud, so it renders with the Japanese underneath."""
    if not questions:
        return ""
    rows = []
    for q in questions:
        who = q.get("who", "TG")
        raw = plain(q.get("ja_ruby", ""))
        rows.append(
            f"""
        <li class="q">
          <div class="q-en">{esc(q.get("en"))} {pill(who, "amber" if who == "TG" else "grey")}
            {f'<button class="copy" data-copy="{esc(raw)}">copy</button>' if raw else ""}</div>
          <div class="q-ja">{furi(q.get("ja_ruby", ""))}</div>
        </li>"""
        )
    return f"""
      <section class="sub">
        <h3>Questions I need answered</h3>
        <ul class="qlist">{"".join(rows)}</ul>
      </section>"""


def running_order(tickets: list[dict], ids: dict[str, str]) -> str:
    rows = []
    for n, t in enumerate(tickets, 1):
        prep = t.get("prep") or {}
        blocks = len(prep.get("script", []))
        note = (
            "status only" if prep.get("tg_ask_needed") is False
            else f"{blocks} block{'s' if blocks != 1 else ''} to say" if blocks
            else "no script yet"
        )
        rows.append(
            f"""
      <li>
        <span class="n">{prep.get("order", n)}</span>
        <a href="#{esc(ids[t.get("ref", "")])}">{esc(t.get("ref"))} &middot; {esc(t.get("title_en"))}</a>
        <span class="say">{esc(note)}</span>
      </li>"""
        )
    return f'<ul class="st-run">{"".join(rows)}</ul>'


def render(board: dict, desk_ids: dict[str, str], built: str, stale: bool) -> str:
    """The standup half of the page. `built` is empty when there is no script
    yet, which is the normal state until Rei presses the button."""
    tickets = [t for t in board.get("tickets", []) if (t.get("prep") or {}).get("script")]
    if not tickets:
        return """
  <div class="st-empty">
    <h2>No script for today yet</h2>
    <p>Press <strong>Build script</strong> and it reads every open ticket, the
    threads behind them and yesterday's decisions, then writes what you say at
    10:30. Takes a couple of minutes.</p>
  </div>"""

    tickets.sort(key=lambda t: (t.get("prep") or {}).get("order", 99))
    ids = {t.get("ref", ""): anchor(desk_ids.get(t.get("ref", ""), "")) for t in tickets}
    cards = "".join(
        render_ticket(t, ids[t.get("ref", "")], desk_ids.get(t.get("ref", ""), ""))
        for t in tickets
    )
    standup = board.get("standup") or {}
    stale_note = (
        '<div class="st-stale">This script was written before the last refresh, '
        "so it may not know the newest replies. Rebuild it if that matters.</div>"
        if stale
        else ""
    )
    lead = standup.get("headline") or board.get("headline") or ""
    return f"""
  {stale_note}
  {f'<div class="st-lead"><p>{esc(lead)}</p></div>' if lead else ""}
  <h2 class="tickets-h">Running order, {len(tickets)} of yours on the board</h2>
  {running_order(tickets, ids)}
  {cards}
  <p class="foot">Script written {esc(built)}. Press 1 for the desk, 2 for the
  standup, s to strip everything but the Japanese.</p>"""
