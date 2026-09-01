#!/usr/bin/env python3
"""One-off: add the 手動ホールドリリース handover ticket to the board.

Applied on 2026-08-28, so this is mostly the record of what went onto the board
rather than something to run again. It stays runnable because `state/` is not in
git, and a board restored from a backup may need this ticket put back.

It writes through `board.save`, which is the only safe way in. That refuses a
board where two items share a number, and it writes the two-space indent every
other writer here uses. The first version of this script did neither: it appended
the ticket unconditionally, so a second run would have given the board a second
ホールドリリース and a second pair of items 23 and 24, and it wrote `indent=1`,
which reformats all 240KB of the file into a diff nobody can read.

Item numbers are how Rei refers to his own work, so 23 and 24 are written out
here rather than taken from `board.next_id` at runtime: they are already on the
real board, and the `closes_when` notes below name them in prose. If the board
has moved on and those numbers belong to something else, that is a renumbering
decision for a person, so this refuses to write rather than guessing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import board as B  # noqa: E402  (needs the path insert above)

REF = "ホールドリリース"

TICKET_URL = (
    "https://app.asana.com/1/696560454032998/project/1209230965235758"
    "/task/1217938859449079"
)
XWS = (
    "https://kraken.enterprise.slack.com/archives/C06S2FZTHEH"
    "/p1787895332798029?thread_ts=1787813255.107989&cid=C06S2FZTHEH"
)

ticket = {
    "id": "1217938859449079",
    "ref": "ホールドリリース",
    "title_ja": "手動ホールドの一括解除作業の東京ガス様への移管",
    "title_en": "Hand bulk manual hold release to TG",
    "asana_url": TICKET_URL,
    "asana": {
        "status": "要件未着手",
        "section": "New Ticket",
        "project": "Billing 2-Week Cycle [TG shared]",
        "priority": "Other",
        "category": "Planning",
        "assignee": "",
    },
    "internal_ticket": {},
    "where_it_stands": (
        "Fourth and last of the operations Koume's list split up, and the one "
        "Heqing called the complicated one. He gave it to Eto to check first; "
        "Eto came back at 14:35 saying raise it off the Notion runbook, bulk "
        "case only, and to ask if anything needed checking.\n\n"
        "Two things did. Release and create are the same permission, "
        "BILLING.MANAGE_MANUAL_HOLDS, so TG cannot be given hold release "
        "without also being given hold creation, and no narrow role separates "
        "them without a code change. And invalidating the manual hold does not "
        "lift the hold already sitting on a pending bill: that needs "
        "bulk_reevaluate_holds_for_accounts, which runs on "
        "EVALUATE_BILLING_DOCUMENT_HOLDS, a permission BILLING_EXPERT does not "
        "carry. So the handover as the runbook describes it spans two "
        "permissions and BILLING_EXPERT covers only the first.\n\n"
        "The ticket is up, unassigned, with Koume following. It states both "
        "facts and adds a third TG decision: whether the re-evaluate job comes "
        "across too. The sheet is built and is Rei's to attach."
    ),
    "closes_when": [
        {
            "what": "The ticket raised in the TG-shared cycle project with the sheet",
            "who": "You",
            "state": "now",
            "note": "Item 23. Raised at 15:00. Only the PDF attachment is left.",
        },
        {
            "what": "Eto sees the two findings before TG act on the ticket",
            "who": "You",
            "state": "now",
            "note": "Item 24. He asked to be told if anything needed checking.",
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
            "note": "New to this ticket. The other two do not carry it.",
        },
        {
            "what": "TG say whether the re-evaluate job moves across too",
            "who": "TG",
            "state": "next",
            "note": "If yes, BILLING_EXPERT is not enough and the scope answer changes.",
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
    ],
    "terms": [
        {
            "term": "Manual hold",
            "say": "{手動|しゅどう}ホールド",
            "means": (
                "A hold a person put on a bill, as against one the system "
                "raised. Only manual holds are in this ticket; system holds "
                "are released through the 強制発行 job."
            ),
            "source_url": "https://app.notion.com/p/1e673c742c71800e911dcae4ffc21aea",
        },
        {
            "term": "Re-evaluate holds",
            "say": "{再評価|さいひょうか}",
            "means": (
                "The job that re-runs the hold checks on a pending bill. "
                "Without it, invalidating the manual hold leaves the hold "
                "already on the bill in place until the next billing run."
            ),
            "source_url": (
                "https://github.com/octoenergy/kraken-core/blob/main/src/octoenergy"
                "/interfaces/systemjobs/management/commands"
                "/bulk_reevaluate_holds_for_accounts.py"
            ),
        },
    ],
    "threads": [
        {
            "label": "X-Workstream 個別議題 thread where the four operations were split",
            "where": "Slack #ext-proj-tokyogas-billing",
            "url": XWS,
        },
    ],
    "events": [
        {
            "on": "2026-08-28",
            "at": "12:03",
            "who": "Heqing Qian, Kraken",
            "what": (
                "Said no ticket exists for hold release, called it the more "
                "complex one and asked Eto to check it and raise it if he could."
            ),
            "so_what": "The ask started with Eto, not Rei.",
            "where": "Slack #ext-proj-tokyogas-billing",
            "source_url": (
                "https://kraken.enterprise.slack.com/archives/C06S2FZTHEH"
                "/p1787886225618889?thread_ts=1787813255.107989&cid=C06S2FZTHEH"
            ),
        },
        {
            "on": "2026-08-28",
            "at": "14:35",
            "who": "Hitoshi Eto, Kraken",
            "what": (
                "Asked Rei to raise the manual hold release ticket off the "
                "Notion runbook, said the bulk case alone is enough, and to "
                "come back with anything that needed checking."
            ),
            "so_what": (
                "Scopes the ticket to bulk manual holds and leaves the "
                "individual and system-held cases out."
            ),
            "where": "Slack #ext-proj-tokyogas-billing",
            "source_url": XWS,
        },
        {
            "on": "2026-08-28",
            "at": "15:00",
            "who": "You",
            "what": (
                "Raised セルフサービス化：手動ホールドの一括解除作業 in the "
                "TG-shared cycle project, unassigned, stating that release and "
                "create share one permission and that the re-evaluate job sits "
                "outside BILLING_EXPERT. Koume follows it."
            ),
            "so_what": "Eto's ask is answered, with the two findings on the record TG read.",
            "where": "Asana, Billing 2-Week Cycle [TG shared]",
            "source_url": TICKET_URL,
        },
    ],
    "items": [
        {
            "id": 23,
            "title": "Attach the sheet to the ホールドリリース ticket, now that it is up",
            "why": (
                "Eto asked for the ticket off the Notion runbook and TG are "
                "reading the thread. The 強制発行 and 強制印刷 tickets are the "
                "named model and both carry a sheet."
            ),
            "prepared": {
                "what": (
                    "The Japanese ticket body and the handover sheet, written "
                    "against the bulk manual hold release path only."
                ),
                "conclusion": (
                    "Same BILLING_EXPERT grant as the other two, so TG answer "
                    "the scope question once for three tickets. But this one "
                    "carries a cost the others do not: the permission that "
                    "releases holds also creates them."
                ),
                "built_at": "2026-08-28 15:00",
                "findings": [
                    "Release and create share BILLING.MANAGE_MANUAL_HOLDS. Giving TG hold release necessarily gives them bulk hold creation, and no role separates the two without a new permission in code.",
                    "TG's BILLING_EXPERT already carries MANAGE_MANUAL_HOLDS, added on the TG client on top of the base role, so this is the same one grant as 強制発行 and 強制印刷.",
                    "Invalidating the manual hold does not lift the hold already on a pending bill. That needs a re-evaluation, so the bill stays blocked until the job runs or the next billing run re-evaluates it. The runbook calls the step optional, which reads as more optional than it is.",
                    "bulk_reevaluate_holds_for_accounts runs on EVALUATE_BILLING_DOCUMENT_HOLDS, which sits on FULL_OPS_USER and not on BILLING_EXPERT. Handing over the full operation therefore spans two permissions.",
                    "Invalidate takes a CSV with an account_number header and a hold reason chosen in the form. Only holds with that reason are invalidated; a bill held for a second reason stays held.",
                    "The Create Reason button is hidden for BILLING_EXPERT, since CREATE_MANUAL_HOLD_REASONS is not on the role. TG could create holds against existing reasons but not add new reasons through the UI.",
                    "Strict holds are not treated differently by bulk invalidate. Strictness bites later: a strict document hold is only released by re-evaluation, never by hand.",
                    "Out of scope by Eto's own line: individual holds, and system-raised holds, which are released through the 強制発行 job's release_holds option.",
                ],
                "unanswered": [
                    "Whether TG will accept that hold release brings hold creation with it. Nobody has put this to them yet and it is the one question this ticket adds.",
                    "Whether the re-evaluate job is part of the handover. If it is, BILLING_EXPERT is not enough and the scope answer changes for this ticket alone.",
                ],
                "files": [
                    {
                        "label": "手動ホールドの一括解除について, the sheet TG receive, PDF",
                        "path": "docs/手動ホールドの一括解除について.pdf",
                    }
                ],
                "sources": [
                    {
                        "label": "Kraken's runbook, Release Bills (In Bulk), Manual Hold Cases",
                        "url": "https://app.notion.com/p/1e673c742c71800e911dcae4ffc21aea",
                    },
                    {
                        "label": "Both the create and the invalidate views on one permission",
                        "url": (
                            "https://github.com/octoenergy/kraken-core/blob/main/src"
                            "/octoenergy/interfaces/supportsite/billing/views.py"
                        ),
                    },
                    {
                        "label": "MANAGE_MANUAL_HOLDS on TG's BILLING_EXPERT",
                        "url": (
                            "https://github.com/octoenergy/kraken-core/blob/main/src"
                            "/octoenergy/plugins/clients/tokyogas/rbac/roles.py"
                        ),
                    },
                    {
                        "label": "The re-evaluate job and its separate permission",
                        "url": (
                            "https://github.com/octoenergy/kraken-core/blob/main/src"
                            "/octoenergy/interfaces/systemjobs/management/commands"
                            "/bulk_reevaluate_holds_for_accounts.py"
                        ),
                    },
                ],
            },
            "steps": [
                "Open the ticket and drag docs/手動ホールドの一括解除について.pdf onto it. That filename is what TG see, and it matches the 添付 line in the body.",
                "Add Tanaka as a follower if you added him to the other two.",
            ],
            "done_when": (
                "The ticket is up with the sheet on it, and TG can see the "
                "scope question is the same one they already have open plus "
                "one more."
            ),
            "draft": {
                "target": "Asana, Billing 2-Week Cycle [TG shared], New Ticket",
                "link": TICKET_URL,
                "language": "ja",
                "title_ja": "セルフサービス化：手動ホールドの一括解除作業",
                "posted": "2026-08-28 15:00",
            },
            "state": "todo",
            "state_at": "",
            "state_note": "",
            "sent_by_you": False,
            "opened": "2026-08-28",
            "committed_to": "",
            "progress_note": (
                "Raised at 15:00, written short like 強制印刷 rather than the "
                "longer 強制発行 body. The permission list is not repeated: it "
                "points at the 強制発行 ticket, since one grant covers all "
                "three. Attaching the sheet is the only step left."
            ),
            "where": "Asana, Billing 2-Week Cycle [TG shared]",
            "link": TICKET_URL,
            "blocked_by": "",
            "urgency": "today",
            "est_minutes": 3,
            "source_quote": "Notionのこの部分を使って、手動ホールドリリースのチケットも作ってもらえますか？",
            "source_url": XWS,
            "history": [],
            "at_standup": False,
            "at_standup_note": "",
        },
        {
            "id": 24,
            "title": "Tell Eto the two things the runbook does not say",
            "why": (
                "He asked to be told if anything needed checking, and both "
                "findings change what TG are being offered. He owns this "
                "operation, so he should see them before Koume acts."
            ),
            "steps": [
                "Send the DM or reply in the thread, whichever he used.",
                "If he wants either line out of the ticket, edit the ticket rather than commenting on it.",
            ],
            "done_when": (
                "Eto has confirmed the ticket can say hold release brings hold "
                "creation with it, and said whether the re-evaluate job is part "
                "of the handover."
            ),
            "draft": {
                "target": "Slack, reply to Eto in the X-Workstream thread",
                "link": XWS,
                "language": "en",
                "sent": False,
            },
            "state": "todo",
            "state_at": "",
            "state_note": "",
            "sent_by_you": False,
            "opened": "2026-08-28",
            "committed_to": "",
            "progress_note": "",
            "where": "Slack #ext-proj-tokyogas-billing",
            "link": XWS,
            "blocked_by": "",
            "urgency": "today",
            "est_minutes": 5,
            "source_quote": "確認する点があれば、声かけてください！",
            "source_url": XWS,
            "history": [],
            "at_standup": False,
            "at_standup_note": "",
        },
    ],
}

b = B.load()

if any(t.get("ref") == REF or t.get("id") == ticket["id"] for t in b["tickets"]):
    print(f"{REF} is already on the board. Nothing to do.")
    raise SystemExit(0)

mine = [str(i["id"]) for i in ticket["items"]]
taken = {str(i.get("id")): t.get("ref") for t, i in B.items(b)}
clash = sorted((n, taken[n]) for n in mine if n in taken)
if clash:
    print(
        "these numbers belong to other work now: "
        + ", ".join(f"{n} on {ref}" for n, ref in clash),
        file=sys.stderr,
    )
    print(
        "Renumber this ticket's items, and the closes_when notes naming them, "
        "before running it again.",
        file=sys.stderr,
    )
    raise SystemExit(1)

b["tickets"].append(ticket)
# Never rewind. A next_id behind the board hands the next writer a number that is
# already taken, which is how items 20 and 22 collided once already.
b["next_id"] = max(b.get("next_id", 1), max(int(n) for n in mine) + 1)
B.save(b)
print(f"added {REF}, items {', '.join(mine)}, next_id {b['next_id']}")
