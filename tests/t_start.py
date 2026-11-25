"""Opening the app lands on Charts (built and loaded); a link with a page keeps that page."""
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
        print("1) fresh open:", await q("() => page + ' ' + location.hash"), "| charts loaded:", await charts_ok(), "| title:", await q("() => document.getElementById('pageTitle').textContent"))
        await q("() => goPage('day')"); await pg.goto("http://localhost:8765/"); await asyncio.sleep(0.5)
        print("2) last page was Day Trade, open the app:", await q("() => page"), "| charts loaded:", await charts_ok())
        await pg.goto("http://localhost:8765/#fund"); await pg.reload(); await asyncio.sleep(0.5)
        print("3) link to #fund:", await q("() => page"))
        await q("() => goPage('swing')"); await pg.reload(); await asyncio.sleep(0.5)
        print("4) refresh on Swing stays:", await q("() => page"))
        await pg.click(".side .brand"); await asyncio.sleep(0.5)
        print("5) logo:", await q("() => page"), "| charts loaded:", await charts_ok())
        print("errors:", errs[:4] or "none")
        await b.close()
asyncio.run(main())
