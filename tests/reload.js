// The page reloads itself when the board moves under it. This is the test that
// it never does so while he is part-way through typing a question.
//
// Losing a half-written question to a helpful reload would be worse than the
// staleness the reload fixes, and it is the kind of fault you only find by doing
// it to yourself at the wrong moment. So the guard gets a test, run by
// ./check.py, with no browser and no packages: a stub DOM, a stub fetch, and the
// real static/desk.js evaluated against them.
//
//     node tests/reload.js

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");

function element(extra) {
  return Object.assign(
    {
      dataset: {},
      hidden: false,
      disabled: false,
      open: false,
      value: "",
      textContent: "",
      className: "",
      classList: {
        add() {}, remove() {}, toggle() {}, contains() { return false; },
      },
      listeners: {},
      addEventListener(type, fn) { this.listeners[type] = fn; },
      removeEventListener() {},
      querySelector() { return null; },
      querySelectorAll() { return []; },
      closest() { return null; },
      setAttribute() {}, getAttribute() { return null; },
      scrollIntoView() {}, focus() {}, remove() {},
      parentNode: null,
    },
    extra
  );
}

// One page, with the knobs the tests turn: what the page was drawn from, what is
// typed into the composer, and whether a composer is open at all.
function makePage(options) {
  const opts = Object.assign(
    { stamp: "AAA", typed: "", composerOpen: false, palOpen: false, helpOpen: false,
      running: "" },
    options
  );

  const ids = {
    login: element(),
    "login-link": element(),
    "refresh-note": element(),
    changed: element({ hidden: true }),
    pal: element({ hidden: !opts.palOpen }),
    help: element({ open: opts.helpOpen }),
  };
  const textarea = element({ value: opts.typed });

  const reloads = { count: 0 };
  const timers = [];

  const document = {
    body: element({ dataset: { stamp: opts.stamp, board: "B1" } }),
    hidden: false,
    getElementById: (id) => (Object.hasOwn(ids, id) ? ids[id] : null),
    querySelectorAll: (sel) => {
      if (sel === "[data-run]") return [element({ dataset: {} })];
      if (sel === ".ask textarea") return [textarea];
      // A question still out when the page was drawn: a bubble on one card.
      if (sel === ".qa[data-live]" && opts.running) {
        const box = element({ dataset: { ask: "item:1" } });
        return [element({ dataset: { qa: opts.running }, closest: () => box })];
      }
      return [];
    },
    querySelector: (sel) => {
      if (sel.indexOf(".ask-box") === 0) return opts.composerOpen ? element() : null;
      return null;
    },
    addEventListener() {},
    createElement: () => element(),
  };

  const sandbox = {
    document,
    window: { addEventListener() {} },
    location: { protocol: "http:", reload: () => { reloads.count += 1; } },
    navigator: {},
    console,
    JSON,
    Math,
    encodeURIComponent,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
    clearTimeout: () => {},
    // Whatever the test wants the server to be saying this poll.
    fetch: (url) => {
      sandbox.fetched.push(url);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(sandbox.reply),
        text: () => Promise.resolve("<ul class=\"qa-list\"></ul>"),
      });
    },
    fetched: [],
    Object,
    Date,
    reply: { state: "idle", message: "", asks: {}, stamp: opts.stamp },
  };

  const source = fs
    .readFileSync(path.join(ROOT, "static", "desk.js"), "utf8")
    // serve.py does this as it serves. Without it the script returns at line 3,
    // which is the whole point of that line, and the test would pass on nothing.
    .replace("__DESK_KEY__", "test-key-not-a-real-one")
    .replace("__DESK_BOOT__", "boot1");

  vm.runInNewContext(source, sandbox, { filename: "static/desk.js" });
  return { sandbox, reloads, timers, ids, textarea };
}

// The script polls on load and the reply is a promise, so let the microtasks run.
const settle = () => new Promise((r) => setImmediate(r));

const results = [];
function check(name, pass, detail) {
  results.push({ name, pass, detail });
}

