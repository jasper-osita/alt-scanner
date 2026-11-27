# Central bank reads: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a high-impact rate decision lands, the app fetches the bank's official statement, reads it with
rules, and shows the decision, the votes, what changed, a hawkish/dovish verdict, a long/short lean per market,
and the outlook until the next meeting. It's instant, automatic and free, and alerts stay in the app (no
Telegram).

**Architecture:**
- The DOM-free reader (`cbItems`, `cbParse`, `cbDiff`, `cbVerdict`) lives in `<script id="core">`.
- The watcher, lean, storage and UI live next to the market brief code in `index.html`.
- The relay gains two fixed-host routes: a feed per bank, and statement pages on that bank's own domain only.
- Tests use saved real statements served by Playwright mocks.

**Tech stack:** vanilla JS in `index.html`, Python `server.py` relay, Vercel rewrites, Playwright tests (Python).

**Spec:** `docs/superpowers/specs/2026-11-19-central-bank-reads-design.md`

## Global constraints
- No paid services, keys or secrets. Fetch only from the bank domains: federalreserve.gov, ecb.europa.eu,
  bankofengland.co.uk, boj.or.jp, rba.gov.au and bankofcanada.ca.
- Banks: USD Fed, EUR ECB, GBP BoE, JPY BoJ, AUD RBA, CAD BoC. Rate decision statements only.
- Verdict: a surprise against the forecast counts most, dissents next, wording least. +2 or more is Hawkish,
  −2 or less is Dovish, anything else is As expected. Always show the evidence (`why`).
- Alerts: `ncAdd` with `noTg: true`. Nothing reaches Telegram.
- Copy: plain language, sentence case, with hints for jargon ("Hawkish = leaning toward higher rates").
  It's a lean for your bias, not an entry.
- Times shown in PHT through the existing helpers (`phtDay`, `phtHM`, `inTxt`).
- After the change: `TZ=Asia/Manila bash bump-version.sh`. Tests: `bash tests/runall.sh t_cbread t_fund t_brief`.
- Commit as Jas: `git -c user.email=jasperosita18@gmail.com -c user.name="Jasper Osita" commit`, with the
  Co-Authored-By line.

## Review focus
1. **Statement not out yet.** While polling, the feed's newest decision is still the old one. The watcher
   keeps polling and neither re-reads nor re-alerts the old one. (Task 4, step "old then new")
2. **Relay path abuse.** `/proxy/cbpage/fed/@evil.com/x`, `..`, `%2F`, `:` or an unknown bank gives a 400
   from server.py and never leaves the bank's host. (Task 1)
3. **Opened days later.** The app reads a missed statement once and alerts once (if under 7 days old).
   Reloading doesn't alert again. (Task 4, step "catch-up")
4. **Statement can't be read.** A 500, a changed layout or a PDF-only statement shows "Couldn't read the
   statement (reason)" plus the decision from the feed title where possible. No page error, and at most 3
   retries per statement. (Task 4, step "failure")
5. **No forecast in the calendar.** The verdict comes from dissents and wording only, and `why` says
   "no forecast to compare". (Task 3)

---

### Task 1: Real samples, relay routes, mocks

**Files:**
- Create: `tests/cb/` (feed and statement samples), `tests/cb/expect.json`, `tests/t_cbread.py` (skeleton)
- Modify: `server.py` (next to `RSS_FEEDS`, `relay_fund`, and the `/proxy/` path dispatch), `vercel.json`
  (rewrites), `tests/mock.py` (new `setup_cb`)

**Interfaces:**
- Produces:
  - Relay `GET /proxy/cb/<bank>` returns the bank's press feed XML.
  - Relay `GET /proxy/cbpage/<bank>/<path>` returns `CB_HOSTS[bank] + "/" + path`.
  - `<bank>` is one of `fed ecb boe boj rba boc`.
  - `setup_cb(ctx)` in `tests/mock.py` serves `tests/cb/<bank>-feed.xml` and `tests/cb/<bank>/<path>`.
    `CB_SRV` lets a test swap the feed file or force a status.

