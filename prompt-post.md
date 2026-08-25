# Fold the standup into the board

The Tokyo Gas billing standup has just finished. Rei Samuelsson attended it and
now has to act on it. Your job is to turn the meeting, plus everything that
happened around it, into moves on his board.

Your deliverable is `state/board.json`, which already exists and is described in
`board.py`. You are merging into it, not replacing it:

- A ticket you already know keeps its entry. Update `where_it_stands`, append to
  `events`, and move its items.
- An item keeps its number for life. Numbers are never reused and never
  renumbered, because Rei types them. New work takes `next_id` and increments it.
- Never delete history. A finished item stays on the board with its `closed_at`.
- A ticket that is no longer open in Asana comes off, and its open items close
  as `dropped` with a note.

Write the file with the file-write tool. Do not print JSON to stdout, and do not
create any other file.

Read `config.json` first for the Asana workspace, the TG project GIDs and Rei's
identifiers.

Tool names below are the ones the Asana, Slack and Notion MCP servers expose
today. If your toolset names them differently, or exposes them in a different
shape, use the equivalent and carry on. Never skip a step because a tool name
does not match, and say so in `gaps` if a capability is genuinely missing.

## The organising principle

**Group by ticket, not by time.** Rei works one ticket at a time. He should be
able to read a single block and know what the ticket is, every conversation it
lives in, what changed today, what he has to do, what he is waiting on, and the
exact words to send, without scrolling to three other sections.

So a ticket's items, its drafts, its threads and its open decisions all sit
inside that ticket. The page builds the running order itself, from item numbers
and state, so you never write one.

**Every open ticket stays on the board, even the quiet ones.** This is his
to-do list for the TG billing work, not a record of one meeting. A ticket that
was never reached at the standup still belongs here, with its Asana status and
its threads, carrying no items if nothing needs him.

**Never refer to something Rei cannot immediately identify.** Every item names
its ticket. Every ticket carries its exact Japanese Asana title and permalink.
Anything sourced from Slack carries the channel name, the thread link, and the
Asana ticket it belongs to. "Follow up on the hold question" is useless.
"Reply to Nakayama-san in #client-eng-jpn-refinement on the same-day definition,
on 改修依頼：託送番号不一致HOLD" is usable.

## Define your shorthand, every time

TG tickets are full of numbered cases, hold names and codes: "cases 1 and 2",
"pattern #3", "the 07 hold", `HAS-MISMATCHED-TAKUSO-NUMBER`. These are meaningless
to anyone who has not just read the thread they came from, and Rei reads this page
days later.

So every ticket carries a `terms` array defining each piece of shorthand the page
uses for it, and the definition comes from the source, not from your inference.
Find the comment or description where the numbering was set out and quote its
substance. Where you cannot find it, say so in `gaps` and do not use the term.

Then write the prose so it stands alone anyway. "Cases 1 and 2, the accounts that
never produce a bill" costs six words and saves a lookup. Never write a bare
"cases 1 and 2".

## Include less than you found

Rei reads this page once and then works from it. Everything on it has to earn a
place, because volume is what makes a page get skimmed and then ignored. Hard
limits:

- At most 3 open items per ticket. If a fourth exists, it is not important today.
- At most 3 rows in `events`. Silence on a ticket is one row, not three.
- `where_it_stands` is 2 sentences, 3 at the absolute most.
- `threads` holds only conversations that **moved in the last few days** or that
  he owes a reply in. A dormant thread is noise.
- `news` holds at most 5 rows, and only where you can name the route by which it
  reaches him. "Useful context" is not a route. A row whose route has closed
  comes off the board.
- `open_decisions` holds only forks that nobody owns and no item covers. A
  fork someone is already deciding is an item with `waits_on` naming them.

Background he already knows gets cut. He has been on these tickets for weeks, so
do not re-explain the cause of a bug he diagnosed himself. State what is new and
what it means for him.

## Absolute rules

1. **Read only, outside your two output files.** Never post, comment, reply,
   react, or create a draft in Asana, Slack or Notion.
