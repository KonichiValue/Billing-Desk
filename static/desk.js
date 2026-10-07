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

  // A run in progress, as a chip rather than a sentence: which button, how
  // long, what it is doing now and how many steps it has taken. The step is
  // the server's plain phrase for the last tool call, never the model's
  // narration, so it reads "Reading the Slack thread" rather than half of
  // "Now let me check whether the".
  function progress(s) {
    var secs = s.seconds || 0;
    var clock = Math.floor(secs / 60) + ":" + ("0" + (secs % 60)).slice(-2);
    var title = { refresh: "Refresh", prep: "Prep" }[s.job] || "Working";
    var doing = s.last || s.message || "Starting";
    note.className = "refresh-note run";
    note.title = s.message || "";
    note.innerHTML =
      '<span class="rn-dot" aria-hidden="true"></span>' +
      '<b class="rn-job">' + esc(title) + "</b>" +
      '<span class="rn-time">' + clock + "</span>" +
      '<span class="rn-doing">' + esc(doing.slice(0, 70)) + "</span>" +
      (s.steps ? '<span class="rn-n">' + s.steps + " step" + (s.steps > 1 ? "s" : "") + "</span>" : "");
  }

  function ready() {
    runners.forEach(function (b) {
      b.disabled = false;
      b.textContent = b.dataset.label || b.textContent;
    });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // The questions this page is waiting on, by id, each with the card it was
  // asked from. Several can be out at once, one per card or three on one, and
  // each is a bubble in its own card's thread rather than one strip at the
  // bottom of the page. `tries` counts the redraws that still showed it running,
  // which happens for a second after a Stop while the process winds down.
  var mine = {};
  // This page started a refresh or a prep, so a "done" belongs to us.
  var started = false;

  function pending() {
    for (var k in mine) if (Object.hasOwn(mine, k)) return true;
    return false;
  }

  function bubbleFor(id) {
    return document.querySelector ? document.querySelector('.qa[data-qa="' + id + '"]') : null;
  }

  function clock(secs) {
    return secs >= 60 ? Math.floor(secs % 3600 / 60) + "m " + (secs % 60) + "s" : secs + "s";
  }

  // One bubble's live line. The CLI usually holds its text to the end, so most
  // of the wait is the count and the dots, and the second line is there to say a
  // long wait is still a normal one.
  function thinking(id, s, queued) {
    var li = bubbleFor(id);
    if (!li) return;
    var t = li.querySelector(".ask-wait-t");
    var tail = li.querySelector(".ask-wait-tail");
    if (!t || !tail) return;
    li.classList.toggle("queued", !!queued);
    if (queued) {
      t.textContent = "Queued, behind the one in front";
      tail.textContent = "It starts on its own. You can ask on other cards meanwhile.";
      tail.hidden = false;
      return;
    }
    // Its own run's progress, not the header's: several can think at once.
    var run = (s.live || {})[id] || {};
    var secs = run.seconds || 0;
    t.textContent = secs ? "Thinking, " + clock(secs) : "Thinking";
    var word = run.last || (secs > 150
      ? "Still going. Anything that reads a thread takes a few minutes."
      : secs > 40 ? "Reading the ticket, the threads and what you asked before." : "");
    tail.textContent = word;
    tail.hidden = !word;
  }

  // One timer, so there is only ever one loop. Several branches used to schedule
  // the next poll themselves and the login path called poll() outright, which is
  // two loops running, then four, each one polling the server on its own clock.
  var timer = null;
  function later(ms) {
    if (timer) clearTimeout(timer);
    // Nothing worth watching while the tab is in the background. The check
    // happens the moment he comes back to it, which is exactly when he has just
    // typed something into a terminal.
    timer = document.hidden ? null : setTimeout(poll, ms);
  }

  // The stamp the page was drawn from. Everything that moves the board writes it
  // and moves the stamp with it: `./tick.py 26` in a terminal, a sweep on a
  // schedule, an ask answered in another tab. None of those come through this
  // page, and a desk quietly a version behind is the one failure this repo
  // exists to prevent.
  var drawnFrom = document.body.dataset.stamp || "";
  // And the server that drew it. A restarted server has a new key, so this page's
  // buttons would all be refused; reloading is how it gets the new one.
  var boot = "__DESK_BOOT__";
  var changed = document.getElementById("changed");
  if (changed) changed.addEventListener("click", function () { location.reload(); });

  function safeToReload() {
    // Everything else survives a reload: the open tab is in sessionStorage, the
    // folds are in localStorage, the browser puts the scroll back. Half a
    // sentence in a composer does not, so that is the one thing worth stopping
    // for. Losing what he was typing to a helpful refresh would be worse than
    // the staleness it fixes.
    var half = [].slice.call(document.querySelectorAll(".ask textarea"))
      .some(function (t) { return t.value.trim(); });
    // The reply line under an answer is always there, so only an open box at
    // the foot of a card counts as open: an empty reply line is not his.
    var open = document.querySelector(".ask-box:not([hidden])");
    var pal = document.getElementById("pal");
    var help = document.getElementById("help");
    var over = (pal && !pal.hidden) || (help && help.open);
    return !half && !open && !over && !ticking();
  }

  // The board alone, without the conversation. When only the conversation
  // moved and it is ours, the answer is swapped into its card in place: a
  // reload for that is what used to put him somewhere else on the board.
  var drawnBoard = document.body.dataset.board || "";

  function boardMoved(s) {
    var restarted = s.boot && boot.indexOf("DESK_BOOT") < 0 && s.boot !== boot;
    var moved = s.stamp && drawnFrom && s.stamp !== drawnFrom;
    if (!restarted && !moved) return false;
    var talkOnly = !restarted && s.board && drawnBoard && s.board === drawnBoard;
    if (talkOnly && pending()) {
      // Our own question moving from queued to running. The bubble already
      // says so; there is nothing to redraw.
      drawnFrom = s.stamp;
      return false;
    }
    if (talkOnly && Date.now() < quietUntil) {
      // Ours, a few seconds ago: a Stop written down, a question forgotten. The
      // card already shows it. Redraw what we touched rather than the page.
      drawnFrom = s.stamp;
      for (var ref in touched) if (Object.hasOwn(touched, ref)) redraw(ref);
      touched = {};
      return false;
    }
    // A job he has just pressed, with its Undo still on screen. The row already
    // shows the move; reloading would take the Undo away. The poll comes back
    // the moment the toast goes.
    if (!restarted && ticking()) return false;
    if (safeToReload()) {
      say(restarted ? "The desk server restarted, reloading" : "The board changed, reloading");
      location.reload();
      return true;
    }
    // Mid-sentence. Offer the reload rather than taking it.
    if (changed) changed.hidden = false;
    return false;
  }

  function poll() {
    timer = null;
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {
      // My own questions first, found by their ids. Watching the one global job
      // state is wrong as soon as two things are in flight: an ask that finished
      // while something else was starting left a card spinning on "Sending"
      // with the answer already written to disk.
      var asks = s.asks || {};
      var out = [];
      for (var id in mine) {
        if (!Object.hasOwn(mine, id)) continue;
        if (asks[id]) thinking(id, s, asks[id] === "queued");
        else out.push(id);
      }
      if (out.length) {
        landed(out, s);
        return;
      }
      if (pending()) {
        if (boardMoved(s)) return;
        later(900);
        return;
      }
      if (s.state === "running") {
        // A sweep reads every ticket and every thread behind it, so minutes are
        // normal. Saying how long it has been and what it last said is the
        // difference between a slow job and a job that looks stuck.
        progress(s);
        later(2000);
        return;
      }
      if (s.state === "done") {
        // Only reload for something this page started. The job state survives the
        // job, so a plain page load finding an old "done" would reload forever.
        if (!started) { ready(); if (!boardMoved(s)) { say(s.message); later(2500); } return; }
        started = false;
        say("Done, reloading");
        location.reload();
        return;
      }
      // Signed out is not a failure, it is one click. Offer the click, and the
      // link the CLI printed once it has one. Keep polling so the moment the
      // browser approval lands the buttons come back on their own.
      if (s.state === "needs_login") {
        ready();
        login.hidden = false;
        if (s.url) { link.href = s.url; link.hidden = false; }
        say(s.message, "bad");
        later(3000);
        return;
      }
      if (s.state === "failed") {
        started = false;
        ready(); say(s.message, "bad");
        later(2500);
        return;
      }
      login.hidden = true;
      link.hidden = true;
      ready();
      // Idle, which is where the page spends nearly all of its life and where it
      // used to stop looking. Keep a slow heartbeat so a change made anywhere
      // else arrives on its own.
      if (boardMoved(s)) return;
      say(s.message);
      later(2500);
    }).catch(function () {
      // One dropped poll is not a finished job. This used to have no catch at
      // all, so a single blip killed the loop and the card span until reload.
      if (pending() || started) { later(3000); return; }
      say("lost the desk server, retrying", "bad");
      later(5000);
    });
  }

  runners.forEach(function (b) {
    b.dataset.label = b.textContent;
    b.addEventListener("click", function () {
      runners.forEach(function (o) { o.disabled = true; });
      b.textContent = b.dataset.busy;
      started = true;
      say("Starting\u2026");
      fetch(b.dataset.run + "?k=" + encodeURIComponent(key), { method: "POST" })
        .then(poll)
        .catch(function () { ready(); say("could not reach the desk server", "bad"); });
    });
  });

  login.addEventListener("click", function () {
    login.disabled = true;
    say("Starting the sign-in\u2026");
    fetch("/api/login?k=" + encodeURIComponent(key), { method: "POST" })
      .then(function () { setTimeout(function () { login.disabled = false; later(0); }, 1500); })
      .catch(function () { login.disabled = false; say("could not reach the desk server", "bad"); });
  });

  // Test connections, in Settings. It lives here rather than in base.js because
  // it needs the server key, and base.js is the half of the front end that runs
  // on a page opened from disk with no server behind it.
  //
  // The check takes about twenty seconds (most of it starting a headless run to
  // count its tools), so the server does it in a thread and this polls
  // /api/status for the rows as they land. Every row arrives as it is decided,
  // rather than all six at the end, because a panel that shows the credential
  // result in one second has already answered the usual question.
  //
  // Bound on the document rather than on the button, because this script runs
  // inline in the header while the page is still parsing: the Settings dialog
  // is at the end of the body and does not exist yet. The same reason the ask
  // sends are delegated a few lines down.
  (function () {
    var list, when, note, go;
    var watching = null;
    function parts() {
      go = document.querySelector("[data-check]");
      list = document.querySelector(".chk-rows");
      when = document.querySelector(".chk-when");
      note = document.querySelector(".chk-note");
      return !!(go && list && when && note);
    }

    function draw(h) {
      if (!parts()) return;
      var rows = h.rows || [];
      list.innerHTML = rows.map(function (r) {
        var mark = r.ok === true ? "ok" : r.ok === false ? "bad" : "unsure";
        var glyph = r.ok === true ? "\u2713" : r.ok === false ? "\u2715" : "?";
        return '<li class="chk ' + mark + '"><span class="chk-m">' + glyph + "</span>"
          + '<span class="chk-b"><b>' + esc(r.name) + "</b>" + esc(r.said || "")
          + (r.fix ? '<i>' + esc(r.fix) + "</i>" : "")
          + "</span></li>";
      }).join("");
      note.textContent = h.note || "";
      if (h.state === "running") {
        when.textContent = "Checking\u2026 " + rows.length + " of about 6";
      } else if (h.state === "done") {
        when.textContent = "Checked at " + (h.at || "");
        go.disabled = false;
        go.textContent = "Test again";
        if (watching) { clearInterval(watching); watching = null; }
      }
    }

    function esc(s) {
      return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
      });
    }

    function follow() {
      fetch("/api/status").then(function (r) { return r.json(); }).then(function (s) {
        if (s.health) draw(s.health);
      }).catch(function () {
        if (parts()) {
          when.textContent = "lost the desk server";
          go.disabled = false;
        }
        if (watching) { clearInterval(watching); watching = null; }
      });
    }

    document.addEventListener("click", function (e) {
      if (!e.target.closest("[data-check]")) return;
      if (!parts()) return;
      go.disabled = true;
      go.textContent = "Checking";
      note.textContent = "";
      list.innerHTML = "";
      when.textContent = "Starting\u2026";
      fetch("/api/check?k=" + encodeURIComponent(key), { method: "POST" })
        .then(function () {
          if (!watching) watching = setInterval(follow, 900);
          follow();
        })
        .catch(function () {
          go.disabled = false;
          go.textContent = "Test connections";
          when.textContent = "could not reach the desk server";
        });
    });
  })();

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
    // A question still running when the page was drawn, from before a reload
    // or from another tab. Watch it like one asked here, so its answer lands in
    // place rather than the bubble sitting on "Thinking" until the next reload.
    [].forEach.call(document.querySelectorAll(".qa[data-live]"), function (li) {
      var box = li.closest(".ask");
      if (box && li.dataset.qa && !mine[li.dataset.qa]) mine[li.dataset.qa] = { ref: box.dataset.ask };
    });
    if (pending()) later(0);
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
    hush();
    var card = bubble.closest(".ask");
    if (card) touched[card.dataset.ask] = true;
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

  // An answer landed. Put it into the card it was asked from, in place, and
  // keep whatever he was reading where it was on screen. A reload did the same
  // job and dropped him somewhere else on the board, which is what he asked to
  // stop. If the answer also rewrote the board (a draft changed, an item moved)
  // that card needs redrawing from the board, and that is a reload.
  function landed(ids, s) {
    var refs = {};
    ids.forEach(function (id) {
      refs[mine[id].ref] = true;
      delete mine[id];
    });
    if (s.board && drawnBoard && s.board !== drawnBoard) {
      say("Answered, and it changed the board");
      if (!boardMoved(s)) later(2500);
      return;
    }
    say("Answered");
    hush(s);
    var done = 0, want = 0;
    for (var ref in refs) if (Object.hasOwn(refs, ref)) want += 1;
    for (var r in refs) {
      if (!Object.hasOwn(refs, r)) continue;
      redraw(r, ids).then(function () {
        done += 1;
        if (done === want) later(pending() ? 900 : 2500);
      });
    }
  }

  // Swallow the next few seconds of conversation-only changes, which are ours:
  // the answer we just drew, a Stop being written down, a question forgotten.
  // Anything that touches the board itself still reloads.
  var quietUntil = 0;
  var touched = {};
  function hush(s) {
    quietUntil = Date.now() + 15000;
    if (s && s.stamp) drawnFrom = s.stamp;
  }

  // One card's conversation, fetched and swapped in. What he has typed into a
  // reply line survives it, and the screen does not move.
  function redraw(ref, fresh) {
    return fetch("/api/thread?ref=" + encodeURIComponent(ref)).then(function (r) {
      if (!r.ok) throw new Error("no thread");
      return r.text();
    }).then(function (html) {
      var place = window.deskPlace ? window.deskPlace.take() : null;
      [].forEach.call(document.querySelectorAll(".ask[data-ask]"), function (box) {
        if (box.dataset.ask !== ref) return;
        var thread = box.querySelector(".ask-thread");
        if (!thread) return;
        var kept = {};
        [].forEach.call(thread.querySelectorAll(".fu"), function (fu) {
          var t = fu.querySelector("textarea");
          if (t && t.value.trim()) kept[fu.dataset.parent] = t.value;
        });
        thread.innerHTML = html;
        for (var k in kept) {
          var back = thread.querySelector('.fu[data-parent="' + k + '"] textarea');
          if (back) back.value = kept[k];
        }
        (fresh || []).forEach(function (id) {
          var li = thread.querySelector('.qa[data-qa="' + id + '"]');
          if (li) li.classList.add("fresh");
        });
        var n = thread.querySelectorAll(".qa").length;
        var count = box.querySelector(".ask-n");
        if (count) count.textContent = n + " asked";
      });
      showSends();
      if (window.deskPlace) window.deskPlace.put(place);
    }).catch(function () {
      // No thread to swap in, so fall back to what this used to do: reload,
      // unless he is mid-sentence, in which case offer it.
      if (safeToReload()) location.reload();
      else if (changed) changed.hidden = false;
    });
  }

  // The bubble for a question that has just gone, drawn here so it is on the
  // card the instant he presses Enter rather than when the server gets round to
  // it. It is the same markup the server draws for a running question, so the
  // redraw that replaces it changes nothing he can see until the answer is in.
  function runningBubble(question, id) {
    var li = document.createElement("li");
    li.className = "qa running fresh";
    li.dataset.qa = id || "";
    li.dataset.live = "1";
    li.innerHTML =
      '<div class="qa-me"><span class="qa-k">You asked</span>' +
      '<span class="qa-q">' + esc(question) + "</span>" +
      '<span class="qa-when">just now</span></div>' +
      '<div class="qa-wait">' +
      '<span class="ask-dots" aria-hidden="true"><i></i><i></i><i></i></span>' +
      '<span class="ask-wait-t">Sending</span>' +
      '<button type="button" class="qa-stop" data-stop="' + esc(id || "") + '">Stop</button>' +
      '<span class="ask-wait-tail" hidden></span></div>';
    return li;
  }

  // Where a new question's bubble goes. A new question about the job goes at
  // the end of the card's thread; a reply goes under the exchange it replies
  // to, and the reply line moves down with it, the way the server draws it.
  function placeBubble(box, panel, li) {
    var thread = box.querySelector(".ask-thread");
    if (panel.classList.contains("fu")) {
      var of = panel.closest(".qa");
      var list = of && of.classList.contains("kid") ? of.parentNode : null;
      if (!list) {
        var det = panel.closest("details");
        list = det && det.querySelector(".qa-kids");
        if (!list && det) {
          list = document.createElement("ul");
          list.className = "qa-kids";
          det.insertBefore(list, panel);
        }
      }
      if (list) { list.appendChild(li); panel.hidden = true; return; }
    }
    var lists = thread ? [].filter.call(thread.children, function (c) {
      return c.classList.contains("qa-list");
    }) : [];
    var root = lists[lists.length - 1];
    if (!root && thread) {
      root = document.createElement("ul");
      root.className = "qa-list";
      thread.appendChild(root);
    }
    if (root) root.appendChild(li);
  }

  function failBubble(li, message) {
    li.className = "qa failed";
    var wait = li.querySelector(".qa-wait");
    if (wait) wait.remove();
    var bad = document.createElement("div");
    bad.className = "qa-bad";
    bad.innerHTML = "<b>That did not go</b>" + esc(message) +
      '<button type="button" class="qa-retry" data-retry="">Try again</button>';
    li.appendChild(bad);
  }

  // Send one question, from a fresh bubble or from Try again on an old one.
  function ask(ref, question, parent, li) {
    return fetch("/api/ask?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: ref, question: question, parent: parent || "" })
    }).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          throw new Error(j.error || j.message || "the desk server said no");
        });
      }
      return r.json().then(function (j) {
        if (!j.id) throw new Error("the desk server lost it");
        mine[j.id] = { ref: ref };
        li.dataset.qa = j.id;
        var stop = li.querySelector(".qa-stop");
        if (stop) stop.dataset.stop = j.id;
        thinking(j.id, {}, !!j.ahead);
        say(j.ahead ? "Queued behind " + j.ahead : "Working on your question…");
        poll();
      });
    });
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".ask-send");
    if (!b || b.hidden) return;
    var box = b.closest(".ask");
    // The send inside an answer is a follow-up to that answer; the one at the
    // foot of the card is a new question about the job.
    var panel = b.closest(".fu") || box.querySelector(".ask-box");
    var field = panel.querySelector("textarea");
    var hint = panel.querySelector(".ask-hint");
    var question = (field.value || "").trim();
    if (!question) { field.focus(); return; }
    if (hint) hint.textContent = "";
    var li = runningBubble(question, "");
    li.dataset.parent = panel.dataset.parent || "";
    placeBubble(box, panel, li);
    // The words are on the card now, in the bubble, so the composer lets go of
    // them: it shuts, and the next question starts on an empty line.
    field.value = "";
    field.style.height = "";
    if (!panel.classList.contains("fu")) {
      panel.hidden = true;
      var bar = box.querySelector(".ask-bar");
      if (bar) bar.hidden = false;
    }
    ask(box.dataset.ask, question, li.dataset.parent, li).catch(function (err) {
      failBubble(li, err.message);
    });
  });

  // Try again, on a bubble that failed. Sent as a new question with the same
  // words and the same parent, and the failed one is forgotten once the new one
  // is in the line, so the card does not keep both.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".qa-retry");
    if (!b) return;
    var li = b.closest(".qa");
    var box = li.closest(".ask");
    var q = li.querySelector(".qa-q");
    var old = b.dataset.retry;
    var question = q ? q.textContent.trim() : "";
    if (!box || !question) return;
    var fresh = runningBubble(question, "");
    fresh.dataset.parent = li.dataset.parent || "";
    li.parentNode.replaceChild(fresh, li);
    ask(box.dataset.ask, question, fresh.dataset.parent, fresh).then(function () {
      if (!old) return;
      hush();
      return fetch("/api/forget?k=" + encodeURIComponent(key), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: old })
      }).catch(function () { say("could not forget the failed one", "bad"); });
    }).catch(function (err) { failBubble(fresh, err.message); });
  });

  // Stop, on the bubble that is running. It used to be a Cancel that only hid
  // the box, which is the worst version: he thinks he has called it off, the
  // agent carries on, and a minute later it rewrites the draft he changed his
  // mind about.
  document.addEventListener("click", function (e) {
    var x = e.target.closest && e.target.closest(".qa-stop");
    if (!x) return;
    var id = x.dataset.stop;
    var li = x.closest(".qa");
    if (!id) return;
    delete mine[id];
    hush();
    var box = li.closest(".ask");
    if (box) touched[box.dataset.ask] = true;
    li.className = "qa cancelled";
    var k = li.querySelector(".qa-k");
    if (k) k.textContent = "Stopped";
    var wait = li.querySelector(".qa-wait");
    if (wait) wait.remove();
    say("Stopped");
    fetch("/api/cancel?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    }).catch(function () { say("could not reach the desk server", "bad"); });
  });

  // The move an answer proposed, now that he has pressed it. The server checks
  // it against the answer it saved and runs ./tick.py, which is still the only
  // thing that writes a state, so the move is in the item's history like any
  // other. The board has moved after it, so the card redraws from the board.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".qa-act");
    if (!b || b.disabled) return;
    var row = b.closest(".qa-acts");
    [].forEach.call(row.querySelectorAll(".qa-act"), function (o) { o.disabled = true; });
    b.classList.add("busy");
    fetch("/api/act?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: b.dataset.act, n: b.dataset.actN, verb: b.dataset.actVerb, who: b.dataset.actWho
      })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || "the desk server said no");
        var did = document.createElement("p");
        did.className = "qa-did";
        did.textContent = j.acted_on || "Moved";
        row.parentNode.replaceChild(did, row);
        later(300);
      });
    }).catch(function (err) {
      [].forEach.call(row.querySelectorAll(".qa-act"), function (o) { o.disabled = false; });
      b.classList.remove("busy");
      var k = row.querySelector(".qa-acts-k");
      if (k) { k.textContent = err.message; k.classList.add("bad"); }
    });
  });


  // The status on every job, Jira's lozenge. Pressing it is him saying the job
  // moved, on the job he means, so it runs ./tick.py like the terminal does and
  // the move is in the item's history. It always opens the moves open from where
  // the job stands, because a job here has more than two states and sending is
  // not finishing. Undo puts back exactly what was there.
  var menu = null, toastEl = null, toastTimer = null, last = null;
  function ticking() { return !!(menu || toastEl); }

  // What the lozenge says the moment a move is pressed, before the board answers.
  var AFTER = {
    done: ["Done", "green"], sent: ["Sent", "green"], dropped: ["Dropped", "grey"],
    mine: ["With you", "red"], waiting: ["Waiting", "blue"]
  };
  var TONE = ["red", "amber", "blue", "green", "grey"];

  function jobEls(n) {
    return [].slice.call(document.querySelectorAll('[data-job="' + n + '"]'));
  }
  function stats(n) {
    return [].slice.call(document.querySelectorAll('.stat[data-tick="' + n + '"]'));
  }
  // `look` is what the lozenge should say now, or null to put back what the
  // page was drawn with. Only a job that closed is struck through and folded
  // off the list; one handed to somebody is still open, just not his.
  function mark(n, closing, look) {
    jobEls(n).forEach(function (el) {
      el.classList.toggle("going", closing);
      if (!closing) el.classList.remove("gone");
      else if (el.classList.contains("tr")) {
        setTimeout(function () { if (el.classList.contains("going")) el.classList.add("gone"); }, 700);
      }
    });
    stats(n).forEach(function (c) {
      var t = c.querySelector(".stat-t");
      if (!c.dataset.was) c.dataset.was = t.textContent + "|" + (TONE.filter(function (k) { return c.classList.contains(k); })[0] || "grey");
      var was = c.dataset.was.split("|");
      var now = look || was;
      t.textContent = now[0];
      TONE.forEach(function (k) { c.classList.toggle(k, k === now[1]); });
      c.classList.toggle("on", !!look);
    });
  }
  function busy(n, on) {
    stats(n).forEach(function (c) { c.setAttribute("aria-busy", on ? "true" : "false"); });
  }

  function closeToast() {
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = null;
    if (toastEl) toastEl.remove();
    toastEl = null;
    later(0);
  }
  function toast(text, undo, bad) {
    if (toastEl) toastEl.remove();
    if (toastTimer) clearTimeout(toastTimer);
    toastEl = document.createElement("div");
    toastEl.className = "toast" + (bad ? " err" : "");
    toastEl.setAttribute("role", "status");
    var t = document.createElement("span");
    t.textContent = text;
    toastEl.appendChild(t);
    if (undo) {
      var u = document.createElement("button");
      u.type = "button";
      u.textContent = "Undo";
      u.title = "Put it back (u)";
      u.addEventListener("click", undo);
      toastEl.appendChild(u);
    }
    var x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.setAttribute("aria-label", "Dismiss");
    x.addEventListener("click", closeToast);
    toastEl.appendChild(x);
    document.body.appendChild(toastEl);
    toastTimer = setTimeout(closeToast, undo ? 6000 : 3500);
  }

  function tick(n, verb, who, before) {
    return fetch("/api/tick?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n: n, verb: verb, who: who || "", before: before || null })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || "the desk server said no");
        return j;
      });
    });
  }

  function undoLast() {
    if (!last) return;
    var was = last;
    last = null;
    mark(was.n, false, null);
    busy(was.n, true);
    toast("Putting " + was.n + " back…");
    tick(was.n, "undo", "", was.before).then(function () {
      busy(was.n, false);
      toast(was.n + " is back where it was");
    }).catch(function (err) {
      busy(was.n, false);
      mark(was.n, was.closing, was.look);
      toast("Could not undo " + was.n + ": " + err.message, null, true);
    });
  }

  function move(n, verb, who) {
    closeMenu();
    var closing = verb === "done" || verb === "sent" || verb === "dropped";
    var look = verb === "waiting" ? ["Waiting on " + who, "blue"] : AFTER[verb];
    mark(n, closing, look);
    busy(n, true);
    tick(n, verb, who).then(function (j) {
      busy(n, false);
      last = { n: n, before: j.before, closing: closing, look: look };
      toast(j.said || n + " moved", undoLast);
    }).catch(function (err) {
      busy(n, false);
      mark(n, false, null);
      toast("Could not move " + n + ": " + err.message, null, true);
    });
  }

  function closeMenu() {
    if (!menu) return;
    var from = menu._from;
    menu.remove();
    menu = null;
    if (from) from.setAttribute("aria-expanded", "false");
  }
  function option(label, small, fn) {
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "menuitem");
    b.textContent = label;
    if (small) {
      var s = document.createElement("small");
      s.textContent = small;
      b.appendChild(s);
    }
    b.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
    return b;
  }
  // A name to hand the job to. Sent and waiting on somebody is the move a
  // draft usually ends in, so on a job with one it comes first.
  function whoRow(n, placeholder, button, value) {
    var row = document.createElement("form");
    row.className = "who";
    var input = document.createElement("input");
    input.value = value || "";
    input.placeholder = placeholder;
    input.setAttribute("aria-label", placeholder);
    var go = document.createElement("button");
    go.type = "submit";
    go.textContent = button;
    row.appendChild(input);
    row.appendChild(go);
    row.addEventListener("submit", function (e) {
      e.preventDefault();
      if (input.value.trim()) move(n, "waiting", input.value.trim());
      else input.focus();
    });
    return row;
  }
  function heading(text) {
    var h = document.createElement("div");
    h.className = "stat-h";
    h.textContent = text;
    return h;
  }
  function openMenu(c) {
    closeMenu();
    if (c.getAttribute("aria-busy") === "true") return;
    var n = c.dataset.tick, st = c.dataset.state, who = c.dataset.who || "";
    var draft = c.hasAttribute("data-draft");
    menu = document.createElement("div");
    menu.className = "stat-menu";
    menu.setAttribute("role", "menu");
    menu._from = c;
    c.setAttribute("aria-expanded", "true");
    var title = c.dataset.title || "";
    menu.appendChild(heading(n + (title ? "  " + title : "")));
    if (st === "done" || st === "sent" || st === "dropped") {
      menu.appendChild(option("Open it again", "back with you", function () { move(n, "mine"); }));
    } else if (st === "waiting") {
      menu.appendChild(option("They replied", "it is yours again", function () { move(n, "mine"); }));
      menu.appendChild(option("Done", "nothing more comes back", function () { move(n, "done"); }));
      menu.appendChild(heading("Handed on"));
      menu.appendChild(whoRow(n, "Now with who?", "Move", ""));
      menu.appendChild(option("Dropped", "no longer needed", function () { move(n, "dropped"); }));
    } else {
      if (draft) {
        menu.appendChild(heading("Sent it?"));
        menu.appendChild(whoRow(n, "Waiting on who?", "Sent", who));
      }
      if (st === "hold") {
        menu.appendChild(option("Start it now", "the hold is over, it is yours", function () { move(n, "mine"); }));
      }
      menu.appendChild(option("Done", "nothing comes back", function () { move(n, "done"); }));
      if (!draft) {
        var hand = option("With someone else", "a reply or their part is owed", function () {
          var row = whoRow(n, "Waiting on who?", "Move", who);
          hand.replaceWith(row);
          row.querySelector("input").focus();
        });
        menu.appendChild(hand);
      }
      menu.appendChild(option("Dropped", "no longer needed", function () { move(n, "dropped"); }));
    }
    document.body.appendChild(menu);
    var r = c.getBoundingClientRect();
    var left = Math.min(r.right + window.scrollX - menu.offsetWidth, window.scrollX + document.documentElement.clientWidth - menu.offsetWidth - 12);
    menu.style.left = Math.max(8, left) + "px";
    var below = r.bottom + 6 + menu.offsetHeight < window.innerHeight;
    menu.style.top = (below ? r.bottom + window.scrollY + 6 : r.top + window.scrollY - menu.offsetHeight - 6) + "px";
    var first = menu.querySelector("input,[role=menuitem]");
    if (first) first.focus();
  }

  // Up and down walk the menu, the way every menu does, and Escape leaves it
  // from anywhere in it, the name box included.
  document.addEventListener("keydown", function (e) {
    if (menu && e.key === "Escape") {
      var from = menu._from;
      closeMenu();
      if (from) from.focus();
      e.preventDefault();
      return;
    }
    if (!menu || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
    var all = [].slice.call(menu.querySelectorAll("input,[role=menuitem]"));
    var i = all.indexOf(document.activeElement);
    var next = all[(i + (e.key === "ArrowDown" ? 1 : all.length - 1)) % all.length];
    if (next) { next.focus(); e.preventDefault(); }
  });

  // Capture, so the press never reaches the summary it sits in and opens the
  // card instead.
  document.addEventListener("click", function (e) {
    var c = e.target.closest && e.target.closest(".stat");
    if (!c) {
      if (menu && !(e.target.closest && e.target.closest(".stat-menu"))) closeMenu();
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    if (menu && menu._from === c) closeMenu();
    else openMenu(c);
  }, true);

  // j and k walk the list, x opens its status, Enter opens the card, u undoes.
  // The list is the To do list on the desk; a row folded away is not in the walk.
  var focusAt = -1;
  function walk() {
    var list = document.querySelector("#todo .track-list");
    if (!list) return [];
    return [].slice.call(list.querySelectorAll("[data-job]")).filter(function (el) {
      return el.offsetParent !== null && !el.classList.contains("going");
    });
  }
  function focusRow(rows, i) {
    rows.forEach(function (el) { el.classList.remove("kfocus"); });
    if (!rows.length) return;
    focusAt = Math.max(0, Math.min(i, rows.length - 1));
    rows[focusAt].classList.add("kfocus");
    rows[focusAt].scrollIntoView({ block: "nearest" });
  }
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || e.target.isContentEditable) return;
    if (document.querySelector("dialog[open]")) return;
    if (document.body.dataset.view === "standup") return;
    var rows = walk();
    var cur = document.querySelector("#todo .kfocus");
    var at = cur ? rows.indexOf(cur) : -1;
    if (e.key === "j") { focusRow(rows, at + 1); e.preventDefault(); }
    else if (e.key === "k") { focusRow(rows, at < 0 ? 0 : at - 1); e.preventDefault(); }
    else if ((e.key === "x" || e.key === "e") && cur) {
      var c = cur.querySelector(".stat");
      if (c) { openMenu(c); e.preventDefault(); }
    } else if ((e.key === "Enter" || e.key === "o") && cur) {
      var a = cur.querySelector("a.tr-title,a[href]");
      if (a) { a.click(); e.preventDefault(); }
    } else if (e.key === "u" && last) { undoLast(); e.preventDefault(); }
  });

  // Coming back to the tab is the moment worth checking. The usual way the board
  // moves is him running `./tick.py 26` in a terminal and then looking at the
  // page, so the reload should be waiting for him rather than up to two seconds
  // behind. It also picks the loop back up, since it stops while hidden.
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) later(0);
  });
  window.addEventListener("focus", function () { if (!timer) later(0); });

  poll();
})();
