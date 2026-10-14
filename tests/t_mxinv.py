import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def waitfor(pg, js, secs=300):
    for _ in range(secs * 2):
        if await pg.evaluate(js): return True
        await asyncio.sleep(0.5)
    return False
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macro'); }")
        print("loaded", await waitfor(pg, "() => !MACRO.running && MACRO.rows.some(r => r.mx)"))
        print("candles:", await q("""async () => { const now = Date.now(); const raw = await mxGet('/api/v1/contract/kline/JPY_USDT', { interval: 'Min60', start: Math.floor((now - 5*3600e3)/1000), end: Math.floor(now/1000) });
          const k = await mxKlinesF('MX:JPY_USDT', '1h', now - 5*3600e3, now); const i = k.length - 1, j = raw.time.length - 1;
          return { raw: [raw.open[j], raw.high[j], raw.low[j], raw.close[j]], app: k[i].slice(1, 5).map(x => +x.toFixed(4)), check: Math.abs(k[i][2] * raw.low[j] - 1) < 1e-9 && Math.abs(k[i][3] * raw.high[j] - 1) < 1e-9 && k[i][2] >= k[i][3] }; }"""))
        print("eur not flipped:", await q("async () => { const now = Date.now(); const k = await mxKlinesF('MX:EUR_USDT', '1h', now - 3*3600e3, now); return k.at(-1)[4]; }"))
        print("ticker:", await q("async () => { const t = (await mxTickers(0))['JPY_USDT']; return [t.lastPrice, t.rawLast, t.fundingRate, t.riseFallRate, t.high24Price >= t.lower24Price]; }"))
        print("row:", await q("() => { const r = MACRO.by['MX:JPY_USDT']; return [r.name, r.pair, coin(r.symbol), fmtPrice(r.price), r.chg24h.toFixed(2), r.momo && r.momo.dir, r.tv]; }"))
        print("row html:", await q("() => document.querySelector('[data-s=\"MX:JPY_USDT\"]').innerText.replace(/\\s+/g,' ').slice(0, 140)"))
        print("note:", await q("() => (document.querySelector('.mxfxnote') || {}).innerText"))
        print("ccy strength:", await q("() => document.getElementById('macroRead').innerText.replace(/\\s+/g,' ').slice(0, 200)"))
        print("live push:", await q("() => { const k0 = LIVE.kind; LIVE.kind = 'mexc'; liveMessage({ channel: 'push.tickers', data: [{ symbol: 'JPY_USDT', lastPrice: 0.0064 }] }); LIVE.kind = k0; return [MACRO.by['MX:JPY_USDT'].price, document.querySelector('[data-mp=\"MX:JPY_USDT\"]').textContent]; }"))
        print("live kline:", await q("() => { let got = null; const o = window.onLiveKline; window.onLiveKline = (s, iv, bar) => { if (s === 'MX:JPY_USDT') got = bar; }; const k0 = LIVE.kind; LIVE.kind = 'mexc'; liveMessage({ channel: 'push.kline', data: { symbol: 'JPY_USDT', interval: 'Min60', t: Math.floor(Date.now()/1000), o: 0.0064, h: 0.0065, l: 0.0063, c: 0.00645, a: 1 } }); window.onLiveKline = o; LIVE.kind = k0; return got && [got.o, got.h, got.l, got.c].map(x => +x.toFixed(3)); }"))
        await q("() => goPage('charts')"); await asyncio.sleep(2); await q("() => chSetSym('MX:JPY_USDT')"); await asyncio.sleep(4)
        print("chart:", await q("() => chName(CH.sym) + ' · ' + chSrc(CH.sym) + ' · ' + chVis().map(P => P.tf + ' last ' + (P.c ? P.c.at(-1) : P.t && P.k ? '' : '?')).join(' ')"))
        print("chart close:", await q("() => { const P = chVis()[0]; const k = P.k || P.data || P.rows; return k ? JSON.stringify(k.c ? k.c.at(-1) : k.at ? k.at(-1) : null) : Object.keys(P).join(','); }"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
