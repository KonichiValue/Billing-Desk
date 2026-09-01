#!/usr/bin/env python3
"""Render the board into one self-contained HTML file with two views.

The desk view answers "what do I do", grouped by ticket because that is how the
work gets done. The standup view answers "what do I say at 10:30", in the order
the meeting walks the board. Same tickets, same file, one source of truth, and
switching between them costs a keystroke.

Usage:
    python3 render_desk.py state/board.json output/desk.html
    python3 render_desk.py --error "message" output/desk.html
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import render_standup
from render import (
    ASKED,
    CSS,
    JS,
    SPARK,
    answered,
    apply_glossary,
    ask_block,
    blocked_on,
    code,
    day_words,
    esc,
    furi,
    index_items,
    item_order,
    item_state as state_of,
    pressing,
    link_btn,
    load_asks,
    next_live,
    opening,
    pill,
    plain,
    script_meta,
    script_session,
    section,
    sessions,
    tracked,
    short_when,
    when_tag,
    when_words,
)

EXTRA_CSS = """
.panel{background:var(--card);border:1px solid var(--line);border-radius:13px}
.tk .sub:last-of-type{border-bottom:0;padding-bottom:0}
/* A card is one ticket. The bar across the top and the tinted header block are
   there so the eye never has to work out where one ticket ends. */
