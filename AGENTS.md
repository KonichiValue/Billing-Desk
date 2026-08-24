# AGENTS.md

Guidance for AI agents working in this repository.

## What this repo is

Two generated pages a day for Rei's Tokyo Gas billing standup: a prep page before
it and an action list after it. See `README.md` for how they are built.

## When Rei asks you to act on the standup

**Read `output/post-<today>.md` first, before answering anything.** That file is
today's action list, grouped by ticket, with every Asana link, Slack thread and
draft already gathered. If it does not exist, check for `output/post-<recent
date>.md` and say which day you are working from. `output/prep-<today>.md` does
not exist; the morning page is HTML plus `output/prep-<today>.json`.

Requests will usually be one of these, and they arrive without much context
because the context is in the file:

- **"Draft the reply to X"** &mdash; find the matching action, check whether it
  already has a `draft`, and improve it rather than starting over. Show the draft
  in chat and wait for approval. Never post it.
- **"Do action 3"** &mdash; the numbers refer to the running order table at the
  top of the markdown, so resolve them from there and confirm which one you mean
  before doing work.
- **"Check the codebase for X"** &mdash; the Kraken Core checkout is at
  `~/Projects/kraken-core`, not here. Read `~/Projects/kraken-core/AGENTS.md`
  before touching it, and never run `./src/manage.py` directly.
- **"What's the status of X"** &mdash; answer from the ticket's block, and follow
  the `threads` links if the answer is not there. Say plainly when the file is
  stale rather than guessing.

## When Rei says he has done something

Run `./tick.py <numbers>` and nothing else. It records the state in
`state/progress-<date>.json` and rebuilds both pages, so the list stops claiming
work that is finished. Never hand-edit the report to mark something done.

```
./tick.py              # what is left
./tick.py 1 3          # close 1 and 3
./tick.py 2 -n "note"  # close with a note
./tick.py 4 --dropped  # closed because it stopped being needed
./tick.py 1 --undo     # reopen
```

Read `state/progress-<today>.json` before answering "what's left". If Rei
mentions doing something that is not on the list, say so rather than inventing a
number for it.

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
7. **Respect a hold.** When the list marks an action "do not send this yet", do
   not draft around it or send it because Rei asked casually. Say what it is
   waiting on and confirm he wants to override.

## Changing what lands on the pages

Edit the prompts, not the output. `prompt.md` drives the morning page and
`prompt-post.md` the afternoon one; the schema at the bottom of each is the
contract the renderers expect. If you add a field, update the matching renderer
in the same change, and check both `render_post.py` and `render_md.py` for the
afternoon page.

Do not hand-edit files in `output/`. They are regenerated.

## House style for this repo

Python is standard library only, no third-party packages. Shell is zsh. Commit
messages follow the "Prior to this change / This change" structure used in
`git log`, and use an `Assistant-model:` trailer rather than `Co-authored-by:`
for AI assistance.
