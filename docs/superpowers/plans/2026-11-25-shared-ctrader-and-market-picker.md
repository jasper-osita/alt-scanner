# Shared cTrader login and market picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign in to cTrader once and let every device borrow that login from a keeper on the website; replace the chart symbol dropdown with a TradingView-style picker that groups each market's sources.

**Architecture:** A Vercel function (`api/ct-keeper.js`) stores the cTrader token pair in Upstash Redis (REST, no packages), renews it alone, and hands the current access to callers with the passphrase. Devices run in "keeper mode" (`ctCfg().keeper`, no local refresh token, so `ctRenew` never runs) and re-pull on rejection. The picker is a centred dialog built from a grouped market list.

**Tech Stack:** Vanilla JS in `index.html`, Vercel Node functions (global `fetch`, `crypto`), Playwright tests with `tests/mock.py`, Node for the function test.

**Spec:** `docs/superpowers/specs/2026-11-25-shared-ctrader-and-market-picker-design.md`

## Global Constraints

- Never put the cTrader client ID/secret/tokens or the passphrase in code, commits, the sync gist or chat. Tokens live in the browser (`finder-ctrader`) and the keeper store only.
- The shared login may trade (Jas decided): the keeper returns whatever scope was seeded.
- `FINDER_PASS` must be 12+ characters; wrong passphrases: 10 per hour per IP, then 429.
- Keeper renews when under 3 days are left (259200000 ms), or when the caller reports the current token as rejected. One renewal at a time (Redis lock, 30 s).
- No npm packages in `api/`. Redis via REST: env `KV_REST_API_URL`/`KV_REST_API_TOKEN`, else `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN`.
- Keeper CORS: same host and `http://localhost:8787` only. Nothing logged.
- UI copy: plain language, sentence case. After changes: `TZ=Asia/Manila bash bump-version.sh`. Commit as Jas (CLAUDE.md), message ends with the Co-Authored-By and Claude-Session lines.

## Review Focus

- Two devices ask the keeper at the same moment near expiry → cTrader's token service is called once; both get the new pair (Task 1 test `concurrent renew`).
- cTrader rejects the borrowed token mid-session (payload 2147) → the device pulls with `bad`, reconnects, never shows "paste a fresh token" (Task 2 test step 4).
- Keeper not set up yet (no Redis env or `FINDER_PASS`) → 503 with a sentence saying what to add; the dialog shows it; the local login keeps working (Task 1 `unconfigured`, Task 2 step 5).
- Wrong passphrase repeatedly → 403 then 429 after 10; no token in any error body (Task 1 `lockout`).
- cTrader not connected → picker has no Pepperstone source, the preferred source is the scan exchange, Gold still lists Binance and MEXC (Task 3 step 5).

---

### Task 1: The keeper function

**Files:**
- Create: `api/ct-keeper.js`
- Create: `tests/keeper_test.mjs` (Node, fakes `fetch` for Redis REST and `openapi.ctrader.com/apps/token`)
- Create: `tests/t_keeper.py` (runs `node tests/keeper_test.mjs`, prints its lines; any `FAIL` line → print `errors: [...]`)

**Interfaces:**
- Produces: `POST /api/ct-keeper` with JSON body:
  - `{action:"seed", pass, clientId, clientSecret, accessToken, refreshToken, expAt, scope}` → `200 {ok:true}`
  - `{action:"get", pass, bad?}` (`bad` = last 8 characters of a token cTrader rejected) → `200 {clientId, clientSecret, accessToken, expAt, scope}`
  - `{action:"forget", pass}` → `200 {ok:true}`
  - Errors `{error:"<sentence>"}`: 400 bad request, 403 wrong passphrase, 429 too many tries, 404 nothing shared yet, 502 cTrader renewal failed, 503 not set up.
  - `OPTIONS` → 204 with CORS headers for allowed origins.
- Redis keys: `ct:login` (JSON of the seed fields), `ct:lock` (`SET NX EX 30`), `ct:fail:<ip>` (`INCR`, `EXPIRE 3600`).

- [ ] **Step 1: Write `tests/keeper_test.mjs`** — loads the module with a fake `req`/`res`, an in-memory Redis behind a fake `fetch`, and a fake token service counting calls. Cases, each printing `ok <name>` or `FAIL <name>: <why>`:
  - `unconfigured`: no Redis env → 503, body mentions "Upstash" and "FINDER_PASS"; `FINDER_PASS` of 8 chars → 503.
  - `wrong pass`: 403; body has no `accessToken`.
  - `lockout`: 10 wrong → 403 each, 11th → 429; a right pass from another IP still works.
  - `seed then get`: get returns the seeded `accessToken`, `clientSecret`, `scope`; token service calls = 0.
  - `renew near expiry`: seed with `expAt = now + 2 days` → get returns the new token; stored `refreshToken` is the new one; calls = 1.
  - `concurrent renew`: two gets in `Promise.all` near expiry → calls = 1, both return the same new token.
  - `bad token`: `bad` = last 8 of current → renew (calls 1); `bad` of an older token → no renew.
  - `renew failed`: token service returns 400 → 502, stored login unchanged.
  - `cors`: origin `http://localhost:8787` echoed in `Access-Control-Allow-Origin`; origin `https://evil.example` not.
  - `forget`: then get → 404.
