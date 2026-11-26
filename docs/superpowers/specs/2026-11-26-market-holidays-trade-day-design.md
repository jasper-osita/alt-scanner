# Market holidays and the trade-day call

## Why
Jas wants to know before the day starts whether it's a day to trade. A bank holiday or a half day in any major market
thins liquidity and breaks his setups (Gold 5m in London, NAS100 1m at the US open, forex, crypto). His rule: **a bank
holiday or a half day in any market means no trade on anything that day.** The app only knows US exchange holidays
today (`usHolidays`, rules) plus Forex Factory's holiday rows for the current week.

## Where this fits
First of four pieces of the chart-first redesign (mockups: https://claude.ai/artifact/CzLyyYsAivYdgtDQdWykv8, artboard
"Home tab · Calendar: market holidays and trade days"): 1. this, 2. tabs and the home tab, 3. the chart tab in layout A,
4. the phone layout. This piece lands in today's Economic Calendar page; piece 2 later moves that page into the home tab.

## Goals
- A third Calendar tab, **Market holidays**, next to Forex Factory and What moves the Nasdaq.
- One call per day: **Trade day** or **No trade**, with the reason (which market, which holiday, closed or half day).
- On that tab: a Today banner; your trade days for the next two weeks (weekdays); the next no-trade days (8 weeks);
  a holiday list for every market with market filter chips; a rules card with "Markets that count" toggles; "On holidays" switches.
- The day's call also shows in the Overview session note and as a chip on the Charts page on no-trade days.
- On no-trade days: alerts are quieted, placing an order asks for confirmation, and Telegram warns the evening before.

## Non-goals
- No "light day" and no per-setup calls (Jas: two outcomes only).
- No change to the Market Hours card ("holidays not included" stays until piece 2 or later).
- No order blocking: a confirmation only.
- Crypto exchange maintenance windows are not tracked.

## Anti-goals
- Calling a real holiday a **Trade day**. When a counted market has no data for a date, the card says so instead of
  showing Trade quietly.
- Network calls or real orders in tests; any token or secret in code.

## The rules (decided by Jas)
- **No trade**: any counted market is closed for a holiday, or closes early (half day), that day. It covers everything:
  Gold, NAS100, forex pairs and crypto.
- **Trade day**: every other weekday. Weekends aren't shown.
- **Markets that count**: US, UK, Euro area, Japan, Hong Kong, Korea, Australia, Canada, Switzerland. All on by default;
  unticking one stops its holidays from cancelling the day.
- **Which day**: a holiday dated D in a market's own calendar makes trading day D no trade, read on the session clock
  (`sessD`: Asia 8 AM through NY PM, New York + 12h; every market's D session falls inside it). Hours before 5 AM on
  the session clock belong to the previous trading day (NY PM). Never plain PHT dates.

## Approaches considered (data)
1. **Broker holiday lists + built-in rules + Forex Factory (picked).** cTrader already returns each symbol's holidays in
   the symbol details the app fetches for position sizing (payload 2116, `ctSpec`); the app ignores them today. That is
   exactly what Pepperstone closes. Built-in rules cover markets the broker doesn't list (Korea), work without cTrader,
   and let the cloud watcher make the same call. Forex Factory's holiday rows cross-check the current week.
2. Built-in rules only. Works offline and is fully testable, but lunar-calendar holidays (Hong Kong, Korea) need a
   hand-kept table every year, and it can't see a closure the broker adds.
3. A public bank-holiday web service through the relay. No yearly upkeep, but its Hong Kong coverage couldn't be
   confirmed from here, and bank holidays aren't exchange closures (Frankfurt shut on Dec 24 and 31, NYSE on Good Friday).

## Design
### Data (core, DOM-free where it can be)
- **Rules** (`<script id="core">`, next to `usHolidays`): per market, full closes and half days for a year, as
  `{ m, d, n, half }`. US reuses `usHolidays`. UK (LSE), Euro area (Xetra), Japan (JPX), Hong Kong (HKEX), Korea (KRX),
  Australia (ASX), Canada (TSX), Switzerland (SIX): fixed dates, Easter-based, nth weekday, weekend substitutes, Japan's
  equinox formula. Lunar-calendar dates (Hong Kong, Korea) from a table for 2026–2027; past the table the card says
  "Hong Kong dates after 2027 aren't loaded".
- **Broker**: when cTrader is connected (own or shared login), read `symbol.holiday[]` (`name`, `holidayDate` in days
  since 1970-01-01, `isRecurring`, `startSecond`/`endSecond`, `scheduleTimeZone`) for one symbol per market plus
  XAUUSD and EURUSD, matched by name like the market picker does. An entry with start/end seconds is a half day,
  otherwise a full close. Cache in localStorage (`finder-hol`), refresh once a day.
  **Unverified:** whether Pepperstone fills this list. The tab shows "From Pepperstone: N holidays across M markets";
  if it's empty, the rules carry the call.
- **Forex Factory**: this week's Holiday rows map by currency (USD→US, GBP→UK, EUR→Euro area, JPY→Japan, AUD→Australia,
  CAD→Canada, CHF→Switzerland; others not counted).
