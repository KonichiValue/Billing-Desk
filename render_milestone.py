#!/usr/bin/env python3
"""A milestone he leads, drawn the way Jira draws an epic.

A milestone is bigger than one ticket and owns no work of its own, so the card is
a roll-up rather than another to-do list: the target date and how far off it is,
a bar for how much of its work is closed, the phases between here and done in
order, and every ticket under it. A ticket that is his links to its card further
down; one that is somebody else's is a row he follows, never a card, because the
board is his to-do list and not the programme's.

The counts come from the items themselves, so the bar cannot claim more than the
board does. `board.py` documents the shape.
"""

from __future__ import annotations

from datetime import date

from render import esc, item_state, link_btn

STATUS = {
    "on-track": ("On track", "green"),
    "at-risk": ("At risk", "amber"),
    "off-track": ("Off track", "red"),
    "done": ("Done", "green"),
}
PHASE = {"done": "Done", "now": "Now", "next": "Next", "blocked": "Blocked"}


def days_left(iso: str) -> str:
    try:
        left = (date.fromisoformat(iso) - date.today()).days
    except (TypeError, ValueError):
        return ""
    if left < 0:
        return f"{-left} days late"
    if left == 0:
        return "due today"
    weeks = left // 7
    return f"{left} days left" + (f" ({weeks} wk)" if weeks >= 2 else "")


def counts(ms: dict, index: dict[str, tuple[dict, dict]]) -> tuple[int, int]:
    states = [item_state(index[str(n)][1]) for n in ms.get("items") or [] if str(n) in index]
    return sum(1 for s in states if s["closed"]), len(states)


def phase_row(p: dict, n: int) -> str:
    state = p.get("state", "next")
    when = f'<span class="ms-when">{esc(p["when"])}</span>' if p.get("when") else ""
    who = f'<span class="ms-who">{esc(p["who"])}</span>' if p.get("who") else ""
    nums = "".join(f'<span class="ms-num">{esc(i)}</span>' for i in p.get("items") or [])
    note = f'<span class="ms-note">{esc(p["note"])}</span>' if p.get("note") else ""
    return (
        f'<li class="ms-ph {esc(state)}"><span class="ms-dot">{n}</span>'
        f'<span class="ms-body"><span class="ms-what">{esc(p.get("what", ""))}</span>'
        f'<span class="ms-meta"><span class="ms-st">{PHASE.get(state, state)}</span>{when}{who}{nums}</span>'
        f"{note}</span></li>"
    )


def ticket_row(row: dict, refs: dict[str, str], index_refs: set[str]) -> str:
    ref = row.get("ref", "")
    title = row.get("title", "")
    mine = ref in index_refs
    if mine:
        name = f'<a class="ms-tk-ref" href="#{esc(refs[ref])}">{esc(ref)}</a>'
    elif row.get("asana_url"):
        name = f'<a class="ms-tk-ref" href="{esc(row["asana_url"])}" target="_blank" rel="noopener">{esc(ref or title)}</a>'
    else:
        name = f'<span class="ms-tk-ref">{esc(ref or title)}</span>'
    tag = "Your card" if mine else (row.get("assignee") or "Not yours yet")
    state = f'<span class="ms-tk-st">{esc(row["state"])}</span>' if row.get("state") else ""
    return (
        f'<li class="ms-tk {"mine" if mine else "follow"}">{name}'
        f'<span class="ms-tk-t">{esc(title if ref else "")}</span>{state}'
        f'<span class="ms-tk-who">{esc(tag)}</span></li>'
    )


def one(ms: dict, refs: dict[str, str], index: dict[str, tuple[dict, dict]]) -> str:
    label, tone = STATUS.get(ms.get("status", "on-track"), STATUS["on-track"])
    done, total = counts(ms, index)
    phases = ms.get("phases") or []
    ph_done = sum(1 for p in phases if p.get("state") == "done")
    pct = round(100 * ph_done / len(phases)) if phases else (round(100 * done / total) if total else 0)
    now = next((p for p in phases if p.get("state") in ("now", "blocked")), None)
    target = ms.get("target", "")
    try:
        target_txt = date.fromisoformat(target).strftime("%a %-d %b %Y")
    except (TypeError, ValueError):
        target_txt = target
    note = f' <span class="ms-tn">({esc(ms["target_note"])})</span>' if ms.get("target_note") else ""
    people = " &middot; ".join(
        esc(f"{k} {ms[f]}") for k, f in (("Lead", "lead"), ("Support", "support")) if ms.get(f)
    )
    index_refs = {t.get("ref", "") for t, _ in index.values()} | set(refs)
    tickets = "".join(ticket_row(r, refs, index_refs) for r in ms.get("tickets") or [])
    jobs = ""
    for n in ms.get("items") or []:
        if str(n) not in index:
            continue
        t, item = index[str(n)]
        st = item_state(item)
        jobs += (
            f'<li class="ms-job {esc(st["state"])}"><span class="ms-num">{esc(n)}</span>'
            f'<a href="#{esc(refs.get(t.get("ref", ""), ""))}">{esc(item.get("title", ""))}</a>'
            f'<span class="ms-tk-st">{esc(st["state"])}</span></li>'
        )
    links = link_btn(ms.get("source_url", ""), "Notion") + link_btn(ms.get("asana_url", ""), "Asana")
    return f"""
    <details class="ms" data-remember="ms-{esc(ms["id"])}">
      <summary class="ms-head">
        <span class="ms-kind">Milestone</span>
        <span class="ms-name">{esc(ms.get("name", ""))}
          {f'<span class="ms-ja">{esc(ms["name_ja"])}</span>' if ms.get("name_ja") else ""}</span>
        <span class="ms-pill {tone}">{esc(label)}</span>
        <span class="ms-due"><b>{esc(target_txt)}</b>{note} &middot; {esc(days_left(target))}</span>
        <span class="fold-hint"></span>
        <span class="ms-bar" role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100">
          <span style="width:{pct}%"></span></span>
        <span class="ms-sum">{ph_done} of {len(phases)} phases done{f" &middot; {done} of {total} jobs closed" if total else ""}
          {f' &middot; now: <b>{esc(now.get("what", ""))}</b>' if now else ""}
          {f' &middot; {people}' if people else ""}</span>
      </summary>
      {f'<p class="ms-notes">{esc(ms["notes"])}</p>' if ms.get("notes") else ""}
      <div class="ms-grid">
        <div><h4>Path to done</h4><ol class="ms-phases">{"".join(phase_row(p, i) for i, p in enumerate(phases, 1))}</ol></div>
        <div>
          {f'<h4>Tickets under it</h4><ul class="ms-tks">{tickets}</ul>' if tickets else ""}
          {f'<h4>Your jobs on it</h4><ul class="ms-jobs">{jobs}</ul>' if jobs else ""}
          <div class="ms-links">{links}</div>
        </div>
      </div>
    </details>"""


