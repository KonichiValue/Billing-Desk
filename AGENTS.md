# AGENTS.md

Guidance for AI agents working in this repository.

## What this repo is

Rei's to-do list for the Tokyo Gas billing work. Every ticket open in his name
in the two TG Asana projects lives here, with the Slack threads it is discussed
in, what has happened on it, and the numbered items of work it has left. The
standup is one of the things that moves it, not the reason it exists.

`state/board.json` is the one durable file, and `board.py` documents it. Days
come and go, the standup happens or it does not, but an item keeps its number
until it is closed. Everything in `output/` is rendered from the board.

The page has two views off that one file. *My work* is what he does; *what I say*
is the words for the next session, from each ticket's `prep` block. Neither
carries its own status, so a script cannot contradict the list.

`news` on the board is the one part that is not his work: what moved around him
that will reach one of his tickets. Add a row only with the route named, and
take it off once that route closes.

**A ticket goes on the board because Asana assigns it to Rei, never because it
matters.** The board is his to-do list, not the programme's status. So a ticket
nobody has given him stays off it even when it is Top Priority, handled as an
incident, and the only thing the standup discussed: that is a `news` row, with the
route by which it reaches one of his tickets named, and nothing more. If work in a
chat turned up a real finding on it, a code trace or a count out of production,
the finding goes in that row rather than becoming an item, because an item is
something he does. Chasing who Kraken assign to a build is not his work and never
gets a number. The one exception is a ticket already on the board with an open item
of his on it: that stays until the item closes, however Asana's assignee field
moves.

`sessions` on the board is every room he still has to speak in, soonest first,
and `script.for_date` says which one the current script was written for. That
session may be an onsite rather than the 10:30 standup, which changes how much
preparation a ticket needs, so read it before writing anything for a meeting.

## When Rei asks you to act on his work

**Read `output/desk.md` first, before answering anything.** That is the board in
markdown: every ticket, its Asana status, its threads, its timeline and its
items, with the drafts already written. Say plainly when `checked_at` is hours
old rather than answering from a stale page.

Requests will usually be one of these, and they arrive without much context
because the context is in the file:

- **"Draft the reply to X"** &mdash; find the matching item, check whether it
  already has a `draft`, and improve it rather than starting over. Show the draft
  in chat and wait for approval. Never post it.
- **"Do 3"** &mdash; item numbers are permanent and unique across the board, so
  resolve the number from `state/board.json` and confirm which one you mean
  before doing work. Then do the part of it that does not need him, put the
  product in the item's `prepared` block with its sources, and leave him only the
  steps that need judgement, a person or a room. An item is not written until
  everything that could be done for him has been.
- **"Check the codebase for X"** &mdash; the Kraken Core checkout is at
 `~/Projects/kraken-core`, not here. Read `~/Projects/kraken-core/AGENTS.md`
 before touching it, and never run `./src/manage.py` directly.
- **"What does the data say"** &mdash; the production data this desk can reach is
 the `krakencore` Postgres analytics replica, declared as `ktdb-tg-krakencore`
 by `./setup-mcp.sh`. Not Databricks, whatever an older note may say. Read
 only: a `SELECT` to see how many accounts a hold covers or what a charge
 actually did is the point, and nothing here ever writes to it. Only
 `krakencore` is readable; `consumption`, `messaging` and `voice` sit on a
 different replica this account has no grant for, so do not build a query that
 needs them. A single account is usually faster to read on
 `support.tokyogas-kraken.energy/accounts/<A-...>`. Say which query or page an
 answer came from, and if the server is not there, say that instead of guessing.
 A missing server here almost always means the Cloudfarer session lapsed, which
 only he can fix with `kraken cloudfarer login`, so put it in `gaps`.
- **"What's the status of X"** &mdash; answer from the ticket's block, and follow
  the `threads` links if the answer is not there. Say plainly when the file is
  stale rather than guessing.

## A question asked from the page

