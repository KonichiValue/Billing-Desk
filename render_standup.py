#!/usr/bin/env python3
"""The speaking view: the same tickets as the desk, in the order the meeting
walks them, with the words to say out loud.

This is not a second page. It renders into the same HTML file as the desk and
reads the same `state/board.json`, because the two views answering to different
files is exactly how a script ends up describing a status that has moved on.

The desk answers "what do I do". This answers "what do I say", and every ticket
carries a link back to its items on the desk.

Most days that means the 10:30 standup. Some days it is an onsite, which is the
same tickets with a day in the room instead of fifteen minutes, so the session
banner, the running order and each card carry the extra weight an onsite needs:
what has to be decided before everyone goes home, and what to say when TG push
back.
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
    script_meta,
    script_session,
    section,
    when_words,
)

EXTRA_CSS = """
.st-run{list-style:none;margin:0 0 22px;padding:0;overflow:hidden}
.st-run li{display:flex;gap:12px;align-items:center;padding:10px 16px;
border-bottom:1px solid var(--hair)}
.st-run li:last-child{border-bottom:0}
.st-run .n{flex:none;width:23px;height:23px;border-radius:7px;
background:var(--accent-bg);color:var(--accent-ink);display:grid;place-items:center;
font-size:12px;font-weight:700}
.st-run a{flex:1;min-width:0;text-decoration:none;color:inherit;font-weight:550;
font-size:14.5px}
.st-run a:hover{color:var(--accent)}
.st-run .say{flex:none;font-size:12px;color:var(--soft)}
.st-tk{padding:20px 22px;margin-bottom:18px;scroll-margin-top:78px}
.st-head{padding-bottom:14px;border-bottom:1px solid var(--hair)}
.st-head h2{margin:0;font-size:17.5px;letter-spacing:-.015em;line-height:1.35;
font-weight:650}
.st-head .ja{margin:4px 0 0;font-size:14px;color:var(--mut)}
.st-head .pos{margin:9px 0 0;display:flex;gap:9px;align-items:center;flex-wrap:wrap;
font-size:12px;color:var(--soft)}
.st-head .pos a{color:var(--accent);text-decoration:none;font-weight:550}
.st-brief{padding:15px 0;border-bottom:1px solid var(--hair)}
.st-brief ul{margin:0;padding-left:18px}
.st-brief li{margin-bottom:4px;font-size:14.5px}
.st-stands{margin:0;font-size:15px}
.st-raise{margin:13px 0 0;padding:0;list-style:none}
.st-raise li{display:flex;gap:10px;align-items:baseline;padding:9px 12px;
background:var(--red-bg);border:1px solid var(--red-line);border-radius:9px;
margin-bottom:6px}
.st-raise .n{flex:none;font-size:11px;font-weight:700;color:var(--red);
text-transform:uppercase;letter-spacing:.05em}
.st-raise .t{flex:1;min-width:0;font-size:14px;color:#912018}
.st-raise a{font-size:12px;color:var(--accent);text-decoration:none;white-space:nowrap}
.st-warn{margin-top:15px;background:var(--amber-bg);border:1px solid var(--amber-line);
border-radius:10px;padding:12px 15px}
.st-warn h3{color:var(--amber);font-size:11.5px;text-transform:uppercase;
letter-spacing:.08em;margin:0 0 6px;font-weight:700}
.st-warn ul{margin:0;padding-left:18px;font-size:14px;color:var(--amber-ink)}
.st-secret{margin:9px 0 0;font-size:12px;color:var(--amber)}
.st-none{margin:0 0 12px;padding:9px 13px;background:var(--green-bg);
border:1px solid var(--green-line);border-radius:8px;color:var(--green);
font-size:14px;font-weight:550}
.st-empty{padding:34px 30px;text-align:center}
.st-empty h2{margin:0 0 8px;font-size:18px;letter-spacing:-.015em}
.st-empty p{margin:0 auto;max-width:470px;color:var(--mut);font-size:14.5px}
.st-stale{margin-bottom:16px;padding:11px 15px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:10px;font-size:13.5px;
color:var(--amber-ink)}

/* The session banner. An onsite is not a longer standup, so it does not look
   like one: the whole banner leans on the kind of session it is. */
.sess{background:var(--card);border:1px solid var(--line);border-radius:14px;
box-shadow:var(--shadow);padding:15px 20px;margin-bottom:18px;
border-left:4px solid var(--accent)}
.sess-top{display:flex;gap:11px;align-items:baseline;flex-wrap:wrap}
.sess-kind{font:700 10.5px/1 inherit;text-transform:uppercase;letter-spacing:.1em;
color:var(--accent);background:var(--accent-bg);border:1px solid var(--accent-line);
padding:5px 9px;border-radius:6px}
.sess-top h2{margin:0;font-size:17px;letter-spacing:-.015em;font-weight:650}
.sess-when{font-size:13px;color:var(--mut);font-weight:600}
.sess-where{font-size:12.5px;color:var(--soft)}
.sess-focus{margin:9px 0 0;font-size:14.5px;color:var(--mut)}
.sess.big{border-left-width:5px}
.sess.big .sess-top h2{font-size:19px}
.agenda{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:1px;
background:var(--line);border:1px solid var(--line);border-radius:10px;
overflow:hidden}
.agenda li{background:#fff;padding:9px 13px;display:flex;gap:12px;
align-items:baseline;flex-wrap:wrap}
.agenda .ag-t{flex:1;min-width:180px;font-size:14px;font-weight:600}
.agenda .ag-w{flex:2;min-width:220px;font-size:13.5px;color:var(--mut)}
.agenda .ag-o{flex:none;font-size:11.5px;font-weight:700;color:var(--accent-ink);
background:var(--accent-bg);padding:2px 8px;border-radius:20px}
.sess-bring{margin:12px 0 0;padding:10px 13px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:9px;font-size:13.5px;
color:var(--amber-ink)}
.sess-bring b{display:block;font-size:11px;text-transform:uppercase;
letter-spacing:.07em;color:var(--amber);margin-bottom:3px}

/* What has to be settled before people leave the room, and the answer ready
   for the pushback that stops it being settled. */
.st-land{list-style:none;margin:0;padding:0}
.st-land li{padding:10px 13px;border:1px solid var(--amber-line);
background:var(--amber-bg);border-radius:9px;margin-bottom:7px}
.st-land .need{font-size:14.5px;font-weight:600;color:var(--amber-ink)}
.st-land .why{display:block;font-size:13.5px;color:var(--mut);margin-top:3px}
.st-land .fall{display:block;font-size:13px;color:var(--amber);margin-top:5px;
font-weight:550}
.st-push{list-style:none;margin:0;padding:0}
.st-push li{padding:11px 0;border-bottom:1px dashed var(--line)}
.st-push li:last-child{border-bottom:0}
.st-push .they{font-size:13.5px;color:var(--mut);padding-left:11px;
border-left:3px solid var(--line);font-style:italic}
.st-push .mine{margin-top:7px;padding-left:11px;border-left:3px solid var(--accent-line)}
.st-push .mine .jp{font-size:18px}
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


def render_session(sess: dict, big: bool) -> str:
    """What Rei is walking into, and for an onsite, the shape of the day."""
    if not sess.get("date") and not sess.get("focus"):
        return ""
    agenda = "".join(
        f"""
      <li>
        <span class="ag-t">{esc(row.get("topic"))}</span>
        <span class="ag-w">{esc(row.get("why"))}</span>
        {f'<span class="ag-o">{esc(row.get("owner"))}</span>' if row.get("owner") else ""}
      </li>"""
        for row in sess.get("agenda", [])
    )
    bring = sess.get("bring", [])
    bring_block = ""
    if bring:
        rows = "".join(f"<li>{esc(b)}</li>" for b in bring)
        bring_block = (
            f'<div class="sess-bring"><b>Have this ready</b>'
            f'<ul style="margin:0;padding-left:17px">{rows}</ul></div>'
        )
    # The kind chip only earns its space when the session is not the usual
    # standup, which is the whole point of having it.
    chip = (
        f'<span class="sess-kind">{esc(sess.get("kind"))}</span>'
        if sess.get("kind") != "standup"
        else ""
    )
    return f"""
  <section class="sess {"big" if big else ""}">
    <div class="sess-top">
      {chip}
      <h2>{esc(sess.get("title") or sess.get("name"))}</h2>
      <span class="sess-when">{esc(when_words(sess.get("date", ""), sess.get("at", "")))}</span>
      {f'<span class="sess-where">{esc(sess.get("place"))}</span>' if sess.get("place") else ""}
    </div>
    {f'<p class="sess-focus">{esc(sess.get("focus"))}</p>' if sess.get("focus") else ""}
    {f'<ul class="agenda">{agenda}</ul>' if agenda else ""}
    {bring_block}
  </section>"""


def render_land(rows: list[dict]) -> str:
    """Decisions that have to be settled in the room, not after it."""
    if not rows:
        return ""
    out = "".join(
        f"""
      <li>
        <span class="need">{esc(r.get("need"))}</span>
        {f'<span class="why">{esc(r.get("why"))}</span>' if r.get("why") else ""}
        {f'<span class="fall">If they will not settle it: {esc(r.get("fallback"))}</span>' if r.get("fallback") else ""}
      </li>"""
        for r in rows
    )
    return section(
        "Settle this before you leave the room",
        f'<ul class="st-land">{out}</ul>',
        role="warn",
        count=len(rows),
        hint="decide it in the room",
    )


def render_pushback(rows: list[dict]) -> str:
    """The objection you can see coming, and the sentence that answers it."""
    if not rows:
        return ""
    out = []
    for r in rows:
        raw = plain(r.get("say_ja", ""))
        out.append(
            f"""
        <li>
          <div class="they">{esc(r.get("they_say"))}</div>
          <div class="mine">
            <p class="jp">{furi(r.get("say_ja", ""))}</p>
            <p class="en">{esc(r.get("say_en"))}</p>
          </div>
          {f'<button class="copy" data-copy="{esc(raw)}">copy</button>' if raw else ""}
        </li>"""
        )
    return section(
        "If they push back",
        f'<ul class="st-push">{"".join(out)}</ul>',
        role="ref",
        count=len(rows),
        fold=True,
    )


def render_ticket(t: dict, ident: str, desk_id: str) -> str:
    prep = t.get("prep") or {}
    # A ticket carrying a decision into the room is not a ticket with nothing to
    # ask, whatever the flag says.
    no_ask = prep.get("tg_ask_needed") is False and not prep.get("decisions")
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
        <h2><span class="tag">{esc(t.get("ref"))}</span> {esc(t.get("title_en"))}</h2>
        <p class="ja">{esc(t.get("title_ja"))}</p>
        <p class="pos">
          {pill("Nothing to ask", "green") if no_ask else pill("Ask on the table", "amber")}
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

      {section("Where it stands",
               f'<p class="st-stands">{esc(t.get("where_it_stands"))}</p>'
               f'{raise_rows(t, desk_id)}',
               role="log", hint="from the desk")}

      <section class="st-cons">{render_consequences(prep.get("consequences", {}))}</section>

      {render_land(prep.get("decisions", []))}

      <section class="sub say script">
        <h3>What I say out loud</h3>
        {'<p class="st-none">Status only. Nothing needed from TG.</p>' if no_ask else ""}
        {render_script(prep.get("script", []))}
      </section>

      {render_pushback(prep.get("pushback", []))}
      {render_questions(
          prep.get("open_questions", []),
          any(b.get("heading") == "質問" for b in prep.get("script", [])),
      )}
      {warn}
      {secret}
    </article>"""


def render_questions(questions: list[dict], spoken: bool) -> str:
    """The asks that are not already in the script.

    When the script has a 質問 block, the questions for TG are in it, and
    printing them again underneath just makes the card longer than the meeting.
    What survives is anything aimed elsewhere: a colleague, or himself.
    """
    if spoken:
        questions = [q for q in questions if q.get("who") not in ("TG", "")]
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
    return section(
        "Also need answering, off the script",
        f'<ul class="qlist">{"".join(rows)}</ul>',
        role="warn",
        count=len(rows),
    )


def running_order(tickets: list[dict], ids: dict[str, str]) -> str:
    rows = []
    for n, t in enumerate(tickets, 1):
        prep = t.get("prep") or {}
        blocks = len(prep.get("script", []))
        decisions = len(prep.get("decisions", []))
        note = (
            f"{decisions} to settle" if decisions
            else "status only" if prep.get("tg_ask_needed") is False
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
    """The speaking half of the page. `built` is empty when there is no script
    yet, which is the normal state until Rei presses the button."""
    sess = script_session(board)
    onsite = sess.get("kind") != "standup"
    banner = render_session(sess, onsite)

    tickets = [t for t in board.get("tickets", []) if (t.get("prep") or {}).get("script")]
    if not tickets:
        # The empty state has to say what pressing the button is for, and that
        # depends entirely on whether the next session is 15 minutes or a day.
        when = when_words(sess.get("date", ""), sess.get("at", ""))
        for_what = f"for {sess.get('name', 'the standup').lower()}" + (
            f" {when}" if when else ""
        )
        extra = (
            " An onsite gets the longer treatment: what has to be decided in the "
            "room, and the answer ready for the pushback."
            if onsite
            else ""
        )
        return f"""
  {banner}
  <div class="st-empty">
    <h2>No script yet {esc(for_what)}</h2>
    <p>Press <strong>Build script</strong> and it reads every open ticket, the
    threads behind them and the last meeting's decisions, then writes what you
    say.{esc(extra)} Takes a couple of minutes.</p>
  </div>"""

    tickets.sort(key=lambda t: (t.get("prep") or {}).get("order", 99))
    ids = {t.get("ref", ""): anchor(desk_ids.get(t.get("ref", ""), "")) for t in tickets}
    cards = "".join(
        render_ticket(t, ids[t.get("ref", "")], desk_ids.get(t.get("ref", ""), ""))
        for t in tickets
    )
    stale_note = (
        '<div class="st-stale">This script was written before the last refresh, '
        "so it may not know the newest replies. Rebuild it if that matters.</div>"
        if stale
        else ""
    )
    lead = script_meta(board).get("headline") or board.get("headline") or ""
    order_h = (
        f"Running order, {len(tickets)} of yours"
        + (" on the board" if not onsite else " to take into the room")
    )
    return f"""
  {stale_note}
  {banner}
  {f'<div class="st-lead"><p>{esc(lead)}</p></div>' if lead else ""}
  <h2 class="tickets-h">{esc(order_h)}</h2>
  {running_order(tickets, ids)}
  {cards}
  <p class="foot">Script written {esc(built)}. <kbd>1</kbd> your work,
  <kbd>2</kbd> what you say, <kbd>s</kbd> Japanese only, <kbd>/</kbd> find
  anything, <kbd>?</kbd> how this works.</p>"""