.tk{padding:0 22px 20px;margin-bottom:20px;scroll-margin-top:96px;
border-top:4px solid var(--line);overflow:hidden}
.tk.mine{border-top-color:var(--red)}
.tk.theirs{border-top-color:#8fbcf7}
.tk.clear{border-top-color:var(--green)}
.tk-head{margin:0 -22px;padding:14px 22px 15px;border-bottom:1px solid var(--line);
background:linear-gradient(180deg,#fbfcfe,#fff)}
.tk.mine .tk-head{background:linear-gradient(180deg,var(--red-bg),#fff)}
.tk-id{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:7px}
.tk-id .tag{margin:0;font-size:14px;padding:3px 11px;vertical-align:0}
.tk-kind{font-size:10px;text-transform:uppercase;letter-spacing:.09em;
color:#9aa3b2;font-weight:700}
.tk-head h2{margin:0;font-size:18.5px;letter-spacing:-.018em;line-height:1.3;
font-weight:700}
.tk-ja{margin:4px 0 0;font-size:14px;color:var(--mut)}
.tk-meta{margin:10px 0 0;display:flex;gap:7px;align-items:center;flex-wrap:wrap;
font-size:12px;color:var(--soft)}
.tk-chip{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:6px;
background:var(--hair);color:var(--mut);border:1px solid var(--line)}
/* Labelled, because a bare 調査中 beside a bare Issue is two unexplained words. */
.tk-chip b{font-weight:700;font-size:10px;text-transform:uppercase;
letter-spacing:.06em;color:#9aa3b2;margin-right:5px}
/* Work he is carrying that Asana has never heard of. It belongs on the board
   the same as a ticket, and the card has to say which one it is. */
.tk-noticket{margin:10px 0 0;padding:8px 11px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
line-height:1.5;color:var(--amber-ink)}
.tk-noticket b{display:block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.07em;color:var(--amber);margin-bottom:2px}
.tk-chip.warn{background:var(--red-bg);color:var(--red);border-color:var(--red-line)}
.tk-chip.warn b{color:var(--red)}
/* The Kraken build sits inside Where it stands, because "queued behind an
   engineer" is half the answer to where a TG ticket is. Sentence case
   throughout: this is read, not scanned, and small capitals in a block this
   dense read as noise. */
.bld{margin:12px 0 0;border:1px solid var(--line);border-radius:10px;
background:#fbfcfe;overflow:hidden}
.bld-head{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;
padding:9px 13px;background:#fff;border-bottom:1px solid var(--line)}
.bld-k{flex:none;font-size:11.5px;font-weight:700;color:var(--soft)}
.bld-kt{font-size:13px;font-weight:700;color:var(--ink);
font-variant-numeric:tabular-nums}
.bld-head .keep{margin-left:auto;font-size:11.5px;font-weight:600;
color:var(--amber)}
.bld-body{padding:12px 13px}
/* Six stops, left to right, so the distance still to run is a shape and not a
   sentence. Green is behind it, accent is where it is, grey is ahead. */
.rail{display:flex;margin:0 0 11px;padding:0;list-style:none;background:#fff;
border:1px solid var(--line);border-radius:7px;overflow:hidden}
.rail li{flex:1;min-width:0;padding:6px 5px;text-align:center;font-size:10.5px;
font-weight:650;color:#9aa3b2;border-right:1px solid var(--line);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rail li:last-child{border-right:0}
.rail li.done{background:var(--green-bg);color:var(--green)}
.rail li.at{background:var(--accent);color:#fff;font-weight:750}
.bld-now{margin:0;font-size:14px;line-height:1.5;color:var(--ink)}
.bld-now b{font-weight:700}
.bld-facts{margin:9px 0 0;display:flex;gap:4px 18px;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.bld-facts b{font-weight:650;color:var(--mut)}
.bld-facts .odd b{color:var(--amber)}
.bld-tg{margin:10px 0 0;padding:8px 11px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
line-height:1.55;color:var(--amber-ink)}
.bld-tg b{display:block;font-size:11.5px;font-weight:700;color:var(--amber);
margin-bottom:2px}
.bld.none{padding:10px 13px;display:flex;gap:9px;align-items:baseline;
flex-wrap:wrap;font-size:13.5px;color:var(--mut)}

/* The gates left before the ticket can close, in the order they have to fall.
   Same left-edge colour language as the item list: red is his, amber is stuck,
   blue is somebody else, green is behind him. */
.gates{margin:0;padding:0;list-style:none;display:grid;gap:1px;
background:var(--line);border:1px solid var(--line);border-radius:10px;
overflow:hidden}
.gate{background:#fff;display:flex;gap:11px;align-items:baseline;
padding:10px 13px;border-left:3px solid var(--line)}
.gate.done{border-left-color:var(--green);background:#fbfefc}
/* The hairlines between rows are the parent showing through, so a row that
   fades has to fade over its own white rather than over that grey. */
.gate.now{border-left-color:var(--red);background-color:#fff;
background-image:linear-gradient(90deg,var(--red-bg),rgba(255,255,255,0) 46%)}
.gate.blocked{border-left-color:#e2a03f}
.gate.next{border-left-color:#8fbcf7}
.g-m{flex:none;width:16px;height:16px;border-radius:50%;background:var(--hair);
border:1px solid var(--line);align-self:center;display:grid;place-items:center;
font-size:9.5px;font-weight:800;color:#fff}
.gate.done .g-m{background:var(--green);border-color:var(--green)}
.gate.done .g-m:after{content:"\\2713"}
.gate.now .g-m{background:var(--red);border-color:var(--red)}
.gate.blocked .g-m{background:var(--amber);border-color:var(--amber)}
.g-w{flex:1;min-width:0;font-size:14px;color:var(--ink);line-height:1.45}
.gate.done .g-w{color:var(--mut)}
.g-n{display:block;font-size:12.5px;color:var(--soft);margin-top:2px}
.g-who{flex:none;font-size:11.5px;font-weight:650;color:var(--soft);
text-align:right}
.gate.now .g-who{color:var(--red)}
/* On a phone six stops in one row become six ellipses, and the owner squeezes
   the gate down to two words a line. Both get their own row instead. */
@media (max-width:640px){
.rail{flex-wrap:wrap}
.rail li{flex:1 0 33.33%;border-bottom:1px solid var(--line)}
.rail li:nth-child(3n){border-right:0}
.rail li:nth-last-child(-n+3){border-bottom:0}
.gate{flex-wrap:wrap}
.g-w{flex:1 0 100%}
.g-who{margin-left:27px;text-align:left}
}
/* Links out live on their own row: they leave the page, the chips above do not. */
.tk-links{margin:12px 0 0;padding-top:11px;border-top:1px dashed var(--line);
display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.tk-links .lab{font-size:10px;text-transform:uppercase;letter-spacing:.08em;
color:#9aa3b2;font-weight:700;margin-right:1px}
.tk-links .keep{font-size:11.5px;color:var(--amber);font-weight:600}

/* One list, in the order the work sits: yours, blocked, theirs, finished. */
.track{overflow:hidden;margin-bottom:8px}
.track-head{display:flex;gap:12px;align-items:baseline;padding:13px 18px 11px;
border-bottom:1px solid var(--line)}
.track-head h2{margin:0;font-size:14px;letter-spacing:-.01em;font-weight:650}
.track-head span{font-size:12.5px;color:var(--soft);margin-left:auto;
font-variant-numeric:tabular-nums}
.track-head .track-key{margin-left:0;font-size:11.5px;color:#9aa3b2}
.track-closed>summary{cursor:pointer;padding:11px 18px;font-size:12.5px;
color:var(--soft);border-top:1px solid var(--line);background:var(--hair);
display:flex;gap:8px;align-items:center}
.track-closed>summary b{font-weight:700;color:var(--mut)}
.track-closed>summary:hover{color:var(--ink)}
.tr{display:flex;gap:11px;padding:10px 18px;border-bottom:1px solid var(--hair);
align-items:center;border-left:3px solid transparent}
.tr:last-child{border-bottom:0}
.tr.mine{border-left-color:var(--red);background:linear-gradient(90deg,
var(--red-bg),rgba(255,255,255,0) 42%)}
.tr.blocked{border-left-color:#e2a03f}
.tr.theirs{border-left-color:#8fbcf7}
/* Due now or due today, whoever holds it: the one row on the list with a clock
   running on it, so it reads red even when it is sitting with someone else. */
.tr.tr-hot{border-left-color:var(--red);border-left-width:4px;
background:linear-gradient(90deg,var(--red-bg),rgba(255,255,255,0) 42%)}
.tr.tr-hot .when{color:var(--red)}
.tr-rank{flex:none;width:21px;font-size:12px;font-weight:700;color:var(--soft);
font-variant-numeric:tabular-nums}
.tr-tag{flex:none;font-size:12px;font-weight:700;padding:2px 8px;border-radius:6px;
background:var(--hair);color:var(--mut)}
.tr-title{flex:1;min-width:0;font-size:14.5px;font-weight:550;color:inherit;
text-decoration:none}
.tr-title:hover{color:var(--accent)}
.tr-note{display:block;font-size:12px;color:var(--soft);font-weight:400;margin-top:1px}
.tr-min{flex:none;font-size:12px;color:var(--soft);font-variant-numeric:tabular-nums;
width:44px;text-align:right}
.tr.shut .tr-title{text-decoration:line-through;text-decoration-color:#a6afbe}
.tr.shut{opacity:.62}

/* The timeline, oldest first, one fold per day with the day as the handle. */
.ev-fold{margin-bottom:8px}
.ev-fold:last-child{margin-bottom:0}
.ev-fold>summary{cursor:pointer;padding:8px 11px;background:var(--hair);
border-radius:8px;display:flex;align-items:center;gap:10px}
.ev-fold[open]>summary{background:transparent;border-bottom:1px solid var(--hair);
border-radius:0;padding-left:1px;padding-right:1px}
.ev-fold>summary:hover .ev-d{color:var(--accent-ink)}
.ev-d{font-size:11px;font-weight:750;text-transform:uppercase;
letter-spacing:.07em;color:var(--mut)}
.ev-c{font-size:11px;color:var(--soft)}
.ev-fold .evs{margin-top:12px;padding-bottom:4px}
.evs{list-style:none;margin:0;padding:0;position:relative}
.evs:before{content:"";position:absolute;left:53px;top:6px;bottom:10px;width:2px;
background:var(--line)}
.ev{display:flex;gap:15px;padding:0 0 14px;position:relative}
.ev:last-child{padding-bottom:0}
.ev-at{flex:none;width:46px;text-align:right;padding-top:1px;
font-variant-numeric:tabular-nums;line-height:1.35}
.ev-at b{display:block;font-size:10px;font-weight:700;color:#9aa3b2;
text-transform:uppercase;letter-spacing:.03em}
.ev-at i{display:block;font-size:11.5px;font-weight:700;color:var(--soft);
font-style:normal}
.ev-body{flex:1;min-width:0;padding-left:18px;position:relative}
.ev-body:before{content:"";position:absolute;left:-5px;top:6px;width:10px;
height:10px;border-radius:50%;background:#fff;border:2px solid var(--accent)}
.ev-who{display:block;font-size:11.5px;font-weight:700;color:var(--accent);
text-transform:uppercase;letter-spacing:.05em}
.ev-what{display:block;font-size:14.5px;margin-top:2px}
.ev-so{display:block;margin-top:6px;padding:8px 12px;background:var(--accent-bg);
border:1px solid var(--accent-line);border-radius:8px;font-size:13.5px;
color:var(--accent-ink);font-weight:550}
.ev-src{display:block;font-size:11.5px;color:var(--soft);margin-top:6px}

/* Threads and shorthand. */
.thr{list-style:none;margin:0;padding:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.thr li{background:#fff;padding:10px 13px;display:flex;gap:12px;
align-items:baseline;flex-wrap:wrap}
.thr-where{flex:none;font-size:11.5px;font-weight:700;color:var(--accent);
min-width:185px}
.thr-body{flex:1;min-width:220px}
.thr-label{font-weight:600;font-size:14px}
.thr-gist{font-size:13px;color:var(--mut);margin-top:2px}
.thr-when{flex:none;font-size:11.5px;color:var(--soft);text-align:right;
font-variant-numeric:tabular-nums}
.thr-when b{display:block;color:var(--mut);font-weight:600}
.terms{margin:0;display:grid;gap:1px;background:var(--line);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
.term{background:#fbfcfe;padding:10px 13px;display:flex;gap:14px;
align-items:baseline;flex-wrap:wrap}
.terms dt{flex:none;width:172px;font-weight:700;font-size:13.5px;
color:var(--accent-ink)}
.terms dd{flex:1;min-width:240px;margin:0;font-size:13.5px;color:var(--mut)}
.term-ja{display:block;margin-top:3px;font-size:14px;font-weight:600;
color:var(--ink);line-height:1.7}
.term-ja ruby rt{font-size:.5em}

/* An item, and the colour of its left edge is where it sits. */
.act{border:1px solid var(--line);border-left:3px solid var(--line);
border-radius:11px;margin-bottom:12px;overflow:hidden;background:#fff}
.act.todo{border-left-color:var(--red)}
.act.hold,.act.held{border-left-color:#e2a03f;background:#fffdf6}
.act.held .act-head{background:var(--amber-bg)}
.act.waiting{border-left-color:#8fbcf7}
.act-head{display:flex;gap:10px;padding:11px 14px;align-items:center;
flex-wrap:wrap;background:#fbfcfe;border-bottom:1px solid var(--hair)}
.act-rank{width:23px;height:23px;flex:none;border-radius:6px;background:var(--ink);
color:#fff;display:grid;place-items:center;font-size:11.5px;font-weight:700}
.act-title{flex:1 1 250px;min-width:0;font-weight:600;font-size:15px}
.act-sub{display:block;font-size:12px;font-weight:400;color:var(--soft);margin-top:2px}
details.act>summary{cursor:pointer;list-style:none}
details.act>summary::-webkit-details-marker{display:none}
details.act>summary::before{display:none}
details.act:not([open])>summary{border-bottom:0}
details.act .act-title{font-weight:550}
details.act.waiting{background:#fcfdff}
details.act.done,details.act.sent,details.act.dropped{opacity:.7;
border-left-color:#ccd4e0}
details.act.done .act-title,details.act.sent .act-title{text-decoration:line-through;
text-decoration-color:#a6afbe}
.act-min{color:var(--soft);font-size:12px;font-variant-numeric:tabular-nums}
.act-body{padding:13px 15px}
/* The steps come first and look like the only thing worth doing, because on an
   open job they are. Everything under them is supporting material. */
.act-do{margin:0 0 12px}
.act-lab{margin:0 0 7px;font-size:10.5px;font-weight:750;text-transform:uppercase;
letter-spacing:.09em;color:var(--accent)}
ol.steps{margin:0;padding-left:19px;counter-reset:none}
ol.steps li{margin-bottom:6px;font-size:14.5px;color:var(--ink);line-height:1.5}
ol.steps li::marker{color:var(--soft);font-weight:700;font-size:12.5px}
ol.steps li:last-child{margin-bottom:0}
ol.steps code,.act-done code{font:600 12.5px/1.4 ui-monospace,SFMono-Regular,
Menlo,monospace;background:var(--hair);border:1px solid var(--line);
border-radius:5px;padding:1px 5px;word-break:break-all}
/* Work already done. It sits above the steps because it is the answer, and the
   steps under it are only what could not be done without him. */
.act-prep{margin:0 0 14px;padding:11px 13px 12px;background:var(--green-bg);
border:1px solid var(--green-line);border-radius:10px}
.act-lab.done{color:var(--green)}
.pw-what{margin:0 0 9px;font-size:14.5px;color:var(--ink);font-weight:550}
.pw-answer{margin:0 0 10px;padding:9px 11px;background:#fff;
border:1px solid var(--green-line);border-radius:8px;font-size:14px;
line-height:1.5;color:var(--ink)}
.pw-answer b,.pw-note b{display:block;margin-bottom:3px;font-size:10.5px;
text-transform:uppercase;letter-spacing:.07em;color:var(--green)}
.pw-t{width:100%;border-collapse:collapse;margin:0 0 10px;font-size:12.5px;
background:#fff;border:1px solid var(--green-line);border-radius:8px;
overflow:hidden}
.pw-t th{text-align:left;padding:7px 9px;font-size:10.5px;font-weight:750;
text-transform:uppercase;letter-spacing:.06em;color:var(--soft);
background:var(--hair);border-bottom:1px solid var(--line);vertical-align:top}
.pw-t td{padding:7px 9px;border-bottom:1px solid var(--hair);color:var(--mut);
vertical-align:top;line-height:1.45}
.pw-t tr:last-child td{border-bottom:0}
.pw-t td:first-child{color:var(--ink);font-weight:550}
.pw-t code{font:600 11.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
word-break:break-all}
/* A verdict cell, so the row that is the problem is findable without reading
   all four columns of every row. */
.pw-v span{display:inline-block;padding:2px 8px;border-radius:999px;
font-size:11px;font-weight:700;border:1px solid}
.pw-v .v-good{background:var(--green-bg);border-color:var(--green-line);
color:var(--green)}
.pw-v .v-gap{background:var(--red-bg);border-color:var(--red-line);color:var(--red)}
.pw-v .v-warn{background:var(--amber-bg);border-color:var(--amber-line);
color:var(--amber-ink)}
.pw-f{margin:0;padding-left:18px}
.pw-f li{font-size:14px;color:var(--ink);margin-bottom:5px;line-height:1.5}
.pw-f li:last-child{margin-bottom:0}
.pw-f code{font:600 12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
background:#fff;border:1px solid var(--green-line);border-radius:5px;
padding:1px 5px;word-break:break-all}
.pw-note{margin:9px 0 0;padding-top:9px;border-top:1px solid var(--green-line);
font-size:13.5px;line-height:1.5;color:var(--mut)}
/* What the work could not settle. Prepared work that hides its own gaps reads
   as a finished answer, and he takes it into a room on that basis. */
.pw-open{margin:10px 0 0;padding:9px 11px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
line-height:1.5;color:var(--amber-ink)}
.pw-open b{display:block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.07em;color:var(--amber);margin-bottom:3px}
.pw-open ul{margin:0;padding-left:17px}
.pw-open li{margin-bottom:3px}
.pw-open li:last-child{margin-bottom:0}
.pw-meeting{margin:10px 0 0;display:flex;gap:9px;align-items:center;
flex-wrap:wrap;font-size:12.5px;color:var(--mut)}
.pw-src{margin:10px 0 0;display:flex;gap:7px;align-items:center;flex-wrap:wrap;
font-size:11.5px;color:var(--soft)}
.act-nosteps{margin:0 0 11px;padding:9px 12px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
color:var(--amber-ink)}
.act-nosteps b{display:block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.08em;margin-bottom:2px}
.act-done{margin:0 0 10px;font-size:13.5px;color:var(--mut)}
.act-why{margin:0 0 10px;font-size:13.5px;color:var(--mut)}
.act-done b,.act-why b{display:inline-block;font-size:10.5px;
text-transform:uppercase;letter-spacing:.08em;color:var(--soft);margin-right:8px;
font-weight:700;vertical-align:1px}
.act-body ul{margin:0;padding-left:18px}
.act-body li{margin-bottom:4px;font-size:14px;color:var(--mut)}
.act-where{margin:9px 0 0;display:flex;gap:9px;align-items:center;flex-wrap:wrap;
font-size:12.5px;color:var(--soft)}
.act-commit{margin:11px 0 0;padding:8px 12px;background:var(--red-bg);
border:1px solid var(--red-line);border-radius:8px;font-size:13px;color:var(--red);
font-weight:550}
.act-block{margin:11px 0 0;padding:8px 12px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
color:var(--amber-ink)}
.act-quote{margin:11px 0 0;padding-left:12px;border-left:3px solid var(--line);
font-size:12.5px;color:var(--soft);font-style:italic}
/* Why a job exists, under the job. One line until it is wanted. */
.act-more{margin:10px 0 0}
.act-more>summary{display:flex;gap:8px;align-items:center;padding:0;cursor:pointer;
font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
color:var(--soft)}
.act-more>summary:hover{color:var(--mut)}
.act-more[open]>summary{margin-bottom:2px}

/* Asking about the job you are looking at. Quiet until it is wanted: one small
   word at the bottom of the card, and the questions already answered above it,
   because why a draft says what it says belongs next to the draft. */
.ask{margin:12px 0 0;padding-top:10px;border-top:1px dashed var(--line)}
/* The one that is not on a card: a question about the day rather than a job.
   Sits under the strip above the tickets, where the counted sentence is. */
#view-desk>.ask{margin:0 0 14px;padding:0 2px;border-top:0}
.ask-bar{display:flex;gap:10px;align-items:center}
.ask-open,.ask-copy,.ask-cancel,.ask-send,.qa-chip{font:inherit;cursor:pointer;
border-radius:7px;border:1px solid var(--line);background:#fff;color:var(--mut);
font-size:12px;font-weight:650;padding:5px 11px}
/* The one button on a card that starts a conversation rather than opening a
   link, so it is the one with a mark on it and enough padding to look pressable
   from across the desk. */
.ask-open{display:inline-flex;gap:7px;align-items:center;padding:7px 13px;
font-size:12.5px;color:var(--plum-ink,#5b21b6);
border-color:var(--plum-line,#ddd6fe);background:var(--plum-bg,#f5f3ff)}
.ask-open .ask-of{font-weight:550;color:var(--plum,#7c3aed);opacity:.85}
.ask-open .spark{width:14px;height:14px;fill:currentColor;flex:none}
.ask-open:hover{background:#fff;border-color:var(--plum,#7c3aed);
box-shadow:0 1px 2px rgba(124,58,237,.14)}
.ask-open:hover .spark{transform:scale(1.08)}
.ask-open .spark{transition:transform .12s ease}
.qa-chip:hover,.ask-copy:hover,.ask-cancel:hover{border-color:#c9cfdb}
/* Same mark, quieter, where the entry point sits in a heading. */
.ask-here .spark{width:11px;height:11px;fill:currentColor;margin-right:4px;
vertical-align:-1px}
.ask-n{font-size:11px;font-weight:650;color:var(--soft)}
.ask-send{background:var(--plum,#7c3aed);border-color:var(--plum,#7c3aed);
color:#fff}
.ask-send:disabled{opacity:.55;cursor:default}
.ask-box{margin:10px 0 0}
.ask-box textarea{width:100%;box-sizing:border-box;font:inherit;font-size:13.5px;
line-height:1.5;padding:9px 11px;border:1px solid var(--line);border-radius:9px;
resize:vertical;color:var(--ink);background:#fff}
.ask-box textarea:focus{outline:2px solid var(--plum-line,#ddd6fe);
border-color:var(--plum,#7c3aed)}
.ask-chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 0}
.qa-chip{font-size:11.5px;font-weight:600;padding:4px 9px;color:var(--soft)}
.ask-go{display:flex;gap:8px;align-items:center;margin:9px 0 0;flex-wrap:wrap}
.ask-hint{font-size:11.5px;color:var(--soft)}
.ask-keys{font-size:11px;color:#9aa3b2;margin-left:auto}
.ask-lede{margin:0 0 8px;font-size:12.5px;color:var(--soft)}
/* Waiting on an answer, on the card that asked. Thirty seconds to two minutes
   of nothing is long enough to reload the page and lose the question, so the
   count runs and the last line the agent printed shows underneath it. */
.ask-wait{display:flex;align-items:center;gap:8px;flex-wrap:wrap;
margin:9px 0 0;padding:8px 11px;border:1px solid var(--plum-line,#ddd6fe);
border-radius:9px;background:var(--plum-bg,#f5f3ff)}
.ask-wait-t{font-size:12px;font-weight:650;color:var(--plum-ink,#5b21b6)}
.ask-wait-tail{flex:1 1 100%;font-size:11.5px;line-height:1.45;color:var(--soft);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ask-dots{display:inline-flex;gap:3px;align-items:center}
.ask-dots i{width:5px;height:5px;border-radius:50%;
background:var(--plum,#7c3aed);animation:askdot 1.05s ease-in-out infinite}
.ask-dots i:nth-child(2){animation-delay:.16s}
.ask-dots i:nth-child(3){animation-delay:.32s}
@keyframes askdot{0%,80%,100%{opacity:.25;transform:translateY(0)}
40%{opacity:1;transform:translateY(-3px)}}
@media (prefers-reduced-motion:reduce){.ask-dots i{animation:none;opacity:.7}}
/* The way in from the draft and the prepared block, where the thing he wants
   changed actually is. Quiet: a word at the end of a label row. */
.ask-here{font:inherit;font-size:11px;font-weight:650;cursor:pointer;
border:1px solid var(--plum-line);background:var(--plum-bg);
color:var(--plum-ink);border-radius:6px;padding:3px 8px;letter-spacing:0;
text-transform:none}
.ask-here:hover{border-color:var(--plum)}
.act-lab .ask-here{margin-left:9px;vertical-align:1px}
.draft-head .ask-here{margin-left:0}
/* The answers. A chat window is gone by tomorrow; this is not.
   Every exchange is shut to a line: the question, when it was asked, and a Show.
   That is how he finds the one he half remembers without reading four answers on
   the way, and it is what keeps a card with a long conversation on it the same
   height as a card with one question. */
.qa-list{list-style:none;margin:0 0 10px;padding:0}
.qa{position:relative;border:1px solid var(--plum-line,#ddd6fe);border-radius:9px;
background:var(--plum-bg,#f8f7ff);margin-bottom:7px}
.qa>details>summary{display:flex;gap:9px;align-items:baseline;cursor:pointer;
padding:9px 34px 9px 12px;list-style:none}
.qa>details>summary::-webkit-details-marker{display:none}
.qa>details>summary::marker{content:""}
.qa>details[open]>summary{border-bottom:1px solid var(--plum-line,#ddd6fe)}
.qa-k{flex:none;font-size:10px;font-weight:750;text-transform:uppercase;
letter-spacing:.07em;color:var(--plum-ink,#5b21b6)}
/* Shut, the question is one line however long it was, because a four-line
   question shut is not much better than the answer open. Open, it wraps: he is
   reading the answer and needs the whole question above it. */
.qa-q{flex:1;min-width:0;font-size:13px;color:var(--ink);font-weight:600;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qa>details[open]>summary .qa-q{white-space:normal}
.qa-when{flex:none;font-size:11px;font-weight:600;color:var(--soft)}
.qa>details>summary .fold-hint{flex:none;font-size:9.5px}
.qa.running{border-style:dashed}
.qa.failed{border-color:var(--amber-line);background:var(--amber-bg)}
.qa-a{padding:10px 12px 0;font-size:13.5px;line-height:1.6;color:var(--mut)}
.qa-a p{margin:0 0 8px}
.qa-a p:last-child{margin-bottom:0}
.qa-a b{color:var(--ink)}
.qa-a ul{margin:0 0 8px;padding-left:17px}
.qa-a li{margin:2px 0}
.qa-a code{font:600 12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
background:#fff;border:1px solid var(--plum-line,#ddd6fe);border-radius:4px;
padding:1px 4px}
/* Forget this one. Top right of its own bubble, quiet until the bubble is
   hovered, because it throws something away. */
.qa-del{position:absolute;top:6px;right:7px;width:21px;height:21px;padding:0;
font:600 15px/1 inherit;cursor:pointer;color:var(--soft);background:transparent;
border:1px solid transparent;border-radius:6px;opacity:.3}
.qa:hover .qa-del,.qa-del:focus{opacity:1}
.qa-del:hover{color:var(--red);border-color:var(--red-line);background:#fff}
/* Pulling on one answer. The follow-ups sit inside the answer they are about,
   so the thread reads down and the card does not grow a second conversation. */
.qa-kids{list-style:none;margin:8px 12px 0;padding:0 0 0 11px;
border-left:2px solid var(--plum-line,#ddd6fe)}
.qa-kids .qa{background:#fff;margin-bottom:6px}
.qa-kids .qa-k{color:var(--soft)}
.qa-foot{padding:8px 12px 10px}
.qa-follow{display:inline-flex;gap:6px;align-items:center;font:inherit;
font-size:11.5px;font-weight:650;cursor:pointer;color:var(--plum-ink,#5b21b6);
background:#fff;border:1px solid var(--plum-line,#ddd6fe);border-radius:7px;
padding:5px 10px}
.qa-follow:hover{border-color:var(--plum,#7c3aed)}
.qa-follow .spark{width:12px;height:12px;fill:currentColor}
.fu{padding:0 12px 11px}
.fu textarea{width:100%;box-sizing:border-box;font:inherit;font-size:13px;
line-height:1.5;padding:8px 10px;border:1px solid var(--plum-line,#ddd6fe);
border-radius:8px;background:#fff;resize:vertical}
.fu textarea:focus{outline:none;border-color:var(--plum,#7c3aed)}
.fu .ask-go{margin-top:7px}
.fu-cancel{font:inherit;font-size:12px;font-weight:650;cursor:pointer;
border:1px solid var(--line);background:#fff;color:var(--mut);border-radius:7px;
padding:5px 11px}
/* Everything asked before the last two, behind one line. */
.qa-earlier{margin-bottom:8px}
.qa-earlier>summary{display:flex;gap:8px;align-items:center;cursor:pointer;
font-size:11.5px;font-weight:700;color:var(--soft);padding:4px 2px;
text-transform:uppercase;letter-spacing:.06em}
.qa-earlier>summary::-webkit-details-marker{display:none}
.qa-earlier>summary:hover{color:var(--plum-ink,#5b21b6)}
.qa-earlier[open]{padding-bottom:2px}
.act-draft{margin:12px 0 0;border:1px solid var(--line);border-radius:9px;
overflow:hidden}
.act-draft.sent{background:#fbfcfe}
.act-draft.sent>summary{padding:9px 13px;cursor:pointer;font-size:11.5px;
font-weight:700;color:var(--soft);text-transform:uppercase;letter-spacing:.06em}
.act-draft.sent[open]>summary{border-bottom:1px solid var(--line)}
.sent-note{margin:0 0 10px;padding:8px 12px;background:var(--blue-bg);
border:1px solid var(--blue-line);border-radius:8px;font-size:13px;color:var(--blue)}
.sent-note b{display:inline-block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.07em;margin-right:8px}
.closed{margin:0 0 10px;font-size:13.5px;color:var(--green)}
.closed b{display:inline-block;font-size:10.5px;text-transform:uppercase;
letter-spacing:.06em;margin-right:8px}
.hold{margin:0 0 11px;padding:10px 13px;background:var(--amber-bg);
border:1px solid var(--amber-line);border-radius:8px;font-size:13px;
color:var(--amber-ink)}
.hold b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--amber);margin-bottom:3px}
.hold-until{color:#7a2e0e;font-weight:600}
.dec{background:var(--amber-bg);border:1px solid var(--amber-line);
border-radius:10px;padding:12px 15px;margin-bottom:10px}
.dec-q{font-weight:600;font-size:14.5px;color:var(--amber-ink)}
.dec ul{margin:7px 0 0;padding-left:18px;font-size:13.5px;color:var(--mut)}
.dec-owner{margin:8px 0 0;font-size:12.5px;color:var(--amber);font-weight:600}

/* Header actions. The one that matters in this view is the bright one. */
.refresh{border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.08);
color:#dce6f5;font:650 12px/1 inherit;padding:0 12px;border-radius:7px;
cursor:pointer}
.refresh:hover{background:rgba(255,255,255,.16);color:#fff}
body[data-view="desk"] #refresh,body[data-view="standup"] #prep{
background:#2f6fe4;border-color:#5b93f0;color:#fff}
body[data-view="desk"] #refresh:hover,body[data-view="standup"] #prep:hover{
background:#4881ec}
body[data-view="standup"] #prep{background:#b32a9c;border-color:#cf56b9}
body[data-view="standup"] #prep:hover{background:#c33bab}
.refresh:disabled{opacity:.5;cursor:default}
a.refresh{text-decoration:none}
.refresh-note{font-size:11.5px;color:#93a4bd;max-width:280px}
.refresh-note.bad{color:#f6b0ac}
/* Buttons that only mean something on one view stay on that view. The work
   view is refreshed, not prepped: the words belong to the other tab. */
body[data-view="desk"] #scriptonly,body[data-view="desk"] #prep{display:none}

/* Need to know: the line of the day, the next room, and TG news, in one block
   that shuts. Everything in it stops being news by the middle of the morning. */
.nk{background:var(--card);border:1px solid var(--line);border-left:4px solid
var(--accent);border-radius:13px;box-shadow:var(--shadow);margin-bottom:18px;
overflow:hidden}
.nk.hot{border-left-color:var(--red)}
.nk>summary{cursor:pointer;list-style:none;display:flex;gap:11px;
align-items:center;flex-wrap:wrap;padding:12px 18px 14px}
.nk>summary::-webkit-details-marker{display:none}
.nk>summary::before{display:none}
.nk[open]>summary{border-bottom:1px solid var(--line);background:#fbfcfe}
.nk-k{flex:none;font:750 9.5px/1 inherit;text-transform:uppercase;
letter-spacing:.09em;color:var(--accent);background:var(--accent-bg);
border:1px solid var(--accent-line);padding:4px 7px;border-radius:5px}
.nk.hot .nk-k{color:var(--red);background:var(--red-bg);border-color:var(--red-line)}
/* The one line that is true whether the block is open or shut: what needs him.
   It is worked out from the items, so it cannot drift into commentary. */
.nk-sum{flex-basis:100%;font-size:16px;line-height:1.5;font-weight:450;
letter-spacing:-.01em;color:var(--mut)}
.nk-sum b{font-weight:700;color:var(--ink)}
.nk-n{flex:none;font-size:11.5px;font-weight:650;color:var(--soft)}
/* Something that needs him inside the hour and is not yet an item. Rare. */
.nk-alert{margin:0 0 11px;padding:11px 14px;background:var(--red-bg);
border:1px solid var(--red-line);border-radius:10px;font-size:14.5px;
color:var(--ink)}
.nk-alert b{display:inline-block;font-size:10px;text-transform:uppercase;
letter-spacing:.09em;color:var(--red);margin-right:9px;vertical-align:1px}
/* The same strip in the house colour, for the sentence saying what a meeting
   has to produce. Not an alarm, but the first thing read on that tab. */
.nk-alert.plain{background:var(--accent-bg);border-color:var(--accent-line)}
.nk-alert.plain b{color:var(--accent)}
.nk-in{padding:15px 18px 17px}
.nk-next{display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:11px 13px;
border:1px solid var(--accent-line);background:var(--accent-bg);border-radius:10px;
margin-bottom:10px}
.nk-next.off{border-color:var(--amber-line);background:var(--amber-bg)}
.nk-next.later{border-color:var(--line);background:#fbfcfe}
.nk-tag{font:750 10px/1 inherit;text-transform:uppercase;letter-spacing:.09em;
color:var(--accent-ink)}
.nk-next.off .nk-tag{color:var(--amber)}
.nk-next.later .nk-tag{color:var(--soft)}
.nk-next.later strong{font-size:14px}
.nk-next strong{font-size:15px;letter-spacing:-.01em}
.nk-when{font-size:13px;font-weight:650;color:var(--mut)}
.nk-where{font-size:12.5px;color:var(--soft)}
.nk-focus{flex-basis:100%;font-size:13.5px;color:var(--mut);margin:0}
/* The shape of a day that is not the usual half hour. An onsite has a time he
   has to be somewhere and a time the real discussion starts, and neither is
   the time in the calendar invite. */
.nk-plan{flex-basis:100%;list-style:none;margin:7px 0 0;padding:8px 0 0;
border-top:1px solid var(--accent-line);display:flex;flex-wrap:wrap;
gap:3px 16px;font-size:12.5px;color:var(--soft)}
.nk-plan li{display:flex;gap:6px}
.nk-plan b{font-variant-numeric:tabular-nums;font-weight:700;color:var(--mut)}
.nk-plan li.mine{color:var(--ink);font-weight:600}
.nk-plan li.mine b{color:var(--accent)}
.nk-news h3{margin:14px 0 8px;font-size:12px;font-weight:750;display:flex;
gap:9px;align-items:center}
.nk-news h3:before{content:"";width:3px;height:13px;border-radius:2px;
background:var(--accent-line)}
.nk-news h3 .q{font-weight:500;font-size:11.5px;color:var(--soft)}
.nk-news ul{list-style:none;margin:0;padding:0;border:1px solid var(--line);
border-radius:10px;overflow:hidden}
.nk-news li{padding:10px 13px;border-bottom:1px solid var(--hair);display:flex;
gap:11px;align-items:baseline;flex-wrap:wrap;background:#fff}
.nk-news li:last-child{border-bottom:0}
.n-what{flex:1;min-width:250px;font-size:13.5px}
.n-what b{font-weight:650}
.n-why{display:block;font-size:12.5px;color:var(--mut);margin-top:2px}
.n-more{margin-top:4px}
.n-more>summary{display:inline-flex;gap:7px;align-items:center;cursor:pointer;
font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
color:var(--soft)}
.n-more>summary:hover{color:var(--accent)}
.n-rest{display:block;margin-top:4px;font-size:12.5px;line-height:1.55;
color:var(--mut)}
.n-when{flex:none;font-size:11px;color:var(--soft);font-weight:650}

/* The section header for the cards, with where each ticket stands on it. */
.tickets-bar{margin:26px 0 12px;padding:13px 17px;background:var(--card);
border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow);
scroll-margin-top:96px}
.tb-head{display:flex;gap:10px;align-items:baseline}
.tb-head h2{margin:0;font-size:14px;font-weight:750;letter-spacing:-.01em}
.tb-n{font-size:12px;color:var(--soft);margin-left:auto}
.tb-chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}
.tb-chip{display:flex;gap:7px;align-items:center;text-decoration:none;
font-size:12.5px;font-weight:650;color:var(--ink);border:1px solid var(--line);
background:#fff;border-radius:8px;padding:5px 10px}
.tb-chip:hover{border-color:var(--accent-line);background:var(--accent-bg)}
.tb-chip .dot{width:8px;height:8px;border-radius:50%;background:var(--line);
flex:none}
.tb-chip.mine .dot{background:var(--red)}
.tb-chip.theirs .dot{background:#8fbcf7}
.tb-chip.clear .dot{background:var(--green)}
.tb-chip .s{font-weight:500;font-size:11.5px;color:var(--soft)}

/* Tickets that need nothing, and tickets that are over. */
.tk-fold{background:var(--card);border:1px solid var(--line);border-radius:13px;
box-shadow:var(--shadow);margin-bottom:18px;padding:0 16px}
.tk-fold>summary{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
padding:13px 2px;font-size:13.5px;font-weight:700;cursor:pointer}
.tk-fold>summary .n{font-size:11px;font-weight:700;color:var(--soft);
background:var(--hair);border:1px solid var(--line);border-radius:20px;
padding:0 7px}
.tk-fold>summary .q{font-weight:500;font-size:12px;color:var(--soft)}
.tk-fold[open]{padding-bottom:14px}
.tk-fold[open]>summary{border-bottom:1px solid var(--line);margin-bottom:16px}
.tk-fold .tk{margin-bottom:14px;border:1px solid var(--line);
border-top:4px solid var(--line);border-radius:12px}
.tk-fold .tk:last-child{margin-bottom:0}
"""


def anchor(ref: str) -> str:
    """A stable URL-safe id for a mostly-Japanese tag."""
    ascii_part = re.sub(r"[^0-9A-Za-z]+", "", ref)
    digest = hashlib.md5(ref.encode("utf-8")).hexdigest()[:6]
    return f"t-{ascii_part}{digest}" if ascii_part else f"t-{digest}"


def sub_line(st: dict, item: dict | None = None) -> str:
    """The one line under a title saying what has already happened to it.

    A held item says what it is held for right here. That used to be a separate
    amber box above the list, which meant reading two lists to find out that one
    of the four things in front of him was not his to send yet.
    """
    bits = []
    if st["state"] == "waiting":
        who = st.get("who", "them")
        since = st.get("at", "")
        bits.append(
            f"sent {since}, with {who}" if st.get("sent") else f"with {who} since {since}"
        )
    elif st["state"] == "hold" and item:
        hold = item.get("hold") or {}
        if hold.get("until"):
            bits.append(f"do not send yet, waiting for {hold['until']}")
    elif st["closed"]:
        bits.append(f"{st['label'].lower()} {st.get('at', '')}")
    if st.get("note"):
        bits.append(st["note"])
    return " &middot; ".join(esc(b) for b in bits)


GROUPS = {"todo": "mine", "hold": "blocked", "waiting": "theirs"}


def track_row(
    ref: str,
    item: dict,
    st: dict,
    refs: dict[str, str],
    sess: dict | None,
    queued_behind: str = "",
) -> str:
    mins = item.get("est_minutes")
    sub = sub_line(st, item)
    if queued_behind:
        sub = f"after {esc(queued_behind)}" + (f" &middot; {sub}" if sub else "")
    group = "shut" if st["closed"] else GROUPS.get(st["state"], "")
    due, due_kind = when_tag(item, st, sess)
    # A clock is running on this one: it is his to start now, or its chase date is
    # today. Either reads red, so the time-critical row stands out of the list.
    hot = not st["closed"] and (due_kind == "now" or "today" in (due or "").lower())
    classes = " ".join(c for c in ("tr", group, "tr-hot" if hot else "") if c)
    return f"""
      <li class="{classes}">
        <span class="tr-rank" title="Job {esc(item.get("id", "-"))}. It keeps this
        number until it closes, so &ldquo;done {esc(item.get("id", "-"))}&rdquo; in
        a chat is enough.">{esc(item.get("id", "-"))}</span>
        <span class="tr-tag">{esc(ref)}</span>
        <a class="tr-title" href="#{esc(refs.get(ref, anchor(ref)))}">{esc(item.get("title"))}
          {f'<span class="tr-note">{sub}</span>' if sub else ""}</a>
        <span class="when {due_kind}">{esc(due)}</span>
        {pill(st["label"], st["tone"])}
        <span class="tr-min">{f"{esc(mins)} min" if mins and not st["closed"] else ""}</span>
      </li>"""


def render_track(
    tickets: list[dict], refs: dict[str, str], sess: dict | None = None
) -> str:
    """The one list Rei works from: what is his, what is not, what is finished."""
    rows = tracked(tickets)
    if not rows:
        return ('<div class="panel" style="padding:18px 22px"><p class="empty">'
                "Nothing open across any ticket. Enjoy it.</p></div>")

    counts = {"todo": 0, "hold": 0, "waiting": 0, "closed": 0}
    index = index_items(tickets)
    live, waiting_cold, queued, shut = [], [], [], []
    for ref, item, st in rows:
        # Only work that would otherwise read "with you" diverts into the queue.
        # An item waiting on someone is already described by who holds it.
        behind = blocked_on(item, index) if st["state"] == "todo" else ""
        row = track_row(ref, item, st, refs, sess, behind)
        if st["closed"]:
            counts["closed"] += 1
            shut.append(row)
            continue
        if behind:
            queued.append(row)
            continue
        counts[st["state"]] = counts.get(st["state"], 0) + 1
        # A job with someone else and no chase date is nothing he can move today,
        # so it folds under the live list rather than padding it. Anything he owns,
        # or that carries a chase date or a room to raise it in, stays up top.
        _, due_kind = when_tag(item, st, sess)
        if st["state"] == "waiting" and due_kind == "none":
            waiting_cold.append(row)
        else:
            live.append(row)

    summary = ", ".join(
        f"{n} {word}"
        for n, word in (
            (counts["todo"], "with you"),
            (len(queued), "queued behind"),
            (counts["hold"], "not yet"),
            (counts["waiting"], "with someone else"),
        )
        if n > 0
    )
    # Jobs sitting with someone else, with no date pulling them back, fold under
    # the live list. They are still on the page, one click away, but they are not
    # the thing he opens the board to do.
    waiting_block = (
        f"""
    <details class="track-closed" data-remember="waiting">
      <summary><b>{len(waiting_cold)} with others</b>, no chase date, nothing to
      do on them yet <span class="fold-hint"></span></summary>
      <ul style="list-style:none;margin:0;padding:0">{"".join(waiting_cold)}</ul>
    </details>"""
        if waiting_cold
        else ""
    )
    # Work that cannot start until something else closes is not a choice, so it
    # folds too. It stays on the page because "what comes after this" is worth
    # one click, and it is wrong to make him rediscover the queue each morning.
    queued_block = (
        f"""
    <details class="track-closed" data-remember="queued">
      <summary><b>{len(queued)} queued</b> behind the jobs above, nothing to do
      on them yet <span class="fold-hint"></span></summary>
      <ul style="list-style:none;margin:0;padding:0">{"".join(queued)}</ul>
    </details>"""
        if queued
        else ""
    )
    # Finished work folds away by default. It is a record, not a list.
    closed_block = (
        f"""
    <details class="track-closed" data-remember="done">
      <summary><b>{len(shut)} finished</b> on these tickets, kept for the record
      <span class="fold-hint"></span></summary>
      <ul style="list-style:none;margin:0;padding:0">{"".join(shut)}</ul>
    </details>"""
        if shut
        else ""
    )
    return f"""
  <div class="track" id="todo">
    <div class="track-head"><h2>To do</h2>
    <span class="track-key">Every job keeps the number on its left until it
    closes</span>
    <span>{esc(summary)}</span></div>
    <ul style="list-style:none;margin:0;padding:0">{"".join(live)}</ul>
    {waiting_block}
    {queued_block}
    {closed_block}
  </div>"""


def render_terms(rows: list[dict]) -> str:
    """The words on this ticket, ours and theirs.

    `say` is what TG call it, and it earns its own line because hearing the
    Japanese in the room and reading the English here are the same lookup.
    """
    if not rows:
        return ""
    items = ""
    for r in rows:
        say = (
            f'<span class="term-ja">{furi(r.get("say", ""))}</span>'
            if r.get("say")
            else ""
        )
        items += (
            f'<div class="term"><dt>{esc(r.get("term"))}{say}</dt>'
            f'<dd>{esc(r.get("means"))} '
            f'{link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}'
            "</dd></div>"
        )
    ja = sum(1 for r in rows if r.get("say"))
    count = f"{len(rows)} terms" + (f", {ja} in Japanese" if ja else "")
    return section(
        "Words and shorthand on this ticket",
        f'<dl class="terms">{items}</dl>',
        role="ref",
        count=count,
        fold=True,
        hint="what they say, what it means",
    )


def render_threads(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        out.append(
            f"""
        <li>
          <span class="thr-where">{esc(r.get("where"))}</span>
          <span class="thr-body">
            <span class="thr-label">{esc(r.get("label"))}</span>
            <span class="thr-gist">{esc(r.get("gist"))}</span>
          </span>
          <span class="thr-when"><b>{esc(r.get("last_from"))}</b>{esc(r.get("last_at"))}</span>
          {link_btn(r.get("url", ""), "Open")}
        </li>"""
        )
    return section(
        "Where this is discussed",
        f'<ul class="thr">{"".join(out)}</ul>',
        role="ref",
        count=f"{len(rows)} threads",
        fold=True,
    )


def event_li(r: dict, show_date: bool) -> str:
    src = r.get("source_url", "")
    day = day_words(r.get("on", "")) if show_date else ""
    when = (
        f'<b>{esc(day)}</b><i>{esc(r.get("at", ""))}</i>'
        if day
        else f'<i>{esc(r.get("at", ""))}</i>'
    )
    return f"""
        <li class="ev">
          <span class="ev-at">{when}</span>
          <span class="ev-body">
            <span class="ev-who">{esc(r.get("who", ""))}</span>
            <span class="ev-what">{esc(r.get("what"))}</span>
            {f'<span class="ev-so">{esc(r.get("so_what"))}</span>' if r.get("so_what") else ""}
            <span class="ev-src">{esc(r.get("where", ""))} {link_btn(src, "Source") if src else ""}</span>
          </span>
        </li>"""


def render_events(rows: list[dict], ident: str = "") -> str:
    """The timeline, one fold per day, oldest at the top so it reads forward.

    The day is the handle: press Yesterday and yesterday closes. The most recent
    day is open because that is the one being asked about, and every other day
    is a line saying how much is behind it.

    The whole thing is shut to begin with. It was a quarter of the page, open on
    every card, and it answers a question he asks once a week: how did this get
    here. Its own summary line carries the only part he needs daily, which is
    whether anything moved today, and the fold remembers being opened.
    """
    if not rows:
        return ""
    ordered = sorted(rows, key=lambda x: (x.get("on", ""), x.get("at", "")))
    days: dict[str, list[dict]] = {}
    for r in ordered:
        days.setdefault(r.get("on", ""), []).append(r)
    keys = list(days)

    out = []
    for day in keys:
        moves = days[day]
        n = len(moves)
        out.append(
            f"""
        <details class="ev-fold" {"open" if day == keys[-1] else ""}>
          <summary><span class="ev-d">{opening(esc(day_words(day)))}</span>
          <span class="ev-c">{n} {"move" if n == 1 else "moves"}</span>
          <span class="fold-hint"></span></summary>
          <ol class="evs">{"".join(event_li(r, False) for r in moves)}</ol>
        </details>"""
        )
    latest = len(days[keys[-1]])
    return section(
        "Timeline",
        "".join(out),
        role="log",
        count=f"{latest} {'move' if latest == 1 else 'moves'} {day_words(keys[-1])}",
        hint=f"{len(keys)} {'day' if len(keys) == 1 else 'days'} in all",
        fold=True,
        remember=f"tl-{ident}",
    )


def render_draft(d: dict, st: dict | None = None) -> str:
    """A draft to paste, or, once it has gone, a folded record of what went."""
    if not d:
        return ""
    body = d.get("body_ruby", "")
    is_ja = d.get("language") == "ja"
    rendered = furi(body) if is_ja else esc(body)
    trans = (
        f'<p class="draft-en">{esc(d.get("body_en"))}</p>'
        if is_ja and d.get("body_en")
        else ""
    )
    # The draft is the thing he most often wants changed rather than explained,
    # and the box that changes it is at the foot of the card. This opens that box
    # with the ask already started, so a rewrite is one click from the words.
    inner = f"""
          <div class="draft-head">
            <span>{esc(d.get("target"))}</span>
            {link_btn(d.get("link", ""), "Go there")}
            <button class="copy" data-copy="{esc(plain(body))}">copy</button>
            <button class="ask-here" type="button"
                    data-ask-seed="Rewrite this draft: ">{SPARK}Rewrite or ask</button>
          </div>
          <div class="draft-body {"ja" if is_ja else ""}">{rendered}</div>
          {trans}"""
    gone = st and st["state"] != "todo" and st["state"] != "hold"
    if gone:
        when = f" at {esc(st.get('at'))}" if st.get("at") else ""
        return f"""
        <details class="act-draft sent">
          <summary>What you sent{when}</summary>
          {inner}
        </details>"""
    return f'<div class="act-draft">{inner}</div>'


def cell(value: object) -> str:
    """One cell of a prepared table, plain or carrying a verdict.

    A four-column comparison where every cell is a sentence hides the row that
    is the point of it. A cell written as {"text", "tone"} prints as a verdict
    instead, so the answer is findable before the evidence is read.
    """
    if isinstance(value, dict):
        tone = str(value.get("tone", "warn"))
        tone = tone if tone in ("good", "gap", "warn") else "warn"
        return f'<td class="pw-v"><span class="v-{tone}">{code(value.get("text"))}</span></td>'
    return f"<td>{code(value)}</td>"


def doc_btns(files: list) -> str:
    """The documents an item hands him, opened from the page it sits on.

    A handover sheet that lives only in the repo is a file he has to go and
    find, and one pasted into the page as prose is not the thing he gives
    anybody. The server carries docs/ at /doc/, so the button opens the real
    file, in the form the reader gets it.

    Some of what the work produces cannot live in `docs/` at all: a Miro board is
    the product of an afternoon and belongs beside the file it explains, so an
    entry may name a `url` instead of a `path`.
    """
    out = []
    for f in files or []:
        path = str(f.get("path", ""))
        url = str(f.get("url", ""))
        if not path and not url:
            continue
        label = f.get("label") or Path(path).name or url
        out.append(link_btn(f"/doc/{Path(path).name}" if path else url, label))
    return " ".join(o for o in out if o)


def prepared_block(p: dict, meeting_href: str = "") -> str:
    """Work that was already done for him, above the steps that remain.

    If a step can be followed without judgement then following it was never his
    job, so the page carries the product rather than the instruction. What is
    left underneath is the part only he can do: check it, decide with it, say it.
    """
    if not p:
        return ""
    head = ""
    tbl = p.get("table") or {}
    if tbl.get("rows"):
        cols = "".join(f"<th>{code(c)}</th>" for c in tbl.get("columns", []))
        body = "".join(
            "<tr>" + "".join(cell(c) for c in row) + "</tr>" for row in tbl["rows"]
        )
        head = f'<table class="pw-t"><thead><tr>{cols}</tr></thead><tbody>{body}</tbody></table>'
    finds = "".join(f"<li>{code(f)}</li>" for f in p.get("findings", []))
    notes = "".join(
        f'<div class="pw-note"><b>{esc(n.get("heading"))}</b>'
        f'{code(n.get("body"))}</div>'
        for n in p.get("notes", [])
        if n.get("heading") and n.get("body")
    )
    meeting = p.get("meeting_use") or {}
    meeting_block = ""
    if meeting and meeting_href:
        meeting_block = (
            '<div class="pw-meeting">'
            f'<span>{esc(meeting.get("summary", "Use this in the next session."))}</span>'
            f'<a class="btn" href="#{esc(meeting_href)}" data-goto="standup">'
            f'{esc(meeting.get("label", "Open meeting version"))}</a></div>'
        )
    open_qs = "".join(f"<li>{code(q)}</li>" for q in p.get("unanswered", []))
    docs = doc_btns(p.get("files", []))
    srcs = " ".join(
        link_btn(s.get("url", ""), s.get("label", "Source"))
        for s in p.get("sources", [])
        if s.get("url")
    )
    return f"""
            <div class="act-prep">
              <p class="act-lab done">Prepared for you{f' &middot; {esc(p.get("built_at"))}' if p.get("built_at") else ""}
                <button class="ask-here" type="button"
                        data-ask-seed="About the prepared work: ">{SPARK}Ask about this</button></p>
              {f'<p class="pw-what">{code(p.get("what"))}</p>' if p.get("what") else ""}
              {f'<p class="pw-answer"><b>Bottom line</b>{code(p.get("conclusion"))}</p>' if p.get("conclusion") else ""}
              {head}
              {f'<ul class="pw-f">{finds}</ul>' if finds else ""}
              {notes}
              {f'<div class="pw-open"><b>Still unanswered</b><ul>{open_qs}</ul></div>' if open_qs else ""}
              {f'<div class="pw-src"><span>Files it made</span>{docs}</div>' if docs else ""}
              {meeting_block}
              {f'<div class="pw-src"><span>Built from</span>{srcs}</div>' if srcs else ""}
            </div>"""


def steps_block(r: dict, steps: str, active: bool) -> str:
    """The steps, first thing inside the item, with somewhere to do them.

    This block used to open with Why, which is the one question he never asks of
    his own list: he knows why it is there, he wants to know what to type. So
    the hands-on part comes first, numbered because they are in an order, with
    the place to do it attached to the last step rather than floating below.
    """
    where = esc(r.get("where") or "")
    go = link_btn(r.get("link", ""), "Open where this happens")
    place = (
        f'<div class="act-where">{f"<span>{where}</span>" if where else ""}{go}</div>'
        if where or go
        else ""
    )
    if not steps:
        # A job with no steps is a job he has to work out from its title, which
        # is the failure this block exists to prevent. Say so, rather than
        # leaving a confident-looking gap.
        if not active:
            return place
        return f"""
            <p class="act-nosteps"><b>No steps written yet</b>Ask the chat to
            break job {esc(r.get("id", "-"))} down.</p>{place}"""
    return f"""
            <div class="act-do">
              <p class="act-lab">Do this</p>
              <ol class="steps">{steps}</ol>
              {place}
            </div>"""


def background(r: dict, quote: str) -> str:
    """Why this job exists, folded, under the work it explains.

    Why it matters, what already happened and the message it came out of are
    three paragraphs he reads once, when the job first appears, and never again.
    Open they pushed the next job off the screen; shut they are one line he can
    press when a job has stopped making sense.
    """
    inside = "".join(
        [
            f'<p class="act-why"><b>Why it matters</b>{esc(r.get("why"))}</p>'
            if r.get("why")
            else "",
            f'<p class="act-quote">Already happened: {esc(r.get("progress_note"))}</p>'
            if r.get("progress_note")
            else "",
            f'<p class="act-quote">{esc(quote)} '
            f'{link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</p>'
            if quote
            else "",
        ]
    )
    if not inside:
        return ""
    return f"""
            <details class="act-more">
              <summary>Why this is here<span class="fold-hint"></span></summary>
              {inside}
            </details>"""


def render_items(
    rows: list[dict],
    raise_label: str = "Raise at standup",
    sess: dict | None = None,
    standup_href: str = "",
    ticket_ref: str = "",
    index: dict[str, dict] | None = None,
) -> str:
    if not rows:
        return section(
            "To do on this ticket",
            '<p class="empty">Nothing on this one needs you. It is here because '
            "it is still open in Asana.</p>",
            role="now",
        )
    index = index if index is not None else {str(r.get("id")): r for r in rows}
    out = []
    for r in sorted(rows, key=lambda x: item_order(x, index)):
        steps = "".join(f"<li>{code(b)}</li>" for b in r.get("steps", []))
        mins = r.get("est_minutes")
        committed = r.get("committed_to")
        blocked = r.get("blocked_by")
        quote = r.get("source_quote")
        hold = r.get("hold") or {}
        st = state_of(r)
        done = st["closed"]
        status_block = ""
        if done:
            note = f" {esc(st['note'])}" if st.get("note") else ""
            status_block = (
                f'<p class="closed"><b>{esc(st["label"])}</b>'
                f'{esc(st.get("at", ""))}.{note}</p>'
            )
        elif st["state"] == "waiting":
            note = f" {esc(st['note'])}." if st.get("note") else ""
            waits = r.get("waits_on") or {}
            owed = f" They owe: {esc(waits['what'])}." if waits.get("what") else ""
            chase_line = (
                f" Chase on {esc(waits['chase_on'])}." if waits.get("chase_on") else ""
            )
            sent = f"Sent {esc(st.get('at', ''))}" if st.get("sent") else "Not yours"
            status_block = (
                f'<p class="sent-note"><b>{sent}</b>'
                f'Nothing further from you until {esc(st.get("who", "they"))} '
                f"answers.{owed}{note}{chase_line}</p>"
            )
        elif hold:
            revisit = hold.get("revisit")
            status_block = f"""
            <p class="hold"><b>Do not send this yet</b>{esc(hold.get("why"))}
            <span class="hold-until">Wait for: {esc(hold.get("until"))}.</span>
            {f'<span class="hold-until"> Chase on {esc(revisit)}.</span>' if revisit else ""}</p>"""
        state_pill = pill(st["label"], st["tone"])
        if r.get("at_standup") and not done:
            state_pill += pill(raise_label, "amber")
        due, due_kind = when_tag(r, st, sess)
        when_chip = f'<span class="when {due_kind}">{esc(due)}</span>' if due else ""
        chase = (r.get("waits_on") or {}).get("chase_on", "")
        # Anything not sitting with Rei folds shut, so the page is only as long
        # as the work he still has. Work queued behind another job folds for the
        # same reason: it is not a decision until the one in front of it closes.
        behind = blocked_on(r, index) if st["state"] in {"todo", "hold"} else ""
        active = st["state"] in {"todo", "hold"} and not behind
        tag, attrs = ("div", "") if active else ("details", "")
        head_tag = "div" if active else "summary"
        sub = sub_line(st) or (f"chase {esc(chase)}" if chase else "")
        if behind:
            lead = index.get(behind) or {}
            sub = f"after job {esc(behind)}"
            status_block = (
                f'<p class="act-block"><b>Queued behind job {esc(behind)}</b>'
                f"Nothing to do here until "
                f"&ldquo;{esc(lead.get('title', 'that one'))}&rdquo; closes.</p>"
            ) + status_block
            # A red "With you" on something he cannot start is the whole problem
            # this field exists to fix, and a due date on it is a second lie.
            state_pill = pill(f"After {behind}", "grey") + (
                pill(raise_label, "amber") if r.get("at_standup") else ""
            )
            when_chip = ""
        out.append(
            f"""
        <{tag} class="act {st["state"]} {"held" if hold and not done else ""} {"commit" if committed else ""}"{attrs}>
          <{head_tag} class="act-head">
            <span class="act-rank">{esc(r.get("id", "-"))}</span>
            <span class="act-title">{esc(r.get("title"))}
              {f'<span class="act-sub">{sub}</span>' if sub and not active else ""}</span>
            {when_chip}
            {state_pill}
            <span class="act-min">{f"{esc(mins)} min" if mins and active else ""}</span>
          </{head_tag}>
          <div class="act-body">
            {status_block}
            {prepared_block(r.get("prepared") or {}, standup_href)}
            {steps_block(r, steps, active)}
            {render_draft(r.get("draft") or {}, st)}
            {f'<p class="act-done"><b>Finished when</b>{code(r.get("done_when"))}</p>' if r.get("done_when") and not done else ""}
            {f'<p class="act-commit">You committed this to {esc(committed)}</p>' if committed else ""}
            {f'<p class="act-block">Blocked by: {esc(blocked)}</p>' if blocked else ""}
            {background(r, quote)}
            {ask_block(
                f'item:{r.get("id")}',
                f'job {r.get("id")}, {ticket_ref}' if ticket_ref else f'job {r.get("id")}',
                ASKED.get(f'item:{r.get("id")}', []),
                f'Read prompt-ask.md, then answer this about job {r.get("id")}'
                f' on {ticket_ref} ("{r.get("title", "")}"):',
                bool(r.get("draft")),
            )}
          </div>
        </{tag}>"""
        )
    live = sum(1 for r in rows if not state_of(r)["closed"])
    done = len(rows) - live
    tally = f"{live} open" if live else "all done"
    if done:
        tally += f", {done} closed"
    return section(
        "To do on this ticket",
        "".join(out),
        role="now",
        count=tally,
        hint="each keeps its number until it closes",
    )


def render_decisions(rows: list[dict]) -> str:
    if not rows:
        return ""
    out = []
    for r in rows:
        opts = "".join(f"<li>{esc(o)}</li>" for o in r.get("options", []))
        out.append(
            f"""
        <div class="dec">
          <div class="dec-q">{esc(r.get("question"))}</div>
          {f"<ul>{opts}</ul>" if opts else ""}
          <p class="dec-owner">Decided by: {esc(r.get("owner"))}
          {link_btn(r.get("source_url", ""), "Source") if r.get("source_url") else ""}</p>
        </div>"""
        )
    return section(
        "Still undecided",
        "".join(out),
        role="warn",
        count=f"{len(rows)} open",
        hint="nobody owns this yet",
    )


def asana_chips(t: dict) -> str:
    """What Asana itself says about this ticket, not what the agent thinks.

    Every value carries its field name, and the field names are Asana's own, so
    what is on the screen matches what he sees when he opens the ticket.
    """
    a = t.get("asana") or {}
    bits = []
    labelled = (
        ("status", "Status"),
        ("category", "Category"),
        ("priority", "Priority"),
        ("severity", "Severity"),
        ("assignee", "Assignee"),
        ("section", "Section"),
    )
    for key, label in labelled:
        if not a.get(key):
            continue
        odd = key == "assignee" and "Rei" not in a[key]
        bits.append(
            f'<span class="tk-chip{" warn" if odd else ""}">'
            f"<b>{label}</b>{esc(a[key])}</span>"
        )
    return "".join(bits)


STAGES = (
    ("refining", "Refining"),
    ("queued", "Queued"),
    ("building", "Building"),
    ("review", "In review"),
    ("released", "Released"),
    ("verified", "Verified"),
)


def build_rail(stage: str) -> str:
    """Six stops from refinement to TG's own verification, current one lit.

    A TG ticket does not close when the code lands, it closes when TG has
    checked the bills that came out after it, so the rail runs one stop past
    the release rather than stopping at Done.
    """
    keys = [k for k, _ in STAGES]
    at = keys.index(stage) if stage in keys else -1
    out = []
    for n, (key, label) in enumerate(STAGES):
        cls = "done" if at > -1 and n < at else "at" if n == at else ""
        out.append(f'<li class="{cls}">{esc(label)}</li>')
    return f'<ol class="rail">{"".join(out)}</ol>'


def build_strip(internal: dict) -> str:
    """The Kraken-side build, inside the ticket's status rather than beside it.

    TG cannot see any of this and must never be quoted any of it, but half of
    "where is this ticket" is which stop the build is at and what it is waiting
    on, so it belongs under the short answer rather than in a chip row of its
    own. `none_yet` is the same answer for a ticket with no build raised: an
    empty queue is a fact about the ticket too.
    """
    b = internal.get("build") or {}
    if not b:
        if internal.get("none_yet"):
            return (
                '<p class="bld none"><span class="bld-k">Kraken build</span>'
                f'{esc(internal["none_yet"])}</p>'
            )
        return ""

    # (text, worth flagging). Amber only where the fact is the reason the build
    # is not moving, so the colour keeps meaning something.
    facts = [
        (f"Engineer <b>{esc(b['engineer'])}</b>", False)
        if b.get("engineer")
        else ("Engineer <b>nobody yet</b>", True)
    ]
    if b.get("size"):
        facts.append((f"Size <b>{esc(b['size'])}</b>", False))
    if b.get("refined_by"):
        facts.append((f"Refined by <b>{esc(b['refined_by'])}</b>", False))
    if b.get("feature_flag") == "Yes":
        facts.append(("Ships <b>behind a feature flag</b>", True))
    if b.get("moved_on"):
        facts.append((f"Last moved <b>{esc(day_words(b['moved_on']))}</b>", False))

    tg = (
        f'<p class="bld-tg"><b>What TG can be told</b>{esc(b.get("safe_to_say"))}</p>'
        if b.get("safe_to_say")
        else ""
    )
    return f"""
      <div class="bld">
        <div class="bld-head">
          <span class="bld-k">Kraken build</span>
          <span class="bld-kt">{esc(b.get("kt", ""))}</span>
          <span class="bld-state">{esc(b.get("asana_status", ""))}</span>
          <span class="keep">never quote this one to TG</span>
          {link_btn(internal.get("url", ""), "Open build ticket")}
        </div>
        <div class="bld-body">
          {build_rail(b.get("stage", ""))}
          <p class="bld-now">{esc(b.get("waiting_on"))}</p>
          <p class="bld-facts">{"".join(
              f'<span class="{"odd" if odd else ""}">{f}</span>' for f, odd in facts
          )}</p>
          {tg}
        </div>
      </div>"""


def render_closes(rows: list[dict], ident: str = "") -> str:
    """Everything that still has to fall before the ticket can be closed.

    The item list says what Rei does next. This says what closing looks like,
    including the gates that are nobody's item: an engineer being assigned, a
    release landing, TG checking the bills that came out after it. Without it a
    ticket with no open items reads as finished when it is only quiet.

    Folded, with the next gate and whose it is on the summary line, because that
    one line is the daily question and the other five gates are the monthly one.
    """
    if not rows:
        return ""
    out = []
    for r in rows:
        state = r.get("state", "next")
        note = f'<span class="g-n">{esc(r.get("note"))}</span>' if r.get("note") else ""
        out.append(
            f"""
        <li class="gate {esc(state)}">
          <span class="g-m"></span>
          <span class="g-w">{esc(r.get("what"))}{note}</span>
          <span class="g-who">{esc(r.get("who", ""))}</span>
        </li>"""
        )
    done = sum(1 for r in rows if r.get("state") == "done")
    nxt = next((r for r in rows if r.get("state") != "done"), None)
    waiting = ""
    if nxt:
        who = nxt.get("who", "")
        whose = (
            "yours"
            if who.strip().lower() in {"you", "rei", "rei samuelsson"}
            else f"with {who}"
            if who
            else ""
        )
        waiting = f"Next: {nxt.get('what', '')}" + (f", {whose}" if whose else "")
        if len(waiting) > 78:
            waiting = waiting[:77].rsplit(" ", 1)[0] + "\u2026"
    return section(
        "What is left before this closes",
        f'<ul class="gates">{"".join(out)}</ul>',
        role="key",
        count=f"{done} of {len(rows)} done",
        hint=waiting,
        fold=True,
        remember=f"gates-{ident}",
    )


def internal_btn(internal: dict) -> str:
    """The Kraken-side ticket, named on hover rather than in the row.

    The name is long, and it is the one string on this page that must never be
    copied into anything addressed to TG, so it does not get to sprawl. A build
    with a strip under Where it stands already carries its own link, so this
    only fires for a linked ticket that has no build detail on it.
    """
    if not internal.get("url") or internal.get("build"):
        return ""
    return (
        f'<a class="btn" href="{esc(internal["url"])}" target="_blank" rel="noopener" '
        f'title="{esc(internal.get("name", ""))}">Internal ticket</a>'
    )


def render_ticket(
    t: dict,
    ident: str,
    raise_label: str = "Raise at standup",
    sess: dict | None = None,
    index: dict[str, dict] | None = None,
) -> str:
    internal = t.get("internal_ticket") or {}
    # The warning belongs beside the link it is about. With a build strip that
    # link has moved into Where it stands, and the warning goes with it.
    keep_in = (
        '<span class="keep">never quote this one to TG</span>'
        if internal.get("name") and not internal.get("build")
        else ""
    )

    states = [state_of(i) for i in t.get("items", [])]
    mine = sum(1 for s in states if s["state"] == "todo")
    open_n = sum(1 for s in states if not s["closed"])
    if mine:
        posture, tone = pill(f"{mine} with you", "red"), "mine"
    elif open_n:
        posture, tone = pill("Nothing on you", "blue"), "theirs"
    else:
        posture, tone = pill("Clear", "green"), "clear"

    # When there is a script for this ticket, the desk card says so and jumps
    # straight to it, because "what do I say about this" is the next question.
    say_link = (
        f'<a class="btn" href="#{esc(render_standup.anchor(ident))}" '
        f'data-goto="standup">What I say about this</a>'
        if (t.get("prep") or {}).get("script")
        else ""
    )

    return f"""
    <article class="tk {tone}" id="{esc(ident)}">
      <header class="tk-head">
        <div class="tk-id">
          <span class="tag">{esc(t.get("ref"))}</span>
          <span class="tk-kind">{"Work in hand" if t.get("no_ticket_yet") else "Asana ticket"}</span>
          {posture}
        </div>
        <h2>{esc(t.get("title_en"))}</h2>
        <p class="tk-ja">{esc(t.get("title_ja"))}</p>
        <p class="tk-meta">
          {asana_chips(t)}
        </p>
        {f'<p class="tk-noticket"><b>No Asana ticket yet</b>{code(t.get("no_ticket_yet"))}</p>'
         if t.get("no_ticket_yet") else ""}
        <div class="tk-links">
          <span class="lab">Go to</span>
          {link_btn(t.get("asana_url", ""), "Open in Asana")}
          {say_link}
          {internal_btn(internal)}
          {keep_in}
        </div>
      </header>

      {section("Where it stands",
               f'<p class="status">{esc(t.get("where_it_stands"))}</p>'
               + build_strip(internal),
               role="key",
               hint="both sides" if internal.get("build") else "the short answer")}

      {render_items(
          t.get("items", []),
          raise_label,
          sess,
          render_standup.anchor(ident),
          t.get("ref", ""),
          index,
      )}
      {render_decisions(t.get("open_decisions", []))}
      {render_closes(t.get("closes_when", []), ident)}
      {render_events(t.get("events", []), ident)}
      {render_terms(t.get("terms", []))}
      {render_threads(t.get("threads", []))}
      {section("Ask or change on this ticket",
               ask_block(
                   f'ticket:{t.get("ref")}',
                   t.get("ref", "this ticket"),
                   ASKED.get(f'ticket:{t.get("ref")}', []),
                   "Read prompt-ask.md, then answer this about the "
                   f'{t.get("ref", "")} ticket:',
               ),
               role="ask",
               hint="when it is not about one job")}
    </article>"""


def shell(
    title: str,
    body: str,
    view: str = "desk",
    meeting_iso: str = "",
    meeting_label: str = "",
) -> str:
    # The manifest and icon are what let Chrome install this as its own app, with
    # its own Dock tile. They 404 harmlessly when the page is opened from disk.
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">
<link rel="apple-touch-icon" href="/icon-512.png">
<meta name="theme-color" content="#0d1524">
<title>{esc(title)}</title>
<style>{CSS}{EXTRA_CSS}{render_standup.EXTRA_CSS}</style></head>
<body data-view="{esc(view)}" data-meeting="{esc(meeting_iso)}"
      data-meeting-label="{esc(meeting_label)}">
{body}
<script>{JS}</script></body></html>"""


# The buttons only appear when serve.py is behind the page, because a file://
# page has nothing to send the click to. serve.py swaps the key in as it serves.
def controls(prep_label: str) -> str:
    return """
  <button id="refresh" class="refresh" hidden data-run="/api/refresh"
          data-busy="Refreshing">Refresh</button>
  <button id="prep" class="refresh" hidden data-run="/api/prep"
          data-busy="Writing">%s</button>
  <button id="login" class="refresh" hidden>Log in</button>
  <a id="login-link" class="refresh" hidden target="_blank" rel="noopener">Open sign-in page</a>
  <span id="refresh-note" class="refresh-note"></span>
<script>
(function () {
  var key = "__DESK_KEY__";
  if (location.protocol !== "http:" || key.indexOf("DESK_KEY") > -1) return;
  var runners = [].slice.call(document.querySelectorAll("[data-run]"));
  var login = document.getElementById("login");
  var link = document.getElementById("login-link");
  var note = document.getElementById("refresh-note");
  runners.forEach(function (b) { b.hidden = false; });

  function say(text, tone) {
    note.textContent = text || "";
    note.className = "refresh-note" + (tone ? " " + tone : "");
  }

  function ready() {
    runners.forEach(function (b) {
      b.disabled = false;
      b.textContent = b.dataset.label || b.textContent;
    });
  }

  // The card that is waiting on an answer. A question takes half a minute to
  // two, and the only thing worse than waiting is not knowing whether anything
  // is happening, so the panel keeps a live count and the last line the agent
  // printed rather than a button frozen on "Sending".
  var waiting = null;

  function thinking(s) {
    if (!waiting) return;
    var secs = s.seconds || 0;
    var mins = secs >= 60 ? Math.floor(secs %% 3600 / 60) + "m " + (secs %% 60) + "s" : secs + "s";
    waiting.querySelector(".ask-wait-t").textContent = "Thinking, " + mins;
    var tail = waiting.querySelector(".ask-wait-tail");
    // What it says it is doing, when it says anything. The CLI usually holds its
    // text to the end, so most of the wait is the count and the dots, and the
    // second line is there to say a long wait is still a normal one.
    var word = s.last || (secs > 150
      ? "Still going. Anything that reads a thread takes a few minutes."
      : secs > 40 ? "Reading the ticket, the threads and what you asked before." : "");
    tail.textContent = word;
    tail.hidden = !word;
  }

  function stopWaiting(message, tone) {
    if (!waiting) return;
    var panel = waiting.parentNode;
    waiting.remove();
    waiting = null;
    var b = panel.querySelector(".ask-send");
    if (b) { b.disabled = false; b.textContent = "Send"; }
    var hint = panel.querySelector(".ask-hint");
    if (hint && message) hint.textContent = message;
    if (tone) say(message, tone);
  }

  function poll() {
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {
      if (s.state === "running") {
        // A sweep reads every ticket and every thread behind it, so minutes are
        // normal. Saying how long it has been and what it last said is the
        // difference between a slow job and a job that looks stuck.
        var note = s.message + "\\u2026";
        if (!waiting && s.seconds) {
          var m = s.seconds >= 60
            ? Math.floor(s.seconds / 60) + "m " + (s.seconds %% 60) + "s"
            : s.seconds + "s";
          note = s.message + " \\u00b7 " + m;
          if (s.last) note += " \\u00b7 " + s.last.slice(0, 90);
        }
        say(note);
        thinking(s);
        setTimeout(poll, waiting ? 900 : 2000);
        return;
      }
      if (s.state === "done") {
        if (waiting) waiting.querySelector(".ask-wait-t").textContent = "Answered, opening it";
        say("Done, reloading");
        location.reload();
        return;
      }
      // Signed out is not a failure, it is one click. Offer the click, and the
      // link the CLI printed once it has one. Keep polling so the moment the
      // browser approval lands the buttons come back on their own.
      if (s.state === "needs_login") {
        ready();
        stopWaiting(s.message);
        login.hidden = false;
        if (s.url) { link.href = s.url; link.hidden = false; }
        say(s.message, "bad");
        setTimeout(poll, 3000);
        return;
      }
      if (s.state === "failed") { ready(); stopWaiting(s.message); say(s.message, "bad"); return; }
      login.hidden = true;
      link.hidden = true;
      ready();
      say(s.message);
    });
  }

  runners.forEach(function (b) {
    b.dataset.label = b.textContent;
    b.addEventListener("click", function () {
      runners.forEach(function (o) { o.disabled = true; });
      b.textContent = b.dataset.busy;
      say("Starting\\u2026");
      fetch(b.dataset.run + "?k=" + encodeURIComponent(key), { method: "POST" })
        .then(poll)
        .catch(function () { ready(); say("could not reach the desk server", "bad"); });
    });
  });

  login.addEventListener("click", function () {
    login.disabled = true;
    say("Starting the sign-in\\u2026");
    fetch("/api/login?k=" + encodeURIComponent(key), { method: "POST" })
      .then(function () { setTimeout(function () { login.disabled = false; poll(); }, 1500); })
      .catch(function () { login.disabled = false; say("could not reach the desk server", "bad"); });
  });

  // Asking from a card. The question travels with the job it was asked about,
  // so the server can hand the agent the ticket, the item and its draft, and
  // the answer comes back onto the same card.
  //
  // Delegated, and the buttons are shown once the cards exist. This script runs
  // from the header while the page is still parsing, so the jobs below it are
  // not in the document yet: reaching for them here found nothing, which left
  // every card with the clipboard fallback and no way to actually send.
  function showSends() {
    [].forEach.call(document.querySelectorAll("[data-ask-send]"), function (b) {
      b.hidden = false;
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showSends);
  } else {
    showSends();
  }

  // Forgetting a question. The record is his, so it is his to throw away, and
  // the bubble goes as soon as the server says it is gone rather than on the
  // next rebuild.
  document.addEventListener("click", function (e) {
    var x = e.target.closest && e.target.closest("[data-forget]");
    if (!x) return;
    var bubble = x.closest(".qa");
    x.disabled = true;
    fetch("/api/forget?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: x.dataset.forget })
    }).then(function (r) {
      if (!r.ok) throw new Error("the desk server kept it");
      var list = bubble.parentNode;
      var fold = list.closest(".qa-earlier");
      bubble.remove();
      if (!list.querySelector(".qa")) list.remove();
      if (fold && !fold.querySelector(".qa")) fold.remove();
    }).catch(function (err) {
      x.disabled = false;
      say(err.message, "bad");
    });
  });

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".ask-send");
    if (!b || b.hidden) return;
    var box = b.closest(".ask");
    // The send inside an answer is a follow-up to that answer; the one at the
    // foot of the card is a new question about the job.
    var panel = b.closest(".fu") || box.querySelector(".ask-box");
    var field = panel.querySelector("textarea");
    var hint = panel.querySelector(".ask-hint") || box.querySelector(".ask-hint");
    var question = (field.value || "").trim();
    if (!question) { field.focus(); return; }
    b.disabled = true;
    b.textContent = "Sending\\u2026";
    hint.textContent = "";
    if (waiting) waiting.remove();
    waiting = document.createElement("div");
    waiting.className = "ask-wait";
    waiting.innerHTML =
      '<span class="ask-dots" aria-hidden="true"><i></i><i></i><i></i></span>' +
      '<span class="ask-wait-t">Thinking, 0s</span>' +
      '<span class="ask-wait-tail" hidden></span>';
    panel.appendChild(waiting);
    fetch("/api/ask?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ref: box.dataset.ask,
        question: question,
        parent: panel.dataset.parent || ""
      })
    }).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          throw new Error(j.error || j.message || "the desk server said no");
        });
      }
      say("Working on your question\\u2026");
      poll();
    }).catch(function (e) {
      stopWaiting("");
      b.disabled = false;
      b.textContent = "Send";
      hint.textContent = e.message;
    });
  });

  poll();
})();
</script>""" % prep_label


def checked_line(stamp: str) -> str:
    """How long ago the board was last brought up to date, in plain words.

    Short, because it shares the header with the tabs and the buttons, and a
    wrapped header pushes the page around every time it changes.
    """
    if not stamp:
        return "never checked"
    try:
        then = datetime.fromisoformat(stamp)
    except ValueError:
        return esc(stamp)
    mins = int((datetime.now().astimezone() - then).total_seconds() // 60)
    if mins < 2:
        return "checked just now"
    if mins < 60:
        return f"checked {mins}m ago"
    if mins < 24 * 60:
        return f"checked {mins // 60}h ago"
    return f"checked {then:%-d %b}"


def is_stale(stamp: str) -> bool:
    """Four hours is long enough for a reply to have landed unseen."""
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return True
    return (datetime.now().astimezone() - then).total_seconds() > 4 * 3600


def view_tabs(mine: int, has_script: bool, sess: dict) -> str:
    """Two tabs, both named for the client, because a second client is coming.

    "TG my work" and "TG what I say" say whose work and which half. The client
    prefix means a Kyuden pair can sit beside them without either name having to
    change or a tab having to be read twice.

    All on one line: the header sits above everything he reads all day, so it
    stays as short as it can while still being the most obvious thing up there.
    """
    badge = (
        f'<span class="badge">{mine}</span>'
        if mine
        else '<span class="badge quiet">0</span>'
    )
    when = short_when(sess.get("date", ""), sess.get("at", ""))
    # The kind, not the board's own label for the room: "Onsite today 09:45"
    # rather than "Billing onsite today 09:45". Everything on this page is
    # billing, and the words it saves are what keep the bar one line tall.
    room = f'{sess.get("tab") or sess.get("name", "Standup")} {when}'.strip()
    alert = "" if has_script else '<span class="badge">!</span>'
    return f"""
  <div class="views" role="tablist" aria-label="Views">
    <button data-view="desk" role="tab" aria-selected="true">
      <span class="k">1</span><span class="lbl">TG my work</span>{badge}
    </button>
    <button data-view="standup" role="tab" aria-selected="false">
      <span class="k">2</span><span class="lbl">TG what I say</span>
      <span class="sub">{esc(room)}</span>{alert}
    </button>
  </div>"""


def opening_view(board: dict, has_script: bool) -> str:
    """What to show on load.

    On the morning of a session, with a script already written, the script is
    what he opens the laptop for. Every other moment of the day, the work is.
    """
    if not has_script:
        return "desk"
    sess = script_session(board)
    if sess.get("date") != date.today().isoformat():
        return "desk"
    at = sess.get("at") or "10:30"
    try:
        hour, minute = (int(x) for x in at.split(":")[:2])
    except ValueError:
        hour, minute = 10, 30
    now = datetime.now()
    return "standup" if (now.hour, now.minute) < (hour, minute) else "desk"


def timetable(rows: list[dict]) -> str:
    """The running order of a day, when the session is a day rather than a slot.

    A standup is a time. An onsite is a building at 09:45, two standups at 11:00
    and the discussion he came for at 13:00, and getting that wrong is the one
    mistake the page can save him from.
    """
    if not rows:
        return ""
    out = []
    for r in rows:
        if not r.get("what"):
            continue
        mine = ' class="mine"' if r.get("mine") else ""
        out.append(f'<li{mine}><b>{esc(r.get("at"))}</b>{esc(r["what"])}</li>')
    return f'<ul class="nk-plan">{"".join(out)}</ul>' if out else ""


def news_rows(rows: list[dict]) -> str:
    """What is moving around TG that is not one of his tickets.

    A ticket page answers "what do I do". It does not answer "what has changed
    around me", and that is the thing he walks into a room not knowing.
    """
    if not rows:
        return ""
    out = []
    for r in rows:
        when = r.get("on", "")
        # The first sentence and the route are the row. The four sentences of
        # detail behind them are why this block was a wall of grey: they are the
        # answer to "and what exactly", which he asks about one row in five.
        said = (r.get("what") or "").strip()
        lead, rest = said, ""
        cut = re.split(r"(?<=[.。])\s+", said, maxsplit=1)
        if len(cut) == 2 and len(cut[0]) < len(said) - 20:
            lead, rest = cut[0], cut[1]
        out.append(
            f"""
      <li>
        <span class="n-what"><b>{esc(r.get("topic"))}</b>
          {f'&mdash; {esc(lead)}' if lead else ""}
          {f'<span class="n-why">{esc(r.get("why"))}</span>' if r.get("why") else ""}
          {f'''<details class="n-more"><summary>The rest of it<span class="fold-hint"></span></summary>
          <span class="n-rest">{esc(rest)}</span></details>''' if rest else ""}
        </span>
        <span class="n-when">{esc(short_when(when) if when else "")}</span>
        {link_btn(r.get("source_url", ""), "Source")}
      </li>"""
        )
    return f"""
    <div class="nk-news">
      <h3>TG news <span class="q">not your tickets, but they move them</span></h3>
      <ul>{"".join(out)}</ul>
    </div>"""


def first_line(tickets: list[dict], soon: dict) -> str:
    """The first sentence on the page, worked out from the board itself.

    This used to be a sentence an agent wrote about yesterday, and by the time
    he read it the words were a recap of a conversation he had already had. The
    only thing worth the top line is what needs him, so it is counted rather
    than composed: the page cannot editorialise, and it cannot go stale.
    """
    index = index_items(tickets)
    mine, held, waiting = [], [], []
    for t in tickets:
        for item in t.get("items", []):
            st = state_of(item)
            row = (t, item, st)
            if st["state"] == "todo":
                # Something queued behind another job is not one of the things
                # that needs him, and counting it here is how the top line ends
                # up naming work he cannot start.
                if not blocked_on(item, index):
                    mine.append(row)
            elif st["state"] == "hold":
                held.append(row)
            elif st["state"] == "waiting":
                waiting.append(row)

    today = date.today().isoformat()
    before = ""
    if soon.get("date"):
        when = when_words(soon.get("date", ""))
        if when in ("today", "tomorrow"):
            room = esc(soon.get("name", "standup")).lower()
            before = (
                f" Material for the {room} {when}."
                if when == "tomorrow"
                else f" The {room} is {when}."
            )

    if mine:
        # The one to start on: something promised to a person outranks a
        # deadline, and a deadline outranks the order the numbers happen to be
        # in. Everything else is on its card.
        def urgency(row: tuple) -> tuple:
            _, item, _ = row
            return (
                0 if item.get("committed_to") else 1,
                0 if item.get("at_standup") else 1,
                item.get("id", 99),
            )

        ticket, item, _ = sorted(mine, key=urgency)[0]
        mins = sum(i.get("est_minutes") or 0 for _, i, _ in mine)
        n = len(mine)
        clock = f", about {mins} min" if mins else ""
        lead = (
            f"<b>One thing needs you{clock}.</b>"
            if n == 1
            else f"<b>{n} things need you{clock} in total.</b>"
        )
        owed = (
            f' You promised it to {esc(item["committed_to"])}.'
            if item.get("committed_to")
            else before
        )
        which = "Item" if n == 1 else "Start with item"
        return (
            f'{lead} {which} <b>{esc(item.get("id"))}</b> on '
            f'{esc(ticket.get("ref"))}: {esc(item.get("title"))}.{owed}'
        )

    due = [
        row
        for row in held + waiting
        if ((row[1].get("hold") or {}).get("revisit") or "") <= today
        and ((row[1].get("hold") or {}).get("revisit") or "")
        or ((row[1].get("waits_on") or {}).get("chase_on") or "") <= today
        and ((row[1].get("waits_on") or {}).get("chase_on") or "")
    ]
    if due:
        ticket, item, st = due[0]
        return (
            f"<b>Nothing is yours to write, but {len(due)} "
            f'{"chase is" if len(due) == 1 else "chases are"} due.</b> '
            f'<b>{esc(item.get("id"))}</b>, {esc(item.get("title"))}, has been '
            f'with {esc(st.get("who") or "them")} since {esc(st.get("at", ""))}.'
        )
    if held or waiting:
        n = len(held) + len(waiting)
        return (
            f"<b>Nothing needs you right now.</b> {n} "
            f'{"thing is" if n == 1 else "things are"} sitting with other people, '
            "none of them due a chase today."
        )
    return "<b>Nothing open across any ticket.</b> Enjoy it."


def need_to_know(
    board: dict, has_script: bool, news: list[dict], tickets: list[dict], soon: dict
) -> str:
    """Everything he has to know before he starts, in one block he can shut.

    The first line is always what needs him, and it stays visible folded, so the
    top of the page answers the only question he opens it with. Underneath, the
    things he has to know but cannot act on: anything flagged as needing him
    inside the hour, the next room, and what moved around him.
    """
    rows = sessions(board)
    live = next((s for s in rows if not s.get("skipped")), {})
    skipped = [s for s in rows if s.get("skipped")]
    alert = board.get("alert") or {}
    if isinstance(alert, str):
        alert = {"what": alert}
    alert_block = ""
    if alert.get("what"):
        alert_block = f"""
      <p class="nk-alert"><b>Needs you now</b>{esc(alert["what"])}
      {link_btn(alert.get("source_url", ""), "Source")}</p>"""

    next_block = ""
    if live:
        covered = has_script and script_meta(board).get("for_date") == live.get("date")
        # A sweep moves the work and deliberately leaves the words alone, so the
        # script can be right about the room and behind on the facts. The
        # speaking view says so at the top; this is the same fact on the work
        # view, where he is standing when he decides whether to rewrite it.
        behind = covered and script_meta(board).get("built_at", "") < board.get(
            "checked_at", ""
        )
        if behind:
            note = (
                '<span class="tk-chip warn">Prep is older than the board</span>'
                '<a class="btn" href="#top" data-goto="standup">Read it anyway</a>'
            )
        elif covered:
            note = '<a class="btn" href="#top" data-goto="standup">Read the prep</a>'
        elif has_script:
            for_day = when_words(script_meta(board).get("for_date", ""))
            note = f'<span class="tk-chip warn">Prep is for {esc(for_day)}, not this</span>'
        else:
            note = '<span class="tk-chip warn">No prep written yet</span>'
        next_block = f"""
      <div class="nk-next">
        <span class="nk-tag">Next room</span>
        <strong>{esc(live.get("title") or live.get("name"))}</strong>
        <span class="nk-when">{esc(when_words(live.get("date", ""), live.get("at", "")))}</span>
        {f'<span class="nk-where">{esc(live.get("place"))}</span>' if live.get("place") else ""}
        {note}
        {f'<span class="nk-focus">{esc(live.get("focus"))}</span>' if live.get("focus") else ""}
        {timetable(live.get("timetable", []))}
      </div>"""
    # Rooms after the next one. A session two days out changes what has to be
    # ready today, so the board holding it is not enough: it has to be on the page.
    for s in rows:
        if s.get("skipped") or s is live:
            continue
        bring = s.get("bring") or []
        next_block += f"""
      <div class="nk-next later">
        <span class="nk-tag">After that</span>
        <strong>{esc(s.get("title") or s.get("name"))}</strong>
        <span class="nk-when">{esc(when_words(s.get("date", ""), s.get("at", "")))}</span>
        {f'<span class="nk-where">{esc(s.get("place"))}</span>' if s.get("place") else ""}
        {f'<span class="nk-focus">{esc(s.get("focus"))}</span>' if s.get("focus") else ""}
        {f'<span class="nk-focus">Bring: {esc("; ".join(bring))}</span>' if bring else ""}
      </div>"""
    for s in skipped:
        next_block += f"""
      <div class="nk-next off">
        <span class="nk-tag">Not running</span>
        <strong>No {esc(s.get("name", "standup")).lower()}
        {esc(when_words(s.get("date", "")))}</strong>
        <span class="nk-focus">{esc(s.get("reason"))} Anything that was waiting
        for that meeting has to move into Asana.</span>
      </div>"""

    inside = []
    if alert_block:
        inside.append("something urgent")
    if next_block:
        inside.append("the next room")
    if news:
        inside.append(f"{len(news)} TG updates" if len(news) != 1 else "1 TG update")
    return f"""
  <details class="nk{" hot" if alert_block else ""}" id="need"
           data-remember="need" open>
    <summary>
      <span class="nk-k">Need to know</span>
      <span class="nk-n">{esc(", ".join(inside))}</span>
      <span class="fold-hint"></span>
      <span class="nk-sum">{first_line(tickets, soon)}</span>
    </summary>
    <div class="nk-in">
      {alert_block}
      {next_block}
      {news_rows(news)}
    </div>
  </details>"""


def jump_bar(tickets: list[dict], refs: dict[str, str], has_news: bool) -> str:
    """The sections and every ticket, one click away, wherever you are."""
    chips = []
    if has_news:
        chips.append('<a href="#need">Need to know</a>')
    chips.append('<a href="#todo">To do</a>')
    chips.append('<a href="#tickets">Tickets</a>')
    for t in tickets:
        ref = t.get("ref", "")
        mine = sum(1 for i in t.get("items", []) if state_of(i)["state"] == "todo")
        count = f'<span class="c">{mine}</span>' if mine else ""
        chips.append(f'<a class="tkt" href="#{esc(refs[ref])}">{esc(ref)}{count}</a>')
    return f"""
  <nav class="jump">
    <span class="lab">Jump to</span>
    {"".join(chips)}
    <button class="find" data-find type="button">Find <kbd>/</kbd></button>
  </nav>"""


def finder(tickets: list[dict], refs: dict[str, str]) -> str:
    """The index behind the finder, and the box it draws into.

    Tickets and items both go in, because "3" and "託送" and "Kevin" are all
    things he would type to get to the same three cards.
    """
    rows = []
    for t in tickets:
        ref = t.get("ref", "")
        title = t.get("title_en", "")
        rows.append(
            {
                "id": refs[ref],
                "tag": ref,
                "label": title,
                "sub": "ticket",
                "view": "desk",
                "hay": f'{ref} {title} {t.get("title_ja", "")}'.lower(),
            }
        )
        if (t.get("prep") or {}).get("script"):
            rows.append(
                {
                    "id": render_standup.anchor(refs[ref]),
                    "tag": ref,
                    "label": f"What I say about {title}",
                    "sub": "script",
                    "view": "standup",
                    "hay": f"say script {ref} {title}".lower(),
                }
            )
        for item in t.get("items", []):
            st = state_of(item)
            rows.append(
                {
                    "id": refs[ref],
                    "tag": f'{item.get("id", "-")}',
                    "label": item.get("title", ""),
                    "sub": st["label"].lower(),
                    "view": "desk",
                    "hay": (
                        f'{item.get("id", "")} {item.get("title", "")} {ref} '
                        f'{st.get("who", "")} {st["label"]}'
                    ).lower(),
                }
            )
    index = json.dumps(rows, ensure_ascii=False)
    return f"""
<script type="application/json" id="desk-index">{index}</script>
<div class="pal" id="pal" hidden>
  <div class="pal-box" role="dialog" aria-label="Find">
    <input type="text" placeholder="Ticket, number, or a word from a title"
           aria-label="Find" autocomplete="off">
    <ul role="listbox"></ul>
    <div class="pal-foot"><span><kbd>&uarr;</kbd><kbd>&darr;</kbd> move</span>
    <span><kbd>enter</kbd> go</span><span><kbd>esc</kbd> close</span></div>
  </div>
</div>"""


def help_dialog() -> str:
    """How to work the thing, one keystroke away from every view.

    Three places do three different things, and the old version of this dialog
    listed chat phrases without ever saying how to get a chat, which is the one
    thing somebody reading it does not know.
    """
    ticks = [
        ("tg", "Prints where everything is. No tokens."),
        ("tg 4", "Job 4 is finished and nothing comes back."),
        ("tg 2 -w Kevin", "Sent. Parks it with him, so it stops looking like yours."),
        ("tg 2 --mine", "He answered. It is yours again."),
        ("tg 5 --dropped", "It went away. Add <code>-n</code> and a reason."),
        ("tg 1 --undo", "Forget that state entirely."),
    ]
    said = "".join(
        f'<li><span class="said">{esc(a)}</span><span class="does">{b}</span></li>'
        for a, b in ticks
    )
    return f"""
<dialog class="help" id="help">
  <div class="help-in">
    <button class="help-close" type="button">Close</button>
    <h2>How to use this</h2>
    <p class="lead">Two tabs. <b>TG my work</b> is what you do, in one numbered
    list. <b>TG what I say</b> is the words for the next meeting. Both read the
    same file, so they can never disagree.</p>

    <h3>Asking, and asking for changes</h3>
    <p>Every job has <b>Ask or change</b> at the foot of its card, every ticket
    has one under its threads, and every draft has <b>Rewrite or ask</b> in its
    header. It is a chat box: type, press <kbd>enter</kbd>, and it answers on the
    card in a minute or two. Both halves of the same conversation go in it, the
    question and the instruction:</p>
    <ul class="say-list">
      <li><span class="said">what do you mean by 稼働確認?</span><span class="does">Answers on the card, and the answer stays there.</span></li>
      <li><span class="said">rewrite this with the latest from the refinement thread, and tell Tanaka-san we are still checking</span><span class="does">Reads the thread, rewrites that draft in the ticket, says what it changed.</span></li>
      <li><span class="said">is that true about refinement?</span><span class="does">Checks it and tells you when it cannot find the source.</span></li>
    </ul>
    <p>You never say which draft or which ticket you mean, because the question
    goes off with the job attached: its draft, its prepared work, its threads and
    everything you have already asked about it. That is the whole point of asking
    from the card. It never marks anything done, and it never sends a word to
    anybody.</p>
    <p>From a terminal it is the same ask, and the answer lands on the same card:
    <code>tg ask 8 "is that true about refinement?"</code>, or a ticket tag
    instead of a number.</p>
    <p>The box above the tickets is the same thing for the questions that belong
    to no card: what to start on, whether tomorrow is covered, what you are
    forgetting. That one gets every open job at once and answers in job numbers.</p>
    <p><b>Every answer takes another question.</b> <b>Ask about this answer</b> at
    the foot of one opens a box inside it, and what you asked and what it said go
    with the follow-up, so <span class="said">why?</span> is a whole question
    there. The digging stays nested under the answer it is about. Answers shut to
    one line each, newest open, and the <b>&times;</b> in the corner forgets one
    for good.</p>

    <h3>When a card is longer than you want</h3>
    <p>Everything a card knows is on it, and most of it is shut. The words on a
    fold say what is behind it, so <b>Timeline, 10 moves today</b> already
    answers the only question you had. What is open is what needs you: where the
    ticket stands, and the jobs. Press a fold and the page remembers it, on this
    card only, until you press it again.</p>

    <h3>Finishing something</h3>
    <p>Not from the page. The page is a window on the board, so a tick on it
    would be a lie, and an answer to a question is not a job done either. In a
    terminal, instant and free:</p>
    <ul class="say-list">{said}</ul>
    <p><b>Sending a message is not finishing.</b> If a reply is coming, use
    <code>-w</code> and the name, so the card sits with them rather than
    pretending it is closed.</p>

    <h3>When you want a real conversation</h3>
    <p><code>tg chat</code> opens Cursor on this folder, and that is for the long
    ones: work spanning three jobs, something you want to argue about, anything
    where you will be reading code together. Same board, same rules, so
    &ldquo;do 3&rdquo; or &ldquo;draft the reply to Kevin&rdquo; work there with
    nothing else said. <b>Copy for a chat</b> on any ask box hands the job and
    your words over for exactly that, and it is what <kbd>enter</kbd> does on a
    page opened from disk, where there is no server to answer.</p>

    <h3>The numbers</h3>
    <p>The number to the left of a job is its own for life: job 3 is job 3 until
    it closes, tomorrow and next week. That is why &ldquo;do 3&rdquo; needs
    nothing else said, and why the list runs 3, 5, 2, 7 with gaps where closed
    work used to be. On <b>TG what I say</b> the numbers are different: those are
    each card's place on TG's own board, in the order the meeting works down
    them.</p>

    <h3>The buttons</h3>
    <p><b>Refresh</b> is the only button this tab needs. It re-reads Asana and
    every thread behind your open work, then rewrites everything here: what
    moved, which jobs that changes, what is closed, and the drafts. A draft the
    thread has overtaken gets rewritten, and one nobody needs to send any more is
    deleted, so what is on this tab is what to do as of the last sweep. Two or
    three minutes.</p>
    <p><b>Update prep</b> lives on <b>TG what I say</b>, because the only thing
    it adds is the words: what you say per ticket and what you need out of the
    room. It does the same sweep first, so it is Refresh plus the script, never
    less.</p>
    <p><b>Why the words are a separate button.</b> They are written for one room
    on one day, and some of them you have already read, cut or rehearsed. If
    every sweep rewrote them, a refresh at 17:00 would throw away the script you
    fixed at 16:00. So a refresh moves the work and leaves the script alone, then
    says plainly that the script is older than the board: amber at the top of
    <b>TG what I say</b>, and <b>Prep is older than the board</b> next to the
    room on this one.</p>
    <p><b>Meeting note</b> opens the last standup's Notion note.
    <b>Japanese only</b> strips the prep tab back to the lines you read aloud,
    and keeps <b>Rewrite or ask</b> on each of them, because reading a line out
    is when you notice it is wrong.</p>

    <h3>Where this page actually lives</h3>
    <p>On this laptop, and nowhere else. It is a small server on
    <code>127.0.0.1</code>, which is an address only this machine can reach, and
    the URL carries a random key on top of that. Nothing is hosted, so there is
    no address anyone else can type. The private GitHub repo holds the code and
    the prompts, never <code>state/</code> or <code>output/</code>, so your
    tickets, threads and drafts have never left the machine.</p>

    <h3>On your phone</h3>
    <p><code>tg phone</code> opens the page to your current wifi for an hour and
    prints the address, then puts it back to laptop-only on its own. During that
    hour anything on the same network needs the key to see anything, and the
    laptop has to be awake. <code>tg phone 15</code> for a shorter window,
    <code>tg stop</code> to end it now. On cafe or office wifi, prefer the short
    window.</p>

    <h3>Keys</h3>
    <p><kbd>1</kbd> your work, <kbd>2</kbd> what you say, <kbd>/</kbd> find
    anything, <kbd>s</kbd> Japanese only, <kbd>?</kbd> this.</p>
  </div>
</dialog>"""


def ticket_group(t: dict) -> str:
    """Which of the three piles a ticket belongs in.

    "live" is anything with open work on it. "clear" is a ticket where he has
    done his part and Asana still has it open, which is worth keeping in sight
    but not worth reading every morning. "closed" is finished on both sides.
    """
    if (t.get("asana") or {}).get("completed") or t.get("closed"):
        return "closed"
    if any(not state_of(i)["closed"] for i in t.get("items", [])):
        return "live"
    return "clear"


def tickets_bar(groups: dict[str, list[dict]], refs: dict[str, str]) -> str:
    """The section header for the cards, with where each ticket stands on it."""
    chips = []
    for t in groups["live"] + groups["clear"] + groups["closed"]:
        ref = t.get("ref", "")
        mine = sum(1 for i in t.get("items", []) if state_of(i)["state"] == "todo")
        open_n = sum(1 for i in t.get("items", []) if not state_of(i)["closed"])
        if mine:
            tone, what = "mine", f"{mine} with you"
        elif open_n:
            tone, what = "theirs", "nothing on you"
        else:
            tone, what = "clear", "clear"
        chips.append(
            f'<a class="tb-chip {tone}" href="#{esc(refs[ref])}">'
            f'<span class="dot"></span>{esc(ref)}<span class="s">{esc(what)}</span></a>'
        )
    total = sum(len(v) for v in groups.values())
    return f"""
  <section class="tickets-bar" id="tickets">
    <div class="tb-head">
      <h2>Open Asana tickets</h2>
      <span class="tb-n">{total} in your name</span>
    </div>
    <div class="tb-chips">{"".join(chips)}</div>
  </section>"""


def render(data: dict) -> str:
    pretty = date.today().strftime("%a %-d %b")
    item_index = index_items(data.get("tickets", []))

    # Tickets you owe something on come first. Everything open stays on the page.
    def ticket_order(t: dict) -> tuple:
        """Cards in the order he should work them, not the order they arrived.

        Work he owes a person comes before work he owes a room, and both come
        before work with no date on it at all. Within that the number decides,
        so the sequence is stable from one build to the next.
        """
        states = [state_of(i) for i in t.get("items", [])]
        mine = [
            i
            for i in t.get("items", [])
            if state_of(i)["state"] == "todo" and not blocked_on(i, item_index)
        ]
        return (
            0 if mine else
            1 if any(not s["closed"] for s in states) else 2,
            0 if any(i.get("committed_to") for i in mine) else 1,
            0 if any(i.get("at_standup") for i in mine) else 1,
            min((pressing(i) for i in mine), default=9),
            min((i.get("id", 99) for i in t.get("items", [])), default=99),
        )

    tickets = sorted(data.get("tickets", []), key=ticket_order)
    refs = {t.get("ref", ""): anchor(t.get("ref", "")) for t in tickets}
    # "Raise at the onsite" and "Raise at standup" are different instructions,
    # so the pill says which room it means.
    raise_label = f'Raise at {next_live(data).get("name", "standup").lower()}'
    soon = next_live(data)

    groups: dict[str, list[dict]] = {"live": [], "clear": [], "closed": []}
    for t in tickets:
        groups[ticket_group(t)].append(t)

    def cards_for(rows: list[dict]) -> str:
        return "".join(
            render_ticket(t, refs[t.get("ref", "")], raise_label, soon, item_index)
            for t in rows
        )

    cards = cards_for(groups["live"])
    for key, title, why in (
        (
            "clear",
            "Done your part, still open in Asana",
            "Nothing here needs you. It stays because Asana has not closed it.",
        ),
        ("closed", "Closed on both sides", "Kept for the record."),
    ):
        if groups[key]:
            cards += f"""
    <details class="tk-fold" data-remember="tk-{key}">
      <summary>{esc(title)} <span class="n">{len(groups[key])}</span>
      <span class="q">{esc(why)}</span><span class="fold-hint"></span></summary>
      {cards_for(groups[key])}
    </details>"""

    total = sum(
        i.get("est_minutes") or 0
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo"
    )

    # `watch` was the old name for the same thing, so a board written before the
    # rename still shows its rows rather than dropping them silently.
    news = data.get("news") or data.get("watch") or []

    gaps = data.get("gaps", [])
    gap_block = ""
    if gaps:
        items = "".join(f"<li>{esc(g)}</li>" for g in gaps)
        gap_block = f'<section class="gaps"><h2>Open gaps</h2><ul>{items}</ul></section>'

    mine = sum(
        1
        for t in tickets
        for i in t.get("items", [])
        if state_of(i)["state"] == "todo"
    )

    meta = script_meta(data)
    built = meta.get("built_at", "")
    has_script = any((t.get("prep") or {}).get("script") for t in tickets)
    # A script written before the last sweep may not know the newest replies.
    stale = bool(has_script and built and built < (data.get("checked_at") or ""))
    prep_label = "Update prep" if has_script else "Write prep"

    # The countdown only makes sense on the day of a session, and an empty value
    # is what tells the page not to draw one at all.
    today_iso = date.today().isoformat()
    on_today = soon.get("date") == today_iso and soon.get("at")
    meeting = f'{today_iso}T{soon.get("at")}:00+09:00' if on_today else ""
    meeting_label = soon.get("name", "standup").lower() if on_today else ""

    body = f"""
<header class="top"><div class="top-in">
  <span class="brand"><img src="/icon-192.png" alt="" onerror="this.remove()">
  <h1>Billing desk</h1></span>
  {view_tabs(mine, has_script, script_session(data))}
  <span class="acts">
    <span class="date {"old" if is_stale(data.get("checked_at", "")) else ""}">
      {esc(pretty)} &middot; {esc(checked_line(data.get("checked_at", "")))}</span>
    <span id="countdown"></span>
    {link_btn((data.get("meeting_note") or {}).get("url", ""), "Meeting note")}
    <button class="toggle" id="scriptonly">Japanese only</button>
    {controls(prep_label)}
    <button class="toggle" data-help type="button" aria-label="How to use this"
            title="How to use this">?</button>
  </span>
</div></header>
<div class="wrap" id="top">
  <div id="view-desk" role="tabpanel">
    {jump_bar(tickets, refs, True)}
    {need_to_know(data, has_script, news, tickets, soon)}
    {render_track(tickets, refs, soon)}
    <div class="howto">
      <span>{f"About <b>{total} min</b> of this is yours. " if total else ""}Every job takes questions and changes: <b>Ask or change</b> at the foot of its card, <kbd>enter</kbd> to send. Finishing one is the page's blind spot: run <code>tg 3</code> in a terminal.</span>
      <button class="more" data-help type="button">How to use this</button>
    </div>
    {ask_block("board", "the desk", ASKED.get("board", []),
               "Read prompt-ask.md, then answer this about the billing desk as a "
               "whole rather than one job:")}
    {tickets_bar(groups, refs)}
    {cards}
    {gap_block}
  </div>
  <div id="view-standup" role="tabpanel">
    {render_standup.render(data, refs, built, stale)}
  </div>
</div>
{finder(tickets, refs)}
{help_dialog()}"""
    return shell(
        "Billing desk", body, opening_view(data, has_script), meeting, meeting_label
    )


def render_error(message: str) -> str:
    body = f"""
<div class="wrap" style="padding-top:40px">
  <div class="err">
    <h1 style="margin:0 0 8px;font-size:20px">The desk did not build</h1>
    <p style="margin:0">The board is still there. Rebuild with
    <code>tg open</code>, or run <code>./run_post.sh --force</code> to start
    again from the meeting note. Details below.</p>
    <pre>{esc(message)}</pre>
  </div>
</div>"""
    return shell("Billing desk, build failed", body)


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == "--error":
        Path(args[2]).write_text(render_error(args[1]), encoding="utf-8")
        return 0
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    src, dest = Path(args[0]), Path(args[1])
    if not src.exists():
        print(f"missing {src}", file=sys.stderr)
        return 1
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {src}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict) or "tickets" not in data:
        print(f"{src} is missing the 'tickets' key", file=sys.stderr)
        return 1

    load_asks(src.parent / "asks.json")
    # Write then rename, so a page load reading this file never catches it half
    # written when two renders overlap.
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(render(apply_glossary(data)), encoding="utf-8")
    os.replace(tmp, dest)
    items = sum(len(t.get("items", [])) for t in data.get("tickets", []))
    print(f"wrote {dest} ({len(data['tickets'])} tickets, {items} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
