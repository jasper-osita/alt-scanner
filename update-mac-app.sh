#!/bin/bash
# Pulls the newest Alt Scanner from its Git repo. Runs automatically at login and every 30 minutes.
SITE="$HOME/Library/Application Support/AltScanner/site"
cd "$SITE" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
OLD="$(git rev-parse HEAD)"
git fetch --quiet origin || { echo "$(date '+%F %T') fetch failed (offline?)"; exit 0; }
git reset --hard --quiet "@{upstream}" || exit 0
NEW="$(git rev-parse HEAD)"
if [ "$OLD" != "$NEW" ]; then
  echo "$(date '+%F %T') updated $(git log -1 --format=%h) $(cat version.json 2>/dev/null)"
  # the app picks up new files on its own; only a change to the local server needs a restart
  if git diff --name-only "$OLD" "$NEW" | grep -q '^server.py$'; then
    launchctl kickstart -k "gui/$(id -u)/com.jas.altscanner" >/dev/null 2>&1 || true
  fi
fi