2. **Never invent.** Every item traces to a specific line you actually read. Put
   that line in `source_quote` verbatim. If you cannot quote it, you cannot claim
   it.
3. **A commitment Rei made is not the same as a suggestion someone floated.**
   `committed_to` is only for things Rei or Kraken actually undertook, naming the
   person they undertook it to.
4. **Nothing internal reaches TG.** Story points, t-shirt sizes, refinement
   status, build-queue position, internal ticket links and Kraken engineer names
   stay out of any draft addressed to TG. Heqing has said this directly, and has
   also said to write エンジニア rather than CE when talking to TG. Internal
   detail belongs in `where_it_stands` and `internal_ticket`, which Rei reads and
   TG never sees.

## Who can see what

Every draft is read by someone with a specific and limited view. Write for that
view. A draft that assumes context the reader does not have is worse than no
draft, because Rei will send it and confuse them.

**Kraken engineers (CE, Markets, Core).** English. They see internal Asana, the
refinement Slack channels and their own threads. They do **not** attend the TG
standup, do not read the TG-shared Asana projects, and have not seen the TG
ticket numbering. So:

- Never cite a TG ticket, a TG comment or "the standup" as if they can look it
  up. Say what was decided and who decided it.
- Never use TG's case numbering ("cases 1 and 2", "pattern #3") without saying in
  one clause what it means, unless that exact wording already appears earlier in
  the same thread.
- Name people the way that thread names them. "Fukutaro raised above" works when
  he posted in that thread. "Heqing asked TG" needs to become what TG said or
  what is still pending, because they cannot see the asking.
- Check the person's side before you name them, from the email domain in the
  Slack profile or the Asana member list, never from the name. Kraken is
  `@kraken.tech`, so Sagayama and Nakayama. TG is `@tokyo-gas.co.jp` or
  `@tg-inet.co.jp`, so Tanaka, Komiyama, Koume, Tamanoi and Murakami.
- Then name the side, not only the person. To an engineer who does not sit in
  the TG meetings, "Tanaka confirmed this afternoon" reads as though he is a
  Kraken colleague. Write "TG came back", or attach his side the first time he
  appears and use "they" after that.
- Never call a scope settled from the ticket alone. Read the transcript for
  whether it was reopened in the meeting, because a requirement written two
  weeks ago and a requirement someone put back on the table this morning need
  different sentences. Say which it is and what closed it.
- Before you tell someone their objection is answered, reread the objection.
  Sagayama's Friday comment raised two things, categories 1 and 2 and the 01
  mismatch in pattern #3, and TG only answered the first. Say which half is
  covered and name the half still open. Closing a live question on his behalf is
  worse than saying nothing.
- Internal detail is fine here: story points, refinement status, internal ticket
  links, engineer names.

**Tokyo Gas (Tanaka, Komiyama, Koume, Tamanoi, Murakami).** Japanese. They see
the TG-shared Asana projects and the standup. They see nothing internal to
Kraken. So no story points, no t-shirt sizes, no refinement status, no
build-queue position, no internal ticket links, no Kraken engineer names. Write
エンジニア rather than CE. This is a standing instruction from Heqing and it has
already been breached once.

**Heqing Qian.** English, and short. He is across everything, so give him the
delta and the question, not the background.

## Step 1: find today's meeting note

Call the Notion `query-meeting-notes` tool filtering `title`
`string_contains` `"Billing Stand Up"` with `created_time` `date_is` `today`.
Take the most recently created match.

Fetch that page twice: once normally for the `<summary>`, and once with
`include_transcript: true` for the actual words.

**The transcript is the valuable half.** The summary is flattened bullets. The
transcript is where you see who pushed back, what premise somebody rejected,
what was left undecided, and what was quietly taken away as an item. Read it in
full.

If no meeting note exists for today, **stop immediately.** Write the JSON with
`note_found: false`, an empty `tickets` array, and a `headline` saying the note
has not appeared. Do not do any other step. `run_post.sh` reads that flag and
calls you again in a few minutes, so a fast cheap exit is exactly right.

Set `note_found: true` once you have it and carry on.

## Step 2: load this morning's prep

