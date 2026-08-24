# Billing desk

The to-do list for the Tokyo Gas billing work. Every ticket open in your name in
the two TG Asana projects, the Slack threads it is argued out in, what has
happened on it, and the numbered work it has left. A Dock app opens it, a
Refresh button brings it up to date, and the numbers stay put.

**The board is the product.** `state/board.json` holds the tickets and the
items; `board.py` documents it. An item is with you, with somebody else, or
finished, and it keeps its number until it closes, so "do 4" means the same
thing next week. Everything else in the repo either writes to the board or draws
it.

**One page, two views.** *My work* answers "what do I do". *What I say* answers
"what comes out of my mouth in the next meeting", in the order that meeting walks
the board, with the Japanese script. Same tickets, same file, and `1` and `2`
switch between them. A ticket that needs airtime carries a *raise at* pill on the
work view and appears under its script; a ticket in the script links back to its
open items. Neither view has a status of its own, so a script can never
contradict the list.

The colour means one thing everywhere: red is with you, amber is blocked, blue is
with somebody else, green is closed. The speaking view runs on warmer paper with a
plum accent, so you can see which view you are in without reading the tab.

Three things put work on the board, and the standup is the day's forcing
function:

| | When | What it does |
|---|---|---|
| **Refresh** | any time you press it | Sweeps every open ticket and thread, moves what changed. |
| **Build script** | when you sit down before a meeting | Refresh, then writes what you say in the next session. |
| **Standup fold-in** | from 11:00, Mon/Wed/Thu | Reads the meeting note and moves the board. Scheduled, because the note appears while you are still in meetings. |

Before a standup you have 20 minutes and you spend them reading, so the speaking
view is for preparing. Replies, investigation and ticket updates wait for the
work view afterwards.

The desk is written twice: `output/desk.html` to read, `output/desk.md` to hand
work back from. Open a Cursor chat in this repo and say "draft the reply to
Nakayama-san" or "check the codebase for X", and `AGENTS.md` points the agent at
the markdown so it starts with the full picture.

## The script

Press **Build script** in the app, or run `tg prep`. Nothing is scheduled for the
morning, deliberately: you build it when you sit down, so it is written against
the replies that landed overnight rather than against 09:10.

1. Runs the full refresh first, so the script sits on the newest state.
2. Puts your tickets in the order the cards appear on the 2-week cycle board, and
   says roughly when you are up.
3. Traces what each agreed fix does **not** cover: what falls outside it, what
   piles up because of that, who owns the pile, and what cleanup means. This is
   where the real questions come from, and it is the step that stops TG raising
   something you had not thought about.
4. Writes the Japanese you say out loud, with furigana above the kanji and
   English underneath, plus the questions you need TG to answer.
5. Marks the items that can only be closed in the meeting, so they show on both
   views.

A ticket with nothing outstanding gets a two-line 現状 block and says *status
only*. That is a good thing to report in one breath, and padding it wastes
standup time.

Internal build tickets, story points, refinement status and delivery dates never
reach the script. They stay on the desk side, where they are for you.

## The standup fold-in

1. Finds today's `Billing Stand Up` meeting note in Notion and reads both the
   summary and the **full transcript**. The transcript is the valuable half:
   pushback, undecided forks and quiet takeaways only exist there.
2. Reads the board so it can show what the meeting changed.
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

Run `./install.sh` once. It puts **Billing Desk** in `~/Applications`, which you
drag to the Dock, and links `tg` into `~/.local/bin`. Both point at this
checkout, so pulling changes updates them; rerun it after any change to `bin/tg`.

Clicking the Dock icon opens the desk in its own window, no tabs and no address
bar. Behind it, `serve.py` runs on `127.0.0.1:8787` and renders the page on every
load, so what you see at four in the afternoon reflects everything you have
ticked off. It starts on first use and stays up; `tg stop` ends it.

That server is also what makes the **Refresh** and **Build script** buttons in
the header work: the button asks the server, the server runs the agent, the page
reports progress and reloads itself when the work lands. Both take the same lock,
so a terminal run and a button press can never write the board at once.

Before spending anything, the server checks that `cursor-agent` is signed in and
that the Asana and Slack connections are authorised. When they are not, the page
says which one and the **Log in** button walks them one browser approval at a
time. That check exists because an agent with no tools does not stop, it
improvises. Opening the HTML file directly still works and simply has no buttons,
since a `file://` page has nothing to send a click to.