async function run() {
  // 1. Nothing has changed. The page must sit quiet and keep watching.
  {
    const page = makePage({ stamp: "AAA" });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "AAA" };
    await settle();
    check("same stamp does not reload", page.reloads.count === 0,
      `reloaded ${page.reloads.count} times`);
    check("same stamp keeps watching", page.timers.length > 0,
      "no follow-up poll was scheduled, so the page went blind");
  }

  // 2. The board moved and nothing is half-written. This is `./tick.py 26` in a
  //    terminal, and it should reload on its own.
  {
    const page = makePage({ stamp: "AAA" });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "BBB" };
    await settle();
    check("a moved board reloads a clean page", page.reloads.count === 1,
      `reloaded ${page.reloads.count} times, wanted once`);
  }

  // 3. The board moved while he is typing. Nothing may be taken from under him.
  {
    const page = makePage({ stamp: "AAA", typed: "why is this still with Kevin" });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "BBB" };
    await settle();
    check("typing is never reloaded away", page.reloads.count === 0,
      "it reloaded and took his half-written question with it");
    check("it offers the reload instead", page.ids.changed.hidden === false,
      "no way back: it neither reloaded nor showed the button");
  }

  // 4. A composer open but empty still counts as his: reloading closes it.
  {
    const page = makePage({ stamp: "AAA", composerOpen: true });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "BBB" };
    await settle();
    check("an open composer is left alone", page.reloads.count === 0,
      "it closed a composer he had opened");
  }

  // 5. The finder open over the page is the same story.
  {
    const page = makePage({ stamp: "AAA", palOpen: true });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "BBB" };
    await settle();
    check("the finder is not reloaded away", page.reloads.count === 0,
      "it reloaded while the finder was open");
  }

  // 6. A server that never sends a stamp at all, which is an older serve.py
  //    still running behind a freshly rendered page.
  {
    const page = makePage({ stamp: "AAA" });
    page.sandbox.reply = { state: "idle", message: "", asks: {} };
    await settle();
    check("no stamp from the server is not a change", page.reloads.count === 0,
      "a server with no stamp put the page in a reload loop");
  }

  // 7. The server restarted under an unchanged board. Its key is new, so every
  //    button on this page would be refused until it reloads.
  {
    const page = makePage({ stamp: "AAA" });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "AAA", boot: "boot2" };
    await settle();
    check("a restarted server reloads a clean page", page.reloads.count === 1,
      `reloaded ${page.reloads.count} times, wanted once`);
  }

  // 8. The same server, same board: still quiet.
  {
    const page = makePage({ stamp: "AAA" });
    page.sandbox.reply = { state: "idle", message: "", asks: {}, stamp: "AAA", boot: "boot1" };
    await settle();
    check("the same server is not a restart", page.reloads.count === 0,
      "it reloaded with nothing changed");
  }

  // 9. His question was answered and the answer touched nothing but the
  //    conversation. It goes into the card in place; a reload is what used to
  //    put him somewhere else on the board.
  {
    const page = makePage({ stamp: "AAA", running: "q1" });
    page.sandbox.reply = { state: "done", message: "", asks: {}, stamp: "BBB", board: "B1" };
    await settle();
    await settle();
    check("an answer lands without a reload", page.reloads.count === 0,
      `reloaded ${page.reloads.count} times, wanted none`);
    check("it redraws that card's thread", page.sandbox.fetched.some((u) => u.indexOf("/api/thread?ref=item%3A1") === 0),
      "never asked the server for the card's thread: " + page.sandbox.fetched.join(", "));
  }

  // 10. The same answer, but it rewrote the board too (a draft, an item). That
  //     card must be redrawn from the board, so this one does reload.
  {
    const page = makePage({ stamp: "AAA", running: "q1" });
    page.sandbox.reply = { state: "done", message: "", asks: {}, stamp: "BBB", board: "B2" };
    await settle();
    await settle();
    check("an answer that moved the board reloads", page.reloads.count === 1,
      `reloaded ${page.reloads.count} times, wanted once`);
  }

  const bad = results.filter((r) => !r.pass);
  for (const r of results) {
    console.log(`  ${r.pass ? "ok  " : "FAIL"}  ${r.name}${r.pass ? "" : "\n          " + r.detail}`);
  }
  if (bad.length) {
    console.log(`\n${bad.length} of ${results.length} failed.`);
    process.exit(1);
  }
  console.log(`\nAll ${results.length} hold.`);
}

run().catch((e) => { console.error(e); process.exit(1); });
