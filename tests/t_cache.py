import asyncio, sys, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# The last scan shows straight away on reopen, and the rescan downloads only the candles that closed since (same results as a cold scan).
PICK = "() => JSON.stringify(data.all.map(r => [r.symbol, r.price, r.dayScore, r.swingScore, r.s1h.state, r.s4h.state, r.s1d.state, r.rvol, r.atrPct, (r.models || []).length]))"
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}); await setup(ctx)
        pg = await ctx.new_page(); errs, kl = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: "/klines" in r.url and kl.append(r.url))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/")
        print("cold scan ok:", await ready(pg), "| kline requests:", len(kl), "| cached flag:", await pg.evaluate("() => !!data.cached"))
        cold = await pg.evaluate(PICK); await asyncio.sleep(1)
        print("saved:", await pg.evaluate("async () => { const s = await scTx('scan', 'readonly', st => st.get(data.key)); const n = await scTx('kl', 'readonly', st => st.count()); return { scan: !!(s && s.all && s.all.length), candleSets: n }; }"))

        # a slow network on reopen, so the rescan is still running when we look
        await pg.add_init_script("(() => { const f = window.fetch; window.fetch = (u, ...a) => /\\/(klines\\?|fapi\\/v1\\/ping)/.test(String(u && u.url || u)) && !window.FAST ? new Promise(r => setTimeout(r, 3000)).then(() => f(u, ...a)) : f(u, ...a); })()")
        kl.clear(); await pg.reload(); await asyncio.sleep(1.2)
        early = await pg.evaluate("() => ({ cached: !!(data && data.cached), coins: data ? data.all.length : 0, rows: document.querySelectorAll('#tbody tr, .board tr, .card').length, status: document.getElementById('status').textContent.slice(0, 90), copy: document.getElementById('copyBtn').disabled })")
        print("1.2 s after reopen:", early)
        print("warm scan ok:", await ready(pg), "| kline requests:", len(kl), "| cached flag after:", await pg.evaluate("() => !!data.cached"), "| status:", await pg.evaluate("() => document.getElementById('status').textContent"))
        warm = await pg.evaluate(PICK)
        print("warm results match cold:", warm == cold, "| coins:", len(json.loads(warm)))
        await pg.evaluate("() => window.FAST = true")

        # an older cache: drop the newest 5 candles, then a read fetches just the gap and stitches it on
        kl.clear()
        r = await pg.evaluate("""async () => { const sym = data.all[3].symbol, k = `${EXCHANGE}|${MODE}|${sym}|1h`, c = SC.mem.get(k);
          ['t', 'o', 'h', 'l', 'c', 'qv'].forEach(f => c[f] = c[f].slice(0, -5));
          SC.on++; let got; try { got = await klines(sym, '1h', 400); } finally { SC.on--; }
          const net = await klinesNet(sym, '1h', 400);
          return { sym, same: JSON.stringify(got) === JSON.stringify(net), len: got.t.length, kept: SC.mem.get(k).t.length }; }""")
        print("gap fill:", r, "| requests:", [u.split("limit=")[-1] for u in kl])
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
