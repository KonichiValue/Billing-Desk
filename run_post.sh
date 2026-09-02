#!/bin/zsh
# Fold today's standup into the board, then open the desk.
#
#   ./run_post.sh            normal run, skips if today's page already exists
#   ./run_post.sh --force    rebuild even if today's page exists
#   ./run_post.sh --no-open  build only, don't open the browser
#   ./run_post.sh --once     one attempt only, don't wait for the Notion note
#
# The Notion meeting note lands roughly five minutes after the standup ends, but
# the meeting itself can run long. So this polls: each attempt is a cheap agent
# run that exits early when the note is missing, and we retry until the deadline.

set -uo pipefail

DIR="${0:A:h}"
cd "$DIR" || exit 1

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export TZ="Asia/Tokyo"

FORCE=0
OPEN=1
ONCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --no-open) OPEN=0 ;;
    --once) ONCE=1 ;;
  esac
done

TODAY="$(date +%Y-%m-%d)"
BOARD="state/board.json"
HTML="output/desk.html"
LOG="logs/run.log"
AGENT_LOG="logs/agent-post-$TODAY.log"
TIMEOUT_SECS="${POST_TIMEOUT:-900}"
DEADLINE="${POST_DEADLINE:-11:45}"
RETRY_SECS="${POST_RETRY:-300}"

mkdir -p output logs state

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] post: $*" | tee -a "$LOG"; }

fail() {
  log "FAILED: $1"
  python3 render_desk.py --error "$1

Agent log: $DIR/$AGENT_LOG" "$HTML"
  [[ $OPEN -eq 1 ]] && open "$HTML"
  exit 1
}

command -v cursor-agent >/dev/null 2>&1 || fail "cursor-agent is not on PATH"

if cursor-agent status 2>&1 | grep -qi "not logged in"; then
  fail "cursor-agent is not logged in. Run: cursor-agent login"
fi

MODEL_ARG=()
[[ -n "${POST_MODEL:-}" ]] && MODEL_ARG=(--model "$POST_MODEL")

# The board has one writer at a time. A prep or a refresh the user is watching
# takes state/refresh.lock (see serve.py and bin/tg), and post must take the same
# one. Without it, a post poll firing in the post-standup window runs its agent
# straight into the prep the user just pressed: two agents writing state/board.json
# at once, which loses updates, and a stale kill -9 watchdog that can land on the
# wrong pid. Post is not urgent, so it waits for a live holder rather than racing.
LOCK="state/refresh.lock"

lock_is_held() {
  [[ -f "$LOCK" ]] || return 1
  local pid
  pid="$(cut -d' ' -f1 "$LOCK" 2>/dev/null)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  rm -f "$LOCK"   # stale: whoever held it is gone
  return 1
}

take_lock() {
  local waited=0
  while lock_is_held; do
    log "board is locked by $(cat "$LOCK" 2>/dev/null); waiting rather than racing it"
    sleep 10
    waited=$((waited + 10))
    (( waited > TIMEOUT_SECS )) && fail "waited $((TIMEOUT_SECS / 60)) min for the board lock; something else is stuck"
  done
  print -r -- "$$ launchd-post $(date +%H:%M)" >"$LOCK"
}

release_lock() {
  # Only ever remove our own lock, never one a prep took while we were between attempts.
  [[ -f "$LOCK" && "$(cut -d' ' -f1 "$LOCK" 2>/dev/null)" == "$$" ]] && rm -f "$LOCK"
}

trap 'release_lock; [[ -n "${WATCHDOG:-}" ]] && kill "$WATCHDOG" 2>/dev/null' EXIT INT TERM

# True when the board has already taken in today's meeting note.
note_found() {
  [[ -f "$BOARD" ]] || return 1
  python3 -c '
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        note = json.load(fh).get("meeting_note") or {}
except (OSError, json.JSONDecodeError):
    sys.exit(1)
sys.exit(0 if note.get("found") and note.get("date") == sys.argv[2] else 1)
' "$BOARD" "$TODAY"
}

if note_found && [[ $FORCE -eq 0 ]]; then
  log "today's note is already on the board, opening the desk (use --force to redo)"
  [[ $OPEN -eq 1 ]] && open "$HTML"
  exit 0
fi

attempt=0
while true; do
  attempt=$((attempt + 1))
  log "attempt $attempt, looking for today's meeting note"

  # Take the board lock for this attempt, and only this attempt. Released below
  # so a prep the user presses between polls can run without waiting out the
  # whole retry window.
  take_lock

  # A copy of the board before the agent touches it. state/ is not in git.
  python3 keep.py post >>"$LOG" 2>&1 || true

  cursor-agent \
    --print \
    --force \
    --approve-mcps \
    --trust \
    --workspace "$DIR" \
    "${MODEL_ARG[@]}" \
    "$(cat prompt-post.md)" >"$AGENT_LOG" 2>&1 &
  AGENT_PID=$!

  # Kill only if the pid is still our agent. A bare `kill -9 $AGENT_PID` will land
  # on whatever inherited that pid once the agent has exited, which is how a post
  # watchdog ends up killing an unrelated prep. The lock already stops the two
  # running together; this is the belt to that braces.
  ( sleep "$TIMEOUT_SECS"
    if kill -0 "$AGENT_PID" 2>/dev/null && ps -p "$AGENT_PID" -o command= 2>/dev/null | grep -q cursor-agent; then
      kill -9 "$AGENT_PID" 2>/dev/null
    fi ) &
  WATCHDOG=$!

  wait $AGENT_PID
  AGENT_RC=$?
  kill $WATCHDOG 2>/dev/null
  WATCHDOG=""
  release_lock

  [[ -f "$BOARD" ]] || fail "the agent finished (exit $AGENT_RC) without writing $BOARD"

  if note_found; then
    log "meeting note found on attempt $attempt"
    break
  fi

  if [[ $ONCE -eq 1 ]]; then
    fail "the meeting note has not been published yet (single attempt requested)"
  fi

  if [[ "$(date +%H:%M)" > "$DEADLINE" ]]; then
    fail "gave up at $DEADLINE: no Billing Stand Up meeting note published today"
  fi

  log "no note yet, retrying in $((RETRY_SECS / 60)) min"
  sleep "$RETRY_SECS"
done

if ! python3 render_desk.py "$BOARD" "$HTML" >>"$LOG" 2>&1; then
  fail "could not render $BOARD into HTML. See $LOG"
fi

# The markdown is the version a Cursor chat reads when handing work back.
if ! python3 render_desk_md.py "$BOARD" "output/desk.md" >>"$LOG" 2>&1; then
  log "WARNING: markdown render failed, HTML page is still fine"
fi

# Actions into Reminders, due today, or on the chase date when they are held.
# Opt in with POST_REMIND=1; needs Reminders access granted once.
if [[ "${POST_REMIND:-0}" == "1" ]]; then
  if ! python3 remind.py "$BOARD" >>"$LOG" 2>&1; then
    log "WARNING: could not push reminders"
  fi
fi

# Say what is coming, since a skipped standup or an onsite changes his week.
log "$(python3 - "$BOARD" <<'PY' 2>/dev/null || true
import json, sys
from render import sessions
board = json.load(open(sys.argv[1], encoding="utf-8"))
rows = sessions(board)
if not rows:
    print("no session on the board")
else:
    print("next: " + "; ".join(
        f"{s.get('title') or s.get('name')} {s.get('date')}"
        + (" (skipped)" if s.get("skipped") else "")
        for s in rows[:3]
    ))
PY
)"

log "built $HTML"
[[ $OPEN -eq 1 ]] && open "$HTML"
exit 0
