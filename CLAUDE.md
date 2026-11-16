# The Finder — notes for Claude

Read this first. Keep answers and diffs tight; Jas architects, Claude executes.

## What it is
Single-page screener PWA for Jas (Philippines, PHT = UTC+8). Crypto boards (Binance/Bybit/MEXC), forex/metals/indices from his
Pepperstone cTrader account, a TradingView-style Charts engine, economic calendar, alerts.
Trading scope: NBB setup; Gold M5 in London, NAS100 M1 at the US open; AOTS = price beyond 20/50/100 with them stacked.
Sessions (PHT): Asia 8–12, London 12–18, London lunch 18–19:30, Pre-NY 19:30–21:30, NY AM 21:30–24, NY PM 0–4.
These are New York based and written as in US summer time: from November to March (New York winter time) they all land 1 hour later in PHT.
Never compare session times with plain PHT: use the session clock in core (`sessD`/`sessH`, New York + 12h; `sessLbl` shows today's PHT; `nyDst`/`ukDst`, `CLK_SHIFT`). Test: `t_dst`.

## Files
- `index.html` (~850 KB, everything). Scripts in order: `<script id="core">` (DOM-free, also run by cloud/watch.mjs in Node),
  UI script, `<script id="charts">`, `<script id="extras">` (calendar, Telegram, Fundamentals, overview charts), SW registration.
  Grep for the function you need and read only that range; never read the whole file.
- `server.py` local app on http://localhost:8787 (LaunchAgent, auto-pulls from GitHub). Relays: /proxy/ff, /proxy/earnings.
- `vercel.json` (CSP + rewrites), `sw.js` (skips /proxy, /api, version.json), `cloud/` (GitHub Actions watcher), `tests/`.

## Key code areas (grep these names)
- Scan: `structure`, `aots`, `preAots`, `preBest`, `coinPlay`, `renderBoards`, `TABS`, `testFilter`.
  Cache (IndexedDB `finder-cache`, `SC`): `scShow` draws the last scan for these settings on open (`data.cached`: alerts skip it),
  `scSave` stores each fresh one; during a scan `klines` keeps closed candles and fetches only new ones (`klinesNet` is the real fetch, `klFlush` saves).
- cTrader markets: `FX_PAIRS` (28, group "Forex": the strength meter), `FX_MORE` (USD/CNH, SEK, NOK, MXN, ZAR, SGD: group "Other Forex", counted in the dollar's
  lean and movers, not the meter), `CT_CFD` (metals, energy, indices, dollar index, grains and softs in group "Commodities"; aliases are full names only).
- cTrader: `ctKlines(sym, tf, limit, keepForming, toMs)`, `ctAccountInfo`, `ctSpec`, `ctLots`, `CT_PERIOD/CT_MS/CT_SPAN`, `ctPrefer`, `ctEquiv`.
  Staying connected: `ctSignIn`/`ctOAuthReturn` (OAuth; token swap direct, or via `/api/ct-token`: server.py on the Mac, `api/ct-token.js` on Vercel), `ctRenew` (2173), `ctScheduleReconnect`, `ctResubscribe`.
  Shared login: `api/ct-keeper.js` (private Vercel Blob store `the-finder-keeper`, or Upstash Redis if connected; env `FINDER_PASS`; `GET /api/ct-keeper?check=1` = set-up check) holds and renews the one login; devices borrow it (`ctCfg().keeper`, no local refresh token): `ctKeeperSeed`/`ctKeeperJoin`/`ctKeeperPull(bad)`, dialog `ctShareHTML`; passphrase in `finder-keeper`. Tests `t_keeper`, `t_keeper_ui`.
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
- Trade watch: a row → `twShow` marks the trade cTrader style on the chart (`chTradeMarks`, state `CHM`, `chStudyGo`). Never place real orders in tests; mocks only.
- Model Guide (`renderGuide`, scanned `MODELS`): your own models `MYM` (localStorage `finder-my-models`; `renderMyGuide`, form `guideEdit`, `mymText` = Copy for Claude); the scanner doesn't look for them. Test: `t_guide`.
- Models: only NBB and V-Trade (`MODELS`, `detectModels`, A-grade `gradeModels`; Playbook switch "A-grade only" = `EDGE.aOnly`, `liveModels`).
- Removed on purpose (Nov 2026): Bot Simulator, NBB Watch (and its keep-awake and cloud NBB alerts), Session Picks, Scorecard,
  Backtest + Edge Finder, and every model except NBB and V-Trade (OB, Bounce, Fade, Breaker, Pullback, ORB, AMD, Leader, Daily 20 Reset, Ignition). Don't bring them back unasked.
- Fundamentals page (`fund`, terminal style): "Today's read" on top (`fundSignals` → `fundCardsData`: Gold, Silver, Nasdaq, dollar, EUR/USD, USD/JPY, Oil, Bitcoin tailwind/headwind with reasons; a card shows its top 3 reasons and 2 warnings), live ticks `fundLive`; `fundLoad` → `fundUST` (Treasury curves via /proxy/ust), `fundCOT` (CFTC via /proxy/cot), `fundFRED` (via /proxy/fred; the relay adds its own key: Vercel env FRED_API_KEY in `api/fred.js`, Mac `~/.finder-fred-key`; a key pasted in the panel, `finder-fred`, wins), `fundBIS` (policy rates for BoE/BoJ/RBA/BoC/SNB/RBNZ, daily; OECD monthly via FRED only as fallback) and `fundYields` (euro-area and Japan 2Y/10Y → `fundGaps`: US minus them), both via /proxy/rates/<bis|ecb|jgb|jgb-all> (server.py `RATE_SRC`, Vercel `api/rates.js`), `fundNews` (RSS via /proxy/rss/<name>); relays in server.py `relay_fund` and vercel.json rewrites.
  Extra FRED series `FUND_MORE` (add new ones to the allow-lists in server.py `FRED_SERIES` and `api/fred.js` too): `fundRank` (gold/oil volatility vs its own year),
  `fundBroad` (Fed broad dollar), `fundLiq` (balance sheet − Treasury cash − reverse repo, $bn), `fundCuts` (rough Fed cuts priced: 2×1Y − 6M yield vs the effective rate).
  EIA weekly stocks `fundEIA` (/proxy/eia?series=…: server.py `EIA_SERIES` + key from env EIA_API_KEY or `~/.finder-eia-key`, Vercel `api/eia.js` with env EIA_API_KEY;
  a key pasted in the panel, `finder-eia`, wins; failures retry after 10 min), `eiaRead` (level, week change, vs 5-year same week), Oil card line, calendar actuals via `CAL_ACT` "EIA:" ids.
  Seasonality `fundSeas` (cTrader monthly candles `ctKlines(sym, "1M", …)`, MN1 = period 14, 5 years a request, up to 20 years; `seasStats`, panel `fundSeasHTML`, card line `seasLine`).
  `COT_MK` [name, CFTC code, group] (a new code refetches the cache); hedge-fund column `fundCOTFunds` (leveraged funds from /proxy/cot-tff for currencies, indices,
  Bitcoin; managed money from /proxy/cot-dis for commodities; fields found by name, falls back to all columns for recent weeks if a $select column is refused); World markets ratios `fRatio` (Gold ÷ Silver, Copper ÷ Gold) and `fGoldIn` (gold in euros and yen;
  the Gold card warns "mostly the dollar" when gold moves in dollars but not in euros).
  Clicking a market opens the market brief (`<dialog id="fbDlg">`, `fbOpen(k, src, dir)`/`fbRender`/`fbClose`; grows out of the clicked row, sections fade up, `FB.hold` defers redraws during it; reduced motion = a fade), not the chart: registry `FB_MK`, lean rules `fbDrivers` (score ±2 = tailwind/headwind, `fbSay`/`fbTip`),
  levels from 1H candles `fbLevels`/`fbLvCalc` (US indices: 15m `fbUsLv`, overnight range, 4 PM close, open gap, first 15 min), `fbFedExp`, `fbStrength`, `fbEvents` (+ `fbEarn`), `fbNews`;
  sudden moves `fbSample` (every 2 s, live prices, alert via `ncAdd` for Gold and the Nasdaq 100); release read `rxTick` (market reaction 2 and 10 min after a high-impact release, history `finder-react`);
  headline alerts on any page `naCheck` (core `NEWS_TAGS`/`newsBig`, MACRO tag; alerts carry `action: "brief"`). Cloud watcher sends headlines too (`.github/workflows/cloud-watch.yml`). Test: `t_brief`.
  Central bank reads (no AI, free): core `CB_BANKS` (Fed/ECB/BoE/BoJ/RBA/BoC: decision list + statement markers), `cbItems`, `cbParse` (decision, rate, dissents), `cbDiff`, `cbVerdict`
  (surprise vs forecast ±3, dissents ±2, wording ±2 → Hawkish/Dovish; As expected, or No clear lean when the calendar has no forecast); UI `cbTick` (polls a bank 2 min before to 90 min after its high-impact decision, catch-up every 6 h), `cbRead`, `CBR`
  (`finder-cbreads`), `cbLean`, panel `fundCBReads`, brief `cbBriefHTML`, today's read `cbL`; alerts are `noTg` (in-app only). Relay `/proxy/cbpage?bank=&p=` (server.py; Vercel `api/cb.js`: bank sites only, plain text, sandboxed). BoJ is PDF-only (not read). Test: `t_cbread` (samples in tests/cb).
- TradingView extras on Charts (end of `<script id="charts">`; test `t_tvx`, `t_sync`): chart types `CH_TYPES`/`chMainSeries`/`chSerPt` (Heikin Ashi `chHA`);
  chart alerts `CHA` (`chaDialog`, `chaQuick`, `chaEval` every 3 s, `chaCandles`, list `chaList`); bar replay `RP` (`rpEnter`, `rpCut`, `rpForward`; blocks `cttPlace`/`mxtPlace`/`qtPlace`);
  compare `CH.cmp` (`chCmpSync`, percent scale); right panel tabs `CH.side` (object tree `chSideRender`, data window `chDataWin`); snapshot `chSnap`;
  sync via private GitHub gist `SYNC_PARTS`/`syNow` (token in `finder-sync`, Settings → Sync); scripts `PS` (Pine-like, no eval: `psLex`/`psParse`/`psCompile`/`psRun`, editor `psEditor`, registered as `IND["ps_<id>"]`).
- Market picker (TradingView style, `#chPick` as a centred dialog): `pkMarkets(cat, src)` groups each market's sources (key = `chName`), preferred first;
  `pkSrcOf`/`pkSrcName`/`pkType`/`pkIcon`; sources page `chPickView = "src"`; a source picked by hand sticks (`chSetSym(sym, true)` → `CH.symExact`). Test `t_picker`.
  Tests start on Overview unless `setup(ctx, start=None)` (the app itself opens on Charts).
- Markets switch on the boards (`MK`, `boardRows`, `mkDay`/`mkSwing`, `mkMix`, `rowOf`; test `t_mkts`): crypto plus `MACRO.rows` (forex, indices, metals & energy) through the same detectors.
  `data.day`/`data.swing`/`aotsList()` stay coin-only for history, streams and exports; the boards call the mixed versions.
- Trading day page (`tday`, sidebar MARKET; spec `docs/superpowers/specs/2026-11-27-trading-day-design.md`, piece 1 built): core `tdKey`/`tdBin`/`tdStart`
  (session-clock day from 8:00, so 3 AM PHT is still yesterday), holiday rules `holRules`/`HOL_TABLE` (HK, KR 2026–2027 only), `holEntries`, broker list
  `ctHolidays`/`brokerHolidays` (`finder-hol`); profiles `tdDays`/`tdProfile`/`tdFx`/`tdDow`/`tdSeries`; forecast and calls `TD_CENTRES`/`tdMk`/`tdForecast`/`tdCall`
  /`tdLive`/`tdRoom`/`tdCalcMarket`; words `tdSay`/`tdSayWeek`. Extras: `tdLoad(force, now)` (1H history ~2 years cached as `td|sym` in `finder-cache` → `kl`,
  15m today, calls kept in `finder-td-calls`), `tdRender` (Today / This week), `tdNote` (Overview session note) and `tdChip` (`#chDay` on Charts). Test `t_td`
  (pass the day to `tdLoad`: a frozen test clock stalls the rate limiter `spend`).
- Event risk (extras): `riskRead` (level 0–2 + reasons: US election nights by rule `usElectionDay`, your own events `riskOwn`/`EVR_KEY`, shock headlines
  `RISK_WORDS`/`RISK_SEVERE` from `FUND.news`, VIX jump via UVXY, Friday weekend gap), `riskCalItems` (into `calAll`),
  `riskTick` every minute (alerts kind "Event risk" once per reason; "protect your trade" for real positions `riskPositions` at ≥1.5R whose stop is still on the losing side),
  banner `riskRender` on Trading day (add/remove your own events), "Today's read" header + card warning. Test: `t_risk`.
- Calendar: List / Week / Month views (`CALV`, `calGrid`, `calGridRange`), `ffNorm`, `usMarketEvents`, `FOMC_DATES`, `earnImpact`.
  Actuals for main US releases from FRED: `CAL_ACT` (title → series, how, months back, dollar sign, kind), `calActual`, `calActFetch` (each series at most every 10 min;
  new series go in the FRED allow-lists too), `calLastSurprise` → "Today's read" header and card line `surLine`. Alerts: `ncAdd` (wrapped to forward to Telegram), `NC_KINDS`; Notification settings in the bell drawer (`ncSetView`/`ncRenderSet`, per kind on/banner/sound/pop-up via `ncPref`, `finder-nc-prefs`; Phone column = Telegram kinds through `ncPhoneHook`).

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
