# Gold bot: rules (draft 1)

Status: **for review**. No code yet. Once Jas signs off, these rules are the single source of truth: the
Finder backtest and the cTrader cBot both implement exactly this, and a change here comes before a change in code.

## Decisions so far

| Question | Answer |
|---|---|
| Market | XAUUSD only, Pepperstone cTrader |
| Where it's built | Rules tested in The Finder on cTrader Gold history, then ported to a C# cBot that trades |
| Account | Prop firm challenge, firm not picked yet (so strict defaults below) |
| Automation | Fully automatic |
| Hold time | Intraday: flat before the daily break, never held overnight or over the weekend |
| Ideas to test | A: session breakout, B: trend following, C: trading the news |
| Hours | Any time; the tests decide which hours to keep |
| Risk per trade | 0.5% |

## Why these three should work on Gold (the hypotheses)

Each strategy rests on a reason, written down before testing, so we know what we're checking for and can drop
a strategy whose results don't match its reason.

- **A. Session breakout.** Gold volume follows the clock. Asia is thin, so price drifts in a tight range. When
  London (the LBMA physical market) and later New York (COMEX futures, US data) open, real order flow arrives,
  and price usually leaves that range in one direction and keeps going for a while.
- **B. Trend following.** Gold's big moves come from slow macro forces: real yields, the dollar, central-bank buying,
  safe-haven demand. Those don't flip in a day, so an hourly trend tends to continue, and a pullback against it
  is a cheaper entry.
- **C. News momentum.** CPI, NFP and FOMC reprice rates and the dollar in one print. Algorithms react within
  seconds, and the first push often carries on for several minutes as stops get run and late traders pile in. C rides
  that push on M1 and gets out as soon as it stalls. The risk is a spike that reverses straight away, and the wide spread.

Caution on B: from 2024 to 2026 Gold was in a huge bull run. A trend strategy will look great long and say little about
how it behaves in a range or a downtrend. Every report splits longs and shorts and shows each year on its own.

## Time

The Philippines has no daylight saving, but London and New York do, so their opens move one hour in PHT twice a
year. The bot defines windows in **London or New York time** and converts; reports still show Jas's PHT sessions.

- Daily break: read from the symbol's trading schedule in cTrader (about 05:00–06:00 PHT in US summer,
  06:00–07:00 in US winter). **Flat 15 minutes before it.** No new trades in the first 30 minutes after it (spreads are wide).
- Friday: flat 60 minutes before the weekend close.

## Strategy A: session breakout

Three windows, tested as separate variants:

| Variant | Range built from | Breakout allowed | Time exit |
|---|---|---|---|
| A1 Your sessions | 08:00–12:00 PHT | 12:00–18:00 PHT | 00:00 PHT |
| A2 London open | daily reopen → 08:00 London | 08:00–11:30 London | 16:00 London |
| A3 New York open | 07:30–09:30 New York | 09:30–12:00 New York | 16:00 New York |

Rules (M5 bars):
1. Range = highest high and lowest low of the range window. ATR = 14-day ATR on D1.
2. Skip the day if the range is narrower than 0.15 × ATR (noise) or wider than 0.6 × ATR (the move already happened).
3. Entry: the first M5 **close** beyond the range high (long) or low (short) during the breakout window. Enter at the
   next bar's open. One trade per variant per day.
4. Stop: the middle of the range. If that's more than 0.5 × ATR away, skip.
5. Target: 2R. Otherwise exit at the time exit or before the daily break, whichever comes first.
6. Trend filter (tested on and off): only take the break in the direction of the H1 trend as defined in B.

## Strategy B: trend following

1. Trend on H1 = your AOTS: EMA 20 > 50 > 100 and the H1 close above EMA 20 → longs only. Mirror for shorts.
   No stack, no trade.
2. Pullback on M5: at least 2 M5 closes below the M5 EMA 20 (for a long).
3. Entry: an M5 close back above EMA 20 **and** above the previous bar's high. Enter at the next bar's open.
4. Stop: lowest low of the pullback minus 0.1 × ATR(H1, 14). Skip if the stop is under 0.25 × or over 1 × ATR(H1).
5. Management: at +1R move the stop to break-even. Exit on an M5 close below the M5 EMA 50, at 4R, or before the
   daily break, whichever comes first.
6. At most 2 trades a day; after a loss, wait for a fresh pullback.

## Strategy C: news momentum (M1 quick play)

Follow the release candle while it's still moving, and get out on M1 as soon as the move stalls.

Events, two variants fixed now:
- **C1**: CPI, NFP, FOMC decision.
- **C2**: C1 plus core PCE, retail sales, ISM manufacturing and services, and the first GDP estimate (a bigger sample).

The Finder only has this week's calendar, so the backtest needs a dated table of past releases with exact times
(from the BLS, BEA, ISM and Fed schedules; `FOMC_DATES` covers part of it).

1. Pre-news price **P0** = the mid price (halfway between bid and ask) 5 seconds before the release.
2. Trigger: within the **first 2 minutes** after the release, the mid moves at least **0.3 × ATR(H1, 14)** away from P0
   (about $5–8 at current prices). Buy if it's up, sell if it's down, **at market, mid-candle**. One trade per event:
   whichever side triggers first.
3. Spread guard: no entry while the spread is over $1.00. If it's still too wide when the 2 minutes are up, skip the event.
4. Stop: back at P0 (price back where it was before the news means the move failed), but never more than the
   trigger distance + $1.00 from the fill, so a bad fill can't blow up the risk. Lots are sized on that maximum.
