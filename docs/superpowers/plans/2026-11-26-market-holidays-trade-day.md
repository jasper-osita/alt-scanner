# Market Holidays and the Trade-Day Call Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Market holidays tab in the Economic Calendar that tracks every market's bank holidays and half days and calls each day Trade day or No trade, with quiet alerts, an order confirmation and a Telegram heads-up on no-trade days.

**Architecture:** Holiday rules, the merge and the call live in `<script id="core">` (DOM-free, so `cloud/watch.mjs` makes the same call). The broker's holiday list comes from cTrader symbol details (payload 2116) next to `ctSpec`. The tab, settings, session note, chart chip, quiet alerts and order check live in `<script id="extras">` next to the calendar; the order check is called from `cttPlace`/`mxtPlace` in `<script id="trade">`.

**Tech Stack:** Vanilla JS in `index.html`; Node `vm` for the cloud watcher; Python Playwright tests with `tests/mock.py` (no network).

**Spec:** `docs/superpowers/specs/2026-11-26-market-holidays-trade-day-design.md`

## Global Constraints

- No trade = any counted market closed for a holiday **or** closing early (half day) that day; it covers everything (Gold, NAS100, forex pairs, crypto). Two outcomes only: "Trade day" / "No trade".
- Counted markets, all on by default: US, UK, Euro area, Japan, Hong Kong, Korea, Australia, Canada, Switzerland. Broker forex/gold closures (market `FX`) always count.
- The day is the session-clock day: `sessD`, with hours before 5 AM on the session clock belonging to the previous trading day. Never plain PHT dates (CLAUDE.md).
- Plain-language UI copy, sentence case. Times shown in PHT.
- No network in tests; never place real orders in tests; no tokens or secrets in code.
- After changes: `TZ=Asia/Manila bash bump-version.sh`. Tests: `bash tests/runall.sh <names>`; a test fails on a Traceback or `errors: [...]`.
- Commit as Jas: `git -c user.email=jasperosita18@gmail.com -c user.name="Jasper Osita" commit`, message ending with the Co-Authored-By and Claude-Session lines.

## Review Focus

- The small hours: 3:00 AM PHT on Friday is still Thursday's NY PM session, so it must get Thursday's call (Task 2 test).
- cTrader not connected, or Pepperstone's list empty: the rules still make the call and the tab says where its data came from (Task 3 and Task 4 tests).
- A range crossing New Year: Dec 31 and Jan 1 from two rule years both appear (Task 2 test).
- Past the Hong Kong/Korea tables (2028): the day shows "can't check Hong Kong, Korea", never a quiet Trade day (Task 2 test).
- Unticking a market flips its days back to Trade day and survives a reload (Task 4 test).

---

### Task 1: Holiday rules for nine markets (core)

**Files:**
- Modify: `index.html` `<script id="core">`, after `usMarketEvents` (≈ line 3060)
- Test: `tests/t_hol.py` (new)

**Interfaces:**
- Consumes: `usHolidays(y)` → `{ closed: [{n,m,d}], early: [{n,m,d}] }`, `easter(y)` → `[m, d]`, `nthWd(y, m, wd, n)`, `lastWd(y, m, wd)`.
- Produces:
  - `const HOL_MKTS = [["US", "US"], ["UK", "UK"], ["EU", "Euro area"], ["JP", "Japan"], ["HK", "Hong Kong"], ["KR", "Korea"], ["AU", "Australia"], ["CA", "Canada"], ["CH", "Switzerland"]]`
  - `hdKey(y, m, d)` → integer day key = `Math.floor(Date.UTC(y, m - 1, d) / 864e5)`; `hdYmd(key)` → `[y, m, d]`.
  - `holRules(mk, y)` → `[{ m, d, n, half }]` (weekdays only), or `null` when the market has no data for that year (HK, KR outside the table).

- [ ] **Step 1: Write the failing test** `tests/t_hol.py`, built like `tests/t_dst.py` (serve, setup, ready, `q = lambda js: pg.evaluate(js)`) with the `check(name, ok, detail)` helper from `tests/t_picker.py` and `print("errors:", F + errs[:4] or "none")` at the end. Part 1 checks:

