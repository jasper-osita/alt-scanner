# The Finder (Crypto Coins Screener)

Binance altcoin scanner: day trade, swing and AOTS boards, model setups (NBB, Bounce/OEZ, Fade, Breaker/Flip,
V-Trade, Pullback, ORB, AMD), a daily playbook, filters with templates, and a suggested play per coin.

A static, installable web app (PWA). No build step, no server, no API keys.

Also includes: session picks (the best 3 coins to day trade in Asia, London and New York), a position size calculator (your risk rules and the ⅓-to-liquidation leverage check), a mini chart per coin
(EMA 20/50/100 with the setup's zone, entry, stop and targets), a watchlist with notes, price and setup alerts
(while the app is open), and a scorecard that tracks every scan's picks and checks whether they hit target or stop.

## Trend Starting: AOTS and the stages before it

AOTS (alignment of the stars) is price beyond the 20, 50 and 100 with the three stacked. The scanner follows a turn through four stages on the 4H and 1H:

| Stage | What it means | Where it shows |
|---|---|---|
| Coiling | 20/50/100 squeezed inside 1.5 ATR, the last 20 candles inside 4 ATR, ATR below 90% of normal, price on the 20's side and the 20 flat or turning | On deck, Pre-AOTS tab |
| Reclaiming | Was beyond all three the other way in the last 60 candles, now 2+ closes back over the 20 and the 50, the 20 turning, within 1.5 ATR of the break level | On deck (ranked first), Pre-AOTS tab, Suggested Play |
| Breaking out | Closed beyond all three and cleared the prior 20-candle range | Trend Starting board |
| Fresh AOTS | The 20/50/100 stacked for 12 candles or fewer | Trend Starting board |

The break level is the furthest MA or the 20-candle base high (low for shorts), whichever is further; "To the Break" shows the distance in ATR and %.
When a coin that was Reclaiming turns into Breaking out or Fresh AOTS, a Breakouts alert fires. Past 12 candles stacked the trend is established and drops off.

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

## Forex, metals & indices: Overview and Momentum Board
The sidebar's Forex · Metals · Indices group has its own Overview, Momentum Board and All Instruments pages, read from
the same instruments as the Forex, Gold & Indices page (MEXC's perps when the exchange is MEXC, otherwise Binance TradFi,
plus your cTrader pairs when connected; where both list the same market, the cTrader price is used).
- **Overview**: market hours in your time (forex, Tokyo, Hong Kong, Seoul, London, New York, CME futures; holidays not
  included), market status (US risk tone from the S&P 500 and Nasdaq 4H + Daily stacks, the dollar against the other
  currencies, gold, oil, 4H breadth, strongest and weakest currency, VIX via UVXY on Binance), top gainers and losers,
  and a Money Flow card: risk-on / risk-off / mixed over the last 7 days with the checks behind it (stocks, the yen and
  franc, gold, volatility), themes such as dollar bid or commodities bid, 24h / 7d / 30d averages per asset class,
  currency strength, and the week's leaders and laggards.
- **Momentum Board**: the coin board's three stages (in momentum, awaiting momentum, breaking out) on 1H with 4H as
  context, with the same breakout alerts.

## NBB Watch (Gold M5, Nasdaq M1)
Sidebar → Forex · Metals · Indices → NBB Watch. Watches the next-base breakout on your trading timeframes, by default Gold on
M5 through London (12–6 PM) and the Nasdaq 100 on M1 at the US open (9:30–11 PM, your cutoff). Candles come from your cTrader
broker when connected (MEXC or Binance otherwise), closed candles only. Each card shows the session, the live price and the
time to the candle close, and the state: basing (with the long and short trigger levels), triggered (entry at the breakout
close, stop beyond the far side of the base, 3R, with checks: with the timeframe's trend, with the higher timeframe, base
swept first, room to 2R, no high-impact news near), or missed. With cTrader connected it shows the lot size for your risk %.
Today's triggers are logged with how they've done since (3R hit, stopped, or open R). Alerts fire inside the session (or
always, with "Outside sessions too"); "Alert when a base forms" is optional. Edit watch list adds any forex pair, metal, index
or oil, on 1m to 1H, with your own session times. It is a watcher, not a trade gate: check the chart before acting.

## Economic calendar
Sidebar → Market → Calendar.
- **Forex Factory**: this week's calendar from Forex Factory's feed (read through the Mac app's relay or Vercel), with the same
  filter as forexfactory.com: impact, event types, currencies and default view, plus reminders a set number of minutes before
  events in your filter (high impact by default). The free feed covers the current week only and has no actual results;
  this device keeps past weeks so Last Week fills in over time.
- **What moves the Nasdaq**: US data from Forex Factory (CPI, jobs, ISM, retail sales, GDP and so on), the Fed (meetings with
  projections, Powell and other speakers, blackout periods), earnings of the Nasdaq-100 heavyweights from Nasdaq.com's
  calendar (Apple, Microsoft, Nvidia, Amazon, Alphabet, Meta, Broadcom, Tesla, Netflix, Costco as high impact), monthly
  options expiry, quad witching and the Nasdaq-100 rebalance, VIX expiry, and US market holidays and early closes. Fed dates
  are the Fed's published schedule (2027 tentative); expiries and holidays follow the exchange rules (one-off closures aren't
  included).
The NBB Watch cards warn when high-impact news for the market's currencies is within an hour.

## Phone alerts (Telegram)
The bell drawer's 📱 Phone button (or NBB Watch → Phone alerts): create a bot with @BotFather, send it a message, paste the
token, press Find my chat ID, then Send test. Pick which alerts go to your phone (NBB Watch, news reminders, setups and price
alerts are on; breakouts, bots and system messages start off). The token stays in that browser only, so set it up on the Mac
app to avoid getting every alert twice. On the Mac app, "Keep this Mac awake during my NBB Watch sessions" asks the local server
to run macOS's `caffeinate` while a session is on (the Mac still sleeps if you close the lid on battery).

## Cloud watcher (alerts while the Mac is off)
A GitHub Actions job (`.github/workflows/cloud-watch.yml`) runs `cloud/watch.mjs` every 5 minutes with the app's own NBB rules
on MEXC's Gold and Nasdaq perpetuals during your sessions, and sends Telegram reminders before high-impact news. It can't use
cTrader (your login never leaves your browser), so prices can differ a little from your broker's, and GitHub's schedule often
runs a few minutes late, which matters most on M1. To turn it on, in the GitHub repo: Settings → Secrets and variables →
Actions → add the secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, and under Variables add `CLOUD_WATCH` = `on`. Markets,
sessions and news settings are in `cloud/watch.json`. Its messages start with ☁️; if the Mac app is also sending, you'll
see both.

## Position size from your broker account
With cTrader connected, the coin pop-up's Size tab on a broker market (and NBB Watch triggers) sizes in lots from your real
balance (read-only), your risk %, the entry and stop, and the contract size and volume step your broker uses, converting the
profit currency to your account currency with your broker's forex prices.

## Trade page (cTrader and MEXC futures)

My Trading → **Trade**, or **Trade** on any coin or market pop-up. One ticket for both venues: forex, metals and indices go to cTrader,
coins go to MEXC USDT perpetuals.

- **Ticket:** buy or sell, market / limit / stop (MEXC: market or limit), stop loss, take profit, size in lots (cTrader) or contracts (MEXC).
  **Size it** turns a risk % of the account into a size from your stop. The button refuses a stop or target on the wrong side.
  With confirmation on (Trade settings), every order needs a second click.
- **cTrader:** uses your cTrader sign-in, which needs *trading access* (Trade settings → Sign in with trading access). It trades a
  **demo account by default**; live accounts stay greyed out until you tick "Allow live accounts" and type LIVE. Market orders carry the
  stop and target as distances from the fill; limit and stop orders carry the exact prices.
- **MEXC:** add an API key with Order Placing and view permissions only (never withdrawals). The key and secret stay in the browser
  and every request is signed there; the Mac app (`/proxy/mexc-priv`) or Vercel only forwards the signed request.
- **From the chart:** draw a Long or Short position (the forecast tools). Its label shows the size from your trading account and
  risk % (the tool's own Risk % setting, or the Trade page's when left empty), and the stop/target in money. Select it and press
  **Trade** (or More → Place order…): blue (entry), red (stop) and green (target) order lines appear across the chart and a small
  order panel opens beside it. Drag any line, or its label, to move that level; the size follows the risk %. Pick market, limit at
  the entry or stop at the entry, and place it. Esc or Cancel closes it.
  In the tool's settings, **Account size** is *Sync with account* by default (the cTrader balance, or MEXC futures equity, re-read
  every 30 s) or *Manual* (type an amount). The risk % stays as set; moving the entry or stop changes only the lots/contracts.
