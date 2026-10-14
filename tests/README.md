# Tests

Browser tests for The Finder. Each one serves the app locally and drives it in Chromium, with Binance, Bybit, MEXC, cTrader,
Forex Factory, Nasdaq and Telegram all replaced by fakes (`mock.py`), so no network or accounts are needed.

```
pip install playwright && playwright install chromium
bash tests/runall.sh              # everything (about an hour)
bash tests/runall.sh t_nw t_cs    # just some
```

A test prints what it checked; any line with a Traceback or `errors: [...]` marks it as failed. Screenshots land in `tests/out/`.
Worth running before changing anything: `t_smoke`, `t_finder`, `t_charts`, `t_macro`, `t_xov`, `t_nw` and `t_mob` cover the main pages.