```python
has = lambda mk, y, m, d, half=None: q(f"() => (holRules('{mk}', {y}) || []).some(h => h.m === {m} && h.d === {d}{'' if half is None else f' && !!h.half === {str(half).lower()}'})")
check("US Thanksgiving 2026 closed", await has("US", 2026, 11, 26, False))
check("US day after Thanksgiving 2026 half", await has("US", 2026, 11, 27, True))
check("UK Boxing Day 2026 moved to Mon 28", await has("UK", 2026, 12, 28, False))
check("UK Christmas Eve 2026 half", await has("UK", 2026, 12, 24, True))
check("Frankfurt shut Dec 24 and 31 2026", await has("EU", 2026, 12, 24, False) and await has("EU", 2026, 12, 31, False))
check("Japan Coming of Age 2027-01-11", await has("JP", 2027, 1, 11, False))
check("Japan citizens' holiday 2026-09-22", await has("JP", 2026, 9, 22, False))
check("Japan vernal equinox 2027 moved to Mon 22", await has("JP", 2027, 3, 22, False))
check("Hong Kong Lunar New Year 2026-02-17", await has("HK", 2026, 2, 17, False))
check("Hong Kong Christmas Eve 2026 half", await has("HK", 2026, 12, 24, True))
check("Korea Chuseok 2026-09-24", await has("KR", 2026, 9, 24, False))
check("Australia Boxing Day 2026 moved to Mon 28", await has("AU", 2026, 12, 28, False))
check("Canada Boxing Day 2026 moved to Mon 28", await has("CA", 2026, 12, 28, False))
check("Switzerland Ascension 2026-05-14", await has("CH", 2026, 5, 14, False))
check("no weekend entries", await q("() => HOL_MKTS.every(([k]) => (holRules(k, 2026) || []).every(h => ![0, 6].includes(new Date(Date.UTC(2026, h.m - 1, h.d)).getUTCDay())))"))
check("Hong Kong 2028 has no data", await q("() => holRules('HK', 2028) === null && holRules('KR', 2028) === null"))
```

- [ ] **Step 2: Run it** — `bash tests/runall.sh t_hol` → FAILED (`holRules is not defined`).

