# Central bank reads: design

## Why
After a big central bank decision, Jas wants the app to read the bank's official statement and tell him
what it means for his trading: hawkish or dovish, which way it leans each market (long/short), and what
to expect until the next meeting. It has to be instant and fully automatic, with no extra cost:
no paid AI, no API key, and nothing for him to copy or paste.

## Goals
- When a high-impact central bank decision is due, the app watches the bank's own press feed. As soon as
  the statement is published, it fetches the statement and reads it.
- The read shows:
  - **Decision**: hike, cut or hold, and the new rate, compared with the calendar's forecast.
  - **Vote**: dissents and which way the dissenters wanted to go (for example "2 wanted a cut").
  - **What changed**: sentences added or dropped since the bank's previous statement.
  - **Verdict**: Hawkish, Dovish or As expected, with the reasons behind it.
  - **Lean per market**: long or short (bullish/bearish) for Gold, Nasdaq, the dollar and the FX pairs
    that use that currency.
  - **Until the next meeting**: the date and countdown, the bank's stance, what the market prices
    (2-year yield for the Fed, from `fbFedExp`), and the high-impact data for that currency before the
    next meeting that could change the picture.
- An in-app alert when the read is ready (bell icon), for example:
  "🏦 Fed held at 3.75%: hawkish · Gold short, Nasdaq short, dollar long". Not sent to Telegram yet
  (Jas's call).
- If the app was closed during the meeting, it reads any statement it missed the next time it opens.

## Non-goals (for now)
- Press-conference transcripts, minutes and speeches. These come later or as PDFs days later.
- Economic data (CPI, jobs). Those keep the existing market-reaction read (`rxTick`).
- Paid AI, or a "Copy for Claude" step.
- Telegram, from the app or from the cloud watcher. Jas asked to leave it out for now. It's possible
  later, because the reader lives in core.

## Anti-goals
- A read that sounds more certain than rules can be. Every verdict shows its evidence (the decision, the
  vote, the changed sentences) and is marked as a rules-based read with a hint.
- An entry signal. This stays "a lean for your bias, not an entry", like the rest of Fundamentals.
- Fetching anything other than the official central bank sites.

## Approaches considered
1. **The app reads the statement itself, with rules (chosen).** Free, instant and automatic. It reads the
   decision, the votes and the wording changes, not tone.
2. A paid Claude API read (cloud watcher or relay). Rejected: costs money.
3. A scheduled Claude Code session on Jas's plan. Rejected: it runs at fixed times, uses plan limits, and
   has more parts to go wrong.
4. "Copy for Claude" for a written read. Dropped: Jas doesn't want to do anything manually.

## Scope: which banks
The six currencies the app already reads reactions for (`RX_CCY`): Fed (USD), ECB (EUR), BoE (GBP),
BoJ (JPY), RBA (AUD) and BoC (CAD). SNB and RBNZ come later. *(My call.)*

## How it works
1. **Trigger.** A loop on every page, like `rxTick`/`naCheck`, sees a calendar event with
   `type === "Central Bank"` and `impact === "High"` for one of the six currencies (the rate decision or
   statement event). Polling of that bank's feed:
   - starts 2 minutes before the decision
   - runs every 30–60 seconds until the new statement appears
   - stops after 90 minutes

   On app open, it also checks each bank's feed once for a decision it hasn't read yet.
2. **Fetch.** Through the relay, as headlines work today:
   - `server.py` (`relay_fund`) and a Vercel function (`api/cb.js`, like `api/fred.js`).
   - Two calls: the bank's press feed, and the statement page.
   - The relay only fetches from the official domains: federalreserve.gov, ecb.europa.eu,
     bankofengland.co.uk, boj.or.jp, rba.gov.au and bankofcanada.ca. The same relay cache pattern
     (`cached_get`) applies.
3. **Read** (in `<script id="core">`, DOM-free, so it can be tested and reused by the cloud watcher later):
   - `cbParse(bank, html)` returns the statement sentences, the decision and the votes. There is one
     small rule set per bank, since each bank words it differently: "maintain the target range",
     "voted by a majority of 7–2 to maintain Bank Rate", "decided to keep the three key ECB interest
     rates unchanged", and so on.
   - `cbDiff(prev, cur)` lists the sentences added and dropped against the bank's previous decision
     statement. The previous statement is the earlier decision item in the same feed.
   - `cbVerdict` scores the read:
     - a surprise against the forecast (calendar `forecast`) counts most
     - dissents toward a hike or cut count next
     - hawkish/dovish phrases in the added and dropped sentences count least ("further tightening",
       "upside risks", "remain vigilant" against "further adjustments", "downside risks",
       "labour market has softened")

     A score of +2 or more is Hawkish, −2 or less is Dovish, anything else is As expected.
   - `cbLean(ccy, verdict)` returns long/short per market in `FB_MK`, using the same signs as
     `fbDrivers` `bank()`:
     - a hawkish Fed means dollar long and Gold, Nasdaq, S&P and EUR/USD short
     - a hawkish BoJ means USD/JPY short, and so on
4. **Store.** Reads are saved in localStorage (`finder-cbreads`, last 2 per bank, with the statement text
   so the next meeting can be compared with it).
5. **Show.**
   - **Fundamentals:** a new panel, "Central bank reads", next to "Rates & central banks". It has one card
     per bank, latest first. Each card shows the decision, a verdict chip, lean chips, what changed
     (top 3 sentences), "Until the next meeting", and a link to the statement on the bank's site. Clicking
     a lean chip opens that market's brief.
   - **Market brief:** a "Last central bank read" section for the market's currencies.
   - **"Today's read" cards:** a fresh hawkish/dovish read (less than 7 days old) adds a reason line,
     such as "Fed statement hawkish (Oct 28)".
6. **Alert.** `ncAdd` with `kind: "News"`, `action: "brief"` and a new `noTg: true` flag, sent once per
   statement. The Telegram wrapper around `ncAdd` skips any alert carrying `noTg`.

## Constraints
- No new paid services, no keys, and no secrets.
- Plain-language copy in sentence case, with a hint for jargon (for example, hawkish = leaning toward
  higher rates).
- Tests use saved samples of real statements in `tests/mock.py`, with no network. A new `t_cbread` test
  covers parse, diff, verdict, lean, the panel, the brief section and the alert.
- Bump the version with `bump-version.sh`. Also keep the relay paths out of the service worker cache
  (`sw.js` already skips `/proxy`).

## Left to the builder / to verify
- The exact feed URLs and page structure per bank. Claude's cloud container is blocked from these sites,
  so Jas approves one network prompt to allow them while the readers are built. The app itself fetches
  from his Mac or Vercel.
- Banks that publish the statement only as a PDF (possibly BoJ). For those, read the decision and the
  vote from the feed item and the HTML summary page, and skip "what changed" if no HTML text exists.
- Exact phrase lists and weights, tuned against several past statements per bank.
