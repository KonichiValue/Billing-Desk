"""Who the board talks about, as people rather than strings.

"Waiting on" used to be a text box, so the board holds one person five ways:
"Tomoya Tanaka, TG", "Tanaka-san", "TG (Tanaka)", "Tanaka", "Tomoya Tanaka（田中
智也）". Every one of them is the same man, and a page that cannot tell is a page
where the picker offers him five times and the week strip reads "With TG
(Tanaka)" on one day and "With Tanaka-san" on the next.

So this reads every name the board already holds (who did each event, who a
job waits on, who each step of closing a ticket belongs to, the Asana assignee),
works out the people behind them, and answers two questions: who is this string,
and what should the page call them. It is worked out on every render rather than
stored, so a name he types into the picker's fallback joins the directory the
moment the tick writes it to `waits_on.who`, and there is no second file to keep
in step with the board.

The value written to the board is the board's own house form, "Given Family,
Org", the form the sweeps already write. What the page shows is shorter, and
the way he says it: Tanaka-san for Tokyo Gas, Heqing for Kraken.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

# Strings that are not a person anyone could be waiting on: Rei himself, the
# rooms, the tools, and the board's own placeholders.
NOT_PEOPLE = {
    "you", "rei", "rei samuelsson", "start of day", "standup", "github", "asana",
    "nobody", "none", "", "other workstreams", "billing team", "kraken (system)",
    "kraken (asana)", "tokyo gas",
}

# The organisations, longest first so "Kraken CE" wins over "Kraken". A team is
# something a job can wait on too ("Waiting on TG"), so each is offered as one.
ORGS = (
    "Kraken CE", "Kraken IE", "Kraken I&J", "TG iNET", "TG Payments", "Kraken", "TG",
)
ORG_ALIAS = {"CE": "Kraken CE", "IE": "Kraken IE", "Tokyo Gas": "TG"}

NAME = r"[A-Z][a-z]+(?:-[A-Z]?[a-z]+)?"
FULL = re.compile(rf"^({NAME}(?: {NAME})+)$")
SURNAME = re.compile(rf"^({NAME})(?:-san)?$")
JA = re.compile(r"[（(]([぀-ヿ㐀-鿿]+)[）)]")
SPLIT = re.compile(r"\s*(?:,? and |\s/\s|、|, then | then |, cc )\s*")

# What a sweep, a tick or a render last worked out. Read-only after `load()`.
DIRECTORY: list[dict] = []
_BY_KEY: dict[str, dict] = {}


def org_of(text: str) -> str:
    """The organisation a string names, or ""."""
    t = text.strip().strip("()").strip()
    if t in ORG_ALIAS:
        return ORG_ALIAS[t]
    for o in ORGS:
        if t == o or t.startswith(o + " ") or t.startswith(o + ","):
            return o
    return ""


def parse(part: str) -> tuple[str, str, str, str]:
    """One name as (full name, surname alias, organisation, Japanese name).

    Exactly one of the first two is set when the part names a person, neither
    when it names only a team or nothing at all.
    """
    part = re.sub(r"-san\b", "", part.strip())
    ja = ""
    m = JA.search(part)
    if m:
        ja = m.group(1)
        part = (part[: m.start()] + part[m.end():]).strip()
    org = ""
    # "TG (Tanaka)", "TG, Tanaka", "Kraken CE / Heqing": a team, then a name.
    m = re.match(r"^(TG|Kraken(?: CE| IE)?)\s*[,(]\s*([A-Za-z-]+?)(?:-san)?\)?$", part)
    if m and SURNAME.match(m.group(2)):
        return "", m.group(2), org_of(m.group(1)), ja
    # "Name, Org, anything else" or "Name (Org)".
    m = re.match(r"^(.+?)\s*\((.+)\)$", part)
    if m and org_of(m.group(2).split(",")[0]):
        part, org = m.group(1), org_of(m.group(2).split(",")[0])
    elif m:
        part = m.group(1)
    bits = [b.strip() for b in part.split(",")]
    if len(bits) > 1:
        part, org = bits[0], org or org_of(bits[1])
    part = re.sub(r"\s*\(.*?\)\s*$", "", part).strip()
    if FULL.match(part):
        return part, "", org, ja
    m = SURNAME.match(part)
    if m and not org_of(part):
        return "", m.group(1), org, ja
    return "", "", org or org_of(part), ja


def short(p: dict) -> str:
    """What the page calls someone: the way he would say it out loud."""
    if p.get("team"):
        return p["name"]
    if p.get("org", "").startswith("TG"):
        return f'{p["surname"]}-san'
    return p["name"].split(" ")[0]


def initials(p: dict) -> str:
    if p.get("team"):
        return "".join(w[0] for w in p["name"].replace("&", "").split())[:2].upper()
    words = p["name"].split()
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def hue(key: str) -> int:
    """A colour per person that is the same on every page and every day."""
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:4], 16) % 360


def strings(board: dict) -> list[tuple[str, str, str]]:
    """Every name the board holds, as (text, ticket ref, date seen)."""
    out: list[tuple[str, str, str]] = []
    for t in board.get("tickets", []):
        ref = str(t.get("ref", ""))
        for e in t.get("events", []):
            out.append((str(e.get("who", "")), ref, str(e.get("on", ""))))
        for c in t.get("closes_when", []) or []:
            if isinstance(c, dict):
                out.append((str(c.get("who", "")), ref, ""))
        a = (t.get("asana") or {}).get("assignee")
        if a:
            out.append((str(a), ref, ""))
        for i in t.get("items", []):
            w = (i.get("waits_on") or {}).get("who")
            if w:
                out.append((str(w), ref, str((i.get("waits_on") or {}).get("since", ""))[:10]))
    for p in board.get("milestones", []) or []:
        for ph in (p.get("phases") or []) if isinstance(p, dict) else []:
            if isinstance(ph, dict) and ph.get("who"):
                out.append((str(ph["who"]), "", ""))
    return out


def build(board: dict) -> list[dict]:
    """The directory: one row per person or team the board has ever named."""
    people: dict[str, dict] = {}
    aliases: list[tuple[str, str, str, str, str]] = []
    teams: Counter = Counter()

    def person(name: str, org: str, ja: str) -> dict:
        key = name.lower()
        p = people.setdefault(key, {
            "id": "p-" + re.sub(r"[^a-z]+", "-", key).strip("-"),
            "name": name, "org": "", "ja": "", "surname": name.split()[-1],
            "aliases": set(), "n": 0, "seen": "", "refs": Counter(),
        })
        if org and (not p["org"] or len(org) > len(p["org"]) and org.startswith(p["org"])):
            p["org"] = org
        if ja and not p["ja"]:
            p["ja"] = ja
        return p

    for text, ref, on in strings(board):
        if text.strip().lower() in NOT_PEOPLE:
            continue
        for part in SPLIT.split(text):
            full, sur, org, ja = parse(part)
            if full:
                if full.lower() in NOT_PEOPLE:
                    continue
                p = person(full, org, ja)
                # Only a string that names this one person is a way of saying
                # them. "Tamanoi-san and Koume-san" is neither.
                if len(SPLIT.split(text)) == 1:
                    p["aliases"].add(text.strip())
                p["n"] += 1
                p["seen"] = max(p["seen"], on)
                if ref:
                    p["refs"][ref] += 1
            elif sur and sur.lower() not in NOT_PEOPLE:
                aliases.append((sur, org, ja, text.strip(), ref + "\0" + on))
            elif org:
                teams[org] += 1

    # A surname on its own belongs to the one full name it matches, preferring
    # one in the same organisation. Two matches and it stays its own row: the
    # picker should never quietly decide which Tanaka he meant.
    for sur, org, ja, text, where in aliases:
        ref, on = where.split("\0")
        hits = [p for p in people.values() if sur in p["name"].split()]
        same = [p for p in hits if org and p["org"].split(" ")[0] == org.split(" ")[0]]
        pick = same if len(same) == 1 else hits if len(hits) == 1 and not (
            org and hits[0]["org"] and hits[0]["org"].split(" ")[0] != org.split(" ")[0]
        ) else []
        if pick:
            p = pick[0]
            p["surname"] = sur
        else:
            p = person(sur, org, ja)
        if ja and not p["ja"]:
            p["ja"] = ja
        if len(SPLIT.split(text)) == 1:
            p["aliases"].add(text)
        p["n"] += 1
        p["seen"] = max(p["seen"], on)
        if ref:
            p["refs"][ref] += 1

    out = []
    for p in people.values():
        p["aliases"] = sorted(p["aliases"] - {p["name"]})
        out.append(p)
    for org, n in teams.items():
        out.append({
            "id": "t-" + re.sub(r"[^a-z]+", "-", org.lower()).strip("-"),
            "name": org, "org": org, "ja": "", "surname": org, "team": True,
            "aliases": [], "n": n, "seen": "", "refs": Counter(),
        })
    for o in ("TG", "Kraken CE"):
        if not any(p.get("team") and p["name"] == o for p in out):
            out.append({
                "id": "t-" + re.sub(r"[^a-z]+", "-", o.lower()).strip("-"),
                "name": o, "org": o, "ja": "", "surname": o, "team": True,
                "aliases": [], "n": 0, "seen": "", "refs": Counter(),
            })
    out.sort(key=lambda p: (bool(p.get("team")), -p["n"], p["name"]))
    return out


def load(board: dict) -> None:
    """Work the directory out from this board, for everything this render draws."""
    DIRECTORY[:] = build(board)
    _BY_KEY.clear()
    for p in DIRECTORY:
        for k in [p["name"], value(p), *p["aliases"]]:
            _BY_KEY.setdefault(k.strip().lower(), p)
        if p.get("ja"):
            _BY_KEY.setdefault(p["ja"], p)


def value(p: dict) -> str:
    """What goes on the board: the house form, "Given Family, Org"."""
    if p.get("team") or not p.get("org"):
        return p["name"]
    return f'{p["name"]}, {p["org"]}'


def find(text: str) -> list[dict]:
    """The people a string names, in order. Empty when it names nobody known."""
    text = (text or "").strip()
    if not text or not DIRECTORY:
        return []
    hit = _BY_KEY.get(text.lower())
    if hit:
        return [hit]
    out: list[dict] = []
    for part in SPLIT.split(text):
        hit = _BY_KEY.get(part.strip().lower())
        if not hit:
            full, sur, org, ja = parse(part)
            hit = _BY_KEY.get((full or sur or org).lower()) if (full or sur or org) else None
            if not hit and sur:
                hits = [p for p in DIRECTORY if not p.get("team") and sur in p["name"].split()]
                hit = hits[0] if len(hits) == 1 else None
        if hit and hit not in out:
            out.append(hit)
    return out


def said(text: str) -> str:
    """A holder string the way the page says it: "Tanaka-san", "Heqing and TG".

    Anything it cannot read comes back as written, so an odd value on the board
    is shown rather than lost.
    """
    found = find(text)
    parts = [p for p in SPLIT.split(text or "") if p.strip()]
    if not found or len(found) != len(parts):
        return text
    names = [short(p) for p in found]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def public(p: dict) -> dict:
    """One row as the page's picker reads it."""
    return {
        "id": p["id"], "name": p["name"], "org": p.get("org", ""), "ja": p.get("ja", ""),
        "short": short(p), "value": value(p), "ini": initials(p), "hue": hue(p["id"]),
        "team": bool(p.get("team")), "n": p["n"],
        "also": [a for a in p["aliases"] if len(a) <= 40][:6],
    }


def near(board: dict) -> dict[str, list[str]]:
    """For each open job, the people on its ticket, busiest first.

    The picker's "On this ticket" group: whoever the job is waiting on is far
    more likely to be one of the dozen names in its own thread than one of the
    hundred on the board.
    """
    out: dict[str, list[str]] = {}
    for t in board.get("tickets", []):
        ref = str(t.get("ref", ""))
        here = sorted(
            (p for p in DIRECTORY if p["refs"].get(ref) and not p.get("team")),
            key=lambda p: (-p["refs"][ref], p["name"]),
        )
        ids = [p["id"] for p in here[:8]]
        for i in t.get("items", []):
            if i.get("state") not in ("done", "sent", "dropped"):
                out[str(i.get("id", ""))] = ids
    return out
