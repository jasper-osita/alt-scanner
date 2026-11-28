"""Opening the app the first time lands on Charts (built and loaded); after that on the last tab you had open; a link with a page keeps that page."""
import asyncio, sys, os, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
print = functools.partial(print, flush=True)
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}); await setup(ctx, start=None)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        q = lambda js: pg.evaluate(js)
        async def charts_ok():
            for _ in range(60):
                if await q("() => typeof CHP !== 'undefined' && CHP.length === 4 && chVis().every(P => P.t.length > 0)"): return True
                await asyncio.sleep(0.25)
            return False
        await pg.goto("http://localhost:8765/"); await q("() => localStorage.clear()"); await pg.goto("http://localhost:8765/")
        def want(name, got, exp):
            if got != exp: errs.append(f"{name}: {got} (wanted {exp})")
        r = [await q("() => page + ' ' + location.hash"), await charts_ok()]
        print("1) fresh open:", r[0], "| charts loaded:", r[1], "| title:", await q("() => document.getElementById('pageTitle').textContent")); want("fresh open", r, ["charts #charts", True])
        await q("() => goPage('day')"); await pg.goto("http://localhost:8765/"); await asyncio.sleep(0.5)
        r = await q("() => page"); print("2) last tab was Day Trade, open the app:", r); want("opens on the last tab", r, "day")
        await pg.goto("http://localhost:8765/#fund"); await pg.reload(); await asyncio.sleep(0.5)
        r = await q("() => page"); print("3) link to #fund:", r); want("link to #fund", r, "fund")
        await q("() => goPage('swing')"); await pg.reload(); await asyncio.sleep(0.5)
        r = await q("() => page"); print("4) refresh on Swing stays:", r); want("refresh on Swing", r, "swing")
        await pg.click("#tabRow .tbtab >> nth=0"); await asyncio.sleep(0.5)
        r = [await q("() => page"), await charts_ok()]; print("5) the chart tab:", r[0], "| charts loaded:", r[1]); want("chart tab", r, ["charts", True])
        print("errors:", errs[:4] or "none")
        await b.close()
asyncio.run(main())