Every job and every ticket on the desk carries an **Ask or change** box, and
`prompt-ask.md` is what runs behind it. The question arrives with the ticket, the
item, its draft and everything already asked about it attached, and the answer
goes back onto that card, in `state/asks.json`. Asked from inside an answer it is
a follow-up, and that exchange arrives above it, so "why" means the last thing
said and not the job. Half of what arrives there is an
instruction rather than a question, "rewrite this with the latest from the
thread" most often, so it edits the item and reports what it changed.

Two things follow for a chat working in this repo. `output/desk.md` carries those
questions and answers under the jobs they were asked about, so **read them before
contradicting one**: he is looking at that answer on the card. And when he asks
the same kind of thing in a chat, answer it the same way `prompt-ask.md` says to,
because the answer should not depend on where he asked.

The same box sits on the speaking view, where the card is the words rather than
the work. An ask from there arrives with the ticket's `prep` block and the session
it was written for, and a change means rewriting `prep.script` or `prep.pushback`
in full, in the house style, since he reads it out to TG.

One ask is not about a job. The box above the tickets asks about the day itself,
what to start on, whether tomorrow is covered, and it arrives with every open job
attached. Answer those in item numbers, and read the board rather than the titles
it hands you.

An ask may change the item it was asked about, and it may move where that job
stands when Rei tells it to: "close this", "this is with Kevin now". It does that
by running `./tick.py`, which is still the only thing that writes state, so the
move is timestamped into the item's history like any other. What it may not do is
infer the move. Concluding from a thread that something looks finished is not him
saying it is, and an ask may never send anything.

## "refresh"

One word, in a chat opened on this folder. **Read `prompt-refresh.md` and follow
it exactly.** It is the same routine `tg refresh` runs from the terminal, so the
answer should not depend on which one he used.

In short: sweep every open ticket in Asana, read the threads behind the open
items, put what you find in each ticket's timeline, move the items those events
affect, rebuild both files, and report only what changed. Closed items stay
closed and numbers never change.

`./tick.py` on its own prints the same status without spending a single token,
so use that when he only wants to know where he is. `./digest.py` prints the
whole readable board in one call, which is how a sweep should read it rather than
opening `state/board.json` a dozen times. It holds itself under 27k characters
so it stays inline, and `--item N` / `--ticket REF` print one record whole. A
sweep writes everything it found as one `tmp/patch.json` and applies it with
`./apply.py`, which goes through `board.save()`; the runner rebuilds afterwards.
`./tick.py --rebuild` redraws both pages without moving anything.

**Slack has no gate.** Asana's `modified_at` tells a sweep which tickets moved;
a Slack reply moves nothing on the board until a sweep reads it. So the digest's
step S names every Slack thread on a ticket with open work that spoke in the last
month, read from its recorded `last_at`, plus searches for his own messages,
his mentions, and the channels of older threads. Never add a "quiet, skip" rule
for Slack: one missed Rei's and Kevin's replies on item 50 on 7 Oct.

**Learning something in a chat is not a reason to leave the board stale.**
Whenever work in a chat turns up something that belongs on the page, a ticket
that moved, a draft that is now wrong, work you did on his behalf, put it on the
board and run `./tick.py --rebuild` in the same turn, without being asked. He
reads the page, not the chat, and a chat that knows more than the page is the one
failure this repo exists to prevent. That does not mean a full sweep every time:
write the thing you learned, rebuild, and say in one line what changed.

The rebuild half of that is for a chat and a terminal only. `serve.py` renders
both pages on every load, so an answer to the **Ask or change** box that spends a
step on `--rebuild` is a step Rei watches a spinner through for a page that was
going to be redrawn anyway. `prompt-ask.md` says so where it matters.

## "prep" or "build the script"

**Read `prompt-prep.md` and follow it exactly.** Same routine as the Write prep
button and `tg prep`: the refresh sweep first, then the speaking half. It writes
each ticket's `prep` block, `sessions` and `script`, and nothing else, so item
states stay where the sweep left them. Check which session you are writing for
before you start: an onsite needs decisions to land and answers to pushback, a
standup needs two sentences per ticket.

## When Rei says he has done something

Run `./tick.py` and nothing else. It records the state on the item in
`state/board.json` and rebuilds both files. Never hand-edit a page to mark
something done.