- [ ] **Step 1: Get network access.** Call `get_environment`, then `update_environment` to add the six bank
  hosts (with `www.`). Jas approves one prompt. Then confirm each bank's press-release feed URL and its
  decision item title. The candidates:
  - Fed `federalreserve.gov/feeds/press_monetary.xml`, item "Federal Reserve issues FOMC statement"
  - ECB `ecb.europa.eu/rss/press.html`, item "Monetary policy decisions"
  - BoE `bankofengland.co.uk/rss/news`, items "Bank Rate maintained/reduced/increased…"
  - BoJ `boj.or.jp/en/rss/whatsnew.xml`, item "Statement on Monetary Policy"
  - RBA `rba.gov.au/rss/rss-cb-media-releases.xml`, item "Statement by the Monetary Policy Board…"
  - BoC `bankofcanada.ca/content_type/press-releases/feed/`, items "Bank of Canada maintains/reduces…"
- [ ] **Step 2: Save the samples.** For each bank, save the feed as `tests/cb/<bank>-feed.xml` and its last
  two decision statements under `tests/cb/<bank>/<same path as on the site>`. Where they exist, also save a
  past statement with a hike or cut and one with a dissent, plus their predecessors. Note in `expect.json`
  any bank whose statement is only a PDF.
- [ ] **Step 3: Write `tests/cb/expect.json`.** Fill it in by reading each sample by hand:
  `{ "<bank>/<path>": { "move": "hold|hike|cut", "rate": <new policy rate %, upper bound for ranges>,
  "hawk": <dissents wanting higher>, "dove": <dissents wanting lower>, "minSentences": <n> } }`.
- [ ] **Step 4: Relay.** In server.py, add `CB_FEEDS` and `CB_HOSTS` dicts, plus two routes in `relay_fund`:
  - `^/proxy/cb/([a-z]+)$` uses `cached_get("cb"+bank, CB_FEEDS[bank], 30, BROWSER)`.
  - `^/proxy/cbpage/([a-z]+)/([A-Za-z0-9/_.\-]+)$` (rejecting `..` and `//`) uses a cache of 3600 s.
  - Anything else gives 400 `{"error":"not allowed"}`.
  - Route both paths through the same dispatch as `/proxy/rss`.
  - In `vercel.json`, add the matching rewrites (`/proxy/cb/fed` → feed URL, and
    `/proxy/cbpage/fed/:path*` → `https://www.federalreserve.gov/:path*`, for each bank).
- [ ] **Step 5: Relay check.** Run a python check that imports `server` and calls `relay_fund` for each
  abusive path in Review focus 2. Expected: code 400 for each, and a valid fed path matches without fetching
  (monkeypatch `cached_get` to return the URL).
- [ ] **Step 6: Mocks.** Add `setup_cb(ctx)` to `tests/mock.py`. Create the `tests/t_cbread.py` skeleton,
  modeled on `t_fund.py`: `serve()`, `setup`, `setup_extra`, `setup_fund`, `setup_cb`, the `errs` list,
  `q`/`wait`, and printing `errors:` at the end. Run `bash tests/runall.sh t_cbread`. Expected: it runs
  with `errors: none`.
- [ ] **Step 7: Commit.** "Central bank reads: statement samples, relay routes, mocks".

### Task 2: Reader in core (`cbItems`, `cbParse`)

**Files:** Modify `index.html` `<script id="core">` (after `rssItems`). Test: `tests/t_cbread.py`.

**Interfaces:**
- Produces:
  - `CB_BANKS: { [ccy]: { bank: "Fed", key: "fed", host: "https://www.federalreserve.gov", item: RegExp } }`
    for the six banks, with the feed item regexes confirmed in Task 1.
  - `cbItems(ccy, xml) -> [{ title, link, path, t }]` returns decision items only, newest first. It handles
    RSS `<item>` and Atom `<entry>` (`link href`). `path` is the link without the host.
  - `cbParse(ccy, html) -> { ok, err?, sentences: string[], move: "hike"|"cut"|"hold"|null, rate: number|null, hawk: number, dove: number }`.

