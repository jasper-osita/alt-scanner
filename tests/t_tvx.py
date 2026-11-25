"""TradingView-style chart extras: chart types, chart alerts, bar replay, compare, object tree, data window, snapshot, scripts."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: ("Content Security Policy" in m.text and csp.append(m.text[:140])) or (m.type == "error" and "Failed to load resource" not in m.text and errs.append("console: " + m.text[:160])))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        # ---- chart types
        await pg.click("#chTypeBtn"); print("1) type menu:", await q("() => [...document.querySelectorAll('#chMenu [data-mk]')].map(b => b.dataset.mk + (b.classList.contains('on') ? '*' : '')).join(' ')"))
        for k in ["hollow", "ha", "bars", "line", "area", "base", "candles"]:
            if await q("() => !!document.getElementById('chMenu')"): await pg.click(f'#chMenu [data-mk="{k}"]')
            else: await q(f"() => chSetType('{k}')")
            await asyncio.sleep(0.15)
            print(f"   {k}:", await q("() => CHP.map(P => P.cs.seriesType() + ':' + P.cs.data().length + '/' + P.t.length).join(' ')"),
                  "| legend:", await q("() => document.getElementById('chLeg1').innerText.replace(/\\s+/g, ' ').slice(0, 90)"))
            if k == "ha": print("   HA check (o = avg prev o/c, c = ohlc/4):", await q("() => { const P = CHP[1], a = P.ha, i = 100, d = P.cs.data()[i]; return Math.abs(a.o[i] - (a.o[i-1] + a.c[i-1]) / 2) < 1e-9 && Math.abs(a.c[i] - (P.o[i] + P.h[i] + P.l[i] + P.c[i]) / 4) < 1e-9 && d.close === a.c[i]; }"))
            if k == "base": await pg.screenshot(path=f"{OUT}/tvx_base.png")
        await q("() => chSetType('ha')"); await q("() => { const P = CHP[1], n = P.t.length; chBar(P, { t: P.t[n - 1], o: P.o[n - 1], h: P.h[n - 1] * 1.01, l: P.l[n - 1], c: P.h[n - 1] * 1.005, v: 1 }); }")
        print("   HA live bar:", await q("() => { const P = CHP[1], n = P.t.length, d = P.cs.data().at(-1); return d.close === P.ha.c[n - 1] && P.ha.c.length === n; }"))
        await pg.reload(); await ready(pg); await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => typeof CHP !== 'undefined' && CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("   after reload:", await q("() => CH.ctype + ' ' + CHP.map(P => P.csType + ':' + P.cs.seriesType()).join(',')"))
        await q("() => chSetType('candles')")
        print("CSP:", csp[:3] or "none", "| errors:", errs[:5] or "none")
        await b.close()
asyncio.run(main())