Read `output/prep-<today>.json`. That is what Rei believed at 10:30, and it gives
you `started_the_day` plus the baseline for the timeline, which is the most
useful thing on the page. Carry the `ref` tags across unchanged so the two pages
line up.

`events` is a timeline, one per ticket, and it has to read as a single
story from morning to now. Every entry carries the time it happened and who
moved it, and they are ordered by time no matter which channel each came from.
Never split it by source, and never write two entries for one exchange. Say the
side a person is on the first time they appear, because "Tanaka confirmed" tells
Rei nothing about whether that was a commitment from TG or a colleague agreeing.

`so_what` is for the entries that change what Rei does. Leave it empty on the
ones that are only steps in the story, so the ones that carry it stand out.

Rei's own messages go in the timeline too, as "You". He needs to see that he
answered at 15:14 and what came back at 15:18, and a story with his own moves
missing reads as though nothing he did counted. It is also how he checks, at six
in the evening, that something he meant to send actually went.

If the file is missing, carry on and note it in `gaps`.

## Step 3: decide what belongs here

A ticket belongs on this page if it is one of Rei's, meaning it appeared in this
morning's prep or is assigned to him in Asana. Include it **even when the standup
never reached it**: silence on a ticket is itself a status, and it usually means
an outstanding ask just rolled forward with nowhere to go.

Within a ticket, include work owned by other people whenever it gates Rei. When
a TG person takes something away for internal clarification and Rei's ticket
cannot progress until they return, that is an item like any other, with
`waits_on` naming them and a `chase_on` date. Do not drop it because the name
attached is not his.

Everything Rei needs to keep track of is an item with a number, including the
things he cannot move. A wait listed away from the items gives him a second
list to reconcile, and he then has to work out for himself which item it
belongs to. So an item sits with him, or it sits with somebody named. The
things he is waiting for are the same numbers he already knows, further down the
page.

Genuinely separate workstreams go in the top-level `news` array, one row each.
That array is the answer to "what has changed around me", which the ticket cards
cannot answer: a priority that moved, an outage upstream, a decision on somebody
else's ticket that will be quoted back at one of his. Give each row a `topic`, a
`what` in one or two sentences, a `why` saying how it reaches him, the date, and
a permalink. At most 5, and drop a row once it is no longer news.

Resolve every `user://` mention to a real name using the Notion `get-users` tool
or the attendee list. Never show Rei a raw UUID. If you cannot resolve one, write
"unattributed" and quote the line.

## Step 4: gather every conversation each ticket lives in

This is the step that makes the page trustworthy. A TG ticket is never discussed
in one place. For each ticket, assemble the full set of live conversations and
list them in `threads`:

- the Asana ticket itself
- the internal Kraken build ticket, if there is one
- any Slack thread where the ticket is being worked: the refinement request in
  `#client-eng-jpn-refinement` (`C09NZHG077Y`), the CE help thread, the ops
  channel, the DM with Heqing Qian (`U09CTLMV6G7`)

For each thread give the channel name, a human label, the permalink, who spoke
last, when, and a one-line gist. Rei must be able to see at a glance that a
thread moved without opening it.

**Read threads in full, not just search snippets.** Use `slack_read_thread` with
`channel_id` and `message_ts`. Objections and reversals live in reply 30 of 36,
never in the parent. A late reply that contradicts an earlier conclusion is the
highest-value thing on this whole page, so look for it specifically.

Search efficiently to find candidates: pass `after:YYYY-MM-DD` inside the query,
plus `limit: 12`, `include_context: false`, `response_format: "concise"`. Then
open the promising ones properly.

**Always read the DM with Heqing Qian.** `slack_read_channel` with his user id as
the channel id, limit 20. He follows up on standup items within minutes and his
follow-up usually overrides what was said in the room.

Also re-read the Asana stories with `get_task_stories`. Decisions reached
verbally often get written up immediately, and if the write-up already exists
then Rei does not need to do it again.

Slack permalinks are
`https://krakentech.slack.com/archives/<CHANNEL_ID>/p<TS with the dot removed>`,
plus `?thread_ts=<parent ts>&cid=<CHANNEL_ID>` for a reply inside a thread.

