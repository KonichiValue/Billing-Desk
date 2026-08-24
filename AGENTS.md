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
  before doing work.
- **"Check the codebase for X"** &mdash; the Kraken Core checkout is at
  `~/Projects/kraken-core`, not here. Read `~/Projects/kraken-core/AGENTS.md`
  before touching it, and never run `./src/manage.py` directly.
- **"What's the status of X"** &mdash; answer from the ticket's block, and follow
  the `threads` links if the answer is not there. Say plainly when the file is
  stale rather than guessing.

## "refresh"

One word, in a chat opened on this folder. **Read `prompt-refresh.md` and follow
it exactly.** It is the same routine `tg refresh` runs from the terminal, so the
answer should not depend on which one he used.

In short: sweep every open ticket in Asana, read the threads behind the open
items, put what you find in each ticket's timeline, move the items those events
affect, rebuild both files, and report only what changed. Closed items stay
closed and numbers never change.

`./tick.py` on its own prints the same status without spending a single token,
so use that when he only wants to know where he is.

## "prep" or "build the script"

**Read `prompt-prep.md` and follow it exactly.** Same routine as the Build script
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
```

**Sending a message is not finishing an item.** If a reply is expected, the item
goes to `-w <who>`, so the page shows it sitting with them rather than pretending
it is closed. Use plain `./tick.py <n>` only when nothing comes back.

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
7. **Respect a hold.** When an item says "do not send this yet", do not draft
   around it or send it because Rei asked casually. Say what it is waiting on and
   confirm he wants to override.

## Changing what lands on the pages

Edit the prompts, not the output. `prompt-refresh.md` is the sweep behind
"refresh", `prompt-prep.md` writes the script on top of that sweep, and
`prompt-post.md` folds the meeting note in. The shape in `board.py` is the
contract the renderers expect, so if you add a field, update `render_desk.py`,
`render_standup.py` and `render_desk_md.py` in the same change.

Do not hand-edit files in `output/`. They are regenerated from the board on
every page load.

## House style for this repo

Python is standard library only, no third-party packages. Shell is zsh. Commit
messages follow the "Prior to this change / This change" structure used in
`git log`, and use an `Assistant-model:` trailer rather than `Co-authored-by:`
for AI assistance.
