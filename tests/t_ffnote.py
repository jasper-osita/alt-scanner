import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# The Filters button is off the top bar; the panel opens from Screener → Filters & Templates. A filter that's on shows as a note on the
# coin table with Edit and Clear, and the panel closes when you leave All Coins.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        print("1) top-bar button hidden:", await q("() => document.getElementById('fToggle').hidden && !document.getElementById('fToggle').offsetParent"))
        await q("() => goPage('screener')"); await asyncio.sleep(0.5)
        print("2) no filter:", await q("() => document.getElementById('count').innerText"))
        await q("() => { FS.filters = [{ kind: 'model', model: 'NBB', stage: 'any', dir: 'Long' }]; filtersChanged(true); }"); await asyncio.sleep(0.6)
        print("3) note:", await q("() => document.getElementById('count').innerText.replace(/\\s+/g, ' ')"))
        await q("() => document.querySelector('#count [data-ff=\"edit\"]').click()"); await asyncio.sleep(0.3)
        print("4) Edit opens the panel:", await q("() => document.body.classList.contains('fopen')"))
        await q("() => goPage('overview')"); await asyncio.sleep(0.3)
        print("5) leaving All Coins closes it:", await q("() => !document.body.classList.contains('fopen')"))
        await q("() => goPage('filters')"); await asyncio.sleep(0.3)
        print("6) menu item opens it on All Coins:", await q("() => [page, document.body.classList.contains('fopen')]"))
        await q("() => document.querySelector('#count [data-ff=\"clear\"]').click()"); await asyncio.sleep(0.6)
        print("7) Clear:", await q("() => [FS.filters.length, document.getElementById('count').innerText]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
