# Alt Scanner (Crypto Coins Screener)

Binance altcoin scanner: day trade, swing and AOTS boards, model setups (NBB, Bounce/OEZ, Fade, Breaker/Flip,
V-Trade, Pullback, ORB, AMD), a daily playbook, filters with templates, and a suggested play per coin.

A static, installable web app (PWA). No build step, no server, no API keys.

Also includes: session picks (the best 3 coins to day trade in Asia, London and New York), a position size calculator (your risk rules and the ⅓-to-liquidation leverage check), a mini chart per coin
(EMA 20/50/100 with the setup's zone, entry, stop and targets), a watchlist with notes, price and setup alerts
(while the app is open), and a scorecard that tracks every scan's picks and checks whether they hit target or stop.

## Momentum Board
Three 1H columns, with 4H shown as context ("4H agrees" = 4H RSI 50+ and price above the 4H 20, for longs):
🔥 **In Momentum**: RSI 70+ with price beyond all three MAs. ⏳ **Awaiting Momentum**: RSI tapped 70 in the last 12 hours,
cooled to 55–70, still holding the 20. 🚀 **Breaking Out**: the first candle that closes clear of bunched 20/50/100 (within
1.5 ATR) with RSI 60+, after at least 15 of the prior 48 hours on the other side (a new trend, not a continuation); "Pressing"
= testing the cluster with RSI rising. Shorts mirror everything (RSI 30, breakdowns) and follow the Direction switch. Coins 3+
ATR from the 20 are flagged "Stretched: don't chase", weak-volume breaks are flagged, and wicky coins follow the Wicks setting.
New breakouts trigger an alert while the app is open. The **Ignition** model (breakout in the last 2 candles, RSI 60+, 1.5×
volume, not stretched; stop beyond the breakout low and the cluster, target 2R) is in the Model Guide, backtest and bots.

## Money Flow (rotation, measured)
Reads where money is actually going over the last 30 days instead of assuming the BTC → ETH → large caps → altseason
story. It compares BTC, ETH (and the ETH/BTC daily trend), and the median 30-day return of large caps (top 20 alts by
CoinGecko market cap), mid caps (21–100), small caps and memes, plus how many alts are beating BTC. A phase is called only
when its checks pass (shown with ✓/✗), alongside what would prove it wrong and what would confirm the next step; otherwise
it says "No clear rotation", or "Risk-off" when everything is falling. Every coin is tagged Leader, Turning, In line,
Holding up, Fading or Laggard against BTC. Laggards are never treated as "next": long plays on them carry a caution,
leaders rank higher, and the backtest's Model × Strength vs BTC view tests whether that holds on real history.

## RSI and momentum
RSI (14) on 1H, 4H and Daily for every coin, with your zones (70+ momentum, 60–70 pre-momentum, 30–40 pre-weak, 30 or
below weak), divergence and ignition (a fresh cross of 60 or 40). The Momentum score (0–100) blends RSI alignment, volume
now, strength vs BTC and range expansion. Use the Momentum tab, the RSI filter, and the Strong Momentum, Momentum Ignition,
RSI Divergence and RSI Reset in Uptrend views. The coin chart has an RSI pane, suggested plays warn about divergence or a
stretched RSI, and the backtest's Model × RSI at Entry view shows whether high-momentum entries pay.

## Bot simulator (forward test)
Paper-trades every strategy (NBB, Bounce, Fade, Breaker, V-Trade, Pullback, plus Claude's Leader Pullback and Daily 20
Reset; ORB and AMD excluded) on live prices, each in its own account. Set the account size, risk %, max open positions,
fees and slippage, press Start Bots, and compare balances, win rates, R, drawdowns and equity curves. The bots trade while
the app is open; on reopen they settle stops and targets hit while it was closed (using 15m candles).

## Claude's setups
**Leader Pullback (day, 1H):** a fresh 48h high on a big, high-volume impulse; a quiet pullback into the 1H 20 or the 38% of
the leg that holds the 50 and gives back ≤ 62%; a reclaim candle. Stop below the pullback low, target 2R.
**Daily 20 Reset (swing, 4H + Daily):** in a Daily uptrend with a rising 20, price resets into the Daily 20 zone (closing
below the 4H 20 at least twice), then a 4H candle reclaims the 20. Stop below the reset low, target 3R, up to 10 days.
Both run long and short and are hypotheses until the backtest and the bots prove them.

## Model backtest
The Model Backtest card replays every model on the last 30, 60 or 90 days of real candles for your top coins
(plus your watchlist) and shows which models pay, by model, session, environment, direction and coin, with an equity
curve. No look-ahead: at each candle the detectors only see candles that had closed. Trades run to the stop, the target
or 48 hours (ORB and AMD on 15m candles with the 11:00 NY close); same-candle stop and target counts as a stop; fees
come off every trade. With "Use results in the playbook" on, a model that loses in an environment (≤ −0.10R over 15+
trades) is moved to Avoid there, and one that pays (≥ +0.25R) is promoted. Results are saved in your browser.

## Live data
The **● Live** badge in the header shows the live stream. While it's live, prices, 24h change and funding update in real
time, the coin chart's current candle moves as it forms, price alerts fire instantly, and at every 1H candle close the
coins that matter (watchlist, board picks, session picks, playbook setups) are re-checked; during the NY window the
15m closes re-check ORB and AMD. Click the badge to pause or resume. If your network blocks the stream, the badge
shows "Live off: polling" and alerts fall back to checking every 30 seconds.

## Exchanges
Switch between **Binance** and **Bybit** with the Exchange pill. Every board, filter, model, chart, alert and scorecard
works on either. Bybit's positioning data has open interest, funding and the accounts long/short ratio (Bybit doesn't
publish taker flow or a top-trader ratio). If Bybit refuses requests made directly from the page, the Mac app's local
server relays Bybit's public market data (read-only `/v5/market/*` paths only), so open the scanner from the Mac app.