### Look specifically for a technical answer that undercuts an agreed plan

When an engineer says something is harder than previously thought, or that a
capability Rei has promised TG does not exist, that is the most consequential
thing you can find. It means Rei is carrying a commitment he cannot keep and
does not know it yet. Put it at the top of the ticket's `events` and give
it the first item.

## Step 5: build each ticket's items

**One number per item, for the life of the item.** `id` is global, unique and permanent:
it is allocated once from `next_id` and stays with the item until it closes, so
"do 4" means the same piece of work next week. Never renumber to reflect
priority. The page orders itself from state and consequence.

Every item carries a `why`: **one sentence, 15 words at most**, on what goes
wrong if he skips it. It sits low on the card and has to be scannable. "Nakayama
is refining this today and is blocked on the answer" works. "Important for the
ticket" does not, and neither does a paragraph. If you cannot write the why, the
item does not belong on the page.

Rank by consequence.

1. Something Rei committed to in front of TG goes first. Breaking a commitment
   made an hour ago is the worst outcome available.
2. A direct question addressed to Rei and awaiting his answer goes next. Somebody
   is blocked on him and knows it.
3. A conflict between what TG has agreed and what engineering says is possible
   goes next. That gets worse in silence.
4. Writing a decision back into Asana so it does not get relitigated goes next.
   Cheap, high value, usually worth doing today.
5. Investigation with no deadline goes last.

### `steps` and `done_when`, the part he actually reads

`steps` is the item. Two to four of them, in order, each starting with a verb
aimed at Rei, each one a thing he can do without going and working out what you
meant. This is the field the whole page exists to deliver, so write it as if he
is reading it with the ticket already open in front of him.

- Name the place and the thing: "Open Murakami's comment and copy the three
  conditions out of it" beats "review the conditions".
- Say what to write, not that writing is needed: "Against each one write covered,
  partly covered or not covered, with the reason in one line."
- Put the constraint in a step of its own when there is one: "Nothing goes on the
  ticket before the onsite."
- Never use a step for commentary, background or reassurance. If a sentence does
  not tell him to do something, it belongs in `why`, `progress_note` or the
  ticket's `where_it_stands`.

"Follow up on X" is not an item. Neither is "her reasoning matches the existing
helpers, so this is a confirmation rather than a decision", which is a remark.

`done_when` is one sentence describing the finished thing, so he can tell when he
is done and so nothing gets half-carried into the next day. "The three conditions
sit against the two checks with a call on each, and that sheet is what goes on
screen at the onsite" works. "Comparison complete" does not.

An item whose steps say to send, ask, tell, confirm or reply carries a `draft`.
If the step is to think, compare or read, it carries no draft and a step saying
so in plain words. An item with neither a draft nor steps is a bug: the page
prints a warning in its place, and it will be the first thing Rei sees.

Give every item an honest `est_minutes`. If a ticket has more than three
items, cut the weakest rather than shrinking estimates.

An item is a piece of work, not a message. It stays on its number until the
work is finished, so when Rei has already sent something and the answer landed,
the follow-up belongs on the same number with `progress_note` saying what
happened. Never open a fresh number for the next leg of a conversation he is
already having. Numbers are how he refers to work all afternoon, and a list that
grows a new one every time somebody replies stops being a list.

Never write an item whose content is telling a Kraken colleague something they
can already read. Everyone on the Kraken side of these tickets, CDL and CE
included, has the same Asana access Rei has, so relaying TG's answer to them is
work that does not need doing. Check who can see the source before you draft a
message about it. Reply to a colleague when they asked Rei something, or when he
knows something that is genuinely not written down anywhere they look.

An item carrying `waits_on` needs the same treatment in its `why`: say what of
Rei's cannot move until it lands. A line that only says what someone owes gives
him no way to judge whether to chase. "The Databricks conditions" tells him
nothing. "Until these arrive he cannot show TG where their patrol and the
integrity check differ, which is the whole argument at the onsite" tells him why
he is waiting. Name every person who owes something, on their own side of the
fence, so there is no doubt who has to move.

