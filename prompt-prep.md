# Write the prep for the next session

Rei presses **Write prep** when he sits down, and this is what runs. It has two
halves: bring the board up to date, then write what he says out loud into it.

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

**First check how fresh the board already is.** `./digest.py` prints `checked_at`
at the top. If it is within the last ~15 minutes, a full sweep just ran and the
board is already current — do **not** re-run it. Do the one cheap confirmation
(the batched Asana `modified_at.after=checked_at` gate, and a glance at the
threads the SWEEP PLAN still lists as not looked at), fold in anything it turns
up, and go straight to the script. Re-sweeping a board that was swept minutes ago
is most of why prep feels slow, and it changes nothing.

Only when `checked_at` is genuinely stale (hours old, or you cannot tell): read
`prompt-refresh.md` and do everything in it, including the rebuild at the end. The
script must sit on top of the newest replies, not yesterday's, and the sweep is
written down in one place so the two routines cannot drift.

That gives you a current `state/board.json`: every open TG billing ticket
assigned to Rei, every item of work on it, and the timeline of how each got
there. `board.py` documents the shape.

## Half two: what he says

Only the speaking half is yours to write now. Do not touch item states, and do
not rewrite `events` or `where_it_stands` beyond what the sweep already did.

**Read the board for the script the same way the sweep does: once, and never by
dumping it.** Writing the script needs the untruncated `where_it_stands`,
`consequences`, `events` and `prepared` that the ordinary digest clips, so run
`./digest.py --full` **once** and write from that. The hard rule in
`prompt-refresh.md` holds here too: no `help(board)`, and no `python3 -c "import
board; ... for t in b['tickets']: print(...)"` to read a field back. You may only
`import board` to *write* your `prep` block, using the WRITE CHEATSHEET forms.
Reading the board per ticket to compose is the flail that runs prep past its
budget.

Read `config.json` first for the Asana workspace, the two TG project GIDs, Rei's
user GID and the Slack channel hints.

### Which room are you writing for

Read `sessions` on the board before anything else and write for the soonest one
that is not `skipped`. Set `script.for_date` to its date. Everything below is
written for a standup unless the session says otherwise, and an onsite is not a
longer standup.

Keep `sessions` true as you go. The last meeting note or a Slack announcement may
have moved something, added an onsite, or cancelled a standup. When you learn of
a session, write it in with its `kind`, `date`, `at` when known, a `focus`
sentence saying what the session is actually for, and, for anything that is not a
standup, the `agenda` and what he has to `bring`. A standup that is not running
stays in the list with `skipped` and a `reason`, because "no standup Wednesday"
changes what has to move into Asana instead.

**When the session is an onsite**, four things change:

1. **Depth.** A standup is 15 minutes for the whole board and he gets two
   sentences per ticket. An onsite is a day, TG are in the room, and thin
   preparation shows. Up to six script blocks per ticket, and cover the ground
   properly.
2. **`prep.decisions`.** What has to be settled before people leave the room, why
   it cannot wait, and the fallback if TG will not settle it today. These print
   in **What I need back** alongside the open questions and anything already
   owed to him, one list per ticket, so a decision written vaguely reads as a
   question and loses its force. This is the
   point of an onsite: decisions that die in a standup because there is no time.
3. **`prep.pushback`.** The objection you can see coming, and the Japanese
   sentence that answers it. Take these from what TG have actually said in the
   threads, not from imagination. Two or three per contested ticket, none for the
   quiet ones.
4. **What to bring.** Anything he promised to have ready, or that the argument
   cannot be had without, goes in the session's `bring` list. Check his own
   commitments in the threads: promising to bring something and arriving without
   it is the failure mode.

### The Friday X-Workstream rollup, always, alongside the standup

Every prep run writes **two** things now, not one: the full standup walk (below),
and the Friday X-Workstream rollup in the board-level `xws` block. Write both,
every time, whichever session is soonest. The standup is the room he walks ticket
by ticket; the X-Workstream is the whole programme in one room, and only the
absolute biggest billing items are ever taken up from him there. So the rollup is
not a second copy of the standup: it is a shortlist.

Set `script.for_date` to the **standup** and write the per-ticket `prep` for it as
always. Do **not** put the X-Workstream in `sessions`: it lives only in `xws`, so
the full walk stays pointed at the standup and the rollup renders as its own card.

