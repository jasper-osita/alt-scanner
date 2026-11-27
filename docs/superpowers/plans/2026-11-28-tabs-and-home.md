# Tabs and the Home tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browser-style tabs across the top of The Finder (a pinned Home tab, chart tabs that stay live in the background, page tabs), replacing the desktop sidebar.

**Architecture:** A new `<script id="tabs">` (after `<script id="trade">`) holds the tab model `TB`, the tab row and the router. `goPage(id)` becomes the router; its current body is renamed `pgShow(id, keepTab)` and still shows one `[data-page]` section. Home is a mode, not a section: the Home tab shows one of the existing Overview / forex Overview / Trading day / Calendar / Fundamentals sections with a left rail. Chart tabs share the one chart engine: switching saves the open tab's chart state and applies the target's (the way `ovcPark` restores Charts today); hidden chart tabs keep their candles current in memory (`TB.mem`) so a switch draws without fetching.

**Tech Stack:** Plain JS in `index.html`, Lightweight Charts (already loaded by `ensureLWC`), Playwright tests with the mocks in `tests/mock.py`.

**Spec:** `docs/superpowers/specs/2026-11-27-tabs-and-home-design.md` (read it with this plan).

## Global Constraints

- Everything stays in `index.html`; scripts in order core, UI, charts, extras, trade, then the new `tabs`. Core stays DOM-free. A later script's top-level function overrides an earlier one with the same name: check new names with `grep -n "function <name>\b"` first (`TABS` is taken: the tab model is `TB`, every new name starts `tb`).
- Plain-language UI copy, sentence case. Tests run on mocks; never place real orders. After changes: `TZ=Asia/Manila bash bump-version.sh`.
- Up to 12 chart tabs (`TB_MAX_CHARTS = 12`); a page opens once. Indicators and chart style stay shared (`CH.ind`, `CS`); drawings stay per exact feed (`CHD[sym]`).
- One live subscription or fetch per market and timeframe, however many tabs show it.
- Phones (≤760px, `isPhone()`) keep the bottom bar and More sheet; no extra chart tabs, no background feeds, no tab sync on phones.
- Synced from other devices: which tabs are open, their order, each chart tab's market (+ `symExact`) and Home's section. Per device: timeframes, layout, maximised pane, zoom/scroll, the open tab.
- Order lines, Quick trade, the chart order panel and `cttPlace`/`mxtPlace`/`qtPlace` are not changed.

## Review Focus

1. **Old or broken saved tabs** (missing fields, a removed page like `nbbwatch`, `sessions`, `bots`, an unknown market) → the app opens with the valid tabs and Home; never a blank screen. Test in Task 1.
2. **Closing the open tab** → the tab to its right opens, else the one to its left, else Home. Test in Task 1.
3. **Switching while a chart is still loading** → candles that arrive late for the tab you left never land in the tab you're on (`P.tok` guard). Test in Task 4.
4. **The same market in many tabs** (e.g. Gold 15m in five tabs) → one background fetch per market and timeframe per tick. Test in Task 5.
5. **Overview borrowing the chart** (`OVC.on`) while you switch tabs → the overview hands the chart back to the open chart tab, and that tab's market and timeframes are what you see. Test in Task 4.

---

### Task 1: The tab model

**Files:**
- Modify: `index.html` — new `<script id="tabs">` before the service-worker registration script.
- Test: create `tests/t_tabs.py` (same skeleton as `tests/t_td.py`: `F`, `check(name, ok, detail)`, `async def partN(q)`, `main()` running each part then `print("errors:", F + errs[:4] or "none")`).