## How it works
- The page is served by your host (Vercel, Netlify, Cloudflare Pages).
- **Market data is fetched by your browser**, straight from Binance, CoinGecko and alternative.me.
  This is deliberate: Binance blocks its API for US server locations, where most hosts run,
  so a server-side proxy would break. Your browser on your network already reaches Binance.
- Filters, templates, settings, watchlist, alerts and scorecard history are saved in each browser (localStorage), per device.

## Install it on your Mac (as an app in your Dock)

**Option 1: from your Vercel URL (recommended).** Deploy (below), open the URL in Chrome and click the install icon at the
right of the address bar (or ⋮ → Cast, save and share → Install page as app…). In Safari: File → Add to Dock.
Updates arrive automatically when you redeploy.

**Option 2: no hosting.** In Terminal, from this folder:
```bash
bash install-mac-app.sh
```
It copies the app to `~/Library/Application Support/AltScanner`, serves it at `http://localhost:8787`
(reachable from this Mac only), starts that server at every login, and opens the page. Then click Install in Chrome
(or File → Add to Dock in Safari). To update, unzip the new version and run the script again.
Remove with `bash uninstall-mac-app.sh`. Needs Python 3 (from Apple's Command Line Tools: `xcode-select --install`).

Your watchlist, alerts and scorecard are stored per address, so the Vercel app and the localhost app keep separate data.

## Automatic updates (one-time setup, about 5 minutes)

After this, you never install updates yourself: open the app and it's already on the newest version.

1. **Put this folder in a GitHub repo.** Easiest with Claude Code, from inside `alt-scanner-app`:
   > Create a GitHub repo called alt-scanner for this folder and push it.

   Or by hand: `git init && git add -A && git commit -m "Alt Scanner" && gh repo create alt-scanner --public --source=. --push`.
   Public is simplest: the code holds no secrets (your watchlist, alerts and scorecard live only in your browser).
   For a private repo, run `gh auth login` and `gh auth setup-git` once so the updater can pull.
2. **Install from the repo:** run `bash install-mac-app.sh` from inside that Git clone (or pass the repo URL as an argument).
   This turns on auto-update: your Mac pulls new versions at login and every 30 minutes.
3. **Optional, for your phone:** vercel.com → Add New → Project → import the repo. Every push redeploys within a minute.

**How an update reaches you:** the change is committed with `bash bump-version.sh` and pushed → your Mac pulls it within
about 2 minutes (Vercel within a minute) → the next time you open the app it's the new version. If the app is already open,
it reloads itself as soon as you're not in the middle of something (otherwise it shows a "Reload now" banner).

**Applying an update from a Claude chat:** download the zip, then tell Claude Code:
> Replace my alt-scanner repo's files with the contents of ~/Downloads/alt-scanner-app.zip (keep .git), run bump-version.sh, commit and push.

The footer shows which version you're running.

## Deploy to Vercel (pick one)

**A. CLI (fastest)**
```bash
npm i -g vercel        # once
cd alt-scanner-app
vercel                 # first deploy: accept the defaults (no framework, no build command)
vercel --prod          # promote to your production URL
```

**B. GitHub (auto-deploys on every push)**
1. Push this folder to a new GitHub repo.
2. vercel.com → Add New → Project → import the repo.
3. Framework preset: **Other**. Build command: none. Output directory: `.` (root). Deploy.

## Other hosts
- **Netlify:** drag the folder onto app.netlify.com/drop. Copy the headers from `vercel.json` into a `_headers` file if you want the same security headers.
- **Cloudflare Pages:** create a project, upload the folder, no build command.

## Install on your phone
- **iPhone:** open the URL in Safari → Share → Add to Home Screen.
- **Android:** Chrome → menu → Install app.

## Files
| File | Purpose |
|---|---|
| `index.html` | The whole app (UI + scanner engine) |
| `manifest.webmanifest`, `icons/` | Makes it installable with its own icon |
| `sw.js` | Keeps the app shell available offline; never caches market data |
| `lib/` | TradingView Lightweight Charts™ 4.2.3 (Apache 2.0), self-hosted so the strict CSP stays intact |
| `install-mac-app.sh`, `uninstall-mac-app.sh`, `server.py` | Mac install without hosting (local server on 127.0.0.1, starts at login) |
| `update-mac-app.sh`, `bump-version.sh`, `version.json` | Auto-update: the Mac updater, the version stamp helper, and the current version |
| `vercel.json` | Security headers (strict CSP that only allows the data sources above) and no-cache for updates |

## If a scan fails
"Couldn't reach Binance" means your network is blocking Binance. Switch DNS to 1.1.1.1 or 8.8.8.8, or use a VPN.
The app falls back to `data-api.binance.vision` (spot market data) automatically when only the futures API is blocked.

## Updating
Edit `index.html`, redeploy (`vercel --prod` or push to GitHub). The service worker fetches the new version first,
so a normal refresh picks it up.
