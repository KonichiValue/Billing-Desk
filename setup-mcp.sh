#!/bin/zsh
# Give headless Claude Code the connections this desk reads from.
#
# Run it once. It adds any missing server, then walks the ones that need a
# browser approval. Everything it does is to your user config, so it counts for
# every folder, not only this one.
#
#   ./setup-mcp.sh          add what is missing, then log in to what needs it
#   ./setup-mcp.sh --check  say where things stand, change nothing

set -uo pipefail

HUB="https://hub.ai.ktl.net/mcp"
KTDB="$HOME/.local/bin/ktdb-mcp"

command -v claude >/dev/null 2>&1 || {
  print -u2 "claude is not installed. Nothing to set up."
  exit 1
}

states() { claude mcp list 2>&1 }

if [[ "${1:-}" == "--check" ]]; then
  states
  exit 0
fi

# Asana and Slack are the two a sweep cannot work without: the tickets and the
# threads. Google comes along because the AI Hub grants it beside Slack and a
# meeting invite is sometimes the only record of when a room happens.
for name in asana slack google; do
  if states | grep -q "^$name:"; then
    print "$name: already configured"
  else
    print "adding $name"
    claude mcp add --transport http --scope user "$name" "$HUB/$name" || {
      print -u2 "could not add $name"
      exit 1
    }
  fi
done

# The krakencore replica is a local process, not an OAuth grant, so it is only
# ever missing when this is a fresh machine.
if states | grep -q "^ktdb-tg-krakencore:"; then
  print "ktdb-tg-krakencore: already configured"
elif [[ -x "$KTDB" ]]; then
  print "adding ktdb-tg-krakencore"
  claude mcp add --scope user -e KTDB_CONN=tokyogas-prod.krakencore \
    ktdb-tg-krakencore -- "$KTDB"
else
  print "ktdb-tg-krakencore: no ktdb-mcp on this machine, skipping"
fi

print ""
print "Now the browser approvals. Each opens a tab; approve it and come back."

# Read the state fresh: a server added a moment ago always needs its grant.
needs=()
while IFS= read -r line; do
  [[ "$line" == *"Needs authentication"* ]] || continue
  needs+=("${line%%:*}")
done < <(states)

if (( ${#needs} == 0 )); then
  print "Nothing needs authorising. You are done."
else
  for name in "${needs[@]}"; do
    print ""
    print "--- $name ---"
    claude mcp login "$name" || print -u2 "$name did not complete. Run: claude mcp login $name"
  done
fi

print ""
print "Where things stand now:"
states