5. Exit, trailing on M1: stay in while the move holds. Close at market on the first M1 close below the previous M1
   candle's low (long) or above its high (short). Hard cap: 15 minutes after entry. No fixed target.
6. A and B keep trading around news as normal. The backtest tags any A/B trade open during a release, so we can
   see whether news helps or hurts them.

Why C needs tick data: a mid-candle entry can't be tested honestly on M1 bars. A bar's high and low don't show
whether price reached the trigger before or after it reversed, and the spread at the release is most of this trade's
cost. cTrader keeps historical bid and ask ticks, so the backtest pulls the real ticks from 5 minutes before to 20
minutes after each release (about 110 events for C1 over 3 years, a small download).

Prop firm note: C opens, and usually closes, within minutes of high-impact news. That is exactly what many firms
restrict on funded accounts (FundedNext's funded accounts, for example). So either pick a firm that allows news
trading on funded accounts, or run C only during the challenge or on your own account. This becomes a filter when
choosing the firm.

Speed matters here: the cBot should run on cTrader Cloud or a server near Pepperstone's, not on the Mac in the
Philippines, where every order would arrive a fraction of a second late.

## Risk and prop guard (shared by all strategies)

Defaults while no firm is picked: the firm allows 4% daily loss and 8% total. The bot stops itself well before either.

- Size: 0.5% of the day's starting balance per trade. Lots = risk ÷ (stop distance × 100 oz), rounded **down**
  to 0.01. If even 0.01 lots risks more than 0.6%, skip the trade.
- At most one position per strategy, and at most 1% total open risk.
- **Daily stop: −2%** (closed + floating, from the day's start) → close everything, no new trades until the daily reset.
- **Total stop: −6%** from the starting balance → close everything, halt, alert. Restarting needs Jas.
- Every order goes out with its stop and target attached on the broker's side, so a disconnect never leaves a trade
  unprotected. On restart the cBot finds its open trades by label and carries on.
- Telegram message on every open, close, daily stop and halt. The bot token is a cBot parameter, never in code.

## Costs in the backtest

cTrader bars are bid prices, so the backtest adds the spread to buys. Defaults (to be replaced with the real
figures from Jas's account):

| A and B | Normal | Daily reopen, and 5 min either side of news |
|---|---|---|
| Spread | $0.20 | $0.60 |
| Slippage on stops and market orders | $0.10 | $0.50 |
| Commission | $7 per lot round trip | same |

C uses the real bid and ask from the ticks, plus $0.30 slippage on every entry and exit (the bot is never first in
line at a release), plus the same commission.

If a single M5 bar touches both the stop and the target, the backtest assumes **the stop was hit first**.

## How we test (and avoid fooling ourselves)

- Data: XAUUSD M5 and H1 from cTrader, October 2023 to now, cached locally. For C: M1 bars and bid/ask ticks
  around each release.
- **Develop** on Oct 2023 → Sep 2025. **Out-of-sample**: Oct 2025 → now, run once per strategy, at the end. Looking
  at it earlier spoils it.
- The variants above are fixed in advance. Every extra variant we try gets written into this doc, because the more
  we try, the more likely a winner is just luck.
- Robustness: move every number (0.15, 0.6, 2R, EMA lengths…) by ±20%. A real edge stays profitable across that
  range; a lucky one only works at the exact value we picked.

A strategy goes forward only if, **after costs**:

| Check | Develop period | Out-of-sample |
|---|---|---|
| Trades | ≥ 150 | ≥ 40 |
| Profit factor | ≥ 1.3 | ≥ 1.15 |
| Average per trade | ≥ +0.15R | > 0 |
| Max drawdown at 0.5% risk | ≤ 5% | ≤ 5% |
| Worst day | ≥ −2% | ≥ −2% |
| Still profitable without the top 5% of winners | yes | — |
| Profitable years | each full year | — |

C is the exception on trade count: C1 has only about 110 events in 3 years, so its minimums are ≥ 50 trades
to develop and ≥ 15 out-of-sample. Its verdict will be the least certain of the three, which is why C2 exists.

Then a **prop check**: shuffle the trade sequence 10,000 times and count how often an account reaches +8% before
it hits −4% in a day or −8% in total. That pass rate is the number that matters for a challenge.

## Build plan

1. **This doc**, reviewed and agreed.
2. **Gold history**: fetch XAUUSD M5/H1 from cTrader in pages (`ctKlines` with `toMs`), cache in IndexedDB, plus the
   news-date table and, for each release, M1 bars and bid/ask ticks from cTrader.
3. **Gold backtest page** in The Finder (Lab): bar-by-bar, no look-ahead, costs and prop guard as above. Results by
   variant, year, session, weekday, long/short, news/no news, plus the prop pass rate. Trades can be opened on the chart.
4. **Robustness and out-of-sample** run; we keep 0–2 strategies.
5. **cBot (C#)**: the same rules and guard. Before trusting it, run it in cTrader's own backtester over the same dates;
   its trade list must match The Finder's (small price differences only). For C, use the tick-data mode and give
   the cBot the same news table.
6. **Demo for 4+ weeks**: compare real fills and slippage with the backtest's assumptions. Then the challenge.

## Open questions (later)

- Pepperstone account type (Razor or Standard) and currency, for the real cost figures.
- A2/A3 use the real London/NY opens instead of your fixed PHT London 12:00. Keep both, or drop A1?
- Once a firm is chosen: its daily-loss basis (balance or equity), reset time, news rule, and any consistency rule.