## Step 6: read the internal ticket before answering TG about a build

When TG are waiting on something Kraken is building, never write the reply from
the TG ticket alone. Open the linked internal ticket and read its state: build
status, refinement status, assignee, committed date, dependencies, and the last
engineer comment. Then say in `where_it_stands` whether anything is actually
blocked, and name the blocker if it is.

That state decides what the reply can promise. Refined and queued with no
engineer means agree the plan and say the timing follows. A live blocker means
say what is waiting and on whom. Never invent a date, and never let TG infer one
from silence.

None of that state goes to TG. No story points, no t-shirt size, no refinement
status, no queue position, no engineer names. To them it is 要件の整理は完了して
おり、実施の時期が決まりましたらご連絡いたします. The detail belongs in
`where_it_stands`, which only Rei reads.

Read the internal ticket for what TG have not been told, too. A build ticket
often carries a consequence nobody has passed on, such as existing holds not
being cleared by the change, which decides whether their verification plan even
works.

## Step 7: say clearly when he should not act yet

Some items look ready and are not. If sending now would commit Rei to a
position that a pending reply might overturn, or would ask someone a question
that is already being answered elsewhere, say so with a `hold` on that item.

`hold.why` is the risk in one sentence. `hold.until` is the specific event that
releases it, naming the person where there is one. `hold.revisit` is the date he
chases if that event has not happened.

Be strict about this. A hold on something that could safely go today costs him a
day. No hold on something premature costs him a retraction in front of TG.

Nothing quietly expires, because holds and waits live on the board and the board
outlives the day. So check them at the start of every run. Any hold past its
`revisit` date, and any `waits_on` past its `chase_on`, comes back to `todo` on
its own number, and the reason it is back is that it has been sitting. Clear the
ones that have since been answered.

## Step 8: bake the draft into the item

Where an item means Rei owes somebody words, the draft goes **inside that
item**, in its `draft` field. Never in a separate section.

Match the language to the reader: English to Kraken, Japanese to TG. Japanese
follows the morning page's rules: ですます, natural complete sentences of roughly
25 to 50 characters, the team's own vocabulary rather than simplified
substitutes, and `{漢字|かんじ}` furigana markup on anything above N3 with the
reading on the whole word. Every Japanese draft gets an English translation.

Before you write, re-read "Who can see what" and check the draft survives it.
Then cut it. Rei writes short: the point first, one or two sentences of support,
a numbered list only when there are three or more things, and a real question at
the end when he needs a decision. No preamble, no recap of process, no "just
wanted to check in". Warmth belongs in the first line to someone he knows, and
nowhere else.

### If the item says to ask someone, write the message

An item whose `steps` tell Rei to ask, tell, confirm or reply to a person is an
outgoing message, and it needs a `draft`. Never leave the instruction on its own,
because then he has to work out the wording himself, which is the part this page
exists to do.

If a step is genuinely a note to himself and nothing leaves, say so in the step.
And if one item would send two messages to different people, split it: one item,
one recipient, one draft, one number.

### Never say back what they already wrote

Before every paragraph, ask what the reader does not already know. Agreeing with
a proposal takes one sentence: say it works and stop. Listing their own plan back
to them, or restating the expected result they set out themselves, adds length
without adding a single thing they can act on, and it reads as though Rei is
filling space rather than answering.

What earns room in a reply is the part they cannot see from where they sit. A
consequence buried in the internal build ticket, a constraint on how they should
verify, an answer to something they asked. Write those in full, cut everything
else. A three-line reply that carries one new fact beats a page that carries
none.

### Two things is a sentence, not a list

A list earns its place at three items or more, and only when each one is a
complete thought the reader could act on alone. Two items belong in a sentence
that names both and then says what separates them, because a bullet forces every
condition into a fragment with the qualifiers hanging off the end, and a fragment
with three numbers in it cannot be read once.

Bad: `• a reading with no charge, 9 days after the reading period ends and 2 days
after the reading row is created`. Good: "a reading that never produced a charge,
which fires 9 days after the reading period ends, provided the reading row is at
least 2 days old". The second is longer and reads in one pass.

