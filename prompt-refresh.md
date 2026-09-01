# Bring the board up to date

Go and see what has moved, fold it into `state/board.json`, rebuild the page.
This is the routine behind the word "refresh" in a chat, behind `tg refresh` in
the terminal, and behind the Refresh button on the page, so all three cost the
same.

Tool names below are indicative. Use whatever equivalents you have for Asana,
Slack and Notion.

## Stop rather than improvise

You need the Asana and Slack tools to do this at all. If they are missing, or
they answer with an authentication error, **stop immediately**, change nothing,
and reply with one line naming what is missing. Rei fixes it with the Log in
button on the page.

Three things are never a workaround, however reasonable they look:

- Calling the Asana, Slack or Notion HTTP APIs yourself, with `curl` or
  anything else. There are no API tokens here, and naming an environment
  variable does not conjure one.
- Starting another agent: no `cursor-agent`, no `tg refresh`, no subagent that
  runs either. You are the refresh. A second one writes the board underneath
  you and can leave it half updated.
- Guessing what a ticket or a thread now says. A source you could not read is a
  source you do not report on.

## What the board is

`state/board.json` is the only durable file, and `board.py` documents its shape.
It holds every open TG billing ticket assigned to Rei and every item of work on
those tickets. Items keep their number until they are closed, so "do 4" means
the same thing next week. Never renumber, never reuse a number, never rewrite
history that has already happened.

## 1. Read where things stand

**Run `./digest.py`, once.** It prints the whole readable half of the board in
one call: every ticket with where it stands, its gates, its threads with the time
each was last read, its last events, and every open item with its steps, its
draft and what it is queued behind. Add `--full` only if you need closed items or
untruncated prose.

From that, note per ticket the timestamp of the last entry in `events`, which is
the line you are checking forward from, and note which items are `todo`, `hold`
or `waiting` and who each waiting item sits with.

That is the only read of the board you need before the sweep. Do not open
`state/board.json` with a one-line script to list the tickets, dump a fragment
into `/tmp` and read it back, or work out the schema by printing `type()` and
`keys()`, and do not run `help(board)`. One refresh ran `help(board)` four times
and read the board twenty times around it; that was most of its thirteen minutes,
and none of it was spent talking to Asana. The schema is the docstring at the top
of `board.py`, and it is the contract: read it once if you need it, and trust it.

To write, `import board`, mutate, `board.save(b)`. To redraw both pages,
`./tick.py --rebuild`. Neither needs discovering.

**The `OUT OF DATE` block at the top of the digest is a worklist, not a warning.**
Every line in it is something a previous sweep should have done and did not: a
chase date that has passed, prepared work older than the ticket it sits on, a
thread whose watermark is older than the events taken out of it. Fix all of them
in this sweep. They are cheap, they are why the page drifts, and nobody else is
going to do them.

The thread watermarks matter most, because they are self-inflicted. Each thread
carries `last_at`, the point you read forward from. A sweep that reads a thread,
writes an event dated later, and leaves `last_at` alone has quietly moved the
next sweep's starting line backwards. Do that a few times and threads look quiet
when they are not, which is exactly how the board ends up behind. **Every thread
you open, set `last_at` and `last_from` to its newest message, even when nothing
in it changed.**

## 2. Sweep every open ticket

Asana first, because the board should match it:

- Every incomplete task assigned to Rei in `インシデント（TG Shared）` and
  `Billing 2-Week Cycle [TG shared]`, **plus every ticket already on the board
  that still has an open item**. Those two together are the ticket set. A ticket
  that is open in Asana belongs on the board even when nothing needs him today.
- For each ticket, refresh `asana`: `status`, `section`, `priority`, `category`,
  `severity`, `assignee`. These are what Asana says, not your reading of it, and
  the page prints them under Asana's own field names.
- New tickets since the last sweep get added, with `where_it_stands`, `terms`
  and `threads` filled in the same way the morning prep does it.
- A ticket completed in Asana keeps its card, with `asana.completed` true, and
  moves into the closed fold.
- **A reassignment changes who TG's owner is, not whose work it is.** When the
  Asana assignee moves to someone else, write the new name into
  `asana.assignee`, add the reassignment as an event, and address later drafts to
  the new assignee. The card stays and the items keep their numbers. Never drop
  an item because the ticket moved: it goes only when the thing it asked for has
  happened or somebody has actually taken it, and the note has to name who. A
  ticket leaves the board when every item on it is closed or dropped, and never
  before, because the items are how Rei refers to his own work.