- [ ] **Step 1: Failing test.** Add test step "1) parse". For every key in `expect.json`, fetch
  `/proxy/cbpage/<key>` in the page, run `cbParse` and assert `move`, `rate`, `hawk` and `dove` equal
  `expect.json`, with `sentences.length >= minSentences`. Also assert `cbItems` on each feed returns ≥ 1 item,
  the newest first.
- [ ] **Step 2: Run it.** `bash tests/runall.sh t_cbread`. Expected: FAIL, `cbParse is not defined`.
- [ ] **Step 3: Implement it.**
  - Take one body region per bank (the statement's main container, seen in the samples). Strip tags, decode
    entities, then split sentences on `/(?<=[.!?])\s+(?=[A-Z"])/`.
  - Drop sentences under 25 characters, and the boilerplate lines (media contacts, "Implementation Note",
    voting lists kept only for the dissent read).
  - Read the decision and rate with each bank's wording, for example: Fed "raise/lower/maintain the target
    range … to X to Y percent"; BoE "voted … to maintain/reduce/increase Bank Rate … to X%"; ECB "deposit
    facility rate". Use the ECB's deposit facility rate, which matches the rates table.
  - Count dissents from "Voting against … who preferred to lower/raise", from the BoE "n members voted to
    reduce/increase", and from the BoJ/RBA/BoC vote lines where present.
  - For a PDF-only bank, return `ok: false, err: "statement is a PDF"`, with `move` and `rate` from the feed
    title when it states them (pass the title as an optional third argument).
- [ ] **Step 4: Run it.** Same command. Expected: step 1 prints matches for every sample, and `errors: none`.
- [ ] **Step 5: Commit.** "Central bank reads: statement reader in core".

### Task 3: Wording changes, verdict, lean

**Files:** Modify `index.html`: core (`cbDiff`, `cbVerdict`), and next to `fbDrivers` (`cbLean`).
Test: `tests/t_cbread.py`.

**Interfaces:**
- Consumes: `cbParse` output (Task 2), `FB_MK`.
- Produces:
  - `cbNorm(s) -> string`: lowercase; numbers and fractions such as `3-3/4` become `#`; month names become
    `@`; whitespace collapsed.
  - `cbDiff(prevSentences, curSentences) -> { added: string[], dropped: string[] }`: compares by `cbNorm`.
  - `CB_HAWK`, `CB_DOVE`: phrase arrays.
  - `cbVerdict(p, diff, forecast /* number|null */) -> { score, label: "Hawkish"|"Dovish"|"As expected", why: string[] }`.
  - `cbLean(ccy, label) -> [{ k /* FB_MK key */, dir: "long"|"short" }]`.

- [ ] **Step 1: Failing test.** Add step "2) verdict & lean" (pure `page.evaluate`):
  - `cbVerdict({move:"hike",rate:4.25,hawk:0,dove:0},{added:[],dropped:[]},4.0).label == "Hawkish"`,
    with `why[0]` mentioning both 4.25% and 4.00%.
  - The same with `rate:4.0` gives "As expected".
  - `{hold, rate 4, dove 2}` with forecast 4 gives "Dovish".
  - Added `["Upside risks to inflation have increased."]` plus dropped `["...further adjustments..."]` gives
    score +2, "Hawkish".
  - Forecast `null` with no dissents gives "As expected", and `why` includes "no forecast to compare".
  - `cbDiff(["In September, inflation rose to 3.1 percent."],["In October, inflation rose to 2.9 percent."])`
    has 0 added and 0 dropped.
  - `cbLean("USD","Hawkish")` includes Gold short, Nasdaq 100 short, US dollar long, EUR/USD short and
    USD/JPY long.
  - `cbLean("JPY","Hawkish")` includes USD/JPY short and Nikkei 225 short.
  - `cbLean(x,"As expected")` is `[]`.
  - Running the diff on each bank's two real samples matches `added`/`dropped` counts in `expect.json`
    (add those fields in this step).
- [ ] **Step 2: Run it.** Expected: FAIL, `cbVerdict is not defined`.
- [ ] **Step 3: Implement it.**
  - **Surprise:** when `|rate − forecast| ≥ 0.05`, add `±3`.
  - **Dissents:** `+1` per hawk and `−1` per dove, capped at ±2.
  - **Wording:** a hawk phrase in added gives +1, in dropped −1; a dove phrase the reverse. Capped at ±2.
  - **Phrase lists** (tune on the samples, keep them short):
    - `CB_HAWK`: "upside risks", "further tightening", "additional policy firming", "remain vigilant",
      "inflation remains elevated", "restrictive for longer", "price pressures".
    - `CB_DOVE`: "further adjustments", "additional adjustments", "downside risks", "has softened",
      "has eased", "reduce the degree of", "less restrictive".
  - **Lean sign** (`s` = +1 for hawkish, −1 for dovish):
    - fx base = ccy gives s; fx quote = ccy gives −s
    - `usd` kind and ccy USD gives s
    - gold, oil, copper and btc with ccy USD give −s
    - idx whose `ccy[0]` = ccy gives −s
- [ ] **Step 4: Run it.** Expected: step 2 prints all pass, and `errors: none`.
- [ ] **Step 5: Commit.** "Central bank reads: wording changes, verdict, lean".

### Task 4: Watcher, storage, catch-up, alert

**Files:** Modify `index.html`, next to `rxTick`. Add the `noTg` check in the Telegram wrapper:
`ncAdd = function (n) {…}` gets `!n.noTg &&`. Test: `tests/t_cbread.py`.

**Interfaces:**
- Consumes: Tasks 2–3, `calAll()`, `ncAdd`, `naMine()`, `RX_MK`.
- Produces:
  - `CBR` = `lsGet("finder-cbreads", {})`, shaped `{ [ccy]: Read[] }`, newest first, max 2 per bank.
  - `Read = { id /* link */, title, at, readAt, ok, err?, p, diff, v, forecast, tries }`.
  - `cbDue(now) -> ccy[]`: high-impact Central Bank events for the six currencies with
    `at − 2 min ≤ now ≤ at + 90 min`.
  - `cbTick(now = Date.now()) -> Promise`: polls due banks at most every 45 s.
  - `cbCatchUp() -> Promise`: once per bank per 6 h. On app open, after 5 s.
  - `cbRead(ccy, item) -> Promise<Read>`
  - Scheduling: `setInterval(() => cbTick().catch(() => {}), 15e3)`.

- [ ] **Step 1: Failing tests.** Add these test steps:
  - **"3) old then new":**
    1. Inject a Fed event 1 min ahead with forecast "4.00%" into `CAL.items`.
    2. Serve the feed without the new item and call `cbTick(at + 60e3)`. Expect no new read and no alert.
    3. Swap the feed via `CB_SRV` and call `cbTick(at + 120e3)`. Expect one new read, with `diff` computed
       against the stored previous one, and exactly one alert with icon 🏦, kind News, `noTg` true, and a
       title like "Fed held at 4.00%: hawkish".
    4. Reload. The alert count is still 1.
  - **"4) catch-up":**
    1. Clear storage and serve a feed whose newest decision is 2 days old. After load, there is 1 read and
       1 alert.
    2. Repeat with a 10-day-old decision: 1 read, 0 alerts.
    3. With no stored previous read, the previous statement is fetched from the feed's second decision item.
  - **"5) failure":** `CB_SRV` forces 500 on the page. The read has `ok: false` and `err`, `tries` ≤ 3 after
    5 ticks, and `errors: none`.
  - **"6) no Telegram":** with Telegram set up (`lsSet(TG_KEY, …)` on, News kind on), stub `tgSend` to
    count calls, then trigger a read. Expect 0 calls.
- [ ] **Step 2: Run them.** Expected: FAIL, `cbTick is not defined`.
- [ ] **Step 3: Implement it.**
  - In `cbRead`, `forecast` is the matching calendar event's `forecast` parsed as a number (same ccy, type
    "Central Bank", within ±1 day of `item.t`), otherwise null.
  - Alert only when the read is new and `item.t` is under 7 days old.
  - The `ncAdd` payload:
    `{ kind: "News", icon: "🏦", tone: "warn", action: "brief", mk: <first naMine() market whose currencies include ccy, else RX_MK[ccy]>, title: "<Bank> <held|raised|cut> at <rate>%: <label lowercased>", detail: <top 3 lean chips as text>, noTg: true }`.