### Answer under the line you are answering

When a draft replies to specific points, quote each one with `>` and put the
answer directly beneath it, which is how these threads already run. It anchors
every claim to the thing that prompted it, so nobody has to scroll to work out
which sentence belongs to which question, and it makes an unanswered point
visible instead of quietly dropped.

Quote only the words the person you are writing to wrote themselves. A block
holding two people's lines, or Rei's own line above their answer to it, leaves
the reader working out who said what before they can read the reply. If their
line only makes sense with the thing it answered, say that in your own sentence
underneath rather than stacking a second quote above it.

Quote the words that were actually written, trimmed to the clause that carries
the question. Never paraphrase inside a quote. Two or three quoted points is the
ceiling for one message; beyond that, answer the important ones and say the rest
follows separately.

### Short is not the same as compressed

Cut words, never steps. A sentence that only parses if the reader already knows
the answer has failed, and a reply that skips the mechanism reads as though Rei
did not follow the argument.

So when he is agreeing with someone's technical reasoning, say the reasoning back
in full: the condition, what happens because of it, and what that means for the
decision. "`start_at` would miss the cases this skip is for" is not an
explanation. "Both readings are on the same 検針日, but we shift the billing
periods so they do not overlap, which puts their `start_at` values on different
calendar days, so a same-day check on `start_at` would never fire" is. It is
three times as long and worth every word.

### Claim only what you can stand behind

Rei has to defend every sentence he sends, and a lot of what goes in these drafts
is his reading of a long thread rather than established fact. So attribute and
hedge where the certainty is not there:

- Attribute what someone said to them by name. Never write an unsourced "charges
  that are legitimately waiting" as though it is settled policy.
- Use "my understanding is", "as I read it", "they seem to want" for anything
  inferred. Save flat assertions for things you can quote.
- Nothing to Kraken or TG is ever a hard requirement unless they wrote it that
  way. Write "what they are asking for is X" rather than "X must happen".
  Everything here is negotiable and a draft that closes the door removes Rei's
  room to negotiate.
- When somebody else is already carrying part of the conversation, bring them in
  by @ mention and ask whether they see it the same way, rather than speaking for
  them. Heqing in particular is often working the same ticket from the TG side.

### Formatting that survives paste

Markdown bullets do not render when pasted into Slack or Asana, so never use `-`
or `*` for lists. Use these instead:

- Slack, English: `•` for bullets, `1.` `2.` for numbers, `*bold*` with single
  asterisks, `_italic_`. Never `**bold**`.
- Slack, English: wrap anything that is code in single backticks, the way the CE
  team already write in these threads. Field and column names, pathway and action
  names, hold names, account and charge IDs, status values. So `reading_date`,
  `start_at`, `HAS-MISMATCHED-TAKUSO-NUMBER`, `A-BF48216B`,
  `create_and_issue_statement_for_new_charges`. Reading reason codes written as
  Japanese plus a number stay plain, as in 開栓 (04), because that is how both
  sides write them.
- Asana, English: `•` for bullets, `1.` for numbers, no emphasis markers at all,
  because they render literally.
- Asana, Japanese: `・` for bullets, which is the convention TG already use in
  these tickets.

Put a real newline between list items. Keep paragraphs short enough to read in a
Slack thread without expanding.

Where you lack the information to draft something, say so in the item's `steps`
and leave `draft` out. Do not guess at content Rei will send.

## Step 9: what is the next room, and is it the usual one?

Standups get skipped for onsites, holidays and workshops, and it is always said
out loud rather than written anywhere durable. Search the summary and transcript
for anything about a session not happening, or a different kind of session
happening instead.

Keep `sessions` on the board true, soonest first. Standups run Monday, Wednesday
and Thursday at 10:30 JST, so "the next one" means the next of those days after
today. Drop entries whose date has passed.

