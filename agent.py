#!/usr/bin/env python3
"""Which agent CLI runs a job, and how to read what it says while it runs.

The buttons on the page and the verbs in `bin/tg` all end up here. Two CLIs can
do the work and they disagree about almost everything: the flag that turns
streaming on, the shape of the events, the word for "signed out". Keeping that
in one file is what lets the rest of the repo ask for "a sweep" without caring
which one answered.

`claude` leads because the MCP servers this desk needs are its own: Asana and
Slack through the Kraken AI Hub, the krakencore replica over stdio. `cursor-agent`
stays behind it as a fallback, because a sweep that cannot run on the morning of
a standup is worse than a sweep that runs on the second choice.

Nothing here writes to the board. It starts a process, turns its output into a
progress line and a log, and reports how it ended.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Opus 5.5 on the Kraken gateway. Named in full rather than as `opus`, because
# the alias follows whatever the account calls newest and a sweep that silently
# changes model between one morning and the next is a difference nobody asked
# for. `config.json` overrides per job, `TG_MODEL` for a single run.
DEFAULT_MODEL = "claude-low-carbon-apac-opus-5-5"

# The MCP servers a sweep cannot do its job without. Asana is where the tickets
# are and Slack is where the threads are; an agent missing either does not stop,
# it improvises, which is the failure this list exists to prevent. ktdb is not
# here: reading the replica is something some jobs do and no job requires.
NEEDED_MCPS = ("asana", "slack")

# The servers a run is allowed to call without being asked. Wider than
# NEEDED_MCPS on purpose: a sweep that reaches for the calendar to date a room,
# or the replica to see how many accounts a hold covers, should get an answer
# rather than a denial nobody is at the keyboard to clear.
MCP_ALLOW = ("asana", "slack", "google", "ktdb-tg-krakencore")

# The built-ins a sweep uses: read the repo, write the board, run ./tick.py.
# They are only listed because naming an MCP tool turns the allow list
# exhaustive, and then a tool nobody named is a tool nobody has. Task is absent
# on purpose: prompt-refresh.md forbids handing a sweep to a subagent, because
# the subagent comes back with a summary and the board loses the detail.
BUILTIN_TOOLS = (
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "TodoWrite", "NotebookEdit",
)


class Kind:
    """One agent CLI, and the vocabulary it happens to use."""

    name = ""
    binary = ""

    def available(self) -> bool:
        return subprocess.run(
            ["which", self.binary], capture_output=True, text=True
        ).returncode == 0


class Claude(Kind):
    """Claude Code, headless. The one with the MCP servers this desk needs."""

    name = "claude"
    binary = "claude"

    def command(self, model: str, prompt_is_stdin: bool = False) -> list[str]:
        # The run is unattended, so a permission prompt is a hang nobody is
        # watching, and `--add-dir` is what keeps the blast radius to this folder.
        #
        # `acceptEdits` rather than `bypassPermissions`, which is the opposite of
        # what it sounds like. On this machine bypassPermissions is refused and
        # quietly downgraded, so a sweep under it could not write a single file:
        # the one that ran on 24 Sep read every ticket and then lost all nine
        # findings. acceptEdits grants the file tools outright, and it is measured
        # rather than assumed, so re-measure before changing it.
        cmd = [
            self.binary,
            "--print",
            "--permission-mode", "acceptEdits",
            "--add-dir", str(ROOT),
        ]
        # No permission mode carries the MCP servers, which cost a day to learn:
        # every Asana call came back "you haven't granted it yet" under both
        # bypassPermissions and --dangerously-skip-permissions. An allow rule is
        # what settles it, and the anchored `mcp__<server>__*` form is the only one
        # that works. A bare `mcp__*` is skipped with a warning, and the
        # server-only `mcp__asana` clears the denial without granting the tool,
        # which reads like success until nothing comes back.
        #
        # Naming any tool makes the list exhaustive, so the built-ins have to be
        # named back in beside them. Leaving them out is what broke that same
        # sweep: Bash survived on remembered rules in settings.local.json, Write
        # had none, and `./tick.py` never ran.
        for tool in (*(f"mcp__{s}__*" for s in MCP_ALLOW), *BUILTIN_TOOLS):
            cmd += ["--allowedTools", tool]
        if model != "auto":
            cmd += ["--model", model]
        return cmd

    # stream-json refuses to run without --verbose, and the pair is what makes a
    # tool call visible the moment it starts rather than at the end.
    stream = ["--output-format", "stream-json", "--verbose"]

    def env(self) -> dict[str, str]:
        """The environment a headless run needs, with the host's stripped out.

        When this server is started from inside a Claude Code session, that
        session exports variables saying an app is managing the provider and
        holding the credentials. A child `claude` that reads them looks for an
        auth handshake that is not there and reports itself signed out. Dropping
        them sends it to `~/.claude/settings.json` and the gateway, which is
        where its real credentials are.
        """
        env = dict(os.environ)
        for var in (
            "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST",
            "CLAUDE_CODE_HOST_AUTH_ENV_VAR",
            "CLAUDE_CODE_HOST_SESSION_ID",
            "CLAUDE_CODE_SESSION_ID",
            "CLAUDE_CODE_ENTRYPOINT",
            "CLAUDE_CODE_MESSAGING_SOCKET",
            "CLAUDE_CODE_MESSAGING_TOKEN",
            "CLAUDE_AGENT_SDK_VERSION",
            "CLAUDECODE",
            "CLAUDE_CODE_SSE_PORT",
            "ANTHROPIC_AUTH_TOKEN",
            # A child of an attended session is told so, and then routes its
            # permission decisions back to a parent that is not listening for
            # them. Every MCP call comes back "you haven't granted it yet".
            "CLAUDE_CODE_CHILD_SESSION",
            "CLAUDE_CODE_SESSION_ATTENDED",
            "CLAUDE_CODE_EXECPATH",
            "CLAUDE_CODE_DIAGNOSTICS_FILE",
            "CLAUDE_PID",
            "CLAUDE_EFFORT",
        ):
            env.pop(var, None)
        env.update(self.mcp_env)
        return env

    # The one thing that makes a sweep possible, and it took a day of failed runs
    # to find. By default a headless run does not wait for its MCP servers: the
    # init event lists the three HTTP ones as `pending`, the first turn starts
    # with none of their tools in context, and every Asana call comes back as a
    # permission denial that no `--permission-mode` affects, because the tool was
    # never registered to be permitted. `claude mcp list` says "Connected"
    # throughout, which is what makes it so misleading.
    #
    # NONBLOCKING=0 makes startup wait for the handshake instead, and 5s is not
    # enough for four OAuth servers behind the hub. With both set, asana reports
    # 31 tools and slack 16 rather than nought.
    #
    # Claude Code 2.1.274 adds CLAUDE_CODE_MCP_STARTUP_WAIT_MS, which is the
    # purpose-built version of this; 2.1.207 is what is installed, so this is the
    # pair that works here. Setting it is harmless on a newer build.
    mcp_env = {
        "MCP_CONNECTION_NONBLOCKING": "0",
        "MCP_CONNECT_TIMEOUT_MS": "20000",
    }

    def signed_in(self) -> bool:
        """Whether a run would reach a model at all.

        `claude auth status` reports the first-party account, which says nothing
        here: this account authenticates to the Kraken gateway through
        `apiKeyHelper`, so a working setup reports `loggedIn: false`. What
        actually matters is whether the gateway is configured, so that is what
        is tested.
        """
        settings = Path.home() / ".claude" / "settings.json"
        try:
            conf = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        env = conf.get("env") or {}
        if conf.get("apiKeyHelper") or env.get("ANTHROPIC_API_KEY"):
            return True
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def mcp_states(self) -> dict[str, str]:
        """Every configured MCP server, and whether it is usable right now.

        Parsed from `claude mcp list`, which health-checks as it goes. The line
        ends in a tick for connected and says so in words when it needs
        authorising, so the test is on the words rather than on the glyph.

        **This answers a different question from the one a sweep needs.** It is an
        interactive health check: it reported all four Connected for a whole day
        while every headless run saw them `pending` and had no Asana tool at all.
        It is the right test for "has Rei approved this grant", which is what the
        Log in button and `setup-mcp.sh` ask. For "can the run about to spend
        money actually call Asana", use `tools_ready()`.
        """
        out = subprocess.run(
            [self.binary, "mcp", "list"],
            capture_output=True, text=True, check=False, timeout=90,
            stdin=subprocess.DEVNULL, env=self.env(), cwd=ROOT,
        )
        states: dict[str, str] = {}
        for raw in ANSI.sub("", out.stdout + out.stderr).splitlines():
            name, sep, rest = raw.partition(":")
            if not sep or not name.strip() or name.strip().startswith("Checking"):
                continue
            low = rest.lower()
            if "needs authentication" in low:
                states[name.strip()] = "needs-auth"
            elif "connected" in low:
                states[name.strip()] = "connected"
            elif "failed" in low or "error" in low:
                states[name.strip()] = "failed"
        return states

    def login_args(self, what: str) -> list[str]:
        # No account step: the gateway credential comes from apiKeyHelper, so
        # every login here is one MCP server's OAuth grant.
        return ["mcp", "login", what]

    def event(self, raw: dict) -> tuple[str, str]:
        """One event, as (what kind of thing happened, the thing).

        Three kinds matter to a page with a spinner on it: a tool call starting,
        prose arriving, and the final result. Everything else is noise the log
        does not need.
        """
        kind = raw.get("type")
        if kind == "assistant":
            for part in (raw.get("message") or {}).get("content") or []:
                if part.get("type") == "tool_use":
                    return "call", phrase_for(part.get("name") or "", part.get("input") or {})
                if part.get("type") == "text" and part.get("text"):
                    return "said", part["text"]
            return "", ""
        if kind == "result":
            whole = raw.get("result")
            if isinstance(whole, str) and whole.strip():
                return "result", whole
        return "", ""


class CursorAgent(Kind):
    """Cursor's agent. Kept as the fallback, not the first choice."""

    name = "cursor-agent"
    binary = "cursor-agent"

    def command(self, model: str, prompt_is_stdin: bool = False) -> list[str]:
        cmd = [self.binary, "--print", "--force", "--approve-mcps", "--trust",
               "--workspace", str(ROOT)]
        if model != "auto":
            cmd += ["--model", model]
        return cmd

    stream = ["--output-format", "stream-json", "--stream-partial-output"]

    def env(self) -> dict[str, str]:
        return dict(os.environ)

    def signed_in(self) -> bool:
        out = subprocess.run(
            [self.binary, "status"],
            capture_output=True, text=True, check=False, timeout=60,
            stdin=subprocess.DEVNULL,
        )
        return "not logged in" not in ANSI.sub("", out.stdout + out.stderr).lower()

    def mcp_states(self) -> dict[str, str]:
        out = subprocess.run(
            [self.binary, "mcp", "list"],
            capture_output=True, text=True, check=False, timeout=90,
            stdin=subprocess.DEVNULL,
        )
        states: dict[str, str] = {}
        for raw in ANSI.sub("", out.stdout + out.stderr).splitlines():
            name, sep, rest = raw.partition(":")
            if not sep or not name.strip():
                continue
            low = rest.lower()
            if "requires_authentication" in low:
                states[name.strip()] = "needs-auth"
            elif "ready" in low:
                states[name.strip()] = "connected"
        return states

    def login_args(self, what: str) -> list[str]:
        return ["login"] if what == "account" else ["mcp", "login", what]

    def event(self, raw: dict) -> tuple[str, str]:
        kind = raw.get("type")
        if kind == "assistant":
            said = "".join(
                p.get("text") or ""
                for p in (raw.get("message") or {}).get("content") or []
            )
            return ("said", said) if said else ("", "")
        if kind == "tool_call" and raw.get("subtype") == "started":
            call = raw.get("tool_call") or {}
            key = next(iter(call), "")
            name = key[: -len("ToolCall")] if key.endswith("ToolCall") else key
            return "call", phrase_for(name, (call.get(key) or {}).get("args") or {})
        if kind == "result":
            whole = raw.get("result")
            if isinstance(whole, str) and whole.strip():
                return "result", whole
        return "", ""


