import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
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
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macroov'); macroScan(true); }")
        print("loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)"))
        await wait("() => !XCH.busy && Object.keys(XCH.charts).length >= 2", 60); await asyncio.sleep(1)
        st = "() => [...document.querySelectorAll('.xch')].map(c => c.dataset.xk + ': ' + c.querySelector('.xchsrc').textContent + ' | ' + c.querySelector('.xchst').innerText.replace(/\\s+/g, ' ') + (c.querySelector('.empty') ? ' | ' + c.querySelector('.empty').innerText : '')).join('\\n')"
        print("cards:\n" + await q(st))
        print("index tabs:", await q("() => document.getElementById('xchIdx').innerText.replace(/\\s+/g, ' ')"), "| chips:", await q("() => document.querySelector('.xchidx').innerText.replace(/\\s+/g, ' ').slice(0, 160)"))
        await q("() => document.querySelector('#xchTf [data-tf=\"4h\"]').click()"); await asyncio.sleep(0.5); await wait("() => !XCH.busy", 30)
        await q("() => document.querySelector('#xchIdx [data-ix=\"S&P 500\"]').click()"); await asyncio.sleep(0.5); await wait("() => !XCH.busy", 30); await asyncio.sleep(0.5)
        print("after 4H + S&P:\n" + await q(st))
        print("saved:", await q("() => [lsGet('finder-xch-tf'), lsGet('finder-xch-idx')]"))
        el = await pg.query_selector(".xchsec:not(.cchsec)"); await el.screenshot(path=f"{OUT}/xcharts.png")
        await q("() => document.querySelector('.xch[data-xk=\"gold\"] .xchc').click()"); await asyncio.sleep(2)
        print("click shows it in the main chart:", await q("() => [document.getElementById('dlg').open, OVC.on, chName(CHP[OVC.act].psym)]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