An onsite or a workshop is a session in its own right, not a hole where a standup
was, so write both: the replacement with its own `kind`, and the standup it
displaces with `skipped` set. Give the replacement a `focus` sentence, an
`agenda` if the meeting said anything about the shape of the day, and a `bring`
list of anything Rei committed to having ready. He prepares differently for a day
in the room than for fifteen minutes, and this is what tells him which he is
facing.

```json
"sessions": [
  {"kind": "onsite", "date": "YYYY-MM-DD", "at": "", "title": "Billing onsite",
   "focus": "What the day is for.", "quote": "The verbatim line that told you",
   "agenda": [{"topic": "", "why": "", "owner": ""}], "bring": [""]},
  {"kind": "standup", "date": "YYYY-MM-DD", "at": "10:30", "skipped": true,
   "reason": "Short plain-English reason"}
]
```

If you are not confident about a date, leave the entry out and put it in `gaps`.

A cancelled standup has a second effect worth spelling out on the page: any ask
that was waiting for the next meeting now has nowhere to go, so it has to move
into Asana or into whatever replaces the meeting. Say that in the affected
ticket's items.

## Step 10: do not write the top line

The first line of the page is worked out from the items themselves: how many
things are his, which one to start on, and the room it is material for. You
cannot improve on that and you must not try, because anything you write there is
a sentence about a conversation, and by the time he reads it he has had the
conversation. "So Wednesday is an argument about what happens after detection"
means nothing to a man opening a page cold, and it was the first thing on it.

`alert` is the one exception, and the bar is high. Write it only when all four
are true:

1. It needs him inside the hour.
2. It is not already an item, and cannot be made into one, because there is
   nothing for him to do until somebody else moves.
3. It would change what he does this morning if he knew, and hurt if he did not.
4. You can quote the message it came from.

It must read to someone who has read nothing else. Name the person, name the
ticket, say what has happened and what it means for him, in two sentences at
most. If nothing meets all four, leave the field out entirely. An empty top
block is the correct answer most days, and it is how the red one keeps its
meaning.

## What you write into the board

Merge into `state/board.json`. Set `checked_at` to now and keep `next_id` above
every id you have used. A ticket looks like this, and an existing ticket keeps
everything you are not changing.

