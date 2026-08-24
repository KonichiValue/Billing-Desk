#!/bin/zsh
# Build the post-standup action list and open it in the browser.
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
JSON="output/post-$TODAY.json"
HTML="output/post-$TODAY.html"
LOG="logs/run.log"
AGENT_LOG="logs/agent-post-$TODAY.log"
TIMEOUT_SECS="${POST_TIMEOUT:-900}"
DEADLINE="${POST_DEADLINE:-11:45}"
RETRY_SECS="${POST_RETRY:-300}"

mkdir -p output logs state

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] post: $*" | tee -a "$LOG"; }

fail() {
  log "FAILED: $1"
  python3 render_post.py --error "$1

Agent log: $DIR/$AGENT_LOG" "$HTML"
  [[ $OPEN -eq 1 ]] && open "$HTML"
  exit 1
}

if [[ -f "$HTML" && $FORCE -eq 0 ]]; then
  log "already built for $TODAY, opening existing page (use --force to rebuild)"
  [[ $OPEN -eq 1 ]] && open "$HTML"
  exit 0
fi

command -v cursor-agent >/dev/null 2>&1 || fail "cursor-agent is not on PATH"

if cursor-agent status 2>&1 | grep -qi "not logged in"; then
  fail "cursor-agent is not logged in. Run: cursor-agent login"
fi

MODEL_ARG=()
[[ -n "${POST_MODEL:-}" ]] && MODEL_ARG=(--model "$POST_MODEL")

# True when the JSON exists and reports that the meeting note was found.
note_found() {
  [[ -f "$JSON" ]] || return 1
  python3 - "$JSON" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(1)
sys.exit(0 if data.get("note_found") else 1)
PY
}

attempt=0
while true; do
  attempt=$((attempt + 1))
  log "attempt $attempt, looking for today's meeting note"
  rm -f "$JSON"

  cursor-agent \
    --print \
    --force \
    --approve-mcps \
    --trust \
    --workspace "$DIR" \
    "${MODEL_ARG[@]}" \
    "$(cat prompt-post.md)" >"$AGENT_LOG" 2>&1 &
  AGENT_PID=$!

  ( sleep "$TIMEOUT_SECS"; kill -0 $AGENT_PID 2>/dev/null && kill -9 $AGENT_PID 2>/dev/null ) &
  WATCHDOG=$!

  wait $AGENT_PID
  AGENT_RC=$?
  kill $WATCHDOG 2>/dev/null

  [[ -f "$JSON" ]] || fail "the agent finished (exit $AGENT_RC) without writing $JSON"

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

if ! python3 render_post.py "$JSON" "$HTML" >>"$LOG" 2>&1; then
  fail "could not render $JSON into HTML. See $LOG"
fi

# The markdown is the version a Cursor chat reads when handing work back.
if ! python3 render_md.py "$JSON" "output/post-$TODAY.md" >>"$LOG" 2>&1; then
  log "WARNING: markdown render failed, HTML page is still fine"
fi

if [[ -f state/skip-next.json ]]; then
  log "next standup marked as skipped: $(python3 -c 'import json;print(json.load(open("state/skip-next.json")).get("skip_date",""))' 2>/dev/null)"
fi

log "built $HTML"
[[ $OPEN -eq 1 ]] && open "$HTML"
exit 0
