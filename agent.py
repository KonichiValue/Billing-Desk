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
        # `--permission-mode bypassPermissions` is the headless equivalent of
        # Cursor's `--force --approve-mcps --trust`: the run is unattended, so a
        # permission prompt is a hang nobody is watching. The blast radius is
        # this folder, which is what `--add-dir` pins.
        cmd = [
            self.binary,
            "--print",
            "--permission-mode", "bypassPermissions",
            "--add-dir", str(ROOT),
        ]
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
        ):
            env.pop(var, None)
        return env

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
    missing = missing_mcps(kind)
    if missing:
        try:
            states = kind.mcp_states()
        except (OSError, subprocess.SubprocessError):
            states = {}
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
    return [], ""
