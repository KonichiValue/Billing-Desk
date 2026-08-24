#!/bin/zsh
# Put the list one click away: a Dock app, and `tg` in the terminal.
#
#   ./install.sh
#
# Both point at this checkout, so nothing is copied and nothing goes stale.
# Run it again after pulling; it is safe to repeat.

set -euo pipefail

DIR="${0:A:h}"
APP="$HOME/Applications/TG Billing Desk.app"
BIN="$HOME/.local/bin"

mkdir -p "$BIN" "$HOME/Applications"

chmod +x "$DIR/bin/tg" "$DIR/tick.py" "$DIR/run_post.sh"
ln -sf "$DIR/bin/tg" "$BIN/tg"
print -r -- "linked $BIN/tg"

# Icon: drawn here rather than shipped as a binary blob in the repo.
python3 "$DIR/app/make_icon.py" "$DIR/app/icon.png" >/dev/null
ICONSET="$(mktemp -d)/icon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 64 128 256 512 1024; do
  sips -z $s $s "$DIR/app/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
done
# Retina names macOS expects alongside the plain ones.
for s in 16 32 128 256 512; do
  cp "$ICONSET/icon_$((s * 2))x$((s * 2)).png" "$ICONSET/icon_${s}x${s}@2x.png" 2>/dev/null || true
done
iconutil -c icns "$ICONSET" -o "$DIR/app/icon.icns" 2>/dev/null \
  || print -r -- "could not build the icns, the app will use the generic icon"

# The two sizes the web manifest points at, so Chrome has an icon to give the
# installed app instead of falling back to its own logo.
for s in 192 512; do
  sips -z $s $s "$DIR/app/icon.png" --out "$DIR/app/icon-$s.png" >/dev/null 2>&1
done

# osacompile rather than a hand-rolled bundle: LaunchServices refuses to open a
# bare script bundle on this macOS, and this one comes out signed and valid.
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"'$DIR/bin/tg' open\""
[[ -f "$DIR/app/icon.icns" ]] && cp "$DIR/app/icon.icns" "$APP/Contents/Resources/applet.icns"
touch "$APP"
print -r -- "built $APP"

# Keep the page server up from login, so an installed web app always finds it.
# launchd gets no PATH of its own, so the plist is written with whichever
# python3 this shell resolves rather than whatever /usr/bin happens to hold.
AGENT="$HOME/Library/LaunchAgents/com.tg-billing-desk.serve.plist"
sed "s|/usr/bin/python3|$(command -v python3)|" \
  "$DIR/launchd/com.tg-billing-desk.serve.plist" >"$AGENT"
launchctl bootout "gui/$UID/com.tg-billing-desk.serve" 2>/dev/null || true
pkill -f "serve.py --port" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$UID" "$AGENT" 2>/dev/null \
  || launchctl load -w "$AGENT" 2>/dev/null \
  || print -r -- "could not load the page server agent, start it with: tg open"
print -r -- "page server running on http://127.0.0.1:8787/"

print -r -- ""
print -r -- "For a Dock icon that is yours rather than Chrome's, open"
print -r -- "http://127.0.0.1:8787/ in Chrome, then the ⋮ menu, Cast Save and Share,"
print -r -- "Install page as app. Chrome builds a real app with the desk icon."
print -r -- ""
print -r -- "  tg            open the page and see where you are"
print -r -- "  tg 4          finish item 4"
print -r -- "  tg refresh    go and see what moved"
