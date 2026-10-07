#!/bin/bash
# Removes the Alt Scanner local server. Remove the app itself from Chrome (chrome://apps) or the Dock.
set -uo pipefail
LABEL="com.jas.altscanner"; PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || launchctl unload -w "$PLIST" >/dev/null 2>&1 || true
UPLIST="$HOME/Library/LaunchAgents/$LABEL.update.plist"
launchctl bootout "gui/$(id -u)" "$UPLIST" >/dev/null 2>&1 || launchctl unload -w "$UPLIST" >/dev/null 2>&1 || true
rm -f "$PLIST" "$UPLIST"
rm -rf "$HOME/Library/Application Support/AltScanner"
echo "The Finder's local server is removed. To remove the app icon: Chrome → chrome://apps → right-click → Remove, or drag it out of the Dock."
