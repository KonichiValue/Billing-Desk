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

from datetime import date, timedelta

from render import (
    ASKED,
    SPARK,
    ask_block,
    day_words,
    esc,
    furi,
    item_state as state_of,
    link_btn,
    opening,
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
.run-h{margin:16px 0 8px;font-size:12px;font-weight:750;display:flex;gap:9px;
align-items:center}
.run-h:before{content:"";width:3px;height:13px;border-radius:2px;
background:var(--accent-line)}
.run-h .q{font-weight:500;font-size:11.5px;color:var(--soft)}
.st-run{list-style:none;margin:0;padding:0;overflow:hidden;
border:1px solid var(--line);border-radius:11px;background:#fff}
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
/* Same card as the work view, so moving between the two costs nothing. */
.st-tk{padding:0 22px 20px;margin-bottom:20px;scroll-margin-top:96px;
border-top:4px solid var(--line);overflow:hidden}
.st-tk.mine{border-top-color:var(--accent)}
.st-tk.clear{border-top-color:var(--green)}
.st-head{margin:0 -22px;padding:14px 22px 15px;border-bottom:1px solid var(--line);
background:linear-gradient(180deg,var(--accent-bg),#fff)}
.st-tk.clear .st-head{background:linear-gradient(180deg,#fbfcfe,#fff)}
.st-head h2{margin:0;font-size:18.5px;letter-spacing:-.018em;line-height:1.3;
font-weight:700}
.st-head .ja{margin:4px 0 0;font-size:14px;color:var(--mut)}
.st-head .pos{margin:8px 0 0;display:flex;gap:9px;align-items:center;flex-wrap:wrap;
font-size:12px;color:var(--soft)}
.st-head .pos:empty{display:none}
.st-issue{margin:0;padding-left:18px}
.st-issue li{margin-bottom:4px;font-size:14.5px}
/* What moved since the last meeting. The answer to the first question asked. */
.moves{list-style:none;margin:0;padding:0}
.moves li{display:flex;gap:12px;align-items:baseline;padding:8px 0;
border-bottom:1px dashed var(--line)}
.moves li:last-child{border-bottom:0}
.mv-day{font-size:11px;font-weight:750;text-transform:uppercase;
letter-spacing:.08em;color:var(--soft);padding:4px 0 2px;border-bottom:0}
.mv-when{flex:none;width:40px;font-size:11.5px;font-weight:700;color:#9aa3b2;
font-variant-numeric:tabular-nums}
.mv-what{flex:1;min-width:0;font-size:14px}
.mv-what b{font-weight:700}
.mv-so{display:block;font-size:13px;color:var(--accent-ink);margin-top:3px;
padding-left:10px;border-left:2px solid var(--accent-line)}
/* The whole history, one fold per day, counting back from today. The line in the
   middle is where he last spoke: above it is what has changed, below it is what
   the room may still ask him to remember. */
.mv-mark{margin:10px 0 4px;padding:6px 10px;background:var(--hair);
border-radius:7px;font-size:11.5px;font-weight:650;color:var(--soft)}
.mv-fold{border-bottom:1px dashed var(--line)}
.mv-fold:last-child{border-bottom:0}
.mv-fold>summary{display:flex;gap:10px;align-items:baseline;cursor:pointer;
padding:7px 0;font-size:13px;color:var(--mut)}
.mv-fold>summary::-webkit-details-marker{display:none}
.mv-fold>summary:hover .mv-d{color:var(--accent-ink)}
.mv-d{font-weight:700}
.mv-c{font-size:11.5px;color:var(--soft)}
.mv-fold .moves{padding:0 0 6px 4px}
.q-side{font-size:12.5px;color:var(--soft);margin-top:3px}
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
.st-safe{margin:5px 0 0;font-size:13.5px;color:var(--ink)}
.st-safe:before{content:"";display:inline-block;width:3px;height:12px;
border-radius:2px;background:var(--green);margin-right:7px;vertical-align:-1px}
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
.sess-focus{margin:0;font-size:14.5px;color:var(--mut)}
.sess.big{border-left-width:5px}
.sess.bare{background:none;border:0;box-shadow:none;padding:0;margin-bottom:14px}
.sess.bare .sess-bring{margin:0}
.day-fold{margin-top:10px}
.day-fold>summary{cursor:pointer;padding:8px 11px;background:var(--hair);
border-radius:8px;display:flex;align-items:center;gap:10px}
.agenda{list-style:none;margin:11px 0 0;padding:0;display:grid;gap:1px;
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

/* Everything he has to come out of the room with, one list. The label on the
   left says which kind it is, so a decision to land and a chase are not read
   with the same weight. */
.needs{list-style:none;margin:0;padding:0}
.need-row{display:flex;gap:13px;padding:11px 13px;border-radius:9px;
margin-bottom:7px;border:1px solid var(--line);background:#fbfcfe}
.need-row.settle{border-color:var(--amber-line);background:var(--amber-bg)}
.need-row.ask{border-color:var(--accent-line);background:var(--accent-bg)}
.need-k{flex:none;width:112px;font-size:10.5px;font-weight:750;
text-transform:uppercase;letter-spacing:.07em;color:var(--soft);padding-top:3px}
.need-row.settle .need-k{color:var(--amber)}
.need-row.ask .need-k{color:var(--accent)}
.need-row.owed .need-k{color:var(--blue)}
.need-b{flex:1;min-width:0}
.need-what{margin:0;font-size:14.5px;font-weight:600;display:flex;gap:9px;
align-items:baseline;flex-wrap:wrap}
.need-why{margin:3px 0 0;font-size:13px;color:var(--mut)}
.need-fall{margin:6px 0 0;font-size:13px;color:var(--amber);font-weight:550}
.need-fall b{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;
margin-right:6px}
.need-b .jp.small{font-size:16px;line-height:1.85;margin-top:5px}
.st-push{list-style:none;margin:0;padding:0}
.st-push li{padding:11px 0;border-bottom:1px dashed var(--line)}
.st-push li:last-child{border-bottom:0}
.st-push .they{font-size:13.5px;color:var(--mut);padding-left:11px;
border-left:3px solid var(--line);font-style:italic}
.st-push .mine{margin-top:7px;padding-left:11px;border-left:3px solid var(--accent-line)}
.st-push .mine .jp{font-size:17px}
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
    """What this room has to produce, and what he has to walk in holding.

    The agenda that used to sit here was a second copy of every ticket's asks,
    one screen above them. What survives is the sentence saying what the room is
    for, and the things he promised to bring, because forgetting one of those is
    the only failure this block can actually prevent.
    """
    if not sess.get("date") and not sess.get("focus"):
        return ""
    bring = sess.get("bring", [])
    bring_block = ""
    if bring:
        rows = "".join(f"<li>{esc(b)}</li>" for b in bring)
        bring_block = (
            f'<div class="sess-bring"><b>Walk in with</b>'
            f'<ul style="margin:0;padding-left:17px">{rows}</ul></div>'
        )
    focus = (
        f'<p class="sess-focus">{esc(sess.get("focus"))}</p>'
        if sess.get("focus")
        else ""
    )
    # With nothing but the bring list in it, the frame is a box drawn round a
    # box. Drop it and let the list stand on its own.
    return f"""
  <section class="sess {"big" if big else ""} {"" if focus else "bare"}">
    {focus}{bring_block}
  </section>"""




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
        count=f"{len(rows)} answers ready",
        fold=True,
        hint="the objection you can see coming",
    )


def move_li(e: dict) -> str:
    """One move: when, who, what it was, and what it meant."""
    src = e.get("source_url", "")
    return f"""
        <li>
          <span class="mv-when">{esc(e.get("at", ""))}</span>
          <span class="mv-what"><b>{esc(e.get("who", ""))}</b> {esc(e.get("what"))}
            {f'<span class="mv-so">{esc(e.get("so_what"))}</span>' if e.get("so_what") else ""}
          </span>
          {link_btn(src, "Source") if src else ""}
        </li>"""


def since_last(t: dict, since: str) -> str:
    """What moved on this ticket since the last meeting, and the days before it.

    Reading the ticket cold at 09:50 is the hard part of the morning, harder
    than the Japanese. This is the paragraph that answers "what happened since
    I last talked about this", which is also the first thing anyone in the room
    asks.

    It used to stop there, at six moves since the last session, and the room does
    not. "When did you first tell us about this" and "what did we agree in
    August" are asked of the same card, and the answer was a tab away on the work
    view. The whole history is here now, one fold per earlier day, so nothing
    asked in the room needs the other tab.
    """
    rows = sorted(t.get("events", []), key=lambda e: (e.get("on", ""), e.get("at", "")))
    if not rows:
        return ""
    new = [e for e in rows if (e.get("on") or "") >= since]
    old = [e for e in rows if (e.get("on") or "") < since]

    # One fold per day, counting back, because the question in the room is "when
    # did that happen". The newest day is open, since that is the day being asked
    # about, and a line says where he last spoke so the days above it are the
    # answer to "what has changed since".
    days: dict[str, list[dict]] = {}
    for e in rows:
        days.setdefault(e.get("on", ""), []).append(e)
    order = sorted(days, reverse=True)
    parts, marked = [], False
    for d in order:
        if old and not marked and d < since:
            parts.append(
                f'<p class="mv-mark">You last spoke about this '
                f"{esc(day_words(since))}. Everything below is older.</p>"
            )
            marked = True
        moves = days[d]
        n = len(moves)
        parts.append(
            f"""
        <details class="mv-fold" {"open" if d == order[0] else ""}>
          <summary><span class="mv-d">{opening(esc(day_words(d)))}</span>
          <span class="mv-c">{n} {"move" if n == 1 else "moves"}</span>
          <span class="fold-hint"></span></summary>
          <ul class="moves">{"".join(move_li(e) for e in moves)}</ul>
        </details>"""
        )
    body = f'<div class="mv-days">{"".join(parts)}</div>'
    if new and old:
        tally = f"{len(new)} since {day_words(since)}, {len(old)} before"
    elif new:
        tally = f"{len(new)} since {day_words(since)}"
    else:
        tally = f"{len(old)} {'move' if len(old) == 1 else 'moves'}, none since you spoke"
    return section(
        "What moved on this ticket",
        body,
        role="log",
        count=tally,
        hint="the question they always ask",
        fold=True,
        remember=f"moved-{t.get('ref', '')}",
    )


def needs(t: dict, spoken: bool) -> str:
    """Everything he has to come out of the room with, in one list.

    A decision to land, a question to get answered and a thing somebody already
    owes him were three blocks under the script, which meant reading three lists
    to answer one question. They are all the same question, so they are one
    list, and each row says which kind it is and who has to move.
    """
    prep = t.get("prep") or {}
    rows, hardest = [], 0
    for d in prep.get("decisions", []):
        hardest = 2
        rows.append(
            f"""
        <li class="need-row settle">
          <div class="need-k">Settle it today</div>
          <div class="need-b">
            <p class="need-what">{esc(d.get("need"))}</p>
            {f'<p class="need-why">{esc(d.get("why"))}</p>' if d.get("why") else ""}
            {f'<p class="need-fall"><b>If they will not settle it</b> {esc(d.get("fallback"))}</p>' if d.get("fallback") else ""}
          </div>
        </li>"""
        )

    asks = list(prep.get("open_questions", []))
    if spoken:
        asks = [q for q in asks if q.get("who") not in ("TG", "")]
    for q in asks:
        hardest = max(hardest, 1)
        who = q.get("who", "TG")
        raw = plain(q.get("ja_ruby", ""))
        rows.append(
            f"""
        <li class="need-row ask">
          <div class="need-k">Answer from {esc(who)}</div>
          <div class="need-b">
            <p class="need-what">{esc(q.get("en"))}
              {f'<button class="copy" data-copy="{esc(raw)}">copy</button>' if raw else ""}</p>
            {f'<p class="jp small">{furi(q.get("ja_ruby", ""))}</p>' if q.get("ja_ruby") else ""}
          </div>
        </li>"""
        )

    for item in t.get("items", []):
        st = state_of(item)
        if st["state"] != "waiting":
            continue
        owed = (item.get("waits_on") or {}).get("what", "")
        rows.append(
            f"""
        <li class="need-row owed">
          <div class="need-k">Already owed</div>
          <div class="need-b">
            <p class="need-what">{esc(owed or item.get("title", ""))}</p>
            <p class="need-why">{esc(st.get("who", "They"))} has had this since
            {esc(st.get("at", ""))}. Item {esc(item.get("id", ""))} on your list.
            Chase it here if they are in the room.</p>
          </div>
        </li>"""
        )

    if not rows:
        return ""
    words = {0: "", 1: "to get answered", 2: "one has to be settled today"}
    return section(
        "What I need back",
        f'<ul class="needs">{"".join(rows)}</ul>',
        role="warn",
        count=f"{len(rows)} in total",
        hint=words[hardest],
    )


def render_ticket(t: dict, ident: str, desk_id: str, since: str) -> str:
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
    # The one line about the build that may be said out loud. It sits with the
    # warning because that is the moment he needs it: asked when, in the room.
    safe = (internal.get("build") or {}).get("safe_to_say")
    if safe:
        secret += f'<p class="st-safe">If they ask when: {furi(safe)}</p>'

    open_items = [i for i in t.get("items", []) if not state_of(i)["closed"]]
    desk_link = (
        f'<a class="btn" href="#{esc(desk_id)}" data-goto="desk">'
        f'{len(open_items)} open on my list</a>'
        if open_items
        else ""
    )
    spoken = any(b.get("heading") == "質問" for b in prep.get("script", []))
    tone = "mine" if not no_ask else "clear"

    return f"""
    <article class="st-tk {tone}" id="{esc(ident)}">
      <header class="st-head">
        <div class="tk-id">
          <span class="tag">{esc(t.get("ref"))}</span>
          <span class="tk-kind">{"Work in hand" if t.get("no_ticket_yet") else "Asana ticket"}</span>
          {pill("Nothing to ask", "green") if no_ask else pill("You need an answer", "amber")}
        </div>
        <h2>{esc(t.get("title_en"))}</h2>
        <p class="ja">{esc(t.get("title_ja"))}</p>
        <p class="pos">
          {f'<span>{esc(prep.get("board_position"))}</span>' if prep.get("board_position") else ""}
          {f'<span class="est">{esc(prep.get("estimate"))}</span>' if prep.get("estimate") else ""}
        </p>
        <div class="tk-links">
          <span class="lab">Go to</span>
          {link_btn(t.get("asana_url", ""), "Open in Asana")}
          {desk_link}
        </div>
      </header>

      {f'''<section class="sub key">
        <h3>The issue in 20 seconds<span class="hint">if they ask what this is</span></h3>
        <ul class="st-issue">{issue}</ul>
        {f'<p class="matters">{esc(prep.get("why_it_matters"))}</p>' if prep.get("why_it_matters") else ""}
      </section>''' if issue else ""}

      {section("Where it stands",
               f'<p class="st-stands">{esc(t.get("where_it_stands"))}</p>'
               f'{raise_rows(t, desk_id)}',
               role="key", hint="one line if they only ask once")}

      {since_last(t, since)}

      <section class="sub say script">
        <h3>Say this<span class="hint">out loud, as written</span>
          <button class="ask-here" type="button"
                  data-ask-seed="Rewrite what I say here: ">{SPARK}Rewrite or ask</button></h3>
        {'<p class="st-none">Status only. Nothing needed from TG.</p>' if no_ask else ""}
        {render_script(prep.get("script", []))}
      </section>

      {render_pushback(prep.get("pushback", []))}
      {needs(t, spoken)}
      <div class="st-cons">{render_consequences(prep.get("consequences", {}), t.get("ref", ""))}</div>
      {warn}
      {secret}
      {section("Ask or change on this ticket",
               ask_block(
                   f'ticket:{t.get("ref")}',
                   f'what I say on {t.get("ref", "this ticket")}',
                   ASKED.get(f'ticket:{t.get("ref")}', []),
                   "Read prompt-ask.md, then answer this about the "
                   f'{t.get("ref", "")} ticket. He is asking from the speaking '
                   "view, in front of what he says at the next session:",
                   kind="say",
               ),
               role="ask",
               hint="the same thread as the work view")}
    </article>"""


def running_order(tickets: list[dict], ids: dict[str, str]) -> str:
    """The order the meeting reaches his tickets, and what each one needs.

    The number is the card's place on TG's board, which is the order they work
    down, so 2 then 11 then 15 is right and is not a count of anything.
    """
    rows = []
    for n, t in enumerate(tickets, 1):
        prep = t.get("prep") or {}
        blocks = len(prep.get("script", []))
        decisions = len(prep.get("decisions", []))
        note = (
            f"{decisions} to settle today" if decisions
            else "status only, nothing to ask" if prep.get("tg_ask_needed") is False
            else f"{blocks} thing{'s' if blocks != 1 else ''} to say" if blocks
            else "nothing written yet"
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


def prep_jump(tickets: list[dict], ids: dict[str, str]) -> str:
    """The same jump bar as the work view, in the order the meeting walks."""
    chips = ['<a href="#prep-need">Need to know</a>']
    for n, t in enumerate(tickets, 1):
        ref = t.get("ref", "")
        prep = t.get("prep") or {}
        chips.append(
            f'<a class="tkt" href="#{esc(ids[ref])}">{esc(ref)}'
            f'<span class="ord">no. {prep.get("order", n)}</span></a>'
        )
    return f"""
  <nav class="jump">
    <span class="lab">Jump to</span>
    {"".join(chips)}
    <button class="find" data-find type="button">Find <kbd>/</kbd></button>
  </nav>"""


def whole_day(sess: dict) -> str:
    """The rest of the meeting, folded, for a long session with other people's
    topics in it. Useful to know where his parts sit in the day, and not worth a
    single line of vertical space until he asks for it."""
    rows = sess.get("agenda", [])
    if not rows:
        return ""
    out = "".join(
        f"""
      <li>
        <span class="ag-t">{esc(r.get("topic"))}</span>
        <span class="ag-w">{esc(r.get("why"))}</span>
        {f'<span class="ag-o">{esc(r.get("owner"))}</span>' if r.get("owner") else ""}
      </li>"""
        for r in rows
    )
    return f"""
      <details class="day-fold">
        <summary><span class="ev-d">The whole day</span>
        <span class="ev-c">{len(rows)} items, yours and everyone else's</span>
        <span class="fold-hint"></span></summary>
        <ul class="agenda">{out}</ul>
      </details>"""


def last_session(board: dict, sess: dict) -> str:
    """The date of the meeting before this one, for "what moved since".

    The meeting note carries the last standup's date. Without one, a week back
    is close enough: a ticket that has not moved in a week has nothing to say.
    """
    note = (board.get("meeting_note") or {}).get("date")
    if note:
        return note
    try:
        return (date.fromisoformat(sess.get("date", "")) - timedelta(days=7)).isoformat()
    except ValueError:
        return ""


def render(board: dict, desk_ids: dict[str, str], built: str, stale: bool) -> str:
    """The speaking half of the page. `built` is empty when there is no script
    yet, which is the normal state until Rei presses the button."""
    sess = script_session(board)
    onsite = sess.get("kind") != "standup"
    # The script's own headline and the session's focus are two people answering
    # "what is this meeting for", and printed together they read as a stutter.
    # The headline was written for this script, so it wins.
    lead = script_meta(board).get("headline") or ""
    room = dict(sess, focus="") if lead else sess
    banner = render_session(room, onsite)

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
    <h2>Nothing written yet {esc(for_what)}</h2>
    <p>Press <strong>Write prep</strong> and it reads every open ticket, the
    threads behind them and the last meeting's decisions, then writes what moved,
    what you say and what you need out of the room.{esc(extra)} Takes a couple of
    minutes.</p>
  </div>"""

    tickets.sort(key=lambda t: (t.get("prep") or {}).get("order", 99))
    ids = {t.get("ref", ""): anchor(desk_ids.get(t.get("ref", ""), "")) for t in tickets}
    since = last_session(board, sess)
    cards = "".join(
        render_ticket(t, ids[t.get("ref", "")], desk_ids.get(t.get("ref", ""), ""), since)
        for t in tickets
    )
    stale_note = (
        '<div class="st-stale">Written before the last refresh, so it may not know '
        "the newest replies. Press Update prep if that matters.</div>"
        if stale
        else ""
    )
    settle = sum(len((t.get("prep") or {}).get("decisions", [])) for t in tickets)
    asks = sum(
        1
        for t in tickets
        if (t.get("prep") or {}).get("tg_ask_needed") is not False
        or (t.get("prep") or {}).get("decisions")
    )
    # The summary line answers the two questions he has walking in: which room,
    # and how much of it is his. Everything else is a click away.
    room = esc(sess.get("title") or sess.get("name"))
    when = esc(when_words(sess.get("date", ""), sess.get("at", "")))
    speak = f'{len(tickets)} of your tickets, {asks} needing an answer from them'
    if settle:
        speak += f', {settle} to settle in the room'
    return f"""
  {prep_jump(tickets, ids)}
  {stale_note}
  <details class="nk" id="prep-need" data-remember="prep-need" open>
    <summary>
      <span class="nk-k">Need to know</span>
      <span class="nk-n">what the room is for, then the order</span>
      <span class="fold-hint"></span>
      <span class="nk-sum"><b>{room}, {when}.</b> You speak on {esc(speak)}.</span>
    </summary>
    <div class="nk-in">
      {f'<p class="nk-alert plain"><b>What today has to produce</b>{esc(lead)}</p>' if lead else ""}
      {banner}
      <h3 class="run-h">The order they reach your tickets<span class="q">the
      number is the card's place on TG's board</span></h3>
      {running_order(tickets, ids)}
      {whole_day(sess)}
    </div>
  </details>
  {cards}
  <p class="foot">Written {esc(built)}. <kbd>1</kbd> your work,
  <kbd>2</kbd> what you say, <kbd>s</kbd> Japanese only, <kbd>/</kbd> find
  anything, <kbd>?</kbd> how this works.</p>"""
