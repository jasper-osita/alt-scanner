# Shared cTrader login and a TradingView-style market picker

## Why
Jas keeps being asked to sign in to cTrader again. Cause: cTrader's refresh token works once and rotates; every device
(Mac app, website, phone) keeps its own copy in localStorage, so the first device to renew (or a fresh sign-in anywhere)
kills the others. OANDA as a central feed is out (its API is closed to OANDA Global Markets, the Philippine division).
Goal: sign in to cTrader once, every device gets live broker prices without logging in again, and a market picker like
TradingView's that shows which source each market comes from.

## Goals
- One sign-in to cTrader; every device borrows it. No device ever renews the token itself.
- Forex, metals, indices and energy from Pepperstone (cTrader) on every device; crypto stays on Binance / Bybit / MEXC (no login).
- A TradingView-style picker: categories, sources filter, one row per market with its other sources under "+N".

## Non-goals
- No new data vendor. No server streaming prices (each device still talks to cTrader directly with the borrowed access).
- No change to how MEXC trading or crypto data work.

## Anti-goals
- The token or client secret in code, commits, the sync gist or chat.
- A shared login anyone can use: the keeper answers only to the passphrase.

## Approaches considered
1. **Keeper on the website (picked).** A Vercel function holds the token pair in a small store and renews it; devices fetch
   the current access with a passphrase. Works for the phone away from home. Needs a free Upstash Redis store on Vercel.
2. Keeper on the Mac (server.py). No new service, but the phone and website can't reach the Mac away from home.
3. Prices from MEXC / Binance perps by default, cTrader only for trading. No login for charts, but not Pepperstone's prices.

## Design
### Keeper (`api/ct-keeper.js`, Vercel)
- Env (Jas sets in Vercel): `FINDER_PASS` (12+ characters) and the Upstash Redis store (`KV_REST_API_URL`/`KV_REST_API_TOKEN`
  or `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN`, added by the Vercel integration). Redis is called over its REST API: no packages.
- `POST {action:"seed", pass, clientId, clientSecret, accessToken, refreshToken, expAt, scope}`: stores the login (from a device that just signed in).
- `POST {action:"get", pass, bad?}`: returns `{clientId, clientSecret, accessToken, expAt, scope}`. Renews first when under 3 days
  are left, or when `bad` matches the current token (the device saw it rejected). One renewal at a time (Redis lock, 30 s);
  others wait and read the new pair. Renewal uses cTrader's token service (`openapi.ctrader.com/apps/token`, refresh grant), like `api/ct-token.js`.
- `POST {action:"forget", pass}`: wipes it.
- Wrong passphrase: 403, with failed tries counted per IP (10 per hour, then 429). Nothing is logged. CORS: the site itself and `http://localhost:8787`.

### Devices (index.html)
- Connect cTrader dialog gets "Share this login with your other devices": passphrase → seed → this device switches to borrowing.
- Other devices: "Use the shared login": passphrase (and on the Mac app, the website's address once) → get.
- Borrowing mode = `ctCfg().keeper` set, no local refresh token, so `ctRenew` never runs here. Pull fresh access at start,
  every 6 hours, and when cTrader rejects the token (send `bad`, then reconnect). Price socket (`ctConnect`) and Trade socket (`cttConnect`) both use it.
- The passphrase stays in this browser (`finder-keeper`), like the Telegram token.
- server.py and vercel.json CSP: allow the keeper's address.

### Market picker (replaces the chart symbol dropdown)
- Centred dialog: search, chips All · Crypto · Forex · Indices · Metals & energy · Stocks, and "All sources ▾" (a Sources page:
  Pepperstone (cTrader), Binance, Bybit, MEXC, searchable).
- One row per market (grouped by the market's name: Gold = CT:XAUUSD, XAUUSDT, MX:XAU_USDT): icon (flags for forex pairs,
  coin logo, letter badge), symbol and description, type tag (Forex CFD, Index CFD, Perpetual, Spot, Stock perp), the preferred
  source on the right, "+N ▾" lists the others. Click the row = preferred source; click a source = that one.
- Same picker for Compare. Keyboard: arrows, Enter, Esc.

## Decided by Jas
- Keeper on the website, Pepperstone central, crypto on the exchanges, TradingView-style picker.

## Open for Jas
- Whether the shared login may trade (see the question in chat).

## Left to the builder
- Exact icons, row layout details, how the preferred source is chosen (cTrader when connected, else the scan exchange).
- Tests: mock keeper + Redis in `tests/mock.py`; `t_keeper` (seed, borrow, renew once under two devices, bad passphrase), `t_picker`.