- **Your positions and orders on the chart:** open positions (entry with size and live P&L, SL, TP) and pending orders
  (dashed, with their SL/TP) for the chart's market, from cTrader or MEXC. The × beside the entry closes the position or cancels
  the order (asks once when “confirm” is on). Drag a cTrader line to change it at the broker when you let go: a pending order's
  price (its SL/TP move with it), any SL or TP, or a position's own line to add a stop loss (towards the loss) or take profit.
  Colours, the ×, dragging and the trade watch are under chart Settings → Trading.
- **Trade watch** (under the charts): Positions, Orders and History tabs with balance, equity and P&L; Close/Cancel per row;
  “Columns” picks what shows (saved); click a header to sort; drag the top edge to resize; double-click a row to open its chart.
  History reads cTrader closed deals (today to 1 year) and MEXC position history.
- **Long or short follows the stop:** drag the stop to the other side of the entry and the position flips (Long ↔ Short),
  keeping its reward:risk; an open order panel switches between Buy and Sell with it.
- **Lock reward : risk** (position settings or the order panel): Off, 1:1, 1:2, 1:3 or any ratio. While locked, moving the
  stop or entry moves the target to keep the ratio; dragging the target picks a new ratio in 0.5R steps. Locked targets show 🔒.
- **Account picker (chart toolbar, right end):** shows the account that sizes and places orders for the chart's market
  (cTrader for forex/metals/indices, MEXC futures for crypto). Click it to switch cTrader accounts (live ones only after
  “Allow live” in Trade settings), to sign in with trading access when your sign-in only reads prices, or to open Trade settings.
  "Open in ticket" copies it to the Trade page instead.
