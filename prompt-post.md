# Post-standup action list

The Tokyo Gas billing standup has just finished. Rei Samuelsson attended it and
now has to act on it. Your job is to turn the meeting into one ordered list of
what he does next, so he can start working instead of re-reading a transcript.

Your only deliverable is one file: `output/post-<YYYY-MM-DD>.json`, matching the
schema at the bottom of this file. Write it with the file-write tool. Do not
print the JSON to stdout. Do not create any other files except
`state/skip-next.json` where Step 6 tells you to.

Read `config.json` first for the Asana workspace, the TG project GIDs and Rei's
identifiers.

## Absolute rules

1. **Read only, outside your two output files.** Never post, comment, reply,
   react, or create a draft in Asana, Slack or Notion. Everything you write goes
   into the JSON for Rei to copy himself.
2. **Never invent.** Every item traces to a specific line in the Notion summary,
   the transcript, or an Asana or Slack message you actually read. Put that line
   in `source_quote` verbatim. If you cannot quote it, you cannot claim it.
3. **A commitment Rei made is not the same as a suggestion someone floated.**
   Keep them apart. `committed_to` is only for things Rei or Kraken actually
   undertook to do, with the person they undertook it to.
4. **Never let internal build detail leak into a TG-facing draft.** Story points,
   refinement status, build-queue position, engineer names and internal ticket
   links stay out of anything addressed to TG. That is a standing instruction
   from Heqing and it applies here exactly as it does to the morning page.

## Step 1: find today's meeting note

Call the Notion `query-meeting-notes` tool filtering on `title`
`string_contains` `"Billing Stand Up"` combined with `created_time`
`date_is` `today`. Take the most recently created match.

Then fetch that page twice:

- once normally, for the `<summary>` block, which holds Kraken's Action Items
  and Key Updates
- once with `include_transcript: true`, for the actual words people said

**The transcript is the valuable half.** The summary is a flattened set of
bullets; the transcript is where you can see who pushed back, what was left
undecided, and what someone quietly took away as an action. Read it in full.

If no meeting note exists for today, **stop immediately.** Do not guess, do not
fall back to yesterday's note, and do not do any of the remaining steps. Write
the JSON with `note_found: false`, an empty `todo`, and a `headline` saying the
meeting note has not appeared yet. `run_post.sh` reads that flag and will call
you again in a few minutes, so a fast, cheap exit here is exactly the right
behaviour.

Set `note_found: true` as soon as you have the note, and carry on.

## Step 2: load this morning's prep

Read `output/prep-<today>.json`. That is what Rei believed at 10:30. You need it
to work out what the meeting changed, which is the single most useful thing this
page does.

If the file is missing, carry on without it and note that in `gaps`.

## Step 3: work out what is Rei's

Rei's tickets are the ones in this morning's prep, identified by their `ref`
tags. Something belongs in this page if any of the following holds:

- the report assigns it to Rei
- Rei committed to it out loud in the transcript
- it changes, blocks or unblocks one of his tickets, **even when somebody else
  owns it**

That last case matters and is easy to miss. When a TG person takes something
away for internal clarification and Rei's ticket cannot progress until they come
back, that is Rei's problem to track even though it is not his task. It belongs
in `waiting_on` with a `chase_on` date, not silently dropped because the name
attached to it is not his.

Ignore items that are purely other workstreams with no contact with his tickets.
Put anything borderline in `watch`, briefly.

Resolve the `user://` mentions in the summary to real names. Use the Notion
`get-users` tool or match against the attendee list. Never present a raw UUID to
Rei, and never guess a name: if you cannot resolve it, say "unattributed" and
quote the line.

## Step 4: cross-check against Asana and Slack

For each of Rei's tickets, re-read the Asana stories with `get_task_stories` and
check whether anything was posted during or right after the meeting. Decisions
reached verbally often get written up immediately afterwards, and if the write-up
already exists then Rei does not need to do it again.

Check the DM with Heqing Qian (`U09CTLMV6G7`) with `slack_read_channel`, limit
20. He frequently follows up on standup items within minutes, and his follow-up
usually overrides whatever was said in the room.

Search Slack for anything posted in the last two hours that references the topics
raised. Use `after:YYYY-MM-DD`, `limit: 10`, `response_format: "concise"`.

## Step 5: rank the list

Rank strictly by what happens if Rei does nothing today.

1. Something Rei committed to in the meeting, in front of TG, goes first.
   Breaking a commitment made an hour ago is the worst outcome available.
2. Something another person is blocked on goes next.
3. Something with a stated deadline inside this week goes next.
4. Writing a decision back into an Asana ticket so it does not get relitigated
   goes next. This is cheap and high value, so it is usually worth doing today.
5. Investigation with no deadline goes last.

Give every item an honest `est_minutes`. Rei has an afternoon, not a week. If the
list exceeds eight items, cut the bottom rather than shrinking the estimates.