- [ ] **Step 2: Run** `bash tests/runall.sh t_keeper` → fails (module missing).
- [ ] **Step 3: Implement `module.exports = async (req, res) => {}` in `api/ct-keeper.js`.** Passphrase check with `crypto.timingSafeEqual` on SHA-256 digests. Renewal: `GET https://openapi.ctrader.com/apps/token?grant_type=refresh_token&refresh_token=…&client_id=…&client_secret=…` (same service as `api/ct-token.js`); new `expAt = now + expires_in*1000` (default 30 days). Lock holder renews; others poll `ct:login` every 500 ms up to 10 s.
- [ ] **Step 4: Run** `bash tests/runall.sh t_keeper` → all `ok`, `errors: none`.
- [ ] **Step 5: Commit** `api/ct-keeper.js tests/keeper_test.mjs tests/t_keeper.py`.

### Task 2: Devices borrow the shared login

**Files:**
- Modify: `index.html` core cTrader block (`ctBind` ~2491, `ctConnect` ~2517, renewal timer ~2578), Trade socket `cttConnect` (~11353), `openCTSettings` (~6971)
- Modify: `server.py` CSP (`connect-src` += `https://*.vercel.app`)
- Modify: `tests/mock.py`: `route_keeper(ctx, state)` — a fake `/api/ct-keeper` keeping `state = {login, gets, seeds, serve_stale}`
- Create: `tests/t_keeper_ui.py`
- Modify: `CLAUDE.md` (one line under cTrader: keeper mode)

**Interfaces:**
- Consumes: Task 1's endpoint and bodies.
- Produces (index.html, UI script or core with `typeof window` guards):
  - `KP = () => ({ pass: "", url: "", ...localStorage "finder-keeper" })`; `kpUrl() -> string` (`url` if set, else `location.origin`) + `/api/ct-keeper`.
  - `async ctKeeper(action: string, extra?: object) -> object` (throws `Error(body.error)`).
  - `async ctKeeperPull(badToken?: string) -> cfg` — saves `{clientId, clientSecret, accessToken, expAt, scope, keeper: true, refreshToken: ""}` merged into `ctCfg()`.
  - `async ctKeeperSeed(pass: string) -> void` — seeds from the current `ctCfg()`, then drops the local refresh token and sets `keeper: true`.

- [ ] **Step 1: Write `tests/t_keeper_ui.py`** (ct mock + `route_keeper`, two contexts):
  1. A: `finder-ctrader` = `{clientId:'cid', clientSecret:'sec', accessToken:'tok', refreshToken:'ref'}`; Connect cTrader → "Share this login" → passphrase `correct horse 42` → keeper `seeds == 1`; A's `ctCfg()` has `keeper: true`, `refreshToken == ""`; `CT.state == "ready"`.
  2. B (empty storage): "Use the shared login" → same passphrase → `CT.state == "ready"`; `ctCfg().accessToken == "tok"`.
  3. `CT_LOG.count(2173) == 0` after both (no device renewed).
  4. Keeper `serve_stale`: B reconnects with token `stale` → mock answers 2142 → B calls get with `bad: "stale"[-8:]` → keeper returns `tok-renewed` → `CT.state == "ready"`; no "Paste a fresh" text anywhere.
  5. Keeper answering 503 `{error:"…FINDER_PASS…"}` → the dialog shows that sentence; A's existing connection stays `ready`.
  6. Wrong passphrase → dialog shows "That passphrase didn't work"; `localStorage finder-keeper` not saved.
  7. `cttConnect()` on B resolves (Trade socket uses the borrowed token).
- [ ] **Step 2: Run** `bash tests/runall.sh t_keeper_ui` → fails.
- [ ] **Step 3: Implement** the four functions above; in `ctConnect`: if `cfg.keeper` and `expAt - now < 864e5` pull first; on a token error with `cfg.keeper` → `ctKeeperPull(cfg.accessToken.slice(-8))` and retry 2149 once. In `ctBind`: payload 2147 with `keeper` → pull with `bad`, then `ctScheduleReconnect(true)`. Pull every 6 h while `keeper`. `cttConnect`: same one retry. Dialog: "Share this login with your other devices" (shown when signed in and not borrowing), "Use the shared login" (passphrase; plus "Website address" field only when `location.hostname === "localhost"`), "Stop using the shared login" (forgets `finder-keeper`, keeps nothing). server.py CSP line.
- [ ] **Step 4: Run** `bash tests/runall.sh t_keeper_ui t_ct t_ctkeep t_ctsignin t_ctfeed` → all `errors: none`.
- [ ] **Step 5: Commit** index.html, server.py, tests/mock.py, tests/t_keeper_ui.py, CLAUDE.md.

