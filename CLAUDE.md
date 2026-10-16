# The Finder — notes for Claude

Read this first. Keep answers and diffs tight; Jas architects, Claude executes.

## What it is
Single-page screener PWA for Jas (Philippines, PHT = UTC+8). Crypto boards (Binance/Bybit/MEXC), forex/metals/indices from his
Pepperstone cTrader account, a TradingView-style Charts engine, NBB Watch, economic calendar, alerts.
Trading scope: NBB setup; Gold M5 in London, NAS100 M1 at the US open; AOTS = price beyond 20/50/100 with them stacked.
Sessions (PHT): Asia 8–12, London 12–18, London lunch 18–19:30, Pre-NY 19:30–21:30, NY AM 21:30–24, NY PM 0–4.

## Files
- `index.html` (~850 KB, everything). Scripts in order: `<script id="core">` (DOM-free, also run by cloud/watch.mjs in Node),
  UI script, `<script id="charts">`, `<script id="extras">` (NBB Watch, calendar, Telegram, keep-awake), SW registration.
  Grep for the function you need and read only that range; never read the whole file.
- `server.py` local app on http://localhost:8787 (LaunchAgent, auto-pulls from GitHub). Relays: /proxy/ff, /proxy/earnings, /api/awake.
- `vercel.json` (CSP + rewrites), `sw.js` (skips /proxy, /api, version.json), `cloud/` (GitHub Actions watcher), `tests/`.

## Key code areas (grep these names)
- Scan: `structure`, `aots`, `preAots`, `preBest`, `coinPlay`, `renderBoards`, `TABS`, `testFilter`.
- cTrader: `ctKlines(sym, tf, limit, keepForming, toMs)`, `ctAccountInfo`, `ctSpec`, `ctLots`, `CT_PERIOD/CT_MS/CT_SPAN`, `ctPrefer`, `ctEquiv`.
  Staying connected: `ctSignIn`/`ctOAuthReturn` (OAuth; token swap direct, or via `/api/ct-token`: server.py on the Mac, `api/ct-token.js` on Vercel), `ctRenew` (2173), `ctScheduleReconnect`, `ctResubscribe`.
- Charts: `CHP` panes, `chLoad`, `chSetData`, `chLoadOlder` (history on scroll, max 5000), `chPaint`, `chIndPaint`, `IND` registry,
  `chIndBuild/Layout/Sync`, dialog mode `CHDLG`/`chDlgStart`, settings `CS_DEF`/`chCS()`.
  Overview main charts borrow the same engine: `OVC`, `ovcHost`/`ovcPark` (Bitcoin on Overview; dollar + Nasdaq 100 side by side on the
  forex overview, each pane its own symbol via `P.psym`/`chPS(P)`; the Charts page's own state is restored on park).
  Forex overview toggles: session timeframes `ovcSessTf`/`ovcSessApply` (NAS100 1m at the US open, Gold 5m in London), same timeframe `ovcTfPicked`.
- Trade page (`<script id="trade">`): cTrader trading on its own socket `CTT` (`cttConnect`, `cttPlace` 2106, reconcile 2124, close 2111,
  amend 2110, cancel 2108, P&L 2187; demo by default, live needs "Allow live" + typing LIVE); chart account picker `trAcctPop`/`trAcctChip`, position sizing `trSizeCalc`/`trPosSize` (Sync or Manual account size); MEXC futures `mxtReq` (HMAC signed in the
  browser, forwarded by `/proxy/mexc-priv`: server.py or a Vercel rewrite), `mxtPlace`.
  Quick trade on the chart (`QT`, toolbar "Quick trade"): `qtLevels` (entry/SL/TP per side), `qtLines` (dashed preview lines, drawn by
  `trChartLines`), `qtDrop` (dragged entry → limit/stop, 2-tick snap to market), `qtPlace` (→ `cttPlace`/`mxtPlace`).
  MEXC auto leverage `mxtLev` (lowest under the margin cap `levCap`%, liquidation ≥ `levBuf`× the stop, isolated; UI `mxtLevUi`). The chart order panel docks right of the charts (`.chbody.trdock`).
- Bot Simulator: filters `BOTF`/`botMatch`, trade review `botReviewHTML`; clicking a closed trade or an open position (`botOpenStudy`) → `chStudy` marks it cTrader style (`chMarkPaint`, state `CHM`) with a docked study panel (notes in `altscan-bot-notes`); a trade watch row → `twShow` (mark only, `CHM.tw`). Never place real orders in tests; mocks only.
- Calendar: `ffNorm`, `usMarketEvents`, `FOMC_DATES`, `earnImpact`. Alerts: `ncAdd` (wrapped to forward to Telegram), `NC_KINDS`.

## Workflow
- After changes: `TZ=Asia/Manila bash bump-version.sh` (updates version.json, index.html, sw.js).
- Tests: `bash tests/runall.sh t_smoke t_charts …` (Playwright + mocks in tests/mock.py, no network). Run only the ones
  that touch the change; the full suite takes about an hour. A test fails on a Traceback or `errors: [...]`.
  Prefer printed checks over screenshots; look at a screenshot only when layout is the question.
- Commit as Jas: `git -c user.email=jasperosita18@gmail.com -c user.name="Jasper Osita" commit`, message ends with the
  Co-Authored-By line. Claude pushes from the cloud clone (Claude GitHub App is installed on the repo).

## Rules
- Never put the cTrader Client ID/Secret/token or the Telegram bot token in code, commits or chat. They live only in the
  browser's localStorage (Connect cTrader dialog, `finder-telegram`). Cloud secrets are GitHub Actions secrets Jas adds himself.
- Plain-language UI copy, sentence case, no jargon without a hint.