- **Merge**: one entry per (market, day) with name, closed or half, and its sources. Any source saying closed or half
  counts; the broker's hours win for the description.
- **The call**: `tradeDay(dayKey, counted)` → `{ ok, why: [...] }`, in core.

### Screen
- `calTab = "hol"` in the Calendar, laid out as in the mockup: Today banner, two weeks of day cards, next no-trade days,
  the holiday table (date, market, holiday, what happens in PHT, the day's call) with market chips, the rules card,
  the switches, and a source note ("Crypto trades every day. Pepperstone's hours from your cTrader account…").
- The Overview session note leads with the call on a no-trade day; the Charts page toolbar shows a "No trade today" chip.
- Settings in localStorage `finder-hol-set`: `{ markets, show, quiet, confirm }`.

### Behaviour on no-trade days
- **Quiet**: `ncAdd` still logs every alert, but sends no Telegram, sound or pop-up. The cloud watcher skips its alerts too.
- **Confirm**: `cttPlace`, `mxtPlace` and `qtPlace` ask "Today is a no-trade day (US Thanksgiving). Place this order
  anyway?" once per order. The replay guard already sits at the same spot.
- **Telegram heads-up**: the cloud watcher sends "Tomorrow is a no-trade day: …" at 8 PM PHT the evening before, rules only
  (no cTrader in the cloud). On by default; switched off in `cloud/watch.json`.

## Testing
- `t_hol`: rule dates for every market in 2026–2027 against known closures (US Thanksgiving 2026-11-26, its half day
  2026-11-27, UK Boxing Day moved to 2026-12-28, Japan 2027-01-11, Christmas and New Year), the session-clock day, the
  call with a market unticked, the merge with a mocked broker list (2117 with `holiday[]` in `tests/mock.py`), the tab
  rendering, quiet alerts, and the order confirmation (mocks only, no real orders). Fixed clock.
- Cloud watcher: the 8 PM heads-up in a dry run with `WATCH_NOW`.

## Decided by Jas
- Bank holiday or half day in any market = no trade on everything; two outcomes only.
- Every market counts by default.
- Build this piece before the rest of the redesign.

## My calls (check these)
- The broker's list is the main source, the rules are the fallback, and Forex Factory cross-checks.
- Quiet means logged but silent, not dropped.
- The Telegram heads-up goes out only before a no-trade day, not every evening, and lives in the cloud watcher's settings.
- Missing data for a counted market is shown as such, never as a Trade day.

## Left to the builder
- Which Pepperstone symbol stands for each market; exact copy and table layout; whether `finder-hol-set` joins the Sync parts.