```
./tick.py                  # where everything is
./tick.py 4                # finished, nothing comes back
./tick.py 2 -w "Kevin"     # sent, ball is with Kevin
./tick.py 2 --mine         # they replied, it is his again
./tick.py 5 --dropped -n "TG answered it themselves"
./tick.py 1 --undo         # forget the state entirely
./tick.py 52 --draft 1     # posted draft 1; moves once its last draft has gone
```

**Sending a message is not finishing an item.** If a reply is expected, the item
goes to `-w <who>`, so the page shows it sitting with them rather than pretending
it is closed. Use plain `./tick.py <n>` only when nothing comes back.

On the page that is the **Posted it** button under every draft, which runs
`--draft K`: it waits on the draft's `reply_from` or the person its `target`
names, closes the job as sent when the draft has `"expects_reply": false`, and
keeps the job with him while another of its drafts is still to send. So a step
never tells him to run `./tick.py`; set those two fields instead, and
`audit.py` flags a step that forgets.

When the reply arrives, the follow-up stays on the same number: run `--mine`,
then edit that item on the board with the new draft and a `progress_note` saying
what already happened. Never add a new number for the next leg of a conversation
he is already in, because the numbers are how he refers to his work.

Read the board before answering "what's left". If Rei mentions doing something
that is not on it, say so rather than inventing a number. The pages show status
but cannot change it; the board is the only truth about what is closed.

## Hard rules that carry over from the source material

1. **Never send anything.** Every message to Slack, Asana, Notion or email is
   drafted in chat and waits for Rei's explicit approval, even when he says
   "handle it". This applies to replies you were asked to write.
2. **Language follows the reader.** Japanese to Tokyo Gas. English to Kraken
   colleagues, including CE, Markets, Core and Heqing Qian.
3. **Nothing internal reaches TG.** Story points, t-shirt sizes, refinement
   status, build-queue position, internal Asana ticket links and Kraken engineer
   names never appear in anything addressed to Tokyo Gas. Write エンジニア, not
   CE. This is a standing instruction from Heqing Qian and it has already been
   breached once.
4. **Write for what the reader can see.** Kraken engineers do not attend the TG
   standup and do not read the TG-shared Asana projects. Never cite a TG ticket,
   a TG comment or "the standup" to them as if they can look it up, and never use
   TG's case numbering without saying what it means unless that wording is
   already in the same thread. Say what was decided and what is still pending.
5. **Japanese to TG follows the house style.** ですます, natural complete
   sentences of roughly 25 to 50 characters, the team's own vocabulary rather
   than simplified substitutes (課金GAPホールド, 稼働確認, ホールド一覧, 期待値,
   ステートメント, インテグリティチェック, リゾルバ). Furigana as `{漢字|かんじ}`
   with the reading on the whole word, never per character.
6. **Never invent a source.** If you cannot quote the message something came
 from, say you could not find it.
7. **A Japanese term in an English line carries its meaning.** The page adds it
 from the board's `glossary`, once per card and once again in the script, so
 write the English plainly and add any missing term to `glossary` rather than
 writing the brackets by hand. An answer in a chat or on a card is not glossed
 for you, so gloss it yourself there: 閉栓翌日開栓 (open the day after close).
8. **Ask, don't propose, to engineers when AI did the reading.** A draft or
   ticket for CE, IE or any technical reader asks each technical point as a
   question from what TG said, what Rei saw or what an engineer already wrote.
   Function, list and file names and code-derived answers go in `prepared`, not
   the message. Follow `.claude/skills/ask-dont-propose/SKILL.md`.
9. **Respect a hold.** When an item says "do not send this yet", do not draft
   around it or send it because Rei asked casually. Say what it is waiting on and
   confirm he wants to override.

## Changing what lands on the pages

Edit the prompts, not the output. `prompt-refresh.md` is the sweep behind
"refresh", `prompt-prep.md` writes the script on top of that sweep,
`prompt-post.md` folds the meeting note in, and `prompt-ask.md` answers one
question about one job. The shape in `board.py` is the
contract the renderers expect, so if you add a field, update `render_desk.py`,
`render_standup.py` and `render_desk_md.py` in the same change.