# Both CLIs, best first. `pick()` walks this in order.
KINDS: tuple[Kind, ...] = (Claude(), CursorAgent())

# What each tool is called, in each CLI's vocabulary, mapped to a verb. Claude
# capitalises its tool names and Cursor does not, so the lookup is lowercased.
VERBS = {
    "bash": "Running", "shell": "Running",
    "read": "Reading", "write": "Writing", "edit": "Editing",
    "notebookedit": "Editing", "delete": "Deleting", "ls": "Listing",
    "grep": "Searching", "glob": "Looking for",
    "websearch": "Searching the web", "webfetch": "Fetching",
    "fetch": "Fetching", "readlints": "Checking",
    "todowrite": "Planning", "task": "Handing off to a subagent",
    "skill": "Following its instructions",
}
HINTS = ("command", "path", "file_path", "target_file", "relative_workspace_path",
         "pattern", "glob_pattern", "query", "search_term", "url", "toolName",
         "prompt", "name")


def phrase_for(tool: str, args: dict) -> str:
    """One line naming what the agent has just gone off to do.

    An MCP tool carries its server in its name, which is the useful half: what
    a sweep is waiting on is almost always Asana or Slack answering.
    """
    if tool.startswith("mcp__"):
        bits = tool.split("__")
        server = bits[1] if len(bits) > 1 else "Tool"
        call = bits[2] if len(bits) > 2 else "call"
        return f"{server}: {call}"[:120]
    # Cursor's own MCP events name the server in the arguments instead.
    if tool == "mcp":
        where = args.get("serverName") or args.get("server") or "Tool"
        return f"{where}: {args.get('toolName') or 'call'}"[:120]
    hint = ""
    for name in HINTS:
        value = args.get(name)
        if isinstance(value, str) and value.strip():
            hint = value.strip()
            break
    hint = hint.replace(f"{ROOT}/", "").replace(str(ROOT), "the repo")
    verb = VERBS.get(tool.lower()) or tool or "Working"
    return (f"{verb} {hint}" if hint else verb)[:120]


