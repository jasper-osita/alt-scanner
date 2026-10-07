#!/bin/bash
# Alt Scanner: install as a Mac app without hosting.
# Serves the app at http://localhost:8787 (this Mac only), starts it at every login, then opens it so you can click Install.
# Run:      bash install-mac-app.sh                      (copy mode: re-run to update)
#           bash install-mac-app.sh <git repo URL>       (auto-update mode: pulls new versions by itself)
#           Running it from inside a Git clone also turns on auto-update, using that clone's origin.
# Remove:   bash uninstall-mac-app.sh
set -euo pipefail
PORT=8787
LABEL="com.jas.altscanner"
SRC="$(cd "$(dirname "$0")" && pwd)"
APPDIR="$HOME/Library/Application Support/AltScanner"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UPLIST="$HOME/Library/LaunchAgents/$LABEL.update.plist"
REPO="${1:-}"
if [ -z "$REPO" ] && [ -d "$SRC/.git" ]; then REPO="$(git -C "$SRC" remote get-url origin 2>/dev/null || true)"; fi

# Python 3 runs the tiny local server (it ships with Xcode Command Line Tools)
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c "import http.server" >/dev/null 2>&1; then
  echo "Python 3 is needed for the local server. Install Apple's Command Line Tools, then run this again:"
  echo "  xcode-select --install"
  exit 1
fi
PY="$("$PY" -c 'import sys; print(sys.executable)')"

mkdir -p "$APPDIR/logs" "$HOME/Library/LaunchAgents"
if [ -n "$REPO" ]; then
  command -v git >/dev/null 2>&1 || { echo "Git is needed for auto-updates. Run: xcode-select --install"; exit 1; }
  echo "Auto-update mode: installing from $REPO"
  if [ -d "$APPDIR/site/.git" ]; then
    git -C "$APPDIR/site" remote set-url origin "$REPO"
    git -C "$APPDIR/site" fetch --quiet origin && git -C "$APPDIR/site" reset --hard --quiet "@{upstream}"
  else
    rm -rf "$APPDIR/site"; git clone --quiet "$REPO" "$APPDIR/site"
  fi
else
  echo "Copying the app to $APPDIR (re-run this script to update)"
  mkdir -p "$APPDIR/site"
  rsync -a --delete --exclude "install-mac-app.sh" --exclude "uninstall-mac-app.sh" --exclude ".vercel" --exclude ".git" "$SRC/" "$APPDIR/site/"
fi

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$APPDIR/site/server.py</string><string>$PORT</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$APPDIR/logs/server.log</string>
  <key>StandardErrorPath</key><string>$APPDIR/logs/server.log</string>
</dict>
</plist>
PLIST

echo "Starting the local server (it will also start at every login)"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load -w "$PLIST"

if [ -n "$REPO" ]; then
  cat > "$UPLIST" <<UPL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL.update</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$APPDIR/site/update-mac-app.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>900</integer>
  <key>StandardOutPath</key><string>$APPDIR/logs/update.log</string>
  <key>StandardErrorPath</key><string>$APPDIR/logs/update.log</string>
</dict>
</plist>
UPL
  launchctl bootout "gui/$(id -u)" "$UPLIST" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$UPLIST" 2>/dev/null || launchctl load -w "$UPLIST"
fi

for i in $(seq 1 20); do
  curl -fs "http://localhost:$PORT/" >/dev/null 2>&1 && break
  sleep 0.5
done
if ! curl -fs "http://localhost:$PORT/" >/dev/null 2>&1; then
  echo "The server didn't start. Check $APPDIR/logs/server.log (another app may be using port $PORT)."
  exit 1
fi

URL="http://localhost:$PORT"
if [ -d "/Applications/Google Chrome.app" ]; then open -a "Google Chrome" "$URL"; else open "$URL"; fi
cat <<MSG

The Finder is running at $URL

Last step, install it as an app:
  Chrome:  click the install icon at the right of the address bar
           (or ⋮ menu → Cast, save and share → Install page as app…)
  Safari:  File → Add to Dock

It then lives in your Dock, Launchpad and Cmd+Tab like any other app.
MSG
if [ -n "$REPO" ]; then
  echo "Auto-update is on: new versions pushed to the repo arrive within about 2 minutes."
  echo "If the app is open when one lands, it reloads itself as soon as you're not in the middle of something."
else
  echo "Tip: install from a Git repo to get automatic updates (see README: Automatic updates)."
fi
