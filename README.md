# TG billing standup

Two pages a day for the Tokyo Gas billing standup, both self-contained HTML,
both opening themselves in the browser.

| | When | What it answers |
|---|---|---|
| **Morning prep** | 09:10, Mon/Wed/Thu | What do I need to know and say at 10:30? |
| **Post-standup list** | from 11:00, same days | What do I do now, in what order? |

The split is deliberate. Before the standup you have 30 minutes and you spend
them reading, so the morning page is for preparing, not working. Replies,
investigation and ticket updates all wait for the afternoon page.

The afternoon page is also written as markdown, `output/post-<date>.md`. That is
the version to hand work back from: open a Cursor chat in this repo and say
"draft the reply to Nakayama-san" or "check the codebase for X", and `AGENTS.md`
points the agent at today's file so it starts with the full picture. The HTML is
for reading, the markdown is for delegating, and both come from the same JSON.

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

## Post-standup list

1. Finds today's `Billing Stand Up` meeting note in Notion and reads both the
   summary and the **full transcript**. The transcript is the valuable half:
   pushback, undecided forks and quiet takeaways only exist there.
2. Loads the morning JSON so it can show what the meeting changed.
3. For each ticket, gathers **every conversation it lives in**: the Asana ticket,
   the internal build ticket, the CE refinement thread, the CE help thread, the
   Heqing DM. Threads get read in full, because a reversal lands in reply 30 and
   an engineer saying "actually this is harder than I thought" outranks anything
   said in the room.
4. Ranks everything by what happens if you do nothing today, commitments made in
   front of TG first.
5. Records anything other people owe you, with a chase date, and the forks nobody
   has been assigned to decide.
6. Writes the replies you now owe, each one sitting inside the action it belongs
   to.

**Everything is grouped by ticket.** One block per ticket holds where it stands,
what changed today, what to do, the drafts, who you are waiting on, what is
undecided, and every thread it lives in. The only cross-ticket structure is the
running order at the top, which tells you which ticket to open first.

The Notion note lands about five minutes after the meeting ends, but meetings
overrun. So each attempt is a cheap agent run that exits immediately when the
note is missing, and the runner retries every five minutes until 11:45.

```sh
./run_post.sh            # polls until the note appears
./run_post.sh --force    # rebuild today's list
./run_post.sh --once     # single attempt, fail if the note isn't up yet
```

`POST_MODEL`, `POST_TIMEOUT` (900), `POST_DEADLINE` (11:45) and `POST_RETRY`
(300 seconds) all override.

Every action has one number, unique across the page, and the running order is
built from those numbers rather than written separately. So "do 4" always means
the same thing, and the table and the ticket sections cannot disagree.

## Keeping the list honest

An action is with you, with somebody else, or finished. Sending a message
usually moves it to the middle one, because the reply comes back on the same
number and the work is not over.

```sh
./tick.py                            # where everything is
./tick.py 4                          # finished, nothing comes back
./tick.py 2 -w "Kevin"               # sent, ball is with Kevin
./tick.py 2 --mine                   # they replied, it is yours again
./tick.py 5 --dropped -n "TG answered it themselves"
./tick.py 1 --undo                   # forget the state entirely
```

Both pages open with **Where you are**: one checklist, yours at the top, then
what you are not allowed to send yet, then what sits with someone else, then
what is finished. Each line carries how it got there, so a waiting row says who
has it and since when. The minutes count only the work still with you.

The checkboxes on the HTML page are live. Ticking one is remembered in that
browser and the page shows the `./tick.py` line that makes it stick, since the
page cannot write to disk on its own. Telling the chat works just as well.

Progress lives in `state/progress-<date>.json`, not in the report, so
regenerating the report keeps it. That file is also how a chat in this repo knows
where you are without you explaining: `AGENTS.md` tells the agent to run
`./tick.py` rather than editing the page by hand.

## Reminders

`POST_REMIND=1` pushes the actions into an Apple Reminders list called
`TG standup` at the end of a run. Anything actionable is due that day, anything
held is due on its chase date and titled "(waiting)". The note carries the why,
the link and the draft. Re-running replaces that day's reminders rather than
duplicating them.

```sh
python3 remind.py output/post-2026-08-24.json --dry-run
python3 remind.py output/post-2026-08-24.json --list "Work"
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
- On the afternoon page, the running order links straight down to the ticket, a
  red action border means you committed to it out loud, and a draft always sits
  inside the action that needs it.
- Both pages are plain HTML. Keep them, mail them, print them.

## Pieces

| File | What it is |
|---|---|
| `prompt.md` | Morning agent instructions and output schema. |
| `prompt-post.md` | Post-standup agent instructions and output schema. |
| `AGENTS.md` | How a Cursor chat in this repo picks up today's list and acts on it. |
| `config.json` | Project GIDs, user GIDs, meeting time, Slack channel hints. |
| `render.py` | Morning JSON into HTML, plus the shared CSS, the error page and the cancelled-standup notice. No network, no LLM. |
| `render_post.py` | Post-standup JSON into HTML. Imports the shared styling from `render.py`. |
| `render_md.py` | Post-standup JSON into markdown, for handing work back in chat. |
| `tick.py` | Close actions and rebuild both pages. The only way progress gets recorded. |
| `run_prep.sh` | Morning entry point. Guards, skip check, timeout, error page. |
| `run_post.sh` | Afternoon entry point. Polls for the Notion note. |
| `launchd/` | The two schedules. |
| `output/` | Per day: the morning JSON and HTML, the afternoon JSON, HTML and markdown. |
| `state/` | `skip-next.json` when a standup has been cancelled, `progress-<date>.json` for what you have closed, `open-loops.json` for holds carried across days. |
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
launchctl unload ~/Library/LaunchAgents/com.tg-billing-standup.prep.plist
launchctl load  ~/Library/LaunchAgents/com.tg-billing-standup.prep.plist
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
Python with no model involved at all, so a page can always be rebuilt from its
JSON.

`CLAUDE.md` and `GEMINI.md` are symlinks to `AGENTS.md`, so an assistant that
looks for its own filename finds the same instructions.

## When it breaks

Both pages still open, showing the error and pointing at the agent log. Most
likely causes, in order: `cursor-agent` logged out, an MCP server needing
re-auth, or the agent writing malformed JSON. For the last one, `--force`
usually fixes it.
