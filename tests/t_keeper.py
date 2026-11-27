"""The shared cTrader login keeper (api/ct-keeper.js): runs tests/keeper_test.mjs under Node with a fake Redis and token service."""
import subprocess, os
here = os.path.dirname(os.path.abspath(__file__))
p = subprocess.run(["node", os.path.join(here, "keeper_test.mjs")], capture_output=True, text=True, timeout=120)
out = (p.stdout + p.stderr).strip()
print(out)
bad = [l for l in out.splitlines() if not l.startswith("ok ")]
print("errors:", bad if bad else "none")
