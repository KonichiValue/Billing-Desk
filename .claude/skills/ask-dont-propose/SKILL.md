---
name: ask-dont-propose
description: Use when drafting anything for a Kraken engineer or other technical reader (CE, IE, Core, Markets, an Ask IE request, a refinement post, an Asana ticket for CE/IE) where most of the technical content came from AI reading code or running queries rather than from an engineer. Turns AI-derived proposals into questions Rei could ask on his own.
---

# Ask, don't propose

Rei is not an engineer, and an engineer reading his message cannot tell which
lines he knows and which an AI read out of kraken-core. A message that proposes
a design ("I'd add a separate list that only `force_require_no_printing_comms`
reads, does that sound right?") invites a quick "yes" to something nobody on
their side has checked. Rei then quotes that "yes" to TG as engineer-confirmed.
A message that asks ("can the slip part be done on its own?") makes the engineer
do the reading, and the answer he gets back is theirs.

So when AI produced most of the technical substance, the message asks and the
engineer answers. The AI's findings stay on the board, where Rei uses them to
check the answer when it arrives.

## When it applies

Any draft or ticket addressed to a technical reader where the specifics come
from AI rather than from:

- an engineer, in writing, somewhere Rei can link;
- something Rei saw himself on the support site, a bill, a slip or a PDF;
- what TG said or asked.

It does not apply to Japanese drafts to TG, which keep the house AI caveat line
(※AIを使ってKrakenのコードを確認した内容です…) and follow `prompt-post.md`.

## The rules

1. **Every technical point is a question.** Write it from what Rei can observe:
   what TG want, what broke, what the screen shows, what the engineer said
   above. Not "X does Y, so I'll do Z", but "TG want A. Would B also cause C? If
   so, can A be done on its own?"
2. **No code-derived names or answers in the message.** No function names,
   constant or list names, file paths, line numbers, or reason sets read from
   the code. That includes a question with the AI's answer attached: "so 請求金額修正,
   調整額 and the 欠損 reasons do too, right?" becomes "Is it only 料金修正, or
   are there others?"
3. **Keep every fact.** Observations, accounts, dates, what TG agreed, what TG
   want, deadlines, who is cc'd. Asking instead of proposing removes conclusions,
   not information. Facts without instructions, as for internal tickets: never
   tell the engineer how to investigate.
4. **Quote what is already confirmed.** Anything an engineer has said in the
   thread, or Rei has verified himself, can be stated plainly, in their words.
   "Since TG want to stop the slip based on the reason, it sounds like hard-coded
   reasons are the way to go" is fine after Stephen recommended exactly that.
5. **A disclaimer is not a licence.** "No CE has checked any of this yet" at the
   top does not make a code-derived proposal acceptable lower down. The engineer
   still gets a leading question.
6. **The AI's findings go to `prepared`, not the message.** Put the code
   reading, function names and expected answer in the item's `prepared.findings`
   or `notes`, so Rei can tell whether the reply is complete or skipped a point.
7. **If Rei asks for the proposal version, write it, but label it** in the draft
   `target` or a note as resting on unconfirmed AI code reading. Keep the asking
   version alongside, so the choice stays his.

## The test

For each sentence: if the engineer asked "where did you get that?", could Rei
answer without "the AI read the code"? If not, turn the sentence into a question
or move it to `prepared`.

## Example

Proposing (AI did the reading, the engineer only has to nod):

> 3. 料金修正 (rate correction) stops the slip through TOKYOGAS_MANUAL_CHARGE_REASONS
> / _CREDIT_REASONS, but bill_has_manual_charges_or_credits uses the same lists to
> switch off late interest. TG want late interest kept on these bills, so I'd add a
> separate list that only force_require_no_printing_comms reads. Does that sound right?
>
> 4. From the code, any reason in those two lists switches off late interest, so
> 請求金額修正, 調整額, the 欠損 (loss) reasons and 利息延滞 do too. Can you confirm
> that's the full set?

Asking (every line traces to TG or the engineer):

> 3. TG want the slip stopped, the same as for 料金修正 (rate correction), but they
> want late interest still calculated on these bills. Would treating them like
> 料金修正 also switch off late interest? If so, can the slip part be done on its own?
>
> 4. TG also asked which reasons switch off late interest. Is it only 料金修正, or
> are there others?

The code reading behind 3 and 4 (the two lists, the late-interest function, the
ten codes) went into item 52's `prepared.findings` instead.
