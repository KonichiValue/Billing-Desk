# Write today's standup script

Rei presses **Build script** when he sits down, and this is what runs. It has two
halves: bring the board up to date, then write what he says at 10:30 into it.

He has 20 minutes with what you produce and he will be speaking Japanese to
Tokyo Gas within the hour. Everything you write is for someone who needs to sound
informed and specific, out loud, without rehearsing.

## Stop rather than improvise

You need the Asana and Slack tools. If they are missing, or answer with an
authentication error, **stop immediately**, change nothing, and reply with one
line naming what is missing. Never call those HTTP APIs yourself with `curl`,
never invent an API token, and never start another agent (`cursor-agent`,
`tg prep`, a subagent that runs either). A source you could not read is a source
you do not write about.

## Half one: bring the board up to date

Read `prompt-refresh.md` and do everything in it, including the rebuild at the
end. The script must sit on top of the newest replies, not yesterday's, and the
sweep is written down in one place so the two routines cannot drift.

That gives you a current `state/board.json`: every open TG billing ticket
assigned to Rei, every item of work on it, and the timeline of how each got
there. `board.py` documents the shape.

## Half two: what he says

Only the standup half is yours to write now. Do not touch item states, and do not
rewrite `events` or `where_it_stands` beyond what the sweep already did.

Read `config.json` first for the Asana workspace, the two TG project GIDs, Rei's
user GID and the Slack channel hints.

### The order the meeting walks