- [ ] **Step 4: Run them.** Expected: steps 3–6 pass, and `errors: none`.
- [ ] **Step 5: Commit.** "Central bank reads: watcher, catch-up, in-app alert (no Telegram)".

### Task 5: Fundamentals panel, brief section, "Today's read" line

**Files:** Modify `index.html`:
- `fundRender` (new panel after `.fcb`)
- a new `fundCBReads()`
- CSS next to the `.fcb` rules
- `fbRender`: a new section, plus a line in the copied brief
- `fundCardsData`: a reason line

Test: `tests/t_cbread.py`.

**Interfaces:**
- Consumes: `CBR`, `cbLean`, `fbMeet`, `fundBank`, `FB_BANK`, `fbFedExp`, `calAll`, `fbOpen`.
- Produces: `fundCBReads() -> html`, `cbCardHTML(ccy, read) -> html`, `cbL(ccy, g) -> [sign, text] | null`.

- [ ] **Step 1: Failing test.** Add step "7) panel":
  - `#fundBody .fcbr` has a header "Central bank reads", and one card per bank with a read, newest first.
  - The Fed card text includes the decision, the verdict chip, "Gold short", a "What changed" list with
    ≤ 3 added and ≤ 3 dropped, and "Until the next meeting" with the next FOMC date from `FOMC_DATES` and
    the stance.
  - The statement link has `target=_blank`, `rel=noopener`, and an href on federalreserve.gov.
  - Clicking "Gold short" opens the brief for Gold, and the brief contains "Last central bank read".
  - The Gold card under "Today's read" contains "Fed statement hawkish".
  - At a 390 px wide viewport, `document.documentElement.scrollWidth <= 390`.
  - For a read with `ok: false`, the card shows "Couldn't read the statement".
