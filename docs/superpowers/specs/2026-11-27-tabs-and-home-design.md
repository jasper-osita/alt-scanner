# Tabs and the Home tab (redesign, piece 1)

## Why
Jas wants The Finder to replace TradingView as the place he charts and trades every day. TradingView is a chart with
everything else beside it; The Finder today is a sidebar of pages with Charts as one of them. The redesign makes it
chart-first: browser-style tabs across the top, each tab a whole page (a chart or any page), several charts open at
once, and a pinned Home tab that gathers the pages he reads the market with.

## Where it fits
Mockups: https://claude.ai/artifact/CzLyyYsAivYdgtDQdWykv8 — "A · Workstation with tabs: a chart tab", "A · A page in its
own tab, with the + menu open", and the "Home tab · …" artboards (Overview crypto, Overview forex, Calendar,
Fundamentals, Trading day today, Trading day this week).

The redesign is three pieces, in this order:
1. **Tabs and Home** (this document).
2. **The chart tab in layout A**: drawing tools on the left, the right-hand panel with its icon strip (watchlist, alerts,
   boards, calendar, news, order ticket), the positions drawer under the chart, range buttons, "show beside a chart".
3. **The phone layout.**

## Decided by Jas
- Chart-first, layout A (Workstation) as the base; set aside the ICT True Day indicator for now.
- A tab row across the top, like a browser. **+** opens a new chart or any page in its own tab. Every tab is a whole page.
- A small **Home** tab (house icon) pinned at the far left. Inside it, a left menu per section: **Overview** (Crypto;
  Forex, metals & indices), **Trading day** (Today; This week), **Calendar**, **Fundamentals**, each with every detail the
  original page has.
- **Chart tabs keep moving live** in the background, built the "in between" way (approach 3 below): one chart screen,
  every chart tab keeps its candles updating, each tab label shows the live price and change and lights up when an alert
  fires on that market, and switching shows the chart instantly, already current, at the zoom and position left.
- **Drawings stay per market** (the exact feed: Pepperstone Gold and MEXC Gold are separate) and show on every tab of
  that market; switching tabs never removes them.
- Tabs reopen as left and carry over to other devices through Sync.
- Phones stay as they are until piece 3.
- **The boards' Chart buttons open The Finder's own chart** (a chart tab), not TradingView. Today's "Open Charts In"
  setting (New Tab / Copy Link / TradingView Helper App, used by `openTV` and `chartBtn`) becomes **"Open charts in"**:
  a chart tab here (the default; jumps to a tab already showing that market), the chart tab I used last, TradingView in a
  browser tab, the TradingView Helper App, or copy the TradingView link. It stays where it is in the scan settings bar,
  which also shows on Home's crypto Overview (as drawn).

## Calls I made (Jas saw these as defaults and didn't object; each can change)
- The app opens on the **last tab** you had open (today it opens on Charts).
- **Chart tabs: as many as you like**, up to 12 (my cap, to bound the live feeds). **A page opens once**: opening it again
  jumps to its tab.
- **Indicators and chart style stay shared** across chart tabs, as today.
- A **half-finished drawing is dropped** when you switch tabs (as when you change market today); finished drawings are
  never touched.
