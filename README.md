# TG standup prep

Two pages a day for the Tokyo Gas billing standup, both self-contained HTML,
both opening themselves in the browser.

| | When | What it answers |
|---|---|---|
| **Morning prep** | 09:10, Mon/Wed/Thu | What do I need to know and say at 10:30? |
| **Post-standup list** | from 11:00, same days | What do I do now, in what order? |

The split is deliberate. Before the standup you have 30 minutes and you spend
them reading, so the morning page is for preparing, not working. Replies,
investigation and ticket updates all wait for the afternoon page.

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
3. Re-reads Asana and the Heqing DM, because decisions reached verbally often get
   written up within minutes and then you do not need to do it again.
4. Ranks everything by what happens if you do nothing today, commitments made in
   front of TG first.
5. Records anything other people owe you, with a chase date.
6. Writes the Japanese replies you now owe, ready to copy.

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
- On the afternoon page, a red left border means you committed to it out loud.
- Both pages are plain HTML. Keep them, mail them, print them.

## Pieces

| File | What it is |
|---|---|
| `prompt.md` | Morning agent instructions and output schema. |
| `prompt-post.md` | Post-standup agent instructions and output schema. |
| `config.json` | Project GIDs, user GIDs, meeting time, Slack channel hints. |
| `render.py` | Morning JSON into HTML, plus the shared CSS, the error page and the cancelled-standup notice. No network, no LLM. |
| `render_post.py` | Post-standup JSON into HTML. Imports the shared styling from `render.py`. |
| `run_prep.sh` | Morning entry point. Guards, skip check, timeout, error page. |
| `run_post.sh` | Afternoon entry point. Polls for the Notion note. |
| `launchd/` | The two schedules. |
| `output/` | One JSON and one HTML per page per day. |
| `state/` | `skip-next.json`, when a standup has been cancelled. |
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
launchctl unload ~/Library/LaunchAgents/com.tg-morning-prep.plist
launchctl load  ~/Library/LaunchAgents/com.tg-morning-prep.plist
launchctl list | grep -E "tg-(morning-prep|post-standup)"
```

To change the days or times, edit the plist in `launchd/`, copy it over the one
in `~/Library/LaunchAgents/`, then unload and load.

## Requirements

- `cursor-agent` on the PATH and logged in (`cursor-agent login`).
- Asana, Slack and Notion MCP servers configured in `~/.cursor/mcp.json`.
- `python3`. No third-party packages.

## When it breaks

Both pages still open, showing the error and pointing at the agent log. Most
likely causes, in order: `cursor-agent` logged out, an MCP server needing
re-auth, or the agent writing malformed JSON. For the last one, `--force`
usually fixes it.
