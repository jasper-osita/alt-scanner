# Trading Day, Piece 1 (the Day's Call) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Trading day" page (Today and This week) that calls each of Jas's non-crypto markets Tradeable, Tradeable until London, Likely quiet or Closed for the day, from measured hourly profiles, past holidays and a live check, with a written summary.

**Architecture:** Pure calculations (holiday rules, trading-day bins, profiles, holiday effects, forecast, calls, summary) go in `<script id="core">` so Node tests and the cloud watcher can use them. Fetching and caching candles (IndexedDB `finder-cache`, store `kl`) and the page go in `<script id="extras">`; the sidebar entry and the Charts chip touch the UI and charts scripts.

**Tech Stack:** Vanilla JS in `index.html`; Python Playwright tests with `tests/mock.py`; Node for core-only checks.

**Spec:** `docs/superpowers/specs/2026-11-27-trading-day-design.md` (pieces 2–4 are out of scope here: no Now line, nudges, releases, ranking, guard or best hours). Mockups: artboards "Home tab · Trading day: today / this week".

## Global Constraints

- Markets: the chart watchlist (`CHW`) minus crypto, matched to the forex/metals/indices rows (`xRows()`); if none match, Gold, Silver, EURUSD, GBPUSD, USDJPY, AUDUSD, NAS100. No crypto anywhere on the page.
- One trading day = 24 hourly bins on the session clock starting at session 8:00; day key from `sessD(ms - 8h)`. PHT labels through `sessLbl`/`hLbl` (they shift with New York daylight saving). Never plain PHT dates (CLAUDE.md).
- Thresholds (spec "My calls"): Likely quiet when the forecast day range is under 70% of normal; Tradeable until London when Asia and London bins are at 80%+ and New York's sum is under 70%; live "Moving normally" at 80%+, "Quiet so far" under 60%, "Waking up" when the current hour runs at 2× its usual.
- Normal = median over the last 20 trading days that weren't holidays for the market's centres. History: 1-hour candles, about two years. Today: 15-minute candles.
- Every past-holiday estimate carries its example count; with fewer than 2 examples the centre map decides (closed centre: its session bins × 0.5, half day × 0.7).
- Plain-language UI copy, sentence case; no network in tests; never real orders; no secrets.
- After changes `TZ=Asia/Manila bash bump-version.sh`; tests `bash tests/runall.sh <names>` (fail on Traceback or `errors: [...]`); commit as Jas (`git -c user.email=jasperosita18@gmail.com -c user.name="Jasper Osita" commit`) with the Co-Authored-By and Claude-Session lines.

## Review Focus

- The small hours: 3 AM PHT on Friday is still Thursday's trading day; a 1-hour candle at session 7:00 belongs to the day before (Task 2 test).
- A market with no candles yet (source down, cTrader not connected for a `CT:` symbol): its row says "No data yet", never "Tradeable" (Task 6 test).
- A week with a holiday on Monday: the normal profile skips that day instead of dragging the median down (Task 3 test).
- New York daylight saving: in July the same session bins land an hour earlier in PHT and the labels follow (Task 2 test).
- A watchlist that is all crypto: the page falls back to the default seven markets (Task 6 test).

---

### Task 1: Holiday rules for nine markets (core)

Carry over **Task 1 of `docs/superpowers/plans/2026-11-26-market-holidays-trade-day.md` unchanged**: `HOL_MKTS`, `hdKey(y, m, d)`, `hdYmd(key)`, `holRules(mk, y)`, `HOL_TABLE` (Hong Kong and Korea 2026–2027, data as listed there), with its part-1 checks, but in a new test file `tests/t_td.py` (same structure: serve, setup, `q`, `check`, `errors:` line).

- [ ] Step 1: the part-1 checks in `tests/t_td.py` → Step 2: `bash tests/runall.sh t_td` FAILS → Step 3: implement → Step 4: `bash tests/runall.sh t_td t_dst` pass → Step 5: commit "Holiday rules for nine markets".

