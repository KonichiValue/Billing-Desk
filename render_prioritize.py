#!/usr/bin/env python3
"""The prioritization round on the desk: when it is, and what to raise before it.

Heqing posts the round's result first thing on a Monday, every second week, and
a build nobody raised by then waits another two weeks. So the card's first line
is the day he has to have spoken by, not the day of the round, and it is drawn
red once that day has come. Under it, his builds: the ones to raise, the edits
to make in Asana first, and the ones already ordered, which only need their
dates kept right. The note to Heqing is built from the same rows, so it cannot
say something the list does not.

Desk only. Nothing here is ever said to TG. `prioritize.py` holds the dates and
the rules; this file only draws them.
"""

from __future__ import annotations

from datetime import date

import prioritize as P
from render import day_words, esc, link_btn

KIND = {
    "raise": ("Raise", "red"),
    "ordered": ("Ordered", "green"),
    "refining": ("Not refined", "grey"),
}


def when(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%a %-d %b")
    except (TypeError, ValueError):
        return iso


def row(r: dict, refs: dict[str, str]) -> str:
    label, tone = KIND[r["kind"]]
    ref = r.get("ticket", "")
    card = (f'<a class="pr-ref" href="#{esc(refs[ref])}">{esc(ref)}</a>'
            if ref and ref in refs else "")
    kt = (f'<a class="pr-kt" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r.get("kt", ""))}</a>'
          if r.get("url") else f'<span class="pr-kt">{esc(r.get("kt", ""))}</span>')
    facts = [r.get("status", ""), r.get("size", "")]
    if r.get("tg_order"):
        facts.append(f"TG Order {r['tg_order']}")
    if r.get("wave"):
        facts.append(r["wave"])
    facts.append(f"due {when(r['due_on'])}" if r.get("due_on") else "no due date")
    fixes = "".join(f'<li>{esc(f)}</li>' for f in r.get("fixes") or [])
    why = f'<span class="pr-why">{esc(r["why"])}</span>' if r.get("why") and r["kind"] == "raise" else ""
    return f"""
        <li class="pr-row {esc(r["kind"])}">
          <span class="pr-tag {tone}">{esc(label)}</span>
          <span class="pr-main">{kt}<span class="pr-name">{esc(P.short(r.get("name", "")))}</span>{card}
            <span class="pr-facts">{esc(" · ".join(f for f in facts if f))}</span>
            {why}
            {f'<ul class="pr-fix">{fixes}</ul>' if fixes else ""}</span>
        </li>"""


def render(board: dict, refs: dict[str, str]) -> str:
    s = P.summary(board)
    nxt = s["next"]
    if not nxt:
        return ""
    cfg = s["config"]
    ask_days = nxt["ask_days"]
    if ask_days < 0:
        due, tone = f"Ask-by day passed ({when(nxt['ask_by'])}); raise it first thing", "red"
    elif ask_days == 0:
        due, tone = "Raise anything today", "red"
    elif ask_days == 1:
        due, tone = "Raise anything by tomorrow", "amber"
    else:
        due, tone = f"Raise anything by {when(nxt['ask_by'])}", "grey"
    moved = f' <span class="pr-moved">(moved: {esc(nxt["moved"])})</span>' if nxt.get("moved") else ""
    raise_n, fix_n = len(s["raise"]), len(s["fixes"])
    counts = []
    if raise_n:
        counts.append(f"{raise_n} to raise")
    if fix_n:
        counts.append(f"{fix_n} to fix in Asana")
    tally = " · ".join(counts) or "nothing to raise"
    rows = "".join(row(r, refs) for r in s["rows"])
    text = P.message(s)
    note = ""
    if text:
        note = f"""
      <div class="draft pr-note">
        <div class="draft-head">
          <span>To Heqing, in {esc(cfg.get("channel", "Slack"))}, before {esc(when(nxt["date"]))} {esc(nxt["at"])}</span>
          {link_btn(cfg.get("example_thread", ""), "Last round's thread")}
          <button class="copy" data-copy="{esc(text)}">copy</button>
        </div>
        <div class="draft-body">{esc(text)}</div>
      </div>"""
    last = s["last_round"]
    last_line = ""
    if last.get("date"):
        bits = []
        if last.get("ordered"):
            bits.append("ordered " + ", ".join(last["ordered"]))
        if last.get("not_pushed"):
            bits.append("not pushed " + ", ".join(last["not_pushed"]))
        last_line = (f'<p class="pr-last">Last round {esc(day_words(last["date"]))}: '
                     f'{esc("; ".join(bits) or "nothing of yours")}. '
                     f'{link_btn(last.get("url", ""), "Thread")}</p>')
    stale = f'<p class="pr-stale">{esc(s["stale"])}</p>' if s["stale"] else ""
    return f"""
    <details class="pr" id="prioritization" data-remember="prioritization"{" open" if ask_days <= 1 and (raise_n or fix_n) else ""}>
      <summary class="pr-head">
        <span class="pr-kind">Prioritization</span>
        <span class="pr-name-h">{esc(when(nxt["date"]))} {esc(nxt["at"])}, {esc(cfg.get("who", "Heqing"))}'s thread{moved}</span>
        <span class="pr-due {tone}">{esc(due)}</span>
        <span class="pr-sum">{esc(tally)}</span>
        <span class="fold-hint"></span>
      </summary>
      {stale}
      <ul class="pr-rows">{rows or '<li class="pr-row">No builds of yours on the board yet.</li>'}</ul>
      {note}
      {last_line}
    </details>"""


def markdown(board: dict) -> str:
    """The same for desk.md, which a chat reads before answering."""
    s = P.summary(board)
    nxt = s["next"]
    if not nxt:
        return ""
    out = ["## Prioritization", ""]
    out.append(
        f"Next round {nxt['date']} {nxt['at']} ({s['config'].get('who', 'Heqing')}'s thread in "
        f"{s['config'].get('channel', 'Slack')}). Raise anything by {nxt['ask_by']}."
        + (f" Moved: {nxt['moved']}." if nxt.get("moved") else "")
    )
    if s["stale"]:
        out.append(f"_{s['stale']}_")
    out.append("")
    for r in s["rows"]:
        label = KIND[r["kind"]][0]
        line = (f"- **{label}** {r.get('kt', '')} {P.short(r.get('name', ''))}"
                + (f" ({r['ticket']})" if r.get("ticket") else "")
                + f": {r.get('status', '')}, {r.get('size', '') or 'no size'}"
                + (f", TG Order {r['tg_order']}" if r.get("tg_order") else "")
                + (f", {r['wave']}" if r.get("wave") else "")
                + f", due {r.get('due_on') or 'none'}.")
        if r.get("why") and r["kind"] == "raise":
            line += f" {r['why']}"
        out.append(line)
        for f in r["fixes"]:
            out.append(f"  - fix in Asana: {f}")
    last = s["last_round"]
    if last.get("date"):
        out += ["", f"Last round {last['date']}: ordered {', '.join(last.get('ordered') or []) or 'none'};"
                    f" not pushed {', '.join(last.get('not_pushed') or []) or 'none'}. {last.get('url', '')}"]
    text = P.message(s)
    if text:
        out += ["", "Note to Heqing (draft, never sent):", "", "```", text, "```"]
    return "\n".join(out) + "\n"