- [ ] **Step 2: Run it.** Expected: FAIL, no `.fcbr`.
- [ ] **Step 3: Implement it.** Each card contains:
  - the bank name and statement date (PHT)
  - the decision line (for example "Held at 4.00% · expected 4.00%")
  - a votes line, only when there are dissents
  - the verdict chip (`fk up` for dovish/`dn` for hawkish on risk), with a hint title
  - lean chips as `data-fmk` (up = long, dn = short)
  - "What changed": added sentences with "+" and dropped with "−", phrase matches first. For the first read,
    show "Nothing to compare yet".
  - "Until the next meeting": date and countdown via `fbMeet`; the stance via `fundBank`; for USD, the line
    from `fbFedExp().txt`; then "Could change it:" listing up to 4 high-impact events for that currency
    before the next meeting, from `calAll()`.
  - the link "Read the statement ↗"
  - the footer: "Read by rules from the bank's own statement. A lean for your bias, not an entry."

  Empty state: "No decisions read yet. The next one: <bank> <date>."

  For "Today's read", `cbL` adds `[g·(hawk?+1:−1), "<Bank> statement <label lowercased> (<Mon D>)"]` for
  reads under 7 days old that aren't "As expected": Gold `cbL("USD",-1)`, Nasdaq `cbL("USD",-1)`, US dollar
  `cbL("USD",1)`, Bitcoin `cbL("USD",-1)`.
- [ ] **Step 4: Run it.** Expected: step 7 passes. Then run `bash tests/runall.sh t_fund t_brief` and expect
  `errors: none` for both.
- [ ] **Step 5: Commit.** "Central bank reads: Fundamentals panel, brief section, today's read".

### Task 6: Ship

**Files:** `CLAUDE.md` (one line under Fundamentals: `CBR`/`cbTick`/`cbParse`, relay `/proxy/cb`, test
`t_cbread`), `version.json`, `index.html` and `sw.js` (via the bump).

- [ ] **Step 1:** `TZ=Asia/Manila bash bump-version.sh`
- [ ] **Step 2:** `bash tests/runall.sh t_cbread t_fund t_brief t_smoke`. Expected: no "FAILED".
- [ ] **Step 3:** Commit "Central bank reads on Fundamentals" and push to `claude/determined-allen-et7nki`.
