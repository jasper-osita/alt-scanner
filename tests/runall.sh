#!/bin/bash
# Runs every browser test against mocked exchanges (no network needed). Needs: Python 3, `pip install playwright`, `playwright install chromium`.
# Usage: bash tests/runall.sh            (all)      bash tests/runall.sh t_nw t_cs   (some)
cd "$(dirname "$0")" && mkdir -p out out/finder out/mob
TESTS=("$@"); [ ${#TESTS[@]} -eq 0 ] && TESTS=($(ls t_*.py | sed 's/\.py$//'))
fail=0
for t in "${TESTS[@]}"; do
  echo "===== $t"
  out=$(cd out && timeout 1300 python3 ../$t.py 2>&1 | grep -v "Failed to load resource\|TargetClosed\|^future:\|Future exception was never retrieved")
  echo "$out" | tail -25
  if echo "$out" | grep -qE "Traceback|errors: \[|^[A-Za-z_.]*Error:"; then echo "!!!!! $t FAILED"; fail=1; fi
done
exit $fail
