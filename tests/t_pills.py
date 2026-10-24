import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# The scan settings bar (exchange, market, direction, quote, volume, MAs, wicks, rating, alts, charts, search) shows only on pages it affects.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        shown, hidden = [], []
        for p in await q("() => Object.keys(PAGE_INFO).filter(k => k !== 'filters')"):
            await q(f"() => goPage('{p}')"); await asyncio.sleep(0.15)
            (shown if await q("() => !!document.querySelector('.pills').offsetParent") else hidden).append(p)
        print("shown on:", " ".join(shown)); print("hidden on:", " ".join(hidden))
        await q("() => goPage('screener')"); await asyncio.sleep(0.3); c = await q("() => document.querySelector('#tbody tr[data-s]').dataset.s")
        await pg.fill("#search", c); await asyncio.sleep(0.5)
        print("search still works:", await q(f"() => [...document.querySelectorAll('#tbody tr[data-s]')].every(tr => tr.dataset.s.includes('{c}'))"), c)
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
