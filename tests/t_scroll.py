import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 950}, device_scale_factor=2, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=200):
            for _ in range(secs * 2):
                if await q(js): return True
                await asyncio.sleep(0.5)
            return False
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macro'); macroScan(true); }")
        print("loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)"))
        await q("() => { openDetail('CT:CADCHF'); }"); await asyncio.sleep(3)
        await q("() => { const s = document.querySelector('#dChartHost .chtf'); if (s) { s.value = '15m'; s.dispatchEvent(new Event('change')); } }"); await asyncio.sleep(3)
        print("pop-up:", await q("() => { const P = chVis()[0]; return [CH.sym, P.tf, P.t.length, (CH.ind||[]).map(I => I.type).join(',')]; }"))
        # real forex has a weekend gap: cut ~2 days out of the middle and re-set the data
        print("gap:", await q("() => { const P = chVis()[0], n = P.t.length, a = n - 300, b = a + 190; ['t','o','h','l','c','v'].forEach(f => P[f].splice(a, b - a)); chSetData(P); chDirty = true; return [n, P.t.length]; }"))
        await asyncio.sleep(0.5)
        host = await pg.query_selector("#dChartHost .chpane")
        bb = await host.bounding_box(); cx, cy = bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] * 0.35
        await pg.screenshot(path=f"{OUT}/scroll0.png")
        # wheel scroll horizontally / zoom, then drag into the future and the past
        await pg.mouse.move(cx, cy)
        for _ in range(6): await pg.mouse.wheel(0, 300); await asyncio.sleep(0.05)
        await asyncio.sleep(0.6); await pg.screenshot(path=f"{OUT}/scroll1.png")
        await pg.mouse.down(); await pg.mouse.move(cx - 600, cy, steps=12); await pg.mouse.up(); await asyncio.sleep(0.6)
        await pg.screenshot(path=f"{OUT}/scroll2.png")
        print("range after drag left:", await q("() => JSON.stringify(chVis()[0].chart.timeScale().getVisibleLogicalRange())"))
        await pg.mouse.move(cx - 300, cy); await pg.mouse.down(); await pg.mouse.move(cx + 300, cy, steps=20); await pg.mouse.up(); await asyncio.sleep(0.6)
        await pg.mouse.move(cx - 300, cy); await pg.mouse.down(); await pg.mouse.move(cx + 300, cy, steps=20); await pg.mouse.up(); await asyncio.sleep(0.6)
        await pg.mouse.move(cx, cy)
        await pg.screenshot(path=f"{OUT}/scroll3.png")
        for _ in range(40): await pg.mouse.wheel(14, 9); await asyncio.sleep(0.016)
        await asyncio.sleep(0.4); await pg.screenshot(path=f"{OUT}/scroll3b.png")
        for _ in range(40): await pg.mouse.wheel(-20, -3); await asyncio.sleep(0.016)
        await asyncio.sleep(0.6); await pg.screenshot(path=f"{OUT}/scroll4.png")
        print("range:", await q("() => JSON.stringify(chVis()[0].chart.timeScale().getVisibleLogicalRange())"))
        for k in range(5):
            await pg.mouse.move(cx + 200, cy); await pg.mouse.down(); await pg.mouse.move(cx - 500, cy, steps=10); await pg.mouse.up(); await asyncio.sleep(0.3)
        await asyncio.sleep(0.5); await pg.screenshot(path=f"{OUT}/scroll5.png")
        print("far right:", await q("() => { const P = chVis()[0]; const r = P.chart.timeScale().getVisibleLogicalRange(); return JSON.stringify([r, P.t.length, P.cs.priceToCoordinate(P.c.at(-1)), P.cs.priceScale().width()]); }"))
        await q("() => { const P = chVis()[0]; P.chart.timeScale().setVisibleLogicalRange({ from: P.t.length + 20, to: P.t.length + 120 }); }"); await asyncio.sleep(0.6)
        await pg.screenshot(path=f"{OUT}/scroll6.png")
        print("past end:", await q("() => { const P = chVis()[0]; const r = P.chart.timeScale().getVisibleLogicalRange(); const I = Object.values(P.ix).find(x => x.pane); const s = I && Object.values(I.ser)[0]; return JSON.stringify([r, P.cs.priceToCoordinate(P.c.at(-1)), s && s.priceToCoordinate(70), s && s.priceToCoordinate(30)]); }"))
        n0 = await q("() => chVis()[0].t.length")
        await q("() => { const P = chVis()[0]; P.userAt = Date.now(); P.chart.timeScale().setVisibleLogicalRange({ from: 5, to: 120 }); }"); await asyncio.sleep(3)
        print("older history:", n0, "→", await q("() => { const P = chVis()[0]; const r = P.chart.timeScale().getVisibleLogicalRange(); return JSON.stringify([P.t.length, Math.round(r.from), Math.round(r.to), P.t.every((t, i) => !i || t > P.t[i - 1]), (CH.ind||[]).length]); }"))
        await pg.screenshot(path=f"{OUT}/scroll_older.png")
        for nm, a, z in [("left", -300, -40), ("leftedge", -200, 6), ("future", 309 + 30, 309 + 300)]:
            await q(f"() => {{ const P = chVis()[0]; P.chart.timeScale().setVisibleLogicalRange({{ from: {a}, to: {z} }}); chDirty = true; }}"); await asyncio.sleep(0.6)
            await pg.screenshot(path=f"{OUT}/scroll_{nm}.png")
            print(nm, await q("() => { const P = chVis()[0]; const I = Object.values(P.ix).find(x => x.pane); const s = I && Object.values(I.ser)[0]; return JSON.stringify([P.chart.timeScale().getVisibleLogicalRange(), P.cs.priceToCoordinate(P.c.at(-1)), s && s.priceToCoordinate(70), s && s.priceToCoordinate(30), chPlotH(P)]); }"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
