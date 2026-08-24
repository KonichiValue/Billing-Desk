# TG morning prep

Builds a standup prep page for the Tokyo Gas billing standup and opens it in the
browser. Runs itself on Monday, Wednesday and Thursday at 09:10.

## What it does

1. Finds every open Asana ticket assigned to Rei in the two TG shared projects.
2. Reads the full comment history on each one, plus the linked internal Kraken
   build ticket.
3. Searches Slack (public, private and DMs) for anything said about those
   tickets that never made it into Asana.
4. Works out what has to happen before 10:30 and ranks it.
5. Writes a Japanese speaking script with furigana and English translations.
6. Renders the lot as `output/prep-<date>.html` and opens it.

## Running it by hand

```sh
./run_prep.sh            # skips if today's page already exists
./run_prep.sh --force    # rebuild from scratch
./run_prep.sh --no-open  # build only
```

`PREP_MODEL=<model>` picks a specific model. `PREP_TIMEOUT=<seconds>` changes the
watchdog, which defaults to 900.

## The page

- **Do first** is the ranked action list. Six rows maximum, with an estimated
  minute count so the whole thing fits in your 30 minutes.
- Each ticket card runs top to bottom in the order you need it: the issue, where
  it stands, how it got there, then the script.
- **What I say today** is meant to be read aloud verbatim. Furigana sits above
  the kanji, English underneath each line, and each block has a copy button that
  copies the Japanese without the furigana markup.
- The amber **Check before 10:30** box holds both open unknowns and hard
  cautions, including anything you must not say to TG.
- **Script only** in the top right strips the page back to just the Japanese at
  a larger size, for reading during the call.
- The page is self-contained HTML. Keep it, mail it, print it.

## Pieces

| File | What it is |
|---|---|
| `prompt.md` | The agent instructions and the output schema. Edit this to change what ends up on the page. |
| `config.json` | Project GIDs, user GIDs, meeting time, Slack channel hints. |
| `render.py` | Turns the agent's JSON into the HTML page. No network, no LLM. |
| `run_prep.sh` | Entry point. Guards, timeout, error page, opens the browser. |
| `launchd/com.tg-morning-prep.plist` | The schedule. |
| `output/` | One JSON and one HTML per day. |
| `logs/` | `run.log` for the runner, `agent-<date>.log` for the raw agent transcript. |

## Furigana markup

The agent writes `{漢字|かんじ}` and `render.py` turns it into real ruby
annotations. The reading goes on the whole word, not per character.

## Schedule

`launchd` fires at 09:10 on Mon, Wed and Thu. If the Mac is asleep or off at
09:10 it runs as soon as it wakes, so opening the laptop at 09:30 still gets you
the page. `run_prep.sh` will not rebuild a page it already built that day, so a
second wake just reopens the existing one.

```sh
launchctl unload ~/Library/LaunchAgents/com.tg-morning-prep.plist
launchctl load  ~/Library/LaunchAgents/com.tg-morning-prep.plist
launchctl list | grep tg-morning-prep
```

To change the days or the time, edit the plist in `launchd/`, copy it over the
one in `~/Library/LaunchAgents/`, then unload and load.

## Requirements

- `cursor-agent` on the PATH and logged in (`cursor-agent login`).
- The Asana and Slack MCP servers configured in `~/.cursor/mcp.json`.
- `python3`. No third-party packages.

## When it breaks

The page still opens, showing the error and pointing at
`logs/agent-<date>.log`. Most likely causes, in order: `cursor-agent` logged
out, an MCP server needing re-auth, or the agent writing malformed JSON. For the
last one, `./run_prep.sh --force` usually fixes it.
