# TG billing desk

The to-do list for the Tokyo Gas billing work. Every ticket open in your name in
the two TG Asana projects, the Slack threads it is argued out in, what has
happened on it, and the numbered work it has left. A Dock app opens it, a
Refresh button brings it up to date, and the numbers stay put.

**The board is the product.** `state/board.json` holds the tickets and the
items; `board.py` documents it. An item is with you, with somebody else, or
finished, and it keeps its number until it closes, so "do 4" means the same
thing next week. Everything else in the repo either writes to the board or draws
it.

Two scheduled runs feed it, because the standup is the day's forcing function:

| | When | What it does |
|---|---|---|
| **Morning prep** | 09:10, Mon/Wed/Thu | A separate briefing page: what to know and say at 10:30. |
| **Standup fold-in** | from 11:00, same days | Reads the meeting note and moves the board. |

The split is deliberate. Before the standup you have 30 minutes and you spend
them reading, so the morning page is for preparing, not working. Replies,
investigation and ticket updates wait for the desk.

The desk is written twice: `output/desk.html` to read, `output/desk.md` to hand
work back from. Open a Cursor chat in this repo and say "draft the reply to
Nakayama-san" or "check the codebase for X", and `AGENTS.md` points the agent at
the markdown so it starts with the full picture.

## Morning prep

1. Finds every open Asana ticket assigned to Rei in the two TG shared projects,
   in the order they appear on the 2-week cycle board.
2. Reads the full comment history on each one, plus the linked internal Kraken
   build ticket.
3. Searches Slack (public, private and DMs) for anything said about those
   tickets that never made it into Asana.
4. Traces what each agreed fix does **not** cover: what falls outside it, what
   piles up because of that, who owns the pile, and what cleanup means. This is
   where the real questions come from, and it is the step that stops TG raising
   something you had not thought about.
5. Writes a Japanese speaking script with furigana and English translations.
6. Renders `output/prep-<date>.html` and opens it.

**Do first** holds at most three rows and is usually empty. An item only
qualifies if a message has been waiting on you for more than a working day, or
TG will raise it at 10:30 and you cannot answer cold.

```sh
./run_prep.sh            # skips if today's page already exists
./run_prep.sh --force    # rebuild from scratch, ignoring a cancelled standup
./run_prep.sh --no-open  # build only
```

`PREP_MODEL` picks a model. `PREP_TIMEOUT` changes the watchdog, default 900.

## The standup fold-in

1. Finds today's `Billing Stand Up` meeting note in Notion and reads both the
   summary and the **full transcript**. The transcript is the valuable half:
   pushback, undecided forks and quiet takeaways only exist there.
2. Loads the morning JSON so it can show what the meeting changed.
3. For each ticket, gathers **every conversation it lives in**: the Asana ticket,
   the internal build ticket, the CE refinement thread, the CE help thread, the
   Heqing DM. Threads get read in full, because a reversal lands in reply 30 and
   an engineer saying "actually this is harder than I thought" outranks anything
   said in the room.
4. Opens new items for what the meeting created, and moves the ones it answered.
   Existing numbers are reused, never reassigned.
5. Records anything other people owe you on the item it blocks, with a chase
   date, so there is no second list of waits to reconcile.
6. Writes the replies you now owe, each one sitting inside the item it belongs
   to.

**Everything is grouped by ticket.** One block per ticket holds its Asana status,
where it stands, the timeline, the items, the drafts, what is undecided and every
thread it lives in. The only cross-ticket structure is the running order at the
top, which the page derives rather than anyone writing.

The Notion note lands about five minutes after the meeting ends, but meetings
overrun. So each attempt is a cheap agent run that exits immediately when the
note is missing, and the runner retries every five minutes until 11:45.

```sh
./run_post.sh            # polls until the note appears
./run_post.sh --force    # fold today's note in again
./run_post.sh --once     # single attempt, fail if the note isn't up yet
```

`POST_MODEL`, `POST_TIMEOUT` (900), `POST_DEADLINE` (11:45) and `POST_RETRY`
(300 seconds) all override.

## Getting at it during the day

