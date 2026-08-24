#!/bin/zsh
# Build the TG billing standup prep page and open it in the browser.
#
#   ./run_prep.sh            normal run, skips if today's page already exists
#   ./run_prep.sh --force    rebuild even if today's page exists
#   ./run_prep.sh --no-open  build only, don't open the browser

set -uo pipefail

DIR="${0:A:h}"
cd "$DIR" || exit 1

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export TZ="Asia/Tokyo"

FORCE=0
OPEN=1
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --no-open) OPEN=0 ;;
  esac
done

TODAY="$(date +%Y-%m-%d)"
JSON="output/prep-$TODAY.json"
HTML="output/prep-$TODAY.html"
LOG="logs/run.log"
AGENT_LOG="logs/agent-$TODAY.log"
TIMEOUT_SECS="${PREP_TIMEOUT:-900}"

mkdir -p output logs

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

fail() {
  log "FAILED: $1"
  python3 render.py --error "$1

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

log "building prep for $TODAY"
rm -f "$JSON"

MODEL_ARG=()
[[ -n "${PREP_MODEL:-}" ]] && MODEL_ARG=(--model "$PREP_MODEL")

cursor-agent \
  --print \
  --force \
  --approve-mcps \
  --trust \
  --workspace "$DIR" \
  "${MODEL_ARG[@]}" \
  "$(cat prompt.md)" >"$AGENT_LOG" 2>&1 &
AGENT_PID=$!

( sleep "$TIMEOUT_SECS"; kill -0 $AGENT_PID 2>/dev/null && kill -9 $AGENT_PID 2>/dev/null ) &
WATCHDOG=$!

wait $AGENT_PID
AGENT_RC=$?
kill $WATCHDOG 2>/dev/null

if [[ ! -f "$JSON" ]]; then
  fail "the agent finished (exit $AGENT_RC) without writing $JSON"
fi

if ! python3 render.py "$JSON" "$HTML" >>"$LOG" 2>&1; then
  fail "could not render $JSON into HTML. See $LOG"
fi

log "built $HTML"
[[ $OPEN -eq 1 ]] && open "$HTML"
exit 0