The page is drawn by five modules, split so one job lives in one file:
`render_desk.py` (the shell, the ticket card, the top of the page),
`render_path.py` (the path to closing a ticket, its jobs, drafts and steps),
`render_week.py` (the week strip), `render_dialogs.py` (help and settings) and
`render_standup.py` (the speaking view). `render.py` holds what more than one of
them needs. `render_desk.render()` is still the entry point everything calls.

**Every job needs a day, or it is invisible on the week strip.** Two fields, and
which one depends on who is holding the work:

- His own work carries `urgency`, which is **exactly one of `today`,
  `this-week`, `monitor`** — hyphen, never a space. The strip reads it as a day:
  `today` is today, `this-week` is the next working day, `monitor` is off the
  strip. So an actionable job marked `monitor` is one he will not see coming.
- Work with somebody else carries `waits_on.chase_on`, an **ISO date and never a
  sentence**. A condition ("only if he raises it again") goes in
  `waits_on.what`; a sentence in `chase_on` is a job with no day.

`board.save()` refuses anything else, so a wrong value is an exception where it
was written rather than a job quietly missing from the page an hour later.
`./check.py` also asserts that everything the desk labels **Do now** has a place
on the strip.

**How the page looks and behaves lives in `static/`, not in the Python.**
`base.css` and `desk.css` and `standup.css` are the styles, `base.js` runs the
buttons and the live status, `desk.js` runs the ask boxes. The renderers read
them at render time and inline them, so a change to a stylesheet shows up on the
next page load with no restart, and `node --check` and any formatter can see the
JavaScript the way they could not while it was a Python string.

Do not hand-edit files in `output/`. They are regenerated from the board on
every page load.

**The open page reloads itself when the board moves.** `render.stamp()` is the
size and modification time of `state/board.json`, `state/asks.json`,
`state/calendar.json` and everything in `static/`, the page carries the one it was drawn from in
`data-stamp`, and `/api/status` reports the current one every couple of seconds.
So `./tick.py 26` in a terminal, a sweep on a schedule and an ask answered in
another tab all reach the page on their own. If you add another file the page is
drawn from, add it to `SOURCES` or the page will not notice it changing.

**Heqing's prioritization round comes from `prioritize.py`.** Every second
Monday (from 26 Oct 2026) she posts the build order in #team-jp-billing-cdl at
08:30; a round on a holiday runs the next working day, and `config.json`
`prioritization.moved` records any other move. The day that matters is the
working day before, the last chance to raise a build. The board's
`prioritization` block is his CE builds by CDL-Owner, nobody else's, and a
sweep rewrites it at step P. The desk draws it as a card under the milestone
with the note to Heqing ready to copy, and the week strip marks both days.
`./prioritize.py` prints the same; `--dates` lists the rounds ahead.

**His meetings come from `calendar_sync.py`, not the board.** It reads Google
Calendar through a one-tool headless Haiku run and writes `state/calendar.json`:
every meeting in the four weeks the strip flips through, with its Meet link and
any notes docs attached. A meeting is a fact about his week, not a job, so it
never goes on the board and a sweep never writes it. serve.py on 8787 reads it
hourly in working hours and again just after a work meeting ends, and
`POST /api/calendar` reads it now. Nothing ever writes to the calendar. When a
work meeting ends with Gemini notes that no `meeting_note`, `migration_note` or
`other_notes` row covers, `calendar_sync.unread_notes()` names it, the digest
lists it as step N, and the next refresh reads the doc and records it. A chat
asked about his day reads the Meetings section of `output/desk.md`.

It holds the reload back for one thing only: something half-written in a
composer, where taking the words away would be worse than the staleness. Then it
shows the amber Board changed button and waits, and for an Undo still on
screen after a status was moved. `tests/reload.js` is what keeps that true,
and `./check.py` runs it.

## Many writers, one board

A sweep, a prep, several asks from the page and a terminal `./tick.py` can all
be running at once, and they all write `state/board.json`. **`board.save()` is
the only safe way to write it.** It takes a lock on `state/board.lock`, reads
what is on disk, and merges field by field against the copy `board.load()` handed
out, so an ask that finished mid-sweep keeps its answer and the sweep keeps its
events. Items and tickets merge by id, `events`, `history` and `earlier` keep
both sides' additions, and two writers that each made a new item get two
numbers. So never edit the file with an edit tool, `sed` or a string replace,
and never `json.dump` it: that is the one write the merge cannot see, and it is
how good work used to vanish from the page.

