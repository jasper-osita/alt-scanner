import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# No scrollbars on the drawing toolbar or the boards: an overview chart grows to fit its toolbar, the Charts page shrinks the buttons a little,
# and a wide table shrinks to fit its box instead of scrolling sideways.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 700}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await ready(pg); q = lambda js: pg.evaluate(js)
        T = "() => { const T = document.getElementById('chTools'); return [T.scrollHeight, T.clientHeight, T.scrollHeight <= T.clientHeight + 1, getComputedStyle(T.querySelector('.chtb')).height]; }"
        await q("() => goPage('charts')"); await asyncio.sleep(3)
        print("1) charts, short window: [content, box, fits, button]", await q(T))
        await pg.set_viewport_size({"width": 1440, "height": 1000}); await asyncio.sleep(1)
        print("2) taller window, full-size buttons:", await q(T))
        await q("() => goPage('overview')"); await asyncio.sleep(3)
        await q("() => { const h = document.querySelector('.ovchost'); h.style.height = '430px'; window.dispatchEvent(new Event('resize')); }"); await asyncio.sleep(1)
        print("3) overview chart squeezed → grows to fit:", await q(T), await q("() => document.querySelector('.ovchost').style.height"))
        await q("() => goPage('momentum')"); await asyncio.sleep(1)
        await pg.set_viewport_size({"width": 1000, "height": 900}); await asyncio.sleep(1.5)
        W = "() => [...document.querySelectorAll('.tablewrap')].filter(w => w.offsetParent).map(w => [w.scrollWidth <= w.clientWidth + 1, w.querySelector('table') && w.querySelector('table').style.zoom || '1'])"
        print("4) boards at 1000px wide: [fits, zoom]", await q(W), await q("() => [...document.querySelectorAll('.tablewrap')].filter(w => w.offsetParent).map(w => (w.scrollWidth / w.clientWidth).toFixed(2))"))
        await pg.set_viewport_size({"width": 1280, "height": 800}); await asyncio.sleep(1.5)
        print("4c) boards at 1280px wide:", await q(W))
        el = await pg.query_selector(".tablewrap >> visible=true"); await el.screenshot(path=__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "fit_board.png"))
        print("4d) columns:", await q("() => { const w = [...document.querySelectorAll('.tablewrap')].find(w => w.offsetParent), t = w.querySelector('table'); t.style.zoom = ''; const r = [w.clientWidth, w.scrollWidth, [...t.tHead.rows[0].cells].map(c => c.innerText.replace(/\\s+/g, ' ') + ':' + Math.round(c.getBoundingClientRect().width)).join(' | ')]; t.dataset.fit = ''; return r; }"))
        await pg.set_viewport_size({"width": 1600, "height": 900}); await asyncio.sleep(1.5)
        print("4b) natural:", await q("() => [...document.querySelectorAll('.tablewrap')].filter(w => w.offsetParent).map(w => { const t = w.querySelector('table'); const z = t.style.zoom; t.style.zoom = ''; const r = [w.clientWidth, w.scrollWidth, t.offsetWidth, w.className, t.className, w.parentElement.className]; t.style.zoom = z; return r; })"))
        print("5) wide window, back to full size:", await q(W))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