def pick(prefer: str = "") -> Kind | None:
    """Which CLI is going to run this, or None when neither can.

    Installed and signed in, in order, so a `claude` that is present but has no
    gateway credential falls through to Cursor rather than failing the run.
    `TG_AGENT` forces one by name, which is how a fallback gets tested on a day
    it is not needed.
    """
    wanted = prefer or os.environ.get("TG_AGENT") or ""
    ordered = [k for k in KINDS if k.name == wanted] or list(KINDS)
    ready = [k for k in ordered if k.available()]
    for kind in ready:
        try:
            if kind.signed_in():
                return kind
        except (OSError, subprocess.SubprocessError):
            continue
    # Nothing is signed in. Hand back something installed anyway, so the caller
    # can report "sign in" against a named CLI rather than "nothing is here".
    return ready[0] if ready else None


def model_for(job: str) -> str:
    """Which model a job runs on.

    Opus 5.5 unless something says otherwise, because half of what comes out of
    this repo is read aloud to Tokyo Gas or sent to them in writing.
    """
    for var in (f"TG_{job.upper()}_MODEL", "TG_MODEL"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        conf = json.loads(CONFIG.read_text(encoding="utf-8")).get(job, {})
    except (OSError, ValueError):
        conf = {}
    return conf.get("model") or DEFAULT_MODEL


def tools_ready(kind: Kind, timeout: int = 180) -> tuple[bool, str]:
    """Whether a run starting now would actually have the tools, not just grants.

    The difference is the whole lesson of this file. `claude mcp list` health-checks
    interactively and said "Connected" for four servers while every headless run
    began with nought Asana tools, so a sweep spent real money reporting gaps that
    were only its own missing tools. This starts a run the way a sweep starts one,
    reads the `init` event it prints before the first turn, and counts the tools
    actually registered.

    It is cheap on purpose: the process is killed the moment `init` arrives, so no
    prompt is ever sent and no model is billed.
    """
    if not isinstance(kind, Claude):
        return True, ""        # only the claude path has this failure mode
    cmd = kind.command(model_for("refresh")) + kind.stream
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=kind.env(), text=True, bufsize=1,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                break
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") != "system" or event.get("subtype") != "init":
                continue
            tools = event.get("tools") or []
            short = [
                name for name in NEEDED_MCPS
                if not any(t.startswith(f"mcp__{name}__") for t in tools)
            ]
            if not short:
                return True, ""
            pending = {
                s.get("name"): s.get("status")
                for s in event.get("mcp_servers") or []
                if s.get("name") in short
            }
            return False, (
                f"{human(short)} answered the health check but brought no tools into "
                f"the run ({pending}). A sweep would read nothing and report gaps that "
                "are not there, so it has not been started."
            )
        return True, ""        # said nothing useful; let the run report for itself
    finally:
        proc.kill()
        proc.wait(timeout=10)


def human(names: list[str]) -> str:
    """"asana" and "slack" as "Asana and Slack", for a sentence on the page."""
    pretty = [n.replace("ktdb-tg-krakencore", "the database").title()
              if n != "ktdb-tg-krakencore" else "the database" for n in names]
    if len(pretty) <= 1:
        return "".join(pretty)
    return ", ".join(pretty[:-1]) + " and " + pretty[-1]


def missing_mcps(kind: Kind) -> list[str]:
    """Which of the servers a sweep needs are not usable.

    A server that is configured but unauthorised and a server nobody configured
    are the same problem from the page's point of view: the sweep cannot read
    that system. They differ in the fix, which is why the message says which.
    """
    try:
        states = kind.mcp_states()
    except (OSError, subprocess.SubprocessError):
        return []          # could not ask; let the run report its own failure
    return [n for n in NEEDED_MCPS if states.get(n) != "connected"]


# A readiness answer is good for a few minutes, and the check costs about 16
# seconds of Rei watching a spinner. Nothing it looks at changes on its own: a
# grant lapses in hours, not between two presses of Ask. So the good answer is
# remembered and the bad one is not, because a bad one is what he is actively
# fixing, and a cached "Slack needs authorising" would survive the login that
# fixed it.
_ready_cache: dict[str, float] = {}
READY_FOR_SECS = 240


def forget_readiness() -> None:
    """Drop the cached answer, after a login or a `./setup-mcp.sh`."""
    _ready_cache.clear()


def blockers(kind: Kind | None) -> tuple[list[str], str]:
    """Everything standing between the button and a real run, in one look."""
    if kind is None:
        return ["install"], (
            "No agent is installed. Install Claude Code, or type 'refresh' in a chat "
            "on this folder."
        )
    if not kind.signed_in():
        if kind.name == "claude":
            return ["account"], (
                "Claude Code has no model credential. Check apiKeyHelper in "
                "~/.claude/settings.json."
            )
        return ["account"], f"{kind.name} is signed out."
    fresh = _ready_cache.get(kind.name, 0)
    if time.time() - fresh < READY_FOR_SECS:
        return [], ""
    # `tools_ready` first, because it is both stricter and cheaper. It asks the
    # only question that decides whether a sweep works, and a run that has the
    # tools cannot have a lapsed grant, so the health check below is only ever
    # reached to explain a failure. Asking it first cost 8s on every press.
    ready, why = tools_ready(kind)
    if ready:
        _ready_cache[kind.name] = time.time()
        return [], ""
    missing = missing_mcps(kind) or ["tools"]
    if missing:
        try:
            states = kind.mcp_states()
        except (OSError, subprocess.SubprocessError):
            states = {}
        if missing == ["tools"]:
            return ["tools"], why
        absent = [n for n in missing if n not in states]
        names = " and ".join(n.title() for n in missing)
        verb = "needs" if len(missing) == 1 else "need"
        if absent:
            return missing, (
                f"{names} {verb} connecting before a refresh can read anything. "
                f"{' and '.join(n.title() for n in absent)} "
                f"{'is' if len(absent) == 1 else 'are'} not configured yet: run "
                f"./setup-mcp.sh"
            )
        return missing, f"{names} {verb} authorising before a refresh can read anything."
    return ["tools"], why
