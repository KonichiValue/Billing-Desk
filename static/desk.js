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
  // The id of the question this page asked, so it can watch that rather than
  // whatever the server happens to be doing. Null when nothing of ours is out.
  var myAsk = null;
  // This page started a refresh or a prep, so a "done" belongs to us.
  var started = false;

  function thinking(s, queued) {
    if (!waiting) return;
    if (queued) {
      // One at a time, because an answer that rewrites a draft rewrites the whole
      // board. Say so, rather than counting seconds at a question nobody has
      // started reading yet.
      waiting.querySelector(".ask-wait-t").textContent = "Queued, behind the one in front";
      var q = waiting.querySelector(".ask-wait-tail");
      q.textContent = "It starts on its own. You can ask on other cards meanwhile.";
      q.hidden = false;
      return;
    }
    var secs = s.seconds || 0;
    var mins = secs >= 60 ? Math.floor(secs % 3600 / 60) + "m " + (secs % 60) + "s" : secs + "s";
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
    var open = document.querySelector(".ask-box:not([hidden]), .fu:not([hidden])");
    var pal = document.getElementById("pal");
    var help = document.getElementById("help");
    var over = (pal && !pal.hidden) || (help && help.open);
    return !half && !open && !over;
  }

  function boardMoved(s) {
    if (!s.stamp || !drawnFrom || s.stamp === drawnFrom) return false;
    if (safeToReload()) {
      say("The board changed, reloading");
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
      // My own question first, found by its id. Watching the one global job state
      // is wrong as soon as two things are in flight: an ask that finished while
      // something else was starting left this card spinning on "Sending" with the
      // answer already written to disk.
      if (myAsk) {
        var mine = (s.asks || {})[myAsk];
        if (mine) {
          thinking(s, mine === "queued");
          later(900);
          return;
        }
        myAsk = null;
        if (waiting) waiting.querySelector(".ask-wait-t").textContent = "Answered, opening it";
        say("Done, reloading");
        location.reload();
        return;
      }
      if (s.state === "running") {
        // A sweep reads every ticket and every thread behind it, so minutes are
        // normal. Saying how long it has been and what it last said is the
        // difference between a slow job and a job that looks stuck.
        var note = s.message + "\u2026";
        if (!waiting && s.seconds) {
          var m = s.seconds >= 60
            ? Math.floor(s.seconds / 60) + "m " + (s.seconds % 60) + "s"
            : s.seconds + "s";
          note = s.message + " \u00b7 " + m;
          if (s.last) note += " \u00b7 " + s.last.slice(0, 90);
        }
        say(note);
        thinking(s);
        later(waiting ? 900 : 2000);
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
        stopWaiting(s.message);
        login.hidden = false;
        if (s.url) { link.href = s.url; link.hidden = false; }
        say(s.message, "bad");
        later(3000);
        return;
      }
      if (s.state === "failed") {
        started = false;
        myAsk = null;
        ready(); stopWaiting(s.message); say(s.message, "bad");
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
      if (myAsk || started) { later(3000); return; }
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

  // Cancel, when there is something of ours actually running. It used to only
  // hide the box, which is the worst version: he thinks he has called it off,
  // the agent carries on, and a minute later it rewrites the draft he changed
  // his mind about. With nothing running it just shuts the box, as before.
  document.addEventListener("click", function (e) {
    var x = e.target.closest && e.target.closest(".ask-cancel, .fu-cancel");
    if (!x || !myAsk) return;
    var id = myAsk;
    myAsk = null;
    stopWaiting("Cancelled.");
    say("Cancelled");
    fetch("/api/cancel?k=" + encodeURIComponent(key), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    }).catch(function () { say("could not reach the desk server", "bad"); });
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
    b.textContent = "Sending\u2026";
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
      return r.json().then(function (j) {
        myAsk = j.id || null;
        say(j.ahead ? "Queued behind " + j.ahead : "Working on your question\u2026");
        poll();
      });
    }).catch(function (e) {
      stopWaiting("");
      b.disabled = false;
      b.textContent = "Send";
      hint.textContent = e.message;
    });
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