- For each ticket with `internal_ticket.url`, refresh `internal_ticket.build`
  from that CE build task. `stage` is the one judgement in it: read Status
  (Kraken Cust), Client Engineering Status and the section together and pick
  `refining`, `queued`, `building`, `review`, `released` or `verified`, where
  `verified` means TG have checked bills issued after the release, not that
  Asana says Done. Fill `kt`, `asana_status`, `engineer` (empty string when
  nobody is on it), `size`, `refined_by`, `refinement`, `feature_flag` and
  `moved_on` from `modified_at`. Rewrite `waiting_on` as one sentence saying why
  it is not moving. All of it is desk-only and must never appear in `prep` or
  anything addressed to TG, `safe_to_say` excepted.
- Then bring `closes_when` up to date on every ticket, since that is what says
  whether a quiet ticket is finished or only quiet. Flip a gate to `done` when
  the sweep found the thing that closes it, and add a gate when something in
  this sweep created one. Keep the gates nobody owns as items: an engineer
  assigned, a release, a feature flag switched on, TG's own verification. Cite
  the item number in `note` rather than restating the item.

Check `modified_at` before pulling comment bodies, so an unchanged ticket costs
one call. A bump is not always a comment: a section move, a status change or a
bulk edit stamps it too, and several tickets stamped the same minute is that
rather than a conversation. Read the `asana` fields you already pulled against
the board first, and pull the stories only when a changed field does not already
explain the bump.

## 3. Migration daily when it has run

