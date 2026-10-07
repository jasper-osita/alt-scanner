#!/bin/bash
# Stamps a new version so every installed copy notices the update and refreshes itself.
# Run before committing a change:   bash bump-version.sh
set -euo pipefail
cd "$(dirname "$0")"
V="$(date +%Y.%m.%d.%H%M)"
python3 - "$V" << 'PY'
import sys, re, json
v = sys.argv[1]
s = open("index.html").read()
s = re.sub(r'const APP_VERSION = "[^"]+";', f'const APP_VERSION = "{v}";', s); open("index.html", "w").write(s)
json.dump({"version": v}, open("version.json", "w"))
w = open("sw.js").read()
w = re.sub(r'const SHELL = "[a-z-]+-shell-[^"]+";', f'const SHELL = "the-finder-shell-{v}";', w); open("sw.js", "w").write(w)
print("Version", v)
PY