Run `./install.sh` once. It puts **TG Billing Desk** in `~/Applications`, which you
drag to the Dock, and links `tg` into `~/.local/bin`. Both point at this
checkout, so pulling changes updates them; rerun it after any change to `bin/tg`.

Clicking the Dock icon opens the desk in its own window, no tabs and no address
bar. Behind it, `serve.py` runs on `127.0.0.1:8787` and renders the page on every
load, so what you see at four in the afternoon reflects everything you have
ticked off. It starts on first use and stays up; `tg stop` ends it.

That server is also what makes the **Refresh** button in the page header work. It
runs the same routine as `tg refresh`: the button asks the server, the server
runs the agent, the page reports progress and reloads itself when the work
lands. If `cursor-agent` is not logged in, the button says so rather than
failing quietly. Opening the HTML file directly still works and simply has no
button, since a `file://` page has nothing to send the click to.

```
tg              open the desk, print where everything sits
tg s            status only, costs nothing
tg 4            item 4 is finished
tg 2 -w Kevin   sent, now sitting with Kevin
tg 2 --mine     he replied, it is yours again
tg refresh      sweep every open ticket and thread, rebuild, open
tg chat         open the folder in Cursor to hand work over
tg build        re-render the page from the board, no agent
tg post         fold today's Notion meeting note in again
```

`refresh` also works as a single word typed into a Cursor chat on this folder.
Both routes run `prompt-refresh.md`, so the answer does not depend on which one
you used: it sweeps every ticket still open in Asana, reads the threads behind
your open items, adds what it finds to each ticket's timeline, and moves the
items those events affect. It never reopens a closed item and never renumbers.

## Keeping the list honest

An item is with you, with somebody else, or finished. Sending a message usually
moves it to the middle one, because the reply comes back on the same number and
the work is not over.

```sh
./tick.py                            # where everything is
./tick.py 4                          # finished, nothing comes back
./tick.py 2 -w "Kevin"               # sent, ball is with Kevin
./tick.py 2 --mine                   # they replied, it is yours again
./tick.py 5 --dropped -n "TG answered it themselves"
./tick.py 1 --undo                   # forget the state entirely
```

The desk opens with **Where you are**: one list, yours at the top, then what you
are not allowed to send yet, then what sits with someone else. Finished work
folds away behind a count. Each line carries how it got there, so a waiting row
says who has it and since when, and the minutes count only what is still yours.

The pages are read-only about status, deliberately. A page opened from disk
cannot write to disk, so a checkbox on it could only ever remember a tick inside
one browser, and a control that looks authoritative while the chat and the state
file know nothing about it is worse than no control. Close things by saying so in
chat, or with `tick.py`.

State lives on the item in `state/board.json`, so rebuilding a page never loses
it and nothing has to be reconciled across days. That file is also how a chat in
this repo knows where you are without you explaining: `AGENTS.md` tells the agent
to run `./tick.py` rather than editing a page by hand.

## Reminders

`POST_REMIND=1` pushes the open items into an Apple Reminders list called
`TG billing` at the end of a run. Anything with you is due that day, anything
held or sitting with someone else is due on its chase date and says so in the
title. The note carries the why, the link and the draft. Finished items are
skipped, and re-running replaces the list rather than duplicating it.

```sh
python3 remind.py state/board.json --dry-run
python3 remind.py state/board.json --list "Work"
```

macOS asks for Reminders access the first time, so run it once by hand before
relying on it in the scheduled job.

## Cancelled standups

Standups get skipped for onsites and workshops, and it is only ever said out
loud. The post-standup agent listens for it and writes `state/skip-next.json`
with the date of the meeting that is not happening. The morning job reads that
file and shows a short "no standup today" page instead of building a prep it
does not need. `--force` overrides.

If the agent is not confident about the date it writes nothing and flags it in
`gaps`, because a missing prep page is worse than a redundant one.

## Reading the pages

- Ticket cards run top to bottom in the order you need them: the issue, where it
  stands, what the fix does not cover, how it got here, then the script.
- **What I say today** is meant to be read aloud verbatim. Furigana sits above
  the kanji, English underneath, and each block has a copy button that copies the
  Japanese without the markup.
- The amber **Check before 10:30** box holds unknowns and hard cautions,
  including anything you must not say to TG.
