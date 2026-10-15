import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('overview')")
        for _ in range(60):
            if await q("() => !CCH.busy && ['c_eth','c_ethbtc'].every(k => XCH.charts[k]) && OVC.on === 'c' && CHP[0].t.length > 50"): break
            await asyncio.sleep(0.5)
        st = "() => [...document.querySelectorAll('.cchsec .xch')].map(c => c.dataset.ck + ': ' + c.querySelector('.xchst').innerText.replace(/\\s+/g, ' ') + ((c.querySelector('.xchnote') || {}).innerText ? ' | ' + c.querySelector('.xchnote').innerText : '') + (c.querySelector('.empty') ? ' | ' + c.querySelector('.empty').innerText : '')).join('\\n')"
        print("cards:\n" + await q(st))
        print("main chart:", await q("() => [OVC.on, CH.sym, CHP[0].tf, CHP[0].t.length, document.getElementById('ovBtcSt').innerText.replace(/\\s+/g, ' ')]"))
        await q("() => document.querySelector('#cchTf [data-tf=\"4h\"]').click()"); await asyncio.sleep(1)
        for _ in range(40):
            if await q("() => !CCH.busy"): break
            await asyncio.sleep(0.5)
        print("4H:\n" + await q(st))
        el = await pg.query_selector(".cchsec"); await el.screenshot(path=f"{OUT}/cch.png")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