Two more things `save()` holds for every model, whichever one is running:

- **An item never disappears.** A save that loses an item from a ticket still on
  the board raises. Close it with `./tick.py <n> --dropped -n "why"` instead.
- **Condensing never loses detail.** A finding or note taken out of a
  `prepared` block moves to `prepared.earlier`, dated, and the card shows it
  under an *Earlier detail* fold. Nobody writes `earlier` by hand.

Only sweeps exclude each other (`state/refresh.lock`). Asks run alongside a
sweep, four at a time, each with its own live progress line.

## The status, and what the page remembers

Every job's status on the page is a button, Jira's idea rather than Todoist's:
a checkbox can only say done, and half of these jobs end in "sent, now waiting
on somebody". Pressing it lists the moves open from where the job stands (with
you: sent and waiting on who, done, with someone else, dropped; waiting: they
replied, done, handed on, dropped; held: start it now; closed: open it again),
and each one posts `/api/tick`, which runs `./tick.py` like the terminal does.
That is Rei saying the job moved, so it is allowed; an agent inferring it is
still not. Undo puts back exactly the fields the tick moved. `j` `k` `x` `u` and
Enter work the To do list from the keyboard, `x` opening the status.

Theme, motion and which folds are open live in `state/prefs.json`, written by
`/api/prefs` and embedded in the page, so the desk looks the same in every
browser and on every port. localStorage is only a cache of it. `prefs.json` is
deliberately not in `render.SOURCES`: opening a fold should not reload the page.

## Which agent runs a button

`agent.py` is the only place that knows which CLI runs a job, on which model, and
how to read what it says back. `serve.py`, `bin/tg` and `run_post.sh` all ask it
rather than hard-coding a binary, so a refresh pressed on the page, typed in a
terminal or fired by launchd is the same run. Claude Code is first choice,
`cursor-agent` is the fallback behind it, and `TG_AGENT=cursor-agent` forces one.
Models come from `config.json` per job, overridable with `TG_REFRESH_MODEL` and
friends. Prompts go in on stdin, because `prompt-post.md` is 48KB and that is no
business of the command line.

A sweep is worth nothing without Asana and Slack, so `agent.blockers()` checks
them before a token is spent. A lapsed grant is not a refusal: the Refresh and
Write prep buttons and `tg refresh` walk the login first and only then refuse,
and a run that stops mid-way on a dead connection starts the login too. `./setup-mcp.sh` adds the
servers and walks the logins, `./setup-mcp.sh --check` and `tg mcp` report where
they stand. Only Rei can approve a grant in a browser, so a lapsed one goes in
`gaps` rather than being worked around.

Headless Claude Code has a real `Task` tool, which `cursor-agent` did not, and a
sweep that hands itself to a subagent loses the board. `prompt-refresh.md` and
`prompt-prep.md` forbid it by name; keep that wording if you touch them.

## Before you say you are done

```
./check.py
```

Both languages parse, every `fetch` handles a failure, the page still reloads
itself without eating his typing, the board is a shape the renderers can
survive, both pages render, and anything out of date is listed.
It takes under a second, it never writes, and it fails loudly on the two faults
that have actually taken this page down: a promise chain with no `.catch()`, and
a board field holding the wrong type.

`board.save()` refuses a board that would not render, so a shape error is an
exception at the point of writing rather than a broken page an hour later. Fix
the item and save again; the file on disk is untouched until the board is sound.

## House style for this repo

Python is standard library only, no third-party packages, and the front end has
no build step or framework for the same reason: the whole thing has to still run
in two years with nothing installed. `node` is used by `./check.py` to parse the
JavaScript if it happens to be there, and the check says so and carries on if it
is not. Shell is zsh. Commit
messages follow the "Prior to this change / This change" structure used in
`git log`, and use an `Assistant-model:` trailer rather than `Co-authored-by:`
for AI assistance.