Into `xws` put its `for_date`, `at` (11:00), `built_at`, a one-line `headline`
saying what he raises at the rollup this week, and `raised`: the shortlist. A
ticket earns a place in `raised` only if the whole workstream needs it, which is a
high bar. It clears the bar when it is a customer-visible incident resolved or
still live, a production release the programme has to hear about (memory: prod
releases are pre-announced in the Migration Daily), or a decision stuck long
enough that it needs escalating above the standup. Most tickets never appear.
Two or three items is a normal week; zero is a real answer, and `headline` then
says so ("nothing from billing needs the room this week") with `raised` empty.

Each `raised` entry is `{ref, why, say}`: `why` is one line on why it is big
enough for the room, and `say` is one or two lines he actually says, higher
altitude than a standup line, in the same `{ja_ruby, en}` shape with furigana.
The hard constraint below holds here too: nothing internal reaches the room, even
though it is a programme meeting, because TG sit in it.

### The order the meeting walks

The standup works down the 2-week cycle board in the order the cards appear on
screen, and Rei follows along live. Call `get_tasks` with
`section: "1212703668929156"` (This Cycle's Priority) and `limit: 60`, which
returns tasks in board order. Set each ticket's `prep.order` to 1, 2, 3 by that
position, and `prep.board_position` to something like `"3 of 14 on the board"` so
he knows roughly when he is up.

If that section GID has moved because a new cycle started, find the current
"This Cycle's Priority" section on project `1209230965235758` and use that.

### What moved since the last meeting

The prep page prints each ticket's recent `events` under "What moved since last
time", so the paragraph he needs at 09:50 is already there if the timeline is
honest. Two things follow from that. Every event since the last session must be
on the ticket, his own messages included, and `so_what` must be filled on any
event that changed what happens next, because that line is what he reads out.
Nothing is written twice: do not repeat the timeline inside `where_it_stands`,
which stays one short paragraph on the current position.

### Do not re-script what the last meeting already settled

**A ticket completed in Asana is finished: give it no `prep` block, whatever its
timeline shows.** A closed TG ticket is done, not a speaking item, so it never
gets a script line and needs no update when the script is written. It stays in
the closed fold as a record.

A ticket earns a place in the script only when the **next** room has something
still to do with it: a status TG have not heard, a question to ask, a decision to
land. If it was talked through at the last session and came out with nothing owed
back from TG, only an action for Rei to carry out afterwards (post the agreed
update to the ticket, attach the evidence once the run confirms), then it is
**finished as a speaking item**. Give it no `prep` block at all. It stays on the
desk as the item it is, and the speaking view is silent on it.

The timeline is how you tell, not the ticket's status. An event like "gave the
update at the standup, agreed to post the evidence in the ticket" means the room
is done with it, even though the ticket is still open and the action is still
Rei's to do. So read what Rei actually said last time before you write a `現状`
line, not just where the work stands.

Re-reading out a matter the room already closed is worse than leaving it off: it
reads as unresolved, invites the same discussion a second time, and buries the
one or two tickets that genuinely need the room.

This is different from a ticket sitting quietly with Kraken engineering, which
still earns its one-line `現状` because TG have a live interest in hearing it is
in hand and have not been told since. The test is whether anything is still owed
**in the room**: nothing owed, and last time already covered it, means no block.

**It reopens only when something new happens.** If the recovery fails, the
evidence is contested, TG raise a fresh question, or a promised date slips, it
earns a slot again with the new fact as its `現状`. A settled item is silent on
the speaking view, not deleted from the board.

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

**At a standup the default is one `現状` block, and most tickets should stay
there.** He is walking a whole board in fifteen minutes, so what he needs per
ticket is where it stands right now, in one or two sentences, and then whatever
he has to ask or tell TG. A ticket is not a presentation to be given: it is a
line of status, plus an ask when there genuinely is one. The full run of blocks
below is a ceiling for a contested ticket, not a shape to fill for every one. If
you find yourself writing `わかったこと` and `提案` for a ticket nobody is
arguing about, you are presenting where you should be reporting.

**A ticket sitting with Kraken engineering is one or two lines, no more.** When
the latest is that the requirements are agreed and Kraken is building it, that is
the whole of the `現状`: {要件|ようけん}は{合意済|ごういず}みで、Kraken側で対応中です,
and stop. That one line is still a line he reads out, so it carries its furigana
like any other (see below); a quiet ticket is the one the markup is most often
dropped on. Add an
approximate timing **only if a date has already been agreed and shared with TG**
(`prep.estimate`); if none exists, say nothing about when, rather than hedging.
Never reach for the build ticket, the queue position, the engineer or the size
to pad it out — those never reach TG (see the hard constraint below), and the
honest one-liner is the right answer, not a thin one.

When a ticket does need more, cover, in this order, skipping any block that does
not apply: `現状` where it stands, `わかったこと` what we found since last time,
`提案` what Kraken proposes, `お願い` what he needs from TG, `質問` what he needs
answered.

Style:

- N2, ですます, kept plain rather than stiff. These are working conversations with
  people he speaks to most days, so prefer direct plain-polite forms over heavy
  keigo: 「{確認|かくにん}します」「お{願|ねが}いします」「{教|おし}えてください」
  「〜と{思|おも}います」, not 「{確認|かくにん}させていただきます」
  「お{願|ねが}いできますでしょうか」「ご{判断|はんだん}いただけますでしょうか」
  「{恐|おそ}れ{入|い}りますが」. Stay polite, but cut the padding that makes a line
  hard to say aloud. This is register only, and never touches the vocabulary rule
  below: the technical terms are kept exactly, never simplified.
- Wrong (too stiff): 「{本番|ほんばん}での{有効|ゆうこう}{化|か}にご{賛同|さんどう}いただけますでしょうか。」
  Right (plain): 「{本番|ほんばん}で{進|すす}めてよいか{教|おし}えてください。」
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
- Two to five lines per block. Four blocks per ticket at a standup and six at an
  onsite are ceilings for a contested ticket, not targets: a quiet ticket is one
  `現状` block, often a single line.

**Furigana.** Wrap kanji above N3 as `{漢字|かんじ}`, reading on the whole word,
not per character. Words he knows (今日, 問題, 対応, 確認, 請求) need none. Err
towards adding it for technical and market vocabulary. This holds for **every**
`ja_ruby` and `say_ja` you write, the one-line quiet `現状` as much as a
six-block onsite, and for the standing vocabulary above: 課金GAPホールド,
稼働確認, 託送番号不一致HOLD, 保安閉栓 and the rest all take their reading when
they land in a spoken line. The bald compound is the failure this repo has seen
most, so `./check.py` fails on a run of three or more un-annotated kanji in a
spoken field: if it flags a line, the reading is missing, not the check wrong.

Correct: `{託送番号|たくそうばんごう}が{一致|いっち}しません。`
Wrong: `{託|たく}{送|そう}{番|ばん}{号|ごう}`

**Only kanji.** Never wrap katakana, hiragana or latin text. `ステートメント`,
`パトロール`, `ケース`, `どちら` already read themselves, and a reading printed
above them is noise on a line he is speaking at speed. The renderer drops these,
so writing them only wastes your output.

**Get the reading right.** 不一致 is ふいっち. A wrong reading is worse than no
reading, because he will say it out loud. If you are not certain of a compound,
leave it unwrapped.

Every line needs a natural English translation in `en`. Translate the meaning,
not the grammar.

### Asks: earn them, do not invent them and do not miss them

Before deciding a ticket needs nothing from TG, check your consequences chain. If
the fix is scoped and you have not established who owns the uncovered cases or
what cleanup means, there **is** an ask and you have not found it yet.

Set `tg_ask_needed` to `false` only when the chain came back genuinely clean: the
fix covers everything, or the leftovers have a named owner and an agreed
definition of done. Then give the ticket a `現状` block of one or two lines and
stop — a ticket sitting with Kraken engineering with nothing outstanding is a
good thing to report in one breath, not a section to expand.

Never invent a question to fill the 質問 block. A weak question wastes standup
time. A missing one is worse: TG raise it instead and he answers cold on his own
ticket.

**Do not say the same thing twice.** A question he asks TG out loud belongs in
the 質問 block and nowhere else. `open_questions` is only for asks that do not
belong in the spoken script: something a Kraken colleague owes him, or something
he has to settle himself. The page hides a TG question that is already in the
script, so writing it in both places only wastes your output.

Where a delivery estimate exists **and has already been shared with TG**, put it
in `prep.estimate`. If none has been agreed, leave it out rather than hedging
about timing.

### What has to be spoken rather than only done

Some items on the board are only closable in the meeting: a question TG owes an
answer to, something he promised to raise, a decision that needs both sides in
the room. Set `at_standup: true` on those items, with a short `at_standup_note`
saying what he needs out of it. They then show on both views, and the standup
view lists them under the ticket. Leave every other item alone.

When an item has `prepared.meeting_use`, its evidence stays on the desk and its
meeting-ready conclusion, ask and response to pushback go in this ticket's
`prep`. The item links to that version. Never leave Rei to translate an analysis
table into spoken words in the room, and never mix a stakeholder's desired
outcome into a table of query conditions.

### Hard constraint: nothing internal reaches TG

Internal Kraken build tickets, story points, t-shirt sizes, refinement status,
build-queue position, engineer names and delivery estimates must **never** appear
in `prep.script`, in an `open_questions` entry aimed at TG, or in any draft
targeted at TG. Heqing has said this directly and more than once. TG cannot see
those tickets and does not get told what is queued.

What Rei may say is the shape of the work: requirements are agreed, Kraken is
working on it, here is what will change. Nothing about when or how big. Keep the
internal detail on the desk side, in item `why` and `steps`, which is for him.

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
  "decisions": [
    {"need": "What has to be agreed today.",
     "why": "Why it cannot wait for the next standup.",
     "fallback": "What he asks for instead if they will not settle it."}
  ],
  "pushback": [
    {"they_say": "The objection, in English, taken from what they have said before.",
     "say_ja": "The answer in Japanese with {漢字|かんじ} markup.",
     "say_en": "The same answer in English."}
  ],
  "tg_ask_needed": true,
  "estimate": "Only if already agreed with TG. Otherwise omit.",
  "unknowns": ["What he should check before he speaks. Also anything he must not say."],
  "built_at": "ISO 8601 with +09:00"
}
```

`decisions` and `pushback` are for an onsite. Leave them out for a standup.

And once at board level:

```json
"script": {
  "for_date": "YYYY-MM-DD, the session you wrote for",
  "at": "10:30",
  "built_at": "ISO 8601 with +09:00",
  "headline": "One sentence naming what this room has to produce. It sits under the session name on the prep tab, so it must read to someone who has opened nothing else: name the ticket and name the decision. Never a recap of what changed, and never a verdict on how big the problem turned out to be."
},
"sessions": [
  {"kind": "onsite", "date": "YYYY-MM-DD", "at": "", "title": "Billing onsite",
   "place": "", "focus": "What this session is for, in one or two sentences.",
   "agenda": [{"topic": "", "why": "", "owner": ""}],
   "bring": ["Anything he promised to have ready."]},
  {"kind": "standup", "date": "YYYY-MM-DD", "at": "10:30",
   "skipped": true, "reason": "Why not, if it is not running."}
],
"xws": {
  "for_date": "YYYY-MM-DD, the Friday",
  "at": "11:00",
  "built_at": "ISO 8601 with +09:00",
  "headline": "What he raises at the rollup this week, or that nothing is big enough.",
  "raised": [
    {"ref": "the ticket tag",
     "why": "One line: why this is big enough for the whole workstream.",
     "say": [{"ja_ruby": "One or two rollup-level lines with {漢字|かんじ} markup.",
              "en": "..."}]}
  ]
}
```

`xws` is not in `sessions` on purpose: it is the rollup card, not a walk. Leave
`raised` empty when nothing clears the bar, and let `headline` carry the week.

Do not write `where_it_stands` inside `prep`. The speaking view reads it from the
ticket, so there is one status and the script can never contradict the desk.

Every `en` line under a Japanese one is what tells him what he is about to say, so
a Japanese term left sitting in it has not been translated. **Any term you leave
in an English line must be in the board's `glossary`**, two or three words, and
the page puts the meaning in brackets after its first mention in the script. Add
what is missing rather than writing the brackets yourself, and never gloss inside
`ja_ruby` or `say_ja`: he reads those out to Tokyo Gas.

## Then rebuild and report

```
python3 render_desk.py    state/board.json output/desk.html
python3 render_desk_md.py state/board.json output/desk.md
```

Finish with a few lines: which session you wrote for, which tickets have an ask
on the table, which are status only, and anything he should check before he
speaks. Always write this, even when the answer is dull, because a silent run
cannot be told apart from a dead one. Never restate the whole script back to him.

The rules in `AGENTS.md` apply throughout, particularly: never send anything, and
never draft around a hold.
