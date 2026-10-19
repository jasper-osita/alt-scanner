import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# Economic calendar: List, Week and Month views, moving between weeks and months, a month day opening its week, both tabs.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx); await setup_extra(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=20):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        await q("() => { CALF = { ...CALF_DEF, imp: ['High', 'Medium', 'Low', 'Holiday'] }; goPage('calendar'); }")
        await wait("() => document.querySelector('#calBody .caltbl')")
        print("0) data:", await q("() => [calAll().length, CAL.err, CALF.view, document.getElementById('calBody').innerText.slice(0, 120)]"))
        n = await q("() => document.querySelectorAll('#calBody .caltbl tbody tr:not(.calday)').length")
        print("1) list rows:", n, "| buttons:", await q("() => [...document.querySelectorAll('#calViews [data-cv]')].map(b => b.textContent + (b.classList.contains('on') ? '*' : '')).join(' ')"))
        await q("() => document.querySelector('#calViews [data-cv=\"week\"]').click()"); await asyncio.sleep(0.4)
        W = "() => [document.querySelector('.calnav b').textContent, document.querySelectorAll('#calBody .calcell').length, document.querySelectorAll('#calBody .calev').length, !!document.querySelector('#calBody .calcell.today'), document.querySelector('#calBody .calgrid').classList.contains('calwk')]"
        print("2) week:", await q(W), "| saved:", await q("() => JSON.parse(localStorage.getItem('finder-cal-view')).mode"))
        print("2b) an event:", await q("() => { const e = document.querySelector('#calBody .calev'); return [e.innerText.replace(/\\s+/g, ' '), e.title.split('\\n').length > 1]; }"))
        el = await pg.query_selector(".calcard"); await el.screenshot(path=f"{OUT}/cal_week.png")
        await q("() => document.querySelector('[data-cvn=\"1\"]').click()"); await asyncio.sleep(0.3); print("3) next week:", await q(W))
        await q("() => document.querySelector('[data-cvn=\"0\"]').click()"); await asyncio.sleep(0.3)
        await q("() => document.querySelector('#calViews [data-cv=\"month\"]').click()"); await asyncio.sleep(0.4)
        print("4) month:", await q(W), "| out-of-month days:", await q("() => document.querySelectorAll('#calBody .calcell.out').length"))
        el = await pg.query_selector(".calcard"); await el.screenshot(path=f"{OUT}/cal_month.png")
        await q("() => document.querySelector('[data-cvn=\"-1\"]').click()"); await asyncio.sleep(0.3); print("5) last month:", await q("() => document.querySelector('.calnav b').textContent"))
        await q("() => document.querySelector('[data-cvn=\"0\"]').click()"); await asyncio.sleep(0.3)
        await q("() => document.querySelector('#calBody .calcell.today').click()"); await asyncio.sleep(0.3)
        print("6) day → its week:", await q("() => [CALV.mode, CALV.off, !!document.querySelector('#calBody .calcell.today')]"))
        await q("() => document.querySelector('#calTabs [data-ct=\"idx\"]').click()"); await wait("() => document.querySelector('#calBody .calgrid')", 20); await asyncio.sleep(1)
        print("7) Nasdaq tab, week:", await q(W))
        await q("() => document.querySelector('#calViews [data-cv=\"list\"]').click()"); await asyncio.sleep(1)
        print("8) back to list:", await q("() => [CALV.mode, !!document.querySelector('#calBody .caltbl') || !!document.querySelector('#calBody .empty')]"))
        await pg.set_viewport_size({"width": 420, "height": 900}); await q("() => document.querySelector('#calViews [data-cv=\"week\"]').click()"); await asyncio.sleep(0.4)
        print("9) phone width, no side scroll:", await q("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