- **Script only** strips the morning page back to the Japanese at a larger size.
- On the desk, the running order links straight down to the ticket, each ticket
  header carries what Asana currently says about it, a red border means you
  committed to it out loud, and a draft always sits inside the item that needs
  it. Anything not with you is folded shut.
- Both pages are plain HTML. Keep them, mail them, print them.

## Pieces

| File | What it is |
|---|---|
| `prompt.md` | Morning agent instructions and output schema. |
| `prompt-post.md` | How the standup gets folded into the board, plus the board schema. |
| `AGENTS.md` | How a Cursor chat in this repo picks up today's list and acts on it. |
| `config.json` | Project GIDs, user GIDs, meeting time, Slack channel hints. |
| `board.py` | The board: what it holds, how state moves, where numbers come from. |
| `render.py` | Morning JSON into HTML, plus the shared CSS, the lifecycle and the error page. No network, no LLM. |
| `render_desk.py` | The board into `output/desk.html`. |
| `render_desk_md.py` | The board into `output/desk.md`, for handing work back in chat. |
| `tick.py` | Move items along and rebuild. The only way state gets recorded. |
| `serve.py` | The local page server: renders on every load, and runs the agent when the Refresh button asks. Loopback only, keyed. |
| `bin/tg` | The one command. Opens the window, moves items along, starts a refresh. |
| `install.sh` | Links `tg` and builds the Dock app. Safe to rerun. |
| `prompt-refresh.md` | What "refresh" means, for the button and for a chat alike. |
| `app/` | The icon generator and the Tokyo Gas mark. The Kraken mark is read from `~/Projects/kraken-core` at build time. |
| `run_prep.sh` | Morning entry point. Guards, skip check, timeout, error page. |
| `run_post.sh` | Afternoon entry point. Polls for the Notion note, then folds it in. |
| `launchd/` | The two schedules. |
| `output/` | `desk.html` and `desk.md`, both rendered from the board, plus the morning prep pages. |
| `state/` | `board.json`, the one durable file, and `skip-next.json` when a standup has been cancelled. |
| `logs/` | `run.log` for both runners, `agent-<date>.log` and `agent-post-<date>.log` for raw agent transcripts. |

## Furigana markup

The agents write `{漢字|かんじ}` and the renderers turn it into real ruby
annotations. The reading goes on the whole word, not per character:
`{託送番号|たくそうばんごう}`, never `{託|たく}{送|そう}`.

## Schedule

Both jobs fire on Mon, Wed and Thu, at 09:10 and 11:00. If the Mac is asleep at
that time `launchd` runs the job as soon as it wakes, so opening the laptop at
09:30 still gets you the morning page. Neither runner rebuilds a page it already
built that day.

```sh
launchctl unload ~/Library/LaunchAgents/com.tg-billing-desk.prep.plist
launchctl load  ~/Library/LaunchAgents/com.tg-billing-desk.prep.plist
launchctl list | grep -E "tg-(morning-prep|post-standup)"
```

To change the days or times, edit the plist in `launchd/`, copy it over the one
in `~/Library/LaunchAgents/`, then unload and load.

## Requirements

- `cursor-agent` on the PATH and logged in (`cursor-agent login`).
- Asana, Slack and Notion MCP servers configured in `~/.cursor/mcp.json`.
- `python3`. No third-party packages.

## Any model, any assistant

Nothing here is tied to one model. Neither runner names one, so both use whatever
`cursor-agent` defaults to, and `PREP_MODEL` and `POST_MODEL` override per run:

```sh
POST_MODEL=gpt-5.6-sol-high ./run_post.sh --force
```

The prompts name the Asana, Slack and Notion tools as those MCP servers expose
them today, and both say to use the equivalent if a toolset names them
differently rather than skipping the step. The renderers and `tick.py` are plain
Python with no model involved at all, so the desk can always be rebuilt from the
board.

`CLAUDE.md` and `GEMINI.md` are symlinks to `AGENTS.md`, so an assistant that
looks for its own filename finds the same instructions.

## When it breaks

Both pages still open, showing the error and pointing at the agent log. Most
likely causes, in order: `cursor-agent` logged out, an MCP server needing
re-auth, or the agent writing malformed JSON. For the last one, `--force`
usually fixes it.