- **Positions & orders:** live P&L, edit the stop/target of a cTrader position, close positions and cancel pending orders
  (each asks "Sure?" first). Activity lists what was sent and what came back.

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
Switch between **Binance**, **Bybit** and **MEXC** with the Exchange pill. Every board, filter, model, chart, alert and scorecard
works on either. Bybit's positioning data has open interest, funding and the accounts long/short ratio (Bybit doesn't
publish taker flow or a top-trader ratio). If Bybit refuses requests made directly from the page, the Mac app's local
server relays Bybit's public market data (read-only `/v5/market/*` paths only), so open the scanner from the Mac app.

**MEXC** is the third choice. Futures use MEXC's contract API (with a live stream for prices, funding and candles); spot
uses MEXC's v3 API and has no live stream here, so spot prices refresh on each scan and alerts check every 30 seconds.
MEXC publishes funding and current open interest; the app builds its missing 3m and 2h candles from 1m and 1h. If MEXC refuses requests
made directly from the page, the Mac app relays its public market data (read-only contract and v3 market paths only).

MEXC also lists its own 24/7 perpetuals on forex (EUR, GBP, AUD, JPY, CAD, CHF, TRY, BRL against USDT), metals (gold, silver,
platinum, palladium, copper and industrial metals), energy (WTI, Brent, natural gas), indices (Nasdaq 100, S&P 500, Dow, Nikkei,
Hang Seng, KOSPI) and 400+ stocks. With the exchange set to MEXC, the Forex, Gold & Indices page reads these instead of Binance's
TradFi perps (no cTrader needed), the Charts page lists them (stocks under Stocks), and the backtest picker offers them. The crypto
scan skips them. MEXC allows about 20 requests per 2 seconds, so the app paces its MEXC calls (starting fast and easing off
when MEXC refuses) and reads each coin's 1H and 4H from one download: a MEXC scan takes about a minute and a half, and contracts
under $1M of 24h volume are skipped.

**"Why it's moving" is complete on every exchange.** Open interest and its change, top-trader and all-account long/short, taker
buy/sell flow and funding: each exchange's own numbers come first (Binance has all of them; Bybit has open interest, accounts
long/short and funding; MEXC has open interest and funding), and anything missing is filled from Binance futures for the same coin
(spot scans take taker flow from Binance spot). The panel says which numbers came from where. Every chart timeframe works on every
exchange.

**Charts page: indicators and drawing tools, TradingView-style.** The **Indicators** button (or `/`) opens a searchable list:
moving averages (EMA, SMA, WMA, RMA, Hull, VWMA, DEMA, TEMA, and the scanner's 20/50/100 stack), Bollinger, Keltner, Donchian,
VWAP, Ichimoku, Parabolic SAR, Supertrend, Volume, RSI, MACD, Stochastic, Stochastic RSI, ATR, ADX/DMI, CCI, OBV, Williams %R,
MFI, Rate of Change, Sessions, time-of-day lines, previous day/week/month highs and lows, pivot points and multi-timeframe fair value
gaps. Star the ones you use for a Favorites list. Each one has a legend on the chart (hide, ⚙ settings, remove); settings have
Inputs, Style (colours, widths, line styles, levels, fills) and Visibility (which timeframes) tabs, previewed live, with Defaults
and Cancel. Oscillators stack in their own panes under the price. The drawing toolbar follows TradingView's groups (lines,
channels and pitchforks; Fibonacci and Gann; patterns and Elliott waves; positions, anchored VWAP, volume profile and measurers;
brushes, arrows and shapes; text and notes; icons) with a flyout per group, stars for a favorites bar, and ⌥T, ⌥H, ⌥J, ⌥V, ⌥C,
⌥F and ⌥⇧R shortcuts. Select a drawing for its floating toolbar (colour, fill, text colour, width, style, settings, lock, delete,
clone, order) or double-click it for settings: Style, Text, Coordinates and Visibility, with "save as default". Also: magnet
(weak or strong), stay in drawing mode, lock, hide, remove, undo and redo, ⌘-drag to clone, and ⌘C / ⌘V.

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