Billing sometimes surfaces in the Migration daily, not only the Billing
standup. On days you refresh on or after the meeting, read today's notes in
Notion and fold any billing mention into `news` (step 7). The page is
[Migration Daily Stand Up](https://app.notion.com/p/3c773c742c7181d989d6cb1f9cc4286c).

- Mon–Thu 11:00–11:30 JST: Migration Daily Stand Up
- Fri 11:00–12:00 JST: 【TG<->Kraken】X-Workstream Meeting (same page,
  different title)

Only billing content matters. Add or update a `news` row when you can name the
route by which it reaches one of his tickets or the build queue behind them. Do
not open items for team-level Kraken action items unless they land on his
tickets. Store what you read in `migration_note`, same shape as `meeting_note`:
`date`, `found`, `url` (the `app.notion.com/p/<id>` form with the day's
anchor). Do not re-read a migration note you have already folded in.

When Rei points you at a note from some other room, read it the same way and
record it in `other_notes` with `date`, `title`, `url`, `found` and a `gist`
saying what came out of it, so a later sweep knows it has been read. A one-off
session usually reaches a ticket as evidence rather than as work: something
answered there that his ticket has been guessing at. Put it in that item's
`prepared` with the session as the source, not in a new item.

## 4. Then the conversations

- New replies in every thread listed under each ticket's `threads`.
- Slack messages that mention Rei and have no reply from him, in the channels
  those threads live in. If one belongs to a ticket on the board, attach it as a
  thread and give it an item. If it belongs to no ticket, still give it an item
  on the closest ticket and say so in the item's `why`.
- The internal build ticket, when TG is waiting on a build.

Do not re-read closed items and do not re-read the meeting note or migration
note you have already folded in.

## 5. Put what you found in the timeline

Add each new event to that ticket's `events`, in time order, with `on`
(YYYY-MM-DD), `at` (HH:MM), `who`, `what`, `so_what`, `where` and `source_url`.
Rei's own messages go in as "You". Leave `so_what` empty unless the event
changes what he does.

## 6. Move the items those events affect

- Someone answered something he sent: the item comes back to `todo` on the same
  number. Rewrite its `draft` for the reply and put what already happened in
  `progress_note`. Never open a new number for the next leg of a conversation
  he is already in.
- The thing an item was held for has happened: drop the `hold`, set `todo`.
- He sent something and the board did not know: `state` becomes `waiting` with
  `waits_on` filled in, or `sent` when nothing comes back.
- Genuinely new work takes `next_id` and increments it.
- Nothing moved on an item: leave it exactly as it is.

Set `checked_at` to now, in ISO 8601 with the offset.

**When part of an item is done, rewrite the title to what is left.** Writing the
fact into `progress_note` is not the job; `progress_note` is additive and safe,
and adding to it is what a sweep does instead of committing to a change. An
actual example, from a sweep that otherwise ran clean: it read the CE ticket,
correctly noted that both files had been re-uploaded at 10:57, and left the item
titled "Re-upload both sheets to the CE ticket and fix the 144s in the
description". Only the second half was still true. Rei reads titles to decide
what to open, so a title describing finished work sends him to do it again, and
he cannot tell from the list which half is left.

So on every item you touch: if the title names two things and one has happened,
retitle it to the one that has not. Trim the `steps` that are done rather than
annotating them. Cut `est_minutes` to what remains. If everything in the title
has happened, the item is closed, not retitled.

Whenever you touch an item, leave its `steps` fit to act on: two to four, in
order, verb first, aimed at Rei, naming the place and the thing. Commentary is
not a step and belongs in `why`. Leave a `done_when` saying what the finished
thing is. If the steps tell him to ask, tell, confirm or reply, there is a
`draft`; if they tell him to read or compare, say so in a step and leave the
draft out. An item with no steps renders as a warning on the page, so never
leave one behind.

**A draft is either the message he would send now, or it is gone.** The work
view is only worth trusting if nothing on it is left over, so read every `draft`
still on the ticket against what you have just found. If the thread moved,
rewrite the draft into the message he would send this minute and say in
`progress_note` what changed and why. If the reason for the message has gone,
delete the draft and the step that asked for it. A draft written yesterday
morning is the most dangerous thing on the page, because it reads as ready to
paste and it is addressed to TG.

One exception: before clearing a draft, check whether it was already sent.
If the `progress_note` or a recent event records that the draft's message was
actually posted, copy the sent text into the item's `history` as
`{"at": "<ISO timestamp>", "state": "sent", "note": "<sent draft body>"}` before
wiping the `draft` field. A sent draft is part of the record and must not be
lost even when the item comes back to `todo`.

Prune what was prepared the same way. Take an `unanswered` question off once it
has an answer, and drop a `prepared` note whose finding has been overtaken,
rather than letting a card grow a history. Nothing stays because it was true
once.

**An item is work somebody is waiting for, not a thought you had.** Before you
write one, name who is blocked without it and what they do with it. Three tests
kill most candidates:

- **Already answered elsewhere.** If TG's own Asana field, the ticket's status or
  their own linked ticket already says it, telling them again is not work.
- **His answer already landed.** A question answered in a room, and not argued
  back, does not need a written repeat. Put the answer in `progress_note` and set
  the item to `monitor`, so it only comes back if they reopen it.
- **Somebody else's job.** TG run their own patrol and their own manual
  recoveries. Confirming to them what they did themselves is noise. So is
  chasing a Kraken queue position, which is not his to move.

Two things TG need in one place go in one comment, on the older number, not two
comments an hour apart. Drop the number that got folded in with a note saying
where it went. A shorter list that is all real is the point; five items he
believes beats nine he has to filter.

**Check this every sweep, not only when you write a new item.** Two items whose
drafts are addressed to the same person on the same ticket are one item, however
they got there, and the way to find them is to read the `target` of every open
draft on a ticket together. Three numbers that end in one Asana comment cost him
three readings and a decision about ordering that does not exist.

**Then chain what is genuinely sequential, with `after`.** Most of what is left
on a ticket is a queue rather than a menu: the scope cannot be confirmed before
the sheet exists, the reply cannot go before the answer arrives. Set `after` to
the number it follows and the page stops offering it: it folds under the item in
front of it, saying which number that is, and becomes a job by itself the moment
that one closes. The test is whether doing it first would be wrong or impossible.
Two items that merely sit on the same ticket are two items, and two that end in
the same message are one item, not a chain. An `after` pointing at something
already closed is ignored, so nothing has to tidy up after itself.

Between the two, the front of the list should only ever hold work he could start
this minute. That is the whole purpose of the view: he reads the top, and it is
true.

**Sort by what has to happen first.** `urgency` is what orders the page inside
each group, so a `today` that is really next week is worse than no flag. Reserve
`today` for work with a person or a room waiting on it, and use `monitor` for
anything that only needs watching.

**`at_standup` follows `sessions`, not habit.** The billing standup runs on the
days in `config.json`, so check the next live session before you leave a flag
on. If the next room is days away and the item is due today, or it is a session
where he does not walk his tickets, take the flag off and put the written route
in the steps instead: no standup means it goes on the ticket. Correct `sessions`
itself when you find a room that is not happening or one that nobody put there,
and drop entries whose date has passed. Never touch `prep` or `script`: those
are the words, and `prompt-prep.md` owns them.

**Do the part of the item you can do.** If a step could be followed without
judgement, following it was your job, not his: read the comments and pull the
conditions out, read `~/Projects/kraken-core` for what the code does, compare the
two and mark the difference, count the cases. The product goes in `prepared` with
its sources, and the steps that remain start after it. `prompt-post.md` has the
full rule and the shape. What is left for him is what needs him: sending,
deciding, speaking.

Write the product to be read once. The `conclusion` is one plain sentence he
could act on without reading on; findings are one fact each, so-what first, four
at most; plain words and file:line rather than adjectives. `prompt-post.md`,
"Write it so he reads it once", is the standard. It changes how the work reads,
never what is in it.

Then say what you could not settle, in `unanswered`, with why it is open. A
prepared block that shows no gaps is read as a finished answer and repeated in a
room on that basis, so an honest gap is worth more than a confident paragraph.
Keep table cells to a phrase and mark the row that is the point with a toned
cell. When the product is a document TG will read rather than words Rei will
say, write it into `docs/` as HTML, run `python3 make_doc.py`, and point
`prepared.files` at the HTML and the PDF.

## 7. Keep the news honest

`news` is what is moving around him that is not one of his tickets: a priority
that changed, an outage upstream, a decision on somebody else's ticket that will
be quoted back at one of his. Add a row only when you can name the route by
which it reaches him, and take a row off once that route has closed. Five at the
outside. Each row carries `topic`, `what`, `why`, `on` and `source_url`.

## 8. Clear the alert, or leave it alone

`alert` is the red strip at the top of the page, for something that needs him
inside the hour and is not an item. If the board carries one, decide whether it
is still true: the moment somebody has answered, or the thing has become an item
with a number, take it off. Do not write a new one to fill the space. The line
above it, what needs him and which item to start on, is counted from the board
by the renderer, so never write a headline or a summary of the day anywhere.

## 9. Keep the shorthand current

`terms` is the vocabulary of the ticket, and it has to carry the Japanese TG
actually say, because that is what he hears in the room and has to place inside
two seconds. Each row is `term` in English, `say` in Japanese with furigana as
`{漢字|かんじ}` on whole words, and `means` in one or two sentences that open
with what the thing is. A term nobody has used in a fortnight comes off. Add one
the moment TG use a word twice and it is not on the list: their reading codes,
their 暫定 and 恒久 pairing, whatever they are calling the hold this week.

`glossary` is the same vocabulary in two or three words, board-wide, and it is
what puts the English meaning in brackets after a Japanese term in every English
line on the page. **Every Japanese term you write into an English sentence must
be in it.** Write the English plainly and let the page add the meaning: putting
the brackets in by hand is how a term ends up explained twice in one sentence.
Check after the sweep with `python3 -c` over the board rather than by eye, since
one missed term is a line he reads without knowing what it says.

## 10. Check your own work, then rebuild

```
./audit.py
```

This is the same list the digest printed at the start, run against the board you
have just written. It is mechanical: passed dates, records that disagree with
each other, sequencing that points at something closed, prepared work older than
the ticket under it. **Fix everything it prints and run it again.** A sweep is
not finished while it prints anything, and "I found nothing new in Asana" is not
a reason to leave it printing, because none of what it catches comes from Asana.

If a line is genuinely wrong, the check is wrong and belongs in `audit.py`. Do
not leave it standing and mention it in the report.

```
./tick.py --rebuild
```

One call, both pages. `tg refresh` and the Refresh button open the page
themselves, so do not open it again.

## 11. Say what changed, briefly

Always end with this, even when the answer is dull. A run that finishes silently
is indistinguishable from a run that died, and the log is the only place Rei can
check afterwards.

A few lines on what moved and what it means for the list. When nothing moved,
one line saying so and the time you swept to. Never restate the whole board back
to him.

The rules in `AGENTS.md` apply throughout, particularly: never send anything,
and never draft around a hold.
