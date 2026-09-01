#!/usr/bin/env python3
"""One-off: fold Eto's 15:53 answers into the ホールドリリース ticket.

Goes through board.load and board.save so the duplicate-number guard runs and
the file keeps its formatting, and returns without writing when the answers are
already on the board, because these scripts get re-run to see what they did.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import board as board_mod  # noqa: E402

DM = (
    "https://kraken.enterprise.slack.com/archives/D0BGN4Y3G3V"
    "/p1787900035222639?thread_ts=1787897680.245899&cid=D0BGN4Y3G3V"
)
REQ = "https://kraken.enterprise.slack.com/archives/C06S2FZTHEH/p1774329827822519"
ANSWERED_AT = "15:53"


def main() -> int:
    board = board_mod.load()

    ticket = next(
        (t for t in board["tickets"] if t.get("ref") == "ホールドリリース"), None
    )
    if ticket is None:
        print("no ホールドリリース ticket on the board; run add_hold_release_ticket.py first")
        return 1

    by_id = {i["id"]: i for i in ticket["items"]}
    missing = [n for n in (23, 24) if n not in by_id]
    if missing:
        owners = []
        for n in missing:
            other_ticket, other_item = board_mod.by_id(board, n)
            if other_item is not None:
                owners.append(f"  {n}: {other_ticket.get('ref')}: {other_item.get('title')}")
        print(f"items {missing} are not on this ticket, so nothing was written.")
        if owners:
            print("They belong to:")
            print("\n".join(owners))
        return 1

    if any(e.get("at") == ANSWERED_AT for e in ticket["events"]):
        print("Eto's answers are already on the board; nothing written")
        return 0

    ticket["where_it_stands"] = (
        "Fourth and last of the operations Koume's list split up. Eto asked at "
        "14:35 for it off the Notion runbook, bulk case only. Raised at 15:00, "
        "then corrected at 16:15 once Eto answered.\n\n"
        "He settled all three questions. TG can be told they get hold creation "
        "along with hold release, so that line stays. The re-evaluate job is out "
        "of scope: he added it after an incident, and in BAU the daily billing run "
        "picks the release up, so the second permission never comes into it. And "
        "he corrected the flow itself: TG build the CSV and name the reason, "
        "Kraken only run the job, which is the opposite of what the first draft "
        "said.\n\n"
        "Two gotchas came out of his own request thread and are now in both the "
        "ticket and the sheet. Accounts without a hold for the chosen reason are "
        "skipped silently rather than erroring, so a repeat request is harmless. "
        "And the screen reports success only, with no per-account result, so the "
        "hold list is the only place to check what happened.\n\n"
        "What is left is the sheet as an attachment, and the scope answer TG owe "
        "on all three tickets."
    )

    ticket["closes_when"] = [
        {
            "what": "The ticket raised in the TG-shared cycle project with the sheet",
            "who": "You",
            "state": "now",
            "note": "Item 23. Raised at 15:00 and corrected at 16:15. Only the PDF attachment is left.",
        },
        {
            "what": "Eto confirms the two findings and the scope",
            "who": "You",
            "state": "done",
            "note": "Item 24. Answered at 15:53. He also corrected who builds the CSV.",
        },
        {
            "what": "TG say whether BILLING_EXPERT is too wide",
            "who": "TG",
            "state": "next",
            "note": "The same question as on 強制発行 and 強制印刷. One answer covers all three.",
        },
        {
            "what": "TG say whether hold creation coming with hold release is acceptable",
            "who": "TG",
            "state": "next",
            "note": "New to this ticket. Eto confirmed TG should be told.",
        },
        {
            "what": "Access granted to the people TG name",
            "who": "Kraken",
            "state": "next",
        },
        {
            "what": "A walkthrough session where TG release a hold themselves",
            "who": "You and TG",
            "state": "next",
            "note": "Can share the 強制発行 session.",
        },
    ]

    ticket["threads"] += [
        {
            "label": "TG's standing request thread for bulk hold release, since Mar 2026",
            "where": "Slack #ext-proj-tokyogas-billing",
            "url": REQ,
        },
        {
            "label": "Eto's answers on scope and the re-evaluate job",
            "where": "Slack DM",
            "url": DM,
        },
    ]

    ticket["events"] += [
        {
            "on": "2026-08-28",
            "at": "15:14",
            "who": "You",
            "what": (
                "Sent Eto the ticket with the two findings: release and create are "
                "one permission, and the released hold sits on the bill until a "
                "re-evaluation."
            ),
            "so_what": "",
            "where": "Slack DM",
            "source_url": (
                "https://kraken.enterprise.slack.com/archives/D0BGN4Y3G3V"
                "/p1787897680245899"
            ),
        },
        {
            "on": "2026-08-28",
            "at": ANSWERED_AT,
            "who": "Hitoshi Eto, Kraken",
            "what": (
                "Answered all three. TG should be told they can create manual "
                "holds on the current permission. The re-evaluate job is a "
                "separate topic he added after incident support, and in BAU TG can "
                "wait for the next run, which is daily. And he corrected the flow: "
                "TG provide the list, not Kraken."
            ),
            "so_what": (
                "The second permission drops out of the handover entirely, and the "
                "現状 paragraph in the ticket and the sheet were the wrong way round."
            ),
            "where": "Slack DM",
            "source_url": DM,
        },
        {
            "on": "2026-08-28",
            "at": "16:15",
            "who": "You",
            "what": (
                "Corrected the ticket and rebuilt the sheet: TG build the CSV, the "
                "daily run applies the release, unmatched accounts are skipped "
                "silently and the screen reports success only."
            ),
            "so_what": "",
            "where": "Asana, Billing 2-Week Cycle [TG shared]",
            "source_url": ticket["asana_url"],
        },
    ]

    item23 = by_id[23]
    prep = item23["prepared"]
    prep["built_at"] = "2026-08-28 16:15"
    prep["conclusion"] = (
        "Same BILLING_EXPERT grant as the other two, so TG answer the scope "
        "question once for three tickets. This one carries a cost the others do "
        "not: the permission that releases holds also creates them, and Eto "
        "confirmed TG should be told that plainly."
    )
    prep["findings"] = [
        "Release and create share BILLING.MANAGE_MANUAL_HOLDS. Giving TG hold release necessarily gives them bulk hold creation, and no role separates the two without a new permission in code. Eto confirmed at 15:53 that TG should be told.",
        "TG's BILLING_EXPERT already carries MANAGE_MANUAL_HOLDS, added on the TG client on top of the base role, so this is the same one grant as 強制発行 and 強制印刷.",
        "TG build the CSV and name the reason; Kraken only run the job. Eto's own request template asks for a CSV with an account_number header plus the reason, and every request in that thread since March has arrived that way. The first draft had it backwards.",
        "The re-evaluate job is out of the handover. Eto added it after incident support, and in BAU the daily billing run picks the release up, so BILLING_EXPERT is enough and the second permission never comes into it.",
        "Accounts with no valid hold for the chosen reason are skipped silently, not errored, so a repeat request that includes already-released accounts is harmless. Eto confirmed this to Koume on 24 April, when she asked exactly that.",
        "The screen reports success only, with no per-account result, so the hold list is the only place to confirm what happened. Koume has already said a per-row report is not needed.",
        "Only holds with the chosen reason are invalidated. A bill held for a second reason stays held.",
        "A malformed CSV is the recurring failure. It has bitten twice, on 15 May and 28 July, both times stray characters in TG's file rather than anything in the job.",
        "Out of scope by Eto's own line: individual holds, and system-raised holds, which are released through the 強制発行 job's release_holds option.",
    ]
    prep["unanswered"] = [
        "Whether TG will accept that hold release brings hold creation with it. Eto is happy for them to be asked; nobody has put it to them yet, and it is the one question this ticket adds to the other two.",
    ]
    prep["sources"] = [
        {
            "label": "Eto's answers on scope, the re-evaluate job and who builds the list",
            "url": DM,
        },
        {
            "label": "The request template and the silent-skip answer to Koume",
            "url": REQ,
        },
        {
            "label": "Kraken's runbook, Release Bills (In Bulk), Manual Hold Cases",
            "url": "https://app.notion.com/p/1e673c742c71800e911dcae4ffc21aea",
        },
        {
            "label": "Both the create and the invalidate views on one permission",
            "url": (
                "https://github.com/octoenergy/kraken-core/blob/main/src/octoenergy"
                "/interfaces/supportsite/billing/views.py"
            ),
        },
        {
            "label": "MANAGE_MANUAL_HOLDS on TG's BILLING_EXPERT",
            "url": (
                "https://github.com/octoenergy/kraken-core/blob/main/src/octoenergy"
                "/plugins/clients/tokyogas/rbac/roles.py"
            ),
        },
    ]
    item23["progress_note"] = (
        "Raised at 15:00, corrected at 16:15 once Eto answered. Three changes: TG "
        "build the CSV rather than Kraken, the release lands on the daily run "
        "rather than needing a second permission, and the two gotchas from Eto's "
        "request thread are in, silent skips and success-only reporting. The sheet "
        "was rebuilt with the same corrections. Attaching it is the only step left."
    )
    item23["done_when"] = (
        "The ticket is up with the sheet on it, and TG can see the scope question "
        "is the same one they already have open plus the hold-creation one."
    )

    item24 = by_id[24]
    board_mod.set_state(
        item24, "done", note="Eto answered all three and corrected who builds the CSV"
    )
    item24["state_at"] = ANSWERED_AT
    item24["sent_by_you"] = True
    item24["draft"]["sent"] = True
    item24["draft"]["link"] = DM
    item24["progress_note"] = (
        "Sent at 15:14, answered at 15:53. TG should be told they get hold "
        "creation, so that line stays in the ticket. The re-evaluate job is out of "
        "scope: he added it after incident support and the daily run covers BAU. "
        "He also corrected the flow, TG provide the list rather than Kraken, which "
        "sent the ticket and the sheet back for a rewrite at 16:15."
    )

    board_mod.save(board)
    print("folded Eto's answers into the ticket, item 24 done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
