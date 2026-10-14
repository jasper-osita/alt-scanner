import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "mob"); import os; os.makedirs(OUT, exist_ok=True)
PAGES = sys.argv[1].split(",") if len(sys.argv) > 1 else ["overview", "playbook", "charts", "momentum", "day", "swing", "aots", "sessions", "macro", "screener", "watch", "bots", "scorecard", "backtest", "guide"]
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        dev = pw.devices["iPhone 13"]
        ctx = await b.new_context(**dev, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        for p in PAGES:
            await q(f"() => goPage('{p}')"); await asyncio.sleep(2.5 if p == "charts" else 1.2)
            ov = await q("() => { const W = document.documentElement.clientWidth; const bad = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > W + 1 && getComputedStyle(e).position !== 'fixed' && !e.closest('[hidden]') && e.offsetParent !== null && !e.closest('.chcv,.tbl-wrap,.scroll-x') ; }).slice(0, 6).map(e => (e.id ? '#' + e.id : '') + '.' + String(e.className).split(' ')[0] + ':' + Math.round(e.getBoundingClientRect().right)); return { sw: document.documentElement.scrollWidth, W, bad }; }")
            print(p, ov)
            await pg.screenshot(path=f"{OUT}/{p}.png", full_page=False)
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
