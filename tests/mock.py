"""Mock market data for testing Alt Scanner offline: Binance futures + spot, CoinGecko, alternative.me.
Every timeframe is aggregated from one hourly path per coin, so 15m/1H/4H/1D candles agree."""
import json, math, random, time, hashlib, os, threading, http.server, socketserver, re
from urllib.parse import urlparse, parse_qs
H = 3600_000
NOW = (int(time.time() * 1000) // H) * H            # top of the current hour; the last hourly candle is still forming
NH = 5600                                           # ~233 days of hourly history
MAJ = ["BTC", "ETH", "SOL"]
NAMED = ["XRP","DOGE","ADA","TRX","AVAX","LINK","DOT","SUI","TON","NEAR","APT","ARB","OP","INJ","TIA","SEI","JUP","WIF","1000PEPE","BONK",
         "FET","RENDER","TAO","UNI","AAVE","LDO","ENA","PENDLE","ZRO","HYPE","ZEC","LTC","BCH","ATOM","FIL","ICP","ETC","XLM","HBAR","STRK",
         "ONDO","WLD","GALA","SAND","MANA","AXS","IMX","PYTH","JTO","RUNE","CRV","DYDX","GMX","ORDI","STX","POPCAT","BRETT","VIRTUAL","KAITO","EIGEN"]
GEN = [f"C{i:03d}" for i in range(1, 100)]
SPECIAL = ["LONGXIA", "COOLX", "RUNX"]                # known shapes for testing the momentum board
BASES = MAJ + NAMED + GEN + SPECIAL
COINS = [b + "USDT" for b in BASES]
# Binance TradFi perpetuals (gold, oil, index ETFs...) plus two that the macro page must ignore
TRADFI = {"XAU": "COMMODITY", "XAG": "COMMODITY", "XPT": "COMMODITY", "XPD": "COMMODITY", "COPPER": "COMMODITY", "CL": "COMMODITY", "BZ": "COMMODITY",
          "NATGAS": "COMMODITY", "SPY": "EQUITY", "QQQ": "EQUITY", "IWM": "EQUITY", "SMH": "EQUITY", "UVXY": "EQUITY", "AAPL": "EQUITY", "USDBRL": "FX"}
TF_SYMS = [b + "USDT" for b in TRADFI]
ALL_SYMS = COINS + TF_SYMS
# drift per hour: BTC steady up, ETH stronger (phase-2-like), large caps mixed, memes hot, generics spread out
def drift_of(base):
    if base == "BTC": return 0.00010
    if base == "ETH": return 0.00016
    if base == "SOL": return 0.00012
    if base in ("DOGE","WIF","1000PEPE","BONK","POPCAT","BRETT"): return 0.00022
    if base in NAMED[:20]: return [0.00018,0.00004,-0.00006,0.00012,0.0002,0.00002,-0.0001,0.00015,0.00008,0.00011,
                                    0.00001,0.00009,-0.00003,0.00013,0.00005,0.00007,0.00016,0.0002,0.00021,0.00019][NAMED.index(base)]
    h = int(hashlib.md5(base.encode()).hexdigest(), 16)
    return ((h % 400) - 180) / 1_000_000
def vol_of(base):
    if base == "BTC": return 2.5e9 / 24
    if base == "ETH": return 1.2e9 / 24
    if base in MAJ or base in NAMED[:30]: return (3e8 - NAMED.index(base) * 6e6 if base in NAMED else 5e8) / 24
    h = int(hashlib.md5(base.encode()).hexdigest(), 16)
    return (4e6 + (h % 120) * 1.1e6) / 24
_cache = {}
def special(base):
    rnd = random.Random(int(hashlib.md5(base.encode()).hexdigest(), 16) % (2**32)); rows = []; p = 0.04 if base == "LONGXIA" else 2.0
    for i in range(NH + 1):
        t = NOW - (NH - i) * H; o = p; left = NH - i
        if base == "LONGXIA":                       # weeks of flat chop, then a volume breakout in the last 4 hours
            p = 0.04 * (1 + 0.012 * math.sin(i * 0.9) + rnd.gauss(0, 0.004)) if left > 4 else p * (1.025 + rnd.gauss(0, 0.002))
            qv = 1.4e6 if left > 4 else 6e6
        elif base == "COOLX":                       # steady climb that pushed RSI over 70, then a gentle cool-off over the last 10 hours
            p = p * (1.0018 + rnd.gauss(0, 0.003)) if left > 10 else p * (0.9994 + rnd.gauss(0, 0.0008)); qv = 2e6
        else:                                       # RUNX: a strong, steady run
            p = p * (1.003 + rnd.gauss(0, 0.002)); qv = 3e6
        hi, lo = max(o, p) * (1 + abs(rnd.gauss(0, 0.003))), min(o, p) * (1 - abs(rnd.gauss(0, 0.003)))
        rows.append([t, o, hi, lo, p, qv])
    return rows
def hourly(base):
    if base in _cache: return _cache[base]
    if base in SPECIAL: _cache[base] = special(base); return _cache[base]
    rnd = random.Random(int(hashlib.md5(base.encode()).hexdigest(), 16) % (2**32))
    p = {"BTC": 60000, "ETH": 3000, "SOL": 150, "XAU": 4100, "XAG": 60, "XPT": 1700, "SPY": 780, "QQQ": 760, "CL": 90, "BZ": 94, "NATGAS": 3.1}.get(base, 0.5 + rnd.random() * 50)
    d, sig, vb = drift_of(base), 0.004 if base == "BTC" else 0.007 + rnd.random() * 0.006, vol_of(base)
    rows = []
    for i in range(NH + 1):
        t = NOW - (NH - i) * H
        o = p; regime = math.sin(i / 300 + rnd.random() * 0.01) * 0.0004
        p = max(1e-6, p * math.exp(d + regime + rnd.gauss(0, sig)))
        hi, lo = max(o, p) * (1 + abs(rnd.gauss(0, sig / 2))), min(o, p) * (1 - abs(rnd.gauss(0, sig / 2)))
        qv = vb * (0.6 + rnd.random() * 0.8) * (3 if rnd.random() < 0.02 else 1)
        rows.append([t, o, hi, lo, p, qv])
    _cache[base] = rows; return rows
STEP = {"1m": H // 60, "3m": H // 20, "5m": H // 12, "15m": H // 4, "30m": H // 2, "1h": H, "2h": 2 * H, "4h": 4 * H, "1d": 24 * H, "1w": 168 * H}
def candles(base, interval):
    hr = hourly(base)
    if interval == "1h": return hr
    if STEP[interval] < H:
        out, n = [], H // STEP[interval]
        for t, o, h, l, c, qv in hr[-(1200 if n <= 4 else 160 if n <= 12 else 40):]:
            pts = [o + (c - o) * k / n for k in range(n + 1)]
            for k in range(n):
                a, b = pts[k], pts[k + 1]
                out.append([t + k * STEP[interval], a, max(a, b) + (h - max(o, c)) * 0.5, min(a, b) - (min(o, c) - l) * 0.5, b, qv / n])
        return out
    step, out, cur = STEP[interval], [], None
    for t, o, h, l, c, qv in hr:
        bt = t - (t % step)
        if not cur or cur[0] != bt:
            if cur: out.append(cur)
            cur = [bt, o, h, l, c, qv]
        else: cur[2] = max(cur[2], h); cur[3] = min(cur[3], l); cur[4] = c; cur[5] += qv
    out.append(cur); return out
def kline_rows(base, interval, limit, start=None, end=None):
    cs = candles(base, interval)
    if start is not None: cs = [x for x in cs if x[0] >= start]
    if end is not None: cs = [x for x in cs if x[0] <= end]
    cs = cs[:limit] if start is not None else cs[-limit:]
    st = STEP[interval]
    return [[t, f"{o:.8g}", f"{h:.8g}", f"{l:.8g}", f"{c:.8g}", f"{qv / max(c, 1e-9):.4f}", t + st - 1, f"{qv:.2f}", 100, "0", f"{qv * 0.52:.2f}", "0"] for t, o, h, l, c, qv in cs]
def ticker(base):
    hr = hourly(base); last, prev = hr[-1][4], hr[-25][4]
    return last, (last / prev - 1) * 100, sum(x[5] for x in hr[-24:])
def binance(url):
    u = urlparse(url); q = {k: v[0] for k, v in parse_qs(u.query).items()}; p = u.path
    if p.endswith("/ping") or p.endswith("/time"): return {}
    if p.endswith("/exchangeInfo"): return {"symbols": [{"symbol": s, "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": s[:-4]} for s in COINS] +
        [{"symbol": b + "USDT", "contractType": "TRADIFI_PERPETUAL", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": b, "underlyingType": t, "underlyingSubType": ["TradFi"]} for b, t in TRADFI.items()]}
    if p.endswith("/ticker/24hr"):
        out = []
        for s in ([q["symbol"]] if "symbol" in q else ALL_SYMS):
            last, chg, qv = ticker(s[:-4]); out.append({"symbol": s, "lastPrice": str(last), "priceChangePercent": f"{chg:.3f}", "quoteVolume": str(qv), "count": 1000})
        return out[0] if "symbol" in q else out
    if p.endswith("/ticker/price"): return [{"symbol": s, "price": str(ticker(s[:-4])[0])} for s in ALL_SYMS]
    if p.endswith("/premiumIndex"): return [{"symbol": s, "lastFundingRate": "0.0007" if s == "ZROUSDT" else "0.0001"} for s in ALL_SYMS]
    if p.endswith("/klines"):
        base = q["symbol"][:-4]
        if q["symbol"] not in ALL_SYMS: return []
        return kline_rows(base, q["interval"], int(q.get("limit", 500)), int(q["startTime"]) if "startTime" in q else None, int(q["endTime"]) if "endTime" in q else None)
    if "openInterestHist" in p: return [{"sumOpenInterestValue": str(1e7 * (1 + 0.01 * i))} for i in range(25)]
    if "LongShort" in p and "taker" not in p: return [{"longShortRatio": "1.4"}]
    if "takerlongshort" in p: return [{"buyVol": "120", "sellVol": "100"}]
    if p.endswith("/fundingRate"): return [{"fundingRate": "0.0001"} for _ in range(21)]
    return {}
CAP_ORDER = ["BTC","ETH","USDT","XRP","BNB","SOL","USDC","DOGE","ADA","TRX","STETH","WBTC","LINK","AVAX","SUI","TON","XLM","HBAR","BCH","LTC",
             "DOT","HYPE","UNI","NEAR","APT","ICP","ETC","AAVE","TAO","RENDER","FET","ARB","OP","INJ","ATOM","FIL","STX","IMX","SEI","TIA",
             "ONDO","ENA","WLD","JUP","LDO","PEPE","BONK","WIF","GALA","SAND","PENDLE","RUNE","PYTH","MANA","AXS","CRV","ZEC","DYDX","STRK","ZRO",
             "JTO","GMX","ORDI","EIGEN","VIRTUAL","KAITO","POPCAT","BRETT"]
def coingecko(url):
    p = urlparse(url).path
    if p.endswith("/global"): return {"data": {"total_market_cap": {"usd": 2.89e12}, "market_cap_change_percentage_24h_usd": 1.45, "market_cap_percentage": {"btc": 57.8, "eth": 11.3}}}
    if p.endswith("/coins/markets"): return [{"symbol": s.lower(), "market_cap_rank": i + 1, "market_cap": 2e12 / (i + 1) ** 1.3} for i, s in enumerate(CAP_ORDER)]
    return {}
def fng(url): return {"data": [{"value": "68", "value_classification": "Greed"}, {"value": "61", "value_classification": "Greed"}]}
async def route_all(route):
    url = route.request.url
    if "binance" in url: body = binance(url)
    elif "coingecko" in url: body = coingecko(url)
    elif "alternative.me" in url: body = fng(url)
    else: return await route.abort()
    await route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"access-control-allow-origin": "*"})
async def setup(ctx):
    for pat in ["**/*binance*/**", "**/api.coingecko.com/**", "**/api.alternative.me/**"]: await ctx.route(pat, route_all)
    await ctx.route("**/s3-symbol-logo.tradingview.com/**", lambda r: r.abort())
# static server with the app's production headers (from vercel.json)
APP = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
def serve(port=8765):
    cfg = json.load(open(APP + "/vercel.json"))
    class Hd(http.server.SimpleHTTPRequestHandler):
        def __init__(s, *a, **k): super().__init__(*a, directory=APP, **k)
        def end_headers(s):
            for rule in cfg["headers"]:
                if re.match("^" + rule["source"].replace("(.*)", ".*") + "$", s.path.split("?")[0]):
                    for h in rule["headers"]: s.send_header(h["key"], h["value"])
            super().end_headers()
        def guess_type(s, p): return "application/manifest+json" if p.endswith(".webmanifest") else super().guess_type(p)
        def log_message(s, *a): pass
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("localhost", port), Hd); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv
async def ready(pg, secs=150):
    for _ in range(secs * 2):
        if await pg.evaluate("() => !document.getElementById('runBtn').disabled && document.getElementById('copyBtn').disabled === false"): return True
        await __import__("asyncio").sleep(0.5)
    return False

# ---------------- mock cTrader Open API (JSON over WebSocket) ----------------
CT_FX = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD","EURGBP","EURJPY","EURCHF","EURCAD","EURAUD","EURNZD","GBPJPY",
         "GBPCHF","GBPCAD","GBPAUD","GBPNZD","AUDJPY","AUDCHF","AUDCAD","AUDNZD","NZDJPY","NZDCHF","NZDCAD","CADJPY","CADCHF","CHFJPY"]
CT_LIST = CT_FX + ["XAUUSD", "XAGUSD", "US500", "NAS100", "US30", "SpotCrude", "GER40", "AAPL.US", "XPTUSD", "SpotBrent", "NatGas", "JPN225", "HK50", "UK100"]
CT_IV = {1: "1m", 3: "3m", 5: "5m", 7: "15m", 8: "30m", 9: "1h", 10: "4h", 12: "1d", 13: "1w"}
CT_LOG = []
CT_ASSET = {"USD": 1, "EUR": 2, "JPY": 3, "XAU": 4, "GBP": 5}
def CT_BASE(n): return CT_ASSET.get(n[:3], 9) if len(n) == 6 and n.isupper() else 9
def CT_QUOTE(n): return CT_ASSET.get(n[3:6], 9) if len(n) == 6 and n.isupper() else (2 if n in ("GER40",) else 3 if n == "JPN225" else 5 if n == "UK100" else 1)
CT_TRADE = {"pos": [], "ord": [], "log": [], "deals": []}
def ct_handler(opts):
    """opts: {'secret': 'sec', 'token': 'tok', 'live': True} — what the fake server accepts."""
    def handler(ws):
        def on(msg):
            m = json.loads(msg); t = m.get("payloadType"); p = m.get("payload") or {}; cid = m.get("clientMsgId")
            if opts.get("names"):
                num = lambda v: int(v) if isinstance(v, str) and v.isdigit() else [num(x) for x in v] if isinstance(v, list) else v
                p = {k: (num(v) if k in ("symbolId", "positionId", "orderId", "volume") else v) for k, v in p.items()}
            CT_LOG.append(t)
            def reply(pt, pl): ws.send(json.dumps({"clientMsgId": cid, "payloadType": pt, "payload": names(pl) if opts.get("names") else pl}))
            if t == 51: return
            if t == 2100:
                return reply(2101, {}) if p.get("clientSecret") == opts["secret"] else reply(2142, {"errorCode": "CH_CLIENT_AUTH_FAILURE", "description": "Client authentication failure"})
            if t == 2149:
                if p.get("accessToken") not in (opts["token"], "tok-renewed"): return reply(2142, {"errorCode": "CH_ACCESS_TOKEN_INVALID", "description": "Invalid access token"})
                accts = [{"ctidTraderAccountId": 4242, "isLive": opts["live"], "traderLogin": 5150123, "brokerTitleShort": "Pepperstone"}]
                if opts.get("demo2"): accts.append({"ctidTraderAccountId": 777, "isLive": False, "traderLogin": 900777, "brokerTitleShort": "Demo Broker"})
                return reply(2150, {"accessToken": p["accessToken"], "permissionScope": opts.get("scope", "SCOPE_VIEW"), "ctidTraderAccount": accts})
            if t == 2102: return reply(2103, {"ctidTraderAccountId": p["ctidTraderAccountId"]})
            if t == 2114: return reply(2115, {"ctidTraderAccountId": p["ctidTraderAccountId"], "symbol": [{"symbolId": i + 1, "symbolName": n, "enabled": True, "baseAssetId": CT_BASE(n), "quoteAssetId": CT_QUOTE(n)} for i, n in enumerate(CT_LIST)]})
            if t == 2137:
                name = CT_LIST[p["symbolId"] - 1]; iv = CT_IV[p["period"]]
                rows = candles(name, iv); rows = [x for x in rows if p["fromTimestamp"] <= x[0] <= p["toTimestamp"]][-p.get("count", 500):]
                bars = []
                for tt, o, h, l, c, qv in rows:
                    lo = round(l * 1e5); bars.append({"volume": int(qv / 1000), "period": p["period"], "low": lo, "deltaOpen": round(o * 1e5) - lo,
                                                     "deltaClose": round(c * 1e5) - lo, "deltaHigh": round(h * 1e5) - lo, "utcTimestampInMinutes": tt // 60000})
                return reply(2138, {"ctidTraderAccountId": p["ctidTraderAccountId"], "period": p["period"], "trendbar": bars})
            if t == 2173 and p.get("refreshToken") not in (opts.get("refresh", "ref"), "ref-renewed"): return reply(2142, {"errorCode": "CH_ACCESS_TOKEN_INVALID", "description": "Invalid refresh token"})
            if t == 2173: return reply(2174, {"accessToken": "tok-renewed", "refreshToken": "ref-renewed", "expiresIn": 2628000, "tokenType": "bearer"})
            if t == 2104: return reply(2105, {"version": "mock"})
            if t == 2121: return reply(2122, {"ctidTraderAccountId": 4242, "trader": {"ctidTraderAccountId": 4242, "balance": 1852034, "moneyDigits": 2, "depositAssetId": 1, "leverageInCents": 50000}})
            if t == 2112: return reply(2113, {"ctidTraderAccountId": 4242, "asset": [{"assetId": 1, "name": "USD"}, {"assetId": 2, "name": "EUR"}, {"assetId": 3, "name": "JPY"}, {"assetId": 4, "name": "XAU"}, {"assetId": 5, "name": "GBP"}]})
            if t == 2116:
                out = []
                for sid in p.get("symbolId", []):
                    n = CT_LIST[sid - 1]
                    out.append({"symbolId": sid, "digits": 2 if n.startswith("XAU") or not n.isupper() or n in ("US500","NAS100","US30","GER40","JPN225","HK50","UK100") else 5,
                                "lotSize": 10000 if n == "XAUUSD" else 100 if n in ("US500","NAS100","US30","GER40","JPN225","HK50","UK100") else 10000000, "stepVolume": 100 if n in ("US500","NAS100","US30") else 1000, "minVolume": 100 if n in ("US500","NAS100","US30") else 1000})
                return reply(2117, {"ctidTraderAccountId": 4242, "symbol": out})
            if t == 2127:
                reply(2128, {})
                for sid in (p.get("symbolId") or [1])[:40]:
                    last = candles(CT_LIST[sid - 1], "1h")[-1][4]
                    ws.send(json.dumps({"payloadType": 2131, "payload": {"ctidTraderAccountId": 4242, "symbolId": sid, "bid": round(last * 1.01 * 1e5), "ask": round(last * 1.0101 * 1e5)}}))
                return
            # ---- trading (Trade page) ----
            if t in (2106, 2124, 2187, 2111, 2110, 2108, 2109, 2133): CT_TRADE["log"].append((t, dict(p)))
            if t == 2106:
                sid = p["symbolId"]; px = candles(CT_LIST[sid - 1], "1h")[-1][4]
                if p.get("orderType") == 1:
                    pid = 9000 + len(CT_TRADE["pos"]); pos = {"positionId": pid, "tradeData": {"symbolId": sid, "volume": p["volume"], "tradeSide": p["tradeSide"]}, "price": px, "positionStatus": 1}
                    CT_TRADE["pos"].append(pos); return reply(2126, {"executionType": 3, "position": pos, "deal": {"executionPrice": px}})
                oid = 5000 + len(CT_TRADE["ord"]); o = {"orderId": oid, "tradeData": {"symbolId": sid, "volume": p["volume"], "tradeSide": p["tradeSide"]}, "orderType": p["orderType"], "limitPrice": p.get("limitPrice"), "stopPrice": p.get("stopPrice"), "stopLoss": p.get("stopLoss"), "takeProfit": p.get("takeProfit")}
                CT_TRADE["ord"].append(o); return reply(2126, {"executionType": 2, "order": o})
            if t == 2124: return reply(2125, {"ctidTraderAccountId": p["ctidTraderAccountId"], "position": CT_TRADE["pos"], "order": CT_TRADE["ord"]})
            if t == 2187: return reply(2188, {"ctidTraderAccountId": p["ctidTraderAccountId"], "moneyDigits": 2, "positionUnrealizedPnL": [{"positionId": x["positionId"], "grossUnrealizedPnL": 1234, "netUnrealizedPnL": 1200} for x in CT_TRADE["pos"]]})
            if t == 2111:
                for x in CT_TRADE["pos"]:
                    if x["positionId"] == p["positionId"]:
                        sid = x["tradeData"]["symbolId"]; px = candles(CT_LIST[sid - 1], "1h")[-1][4]; now = int(time.time() * 1000); side = x["tradeData"]["tradeSide"]
                        CT_TRADE["deals"].append({"dealId": 700 + len(CT_TRADE["deals"]), "positionId": x["positionId"], "symbolId": sid, "volume": x["tradeData"]["volume"], "tradeSide": side, "executionPrice": x["price"], "executionTimestamp": now - 3600e3})
                        CT_TRADE["deals"].append({"dealId": 700 + len(CT_TRADE["deals"]), "positionId": x["positionId"], "symbolId": sid, "volume": x["tradeData"]["volume"], "tradeSide": 3 - side, "executionPrice": px * 1.002, "executionTimestamp": now,
                                                  "closePositionDetail": {"entryPrice": x["price"], "grossProfit": 4520, "swap": -30, "commission": -150, "balance": 1852034, "closedVolume": x["tradeData"]["volume"], "moneyDigits": 2}})
                CT_TRADE["pos"] = [x for x in CT_TRADE["pos"] if x["positionId"] != p["positionId"]]; return reply(2126, {"executionType": 3, "deal": {"executionPrice": 1}})
            if t == 2109:
                for x in CT_TRADE["ord"]:
                    if x["orderId"] == p["orderId"]:
                        for k in ("limitPrice", "stopPrice", "stopLoss", "takeProfit", "volume"):
                            if k in p: (x["tradeData"] if k == "volume" else x)[k] = p[k]
                return reply(2126, {"executionType": 4})
            if t == 2133: return reply(2134, {"ctidTraderAccountId": p["ctidTraderAccountId"], "deal": [d for d in CT_TRADE["deals"] if p["fromTimestamp"] <= d["executionTimestamp"] <= p["toTimestamp"]], "hasMore": False})
            if t == 2110:
                for x in CT_TRADE["pos"]:
                    if x["positionId"] == p["positionId"]: x["stopLoss"] = p.get("stopLoss"); x["takeProfit"] = p.get("takeProfit")
                return reply(2126, {"executionType": 4})
            if t == 2108:
                CT_TRADE["ord"] = [x for x in CT_TRADE["ord"] if x["orderId"] != p["orderId"]]; return reply(2126, {"executionType": 5})
            reply(2142, {"errorCode": "UNSUPPORTED", "description": f"mock has no {t}"})
        ws.on_message(on)
    return handler

EN = {"tradeSide": {1: "BUY", 2: "SELL"}, "orderType": {1: "MARKET", 2: "LIMIT", 3: "STOP", 4: "STOP_LOSS_TAKE_PROFIT", 6: "STOP_LIMIT"},
      "executionType": {2: "ORDER_ACCEPTED", 3: "ORDER_FILLED", 4: "ORDER_REPLACED", 5: "ORDER_CANCELLED", 7: "ORDER_REJECTED"}}
def names(o):                           # like the real JSON feed: enums by name, ids and volumes as strings
    if isinstance(o, list): return [names(v) for v in o]
    if not isinstance(o, dict): return o
    out = {}
    for k, v in o.items():
        if k in EN and v in EN[k]: out[k] = EN[k][v]
        elif k in ("symbolId", "positionId", "orderId", "volume") and isinstance(v, int) and not isinstance(v, bool): out[k] = str(v)
        else: out[k] = names(v)
    return out
# ---------------- mock MEXC (futures contract API + spot v3 + futures WebSocket) ----------------
MX_SPOT_SKIP = {"C001USDT", "C002USDT", "HYPEUSDT"}     # a few coins MEXC lists as futures only
MX_LOG = []
MXF_STEP = {"Min1": "1m", "Min5": "5m", "Min15": "15m", "Min30": "30m", "Min60": "1h", "Hour4": "4h", "Day1": "1d", "Week1": "1w"}
MXS_STEP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "1h", "4h": "4h", "1d": "1d", "1W": "1w"}
def mx_ok(d): return {"success": True, "code": 0, "data": d}
# MEXC's own TradFi perps (type 2 / "tradfi" plate) — the crypto scan must skip these
MX_TF = {"XAU_USDT": ("Commodities", 1), "SILVER_USDT": ("Commodities", 1), "COPPER_USDT": ("Commodities", 1), "USOIL_USDT": ("OIL", 2), "UKOIL_USDT": ("OIL", 2),
         "NAS100_USDT": ("stockindex", 2), "SPX500_USDT": ("stockindex", 2), "US30_USDT": ("stockindex", 2), "JP225_USDT": ("stockindex", 2),
         "EUR_USDT": ("Forex", 1), "GBP_USDT": ("Forex", 1), "JPY_USDT": ("Forex", 1), "AUD_USDT": ("Forex", 1),
         "AAPLSTOCK_USDT": ("Stock", 2), "NVIDIA_USDT": ("Stock", 2), "TESLA_USDT": ("Stock", 2), "SPY_USDT": ("Stock", 2)}
MX_TF_NAME = {"AAPLSTOCK_USDT": "AAPL_USDT", "NVIDIA_USDT": "NVDA_USDT", "TESLA_USDT": "TSLA_USDT"}
MX_RL = {"tokens": 6.0, "at": time.time(), "hits": 0, "served": 0, "on": True}
MX_WIN = {"start": 0.0, "n": 0}
def mx_limited():                       # like MEXC's contract API (measured): 20 requests per 2-second window
    now = time.time()
    if not MX_RL["on"]: return False
    if now - MX_WIN["start"] >= 2.0: MX_WIN["start"] = now; MX_WIN["n"] = 0
    if MX_WIN["n"] >= 20: MX_RL["hits"] += 1; return True
    MX_WIN["n"] += 1; MX_RL["served"] += 1; return False
def mx_px(base):
    if base == "JPY": return 0.0064
    if base == "EUR": return 1.12
    return None
def mexc(url):
    u = urlparse(url); q = {k: v[0] for k, v in parse_qs(u.query).items()}; p = u.path; MX_LOG.append(p)
    if "contract.mexc.com" in u.netloc or "/proxy/mexc-fut" in p:
        if p.endswith("/contract/ping"): return mx_ok(int(time.time() * 1000))
        if mx_limited(): return {"success": False, "code": 510, "message": "Requests are too frequent, please try again later"}
        if p.endswith("/contract/detail"):
            return mx_ok([{"symbol": s[:-4] + "_USDT", "baseCoin": s[:-4], "quoteCoin": "USDT", "settleCoin": "USDT", "state": 0, "futureType": 1, "contractSize": 0.01} for s in COINS] +
                         [{"symbol": "OLD_USDT", "baseCoin": "OLD", "quoteCoin": "USDT", "settleCoin": "USDT", "state": 4, "futureType": 1}] +
                         [{"symbol": k, "baseCoin": k.split("_")[0], "quoteCoin": "USDT", "settleCoin": "USDT", "state": 0, "futureType": 1, "type": t,
                           "conceptPlate": ["mc-trade-zone-tradfi", "mc-trade-zone-" + pl], "displayNameEn": MX_TF_NAME.get(k, k) + " PERPETUAL"} for k, (pl, t) in MX_TF.items()])
        if p.endswith("/contract/ticker"):
            syms = [q["symbol"]] if "symbol" in q else [s[:-4] + "_USDT" for s in COINS] + list(MX_TF)
            out = []
            for s in syms:
                last, chg, qv = ticker(s.split("_")[0])
                out.append({"symbol": s, "lastPrice": last, "riseFallRate": round(chg / 100, 5), "amount24": qv, "fundingRate": 0.0007 if s == "ZRO_USDT" else 0.0001, "holdVol": 1000000})
            return mx_ok(out[0] if "symbol" in q else out)
        if "/contract/kline/" in p:
            base = p.rsplit("/", 1)[1].split("_")[0]; iv = MXF_STEP[q["interval"]]
            st, en = int(q["start"]) * 1000, int(q["end"]) * 1000
            cs = [x for x in candles(base, iv) if st <= x[0] <= en][:2000]
            return mx_ok({"time": [x[0] // 1000 for x in cs], "open": [x[1] for x in cs], "high": [x[2] for x in cs], "low": [x[3] for x in cs],
                          "close": [x[4] for x in cs], "vol": [x[5] / max(x[4], 1e-9) for x in cs], "amount": [x[5] for x in cs]})
        if p.endswith("/funding_rate/history"): return mx_ok({"pageSize": 21, "totalCount": 21, "resultList": [{"symbol": q.get("symbol"), "fundingRate": 0.0001} for _ in range(21)]})
        return {"success": False, "code": 404, "message": "mock: no " + p}
    # spot v3 (Binance-style)
    spot = [s for s in COINS if s not in MX_SPOT_SKIP]
    if p.endswith("/ping"): return {}
    if p.endswith("/ticker/24hr"):
        def one(s):
            last, chg, qv = ticker(s[:-4]); op = last / (1 + chg / 100)
            return {"symbol": s, "lastPrice": str(last), "openPrice": str(op), "priceChangePercent": f"{chg / 100:.5f}", "quoteVolume": str(qv)}
        return one(q["symbol"]) if "symbol" in q else [one(s) for s in spot]
    if p.endswith("/ticker/price"): return [{"symbol": s, "price": str(ticker(s[:-4])[0])} for s in spot]
    if p.endswith("/klines"):
        if q["symbol"] not in spot: return []
        rows = kline_rows(q["symbol"][:-4], MXS_STEP[q["interval"]], min(1000, int(q.get("limit", 500))), int(q["startTime"]) if "startTime" in q else None, int(q["endTime"]) if "endTime" in q else None)
        return [r[:8] for r in rows]
    return {}
async def route_mexc(route):
    await route.fulfill(status=200, content_type="application/json", body=json.dumps(mexc(route.request.url)), headers={"access-control-allow-origin": "*"})
async def setup_mexc(ctx):
    for pat in ["**/contract.mexc.com/**", "**/api.mexc.com/**", "**/proxy/mexc-*/**"]: await ctx.route(pat, route_mexc)
MXWS_LOG = []
def mx_ws_handler(ws):
    """Fake wss://contract.mexc.com/edge: acks subscriptions, then pushes one ticker batch and two BTC kline updates (second one opens a new candle)."""
    def on(msg):
        m = json.loads(msg); MXWS_LOG.append(m); meth = m.get("method")
        if meth == "ping": return ws.send(json.dumps({"channel": "pong", "data": int(time.time() * 1000)}))
        if meth == "sub.tickers":
            ws.send(json.dumps({"channel": "rs.sub.tickers", "data": "success"}))
            ws.send(json.dumps({"channel": "push.tickers", "data": [{"symbol": "BTC_USDT", "lastPrice": 77777.7, "riseFallRate": 0.0321, "amount24": 9.9e9, "fundingRate": 0.0002}, {"symbol": "XRP_USDT", "lastPrice": 1.2345, "riseFallRate": 0.0432, "amount24": 5.5e9, "fundingRate": 0.0003}, {"symbol": "XAU_USDT", "lastPrice": 4321.5, "riseFallRate": 0.01, "amount24": 3e8}]}))
        if meth == "sub.kline" and m.get("param", {}).get("symbol") == "BTC_USDT":
            iv = m["param"]["interval"]; step = STEP[MXF_STEP[iv]] // 1000; t0 = (int(time.time()) // step) * step
            ws.send(json.dumps({"channel": "push.kline", "symbol": "BTC_USDT", "data": {"symbol": "BTC_USDT", "interval": iv, "t": t0, "o": 77000, "h": 77900, "l": 76900, "c": 77777.7}}))
            ws.send(json.dumps({"channel": "push.kline", "symbol": "BTC_USDT", "data": {"symbol": "BTC_USDT", "interval": iv, "t": t0 + step, "o": 77777.7, "h": 77800, "l": 77700, "c": 77750}}))
    ws.on_message(on)

# ---------------- calendar feeds, Telegram, keep-awake ----------------
def ff_sample():
    import datetime as dt
    now = time.time(); base = int(now // 3600) * 3600
    def iso(ts): return dt.datetime.fromtimestamp(ts, dt.timezone(dt.timedelta(hours=-4))).isoformat()
    ev = [("Core CPI m/m", "USD", "High", 600, "0.2%", "0.3%"), ("CPI y/y", "USD", "High", 600, "3.6%", "3.4%"), ("Unemployment Claims", "USD", "Medium", 2 * 86400, "230K", "226K"),
          ("Fed Chair Powell Speaks", "USD", "High", 3 * 3600, "", ""), ("FOMC Statement", "USD", "High", 86400 + 7200, "", ""), ("10-y Bond Auction", "USD", "Low", 5 * 3600, "", "4.11|2.5"),
          ("ECB Main Refinancing Rate", "EUR", "High", 30 * 3600, "2.15%", "2.15%"), ("German ZEW Economic Sentiment", "EUR", "Medium", -5 * 3600, "39.5", "37.3"),
          ("BOJ Gov Ueda Speaks", "JPY", "Medium", 20 * 3600, "", ""), ("Bank Holiday", "USD", "Holiday", -3 * 3600, "", ""), ("Employment Change", "AUD", "High", 44 * 3600, "20.0K", "39.5K"),
          ("Retail Sales m/m", "USD", "High", 3 * 86400, "0.4%", "0.6%"), ("Pending Home Sales m/m", "USD", "Medium", 4 * 86400, "0.1%", "-0.4%")]
    return [{"title": t, "country": c, "date": iso((int(now // 60) * 60 + 600 if t == "Core CPI m/m" else base + off)), "impact": imp, "forecast": f, "previous": pv} for t, c, imp, off, f, pv in ev]
EARN_ROWS = {"NFLX": ("Netflix, Inc.", "time-after-hours", 520e9, "$6.88"), "TSLA": ("Tesla, Inc.", "time-after-hours", 1.3e12, "$0.55"), "JPM": ("JPMorgan Chase & Co.", "time-pre-market", 820e9, "$5.10"),
             "ASML": ("ASML Holding N.V.", "time-pre-market", 682e9, "$12.47"), "PEP": ("PepsiCo, Inc.", "time-pre-market", 205e9, "$2.30"), "XYZ": ("Small Co", "time-not-supplied", 12e9, "$0.10")}
TG_LOG = []; AWAKE_LOG = []; FF_HITS = {"n": 0}; EARN_HITS = []
async def route_extra(route):
    u = route.request.url; p = urlparse(u)
    if p.path == "/proxy/ff":
        FF_HITS["n"] += 1; return await route.fulfill(status=200, content_type="application/json", body=json.dumps(ff_sample()))
    if p.path == "/proxy/earnings":
        d = parse_qs(p.query).get("date", [""])[0]; EARN_HITS.append(d)
        import datetime as dt
        wd = dt.date.fromisoformat(d).weekday(); keys = list(EARN_ROWS)
        rows = [{"symbol": k, "name": EARN_ROWS[k][0], "time": EARN_ROWS[k][1], "marketCap": "${:,.0f}".format(EARN_ROWS[k][2]), "epsForecast": EARN_ROWS[k][3], "noOfEsts": "5"} for k in keys if hash(k + d) % 3 == 0 or (k == "TSLA" and wd == 2)]
        return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": {"asOf": d, "rows": rows}}))
    if p.path == "/api/awake":
        AWAKE_LOG.append(p.query); return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"awakeUntil": int(time.time() * 1000) + 1200000, "running": True}))
    if "api.telegram.org" in u:
        if u.endswith("/getUpdates"): return await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps({"ok": True, "result": [{"update_id": 1, "message": {"message_id": 1, "chat": {"id": 987654321, "first_name": "Jas", "type": "private"}, "text": "hi"}}]}))
        if u.endswith("/sendMessage"):
            if route.request.method == "OPTIONS": return await route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "POST"})
            TG_LOG.append(json.loads(route.request.post_data or "{}")); return await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps({"ok": True, "result": {"message_id": len(TG_LOG)}}))
    return await route.fulfill(status=404, body="")
async def setup_extra(ctx):
    for pat in ["**/proxy/ff*", "**/proxy/earnings*", "**/api/awake*", "**/api.telegram.org/**"]: await ctx.route(pat, route_extra)