The standup works down the 2-week cycle board in the order the cards appear on
screen, and Rei follows along live. Call `get_tasks` with
`section: "1212703668929156"` (This Cycle's Priority) and `limit: 60`, which
returns tasks in board order. Set each ticket's `prep.order` to 1, 2, 3 by that
position, and `prep.board_position` to something like `"3 of 14 on the board"` so
he knows roughly when he is up.

If that section GID has moved because a new cycle started, find the current
"This Cycle's Priority" section on project `1209230965235758` and use that.

### Trace what the fix does not cover

This is the step that separates a useful script from a status readout, so do it
for every ticket, properly. Almost every fix in this programme is scoped: it
fixes one case out of several. Reading the ticket tells you what it covers. Your
job is what happens to everything it does not, because that is what Rei gets
asked.

Write the chain into `prep.consequences`:

1. **What does the agreed fix cover?** Name the cases in the team's own numbering.
2. **What falls outside it?** Name those too.
3. **What accumulates?** If a hold or a manual step keeps firing on the uncovered
   cases, accounts pile up somewhere. Say where, and say whether the pile grows
   or is a fixed legacy set. TG will make that distinction.
4. **Who owns the pile?** Somebody reviews or clears it. If the ticket does not
   say, that is a real question and a good one.
5. **What does done mean for the uncovered cases?** If a cleanup has been asked
   for, pin down which accounts, which cases, who executes.
6. **What decision is genuinely still open?** Not "we should investigate", but a
   fork with two named options and nobody assigned to choose.

Anything only TG can answer becomes an `open_questions` entry. Anything Rei can
answer himself becomes an `unknowns` entry.

### The script itself

Every ticket gets `prep.script`: the actual sentences he will say. This is speech,
not a translation of your English summary.

Cover, in this order, skipping any block that does not apply:
`現状` where it stands, `わかったこと` what we found since last time, `提案` what
Kraken proposes, `お願い` what he needs from TG, `質問` what he needs answered.

Style:

- N2, ですます, business-polite and plain.
- **Every line is a complete, natural sentence.** One idea per line, but the line
  has to stand on its own when spoken. Never chop a sentence into fragments
  across lines. Roughly 25 to 50 characters is the sweet spot, longer when the
  sentence needs it.
- Wrong: 「自動発行はNG。」「ステートメントの作成までです。」
  Right: 「理由に関わらず自動で請求を発行するのはNG、という理解です。」
- **Use the exact vocabulary TG and the team already use.** Never simplify a term
  into something more basic: TG has to recognise what he is talking about. Keep
  課金GAPホールド, 稼働確認, ホールド一覧, 管理件名, 期待値, ステートメント,
  インテグリティチェック, リゾルバ, 託送番号不一致HOLD, 保安閉栓, 供給中断,
  アキュラル and anything else lifted from the ticket or the thread.
- Cut padding, not substance. Drop repeated お疲れ様です. Never write a line that
  only restates the one before it.
- Lead each block with the topic, not the wind-up. 「請求未発行の恒久対応についてです。」
  beats 「請求未発行の恒久対応について、お話しさせていただきたいと思います。」
- Two to five lines per block, at most four blocks per ticket.

**Furigana.** Wrap kanji above N3 as `{漢字|かんじ}`, reading on the whole word,
not per character. Words he knows (今日, 問題, 対応, 確認, 請求) need none. Err
towards adding it for technical and market vocabulary.

Correct: `{託送番号|たくそうばんごう}が{一致|いっち}しません。`
Wrong: `{託|たく}{送|そう}{番|ばん}{号|ごう}`

Every line needs a natural English translation in `en`. Translate the meaning,
not the grammar.

### Asks: earn them, do not invent them and do not miss them

Before deciding a ticket needs nothing from TG, check your consequences chain. If
the fix is scoped and you have not established who owns the uncovered cases or
what cleanup means, there **is** an ask and you have not found it yet.

Set `tg_ask_needed` to `false` only when the chain came back genuinely clean: the
fix covers everything, or the leftovers have a named owner and an agreed
definition of done. Then give the ticket a `現状` block of two to four lines and
stop. A ticket sitting with Kraken engineering with nothing outstanding is a good
thing to report in one breath.

Never invent a question to fill the 質問 block. A weak question wastes standup
time. A missing one is worse: TG raise it instead and he answers cold on his own
ticket.

Where a delivery estimate exists **and has already been shared with TG**, put it
in `prep.estimate`. If none has been agreed, leave it out rather than hedging
about timing.

### What has to be spoken rather than only done

Some items on the board are only closable in the meeting: a question TG owes an
answer to, something he promised to raise, a decision that needs both sides in
the room. Set `at_standup: true` on those items, with a short `at_standup_note`
saying what he needs out of it. They then show on both views, and the standup
view lists them under the ticket. Leave every other item alone.

### Hard constraint: nothing internal reaches TG

Internal Kraken build tickets, story points, t-shirt sizes, refinement status,
build-queue position, engineer names and delivery estimates must **never** appear
in `prep.script`, in an `open_questions` entry aimed at TG, or in any draft
targeted at TG. Heqing has said this directly and more than once. TG cannot see
those tickets and does not get told what is queued.

What Rei may say is the shape of the work: requirements are agreed, Kraken is
working on it, here is what will change. Nothing about when or how big. Keep the
internal detail on the desk side, in item `why` and `detail`, which is for him.

## What you write into the board

Per ticket, one `prep` object, replacing whatever was there:

```json
"prep": {
  "order": 1,
  "board_position": "3 of 14 on the board",
  "issue": ["Two or three lines of plain English. No jargon, no Japanese.",
            "Someone who has never seen this ticket understands it here."],
  "why_it_matters": "One sentence on the customer or business impact.",
  "consequences": {
    "fix_covers": "", "falls_outside": "", "accumulates": "",
    "who_owns_it": "", "done_means": "", "still_open": ""
  },
  "open_questions": [
    {"en": "The question in English.",
     "ja_ruby": "The question in Japanese with {漢字|かんじ} markup.",
     "who": "TG | Kraken CE | Rei"}
  ],
  "script": [
    {"heading": "現状", "heading_en": "Where it stands",
     "lines": [{"ja_ruby": "...", "en": "..."}]}
  ],
  "tg_ask_needed": true,
  "estimate": "Only if already agreed with TG. Otherwise omit.",
  "unknowns": ["What he should check before he speaks. Also anything he must not say."],
  "built_at": "ISO 8601 with +09:00"
}
```

And once at board level:

```json
"standup": {
  "date": "YYYY-MM-DD",
  "at": "10:30",
  "built_at": "ISO 8601 with +09:00",
  "headline": "One sentence. The single most important thing about today."
}
```

Do not write `where_it_stands` inside `prep`. The standup view reads it from the
ticket, so there is one status and the script can never contradict the desk.

## Is the standup even happening?

Check `standup.skipped` and `next_standup` on the board. The last meeting may have
announced a cancellation, usually for an onsite. If today is that date, write the
prep anyway but put it in `standup.headline`, in one clause, so the page says so
at the top.

## Then rebuild and report

```
python3 render_desk.py    state/board.json output/desk.html
python3 render_desk_md.py state/board.json output/desk.md
```

Finish with a few lines: which tickets have an ask on the table, which are status
only, and anything he should check before 10:30. Always write this, even when the
answer is dull, because a silent run cannot be told apart from a dead one. Never
restate the whole script back to him.

The rules in `AGENTS.md` apply throughout, particularly: never send anything, and
never draft around a hold.
