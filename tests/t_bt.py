import asyncio, json, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        await pg.evaluate("() => goPage('backtest')")
        await pg.select_option("#btCoins", "20"); await pg.select_option("#btDays", "30")
        t0 = time.time(); await pg.click("#btRun")
        for _ in range(500):
            if await pg.evaluate("() => !btRunning && !!BT"): break
            await asyncio.sleep(0.5)
        print(f"backtest {time.time()-t0:.0f}s:", await pg.evaluate("() => BT.trades.length + ' trades'"),
              "| rotation tags:", await pg.evaluate("() => JSON.stringify(Object.fromEntries(Object.entries(btGroup(BT.trades, t => t.rot)).map(([k, v]) => [k, v.length])))"))
        print("OB trades:", await pg.evaluate("() => { const s = btStats(BT.trades.filter(t => t.model === 'OB')); return s ? s.n + ' trades, win ' + s.win.toFixed(0) + '%, avg ' + s.avg.toFixed(2) + 'R' : 'none'; }")); print("Ignition trades:", await pg.evaluate("() => { const s = btStats(BT.trades.filter(t => t.model === 'Ignite')); return s ? s.n + ' trades, win ' + s.win.toFixed(0) + '%, avg ' + s.avg.toFixed(2) + 'R' : 'none'; }"))
        await pg.click('[data-bv="rot"]'); await asyncio.sleep(0.4)
        print("view:", await pg.evaluate("() => [...document.querySelectorAll('#backtest table thead th')].map(t => t.innerText).join(' | ')"))
        print("rows:", await pg.evaluate("() => [...document.querySelectorAll('#backtest table tbody tr')].map(t => t.innerText.replace(/\\s+/g, ' ')).join(' || ')"))
        await pg.evaluate("() => document.getElementById('backtest').scrollIntoView()"); await asyncio.sleep(0.3); await pg.screenshot(path="bt_rot.png")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