### Task 3: TradingView-style market picker

**Files:**
- Modify: `index.html` charts script: picker section (`chPickOpen`/`chPickRender` ~8394–8430, `CH_CATS` ~8442, `chCatList` ~8453) and its callers (`#chSymBtn`, `[data-cat]` toolbar buttons, `#chCmpBtn`)
- Create: `tests/t_picker.py`
- Modify: `tests/t_chpick.py` only where it relies on the old dropdown markup
- Modify: `CLAUDE.md` (Charts line: `pkMarkets`, `pkOpen`)

**Interfaces:**
- Consumes: `chName(sym)`, `chCatOf(sym)`, `chQuote(sym)`, `ctList()`, `MX_INFO`, `MACRO_INFO`, `ctPrefer()`, `chSetSym`, `chCmpAdd`.
- Produces:
  - `PK_SRC = { ct, binance, bybit, mexc }` → display names (`ct` uses `CT.broker || "Pepperstone"`, shown as "<broker> (cTrader)").
  - `pkSrcOf(sym) -> "ct"|"binance"|"bybit"|"mexc"`.
  - `pkType(sym) -> "Forex CFD"|"Index CFD"|"Metal CFD"|"Energy CFD"|"Perpetual"|"Spot"|"Stock perp"`.
  - `pkMarkets(cat, src) -> [{ key, name, desc, type, cat, syms }]` — one entry per market, `syms[0]` the preferred source (cTrader when `ctPrefer()`, else the scan exchange, else MEXC). Grouping key: `chName(sym)` normalised (case, spaces, "/" removed), so Gold = `CT:XAUUSD`, `XAUUSDT`, `MX:XAU_USDT`.
  - `pkOpen({ cat = "all", onPick = chSetSym })`. Markup ids kept for old tests: search input `#chPickQ`, rows `[data-pk]`, each source `[data-ps="<sym>"]`, more toggle `[data-more]`, chips `[data-pc]`, sources button `#pkSrcB`, sources page items `[data-src]`.
- Layout (copy fixed): placeholder "Symbol or name"; chips All · Crypto · Forex · Indices · Metals & energy · Stocks · Recent; "All sources ▾"; Sources page title "Sources" with its own search.

- [ ] **Step 1: Write `tests/t_picker.py`** (ct mock connected, MEXC mock on):
  1. `#chSymBtn` → dialog visible, chips text in order above, search focused.
  2. Type `gold` → exactly one `[data-pk]` row; its source text contains "Pepperstone"; `[data-more]` shows `+2`; expanding lists `XAUUSDT` and `MX:XAU_USDT`.
  3. Click `[data-ps="MX:XAU_USDT"]` → dialog closed, `CH.sym == "MX:XAU_USDT"`.
  4. Chip Forex → every row's `pkCls` is fx; Sources page → MEXC → every listed `[data-ps]` is `MX:`; "All sources" restores.
  5. cTrader disconnected (`CT.state = "closed"`, `ctPrefer` false) → Gold row's first source is Binance; `+1`.
  6. `#chCmpBtn` → same dialog; Enter on the first row → `CH.cmp` gains it, `CH.sym` unchanged.
  7. Esc closes; arrows move the highlight (`.sel` index changes).
- [ ] **Step 2: Run** `bash tests/runall.sh t_picker` → fails.
- [ ] **Step 3: Implement** the produced functions and dialog (built with `chModal`, class `chmpk`); icons: forex pairs = two flag emoji from currency codes, crypto = the existing TradingView logo `<img>` with letter fallback (as `logoHTML`), others = letter badge in the group colour (`MACRO_COL`). Remove the old dropdown body (`chPickRender`'s list); keep `chPickOpen(cat, onPick)` as a thin wrapper calling `pkOpen` so other callers keep working.
- [ ] **Step 4: Run** `bash tests/runall.sh t_picker t_chpick t_charts t_tvx t_fxchart t_mxtf t_mob` → all `errors: none`.
- [ ] **Step 5: Bump, commit, push** (`TZ=Asia/Manila bash bump-version.sh`; index.html, version.json, sw.js, tests, CLAUDE.md).

### Task 4: Set up the keeper on Vercel (needs the Vercel connector signed in, or Jas)

- [ ] **Step 1:** Vercel project for this repo → Storage → add Upstash Redis (free) → connect to the project (adds the REST env vars).
- [ ] **Step 2:** Add env `FINDER_PASS` (12+ characters, chosen by Jas; never written in chat or code).
- [ ] **Step 3:** Deploy the branch (preview) and check `curl -s -X POST <preview>/api/ct-keeper -d '{"action":"get","pass":"x"}'` → `403 {"error":"That passphrase didn't work"}` (proves Redis + env are wired).
- [ ] **Step 4:** On the website: Connect cTrader → sign in → Share this login. On the phone and the Mac app: Use the shared login.
