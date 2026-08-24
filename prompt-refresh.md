# Refresh today's standup list

Go and see what has moved since the page was last built, then rebuild it. Do
this and nothing else. This is the routine behind the word "refresh" in a chat
and behind `tg refresh` in the terminal, so both cost the same.

Tool names below are indicative. Use whatever equivalents you have for Asana,
Slack and Notion.

## 1. Read where things stand

Read `output/post-<today>.json` and `state/progress-<today>.json`. If there is
no list for today, read the most recent `output/post-*.json` and say which day
you are working from. Note the timestamp of the last entry in each ticket's
`changed_today`, because that is the line you are checking forward from.

## 2. Check only what the open actions point at

For every action that is not finished:

- New comments on that ticket in Asana, after the last timeline entry.
- New replies in the Slack threads listed under the ticket's `threads`.
- The internal build ticket, when TG is waiting on a build.

Nothing else. Do not re-read closed actions, do not re-read the meeting note,
and do not go looking for new tickets; the morning run does that. Check comment
timestamps before pulling comment bodies, so an unchanged ticket costs one call.

## 3. Put what you found in the timeline

Add each new event to that ticket's `changed_today`, in time order, with `at`,
`who`, `what`, `so_what` and `source_url`. Rei's own messages go in as "You".
Leave `so_what` empty unless the event changes what he does.

## 4. Move the actions those events affect

- Someone answered something he sent: the action comes back on the same number.
  Rewrite the `draft` for the reply and add a `progress_note` saying what
  already happened. Do not create a new number for the next leg of a
  conversation he is already in.
- The thing an action was held for has happened: drop the `hold`.
- He sent something and the page did not know: `./tick.py <n> -w "<who>"` when a
  reply is expected, `./tick.py <n> --sent` when nothing comes back.
- Genuinely new work takes the next free number.

## 5. Rebuild

```
python3 render_post.py output/post-<date>.json output/post-<date>.html
python3 render_md.py   output/post-<date>.json output/post-<date>.md
```

`tg refresh` opens the page itself, so do not open it again.

## 6. Say what changed, briefly

A few lines on what moved and what it means for the list. If nothing moved, say
so in one line and stop. Never restate the whole list back to him.

The rules in `AGENTS.md` apply throughout, particularly: never send anything,
and never draft around a hold.