### Task 2: Trading-day clock, holiday merge, broker list (core)

**Files:** `index.html` core (after Task 1; broker code after `ctSpec` ≈ line 2695); `tests/mock.py` (2116 reply); `tests/t_td.py` (part 2).

**Interfaces:**
- Consumes: Task 1; `sessD`, `sessShift`, `PHT_MS`; `ctReq`, `CT.symbols`, `ctNorm`.
- Produces:
  - `tdKey(ms)` → integer day key = `Math.floor((sessD(ms).getTime() - 8 * 3600e3) / 864e5)`; `tdBin(ms)` → 0–23 (hour since session 8:00); `tdStart(key)` → UTC ms of session 8:00 on that day (inverse of `tdKey`, daylight saving included).
  - `TD_CENTRE_BINS = { US: [13..19], CA: [13..17], UK: [4..10], EU: [4..10], CH: [4..10], JP: [0..3], HK: [0..3], KR: [0..3], AU: [0..3] }` (bins a centre's closure thins).
  - `ffHolidays(rows)`, `holEntries(fromKey, toKey, extra = [])`, `holSay(entry)` exactly as Task 2 of the superseded plan (merged entries `{ key, mk, n, half, srcs }`; keys are now `tdKey`-compatible day keys, i.e. the market's local calendar date).
  - `HOL_SYMS`, `brokerHolidays(bySym, fromKey, toKey)`, `async ctHolidays(force)` exactly as Task 3 of the superseded plan, including its mock (`CT_HOL` in `tests/mock.py`).

- [ ] **Step 1: Part-2 checks** — the superseded plan's Task 2 and Task 3 checks (rename `tradeDayKey` → `tdKey`; drop its `tradeDay` checks), plus:

```python
check("3:00 AM PHT Fri is Thursday's trading day", await q("() => tdKey(Date.UTC(2026, 10, 26, 19, 0)) === hdKey(2026, 11, 26)"))
check("8:30 AM PHT Fri is still Thursday (before the winter Asia open)", await q("() => tdKey(Date.UTC(2026, 10, 27, 0, 30)) === hdKey(2026, 11, 26)"))
check("9:15 AM PHT Fri is Friday, bin 0", await q("() => tdKey(Date.UTC(2026, 10, 27, 1, 15)) === hdKey(2026, 11, 27) && tdBin(Date.UTC(2026, 10, 27, 1, 15)) === 0"))
check("July: 8:15 AM PHT is already bin 0", await q("() => tdBin(Date.UTC(2026, 6, 15, 0, 15)) === 0"))
check("tdStart inverts tdKey (winter and summer)", await q("() => [hdKey(2026, 11, 27), hdKey(2026, 7, 15)].every(k => tdKey(tdStart(k)) === k && tdBin(tdStart(k)) === 0)"))
```

- [ ] **Step 2:** `bash tests/runall.sh t_td` → FAILED.
- [ ] **Step 3:** implement the listed functions and the mock change.
- [ ] **Step 4:** `bash tests/runall.sh t_td t_dst t_ctfeed t_trade` → pass.
- [ ] **Step 5:** commit "Trading-day clock, holiday merge and the broker's list".

### Task 3: Profiles and holiday effects (core)

**Files:** `index.html` core (after Task 2); `tests/t_td.py` (part 3, fixtures built in the page with a seeded generator).

**Interfaces:**
- Consumes: Task 2. Candles `K = { t: [ms], h: [], l: [] }` (1-hour, ascending; `o`, `c`, `qv` may be present).
- Produces:
  - `tdDays(K)` → `Map(dayKey → { bins: [24 ranges or null], hi, lo, range })` (weekends dropped; a day's range = max high − min low of its candles).
  - `tdProfile(days, skipKeys, beforeKey, n = 20)` → `{ bins: [24 medians], day: median day range, n: days used, keys }` over the last `n` days before `beforeKey` not in `skipKeys` (a `Set`).
  - `tdFx(days, entries, centres)` → `{ [centre]: { n, day: median ratio, bins: [24 median ratios], keys } }`: for each past day where `centre` has an entry, its day range (and each bin) ÷ the `tdProfile` of the 20 normal days before it.
  - `tdDow(days, skipKeys, weeks = 12)` → `[5 medians]` Mon–Fri day ranges; `tdSeries(days, count = 65)` → `[{ key, range }]` latest trading days.

- [ ] **Step 1: Part-3 checks** — the test file injects (with `pg.add_init_script`) `TD_TEST_SHAPE = [5, 5, 4.5, 4.5, 5, 6.5, 12, 16, 14, 12, 10, 9, 13, 18, 20, 16, 12, 9, 7, 5, 3, 3, 3.5, 4.5]` and `tdFixture(seed, opts)`: 1-hour candles for every weekday from 2025-06-02 to 2026-12-31, 24 per day starting at `tdStart(key)`, each candle's range = `TD_TEST_SHAPE[bin] × (opts.flat ? 1 : 0.9 + 0.2 × seeded random) × (opts.thin?.[key] ?? 1)`, consecutive candles sharing a mid-price so a day's range is well defined:

```python
check("profile ignores holidays", await q("() => { const K = tdFixture(1, { thin: { [hdKey(2026, 11, 23)]: 0.3 } }), D = tdDays(K); const a = tdProfile(D, new Set([hdKey(2026, 11, 23)]), hdKey(2026, 11, 27)), b = tdProfile(D, new Set(), hdKey(2026, 11, 27)); return a.n === 20 && !a.keys.includes(hdKey(2026, 11, 23)) && b.keys.includes(hdKey(2026, 11, 23)); }"))
check("profile median of a flat fixture equals its shape", await q("() => { const P = tdProfile(tdDays(tdFixture(2, { flat: true })), new Set(), hdKey(2026, 11, 27)); return Math.abs(P.bins[6] / P.bins[0] - TD_TEST_SHAPE[6] / TD_TEST_SHAPE[0]) < 0.01; }"))
check("US holiday effect measured at about 0.6 with its count", await q("() => { const E = holEntries(hdKey(2025, 7, 1), hdKey(2026, 11, 20)); const K = tdFixture(3, { thin: Object.fromEntries(E.filter(e => e.mk === 'US').map(e => [e.key, 0.6])) }); const fx = tdFx(tdDays(K), E, ['US'])['US']; return fx.n >= 8 && Math.abs(fx.day - 0.6) < 0.08; }"))
check("day of week has five values", await q("() => tdDow(tdDays(tdFixture(4, {})), new Set()).length === 5"))
check("series is the latest 65 trading days", await q("() => { const S = tdSeries(tdDays(tdFixture(5, {}))); return S.length === 65 && S[64].key > S[0].key; }"))
```

(`tdFixture` and `TD_TEST_SHAPE` live in the test file and are injected with `pg.add_init_script`, not in `index.html`.)

- [ ] **Step 2:** run → FAILED. **Step 3:** implement. **Step 4:** `bash tests/runall.sh t_td` → pass. **Step 5:** commit "Hourly profiles and holiday effects".

### Task 4: Forecast, calls, live check, room left (core)

**Files:** `index.html` core; `tests/t_td.py` (part 4).

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - `TD_CENTRES = { Gold: ["UK", "US"], Silver: ["UK", "US"], EURUSD: ["UK", "EU", "US"], GBPUSD: ["UK", "US"], USDJPY: ["JP", "US"], AUDUSD: ["AU", "US"], NAS100: ["US"], US500: ["US"], US30: ["US"], GER40: ["EU"], JP225: ["JP"], HK50: ["HK"], UK100: ["UK"] }`; `TD_OWN = { NAS100: "US", US500: "US", US30: "US", GER40: "EU", JP225: "JP", HK50: "HK", UK100: "UK" }`.
  - `tdMk(sym)` → market id from any symbol or name (`CT:XAUUSD`, `XAUUSDT`, `MX:XAU_USDT`, "Gold" → "Gold"; `US100`/`USTEC`/`QQQUSDT`/"Nasdaq 100" → "NAS100"; `SPYUSDT`/"S&P 500" → "US500"; unknown → `null`).
  - `tdForecast(mk, prof, fx, todayEntries)` → `{ bins: [24], day, ratio, closed, why: [{ centre, n, half, factor }] }`: start from `prof.bins`; for each centre in `TD_CENTRES[mk]` with an entry today, multiply by `fx[centre].bins` when `fx[centre].n >= 2`, else by 0.5 (0.7 for half days) on `TD_CENTRE_BINS[centre]`; `closed` when `TD_OWN[mk]` has a full close today; `ratio` = Σ forecast bins ÷ Σ profile bins; `day` = `prof.day × ratio`.
  - `tdCall(fc, prof)` → `"closed" | "quiet" | "untilLondon" | "ok"` per Global Constraints (London bins = `TD_CENTRE_BINS.UK`, New York = `TD_CENTRE_BINS.US`).
  - `tdLive(today, prof, bin)` → `{ soFar, normalSoFar, ratio, hourRatio, state: "normal" | "quiet" | "waking" | "between" }` where `today` = `{ bins: [24 ranges or null], range }` from 15-minute candles; `normalSoFar = prof.day × Σ prof.bins[0..bin] ÷ Σ prof.bins`.
  - `tdRoom(todayRange, fcDay)` → 0–1.
  - `tdLive` precedence: `waking` when `hourRatio >= 2`, else `normal` at `ratio >= 0.8`, `quiet` under 0.6, otherwise `between`. `tdCall` precedence: `closed`, then `quiet` (`ratio < 0.7`), then `untilLondon`, then `ok`.
  - `tdCalcMarket(m, K1h, K15, entries, key, now)` → `{ ...m, prof, fx, fc, call, live, room, days, err }`; with no 1-hour candles it returns `call: null, err: "No data yet"`.

- [ ] **Step 1: Part-4 checks**

```python
P = "{ bins: TD_TEST_SHAPE.slice(), day: 60, n: 20 }"
check("no holiday: Tradeable", await q(f"() => tdCall(tdForecast('EURUSD', {P}, {{}}, []), {P}) === 'ok'"))
check("US closed, no history: Tradeable until London", await q(f"() => tdCall(tdForecast('EURUSD', {P}, {{}}, [{{ mk: 'US', half: false }}]), {P}) === 'untilLondon'"))
check("US closed: NAS100 Closed", await q(f"() => tdCall(tdForecast('NAS100', {P}, {{}}, [{{ mk: 'US', half: false }}]), {P}) === 'closed'"))
check("UK and US closed: Gold Likely quiet", await q(f"() => tdCall(tdForecast('Gold', {P}, {{}}, [{{ mk: 'UK', half: false }}, {{ mk: 'US', half: false }}]), {P}) === 'quiet'"))
check("Japan holiday leaves Gold Tradeable", await q(f"() => tdCall(tdForecast('Gold', {P}, {{}}, [{{ mk: 'JP', half: false }}]), {P}) === 'ok'"))
check("measured effect wins with 2+ examples", await q(f"() => tdForecast('Gold', {P}, {{ US: {{ n: 3, day: 0.95, bins: Array(24).fill(0.95) }} }}, [{{ mk: 'US', half: false }}]).ratio > 0.9"))
check("live: waking up at twice the hour", await q(f"() => tdLive({{ bins: TD_TEST_SHAPE.map((v, i) => i === 6 ? v * 2.2 : i < 6 ? v : null), range: 70 }}, {P}, 6).state === 'waking'"))
check("live: quiet under 60%", await q(f"() => tdLive({{ bins: TD_TEST_SHAPE.map((v, i) => i <= 6 ? v * 0.4 : null), range: 6 }}, {P}, 6).state === 'quiet'"))
check("room left", await q("() => Math.abs(tdRoom(15, 40) - 0.625) < 1e-9 && tdRoom(50, 40) === 0"))
check("market ids", await q("() => ['CT:XAUUSD', 'XAUUSDT', 'MX:XAU_USDT', 'Gold'].every(s => tdMk(s) === 'Gold') && tdMk('QQQUSDT') === 'NAS100' && tdMk('BTCUSDT') === null"))
check("no candles: no call, says so", await q("() => { const r = tdCalcMarket({ mk: 'Gold', sym: 'CT:XAUUSD' }, null, null, [], hdKey(2026, 11, 26), Date.UTC(2026, 10, 26, 7, 42)); return r.call === null && r.err === 'No data yet'; }"))
```

- [ ] **Step 2:** run → FAILED. **Step 3:** implement. **Step 4:** `bash tests/runall.sh t_td` → pass. **Step 5:** commit "Forecast, day calls and the live check".

### Task 5: The day's written summary (core)

**Files:** `index.html` core; `tests/t_td.py` (part 5).

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `tdSay({ key, markets: [{ mk, call, fc, live }], entries })` → `{ verdict: "Thin day" | "Normal day" | "Closed day", title, lines: [{ k: "Asia" | "London" | "New York" | "Past years" | "For you", v }], week: null }` and `tdSayWeek(days)` → one sentence for the week. Rules: verdict Thin day when most markets are below `ok`, Closed day when all are `closed`; each session line says "Normal.", "Thin.", "Half day." or "Closed." with the holiday name and time from `holSay`; "Past years" appears only when some market's `fx` has `n >= 2` and quotes that count; "For you" uses the best window (Asia/London/New York with the highest forecast share).

- [ ] **Step 1: Part-5 checks**

```python
S = "tdSay({ key: hdKey(2026, 11, 26), markets: [{ mk: 'Gold', call: 'untilLondon', fc: { ratio: 0.62, why: [{ centre: 'US', n: 3, half: false }] } }, { mk: 'NAS100', call: 'closed', fc: { ratio: 0, why: [] } }], entries: holEntries(hdKey(2026, 11, 26), hdKey(2026, 11, 26)) })"
check("thin day verdict", await q(f"() => {S}.verdict === 'Thin day'"))
check("New York line names Thanksgiving", "Thanksgiving" in await q(f"() => {S}.lines.find(l => l.k === 'New York').v"))
check("past years quotes its count", "3" in await q(f"() => ({S}.lines.find(l => l.k === 'Past years') || {{}}).v || ''"))
check("normal day", await q("() => tdSay({ key: hdKey(2026, 12, 2), markets: [{ mk: 'Gold', call: 'ok', fc: { ratio: 1, why: [] } }], entries: [] }).verdict === 'Normal day'"))
```

- [ ] **Step 2:** run → FAILED. **Step 3:** implement. **Step 4:** pass. **Step 5:** commit "The day's written summary".

### Task 6: Loading candles and computing the day (extras)

**Files:** `index.html` core (`klinesRange`, after `klines` ≈ line 1760); `index.html` extras (new block after the calendar code); `tests/t_td.py` (part 6).

**Interfaces:**
- Consumes: Tasks 1–5; `klines(sym, "15m", 100)`; `ctKlines(sym, "1h", limit, false, toMs)`; `mxKlinesF(sym, "1h", from, to)`; Binance `${FAPI}/fapi/v1/klines?symbol&interval=1h&startTime&endTime&limit=1500`; `scTx("kl", ...)`; `CHW`; `xRows()`; `calAll()`; `ctHolidays()`.
- Produces:
  - `async klinesRange(sym, interval, fromMs, toMs)` (core) → `K` ascending, paging by source (`CT:` 5000 per step back with `toMs`, `MX:` 2000-hour windows, Binance 1500 with `startTime`/`endTime`).
  - `TD = { at, key, markets: [{ mk, sym, name, prof, fx, fc, call, live, room, days, err }], entries, busy, err }` and `async tdLoad(force)`: markets per Global Constraints; 1-hour history from cache key `"td|" + sym` in the `kl` store (fetch only what's newer than the cached last candle; first load fetches two years), 15-minute today candles, holidays from rules + `ffHolidays(calAll())` + broker list when cTrader is ready; computes everything; stores the day's calls in localStorage `finder-td-calls` (`{ [dayKey]: { [mk]: { call, ratio } } }`, last 60 days) for This week; refreshes the live part every 15 minutes while the page is open.

- [ ] **Step 1: Part-6 checks** (first page, mocks, fixed clock `2026-11-26T07:42Z`, `await q("() => tdLoad(true)")`):

```python
check("markets fall back to the default seven with an all-crypto watchlist", await q("() => { CHW = ['BTCUSDT', 'ETHUSDT']; return tdMarkets().map(m => m.mk).join() === 'Gold,Silver,EURUSD,GBPUSD,USDJPY,AUDUSD,NAS100'; }"))
check("no crypto ever", await q("() => TD.markets.every(m => tdMk(m.sym) !== null)"))
check("today's key is Thursday", await q("() => TD.key === hdKey(2026, 11, 26)"))
check("NAS100 is closed on Thanksgiving", await q("() => (TD.markets.find(m => m.mk === 'NAS100') || {}).call === 'closed'"))
check("a market whose candles fail says so", await q("() => TD.markets.filter(x => x.err).every(m => m.call === null)"))
check("history cached for next time", await q("() => scTx('kl', 'readonly', st => st.get('td|' + TD.markets[0].sym)).then(x => !!(x && x.t.length))"))
check("calls stored for the week", await q("() => !!JSON.parse(localStorage.getItem('finder-td-calls'))[TD.key]"))
```

- [ ] **Step 2:** run → FAILED. **Step 3:** implement `klinesRange`, `tdMarkets()` (sync; returns `[{ mk, sym, name }]` from `xRows()`, which `tdLoad` fills first with `await macroScan(false)` when `MACRO.rows` is empty; one row per market id, the row `xRows()` prefers), `tdLoad` (per market: fetch, then `tdCalcMarket`; a failed fetch keeps the market with `err` set). **Step 4:** `bash tests/runall.sh t_td t_macro t_xov` → pass. **Step 5:** commit "Load and compute the trading day".

### Task 7: The Trading day page

**Files:** `index.html` `PAGES` (line 6526: add `["tday", "Trading day"]` to MARKET after Overview), page markup (a `<section class="card tdcard" data-page="tday">` next to the calendar section), CSS (new `.td*` rules near the calendar CSS), `goPage` hook (`if (id === "tday" && typeof tdShown === "function") tdShown();`), extras render code, `tickClock` (session note), charts markup `.chbar` (chip `#chDay`).

**Interfaces:**
- Consumes: Task 6's `TD`, `tdLoad`, `tdSay`, `tdSayWeek`.
- Produces: `tdShown()`, `tdRender()`; `TD_VIEW` (`"today" | "week"`, localStorage `finder-td-view`); `TD_SEL` (selected market id).

- [ ] **Step 1: Part-7 checks** (fixed clock `2026-11-26T07:42Z`, `await q("() => goPage('tday')")`, wait for `#tdMkts .tdrow`):

```python
check("sidebar has Trading day under MARKET", await q("() => PAGE_INFO.tday && PAGE_INFO.tday.g === 'MARKET'"))
check("summary leads with the verdict", "Thin day" in await q("() => document.querySelector('.tdsay').innerText"))
check("one row per market, no crypto", await q("() => [...document.querySelectorAll('#tdMkts .tdrow')].every(r => !/BTC|ETH|SOL/.test(r.innerText))"))
check("24 hour bars with PHT labels starting 9 (winter)", await q("() => document.querySelectorAll('.tdhours .tdbar').length === 24 && document.querySelector('.tdhlbl span').innerText.trim() === '9'"))
await pg.click('#tdMkts .tdrow[data-mk="GBPUSD"]')
check("clicking a market switches the charts", "GBPUSD" in await q("() => document.querySelector('.tdhourstitle').innerText"))
await pg.click('[data-tdview="week"]')
check("week grid: 5 days × markets", await q("() => document.querySelectorAll('.tdweek .tdcell').length === 5 * TD.markets.length"))
check("thin stretches ahead list Christmas", "Dec 25" in await q("() => document.querySelector('.tdahead').innerText"))
await q("() => { goPage('charts'); tickClock(); }")
check("Charts chip shows the day", await q("() => !document.getElementById('chDay').hidden && /Thin day|Normal day|Closed day/.test(document.getElementById('chDay').innerText)"))
check("Overview note leads with the day on a thin day", (await q("() => { goPage('overview'); tickClock(); return document.getElementById('sessNote').innerText; }")).startswith("Thin day"))
```

- [ ] **Step 2:** run → FAILED.
- [ ] **Step 3:** implement, laid out as the mockups (Today: summary card with verdict chip and the five lines, live line, trading-day strip, "Your markets today" rows `[data-mk]` with session dots, call, day range `~{forecast} of {normal} usual ({ratio})`, live; "Hour by hour" (`.tdhours`, `.tdbar` with normal outline, today so far, forecast; `.tdhlbl` labels = the PHT hour on a 12-hour clock without AM/PM, from the bin's start time; session bands); "Day of the week" (`tdDow`); "Volatility, last 3 months" (`tdSeries`, holidays dotted); "Why this call" (holidays today, centre map, past-holiday counts). This week: `.tdweek` grid of `.tdcell` (call chip, three dots, measured % for past days from `finder-td-calls` and `tdDays`, forecast for later), the week sentence (`tdSayWeek`), a day's story on click with "Right."/"Off." against the measured ratio (right when the call was quiet/closed and the day came in under 70%, or ok and at 70%+), and `.tdahead` (holiday entries for the next 8 weeks that touch a market's centres). Session note: on a non-normal day `tickClock` prefixes `#sessNote` with `"<b>{verdict}</b> · {title}. "`; `#chDay` chip after the chart symbol button shows the verdict.
- [ ] **Step 4:** `bash tests/runall.sh t_td t_smoke t_dst t_charts t_start t_ovch` → pass.
- [ ] **Step 5:** commit "Trading day page: today and this week".

### Task 8: Version, notes, regression

- [ ] **Step 1:** CLAUDE.md, under Key code areas: "Trading day page (`tday`): core `tdKey`/`tdBin`/`tdStart` (session-clock day from 8:00), holiday rules `holRules`/`HOL_TABLE` (HK, KR 2026–2027), `holEntries`, broker list `ctHolidays`; profiles `tdDays`/`tdProfile`/`tdFx`, forecast and calls `tdForecast`/`tdCall`/`tdLive`/`tdRoom`, summary `tdSay`; extras `tdLoad` (1H history cached as `td|sym` in `finder-cache`, 15m today, calls in `finder-td-calls`), `tdRender`. Test `t_td`."
- [ ] **Step 2:** `TZ=Asia/Manila bash bump-version.sh`.
- [ ] **Step 3:** `bash tests/runall.sh t_td t_smoke t_dst t_charts t_start t_ovch t_macro t_xov t_ctfeed t_trade t_calview` → all pass.
- [ ] **Step 4:** commit "Trading day: version and notes"; `git push -u origin claude/loving-faraday-eva9zo`.
