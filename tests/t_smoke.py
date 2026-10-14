import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload()
        ok = await ready(pg)
        print("scan ok:", ok, "|", await pg.evaluate("() => data && (data.analysed + ' coins · ' + data.env.label + ' · day ' + data.day.length + ' · swing ' + data.swing.length)"),
              "| status:", await pg.evaluate("() => document.getElementById('status').textContent"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