- [ ] **Step 3: Implement `HOL_MKTS`, `hdKey`, `hdYmd`, `holRules(mk, y)` in core.** Rules per market (drop weekend dates at the end; "moved" = a weekend date's weekday substitute):
  - **US**: `usHolidays(y)`: `closed` → `half: false`, `early` → `half: true`.
  - **UK** (LSE): New Year (Sat/Sun → Mon), Good Friday, Easter Monday, first Mon May, last Mon May, last Mon Aug, Christmas and Boxing Day with UK substitutes (25 Sat → Mon 27 + Tue 28; 25 Fri/26 Sat → Mon 28; 25 Sun → Tue 27 + 26 Mon); half: Dec 24, Dec 31.
  - **EU** (Xetra): Jan 1, Good Friday, Easter Monday, May 1, Dec 24, 25, 26, 31 (all full closes, no substitutes).
  - **JP** (JPX): Jan 1–3, 2nd Mon Jan, Feb 11, Feb 23, vernal equinox `Math.floor(20.8431 + 0.242194 * (y - 1980) - Math.floor((y - 1980) / 4))` Mar, Apr 29, May 3, 4, 5, 3rd Mon Jul, Aug 11, 3rd Mon Sep, autumnal equinox `Math.floor(23.2488 + 0.242194 * (y - 1980) - Math.floor((y - 1980) / 4))` Sep, 2nd Mon Oct, Nov 3, Nov 23, Dec 31. A holiday on Sunday moves to the next day that isn't a holiday; a weekday between two holidays is a holiday.
  - **AU** (ASX): Jan 1 and Jan 26 (weekend → Mon), Good Friday, Easter Monday, Apr 25 (weekday only), 2nd Mon Jun, Christmas/Boxing Day with UK substitutes; half: Dec 24, Dec 31.
  - **CA** (TSX): Jan 1 (weekend → Mon), 3rd Mon Feb, Good Friday, the Monday before May 25, Jul 1 (weekend → Mon), 1st Mon Aug, 1st Mon Sep, 2nd Mon Oct, Christmas/Boxing Day with UK substitutes; half: Dec 24.
  - **CH** (SIX): Jan 1, Jan 2, Good Friday, Easter Monday, May 1, Ascension (Easter + 39), Whit Monday (Easter + 50), Aug 1, Dec 24, 25, 26, 31.
  - **HK, KR**: a table `HOL_TABLE = { HK: { 2026: [...], 2027: [...] }, KR: { ... } }` of `[m, d, n, half?]`; `null` for other years. Data (best knowledge; the tab's note asks to check HKEX/KRX):

```js
HK: { 2026: [[1,1,"New Year's Day"],[2,16,"Lunar New Year's Eve",1],[2,17,"Lunar New Year"],[2,18,"Lunar New Year"],[2,19,"Lunar New Year"],[4,3,"Good Friday"],[4,6,"Easter Monday"],[4,7,"Day after Ching Ming"],[5,1,"Labour Day"],[5,25,"Day after Buddha's Birthday"],[6,19,"Tuen Ng"],[7,1,"HKSAR Establishment Day"],[10,1,"National Day"],[10,19,"Day after Chung Yeung"],[12,24,"Christmas Eve",1],[12,25,"Christmas Day"],[12,31,"New Year's Eve",1]],
      2027: [[1,1,"New Year's Day"],[2,5,"Lunar New Year's Eve",1],[2,8,"Lunar New Year"],[2,9,"Lunar New Year"],[3,26,"Good Friday"],[3,29,"Easter Monday"],[4,5,"Ching Ming"],[5,13,"Buddha's Birthday"],[6,9,"Tuen Ng"],[7,1,"HKSAR Establishment Day"],[9,16,"Day after Mid-Autumn"],[10,1,"National Day"],[10,8,"Chung Yeung"],[12,24,"Christmas Eve",1],[12,27,"First weekday after Christmas"],[12,31,"New Year's Eve",1]] },
KR: { 2026: [[1,1,"New Year's Day"],[2,16,"Seollal"],[2,17,"Seollal"],[2,18,"Seollal"],[3,2,"Independence Movement Day (moved)"],[5,1,"Labour Day"],[5,5,"Children's Day"],[5,25,"Buddha's Birthday (moved)"],[6,3,"Local elections"],[8,17,"Liberation Day (moved)"],[9,24,"Chuseok"],[9,25,"Chuseok"],[10,5,"National Foundation Day (moved)"],[10,9,"Hangeul Day"],[12,25,"Christmas Day"],[12,31,"Year-end closing"]],
      2027: [[1,1,"New Year's Day"],[2,8,"Seollal"],[2,9,"Seollal (moved)"],[3,1,"Independence Movement Day"],[5,5,"Children's Day"],[5,13,"Buddha's Birthday"],[8,16,"Liberation Day (moved)"],[9,14,"Chuseok"],[9,15,"Chuseok"],[9,16,"Chuseok"],[10,4,"National Foundation Day (moved)"],[10,11,"Hangeul Day (moved)"],[12,27,"Christmas (moved)"],[12,31,"Year-end closing"]] }
```

- [ ] **Step 4: Run** `bash tests/runall.sh t_hol t_dst` → both pass (`errors: none`).
- [ ] **Step 5: Commit** — `git add index.html tests/t_hol.py` · "Holiday rules for nine markets".

### Task 2: The merge and the day's call (core)

**Files:**
- Modify: `index.html` core, after Task 1's code
- Test: `tests/t_hol.py` (part 2)

**Interfaces:**
- Consumes: Task 1; `sessD(ms)`; `ffNorm` rows `{ at, ccy, title, impact }`.
- Produces:
  - `tradeDayKey(ms)` → day key = `Math.floor((sessD(ms).getTime() - 5 * 3600e3) / 864e5)`.
  - `ffHolidays(rows)` → `[{ key, mk, n, half: false, src: "ff" }]` for `impact === "Holiday"` rows; currency → market `USD→US, GBP→UK, EUR→EU, JPY→JP, AUD→AU, CAD→CA, CHF→CH` (others dropped); the date is the row's New York calendar date (Forex Factory's feed is in New York time).
  - `holEntries(fromKey, toKey, extra = [])` → merged `[{ key, mk, n, half, srcs: [...] }]` sorted by key then market: rules (`src: "rules"`) for every year the range touches, plus `extra`. One entry per (key, mk): a full close beats a half day, names joined with " / " when they differ, `srcs` the union.
  - `tradeDay(key, entries, counted)` → `{ key, ok, weekend, why: [entry...], missing: [mk...] }`; `weekend` for Sat/Sun keys (`ok: false`); `why` = entries for that key whose market is in `counted` or is `"FX"`; `ok = !weekend && !why.length`; `missing` = counted markets whose `holRules(mk, y)` is `null`.
  - `holSay(entry)` → plain text: full close `"US Thanksgiving"`, half day `"US half day (Day after Thanksgiving)"`, using the market's `HOL_MKTS` label (`FX` → `"Your broker"`).

- [ ] **Step 1: Add part 2 checks to `tests/t_hol.py`**

```python
K = lambda y, m, d: f"hdKey({y}, {m}, {d})"
ALL = "HOL_MKTS.map(x => x[0])"
day = lambda key, counted=ALL: q(f"() => JSON.stringify(tradeDay({key}, holEntries({key} - 1, {key} + 1), {counted}))")
check("Thanksgiving is no trade", '"ok":false' in await day(K(2026, 11, 26)))
check("its half day is no trade too", '"ok":false' in await day(K(2026, 11, 27)))
check("Mon Nov 30 is a trade day", '"ok":true' in await day(K(2026, 11, 30)))
check("unticking the US makes Thanksgiving a trade day", '"ok":true' in await day(K(2026, 11, 26), "['UK','EU','JP']"))
check("3:00 AM PHT Fri is still Thursday", await q("() => tradeDayKey(Date.UTC(2026, 10, 26, 19, 0)) === hdKey(2026, 11, 26)"))
check("6:00 AM PHT Fri is Friday", await q("() => tradeDayKey(Date.UTC(2026, 10, 26, 22, 0)) === hdKey(2026, 11, 27)"))
check("summer time: 3:00 AM PHT is still the day before", await q("() => tradeDayKey(Date.UTC(2026, 6, 15, 19, 0)) === hdKey(2026, 7, 15)"))
check("a range over New Year has Dec 31 and Jan 1", await q("() => { const E = holEntries(hdKey(2026, 12, 30), hdKey(2027, 1, 2)); return E.some(e => e.key === hdKey(2026, 12, 31)) && E.some(e => e.key === hdKey(2027, 1, 1)); }"))
check("2028 flags Hong Kong and Korea as missing", await q("() => tradeDay(hdKey(2028, 3, 7), holEntries(hdKey(2028, 3, 6), hdKey(2028, 3, 8)), HOL_MKTS.map(x => x[0])).missing.join() === 'HK,KR'"))
check("weekends are not trade days", await q("() => tradeDay(hdKey(2026, 11, 28), [], ['US']).weekend === true"))
check("Forex Factory USD holiday maps to the US", await q("() => ffHolidays([{ at: Date.parse('2026-11-26T00:00:00-05:00'), ccy: 'USD', title: 'Bank Holiday', impact: 'Holiday' }])[0].key === hdKey(2026, 11, 26)"))
check("broker FX closure always counts", await q("() => !tradeDay(hdKey(2026, 12, 7), holEntries(hdKey(2026, 12, 7), hdKey(2026, 12, 7), [{ key: hdKey(2026, 12, 7), mk: 'FX', n: 'Maintenance', half: true, src: 'broker' }]), []).ok"))
check("plain wording", await q("() => holSay({ mk: 'US', n: 'Day after Thanksgiving', half: true }) === 'US half day (Day after Thanksgiving)'"))
```

- [ ] **Step 2: Run** `bash tests/runall.sh t_hol` → FAILED (`tradeDayKey is not defined`).
- [ ] **Step 3: Implement** `tradeDayKey`, `ffHolidays`, `holEntries`, `tradeDay`, `holSay` in core with the signatures above.
- [ ] **Step 4: Run** `bash tests/runall.sh t_hol t_dst` → pass.
- [ ] **Step 5: Commit** — "The trade-day call: merge and session-clock day".

### Task 3: The broker's holiday list from cTrader

**Files:**
- Modify: `index.html` core, after `ctSpec` (≈ line 2695)
- Modify: `tests/mock.py` (the 2116 handler ≈ line 209)
- Test: `tests/t_hol.py` (part 3)

**Interfaces:**
- Consumes: `CT.symbols`, `ctNorm`, `ctReq(2116, { ctidTraderAccountId, symbolId: [...] })` → `{ symbol: [{ symbolId, holiday: [{ name, holidayDate, isRecurring, startSecond, endSecond, scheduleTimeZone }] }] }`.
- Produces:
  - `const HOL_SYMS = { US: ["NAS100", "US500", "US30"], UK: ["UK100"], EU: ["GER40", "EU50"], JP: ["JPN225", "JP225"], HK: ["HK50"], AU: ["AUS200"], CA: ["CA60", "CAN60"], CH: ["SWI20"], FX: ["XAUUSD", "EURUSD"] }` (the first name present in `CT.symbols` per market; for `FX`, every name present).
  - `brokerHolidays(bySym, fromKey, toKey)` → `[{ key, mk, n, half, src: "broker" }]` from `{ US: [holiday...], ... }`; `holidayDate` is already a day key; `isRecurring` repeats the month/day every year in range; `half` when `startSecond`/`endSecond` are set and don't span the whole day.
  - `async ctHolidays(force)` → `{ at, bySym, count, markets }` (`bySym` keyed by market: `{ US: [holiday...], ... }`; `count` = holidays, `markets` = markets with at least one), cached in localStorage `finder-hol` and reused for 24 h unless `force`; throws `Error("cTrader isn't connected")` when `CT.state !== "ready"` (it never connects by itself).

- [ ] **Step 1: Mock** — in `tests/mock.py`'s 2116 reply, add `"holiday"` lists from a module-level `CT_HOL = {"NAS100": [{"holidayId": 1, "name": "Thanksgiving", "holidayDate": (date(2026, 11, 26) - date(1970, 1, 1)).days, "isRecurring": False, "scheduleTimeZone": "America/New_York"}, {"holidayId": 2, "name": "Day after Thanksgiving", "holidayDate": (date(2026, 11, 27) - date(1970, 1, 1)).days, "isRecurring": False, "startSecond": 46800, "endSecond": 86400, "scheduleTimeZone": "America/New_York"}], "UK100": [{"holidayId": 3, "name": "Boxing Day", "holidayDate": (date(2026, 12, 28) - date(1970, 1, 1)).days, "isRecurring": False, "scheduleTimeZone": "Europe/London"}], "XAUUSD": [{"holidayId": 4, "name": "Christmas", "holidayDate": (date(2025, 12, 25) - date(1970, 1, 1)).days, "isRecurring": True, "scheduleTimeZone": "UTC"}]}` (symbols missing from the dict get no `holiday`; `from datetime import date` at the top of `mock.py`).
- [ ] **Step 2: Add part 3 checks** — open a second page `pg2` that routes the cTrader socket with `ct_handler(OPTS)` and stores `finder-ctrader` as `tests/t_ctfeed.py` does, `await pg2.wait_for_function("() => CT.state === 'ready'")`, `q2 = lambda js: pg2.evaluate(js)`, then:

```python
r = await q2("() => ctHolidays(true).then(x => JSON.stringify({ c: x.count, m: x.markets }), e => 'err ' + e.message)")
check("broker list read", '"c":4' in r and '"m":3' in r, r)
check("recurring broker holiday repeats", await q2("() => brokerHolidays(JSON.parse(localStorage.getItem('finder-hol')).bySym, hdKey(2026, 12, 1), hdKey(2026, 12, 31)).some(h => h.mk === 'FX' && h.key === hdKey(2026, 12, 25))"))
check("broker half day", await q2("() => brokerHolidays(JSON.parse(localStorage.getItem('finder-hol')).bySym, hdKey(2026, 11, 27), hdKey(2026, 11, 27))[0].half === true"))
check("no cTrader: a clear error, not a crash", (await q("() => ctHolidays(true).then(() => 'ok', e => 'err')")) == "err")
```

- [ ] **Step 3: Run** `bash tests/runall.sh t_hol` → FAILED (`ctHolidays is not defined`).
- [ ] **Step 4: Implement** `HOL_SYMS`, `brokerHolidays`, `ctHolidays` in core (one 2116 request with all chosen symbol ids).
- [ ] **Step 5: Run** `bash tests/runall.sh t_hol t_ctfeed t_trade` → pass (the mock change must not break them).
- [ ] **Step 6: Commit** — "Read the broker's holiday list from cTrader".

### Task 4: The Market holidays tab

**Files:**
- Modify: `index.html` markup `#calTabs` (line 1238) and `<script id="extras">` calendar code (`calRender` ≈ 10532, binding ≈ 10563)
- Modify: `index.html` CSS (the calendar block near `.calup`)
- Test: `tests/t_hol.py` (part 4)

**Interfaces:**
- Consumes: Tasks 1–3; `calAll()`; `phtDay(ms)`; `CT.state`.
- Produces:
  - `HOL_SET_KEY = "finder-hol-set"`; `holSet()` → `{ markets: [...all nine], show: true, quiet: true, confirm: true }` merged with what's stored; `holSetSave(s)`.
  - `holToday(now = Date.now())` → `tradeDay(...)` for `tradeDayKey(now)`, using rules + `ffHolidays(calAll())` + the cached broker list.
  - `holRender()` fills `#calBody` when `calTab === "hol"`.

- [ ] **Step 1: Add part 4 checks** — on the first page (no cTrader), `await pg.clock.set_fixed_time(datetime.datetime(2026, 11, 26, 7, 42, tzinfo=UTC))` (3:42 PM PHT Thu), `await q("() => goPage('calendar')")`, click `#calTabs [data-ct="hol"]`:

```python
check("tab shows", await q("() => !!document.querySelector('#calTabs [data-ct=\"hol\"].on')"))
check("today banner says no trade", "No trade" in await q("() => document.querySelector('.holtoday').innerText") and "Thanksgiving" in await q("() => document.querySelector('.holtoday').innerText"))
check("ten weekday cards", await q("() => document.querySelectorAll('.holdays .holday').length") == 10)
check("Fri Nov 27 card is no trade", "No trade" in await q("() => document.querySelectorAll('.holdays .holday')[1].innerText"))
check("next no-trade days list Dec 24, 25, 28, 31, Jan 1", await q("() => ['Dec 24', 'Dec 25', 'Dec 28', 'Dec 31', 'Jan 1'].every(d => document.querySelector('.holnext').innerText.includes(d))"))
check("holiday table has rows for several markets", await q("() => new Set([...document.querySelectorAll('.holtbl [data-mk]')].map(r => r.dataset.mk)).size") >= 5)
check("views and filter hidden on this tab", await q("() => document.getElementById('calViews').hidden && document.getElementById('calFilterBtn').hidden"))
check("source line without cTrader", "rules" in await q("() => document.querySelector('.holsrc').innerText"))
await pg.click('.holmk [data-holmk="US"]'); await asyncio.sleep(0.2)
check("unticking the US makes today a trade day", "Trade day" in await q("() => document.querySelector('.holtoday').innerText"))
await pg.reload(); await ready(pg)
check("the choice survives a reload", await q("() => !holSet().markets.includes('US')"))
```

- [ ] **Step 2: Run** `bash tests/runall.sh t_hol` → FAILED.
- [ ] **Step 3: Implement.** Add `<button role="tab" data-ct="hol">Market holidays</button>` to `#calTabs`; `calRender` branches to `holRender()` for `"hol"` and hides `#calViews` and `#calFilterBtn` there (shown again on the other tabs). Layout and copy from the mockup (artboard "Home tab · Calendar: market holidays and trade days"):
  - `.holtoday` banner: no trade → `"No trade"` chip + `"<b>{holSay} is a bank holiday</b>, so no trading on any market today: Gold, NAS100, forex pairs and crypto."` (half day: `"<b>{holSay}</b>, so no trading…"`); trade day → `"Trade day"` chip + `"No market holidays today."`; with `missing` → `"… · can't check {labels}"`.
  - `.holdays`: the next 10 weekdays from today as `.holday` cards (weekday, date, chip, reason).
  - `.holnext`: the next no-trade days within 8 weeks.
  - `.holtbl`: rows `[data-mk]` with date, market label, holiday name, what happens ("Closed" / "Closes early"), and the day's call; market chips filter the rows (All + the nine + "Your broker").
  - `.holmk` rules card: the three rule lines from the mockup and one `[data-holmk]` toggle per market, saved with `holSetSave`.
  - "On holidays" switches bound to `show`, `quiet`, `confirm`.
  - `.holsrc` line: `"From Pepperstone: {count} holidays across {markets} markets · exchange rules · Forex Factory (this week)"`, or `"cTrader isn't connected: exchange rules and Forex Factory only"`; plus `"Crypto trades every day. Hong Kong and Korea dates come from a table for 2026–2027: check them against HKEX and KRX."`
  - When cTrader is ready, call `ctHolidays()` in the background and re-render.
- [ ] **Step 4: Run** `bash tests/runall.sh t_hol t_calview t_ffnote` → pass.
- [ ] **Step 5: Commit** — "Market holidays tab in the calendar".

### Task 5: The call around the app on no-trade days

**Files:**
- Modify: `index.html` UI script `tickClock` (≈ 3105) and `notify`/`ncAdd` (≈ 4224, 6425); charts markup `.chbar` (≈ 8360); extras Telegram wrapper (≈ 10761); trade script `cttPlace` (11555) and `mxtPlace` (11599)
- Test: `tests/t_hol.py` (part 5)

**Interfaces:**
- Consumes: Task 4's `holSet()`, `holToday()`, `holSay()`.
- Produces: `holQuietNow()` → boolean (`holSet().quiet && !holToday().ok`); `holOrderOK()` → boolean (true on trade days or when `confirm` is off; else `confirm("Today is a no-trade day (" + reasons + "). Place this order anyway?")`).

- [ ] **Step 1: Add part 5 checks** (clock still Thu Nov 26 2026, US ticked again):

```python
check("session note leads with the call", (await q("() => document.getElementById('sessNote').innerText")).startswith("No trade today"))
check("chart chip shows", await q("() => { goPage('charts'); tickClock(); return !document.getElementById('chHol').hidden; }"))
n0 = await q("() => document.querySelectorAll('#ncToasts .nctoast').length")
await q("() => ncAdd({ title: 'Test alert', kind: 'Setups' })")
check("quiet: logged, no pop-up", await q("() => NC[0].title === 'Test alert'") and await q("() => document.querySelectorAll('#ncToasts .nctoast').length") == n0)
pg.once("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
check("order asks and stops when declined", (await q("() => cttPlace({ x: { symbolId: 1 }, side: 'buy', type: 'market', lots: 0.01 }).then(() => 'placed', e => e.message)")) == "cancelled: today is a no-trade day")
await q("() => { const s = holSet(); s.confirm = false; holSetSave(s); }")
check("no question with confirm off", await q("() => holOrderOK()") is True)   # an unexpected dialog is auto-dismissed → False
```

- [ ] **Step 2: Run** `bash tests/runall.sh t_hol` → FAILED.
- [ ] **Step 3: Implement.**
  - `tickClock`: when `holSet().show` and today is no trade, `#sessNote` starts with `"<b>No trade today</b> · {holSay of the first reason}. "` before the NBB text.
  - Charts: `<span class="holchip" id="chHol" hidden>No trade today</span>` after `#chSymBtn`'s wrapper; shown/hidden from `tickClock` with the same condition; its title lists the reasons.
  - Quiet: `ncAdd` skips `ncToast` when `holQuietNow()`; `notify` skips `beep()` and the desktop notification; the Telegram wrapper skips `tgSend`. Use `typeof holQuietNow === "function" && holQuietNow()` (extras loads after the UI script).
  - Orders: first lines of `cttPlace` and `mxtPlace`, after the replay guard: `if (typeof holOrderOK === "function" && !holOrderOK()) throw new Error("cancelled: today is a no-trade day");` (`qtPlace` goes through these).
- [ ] **Step 4: Run** `bash tests/runall.sh t_hol t_nc t_trade t_qt t_mxtf t_dst t_charts` → pass.
- [ ] **Step 5: Commit** — "No-trade days: session note, chart chip, quiet alerts, order check".

### Task 6: Cloud watcher heads-up and quiet days

**Files:**
- Modify: `index.html` core (one function), `cloud/watch.mjs`, `cloud/watch.json`
- Test: `tests/t_hol.py` (part 6, Node)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `holHeadsUp(nowMs, counted)` in core → `{ id, text }` or `null`: only between 8:00 and 9:00 PM PHT (plain PHT clock time of the message), for the next weekday's key after `tradeDayKey(nowMs)`, when that day is not a trade day; `id = "hol|" + key`; text `"Tomorrow, {Fri Nov 27}, is a no-trade day: {holSay reasons joined by '; '}."` ("On Monday, …" when the next weekday is Monday).

- [ ] **Step 1: Add part 6 checks** — a helper `node(expr)` runs `node -e` with core loaded the way `cloud/watch.mjs` does (read `index.html`, slice `<script id="core">`, `vm.runInContext` with the same context object), defines `ALL = HOL_MKTS.map(x => x[0])`, and returns the printed `JSON.stringify(expr)` (`"null"` for null). Checks:

```python
check("8:10 PM Wed Nov 25: heads-up for Thanksgiving", "Thanksgiving" in node("holHeadsUp(Date.UTC(2026, 10, 25, 12, 10), ALL)?.text"))
check("8:10 PM Thu Nov 26: heads-up for the half day", "half day" in node("holHeadsUp(Date.UTC(2026, 10, 26, 12, 10), ALL)?.text"))
check("8:10 PM Mon Nov 30: nothing", node("holHeadsUp(Date.UTC(2026, 10, 30, 12, 10), ALL)") == "null")
check("3:00 PM Wed: nothing yet", node("holHeadsUp(Date.UTC(2026, 10, 25, 7, 0), ALL)") == "null")
check("Fri Dec 25 evening looks at Monday Dec 28", "Monday" in node("holHeadsUp(Date.UTC(2026, 11, 25, 12, 10), ALL)?.text"))
```

- [ ] **Step 2: Run** `bash tests/runall.sh t_hol` → FAILED.
- [ ] **Step 3: Implement** `holHeadsUp` in core; in `cloud/watch.mjs` add `holHeadsUp, tradeDay, tradeDayKey, holEntries, HOL_MKTS` to the exported `__F`; read `CFG.holidays` (`{ "headsUp": true, "quiet": true, "markets": [all nine] }`, added to `cloud/watch.json` with a `_help` sentence); send the heads-up through `send(id, text)`; when `quiet` and today is not a trade day, skip every other send. Mention it in the `_help` text.
- [ ] **Step 4: Run** `bash tests/runall.sh t_hol` → pass; `WATCH_DRY=1 WATCH_NOW=$(node -e 'console.log(Date.UTC(2026,10,25,12,10))') node cloud/watch.mjs` prints a `[dry run]` heads-up (network errors from MEXC/Forex Factory in the container are fine).
- [ ] **Step 5: Commit** — "Cloud watcher: no-trade heads-up and quiet days".

### Task 7: Version, notes, regression

**Files:**
- Modify: `version.json`, `index.html`, `sw.js` (via `bump-version.sh`), `CLAUDE.md`

- [ ] **Step 1:** Add a CLAUDE.md line under Calendar: "Market holidays tab (`calTab = "hol"`, `holRender`): rules `holRules`/`HOL_TABLE` (HK, KR 2026–2027), broker list `ctHolidays`/`brokerHolidays` (cached `finder-hol`), merge `holEntries`, call `tradeDay`/`tradeDayKey` (session clock, before 5 AM = previous day), settings `finder-hol-set`; no-trade days quiet `ncAdd`, ask in `cttPlace`/`mxtPlace` (`holOrderOK`), cloud heads-up `holHeadsUp`. Test `t_hol`."
- [ ] **Step 2:** `TZ=Asia/Manila bash bump-version.sh`.
- [ ] **Step 3:** `bash tests/runall.sh t_hol t_smoke t_dst t_calview t_ffnote t_nc t_trade t_qt t_mxtf t_ctfeed t_charts t_start` → all pass.
- [ ] **Step 4:** Commit "Market holidays: version and notes", then `git push -u origin claude/loving-faraday-eva9zo`.
