import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
# Charts: "Compare with another market" (overlay on its own scale) and "Ratio to another market" (pane), with typed market names.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and "s3-symbol-logo" not in m.text and "Failed to load resource" not in m.text and errs.append("console: " + m.text[:200]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=60):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        await q("() => macroScan(true)"); print("0) forex loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)", 200))
        print("1) in the picker:", await q("() => ['cmp', 'ratio'].map(k => IND[k].name + ' [' + IND[k].cat + ']').join(', ') + ' | category listed: ' + IND_CATS.some(c => c[0] === 'Comparison')"))
        print("2) typed names:", await q("() => ['DXY', 'Gold', 'gold', 'Silver', 'EUR/USD', 'eurusd', 'XAUUSD', 'NAS100', 'Nasdaq 100', 'BTCUSDT', 'nonsense'].map(t => t + '→' + chCmpSym(t)).join(', ')"))
        await q("() => goPage('charts')"); await wait("() => CHP.length && CHP.every(P => P.t.length > 0)", 30)
        await q("() => openInCharts('CT:XAUUSD')")
        print("   chart:", await wait("() => CHP[0].sym === 'CT:XAUUSD' && CHP[0].t.length > 100", 40), await q("() => CHP.map(P => P.sym + ' ' + P.tf).join(', ')"))
        await q("() => { CH.ind = CH.ind || []; const a = indNew('cmp'), r = indNew('ratio'); a.p = { ...a.p, sym: 'Silver' }; r.p = { ...r.p, sym: 'Silver' }; CH.ind.push(a, r); chIndChanged(); }")
        ok = await wait("() => { const P = CHP[0], a = CH.ind.find(I => I.type === 'cmp'), r = CH.ind.find(I => I.type === 'ratio'); return P.iv && P.iv[a.id] && P.iv[a.id].cmp && P.iv[r.id] && P.iv[r.id].r && P.iv[r.id].r.at(-1) != null; }", 30)
        print("3) filled in:", ok)
        print("4) values:", await q("""async () => { const P = CHP[0], a = CH.ind.find(I => I.type === 'cmp'), r = CH.ind.find(I => I.type === 'ratio'), k = await klines('CT:XAGUSD', P.tf, 500);
          const i = P.t.length - 2, t = P.t[i], j = k.t.indexOf(t), cm = P.iv[a.id].cmp[i], rt = P.iv[r.id].r[i];
          return 'bar ' + new Date(t).toISOString().slice(0, 16) + ': compare ' + (cm && cm.toFixed(3)) + ' vs silver close ' + (j >= 0 ? k.c[j].toFixed(3) : 'n/a') + ' · ratio ' + (rt && rt.toFixed(3)) + ' vs gold÷silver ' + (j >= 0 ? (P.c[i] / k.c[j]).toFixed(3) : 'n/a') + ' · average ' + (P.iv[r.id].m.at(-1) || 0).toFixed(3); }"""))
        print("5) own scale:", await q("() => { const P = CHP[0], a = CH.ind.find(I => I.type === 'cmp'), s = P.ix[a.id] && P.ix[a.id].ser.cmp; return s ? s.options().priceScaleId : 'no series'; }"),
              "| legends:", await q("() => document.querySelector('#chWrap0 .chind') ? document.querySelector('#chWrap0 .chind').innerText.replace(/\\s+/g, ' ').slice(0, 160) : 'none'"))
        print("6) carry forward:", await q("""() => { const H = 3600e3, P = { t: [0, 1, 2, 3, 4].map(i => i * H), tf: '1h' }; CHCMP_SYM['TESTX'] = { s: 'TESTX', at: Date.now() }; CHCMP['TESTX|1h'] = { t: [0, 2 * H], c: [10, 12], at: Date.now() };
          return JSON.stringify(chCmpLine(P, 'TESTX')) + ' (before the first: ' + JSON.stringify(chCmpLine({ t: [-H, 0], tf: '1h' }, 'TESTX')) + ')'; }"""))
        await q("() => { const a = CH.ind.find(I => I.type === 'cmp'); a.p.sym = 'nonsense'; chIndChanged(); }"); await asyncio.sleep(0.5)
        print("7) unknown market, no crash:", await q("() => { const P = CHP[0], a = CH.ind.find(I => I.type === 'cmp'); return JSON.stringify(Object.keys(P.iv[a.id] || {})); }"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
