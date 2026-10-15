import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# A forex chart opened before the cTrader price link is up: the chart starts the link and loads once it's ready
# (it used to stop at "Connect cTrader (Forex, Gold & Indices page) to chart forex").
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/")
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok', prefer: false })); localStorage.setItem('finder-charts', JSON.stringify({ sym: 'CT:EURUSD', layout: '1', tfs: ['1h', '1h', '15m', '5m'] })); localStorage.setItem('finder-page', 'charts'); }")
        await pg.goto("http://localhost:8765/#charts"); await pg.reload(); await asyncio.sleep(0.8)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('charts')"); await asyncio.sleep(1.2)
        print("1) first message:", await q("() => chVis()[0].msg.textContent"))
        for _ in range(60):
            if await q("() => chVis()[0].sym === 'CT:EURUSD' && chVis()[0].t.length > 100 && chVis()[0].msg.hidden"): break
            await asyncio.sleep(0.5)
        print("2) loaded: [cTrader, sym, bars>100, message hidden]", await q("() => [CT.state, chVis()[0].sym, chVis()[0].t.length > 100, chVis()[0].msg.hidden]"))
        await q("() => chSetSym('CT:NOPEXYZ')"); await asyncio.sleep(2)
        print("3) not on the account:", await q("() => chVis()[0].msg.textContent"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