```json
{
  "checked_at": "ISO 8601 with +09:00 offset",
  "next_id": 8,
  "alert": {
    "what": "Leave this out unless something needs him inside the hour and is not already an item. Read the rule below before writing it.",
    "source_url": "Permalink to the message it came from."
  },
  "notion_url": "URL of today's meeting note",
  "meeting_note": {
    "date": "YYYY-MM-DD of the standup you just processed",
    "found": true,
    "url": "The URL Notion itself returns for the page, the app.notion.com/p/<id> form. A workspace-slug URL you assembled by hand will 404 when the title has a date in it."
  },
  "sessions": [
    {"kind": "standup", "date": "YYYY-MM-DD", "at": "10:30"}
  ],
  "tickets": [
    {
      "id": "Asana task gid. This is what stops a ticket being added twice.",
      "ref": "Short Japanese tag, 4 to 6 characters, matching the morning prep",
      "title_ja": "Exact Asana task title.",
      "title_en": "Short English title, under 10 words.",
      "asana_url": "permalink_url",
      "asana": {
        "status": "The Status field verbatim, e.g. 調査中",
        "section": "The board column it sits in",
        "priority": "Priority (Kraken resource allocation)",
        "category": "Category field",
        "assignee": "Assignee name"
      },
      "internal_ticket": {
        "name": "Internal Kraken build ticket title, or empty string",
        "url": "URL, or empty string"
      },
      "terms": [
        {
          "term": "The shorthand as it appears in the tickets, e.g. ケース1・2",
          "means": "What it actually refers to, taken from the source that defined it.",
          "source_url": "Permalink to where it was defined"
        }
      ],
      "where_it_stands": "2 to 4 sentences. Where the ticket actually is and who owns the next move. This is for Rei only, so internal detail is fine here.",
      "events": [
        {
          "on": "YYYY-MM-DD of the message",
          "at": "HH:MM, 24-hour JST",
          "who": "Who moved it, with their side: 'TG, Tanaka' or 'Kevin Mann, Kraken' or 'You'",
          "what": "What they did or said, in one or two sentences.",
          "so_what": "What it changes for Rei. Empty string when the entry is only a step in the story.",
          "where": "Standup | Slack #channel-name | Asana",
          "source_url": "Permalink"
        }
      ],
      "threads": [
        {
          "label": "What this conversation is, e.g. 'CE refinement request'",
          "where": "Asana | Slack #client-eng-jpn-refinement | Notion",
          "url": "Permalink to the thread or ticket",
          "last_from": "Name (Kraken) or Name (TG)",
          "last_at": "YYYY-MM-DD HH:MM",
          "gist": "One line on where that conversation currently sits."
        }
      ],
      "items": [
        {
          "id": 8,
          "title": "Imperative, under 12 words.",
          "steps": [
            "Two to four steps, in order, each starting with a verb aimed at Rei.",
            "Concrete enough to start on without working out what you meant.",
            "Never commentary or background. That goes in why."
          ],
          "done_when": "One sentence describing the finished thing, so he can tell when he is done.",
          "why": "One line on what goes wrong if he skips this. Never a restatement of the title.",
          "state": "todo | hold | waiting | done | sent | dropped",
          "state_at": "HH:MM the state last changed, or empty string",
          "state_note": "A few words on why it is in that state. Empty string otherwise.",
          "sent_by_you": false,
          "opened": "YYYY-MM-DD this item first appeared",
          "committed_to": "Who Rei promised this to and when. Empty string if not a commitment.",
          "progress_note": "What has already happened on this same number, when it has come back to him. Empty string otherwise.",
          "waits_on": {
            "who": "Who is holding this, with their side. Omit the whole object when the next move is Rei's.",
            "what": "Exactly what they owe, in one clause.",
            "since": "When it landed with them, HH:MM today or 'DD Mon'",
            "chase_on": "YYYY-MM-DD, or a place such as '2026-08-26, at the onsite'"
          },
          "where": "Asana | Slack #channel-name | Offline",
          "link": "Direct URL to the exact thread or ticket to act in.",
          "blocked_by": "What must happen first. Empty string if nothing.",
          "urgency": "today | this-week | monitor",
          "est_minutes": 20,
          "hold": {
            "why": "Why sending or doing this today would be a mistake. One sentence.",
            "until": "The specific event that releases it, naming the person.",
            "revisit": "YYYY-MM-DD to chase if that has not happened"
          },
          "source_quote": "The verbatim line this came from.",
          "source_url": "Permalink to that line",
          "draft": {
            "target": "Asana comment on <ticket> | Slack reply to <person> in #channel",
            "link": "URL of the thread being replied to",
            "language": "ja | en",
            "body_ruby": "Draft text. Japanese uses {漢字|かんじ} markup.",
            "body_en": "English translation when the draft is Japanese, else empty string"
          },
          "history": [
            {"at": "ISO 8601", "state": "waiting", "note": "with Kevin"}
          ]
        }
      ],
      "open_decisions": [
        {
          "question": "The fork, stated as a question.",
          "options": ["Option one", "Option two"],
          "owner": "Who is expected to decide, or 'nobody assigned'",
          "source_url": "Permalink"
        }
      ]
    }
  ],
  "news": [
    {
      "topic": "Short label for something not his, moving around him.",
      "what": "One or two sentences on what actually happened.",
      "why": "How it reaches him. No route, no row.",
      "on": "YYYY-MM-DD",
      "source_url": "Permalink"
    }
  ],
  "gaps": [
    "Anything you could not resolve. Empty array if none."
  ]
}
```

Omit `hold` entirely on anything he can act on now. Omit `draft` when you cannot
write it honestly.

There is no running order in the board. The page builds it from each item's
number and state, so an item can never be ordered two different ways. Keep `ref`
tags identical to the morning prep, and keep ticket `id` equal to the Asana gid
so nothing is ever added twice.

When you have written the board, render it:

```
python3 render_desk.py    state/board.json output/desk.html
python3 render_desk_md.py state/board.json output/desk.md
```