- The right end of the tab row holds search, the bell, Scan now, the Live badge, and a ⋯ menu with Auto-refresh, Copy for
  Claude, Export JSON and Settings (the current top bar's controls).
- **Replay ends** when you leave its chart tab (replay blocks orders; carrying it hidden across tabs is a trap).
- **"Open in a chart" from any page** (a brief, an alert, the coin panel, Trade) goes to a chart tab already showing that
  market if there is one, else opens a new chart tab.
- **What syncs:** which tabs are open, their order, each chart tab's market and Home's section. Each device keeps its own
  timeframes, layout, zoom and open tab: today's rule that "a phone wants one chart, the Mac four" (`SYNC_PARTS` note)
  stays. The newest device's tab list replaces the others' (merging would bring back tabs you closed). A tab list pulled
  in the first few seconds after the app opens, before you've touched the tabs, applies at once; one pulled later
  applies on the next open, never mid-session (it would yank the screen).
- **Phones in this piece:** chart tabs stay a desktop thing. On a phone, "Charts" shows the open chart tab and "open in a
  chart" changes that tab's market; a phone opens no new tabs, keeps no background feeds for other tabs, and neither
  sends nor applies the tab list until piece 3.
- **A new chart tab copies the timeframes and layout of the chart tab you used last** (the built-in 4H / 1H / 15m / 5m
  four-pane grid only when there is none).

## How it works

### The tab row
- Left to right: **⌂ Home** (pinned; can't be closed or moved), the open tabs in your order, **+**.
- **A chart tab's label**: market and the timeframe of its main pane, the live price, the change the chart watchlist
  shows, and 🔔 when a chart alert or price alert fires on that market (cleared when you open the tab).
- **A page tab's label**: the page name and its count, the same numbers the sidebar shows today (Day trade 6, Momentum 8…).
- **×** closes a tab (not Home). Drag to reorder. When the tabs don't fit, they shrink to a minimum width and then the
  row scrolls, like a browser. Alt+1…9 jumps to a tab.
- Closing the last tab other than Home leaves Home showing.

### The + menu
- **New chart** first: opens the market picker; picking a market opens a new chart tab with it, with the timeframes
  and layout of the chart tab you used last.
- Then every page, grouped:
  - **Home pages**, each in its own tab: Overview (Crypto), Overview (Forex, metals & indices), Trading day, Calendar,
    Fundamentals.
  - **Boards**: Momentum Board, Day Trade, Swing, Trend Starting.
  - **Forex · metals · indices**: Momentum Board, Pair Picker, All Instruments.
  - **Screener**: All Coins, Filters & Templates (All Coins with its filters panel open, as today).
  - **My trading**: Trade, Watchlist & Alerts.
  - **More**: Playbook, Model Guide.
- A search box at the top filters pages, and typing a market's name offers "New chart: Gold" and the like.

### The Home tab
- The left menu: Overview › Crypto, Forex metals & indices; Trading day › Today, This week; Calendar; Fundamentals.
- Each section is today's page, unchanged, shown inside Home's frame (the same sections, moved, not rebuilt). Home
  remembers which section was open.
- Each section has **Open in its own tab**, which opens that page as a page tab.
- The scan settings bar shows on the sections it affects, as it does today on those pages.
- The sidebar footer's scan status moves to the tab row's right end: the last scan ("312 coins · scanned 3:40 PM", the
  progress while a scan runs) beside Scan now, and Exchange / Direction / Stream in the Live badge's tooltip (my call, as
  drawn in the mockups).

### Chart tabs (approach 3)
- **One chart screen** draws the open chart tab. Each chart tab remembers: its market (and whether the source was picked
  by hand), each pane's timeframe, the layout, the maximised pane, and each pane's view (zoom and scroll, plus whether it
  was at the live edge, so it comes back following new candles if it was).
- **In the background**, every open chart tab's markets keep their live prices and their candles current in memory, for
  each of that tab's timeframes, through the live feeds the app already uses (cTrader prices, the exchange streams).
- **Switching** draws the target tab from memory without fetching (a top-up from the candle cache only if it has fallen
  behind), restores its view, and does the same tidy-up as changing market does today: menus and dialogs close, the tool
  goes back to the cursor, a half-finished drawing or measurement is dropped, undo history resets.
- **Changing market or timeframe inside a chart tab** changes that tab; it doesn't open a new one.
- The Overview pages keep borrowing the chart screen for their own charts and hand it back (as `ovcHost`/`ovcPark` do
  today), now back to whichever chart tab is open.
- Chart alerts already check their own prices whatever is on screen; nothing changes there except the 🔔 on the tab.
- Order lines, Quick trade and the chart order panel belong to the open chart tab's market and are otherwise unchanged.

### Remembering and syncing
- Tabs, their order, the open tab and Home's section are saved on the device and restored on open.
- Sync (Settings → Sync) gains a part, "Your tabs", next to drawings, watchlist and the rest; what it carries and when it
  applies is under "Calls I made". The Sync panel's note about what stays per device is updated to match.
- Links that name a page (`#fund` and the like) open that page's tab, or jump to it if it's open.

### First open after the update
- Home, plus one chart tab built from the current Charts settings (market, timeframes, layout), plus a page tab for the
  page you were last on if it isn't Charts or a Home section. The chart tab is the one shown.

### What goes away
- The sidebar on desktop (its pages move to + and Home), and the breadcrumb in the top bar (the tab row replaces it).
- On phones nothing changes in this piece: the bottom bar and the More sheet stay, and "Charts" there shows the open chart
  tab (see "Phones in this piece").

## Approaches considered
1. **Every chart tab runs its own live chart.** Instant switching with everything kept as left, per-tab indicators
   possible. Rejected: the chart engine is written as one shared chart that order lines, Quick trade, replay, alerts and
   the Overview charts all lean on, so it means a rebuild that puts the trading parts at risk; it is heavy on a laptop or
   phone (six tabs could mean 24 charts drawing); weeks of work.
2. **Tabs take turns on one chart, nothing live in the background.** Quick and low-risk. Rejected: Jas wants tabs to keep
   moving live.
3. **One chart screen, every chart tab's data kept live** (chosen). Instant, current switching and awareness from the tab
   row, without touching the chart engine's trading parts. Costs: a hidden tab's chart doesn't redraw (it can't be seen
   anyway) and indicators stay shared.

Real browser tabs were ruled out earlier: each would run its own copy of The Finder (its own scan, its own cTrader
connection, its own alerts).

## Goals
- Open several charts and any pages as tabs; switch between them instantly.
- Charts not on screen stay current, and the tab row shows what's moving and what alerted.
- Home holds Overview, Trading day, Calendar and Fundamentals in full.
- Tabs survive a reload and follow you to your other devices.

## Non-goals (this piece)
- Layout A's chart workspace (piece 2) and the phone layout (piece 3).
- Per-tab indicators, a separate chart engine per tab, real browser tabs.
- Changing what any page shows, beyond moving the four into Home.

## Anti-goals (a failure even if it works)
- Any change to how orders are placed, to order lines or to Quick trade.
- Losing drawings, tabs or a detail of Overview, Trading day, Calendar or Fundamentals.
- A hidden tab costing as much as a visible chart (drawing it, or fetching its full history every few seconds).
- The screen changing under you because another device synced.

## Constraints
- Everything stays in `index.html` (scripts in order: core, UI, charts, extras, trade); core stays DOM-free.
- Plain-language UI copy, sentence case. Tests run with mocks, never place real orders. Bump the version after changes.
- Live feeds have limits: keep one subscription per market however many tabs show it.
- Tests open pages with `goPage(...)` and some click the sidebar (`#side [data-go=…]`); those need a new way in. Tests
  start on Overview unless `setup(ctx, start=None)`.

## Left to the builder
- Tab sizes, truncation, overflow arrows, drag feel, animation.
- How background candles are kept current (reusing the existing live stream paths is expected), how far behind counts
  as "fallen behind", and how much history a hidden tab keeps in memory.
- How the scan status reads while a scan runs (text, a thin progress bar, or both).
- Keyboard shortcuts beyond Alt+1…9.