```
tg              open the desk, print where everything sits
tg s            status only, costs nothing
tg 4            item 4 is finished
tg 2 -w Kevin   sent, now sitting with Kevin
tg 2 --mine     he replied, it is yours again
tg refresh      sweep every open ticket and thread, rebuild, open
tg prep         sweep, then write the script for the next session
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

The desk opens with **Everything you are carrying**: one list, yours at the top,
then what you are not allowed to send yet, then what sits with someone else.
Finished work folds away behind a count. Each line carries how it got there, so a
waiting row says who has it and since when, and the minutes count only what is
still yours. Every row also says *when*: Do now, Held to Wednesday, Chase today,
or "No chase date" when nothing has been set and the thing could sit for ever.

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

## Onsites, and standups that are not happening

The next meeting is not always the 10:30 standup. Onsites and workshops replace
it, and it is only ever said out loud in the room, so both agents listen for it
and keep `sessions` on the board: what kind of session, when, what it is for, and
which standup it displaces.

An onsite is a day rather than fifteen minutes, so the speaking view carries more
for one: the shape of the day and what to have ready at the top, then per ticket
what has to be **settled before you leave the room**, up to six script blocks
instead of four, and the answer ready for the pushback you can see coming. The
work view says what is next and, when the script in the app was written for a
different session, says that too rather than letting you walk in with the wrong
one.

A skipped standup stays visible, because any ask that was waiting for it now has
to move into Asana instead. If an agent is not confident about a date it records
nothing and flags it, since a missing warning beats a wrong one.

## Reading the page

- `1` shows your work, `2` what you say, `s` strips everything but the Japanese
  at a larger size, `/` finds anything, `?` explains the whole thing. The tab you
  were on survives a reload, each view remembers where you had scrolled to, and
  the morning of a session opens on the script when one has been built and the
  meeting has not started yet.
- **Jump to** sits under the banner with every ticket on it, and the chip for the
  card you are looking at lights up as you scroll. `/` opens a finder over the
  page that takes a ticket tag, an item number or any word from a title.
- On the work view, **Everything you are carrying** is one list: yours at the top,
  then what you may not send yet, then what sits with someone else, with finished
  work folded away behind a count. Each ticket header carries what Asana currently
  says about it, every value labelled with its field, and links out live on their
  own row underneath. A draft always sits inside the item that needs it.
- **Around you at TG** is the news panel: things that are not your tickets but
  move them, each with the route by which it reaches you and a link to where it
  was said.
- Inside a card the sections are colour-keyed by what they are for. Red is the
  work, blue is the short answer and the timeline, amber is undecided, and grey
  reference sections (shorthand, threads, a day where nothing moved) start folded.
- On the speaking view, cards run in board order: the issue in 20 seconds, where
  it stands, what the fix does not cover, what has to be settled today, then the
  script.
- **What I say** is meant to be read aloud verbatim. Furigana sits above the
  kanji, English underneath, and each block copies the Japanese without the
  markup.
- The amber **Check before you speak** box holds unknowns and hard cautions,
  including anything you must not say to TG.
- It is plain HTML in one file. Keep it, mail it, print it.

## Pieces

| File | What it is |
|---|---|
| `board.py` | The board: what it holds, how state moves, where numbers come from. |
| `prompt-refresh.md` | What "refresh" means, for the button, `tg refresh` and a chat alike. |
| `prompt-prep.md` | The script: the sweep, then what goes in `prep`, standup or onsite. |
| `prompt-post.md` | How the standup gets folded into the board. |
| `AGENTS.md` | How a Cursor chat in this repo picks up the list and acts on it. |
| `config.json` | Project GIDs, user GIDs, meeting time, Slack channel hints. |
| `render.py` | Shared styling, furigana, item lifecycle and the common blocks. No network, no LLM. |
| `render_desk.py` | The board into `output/desk.html`, both views in one file. |
| `render_standup.py` | The speaking view inside that file, standups and onsites. |
| `render_desk_md.py` | The board into `output/desk.md`, for handing work back in chat. |
| `tick.py` | Move items along and rebuild. The only way state gets recorded. |
| `serve.py` | The local page server: renders on every load, runs an agent when a button asks, and walks the sign-in when something is not authorised. Loopback only, keyed. |
| `bin/tg` | The one command. Opens the window, moves items along, starts a run. |
| `install.sh` | Links `tg`, builds the Dock app, keeps the server running. Safe to rerun. |
| `app/` | The icon generator: the Kraken mark over a ticked list, read from `~/Projects/kraken-core` at build time. No client mark, so the app fits whoever the work is for. |
| `run_post.sh` | The fold-in entry point. Polls for the Notion note, then folds it in. |
| `launchd/` | The fold-in schedule and the page server. |
| `output/` | `desk.html` and `desk.md`, both rendered from the board. |
| `state/` | `board.json`, the one durable file. |
| `logs/` | `refresh-<date>.log`, `prep-<date>.log` and the fold-in logs. |

## Furigana markup

The agents write `{漢字|かんじ}` and the renderers turn it into real ruby
annotations. The reading goes on the whole word, not per character:
`{託送番号|たくそうばんごう}`, never `{託|たく}{送|そう}`.

## Schedule

Only two things run on their own. The fold-in fires from 11:00 on Mon, Wed and
Thu and retries until the Notion note appears, because that note lands while you
are still in meetings. The page server starts at login and stays up, so the Dock
app always finds it. Everything else is a button.

If the Mac is asleep at 11:00, `launchd` runs the job as soon as it wakes.

```sh
launchctl kickstart -k "gui/$UID/com.tg-billing-desk.post"
launchctl list | grep tg-billing
```

To change the days or times, edit the plist in `launchd/`, copy it over the one
in `~/Library/LaunchAgents/`, then `launchctl bootout` and `bootstrap` it.

## Requirements

- `cursor-agent` on the PATH and logged in (`cursor-agent login`).
- Asana, Slack and Notion MCP servers configured in `~/.cursor/mcp.json`.
- `python3`. No third-party packages.

## Any model, any assistant

Nothing here is tied to one model. Nothing names one, so every run uses whatever
`cursor-agent` defaults to, and `TG_MODEL` or `POST_MODEL` override per run:

```sh
TG_MODEL=gpt-5.6-sol-high tg prep
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

The page still opens, since it renders from the board and the board is only
written by a run that finished. Most likely causes, in order: the Asana or Slack
connection needing re-auth, `cursor-agent` signed out, or an agent writing
malformed JSON. The first two are what the Log in button is for. For the last,
run it again.

```sh
tail -f logs/refresh-$(date +%F).log
tail -f logs/serve.log
```
