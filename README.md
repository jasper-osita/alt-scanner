# Alt Scanner (Crypto Coins Screener)

Binance altcoin scanner: day trade, swing and AOTS boards, model setups (NBB, Bounce/OEZ, Fade, Breaker/Flip,
V-Trade, Pullback, ORB, AMD), a daily playbook, filters with templates, and a suggested play per coin.

A static, installable web app (PWA). No build step, no server, no API keys.

Also includes: session picks (the best 3 coins to day trade in Asia, London and New York), a position size calculator (your risk rules and the ⅓-to-liquidation leverage check), a mini chart per coin
(EMA 20/50/100 with the setup's zone, entry, stop and targets), a watchlist with notes, price and setup alerts
(while the app is open), and a scorecard that tracks every scan's picks and checks whether they hit target or stop.

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
