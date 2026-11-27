# Trading day: when to be present and when to stay quiet

Replaces `2026-11-26-market-holidays-trade-day-design.md` (its holiday rules carry over as one input; its blanket
"a bank holiday anywhere = no trade on everything" rule is dropped).

## Why
Jas no longer trades one fixed session. He looks for entries in Asia and London on the 15-minute chart and holds for the
day. What he needs every day is: **when to participate and when to stay quiet**, and **where the opportunity is** when he
does. Thin liquidity (holidays, half days, dead hours) makes markets range-bound, and choppy or wicky markets waste
entries. The app should tell him, for the whole trading day and the week, which markets are worth his attention and when.

## Where it fits
Mockups: https://claude.ai/artifact/CzLyyYsAivYdgtDQdWykv8, artboards "Home tab · Trading day: today" and
"Home tab · Trading day: this week". In the redesign it's an item in the home tab's menu (Overview, **Trading day**,
Calendar, Fundamentals). The home tab isn't built yet, so this lands first as a page in today's sidebar (group MARKET,
"Trading day") and moves into the home tab with piece 2 of the redesign.

## Goals
- **Now line**: be present or stay quiet right now, which markets to look at or stay out of, and the next windows
  (session opens, releases, rollover).
- **The day's call** per market: Tradeable, Tradeable until London, Likely quiet or Closed, with a written summary for the
  day (Asia, London, New York, past years, what it means for him) and a live check at each 15-minute close.
- **Best places to look right now**: markets ranked by movement left today, clean trend and clean candles; choppy and
  wicky markets marked "Stay out" and pushed to the bottom.
- **Hour by hour** (the screenshot Jas shared, extended): usual range per hour of the trading day, today so far, the
  forecast for the rest of today, scheduled releases marked; plus day of the week and the last 3 months. One market at a
  time; clicking a market anywhere on the page switches it.
- **This week**: a grid of his markets Monday to Friday (call, Asia/London/New York, % of a normal day), a summary of the
  week, each day's story with whether the call was right, and thin stretches ahead (8 weeks).
- **Nudges**: a window opening in 15 minutes, a market waking up, everything gone flat, the rollover warning, and the
  evening heads-up before a closed or quiet day; in the app and on Telegram.
- **Guard**: confirm before placing an order on a "Stay out" market or a Closed/Likely quiet market for the day.
- **Your best hours**: his results by hour of the day, weekday, and thin days versus normal days, from his own trades.

## Non-goals
- Crypto (it has its own section). Markets here: forex, metals, energy and indices.
- Blocking orders or trading for him; changing NBB Watch or the cloud watcher's NBB settings (a separate follow-up,
  since they're still built around Gold 5m in London and NAS100 1m at the US open).
- Monthly or quarter-end flows and the volatility regime of the month (later).

## Anti-goals
- A quiet "Tradeable" when the data for a market is missing: say what's missing instead.
- Numbers without their footing: every estimate from past holidays shows how many past examples it rests on.
- Nudge noise: at most one nudge per kind per market per hour, each kind switchable.

## Decided by Jas
- Thin liquidity is the reason to stand aside; the call is per market, not one rule for everything.
- The whole trading day and the week, not one session; 15-minute execution, day holds.
- All four extras in the first version: Now line and nudges, news on the forecast, opportunity ranking, best hours.
- Rank the best market to participate in, and keep him out of choppy and wicky markets. No crypto on this page.
- A separate Trading day page with Today and This week.

## Approaches considered
1. **Layered (picked):** a fixed map of which centres move each market as the starting point, past holidays and normal
   days measured from candles to confirm or overrule it, and a live check during the day.
2. Fixed map only: simple and predictable, but a guess, never checked against how the markets actually behave.
3. Live check only: the most direct, but it knows nothing until the session has started, so no plan for the day or week.

## Design

### The trading day and its hours
- One trading day = 24 hourly bins on the session clock starting at session 8:00 (Asia open: 9 AM PHT in winter,
  8 AM in summer). Day key from `sessD(ms - 8h)`. PHT labels come from `sessLbl`, so they shift with New York's
  daylight saving like the rest of the app. Rollover = 5 PM New York (6 AM PHT in winter, 5 AM in summer).
- Markets: his watchlist minus crypto; if that's empty, Gold, Silver, EURUSD, GBPUSD, USDJPY, AUDUSD, NAS100. Candles come
  from the same source the boards use for that market (Pepperstone through cTrader when connected, else MEXC or Binance).

### Measurements (core, DOM-free)
- **Normal**: for each market, the median range per hourly bin and the median day range over the last 20 trading days
  that weren't holidays, from 15-minute candles (also the source of today so far).
- **Past holidays**: from 1-hour candles, about two years, cached in the existing IndexedDB cache. For each market and each
  centre (US, UK, Euro area, Japan, Hong Kong, Korea, Australia, Canada, Switzerland), the median ratio of the day
  range and of each bin on that centre's past holidays against the 20 normal days before, with the number of examples.