def render(board: dict, refs: dict[str, str]) -> str:
    rows = [m for m in board.get("milestones") or [] if isinstance(m, dict)]
    if not rows:
        return ""
    index = {str(i.get("id")): (t, i) for t in board.get("tickets", []) for i in t.get("items", [])}
    # Open ones first, soonest target first; a finished milestone folds to the end.
    rows.sort(key=lambda m: (m.get("status") == "done", m.get("target") or "9999"))
    return '<section class="milestones">' + "".join(one(m, refs, index) for m in rows) + "</section>"


def markdown(board: dict) -> str:
    """The same roll-up for desk.md, which a chat reads before answering."""
    rows = [m for m in board.get("milestones") or [] if isinstance(m, dict)]
    if not rows:
        return ""
    index = {str(i.get("id")): (t, i) for t in board.get("tickets", []) for i in t.get("items", [])}
    out = ["## Milestones", ""]
    for ms in rows:
        label = STATUS.get(ms.get("status", "on-track"), STATUS["on-track"])[0]
        done, total = counts(ms, index)
        out.append(f"### {ms.get('name', '')} {ms.get('name_ja', '')}".rstrip())
        out.append("")
        out.append(
            f"- Target {ms.get('target', '?')}"
            + (f" ({ms['target_note']})" if ms.get("target_note") else "")
            + f", {days_left(ms.get('target', ''))}. {label}."
            + (f" Lead {ms['lead']}." if ms.get("lead") else "")
            + (f" Support {ms['support']}." if ms.get("support") else "")
        )
        if ms.get("notes"):
            out.append(f"- {ms['notes']}")
        if ms.get("source_url"):
            out.append(f"- Source: {ms['source_url']}")
        if total:
            out.append(f"- Jobs closed: {done} of {total}")
        out.append("")
        for n, p in enumerate(ms.get("phases") or [], 1):
            bits = [p.get("when", ""), p.get("who", "")]
            items = ", ".join(str(i) for i in p.get("items") or [])
            out.append(
                f"{n}. [{p.get('state', 'next')}] {p.get('what', '')}"
                + (f" ({', '.join(b for b in bits if b)})" if any(bits) else "")
                + (f" items {items}" if items else "")
                + (f". {p['note']}" if p.get("note") else "")
            )
        for r in ms.get("tickets") or []:
            out.append(
                f"- Ticket {r.get('ref') or r.get('title', '')}: {r.get('title', '')}"
                + (f", {r['state']}" if r.get("state") else "")
                + f", {r.get('assignee') or 'not assigned to Rei'}"
                + (f" {r['asana_url']}" if r.get("asana_url") else "")
            )
        for n in ms.get("items") or []:
            if str(n) in index:
                t, item = index[str(n)]
                out.append(f"- Job {n} ({t.get('ref', '')}, {item_state(item)['state']}): {item.get('title', '')}")
        out.append("")
    return "\n".join(out)


def speaking(board: dict) -> str:
    """One line per open milestone on the speaking view: where it is, and the
    words for the room if the prep wrote any (`say`, house-style Japanese)."""
    from render import furi

    rows = [m for m in board.get("milestones") or []
            if isinstance(m, dict) and m.get("status") != "done"]
    if not rows:
        return ""
    out = ""
    for ms in rows:
        phases = ms.get("phases") or []
        now = next((p for p in phases if p.get("state") in ("now", "blocked")), None)
        said = "".join(f"<p class=\"ms-say\">{furi(line)}</p>" for line in ms.get("say") or [])
        out += (
            f'<div class="ms-spk"><span class="ms-kind">Milestone</span> '
            f'<b>{esc(ms.get("name_ja") or ms.get("name", ""))}</b> '
            f'<span class="ms-due">{esc(ms.get("target", ""))} &middot; {esc(days_left(ms.get("target", "")))}</span>'
            + (f' <span class="ms-now">now: {esc(now.get("what", ""))}</span>' if now else "")
            + f"{said}</div>"
        )
    return f'<section class="ms-spks">{out}</section>'