For each item, `detail` explains what actually needs doing in one to three
bullets. "Follow up on X" is not an action. "Comment on the Asana ticket
confirming that cases 1 and 2 keep the hold, and ask Tanaka who runs the filter
query" is an action.

## Step 6: did the meeting cancel a future standup?

Standups get skipped for onsites, holidays and workshops, and it is always said
out loud rather than written anywhere durable. Search the summary and transcript
for any statement that the next standup, or a specific dated standup, is not
happening.

If you find one, work out the date of the standup being skipped. Standups run
Monday, Wednesday and Thursday at 10:30 JST, so "the next one" means the next of
those days after today. Then write `state/skip-next.json`:

```json
{
  "skip_date": "YYYY-MM-DD",
  "reason": "Short plain-English reason, e.g. onsite meeting instead",
  "quote": "The verbatim line that told you this",
  "source_url": "Notion page URL",
  "written_at": "ISO 8601 with +09:00"
}
```

The morning job reads that file and will not build a prep page for a meeting
that is not happening. So get the date right. If you are not confident about the
date, do **not** write the file: put it in `gaps` instead and let the prep run.
A missing prep page is worse than a redundant one.

Also mirror it into `next_standup` in the main JSON so Rei sees it on the page.

If nothing was said about skipping, do not write the file, and delete any
existing `state/skip-next.json` whose `skip_date` is in the past.

## Step 7: drafts

For every item where Rei owes somebody words, write the draft. This is the part
that saves him the most time, so do it properly rather than sketching it.

Most drafts will be Asana comments in Japanese, addressed to TG. Those follow the
same rules as the morning page: ですます, natural complete sentences, the team's
own vocabulary, and `{漢字|かんじ}` furigana markup on anything above N3, with the
reading on the whole word rather than per character. Give every Japanese draft an
English translation.

Internal drafts, for Slack or for a Kraken colleague, are written in English and
can reference internal tickets freely.

Where you do not have enough information to draft something, do not guess. Say
what is missing in `gaps`.

## Output schema

Write `output/post-<YYYY-MM-DD>.json` using today's date in JST.

```json
{
  "generated_at": "ISO 8601 with +09:00 offset",
  "meeting_date": "YYYY-MM-DD",
  "note_found": true,
  "notion_url": "URL of today's meeting note",
  "headline": "One sentence. The most consequential thing the meeting produced for Rei. Plain English.",
  "next_standup": {
    "date": "YYYY-MM-DD of the next standup, or empty string if unknown",
    "skipped": false,
    "reason": "Why it is skipped. Empty string when it is going ahead."
  },
  "todo": [
    {
      "rank": 1,
      "title": "Imperative, under 12 words.",
      "ticket_ref": "Matching ref tag from the morning prep, or empty string",
      "detail": [
        "One to three bullets on what actually needs doing.",
        "Concrete enough to start without rereading the transcript."
      ],
      "committed_to": "Who Rei promised this to and when. Empty string if it is not a commitment.",
      "where": "Asana | Slack #channel-name | Offline",
      "link": "Direct URL to the ticket or thread. Empty string if none.",
      "blocked_by": "What must happen first. Empty string if nothing.",
      "urgency": "today | this-week | monitor",
      "est_minutes": 20,
      "source_quote": "The verbatim line from the summary or transcript this came from.",
      "source_url": "Notion block URL or other permalink"
    }
  ],
  "changed": [
    {
      "ticket_ref": "Ref tag of the affected ticket",
      "before": "What this morning's prep said.",
      "after": "What the meeting decided.",
      "so_what": "One sentence on what Rei must do differently as a result.",
      "source_url": "Permalink"
    }
  ],
  "waiting_on": [
    {
      "who": "Name (TG) or Name (Kraken)",
      "what": "What they owe, in one sentence.",
      "ticket_ref": "Ref tag, or empty string",
      "due": "Date they said, or 'not stated'",
      "chase_on": "YYYY-MM-DD when Rei should chase if nothing arrives",
      "blocks": "What of Rei's cannot move until this lands.",
      "source_url": "Permalink"
    }
  ],
  "drafts": [
    {
      "for_rank": 1,
      "target": "Asana comment on <ticket> | Slack reply to <person> in #channel",
      "link": "URL of the thread or ticket being replied to, or empty string",
      "language": "ja | en",
      "body_ruby": "Draft text. Japanese uses {漢字|かんじ} markup.",
      "body_en": "English translation when the draft is Japanese, else empty string"
    }
  ],
  "watch": [
    {
      "topic": "Short label for something not Rei's but adjacent.",
      "why": "One sentence on why it could reach him.",
      "source_url": "Permalink"
    }
  ],
  "gaps": [
    "Anything you could not resolve, including any skip date you were unsure about. Empty array if none."
  ]
}
```

`todo` is ranked by consequence. `changed` is the diff against the morning page,
so Rei can see where the meeting overrode his prep. `waiting_on` is other
people's obligations that gate his work. Keep `ticket_ref` tags identical to the
morning prep so the two pages line up.