- **Centre map** (starting point when a pairing has fewer than 2 examples): Gold, Silver → London, New York; EURUSD →
  London, Euro area, New York; GBPUSD → London, New York; USDJPY → Japan, New York; AUDUSD → Australia, New York;
  NAS100, US500, US30 → New York (its own exchange: Closed on US closures); GER40 → Euro area; JP225 → Japan;
  HK50 → Hong Kong; UK100 → UK. A closed centre in the map scales its session's bins to 0.5 and half days to 0.7.
- **Holidays**: the rules from the replaced design (nine markets, Hong Kong and Korea tables for 2026–2027), the broker's
  holiday list from cTrader, and Forex Factory's holiday rows.
- **Releases**: high and medium impact events from the calendar for the currencies that move each market. Their hour is
  scaled ×1.8 (high) or ×1.3 (medium) and the hour before ×0.8, until the app has measured at least 3 past occurrences of
  the same event, then the measured ratio. Measured ratios are kept per event name in localStorage, because the calendar
  only keeps 3 weeks.
- **Structure**: from the forex/metals/indices scan (`MACRO.rows`): `rate()` "Chop" or a "Tangled" 1H stack = **choppy**;
  `wicky` = **wicky**; 1H and 15m stack direction = trend.

### The calls
- **Forecast** for today per bin = normal × holiday factors × release factors; forecast day range = its sum scaled to the
  normal day range.
- **Day call** per market: **Closed** when its own exchange is shut; **Likely quiet** when the forecast day range is under
  70% of normal; **Tradeable until London** when Asia and London bins are normal but New York's are under 70%;
  otherwise **Tradeable**. The page's verdict for the day: thin day if most markets are below Tradeable.
- **Live**, at each 15-minute close: range so far against a normal day at the same point. "Moving normally" at 80% or
  more, "Quiet so far" under 60%, "Waking up" when the current hour runs at 2× its usual.
- **Room left** = 1 − today's range so far ÷ forecast day range.
- **Now** per market: Stay out: choppy / Stay out: wicky (first); Quiet till {next window} when the coming hour is
  usually quiet; Wait for {time} when a release is within 2 hours and the market is quiet before it; else Look here.
  Ranking among Look here: room left × trend clarity. The page's Now line: Be present if any market is Look here,
  else Stay quiet, plus the next windows (London open, New York open, releases, rollover).

### Screens
- **Today** and **This week**, laid out as in the mockups. The day's summary is written from the calls (one sentence per
  session, the past-years line with its example count, and a "For you" line that uses his best hours when there are enough
  trades). The same Now verdict shows as a chip on the Charts page and in the Overview session note.
- **This week**: past days show the measured % of a normal day and whether the call was right; today and later show the forecast.

### Nudges and the guard
- New alert kind "Trading day" in `NC_KINDS`, sent through `ncAdd` (so the existing Telegram forwarding and kind filter
  apply). Window opening, waking up, gone flat and the rollover warning come from the app while it's open. The cloud
  watcher sends the schedule-based ones (window opening, releases, rollover, the evening heads-up) when the app is closed.
- On a Closed or Likely quiet day for a market, alerts about that market are logged but silent (switch, on by default).
- `cttPlace` and `mxtPlace` ask for confirmation when the market is "Stay out" or Closed/Likely quiet today (switch,
  on by default). `qtPlace` goes through them.

### Your best hours
- From his closed trades (`twLoadHist`: cTrader deals and MEXC history), crypto left out, last 90 days. By entry hour bin,
  weekday, and thin versus normal days (using the stored day calls). Result per trade in R when the app knows the stop
  (orders placed in The Finder record their stop at placement), otherwise as % of the account. Bins with fewer than 5
  trades are greyed out.

## Pieces, in order
1. **The day's call**: holiday rules, measurements, forecast, calls, Today and This week, summary, live check.
2. **Now line, nudges, releases on the forecast.**
3. **Opportunity ranking and the Stay out guard.**
4. **Your best hours.**

## Testing
- Core functions on fixed candle fixtures and a fixed clock: bins and DST, normal profile, holiday ratios, release factors,
  each day call, live thresholds, room left, Now calls and ranking.
- Playwright with the existing exchange and cTrader mocks: the page, switching markets, the week grid, nudges through
  `ncAdd`, the order confirmation (mocks only, no real orders), best hours from mocked deals.
- Cloud watcher heads-up and schedule nudges as pure core functions.

## My calls (check these)
- Thresholds: Likely quiet under 70% of a normal day; live "Moving normally" at 80%+, "Quiet so far" under 60%, "Waking
  up" at 2× the usual hour.
- Release factors ×1.8 high, ×1.3 medium, ×0.8 the hour before, until measured.
- History on 1-hour candles (two years), today and normal days on 15-minute candles.
- Best hours in R only when the stop is known, else % of the account.
- The cloud watcher sends only schedule-based nudges; live ones need the app open.

## Left to the builder
- Exact copy of the summaries and nudges; table and chart layout details; cache sizes; how the fallback market list is stored.
