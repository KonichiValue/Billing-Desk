#!/usr/bin/env python3
"""Everything that can be checked without a person looking at the page.

Most of what goes wrong here is not a bug in the logic. It is a shape: a field
holding a dict where every reader expects a string, a promise chain with no
`.catch()`, a renderer that throws halfway down a card. Those are cheap to catch
and expensive to find by reloading the page and squinting.

This is the gate to run after editing anything in this repo, and it is fast
enough that there is no reason not to. It never writes.

    ./check.py            everything
    ./check.py --quiet     one line per section, for a hook

What it does not check is whether the words are right. That still needs reading.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import audit  # noqa: E402
import board as B  # noqa: E402


class Result:
    def __init__(self) -> None:
        self.sections: list[tuple[str, list[str]]] = []

    def add(self, name: str, problems: list[str]) -> None:
        self.sections.append((name, problems))

    @property
    def total(self) -> int:
        return sum(len(p) for _, p in self.sections)


def python_parses() -> list[str]:
    """Every module still parses. The cheapest possible check, and it has caught
    a truncated edit more than once."""
    bad = []
    for path in sorted(ROOT.glob("*.py")) + sorted(ROOT.glob("bin/*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            bad.append(f"{path.name}:{exc.lineno}: {exc.msg}")
    return bad


def javascript_parses() -> list[str]:
    """The scripts, through a real parser.

    This is the check that could not exist while the JavaScript lived inside
    Python string literals, and it is the one that would have caught the polling
    bug that left a card spinning with its answer already written to disk.
    """
    node = shutil.which("node")
    if not node:
        return ["node is not installed, so the JavaScript went unchecked"]
    bad = []
    for path in sorted((ROOT / "static").glob("*.js")):
        done = subprocess.run(
            [node, "--check", str(path)], capture_output=True, text=True, check=False
        )
        if done.returncode != 0:
            first = (done.stderr or "").strip().splitlines()
            bad.append(f"static/{path.name}: {first[0] if first else 'failed'}")
    return bad


def chain_end(text: str, start: int) -> int:
    """Where the call chain beginning at `start` finishes.

    Walked rather than pattern-matched, because a `.then()` body is full of its
    own semicolons and parentheses, and the first version of this check stopped at
    the first `;\\n` inside a callback and reported two chains as uncaught that
    both ended in `.catch()`. A check that cries wolf is worse than no check: he
    stops reading it, and the real one goes past him with the rest.
    """
    depth, at, size = 0, text.index("(", start), len(text)
    quote = ""
    while at < size:
        char = text[at]
        if quote:
            if char == "\\":
                at += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                # One call closed. If another link follows, keep going.
                nxt = at + 1
                while nxt < size and text[nxt].isspace():
                    nxt += 1
                word = re.match(r"\.(then|catch|finally)\s*\(", text[nxt:])
                if word:
                    at = nxt + word.end() - 1
                    depth = 0
                    continue
                return at + 1
        at += 1
    return size


def promises_are_caught() -> list[str]:
    """A `fetch` whose chain never handles a rejection.

    One dropped request used to kill the status loop for good, and the card spun
    until he reloaded the page with the answer already written to disk. No parser
    sees that, and it is the single most likely thing to go wrong in this file, so
    it gets its own check.
    """
    bad = []
    for path in sorted((ROOT / "static").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\bfetch\(", text):
            chain = text[match.start() : chain_end(text, match.start())]
            if ".catch(" in chain:
                continue
            bad.append(
                f"static/{path.name}:{text[: match.start()].count(chr(10)) + 1}: "
                f"fetch with no .catch(), so a dropped request fails silently."
            )
    return bad


def pages_render() -> list[str]:
    """Both pages come out of the real board without throwing.

    A renderer that dies on one field takes the whole page with it, so this is
    the difference between finding out here and finding out in front of him.
    """
    try:
        import render_desk
        import render_desk_md
    except Exception as exc:  # an import error is a real failure here
        return [f"could not import the renderers: {type(exc).__name__}: {exc}"]
    data = B.load()
    bad = []
    for name, fn in (("output/desk.html", render_desk.render),
                     ("output/desk.md", render_desk_md.render)):
        try:
            text = fn(data)
            if len(text) < 1000:
                bad.append(f"{name} rendered only {len(text)} bytes, which is empty")
        except Exception as exc:
            bad.append(f"{name} threw {type(exc).__name__}: {exc}")
    return bad


def board_shape() -> list[str]:
    return B.check(B.load())


def board_freshness() -> list[str]:
    data = B.load()
    rep = audit.Report()
    for one in audit.CHECKS:
        one(data, rep)
    return [line.strip() for lines in rep.groups.values() for line in lines]


CHECKS = (
    ("Python parses", python_parses),
    ("JavaScript parses", javascript_parses),
    ("Every fetch handles a failure", promises_are_caught),
    ("The board is the shape the renderers expect", board_shape),
    ("Both pages render", pages_render),
    ("The board is up to date", board_freshness),
)

# The board being stale is a thing for a refresh to fix, not a broken repo, so it
# is reported and does not fail the run.
ADVISORY = {"The board is up to date"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true", help="one line per section")
    args = ap.parse_args()

    result = Result()
    for name, fn in CHECKS:
        result.add(name, fn())

    failed = 0
    for name, problems in result.sections:
        mark = "ok  " if not problems else ("note" if name in ADVISORY else "FAIL")
        if problems and name not in ADVISORY:
            failed += len(problems)
        print(f"[{mark}] {name}" + (f", {len(problems)}" if problems else ""))
        if problems and not args.quiet:
            for line in problems[:12]:
                print(f"         {line}")
            if len(problems) > 12:
                print(f"         and {len(problems) - 12} more")

    print()
    if failed:
        print(f"{failed} things to fix before this is worth loading.")
        return 1
    stale = sum(len(p) for n, p in result.sections if n in ADVISORY)
    if stale:
        print(f"Nothing broken. {stale} things are out of date, which a refresh fixes.")
    else:
        print("Nothing broken, nothing out of date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
