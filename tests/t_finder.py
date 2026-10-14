import asyncio, sys, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
PAGES = ["overview", "playbook", "momentum", "day", "swing", "aots", "sessions", "screener", "watch", "bots", "scorecard", "backtest", "guide"]
async def main():
    import os; os.makedirs(OUT, exist_ok=True)
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload()
        await asyncio.sleep(1.5)
        print("during scan side status:", await pg.evaluate("() => document.getElementById('sideStatus').textContent.slice(0,80) + ' | prog ' + document.getElementById('sideProg').style.width"))
        ok = await ready(pg); print("scan ok:", ok)
        print("font:", await pg.evaluate("() => document.fonts.check('14px \"Space Grotesk\"')"), "| bg:", await pg.evaluate("() => getComputedStyle(document.body).backgroundColor"), "| title:", await pg.title())
        print("badges:", await pg.evaluate("() => [...document.querySelectorAll('.nav')].map(n => n.dataset.go + '=' + n.querySelector('.nb').textContent).join('  ')"))
        for p in PAGES:
            await pg.evaluate(f"() => goPage('{p}')"); await asyncio.sleep(0.5)
            vis = await pg.evaluate("() => [...document.querySelectorAll('main [data-page], footer[data-page]')].filter(e => e.offsetParent !== null || getComputedStyle(e).display !== 'none' && e.getClientRects().length).map(e => e.id || e.className.split(' ').slice(0,2).join('.')).join(', ')")
            info = await pg.evaluate("() => ({ h: location.hash, h1: document.getElementById('pageTitle').textContent, tab: tab, on: document.querySelector('.nav.on').dataset.go, height: document.documentElement.scrollHeight })")
            print(f"{p:10s} -> {info} | visible: {vis}")
            await pg.screenshot(path=f"{OUT}/{p}.png")
        # filters item opens the panel on the screener page
        await pg.click('.nav[data-go="filters"]'); await asyncio.sleep(0.4)
        print("filters:", await pg.evaluate("() => ({ page, fopen: document.body.classList.contains('fopen'), hash: location.hash })"))
        await pg.screenshot(path=f"{OUT}/filters.png")
        await pg.click("#fClose"); await asyncio.sleep(0.2)
        # click flows on their pages
        await pg.click('.nav[data-go="backtest"]'); await asyncio.sleep(0.2); await pg.click("#btRun")
        await pg.click('.nav[data-go="bots"]'); await asyncio.sleep(0.2); await pg.click("#botRun"); await asyncio.sleep(1)
        await pg.click('.nav[data-go="momentum"]'); await asyncio.sleep(0.3)
        r = await pg.query_selector("#momoBoard .row")
        if r: await r.click(); await asyncio.sleep(1.2); print("popup open:", await pg.evaluate("() => document.getElementById('dlg').open")); await pg.screenshot(path=f"{OUT}/popup.png"); await pg.keyboard.press("Escape")
        # hash routing + reload persistence
        await pg.goto("http://localhost:8765/#swing"); await asyncio.sleep(1.5)
        print("deep link:", await pg.evaluate("() => page + ' ' + document.querySelector('.nav.on').dataset.go"))
        await pg.goto("http://localhost:8765/"); await asyncio.sleep(1.5)
        print("remembered:", await pg.evaluate("() => page"))
        # phone width
        await pg.set_viewport_size({"width": 390, "height": 844}); await pg.evaluate("() => goPage('momentum')"); await asyncio.sleep(0.5)
        print("mobile overflow:", await pg.evaluate("() => document.documentElement.scrollWidth - innerWidth"))
        await pg.screenshot(path=f"{OUT}/mobile.png")
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