**Interfaces:**
- Produces:
  - `TB_KEY = "finder-tabs"`, `TB_MAX_CHARTS = 12`, `HOME_PAGES = ["overview", "macroov", "tday", "calendar", "fund"]`.
  - `TB = { list: Tab[], active: string, home: string, last: string|null, touched: boolean, mem: Map }`, where Home is the implicit id `"home"` (never in `list`).
  - `Tab = { id: string, kind: "page", page: string, bell?: boolean } | { id: string, kind: "chart", ch: { sym, symExact, tfs: string[4], layout, max, views: Array<{from, to, live}|null> }, bell?: boolean }`. `TB.last` = id of the chart tab used last.
  - `tbValid(t: Tab) -> boolean` (page tabs: `PAGE_INFO[t.page]` exists and isn't `"charts"`/`"filters"`; chart tabs: `t.ch.sym` is a non-empty string; fills missing `tfs`/`layout`/`views` from `CH` defaults).
  - `tbFirst(ch: object, lastPage: string) -> {list, active, home, last}`: Home, one chart tab from `ch` (the current `finder-charts`), plus a page tab for `lastPage` unless it is `charts`, `filters` or a Home page; `active` = the chart tab; `home` = `lastPage` if it is a Home page, else `"overview"`.
  - `tbRead() -> void` (fills `TB` from `localStorage[TB_KEY]`, dropping invalid tabs; when the key is absent, from `tbFirst(chLoadJSON(CH_KEY, {}), localStorage["finder-page"])`).
  - `tbSave() -> void`, `tbOpenPage(page) -> Tab`, `tbOpenChart(sym, { exact?: boolean, reuse?: boolean }) -> Tab|null`, `tbClose(id) -> void`, `tbMove(id, toIndex) -> void`, `tbNextAfterClose(id) -> string`.

- [ ] **Step 1: Write the failing test** — `part1(q)` in `tests/t_tabs.py`:

```python
check("first open: Home + a chart tab from the current chart + the last page", await q("""() => {
  const r = tbFirst({ sym: 'CT:XAUUSD', tfs: ['15m','1h','4h','1d'], layout: '2c' }, 'momentum');
  return r.list.map(t => t.kind === 'chart' ? 'chart:' + t.ch.sym + ':' + t.ch.layout : 'page:' + t.page).join() === 'chart:CT:XAUUSD:2c,page:momentum'
    && r.active === r.list[0].id && r.home === 'overview'; }"""))
check("a Home page last time: Home opens on it, no extra tab", await q("() => { const r = tbFirst({ sym: 'BTCUSDT' }, 'tday'); return r.list.length === 1 && r.home === 'tday'; }"))
check("removed or unknown pages and broken tabs are dropped", await q("""() => { localStorage.setItem('finder-tabs', JSON.stringify({ list: [{ id: 'a', kind: 'page', page: 'nbbwatch' }, { id: 'b', kind: 'page', page: 'sessions' }, { id: 'c', kind: 'chart', ch: {} }, { id: 'd', kind: 'page', page: 'momentum' }, { id: 'e' }], active: 'a', home: 'bots' }));
  tbRead(); return TB.list.map(t => t.id).join() === 'd' && TB.active === 'home' && TB.home === 'overview'; }"""))
check("a page opens once", await q("() => { const a = tbOpenPage('day'), b = tbOpenPage('day'); return a.id === b.id && TB.list.filter(t => t.page === 'day').length === 1; }"))
check("12 chart tabs at most", await q("() => { TB.list = TB.list.filter(t => t.kind !== 'chart'); for (let i = 0; i < 12; i++) tbOpenChart('SYM' + i + 'USDT'); return tbOpenChart('ONEMOREUSDT') === null && TB.list.filter(t => t.kind === 'chart').length === 12; }"))
check("reuse finds a tab already on that market", await q("() => tbOpenChart('SYM3USDT', { reuse: true }).ch.sym === 'SYM3USDT' && TB.list.filter(t => t.kind === 'chart' && t.ch.sym === 'SYM3USDT').length === 1"))
check("a new chart tab copies the last-used chart tab's timeframes and layout", await q("() => { const L = TB.list.find(t => t.kind === 'chart'); L.ch.tfs = ['15m','15m','1h','4h']; L.ch.layout = '2c'; TB.last = L.id; TB.list = TB.list.filter(t => t.kind !== 'chart' || t === L); const n = tbOpenChart('NEWUSDT'); return n.ch.tfs.join() === '15m,15m,1h,4h' && n.ch.layout === '2c'; }"))
check("closing the open tab: right neighbour, else left, else Home", await q("""() => { TB.list = [{ id: 'x', kind: 'page', page: 'day' }, { id: 'y', kind: 'page', page: 'swing' }, { id: 'z', kind: 'page', page: 'aots' }];
  const r = [tbNextAfterClose('y'), tbNextAfterClose('z')]; TB.list = [{ id: 'x', kind: 'page', page: 'day' }]; r.push(tbNextAfterClose('x')); return r.join() === 'z,y,home'; }"""))
check("tabs survive a reload", await q("() => { tbSave(); const keep = JSON.stringify(TB.list); tbRead(); return JSON.stringify(TB.list) === keep; }"))
```

- [ ] **Step 2: Run it to verify it fails** — `bash tests/runall.sh t_tabs`. Expected: `ReferenceError: tbFirst is not defined`.

- [ ] **Step 3: Implement the model** in `<script id="tabs">`: the constants, `TB`, and the functions in Interfaces. Ids from `Date.now().toString(36) + n`. `tbOpenChart` with `reuse` returns an existing chart tab whose `ch.sym === sym`; without it, or none found, it appends a chart tab whose `tfs`/`layout` come from `TB.last`'s tab (else `CH`), or returns `null` and `toast("You have 12 chart tabs open: close one first.")` at the cap. `tbClose` removes the tab and, if it was `TB.active`, sets `TB.active = tbNextAfterClose(id)` computed before removal. Call `tbRead()` once when the script loads.

- [ ] **Step 4: Run the test** — `bash tests/runall.sh t_tabs`. Expected: every `ok`, `errors: none`.

- [ ] **Step 5: Commit** — `git commit -m "Tabs: the tab model (open, close, order, cap, first open, saved tabs)"`.

### Task 2: The router and the tab row

**Files:**
- Modify: `index.html` — UI script: rename `goPage`'s body to `pgShow(id, keepTab)` (`index.html:5659` area) and keep `window.goPage`; topbar markup (`index.html:1129-1141`: add `<nav id="tabRow">` where `#crumb` sits, keep `#crumb` for phones); CSS block; the boot IIFE at `index.html:6368` (start on `TB.active` instead of `"charts"`).
- Modify: `<script id="tabs">`: `goPage` router, `tbActivate`, `tbRender`, the + menu, Alt+1…9.
- Test: `tests/t_tabs.py` `part2(pg, q)`.

**Interfaces:**
- Consumes: Task 1's model.
- Produces:
  - `goPage(id, keepTab)`: the router. `"charts"` → `tbActivate(TB.last || first chart tab || new chart tab from CH)`; a Home page → the page tab for it if one is open, else Home with `TB.home = id`; `"filters"` → the `screener` page tab, then `togglePanel(true)`; any other known page → `tbActivate(tbOpenPage(id).id)`; unknown → Home.
  - `pgShow(id, keepTab)`: today's `goPage` body unchanged (sections, title, `mTabSync`, page hooks, `chPageShown`).
  - `tbActivate(id)`: sets `TB.active`, `TB.touched = true` when called from a click, clears that tab's `bell`, `tbSave()`; Home → `pgShow(TB.home)` with `body.homeon`; page tab → `pgShow(tab.page)`; chart tab → `tbShowChart(tab)` (Task 4).
  - `tbRender()`: draws `#tabRow`: `⌂` (`data-tab="home"`), the tabs (`data-tab=<id>`, `×` = `data-tclose=<id>`, draggable), `+` (`#tabPlus`), then the right end: search (opens the + menu with its search focused), `#tbStat` (last scan: `"<n> coins · scanned <time>"`, or the progress while scanning, mirrored from `#status` like `mirrorSide` does), `#liveBadge` (title: exchange · direction · stream), `#bellBtn`, `#runBtn`, `#mMore` as ⋯ (its menu already has Auto-refresh, Copy for Claude, Export JSON, Filters; add Settings).
  - `tbPlusMenu(query: string) -> HTML`: "New chart" first (opens `#chPick`; picking opens a chart tab), then groups: **Home pages** (Overview: crypto → `overview`, Overview: forex, metals & indices → `macroov`, Trading day → `tday`, Calendar → `calendar`, Fundamentals → `fund`), **Boards** (`momentum`, `day`, `swing`, `aots`), **Forex · metals · indices** (`macromomo`, `macropair`, `macro`), **Screener** (`screener`, `filters`), **My trading** (`trade`, `watch`), **More** (`playbook`, `guide`). A query filters by label; it also lists up to 5 markets from `pkMarkets("all", "all")` whose name or ticker matches, as "New chart: <chName>".
- Desktop CSS (`@media (min-width:761px)`): `#side` hidden, `.wrap` full width, `#tabRow` shown, `#crumb` hidden; tabs shrink to a 120px minimum, then the tab list scrolls sideways (Home, + and the right end stay put). Phones: `#tabRow` hidden, everything else as today.

- [ ] **Step 1: Write the failing test** — `part2(pg, q)`:

```python
await q("() => { localStorage.removeItem('finder-tabs'); location.hash = ''; }"); await pg.reload(); await ready(pg)
check("desktop: no sidebar, a tab row with Home first", await q("() => getComputedStyle(document.getElementById('side')).display === 'none' && document.querySelector('#tabRow [data-tab]').dataset.tab === 'home'"))
check("opens on the chart tab built from the current chart", await q("() => TB.list[0].kind === 'chart' && TB.active === TB.list[0].id && page === 'charts'"))
await q("() => goPage('day')")
check("goPage opens a page tab once", await q("() => page === 'day' && TB.list.filter(t => t.page === 'day').length === 1 && TB.active === TB.list.find(t => t.page === 'day').id"))
await q("() => goPage('fund')")
check("a Home page goes to Home", await q("() => TB.active === 'home' && TB.home === 'fund' && page === 'fund'"))
await pg.click('#tabRow [data-tab="' + await q("() => TB.list.find(t => t.page === 'day').id") + '"]')
check("clicking a tab shows it", await q("() => page === 'day'"))
await pg.click("#tabPlus"); await pg.keyboard.type("gold")
txt = await q("() => document.getElementById('tbMenu').innerText")
check("+ menu search offers a chart for Gold", "New chart: Gold" in txt, txt[:200])
await pg.keyboard.press("Escape"); await pg.click("#tabPlus")
groups = await q("() => [...document.querySelectorAll('#tbMenu .tbgrp')].map(g => g.firstChild.textContent.trim())")
check("+ menu groups", groups == ["Home pages", "Boards", "Forex · metals · indices", "Screener", "My trading", "More"], groups)
await pg.keyboard.press("Escape"); await pg.keyboard.press("Alt+1")
check("Alt+1 is the first tab after Home", await q("() => TB.active === TB.list[0].id"))
await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.3)
check("phone: bottom bar, no tab row", await q("() => getComputedStyle(document.getElementById('mTab')).display !== 'none' && getComputedStyle(document.getElementById('tabRow')).display === 'none'"))
await pg.set_viewport_size({"width": 1440, "height": 900})
```

- [ ] **Step 2: Run it to verify it fails** — Expected: `FAIL desktop: no sidebar…` (and the later checks).
- [ ] **Step 3: Implement the router, `pgShow`, `tbActivate`, `tbRender`, the + menu (`#tbMenu`, closes on Escape or a click outside), drag to reorder (`tbMove` on drop), Alt+1…9, the CSS, and the boot change.** The tab row redraws on `tbSave()` and every 2 s (labels; Task 5).
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_smoke t_start`. Expected: all pass; fix `t_start`'s expectation that a fresh open lands on Charts only if it now checks `page === 'charts'` through the sidebar (it should still be `charts`).
- [ ] **Step 5: Commit** — `"Tabs: the tab row, the + menu and goPage as the router"`.

### Task 3: The Home tab

**Files:**
- Modify: `index.html` — markup: `<nav id="homeNav" class="homenav" aria-label="Home sections">` at the top of `<main>`; an "Open in its own tab" button (`data-owntab="<page>"`) in the header of the `overview`, `macroov`, `tday`, `calendar` and `fund` sections; CSS (`body.homeon` shows `#homeNav` as a left column on desktop).
- Modify: `<script id="tabs">`: `tbHomeRender()`.
- Test: `tests/t_tabs.py` `part3(pg, q)`.

**Interfaces:**
- Consumes: `goPage`, `pgShow`, `TB.home`, `TD_VIEW` and `tdRender()` (Trading day's Today / This week).
- Produces: `tbHomeRender()` — the rail (each item carries `data-hp="<page>"`; the two Trading day items also `data-tdv="today|week"`): **Overview** (Crypto → `overview`, Forex, metals & indices → `macroov`), **Trading day** (Today → `tday` + `TD_VIEW = "today"`, This week → `tday` + `TD_VIEW = "week"`), **Calendar**, **Fundamentals**; the open one marked `aria-current`.

- [ ] **Step 1: Write the failing test** — `part3`:

```python
await q("() => tbActivate('home')")
rail = await q("() => [...document.querySelectorAll('#homeNav a, #homeNav button')].map(e => e.textContent.trim())")
check("Home rail", rail == ["Overview", "Crypto", "Forex, metals & indices", "Trading day", "Today", "This week", "Calendar", "Fundamentals"], rail)
await pg.click('#homeNav [data-hp="tday"][data-tdv="week"]')
check("This week opens Trading day on its week view", await q("() => page === 'tday' && TD_VIEW === 'week' && TB.home === 'tday'"))
await q("() => goPage('charts')"); await q("() => tbActivate('home')")
check("Home remembers its section", await q("() => page === 'tday'"))
await pg.click('[data-page="tday"] [data-owntab="tday"]')
check("Open in its own tab", await q("() => TB.list.some(t => t.page === 'tday') && TB.active === TB.list.find(t => t.page === 'tday').id && !document.body.classList.contains('homeon')"))
await q("() => goPage('tday')")
check("with its own tab open, goPage goes to that tab", await q("() => TB.active === TB.list.find(t => t.page === 'tday').id"))
```

- [ ] **Step 2: Run to verify it fails** — Expected: `FAIL Home rail`.
- [ ] **Step 3: Implement** `#homeNav`, `tbHomeRender`, the owntab buttons (click → `tbActivate(tbOpenPage(page).id)`), and `body.homeon` toggled by `tbActivate`.
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_td t_fund t_calview t_ovch`. Expected: all pass.
- [ ] **Step 5: Commit** — `"Tabs: the Home tab and its left menu"`.

### Task 4: Chart tabs share the chart

**Files:**
- Modify: `<script id="tabs">`: `tbSnapChart`, `tbShowChart`, `tbSyncActiveChart`.
- Modify: `index.html` charts script: `chSave` (`index.html:6385`) also calls `tbSyncActiveChart()` when a chart tab is open; `openInCharts` (grep `function openInCharts`) goes through `tbOpenChart(sym, { reuse: true })`; `ovcHost` takes `OVC.prev` from the open chart tab's `ch` and `ovcPark` writes back to it.
- Test: `tests/t_tabs.py` `part4(pg, q)`.

**Interfaces:**
- Consumes: Task 1 (`TB`, `tbOpenChart`), Task 2 (`tbActivate`, `pgShow`), the engine (`CH`, `CHP`, `chVis()`, `chLoad(P)`, `chSetData(P)`, `chSetSym`, `rpExit()`, `RP.on`, `chDraft`/`chMeasure`/`chSel`/`chUndo`/`chRedo`, `chSetTool("cursor")`).
- Produces:
  - `tbSnapChart() -> ch` — from `CH` and `chVis()`: `views[i] = { from, to, live }` from `P.chart.timeScale().getVisibleLogicalRange()`, `live = to >= P.t.length - 2`.
  - `tbShowChart(tab)` — if a chart tab was open: `tab_prev.ch = tbSnapChart()` and Task 5's `tbRemember(tab_prev)`; then apply `tab.ch` to `CH` (`sym`, `symExact`, `tfs`, `layout`, `max`), the tidy-up (`rpExit()` if `RP.on`; drop draft, measure, selection; reset undo/redo; tool to cursor; close menus and dialogs as `ovcPark` does), bump every pane's `P.tok`, `pgShow("charts")`, draw (Task 5's memory first, else `chLoad(P)`), then restore each pane's view (a `live` view scrolls to the newest candle).
  - `tbSyncActiveChart()` — copies `tbSnapChart()` into the open chart tab and `tbSave()`.

- [ ] **Step 1: Write the failing test** — `part4` (Binance mocks; `CH_TFS` include `15m`, `1h`):

```python
await q("() => { TB.list = []; TB.active = 'home'; const a = tbOpenChart('BTCUSDT'), b = tbOpenChart('ETHUSDT'); b.ch.tfs = ['15m','1h','4h','1d']; b.ch.layout = '1'; window.__a = a.id; window.__b = b.id; tbActivate(a.id); }")
await wait("() => CH.sym === 'BTCUSDT' && chVis()[0].t.length > 50")
await q("() => { const P = chVis()[0]; P.chart.timeScale().setVisibleLogicalRange({ from: P.t.length - 60, to: P.t.length - 30 }); }")
await q("() => tbActivate(window.__b)"); await wait("() => CH.sym === 'ETHUSDT' && CH.layout === '1' && chVis()[0].tf === '15m' && chVis()[0].t.length > 50")
await q("() => tbActivate(window.__a)"); await wait("() => CH.sym === 'BTCUSDT' && chVis()[0].t.length > 50")
v = await q("() => { const P = chVis()[0], r = P.chart.timeScale().getVisibleLogicalRange(); return [Math.round(r.to - (P.t.length - 30))]; }")
check("each chart tab keeps its market, timeframes, layout and zoom", abs(v[0]) <= 2, v)
await q("() => { chPush(); chList().push({ id: 'tbd', type: 'hline', pts: [{ t: chVis()[0].t.at(-5), p: chVis()[0].c.at(-1) }] }); chSaveDraw(); }")
await q("() => tbActivate(window.__b)"); await q("() => tbActivate(window.__a)")
check("drawings stay on their market", await q("() => chList('BTCUSDT').some(d => d.id === 'tbd') && !chList('ETHUSDT').some(d => d.id === 'tbd')"))
await q("() => rpEnter()"); await q("() => tbActivate(window.__b)")
check("replay ends when you leave its tab", await q("() => !RP.on"))
await q("() => { tbActivate(window.__a); chDraft = { type: 'trend', pts: [] }; tbActivate(window.__b); }")
check("a half-finished drawing is dropped on switching", await q("() => chDraft === null && chTool === 'cursor'"))
late = await q("""async () => { tbActivate(window.__a); const P = chVis()[0], tok = P.tok; tbActivate(window.__b); await new Promise(r => setTimeout(r, 1500)); return [CH.sym, chVis()[0].sym, chVis()[0].tok !== tok]; }""")
check("a chart still loading for the tab you left never lands in this one", late == ["ETHUSDT", "ETHUSDT", True], late)
await q("() => goPage('overview')"); await wait("() => OVC.on === 'c'"); await q("() => tbActivate(window.__a)")
check("the overview hands the chart back to the open chart tab", await wait("() => !OVC.on && page === 'charts' && CH.sym === 'BTCUSDT'"))
await q("() => openInCharts('ETHUSDT')")
check("open in a chart goes to the tab already on that market", await q("() => TB.active === window.__b && TB.list.filter(t => t.kind === 'chart').length === 2"))
```
(`wait(js, secs=30)` = the polling helper from `tests/t_cmp.py`.)

- [ ] **Step 2: Run to verify it fails** — Expected: the first `wait` times out (no `tbShowChart`).
- [ ] **Step 3: Implement** `tbSnapChart`, `tbShowChart`, `tbSyncActiveChart`, the `chSave`, `openInCharts` and `ovcHost`/`ovcPark` changes. On phones `openInCharts(sym)` sets the open chart tab's market (`chSetSym`) instead of opening a tab.
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_charts t_ovch t_tvx t_trade t_mob2`. Expected: all pass.
- [ ] **Step 5: Commit** — `"Tabs: chart tabs share the chart and keep their own market, timeframes and zoom"`.

### Task 5: Hidden chart tabs stay live; the labels

**Files:**
- Modify: `<script id="tabs">`: `tbRemember`, `tbMerge`, `tbBgTick`, `tbLabel`, the bell hook.
- Modify: `index.html` charts script: `chQuotesFetch(list)` (`index.html:8957`) also asks for every chart tab's market when called with no list.
- Test: `tests/t_tabs.py` `part5(pg, q)`.

**Interfaces:**
- Consumes: Task 4 (`tbShowChart` reads memory through `tbMemFor(sym, tf)`), `formingBar(sym, tf) -> Promise<{t,o,h,l,c,v}>`, `chQuote(sym) -> {price, chg}|null`, `notify`/`ncAdd` (alerts carry `sym`).
- Produces:
  - `TB.mem: Map<"sym|tf", { t, o, h, l, c, v, at }>` (arrays, at most the last 600 candles).
  - `tbRemember(tab)` — copies each visible pane's arrays into `TB.mem` when its tab is left.
  - `tbMerge(m, bar)` — replaces the last candle when `bar.t === m.t.at(-1)`, appends when newer, ignores older.
  - `tbMemFor(sym, tf) -> m|null` — `null` when its last candle is more than 2 candles behind now (then `tbShowChart` falls back to `chLoad(P)`).
  - `tbBgTick() -> Promise<void>` — runs every 15 s on desktop while visible: the unique `sym|tf` pairs of hidden chart tabs' visible panes; one `formingBar` per pair; `tbMerge`; the promise settles once this tick's fetches are merged.
  - `tbLabel(tab) -> { name, tf, price, chg }` — `chName(ch.sym)`, the main pane's timeframe label, `chQuote` price and change.
  - The bell: alerts with a `sym` set `bell = true` on hidden chart tabs whose `ch.sym` equals it; `tbActivate` clears it; the label shows `🔔`.

- [ ] **Step 1: Write the failing test** — `part5`:

```python
check("merge: same candle replaced, newer appended, older ignored", await q("""() => { const m = { t: [1, 2], o: [1, 1], h: [2, 2], l: [0, 0], c: [1, 1], v: [1, 1] };
  tbMerge(m, { t: 2, o: 1, h: 3, l: 0, c: 2.5, v: 2 }); tbMerge(m, { t: 3, o: 2.5, h: 3, l: 2, c: 2.8, v: 1 }); tbMerge(m, { t: 1, o: 9, h: 9, l: 9, c: 9, v: 9 });
  return m.t.join() === '1,2,3' && m.c.join() === '1,2.5,2.8'; }"""))
await q("() => { window.__fb = 0; const f = formingBar; window.formingBar = formingBar = (s, tf) => { window.__fb++; return f(s, tf); }; }")
await q("() => { TB.list = TB.list.filter(t => t.kind !== 'chart'); const ids = []; for (let i = 0; i < 5; i++) { const t = tbOpenChart('BTCUSDT'); t.ch.tfs = ['15m','15m','15m','15m']; t.ch.layout = '1'; ids.push(t.id); } const o = tbOpenChart('ETHUSDT'); o.ch.layout = '1'; tbActivate(o.id); window.__ids = ids; }")
await asyncio.sleep(1); await q("() => { window.__fb = 0; return tbBgTick(); }")
check("five tabs on BTC 15m: one fetch per tick", await q("() => window.__fb === 1"), await q("() => window.__fb"))
last = await q("() => TB.mem.get('BTCUSDT|15m').t.at(-1)")
await q("() => tbActivate(window.__ids[0])")
check("switching draws the newest candle at once, from memory", await q(f"() => chVis()[0].t.at(-1) === {last}"))
lab = await q("() => tbLabel(TB.list.find(t => t.kind === 'chart'))")
check("the label: market, timeframe, price, change", lab["name"] and lab["tf"] == "15m" and lab["price"] is not None and lab["chg"] is not None, lab)
await q("() => { tbActivate(TB.list.find(t => t.ch && t.ch.sym === 'ETHUSDT').id); notify('BTC alert', 'x', { sym: 'BTCUSDT', kind: 'Price', icon: '🔔', title: 'BTC crossed your level' }); tbRender(); }")
check("an alert lights its tab", await q("() => TB.list.filter(t => t.bell).length >= 1 && document.getElementById('tabRow').textContent.includes('🔔')"))
await q("() => tbActivate(window.__ids[0])")
check("opening it clears the bell", await q("() => !TB.list.find(t => t.id === window.__ids[0]).bell"))
```

- [ ] **Step 2: Run to verify it fails** — Expected: `ReferenceError: tbMerge is not defined`.
- [ ] **Step 3: Implement** the Interfaces. The 15 s timer skips phones and hidden documents; labels redraw with the tab row every 2 s.
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_charts t_ctfeed`. Expected: all pass.
- [ ] **Step 5: Commit** — `"Tabs: hidden chart tabs stay live; live prices and alerts on the tab row"`.

### Task 6: Board Chart buttons open a chart tab

**Files:**
- Modify: `index.html` — the scan settings select `#chartMode` (`index.html:1159`), `openTV` (`index.html:3252`), `chartBtn` (`index.html:3266`) and the `[data-tv]` binders (`index.html:3268`, `5307`).
- Test: `tests/t_tabs.py` `part6(pg, q)`.

**Interfaces:**
- Consumes: Task 1 `tbOpenChart`, Task 2 `tbActivate`, Task 4 `chSetSym` on the open chart tab.
- Produces: `#chartMode` options, label "Open charts in": `here` "A chart tab here" (default), `last` "The chart tab I used last", `tab` "TradingView (browser tab)", `helper` "TradingView Helper App", `copy` "Copy the TradingView link". `openChart(sym)`: `here` → `tbActivate(tbOpenChart(sym, { reuse: true }).id)`; `last` → open `TB.last` (or a new chart tab) and `chSetSym(sym)`; otherwise → `openTV(sym)` as today. `tbChartModeMigrate()`: a saved `"tab"` from before this change becomes `"here"` once (flag `finder-chartmode-v2`). `chartBtn` title: "Open the chart".

- [ ] **Step 1: Write the failing test** — `part6`:

```python
opts = await q("() => [...document.querySelectorAll('#chartMode option')].map(o => o.value + ':' + o.textContent)")
check("Open charts in", opts == ["here:A chart tab here", "last:The chart tab I used last", "tab:TradingView (browser tab)", "helper:TradingView Helper App", "copy:Copy the TradingView link"], opts)
await q("() => goPage('day')"); await wait("() => document.querySelector('#dayBoard [data-tv]')")
s = await q("() => { const b = document.querySelector('#dayBoard [data-tv]'); b.click(); return b.dataset.tv; }")
check("a board's Chart button opens that market in a chart tab", await wait(f"() => page === 'charts' && CH.sym === '{s}' && TB.list.find(t => t.id === TB.active).kind === 'chart'"))
check("old 'New Tab' choice moves to a chart tab here once", await q("() => { localStorage.removeItem('finder-chartmode-v2'); $('chartMode').value = 'tab'; tbChartModeMigrate(); return $('chartMode').value === 'here'; }"))
```

- [ ] **Step 2: Run to verify it fails** — Expected: `FAIL Open charts in`.
- [ ] **Step 3: Implement** `openChart`, `tbChartModeMigrate()` (runs once at load), the options, the binders calling `openChart`.
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_mkts t_momoui t_finder`. Expected: all pass.
- [ ] **Step 5: Commit** — `"Tabs: board Chart buttons open a chart tab here"`.

### Task 7: Sync, phones and links

**Files:**
- Modify: `index.html` — `SYNC_PARTS` (`index.html:8975`): add `tabs`; the Sync settings text about what stays per device (grep `"stay per device"`); the `hashchange` listener (`index.html:5762`).
- Test: `tests/t_tabs.py` `part7(pg, q)`.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `SYNC_PARTS.tabs = { l: "Your tabs", get: tbSyncGet, set: tbSyncSet }`. `tbSyncGet() -> { list: [{ kind, page } | { kind, sym, symExact }], home }` (no ids, timeframes, layout or views); on phones it returns the last value it received, unchanged, so a phone never overwrites the desktop's tabs.
  - `tbSyncSet(v)`: on phones, ignored. Otherwise saved as `finder-tabs-in`; applied at once when `Date.now() - TB_BOOT < 5000 && !TB.touched`, else at the next `tbRead()`. Applying keeps each local chart tab's timeframes, layout and views when the same market is in the incoming list, gives new chart tabs the last-used timeframes and layout, keeps the open tab if it still exists (else the first tab).
  - `hashchange` and links: `#<page>` → `goPage(page)`; an unknown page → Home.

- [ ] **Step 1: Write the failing test** — `part7`:

```python
g = await q("() => { TB.list = []; const a = tbOpenChart('BTCUSDT'); a.ch.tfs = ['1m','5m','15m','1h']; tbOpenPage('day'); return tbSyncGet(); }")
check("sync carries markets and pages, not timeframes", g["list"] == [{"kind": "chart", "sym": "BTCUSDT", "symExact": False}, {"kind": "page", "page": "day"}], g)
r = await q("""() => { window.TB_BOOT = Date.now(); TB.touched = false; tbSyncSet({ list: [{ kind: 'page', page: 'swing' }, { kind: 'chart', sym: 'BTCUSDT', symExact: false }, { kind: 'chart', sym: 'ETHUSDT', symExact: false }], home: 'tday' });
  const b = TB.list.find(t => t.ch && t.ch.sym === 'BTCUSDT'); return [TB.list.map(t => t.page || t.ch.sym).join(), b.ch.tfs.join(), TB.home]; }""")
check("a list pulled right after opening applies at once and keeps this device's timeframes", r == ["swing,BTCUSDT,ETHUSDT", "1m,5m,15m,1h", "tday"], r)
r = await q("() => { TB.touched = true; const before = TB.list.map(t => t.page || t.ch.sym).join(); tbSyncSet({ list: [{ kind: 'page', page: 'aots' }], home: 'fund' }); return [TB.list.map(t => t.page || t.ch.sym).join() === before, localStorage.getItem('finder-tabs-in') !== null]; }")
check("a list pulled later waits for the next open", r == [True, True], r)
await q("() => { location.hash = '#nbbwatch'; }"); await asyncio.sleep(0.3)
check("a link to a removed page lands on Home", await q("() => TB.active === 'home'"))
await pg.set_viewport_size({"width": 390, "height": 844})
r = await q("() => { const n = TB.list.length; openInCharts('SOLUSDT'); return [TB.list.length === n, CH.sym]; }")
check("phone: open in a chart changes the open chart tab, no new tab", r == [True, "SOLUSDT"], r)
await pg.set_viewport_size({"width": 1440, "height": 900})
```

- [ ] **Step 2: Run to verify it fails** — Expected: `ReferenceError: tbSyncGet is not defined`.
- [ ] **Step 3: Implement** the Interfaces; set `TB_BOOT = Date.now()` when the tabs script loads.
- [ ] **Step 4: Run** `bash tests/runall.sh t_tabs t_sync`. Expected: all pass.
- [ ] **Step 5: Commit** — `"Tabs: sync the tab list, phones unchanged, links route through the tabs"`.

### Task 8: The rest of the suite, notes and version

**Files:**
- Modify: tests that click the desktop sidebar or expect `#crumb` (find them: `grep -ln "#side\|navList\|crumb" tests/*.py`): use `goPage(...)` or the tab row; keep phone tests on the More sheet.
- Modify: `CLAUDE.md` "Key code areas": a Tabs line (`TB`, `tbRead`/`tbSave`, `goPage` router + `pgShow`, `tbActivate`, `tbShowChart`/`tbSnapChart`, `TB.mem`/`tbBgTick`, `tbPlusMenu`, `#homeNav`, `SYNC_PARTS.tabs`, `openChart`; test `t_tabs`), and replace "the app itself opens on Charts" with "the app opens on the last tab".
- Modify: `version.json`, `index.html`, `sw.js` via `TZ=Asia/Manila bash bump-version.sh`.

- [ ] **Step 1: Run the full suite** — `bash tests/runall.sh` (about an hour; it can be split across parts). Expected: list of failures to fix.
- [ ] **Step 2: Fix each failure** at its cause (a changed route or selector in the test, or a real regression in the app); re-run only the failing tests.
- [ ] **Step 3: Update `CLAUDE.md`, bump the version, run** `bash tests/runall.sh t_tabs t_smoke t_start`. Expected: `errors: none`.
- [ ] **Step 4: Commit** — `"Tabs: suite, notes, version"`.
