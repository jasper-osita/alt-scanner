import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "mob")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(**pw.devices["iPhone 13"], color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js); shot = lambda n: pg.screenshot(path=f"{OUT}/{n}.png")
        await q("() => { ncClearToasts(); }")
        # More sheet, ⋯ menu, scan settings
        await pg.tap('#mTab [data-mgo="more"]'); await asyncio.sleep(0.3); await shot("m_more")
        print("1) more sheet open:", await q("() => document.body.classList.contains('mnavopen')"), "| items:", await q("() => document.querySelectorAll('#side .nav').length"))
        await pg.tap('#side [data-go="momentum"]'); await asyncio.sleep(0.4); print("   went to:", await q("() => page"), "| sheet closed:", await q("() => !document.body.classList.contains('mnavopen')"))
        await pg.tap("#mMore"); await asyncio.sleep(0.3); await shot("m_menu"); print("2) ⋯ menu:", await q("() => [...document.querySelectorAll('#chMenu [data-mk] .ml')].map(e => e.textContent).join(' | ')"))
        await pg.tap('#chMenu [data-mk="settings"]'); await asyncio.sleep(0.3); await shot("m_settings"); print("   settings open:", await q("() => document.body.classList.contains('pillsopen')"))
        await pg.tap("#pillSum")
        # coin panel
        await q("() => openDetail(data.day[0].symbol)"); await asyncio.sleep(2); await shot("m_detail")
        print("3) detail width:", await q("() => { const r = document.getElementById('dlg').getBoundingClientRect(); return Math.round(r.left) + '-' + Math.round(r.right) + ' sw ' + document.documentElement.scrollWidth; }"))
        await q("() => document.getElementById('dlg').close()")
        # charts on a phone
        await pg.tap('#mTab [data-mgo="charts"]'); await asyncio.sleep(3); await shot("m_charts")
        print("4) charts:", await q("() => CH.layout + ' wl ' + CH.wl + ' panes ' + chVis().map(P => P.tf + ' ' + Math.round(P.cv.clientWidth) + 'x' + Math.round(P.cv.clientHeight)).join(',')"))
        await pg.tap('#chTools [data-garr="lines"]'); await asyncio.sleep(0.3); await shot("m_flyout")
        print("   flyout:", await q("() => { const r = document.getElementById('chMenu').getBoundingClientRect(); return Math.round(r.left) + ',' + Math.round(r.top) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height); }"))
        await pg.tap('#chMenu [data-mk="trend"]'); await asyncio.sleep(0.2)
        bx = await pg.locator(f"#chCv{await q('() => chVis()[0].i')}").bounding_box()
        await pg.touchscreen.tap(bx["x"] + bx["width"] * 0.3, bx["y"] + bx["height"] * 0.5); await asyncio.sleep(0.2)
        await pg.touchscreen.tap(bx["x"] + bx["width"] * 0.65, bx["y"] + bx["height"] * 0.3); await asyncio.sleep(0.4)
        print("5) touch trend:", await q("() => chList().length + ' drawing, selected ' + !!chSelD() + ', tool ' + chTool"))
        await shot("m_drawsel")
        print("   float bar:", await q("() => { const r = document.getElementById('chFloat').getBoundingClientRect(); return Math.round(r.left) + '-' + Math.round(r.right) + ' visible ' + !document.getElementById('chFloat').hidden; }"))
        await pg.tap('#chFloat [data-fl="c"]'); await asyncio.sleep(0.3); await shot("m_color"); await pg.tap('#chColPop [data-pc="#f23645"]'); await q("() => chColorClose()")
        await pg.tap('#chFloat [data-fl="set"]'); await asyncio.sleep(0.3); await shot("m_drawset"); await q("() => chModalClose()")
        await pg.tap("#chIndBtn"); await asyncio.sleep(0.4); await shot("m_inddlg")
        print("6) indicators dialog:", await q("() => { const r = document.querySelector('.chmod').getBoundingClientRect(); return Math.round(r.width) + 'x' + Math.round(r.height); }"))
        await q("() => chModalClose()")
        # touch: tap a line to select, drag it with a finger
        await q("() => { chSel = null; chSelBar(); }")
        mid = await q("() => { const P = chVis()[0], d = chList()[0], r = P.cv.getBoundingClientRect(); return [r.left + (chX(P, d.pts[0].t) + chX(P, d.pts[1].t)) / 2, r.top + (chY(P, d.pts[0].p) + chY(P, d.pts[1].p)) / 2 + 7]; }")
        await pg.touchscreen.tap(mid[0], mid[1]); await asyncio.sleep(0.3)
        print("7) tap 7px off the line selects:", await q("() => !!chSelD()"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
