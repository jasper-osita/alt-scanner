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
  Cache (IndexedDB `finder-cache`, `SC`): `scShow` draws the last scan for these settings on open (`data.cached`: alerts, bot and history skip it),
  `scSave` stores each fresh one; during a scan `klines` keeps closed candles and fetches only new ones (`klinesNet` is the real fetch, `klFlush` saves).
- cTrader markets: `FX_PAIRS` (28, group "Forex": the strength meter), `FX_MORE` (USD/CNH, SEK, NOK, MXN, ZAR, SGD: group "Other Forex", counted in the dollar's
  lean and movers, not the meter), `CT_CFD` (metals, energy, indices, dollar index, grains and softs in group "Commodities"; aliases are full names only).
- cTrader: `ctKlines(sym, tf, limit, keepForming, toMs)`, `ctAccountInfo`, `ctSpec`, `ctLots`, `CT_PERIOD/CT_MS/CT_SPAN`, `ctPrefer`, `ctEquiv`.
  Staying connected: `ctSignIn`/`ctOAuthReturn` (OAuth; token swap direct, or via `/api/ct-token`: server.py on the Mac, `api/ct-token.js` on Vercel), `ctRenew` (2173), `ctScheduleReconnect`, `ctResubscribe`.
- Charts: `CHP` panes, `chLoad`, `chSetData`, `chLoadOlder` (history on scroll, max 5000), `chPaint`, `chIndPaint`, `IND` registry,
  `chIndBuild/Layout/Sync`, dialog mode `CHDLG`/`chDlgStart`, settings `CS_DEF`/`chCS()`.
  Comparison indicators `cmp` (another market over the chart on its own scale, `ownScale`) and `ratio` (pane): `chCmpSym` (typed name → symbol), `chCmpData` (cache `CHCMP`), `chCmpLine`.
  Overview main charts borrow the same engine: `OVC`, `ovcHost`/`ovcPark` (Bitcoin on Overview; dollar + Nasdaq 100 side by side on the
  forex overview, each pane its own symbol via `P.psym`/`chPS(P)`; the Charts page's own state is restored on park).
  Forex overview toggles: session timeframes `ovcSessTf`/`ovcSessApply` (NAS100 1m at the US open, Gold 5m in London), same timeframe `ovcTfPicked`.
- Day range used (core, also in Node): `adrOf` (14-day average high−low), `dayRange` (closed candles since the current daily candle opened) and `dayUsed` (+ live price);
  `r.day` on every scanned row, `dayTag` on forex/momentum rows, `nwDay` on NBB Watch cards, checklist and alerts. Currency strength window
  `XCS` (Session/24h/7d) in Money Flow: `xSessStart` (latest of Asia 8 AM, London 12 PM, New York 9:30 PM PHT), `xSessRet` from `r.opens` (15m opens, forex/metals/indices rows only).
- Pair Picker page (`macropair`): `PP_GROUPS` (legs in cross order, ±1 = how each prices the other side in the shared one), `ppGroups` → per group the shared side's lean
  `ppLean` (dollar index + every pair with that currency, or the legs' own trend), which leg is stronger (cross/ratio from `r.c1`/`r.c4` closes via `ppAlign`:
  session + 24h change, 20/50/100 stack `ppStack`), `ppCorr` (hourly, ~5 days) and the pick; `ppCardHTML`, `renderPP`. Test: `t_pair` (synthetic rows with known answers).
- Trade page (`<script id="trade">`): cTrader trading on its own socket `CTT` (`cttConnect`, `cttPlace` 2106, reconcile 2124, close 2111,
  amend 2110, cancel 2108, P&L 2187; demo by default, live needs "Allow live" + typing LIVE); chart account picker `trAcctPop`/`trAcctChip`, position sizing `trSizeCalc`/`trPosSize` (Sync or Manual account size); MEXC futures `mxtReq` (HMAC signed in the
  browser, forwarded by `/proxy/mexc-priv`: server.py or a Vercel rewrite), `mxtPlace`.
  Quick trade on the chart (`QT`, toolbar "Quick trade"): `qtLevels` (entry/SL/TP per side), `qtLines` (dashed preview lines, drawn by
  `trChartLines`), `qtDrop` (dragged entry → limit/stop, 2-tick snap to market), `qtPlace` (→ `cttPlace`/`mxtPlace`).
  MEXC auto leverage `mxtLev` (lowest under the margin cap `levCap`%, liquidation ≥ `levBuf`× the stop, isolated; UI `mxtLevUi`). The chart order panel docks right of the charts (`.chbody.trdock`).
- Bot Simulator: filters `BOTF`/`botMatch`, trade review `botReviewHTML`; clicking a closed trade or an open position (`botOpenStudy`) → `chStudy` marks it cTrader style (`chTradeMarks`, state `CHM`; the menu switch `BOTF.chart` → `chBotTrades`) with a docked study panel (notes in `altscan-bot-notes`); a trade watch row → `twShow` (mark only, `CHM.tw`). The Bot Simulator is also an account in the chart account menu (`twBots`, `TWS().bots`): the trade watch then lists `twBotRows`. Never place real orders in tests; mocks only.
- Fundamentals page (`fund`, terminal style): "Today's read" on top (`fundSignals` → `fundCardsData`: Gold, Silver, Nasdaq, dollar, EUR/USD, USD/JPY, Oil, Bitcoin tailwind/headwind with reasons; a card shows its top 3 reasons and 2 warnings), live ticks `fundLive`; `fundLoad` → `fundUST` (Treasury curves via /proxy/ust), `fundCOT` (CFTC via /proxy/cot), `fundFRED` (via /proxy/fred; the relay adds its own key: Vercel env FRED_API_KEY in `api/fred.js`, Mac `~/.finder-fred-key`; a key pasted in the panel, `finder-fred`, wins), `fundBIS` (policy rates for BoE/BoJ/RBA/BoC/SNB/RBNZ, daily; OECD monthly via FRED only as fallback) and `fundYields` (euro-area and Japan 2Y/10Y → `fundGaps`: US minus them), both via /proxy/rates/<bis|ecb|jgb|jgb-all> (server.py `RATE_SRC`, Vercel `api/rates.js`), `fundNews` (RSS via /proxy/rss/<name>); relays in server.py `relay_fund` and vercel.json rewrites.
  Extra FRED series `FUND_MORE` (add new ones to the allow-lists in server.py `FRED_SERIES` and `api/fred.js` too): `fundRank` (gold/oil volatility vs its own year),
  `fundBroad` (Fed broad dollar), `fundLiq` (balance sheet − Treasury cash − reverse repo, $bn), `fundCuts` (rough Fed cuts priced: 2×1Y − 6M yield vs the effective rate).
  Seasonality `fundSeas` (cTrader monthly candles `ctKlines(sym, "1M", …)`, MN1 = period 14, 5 years a request, up to 20 years; `seasStats`, panel `fundSeasHTML`, card line `seasLine`).
  `COT_MK` [name, CFTC code, group] (a new code refetches the cache); hedge-fund column `fundCOTFunds` (leveraged funds from /proxy/cot-tff for currencies, indices,
  Bitcoin; managed money from /proxy/cot-dis for commodities; fields found by name, falls back to all columns for recent weeks if a $select column is refused); World markets ratios `fRatio` (Gold ÷ Silver, Copper ÷ Gold) and `fGoldIn` (gold in euros and yen;
  the Gold card warns "mostly the dollar" when gold moves in dollars but not in euros).
- Calendar: List / Week / Month views (`CALV`, `calGrid`, `calGridRange`), `ffNorm`, `usMarketEvents`, `FOMC_DATES`, `earnImpact`.
  Actuals for main US releases from FRED: `CAL_ACT` (title → series, how, months back, dollar sign, kind), `calActual`, `calActFetch` (each series at most every 10 min;
  new series go in the FRED allow-lists too), `calLastSurprise` → "Today's read" header and card line `surLine`. Alerts: `ncAdd` (wrapped to forward to Telegram), `NC_KINDS`.

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
