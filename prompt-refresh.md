# Bring the board up to date

Go and see what has moved, fold it into `state/board.json`, rebuild the page.
This is the routine behind the word "refresh" in a chat, behind `tg refresh` in
the terminal, and behind the Refresh button on the page, so all three cost the
same.

Tool names below are indicative. Use whatever equivalents you have for Asana,
Slack and Notion.

## What the board is

`state/board.json` is the only durable file, and `board.py` documents its shape.
It holds every open TG billing ticket assigned to Rei and every item of work on
those tickets. Items keep their number until they are closed, so "do 4" means
the same thing next week. Never renumber, never reuse a number, never rewrite
history that has already happened.

## 1. Read where things stand

Read `state/board.json`. Note, per ticket, the timestamp of the last entry in
`events`: that is the line you are checking forward from. Note which items are
`todo`, `hold` or `waiting`, and who each waiting item sits with.

## 2. Sweep every open ticket

Asana first, because the board should match it:

- Every incomplete task assigned to Rei in `インシデント（TG Shared）` and
  `Billing 2-Week Cycle [TG shared]`. That is the ticket set. A ticket that is
  open in Asana belongs on the board even when nothing needs him today.
- For each ticket, refresh `asana`: `status`, `section`, `priority`, `category`,
  `assignee`. These are what Asana says, not your reading of it.
- New tickets since the last sweep get added, with `where_it_stands`, `terms`
  and `threads` filled in the same way the morning prep does it.
- A ticket completed in Asana, or reassigned away from Rei, comes off the board.
  Close its open items as `dropped` with a note saying why.

Check `modified_at` before pulling comment bodies, so an unchanged ticket costs
one call.

## 3. Then the conversations

- New replies in every thread listed under each ticket's `threads`.
- Slack messages that mention Rei and have no reply from him, in the channels
  those threads live in. If one belongs to a ticket on the board, attach it as a
  thread and give it an item. If it belongs to no ticket, still give it an item
  on the closest ticket and say so in the item's `why`.
- The internal build ticket, when TG is waiting on a build.

Do not re-read closed items and do not re-read the meeting note.

## 4. Put what you found in the timeline

Add each new event to that ticket's `events`, in time order, with `on`
(YYYY-MM-DD), `at` (HH:MM), `who`, `what`, `so_what`, `where` and `source_url`.
Rei's own messages go in as "You". Leave `so_what` empty unless the event
changes what he does.

## 5. Move the items those events affect

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

## 6. Rebuild

```
python3 render_desk.py    state/board.json output/desk.html
python3 render_desk_md.py state/board.json output/desk.md
```

`tg refresh` and the Refresh button open the page themselves, so do not open it
again.

## 7. Say what changed, briefly

A few lines on what moved and what it means for the list. If nothing moved, say
so in one line and stop. Never restate the whole board back to him.

The rules in `AGENTS.md` apply throughout, particularly: never send anything,
and never draft around a hold.
